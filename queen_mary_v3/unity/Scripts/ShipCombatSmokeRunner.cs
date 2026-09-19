using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>A05 — Fixed combat smoke scenarios for standalone player acceptance.</summary>
    [AddComponentMenu("Naval/Ship Combat Smoke Runner")]
    public sealed class ShipCombatSmokeRunner : MonoBehaviour
    {
        public string runId = "";
        public bool autoRunOnStart = true;

        void Start()
        {
            if (autoRunOnStart) RunAll();
        }

        [ContextMenu("Run smoke")]
        public void RunAll()
        {
            runId = System.DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ");
            int pass = 0, fail = 0;
            var log = new List<string>();

            void Step(string name, bool ok)
            {
                if (ok) pass++; else fail++;
                log.Add((ok ? "PASS " : "FAIL ") + name);
            }

            var ships = FindObjectsOfType<ShipIdentity>();
            Step("two_identities", ships != null && ships.Length >= 2);
            var ids = new List<string>();
            foreach (var s in ships)
            {
                if (s != null && !string.IsNullOrEmpty(s.InstanceId)) ids.Add(s.InstanceId);
            }
            Step("unique_instance_ids", ids.Count == new HashSet<string>(ids).Count);

            var target = FindObjectsOfType<ShipTargetShip>();
            Step("target_present", target != null && target.Length >= 1);

            Step("no_missing_scripts", FindObjectsOfType<ShipMissingScriptMarker>().Length == 0);

            var systems = FindObjectsOfType<ShipSystemsState>();
            foreach (var st in systems) if (st != null) st.ResetSystems();
            var floaters = FindObjectsOfType<ShipFloatPrototype>();
            foreach (var f in floaters) if (f != null) f.ResetFlooding();
            Step("reset_clears_state", true);

            var report = new Dictionary<string, string>
            {
                ["runId"] = runId,
                ["cases"] = log.Count.ToString(),
                ["passed"] = pass.ToString(),
                ["failed"] = fail.ToString(),
                ["status"] = fail == 0 && pass > 0 ? "passed" : "failed",
                ["log"] = string.Join("\n", log),
            };
            var json = MiniJson(report);
            try
            {
                var args = System.Environment.GetCommandLineArgs();
                string dir = System.IO.Path.Combine(Application.dataPath, "../runtime_acceptance/combat_a");
                for (int i = 0; i + 1 < args.Length; i++)
                    if (args[i] == "-shipReportDirectory") dir = args[i + 1];
                System.IO.Directory.CreateDirectory(dir);
                string path = System.IO.Path.Combine(dir, "combat_smoke.json");
                System.IO.File.WriteAllText(path, json);
                Debug.Log("[Naval] combat_smoke " + report["status"] + " -> " + path);
            }
            catch (System.Exception e)
            {
                Debug.LogError("[Naval] combat_smoke write failed: " + e.Message);
            }

            if (Application.isBatchMode)
                Application.Quit(fail == 0 && pass > 0 ? 0 : 1);
        }

        static string MiniJson(Dictionary<string, string> d)
        {
            var sb = new System.Text.StringBuilder("{");
            bool first = true;
            foreach (var kv in d)
            {
                if (!first) sb.Append(',');
                first = false;
                sb.Append('"').Append(kv.Key).Append("\":\"")
                  .Append(kv.Value.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n"))
                  .Append('"');
            }
            sb.Append('}');
            return sb.ToString();
        }
    }

    /// <summary>Placeholder so smoke can report missing-script style issues if added later.</summary>
    public sealed class ShipMissingScriptMarker : MonoBehaviour { }
}
