using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// v4 Unity import acceptance — read-only checks before greybox replacement.
    /// Batch: Naval.EditorTools.ShipV4Acceptance.RunBatch
    /// Report: -shipReportDirectory/v4_unity_acceptance.json
    /// </summary>
    public static class ShipV4Acceptance
    {
        public const string V4ModelDir = "Assets/Resources/Ships/HMS_Queen_Mary_1913_v4";
        public const string ExteriorFbx = V4ModelDir + "/QueenMary_v4_Exterior.fbx";
        public const string GameplayFbx = V4ModelDir + "/QueenMary_v4_Gameplay.fbx";
        public const string InteriorFbx = V4ModelDir + "/QueenMary_v4_Interior.fbx";
        public const string MaterialManifest = V4ModelDir + "/material_manifest.json";

        [MenuItem("Tools/Naval/V4 import acceptance")]
        public static void RunMenu()
        {
            var json = Run();
            Debug.Log("[Naval] v4 acceptance: " + json.status + " " + json.passed + "/" + json.total);
        }

        public static void RunBatch()
        {
            var json = Run();
            Debug.Log("[Naval] v4 acceptance: " + json.status + " passed=" + json.passed + " failed=" + json.failed);
            if (Application.isBatchMode)
                EditorApplication.Exit(json.status == "passed" ? 0 : 1);
        }

        [Serializable]
        public class Check
        {
            public string id;
            public bool passed;
            public string evidence;
        }

        [Serializable]
        public class Report
        {
            public string status;
            public string runId;
            public string builtUtc;
            public string unityVersion;
            public int total;
            public int passed;
            public int failed;
            public Check[] checks;
            public string[] notes;
        }

        public static Report Run()
        {
            var runId = DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ");
            var checks = new List<Check>();
            var notes = new List<string>();

            void Add(string id, bool ok, string evidence)
            {
                checks.Add(new Check { id = id, passed = ok, evidence = evidence ?? "" });
            }

            var exterior = AssetDatabase.LoadAssetAtPath<GameObject>(ExteriorFbx);
            Add("exterior_fbx_exists", exterior != null, ExteriorFbx);
            var gameplay = AssetDatabase.LoadAssetAtPath<GameObject>(GameplayFbx);
            Add("gameplay_fbx_exists", gameplay != null, GameplayFbx);

            var interior = AssetDatabase.LoadAssetAtPath<GameObject>(InteriorFbx);
            Add("interior_fbx_exists", interior != null, InteriorFbx);

            // Prefer gameplay FBX for hierarchy/logic checks (includes damage/armour proxies).
            var visual = gameplay != null ? gameplay : exterior;
            if (visual == null)
            {
                return Finish(runId, checks, notes, new[]
                {
                    "Neither gameplay nor exterior FBX found — run sync_v4_to_unity.ps1 after rebuild_v4.ps1"
                });
            }

            var inst = UnityEngine.Object.Instantiate(visual);
            inst.name = "V4_Acceptance_Instance";
            try
            {
                // Required combat hierarchy names (same contract as v3).
                string[] required =
                {
                    "Hull", "Turret_A", "Turret_B", "Turret_Q", "Turret_X",
                    "Elevation_A", "Elevation_B", "Elevation_Q", "Elevation_X",
                    "Barrel_A_Port", "Barrel_A_Starboard",
                    "Barrel_Q_Port", "Barrel_Q_Starboard"
                };
                var missing = new List<string>();
                foreach (var n in required)
                    if (FindDeep(inst.transform, n) == null) missing.Add(n);
                Add("required_nodes", missing.Count == 0,
                    missing.Count == 0 ? "all present" : "missing:" + string.Join(",", missing));

                int muzzles = 0;
                var muzzleEvidence = new StringBuilder();
                foreach (var key in new[] { "A", "B", "Q", "X" })
                foreach (var side in new[] { "Port", "Starboard" })
                {
                    var m = FindDeep(inst.transform, "Muzzle_" + key + "_" + side);
                    if (m == null) continue;
                    muzzles++;
                    var barrel = FindDeep(inst.transform, "Barrel_" + key + "_" + side);
                    bool parentOk = barrel != null && m.IsChildOf(barrel.transform);
                    muzzleEvidence.Append(m.name).Append(" parentBarrel=").Append(parentOk ? "1" : "0")
                        .Append(" local=").Append(m.localPosition.ToString("F3")).Append("; ");
                }
                Add("eight_muzzles", muzzles == 8, muzzleEvidence.ToString());

                // Bounds on meshes (world AABB after instantiate at origin).
                var rends = inst.GetComponentsInChildren<MeshRenderer>(true);
                Bounds b = new Bounds();
                bool hasB = false;
                int meshCount = 0;
                foreach (var r in rends)
                {
                    if (r == null || r.GetComponent<MeshFilter>() == null) continue;
                    meshCount++;
                    if (!hasB) { b = r.bounds; hasB = true; }
                    else b.Encapsulate(r.bounds);
                }
                Add("mesh_renderer_count", meshCount > 0, "meshes=" + meshCount);
                if (hasB)
                {
                    var size = b.size;
                    // Full ship includes masts/funnels; hull is ~15 m but vertical extent can be ~40-55 m.
                    Add("length_along_z", size.z >= 200f && size.z <= 240f, size.z.ToString("F2"));
                    Add("beam_or_extents_x", size.x > 20f && size.x < 50f, size.x.ToString("F2"));
                    Add("height_y", size.y > 12f && size.y < 60f, size.y.ToString("F2"));
                    notes.Add(string.Format("bounds size=({0:F2},{1:F2},{2:F2}) center={3}", size.x, size.y, size.z, b.center));
                }
                else Add("bounds_available", false, "no mesh bounds");

                // Bow direction: A barbette vs X barbette in instance local/world.
                var a = FindDeep(inst.transform, "Barbette_A");
                var x = FindDeep(inst.transform, "Barbette_X");
                if (a != null && x != null)
                {
                    float dz = a.position.z - x.position.z;
                    Add("bow_plus_z", dz > 20f, "Barbette_A.z - Barbette_X.z = " + dz.ToString("F2"));
                }
                else Add("bow_plus_z", false, "barbettes missing");

                // Compartment / damage proxy names
                int moduleHits = 0;
                var moduleNames = new List<string>
                {
                    "Magazine_A", "Boiler_Room_1", "Engine_Room_1", "Steering_Gear",
                    "Armour_Belt_229mm"
                };
                foreach (var n in moduleNames)
                    if (FindDeep(inst.transform, n) != null) moduleHits++;
                Add("logic_module_names", moduleHits >= 4, "found " + moduleHits + "/" + moduleNames.Count);

                // Materials
                var mats = new HashSet<string>();
                int nonUrp = 0;
                foreach (var r in rends)
                {
                    foreach (var m in r.sharedMaterials)
                    {
                        if (m == null) continue;
                        mats.Add(m.name);
                        var sn = m.shader != null ? m.shader.name : "";
                        if (sn.IndexOf("Universal Render Pipeline", StringComparison.OrdinalIgnoreCase) < 0)
                            nonUrp++;
                    }
                }
                Add("material_slots_present", mats.Count > 0, string.Join(",", mats));
                notes.Add("non_urp_material_slots=" + nonUrp + " (remap via UrpSetup/V4 if >0)");
                var manifestText = AssetDatabase.LoadAssetAtPath<TextAsset>(MaterialManifest);
                Add("material_manifest_synced", manifestText != null, MaterialManifest);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(inst);
            }

            return Finish(runId, checks, notes, null);
        }

        static Report Finish(string runId, List<Check> checks, List<string> notes, string[] extraNotes)
        {
            if (extraNotes != null) notes.AddRange(extraNotes);
            int pass = 0;
            foreach (var c in checks) if (c.passed) pass++;
            var report = new Report
            {
                runId = runId,
                builtUtc = DateTime.UtcNow.ToString("o"),
                unityVersion = Application.unityVersion,
                total = checks.Count,
                passed = pass,
                failed = checks.Count - pass,
                checks = checks.ToArray(),
                notes = notes.ToArray(),
                status = pass == checks.Count && checks.Count > 0 ? "passed" : "failed"
            };
            try
            {
                string outDir = "Assets/../runtime_acceptance";
                var args = Environment.GetCommandLineArgs();
                for (int i = 0; i + 1 < args.Length; i++)
                    if (args[i] == "-shipReportDirectory") outDir = args[i + 1];
                string full = Path.GetFullPath(outDir);
                Directory.CreateDirectory(full);
                string path = Path.Combine(full, "v4_unity_acceptance.json");
                File.WriteAllText(path, JsonUtility.ToJson(report, true), new UTF8Encoding(false));
                Debug.Log("[Naval] v4 acceptance report: " + path + " " + report.status);
            }
            catch (Exception e)
            {
                Debug.LogError("[Naval] v4 acceptance report write failed: " + e.Message);
            }
            return report;
        }

        static Transform FindDeep(Transform root, string name)
        {
            if (root == null || string.IsNullOrEmpty(name)) return null;
            if (root.name == name) return root;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            return null;
        }
    }
}
