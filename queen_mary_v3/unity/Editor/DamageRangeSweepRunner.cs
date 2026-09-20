using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// Batch/menu entry for DamageRange factor sweeps.
    /// Batch: Naval.EditorTools.DamageRangeSweepRunner.RunBatch
    /// Optional: -labOutput &lt;dir&gt; else damage_range/sweeps/&lt;runId&gt; under Assets/../
    /// </summary>
    public static class DamageRangeSweepRunner
    {
        [MenuItem("Tools/Naval/Run damage range sweep")]
        public static void RunMenu()
        {
            var report = Naval.DamageLab.DamageRangeSweep.RunAll();
            string dir = DefaultDir(report.runId);
            Naval.DamageLab.DamageRangeSweep.WriteOutputs(report, dir);
            Debug.Log("[Naval] DamageRange sweep " + report.runId + " cases=" + report.totalCases + " -> " + dir);
            foreach (var f in report.findings) Debug.Log("[Naval] sweep finding: " + f);
        }

        public static void RunBatch()
        {
            string dir = null;
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; i++)
                if (args[i] == "-labOutput") dir = args[i + 1];

            var report = Naval.DamageLab.DamageRangeSweep.RunAll();
            if (string.IsNullOrEmpty(dir)) dir = DefaultDir(report.runId);
            try
            {
                Naval.DamageLab.DamageRangeSweep.WriteOutputs(report, dir);
                Debug.Log("[Naval] DamageRange sweep OK runId=" + report.runId +
                          " cases=" + report.totalCases + " dir=" + dir);
                foreach (var f in report.findings) Debug.Log("[Naval] " + f);
                if (Application.isBatchMode) EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                try { File.WriteAllText(Path.Combine(dir ?? ".", "sweep_error.txt"), e.ToString()); } catch { }
                if (Application.isBatchMode) EditorApplication.Exit(1);
            }
        }

        static string DefaultDir(string runId)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            // Prefer asset-repo relative path when project sits elsewhere.
            string candidates = Path.Combine(projectRoot, "DamageRangeSweeps", runId);
            return candidates;
        }
    }
}
