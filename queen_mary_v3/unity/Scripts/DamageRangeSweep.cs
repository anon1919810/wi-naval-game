using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Naval.DamageLab;
// Note: keep this type UnityEngine-free so sweeps stay testable as pure data.

namespace Naval.DamageLab
{
    /// <summary>
    /// Deterministic parameter sweeps for the damage-range experimental solver.
    /// Pure data: no scene, no rendering. Not historical ballistics.
    /// </summary>
    public static class DamageRangeSweep
    {
        public sealed class Row
        {
            public string campaign;
            public string caseId;
            public RangeConfig config;
            public RangeReport report;
            public string outcome;
            public float boiler, engine, pump;
            public int events, fragments, fragmentEscapes;
            public bool deterministicOk = true;
        }

        public sealed class CampaignResult
        {
            public string name;
            public int cases;
            public int stopped, penetrated, detonated, exited;
            public float meanDurationMs;
            public List<Row> rows = new List<Row>();
        }

        public sealed class SweepReport
        {
            public string runId;
            public string utc;
            public string solverModel = "experimental-resistance-v1";
            public bool historicallyCertified = false;
            public List<CampaignResult> campaigns = new List<CampaignResult>();
            public List<string> findings = new List<string>();
            public int totalCases;
        }

        static RangeConfig Base()
        {
            return new RangeConfig(); // defaults from DamageRangeModel
        }

        static Row Fire(string campaign, string caseId, RangeConfig cfg)
        {
            var c = cfg.Copy();
            var r = RangeSolver.Fire(c);
            var row = new Row
            {
                campaign = campaign,
                caseId = caseId,
                config = c,
                report = r,
                outcome = r.exploded && r.stopped ? "stopped+det"
                         : r.exploded ? "detonated"
                         : r.stopped ? "stopped" : "exited",
                events = r.events.Count,
                fragments = r.fragments.Count,
            };
            foreach (var f in r.fragments) if (f.hit == "escape" || f.hit == "Section") row.fragmentEscapes++;
            foreach (var m in r.modules)
            {
                if (m.id == "Boiler_Room_1") row.boiler = m.damage;
                else if (m.id == "Engine_Room_1") row.engine = m.damage;
                else if (m.id == "Feed_Pump") row.pump = m.damage;
            }
            // Same-seed replay must match (solver contract).
            var again = RangeSolver.Fire(c);
            if (again.Signature() != r.Signature()) row.deterministicOk = false;
            return row;
        }

        public static SweepReport RunAll()
        {
            var report = new SweepReport
            {
                runId = DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ"),
                utc = DateTime.UtcNow.ToString("o"),
            };

            // C1: armour × speed × incidence
            var c1 = new CampaignResult { name = "C1_armour_speed_angle" };
            float[] outers = { 0, 90, 180, 229, 300, 600 };
            float[] speeds = { 200, 400, 600, 800 };
            float[] angles = { 0, 10, 20, 30 };
            foreach (var o in outers)
            foreach (var s in speeds)
            foreach (var a in angles)
            {
                var cfg = Base();
                cfg.outerMm = o; cfg.speed = s; cfg.angleDeg = a;
                cfg.innerMm = 25; cfg.rearMm = 40; cfg.fuseMode = 1;
                c1.rows.Add(Fire(c1.name, string.Format(CultureInfo.InvariantCulture,
                    "O{0}_S{1}_A{2}", o, s, a), cfg));
            }
            Summarize(c1); report.campaigns.Add(c1);

            // C2: three-layer armour grid at 600 m/s
            var c2 = new CampaignResult { name = "C2_multilayer" };
            foreach (var o in new[] { 0f, 100f, 229f })
            foreach (var i in new[] { 0f, 25f, 102f })
            foreach (var rr in new[] { 0f, 40f, 102f })
            {
                var cfg = Base();
                cfg.outerMm = o; cfg.innerMm = i; cfg.rearMm = rr;
                cfg.speed = 600; cfg.fuseMode = 1; cfg.fuseDelay = 0.012f;
                c2.rows.Add(Fire(c2.name, string.Format(CultureInfo.InvariantCulture,
                    "O{0}_I{1}_R{2}", o, i, rr), cfg));
            }
            Summarize(c2); report.campaigns.Add(c2);

            // C3: fuse behaviour
            var c3 = new CampaignResult { name = "C3_fuse" };
            foreach (var mode in new[] { 0, 1, 2 })
            foreach (var delay in new[] { 0f, 0.005f, 0.012f, 0.03f })
            foreach (var o in new[] { 0f, 180f, 400f })
            {
                var cfg = Base();
                cfg.fuseMode = mode; cfg.fuseDelay = delay; cfg.outerMm = o;
                cfg.speed = 600;
                c3.rows.Add(Fire(c3.name, string.Format(CultureInfo.InvariantCulture,
                    "M{0}_D{1}_O{2}", mode, delay, o), cfg));
            }
            Summarize(c3); report.campaigns.Add(c3);

            // C4: material resistance × angle
            var c4 = new CampaignResult { name = "C4_resistance_angle" };
            foreach (var res in new[] { 0.5f, 1.0f, 1.5f })
            foreach (var a in new[] { 0f, 20f, 30f })
            foreach (var o in new[] { 100f, 229f, 400f })
            {
                var cfg = Base();
                cfg.resistance = res; cfg.angleDeg = a; cfg.outerMm = o;
                cfg.speed = 600; cfg.fuseMode = 1;
                c4.rows.Add(Fire(c4.name, string.Format(CultureInfo.InvariantCulture,
                    "R{0}_A{1}_O{2}", res, a, o), cfg));
            }
            Summarize(c4); report.campaigns.Add(c4);

            // C5: fragment samples × blast × seeds
            var c5 = new CampaignResult { name = "C5_fragments" };
            foreach (var n in new[] { 16, 32, 64, 128, 192, 512 })
            foreach (var blast in new[] { 0.5f, 1f, 2f })
            foreach (var seed in new[] { 1, 1913, 42, 7 })
            {
                var cfg = Base();
                cfg.fragmentSamples = n; cfg.blastStrength = blast; cfg.seed = seed;
                cfg.fuseMode = 0; cfg.outerMm = 0; // detonate in open for fragment spread
                c5.rows.Add(Fire(c5.name, string.Format(CultureInfo.InvariantCulture,
                    "N{0}_B{1}_S{2}", n, blast, seed), cfg));
            }
            Summarize(c5); report.campaigns.Add(c5);

            // C6: seed reproducibility / module damage variance on default delayed shot
            var c6 = new CampaignResult { name = "C6_seed_stability" };
            for (int seed = 0; seed < 24; seed++)
            {
                var cfg = Base();
                cfg.seed = seed;
                c6.rows.Add(Fire(c6.name, "seed" + seed, cfg));
            }
            Summarize(c6); report.campaigns.Add(c6);

            foreach (var c in report.campaigns)
            {
                report.totalCases += c.rows.Count;
                foreach (var row in c.rows)
                {
                    if (!row.deterministicOk)
                        report.findings.Add("NON_DETERMINISTIC " + c.name + "/" + row.caseId);
                }
            }

            Analyze(report);
            return report;
        }

        static void Summarize(CampaignResult c)
        {
            c.cases = c.rows.Count;
            double ms = 0;
            foreach (var r in c.rows)
            {
                if (r.outcome.Contains("stopped")) c.stopped++;
                if (r.outcome.Contains("detonated") || r.outcome.Contains("det")) c.detonated++;
                if (r.outcome == "exited") c.exited++;
                ms += r.report.duration;
            }
            c.meanDurationMs = c.cases > 0 ? (float)(ms / c.cases) : 0f;
        }

        static void Analyze(SweepReport report)
        {
            var c1 = report.campaigns.Find(c => c.name == "C1_armour_speed_angle");
            if (c1 != null)
            {
                // At fixed 600 m/s angle 0: thicker outer belt should not increase penetration success.
                int PenCount(float outer)
                {
                    int n = 0;
                    foreach (var r in c1.rows)
                    {
                        if (r.config.speed != 600f || Math.Abs(r.config.angleDeg) > 0.01f) continue;
                        if (Math.Abs(r.config.outerMm - outer) > 0.01f) continue;
                        if (!r.outcome.Contains("stopped") && r.report.events.Exists(e => e.kind == "penetrated"))
                            n++;
                    }
                    return n;
                }
                int p0 = PenCount(0), p229 = PenCount(229), p600 = PenCount(600);
                report.findings.Add(string.Format(CultureInfo.InvariantCulture,
                    "C1 speed600 angle0 outer0 penetrations={0} outer229={1} outer600={2} (monotone non-increasing expected)", p0, p229, p600));
                if (p0 < p229)
                    report.findings.Add("C1_MONOTONICITY_FAIL thicker armour reported more penetrations at 600/0");
            }

            var c3 = report.campaigns.Find(c => c.name == "C3_fuse");
            if (c3 != null)
            {
                int contactDet = 0, delayDet = 0, dudDet = 0;
                foreach (var r in c3.rows)
                {
                    if (r.config.fuseMode == 0 && r.report.exploded) contactDet++;
                    if (r.config.fuseMode == 1 && r.report.exploded) delayDet++;
                    if (r.config.fuseMode == 2 && r.report.exploded) dudDet++;
                }
                report.findings.Add(string.Format(CultureInfo.InvariantCulture,
                    "C3 detonations contact={0} delay={1} dud={2} (dud expected 0)", contactDet, delayDet, dudDet));
            }

            var c5 = report.campaigns.Find(c => c.name == "C5_fragments");
            if (c5 != null)
            {
                int badWeight = 0;
                foreach (var r in c5.rows)
                {
                    float w = 0;
                    foreach (var f in r.report.fragments) w += f.weight;
                    if (r.report.fragments.Count > 0 && Math.Abs(w - 1f) > 0.001f) badWeight++;
                }
                report.findings.Add("C5 fragment_weight_violations=" + badWeight);
            }

            var c6 = report.campaigns.Find(c => c.name == "C6_seed_stability");
            if (c6 != null)
            {
                var dam = new List<float>();
                foreach (var r in c6.rows) dam.Add(r.boiler);
                dam.Sort();
                report.findings.Add(string.Format(CultureInfo.InvariantCulture,
                    "C6 boiler damage across 24 seeds: min={0:F3} median={1:F3} max={2:F3}",
                    dam[0], dam[dam.Count / 2], dam[dam.Count - 1]));
            }
        }

        public static string WriteOutputs(SweepReport report, string dir)
        {
            Directory.CreateDirectory(dir);
            var csv = new StringBuilder();
            csv.AppendLine("campaign,case_id,outer_mm,inner_mm,rear_mm,resistance,speed,angle,refpen,fuse_mode,fuse_delay,samples,blast,seed,outcome,final_speed,duration,events,fragments,frag_escapes,boiler,engine,pump,det_ok");
            foreach (var camp in report.campaigns)
            foreach (var r in camp.rows)
            {
                var c = r.config;
                csv.Append(camp.name).Append(',').Append(r.caseId).Append(',')
                   .Append(c.outerMm.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.innerMm.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.rearMm.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.resistance.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.speed.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.angleDeg.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.referencePenMm.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.fuseMode).Append(',')
                   .Append(c.fuseDelay.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.fragmentSamples).Append(',')
                   .Append(c.blastStrength.ToString(CultureInfo.InvariantCulture)).Append(',')
                   .Append(c.seed).Append(',')
                   .Append(r.outcome).Append(',')
                   .Append(r.report.finalSpeed.ToString("F2", CultureInfo.InvariantCulture)).Append(',')
                   .Append(r.report.duration.ToString("F4", CultureInfo.InvariantCulture)).Append(',')
                   .Append(r.events).Append(',')
                   .Append(r.fragments).Append(',')
                   .Append(r.fragmentEscapes).Append(',')
                   .Append(r.boiler.ToString("F3", CultureInfo.InvariantCulture)).Append(',')
                   .Append(r.engine.ToString("F3", CultureInfo.InvariantCulture)).Append(',')
                   .Append(r.pump.ToString("F3", CultureInfo.InvariantCulture)).Append(',')
                   .Append(r.deterministicOk ? 1 : 0)
                   .AppendLine();
            }
            File.WriteAllText(Path.Combine(dir, "campaigns.csv"), csv.ToString(), new UTF8Encoding(false));

            var md = new StringBuilder();
            md.AppendLine("# Damage Range Sweep Report");
            md.AppendLine();
            md.AppendLine("- runId: `" + report.runId + "`");
            md.AppendLine("- utc: " + report.utc);
            md.AppendLine("- model: " + report.solverModel + " · historically_certified: false");
            md.AppendLine("- totalCases: " + report.totalCases);
            md.AppendLine();
            md.AppendLine("## Campaigns");
            md.AppendLine();
            md.AppendLine("| Campaign | cases | stopped | detonated | exited |");
            md.AppendLine("|---|---:|---:|---:|---:|");
            foreach (var c in report.campaigns)
                md.AppendLine("| " + c.name + " | " + c.cases + " | " + c.stopped + " | " + c.detonated + " | " + c.exited + " |");
            md.AppendLine();
            md.AppendLine("## Findings");
            foreach (var f in report.findings) md.AppendLine("- " + f);
            md.AppendLine();
            md.AppendLine("## Notes");
            md.AppendLine("- Resistance model is an experimental v² surrogate, not WWI ballistic tables.");
            md.AppendLine("- Module ids in the range are experiment contracts (Feed_Pump not in main ship contract).");
            md.AppendLine("- Serial solver timing is not game FPS.");
            File.WriteAllText(Path.Combine(dir, "SUMMARY.md"), md.ToString(), new UTF8Encoding(false));

            // Compact machine-readable summary (JsonUtility cannot serialize nested lists of custom easily without wrappers)
            var sb = new StringBuilder("{");
            sb.Append("\"runId\":\"").Append(report.runId).Append("\",");
            sb.Append("\"utc\":\"").Append(report.utc).Append("\",");
            sb.Append("\"totalCases\":").Append(report.totalCases).Append(',');
            sb.Append("\"findings\":[");
            for (int i = 0; i < report.findings.Count; i++)
            {
                if (i > 0) sb.Append(',');
                sb.Append('"').Append(report.findings[i].Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"');
            }
            sb.Append("]}");
            File.WriteAllText(Path.Combine(dir, "summary.json"), sb.ToString(), new UTF8Encoding(false));
            return dir;
        }
    }
}
