using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>A05 — Persist combat lab and optionally build standalone player.</summary>
    public static class ShipCombatAcceptance
    {
        public static void BuildPlayerBatch()
        {
            string reportDir = "runtime_acceptance/combat_a";
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; i++)
                if (args[i] == "-shipReportDirectory") reportDir = args[i + 1];
            Directory.CreateDirectory(reportDir);

            // Ensure lab scene uses current runtime prefab graph.
            var lab = ShipGameplayLabBuilder.Build();
            if (lab == null || !lab.StartsWith("OK"))
            {
                Debug.LogError("[Naval] Combat acceptance lab build failed: " + lab);
                File.WriteAllText(Path.Combine(reportDir, "combat_player_build.txt"), "lab_failed " + lab);
                if (Application.isBatchMode) EditorApplication.Exit(1);
                return;
            }

            var scenes = new EditorBuildSettingsScene[]
            {
                new EditorBuildSettingsScene("Assets/Scenes/GameplayLab.unity", true)
            };
            EditorBuildSettings.scenes = scenes;

            var options = new BuildPlayerOptions
            {
                scenes = new[] { "Assets/Scenes/GameplayLab.unity" },
                locationPathName = Path.Combine(reportDir, "player/QueenMaryCombatLab.exe"),
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None
            };
            var report = BuildPipeline.BuildPlayer(options);
            string summary = report.summary.result.ToString() + " errors=" + report.summary.totalErrors +
                             " path=" + options.locationPathName;
            File.WriteAllText(Path.Combine(reportDir, "combat_player_build.txt"),
                DateTime.UtcNow.ToString("o") + "\n" + summary + "\nlab=" + lab + "\n");
            Debug.Log("[Naval] Combat player build: " + summary);
            if (Application.isBatchMode)
                EditorApplication.Exit(report.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded ? 0 : 1);
        }
    }
}
