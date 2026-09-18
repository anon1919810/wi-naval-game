using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Naval.EditorTools
{
    public static class ShipBenchmarkBuilder
    {
        public static void BuildBatch()
        {
            Directory.CreateDirectory(ShipRuntimeAcceptance.OutputDirectory);
            bool frameTiming = PlayerSettings.enableFrameTimingStats;
            try
            {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var camera = new GameObject("FleetCamera").AddComponent<Camera>();
                camera.GetUniversalAdditionalCameraData();
                camera.transform.position = new Vector3(820, 980, -1080);
                camera.transform.LookAt(new Vector3(0, 0, 0));
                camera.fieldOfView = 50;
                camera.nearClipPlane = 1;
                camera.farClipPlane = 6000;
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(.12f, .17f, .23f);
                var light = new GameObject("FleetSun").AddComponent<Light>();
                light.type = LightType.Directional;
                light.intensity = 1.5f;
                light.shadows = LightShadows.Soft;
                light.transform.rotation = Quaternion.Euler(45, -35, 0);
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(.45f, .45f, .45f);
                RenderSettings.fog = false;
                var sea = GameObject.CreatePrimitive(PrimitiveType.Plane);
                sea.name = "Benchmark_Flat_Sea";
                sea.transform.localScale = new Vector3(600, 1, 600);
                UnityEngine.Object.DestroyImmediate(sea.GetComponent<Collider>());
                var material = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                material.SetColor("_BaseColor", new Color(.025f, .08f, .11f));
                material.SetFloat("_Smoothness", .1f);
                const string matPath = "Assets/Materials/BenchmarkSea.mat";
                var existing = AssetDatabase.LoadAssetAtPath<Material>(matPath);
                if (existing) { EditorUtility.CopySerialized(material, existing); UnityEngine.Object.DestroyImmediate(material); material = existing; EditorUtility.SetDirty(material); }
                else AssetDatabase.CreateAsset(material, matPath);
                sea.GetComponent<MeshRenderer>().sharedMaterial = material;
                var driver = new GameObject("FleetBenchmark").AddComponent<ShipFleetBenchmark>();
                driver.shipPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(ShipRuntimeBuilder.PrefabPath);
                driver.benchmarkCamera = camera;
                if (!driver.shipPrefab) throw new InvalidOperationException("Build the ship prefab first");
                const string scenePath = "Assets/Scenes/QueenMaryFleetBenchmark.unity";
                EditorSceneManager.SaveScene(scene, scenePath);
                AssetDatabase.SaveAssets();
                PlayerSettings.enableFrameTimingStats = true;
                var result = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                    scenes = new[] { scenePath }, target = BuildTarget.StandaloneWindows64,
                    locationPathName = Path.Combine(ShipRuntimeAcceptance.OutputDirectory, "player/QueenMaryFleetBenchmark.exe"),
                    options = BuildOptions.None });
                File.WriteAllText(Path.Combine(ShipRuntimeAcceptance.OutputDirectory, "player_build.txt"), result.summary.result + "\n" + result.summary.totalTime + "\nbytes=" + result.summary.totalSize);
                if (result.summary.result != BuildResult.Succeeded) throw new Exception("Player build: " + result.summary.result);
            }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); return; }
            finally { PlayerSettings.enableFrameTimingStats = frameTiming; }
            EditorApplication.Exit(0);
        }
    }
}
