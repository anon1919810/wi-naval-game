using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Naval.EditorTools
{
    /// <summary>Exercise the saved prefab, actual PhysX queries and URP pixels, including forced far LODs.</summary>
    public static class ShipRuntimeAcceptance
    {
        public static string OutputDirectory
        {
            get
            {
                var args = Environment.GetCommandLineArgs();
                for (int i = 0; i + 1 < args.Length; i++)
                    if (args[i] == "-shipReportDirectory") return Path.GetFullPath(args[i + 1]);
                return Path.GetFullPath("ShipAcceptance");
            }
        }

        [Serializable] public class ImageCheck
        {
            public string view, file;
            public int lod, pixels, triangles, renderers, submeshes;
            public float coverageAgainstLod0, intersectionOverUnion;
        }
        [Serializable] public class Report
        {
            public string status, builtUtc, unityVersion;
            public int compartments, hullColliders, colliderRays;
            public List<string> failures = new List<string>();
            public List<ImageCheck> images = new List<ImageCheck>();
        }

        public static void RunBatch()
        {
            var report = Run();
            EditorApplication.Exit(report.failures.Count == 0 ? 0 : 1);
        }

        public static void RebuildAndTestBatch()
        {
            var first = ShipRuntimeBuilder.Build();
            if (first.status != "passed") { EditorApplication.Exit(1); return; }
            var paths = AssetDatabase.FindAssets("t:Mesh", new[] { "Assets/Meshes/Ships" })
                .Select(AssetDatabase.GUIDToAssetPath).ToArray();
            var guids = paths.Select(AssetDatabase.AssetPathToGUID).ToArray();
            var second = ShipRuntimeBuilder.Build();
            var r = Run();
            if (second.status != "passed") r.failures.Add("Repeated runtime build failed");
            for (int i = 0; i < paths.Length; i++)
                if (AssetDatabase.AssetPathToGUID(paths[i]) != guids[i]) r.failures.Add("Repeat build broke mesh GUID: " + paths[i]);
            r.status = r.failures.Count == 0 ? "passed" : "failed";
            File.WriteAllText(Path.Combine(OutputDirectory, "runtime_acceptance.json"), JsonUtility.ToJson(r, true));
            File.WriteAllText(Path.Combine(OutputDirectory, "repeat_build.txt"), "Two builds in one Unity session; " + paths.Length + " persistent mesh GUIDs checked; " + r.status);
            EditorApplication.Exit(r.failures.Count == 0 ? 0 : 1);
        }

        public static Report Run()
        {
            Directory.CreateDirectory(OutputDirectory);
            var r = new Report { builtUtc = DateTime.UtcNow.ToString("o"), unityVersion = Application.unityVersion };
            GameObject ship = null;
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            try
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(ShipRuntimeBuilder.PrefabPath);
                if (prefab == null) throw new InvalidOperationException("Runtime prefab missing");
                ship = UnityEngine.Object.Instantiate(prefab);
                var contract = ShipContractData.Load(ShipRuntimeBuilder.ShipId);
                if (!contract.file_refs.Any(f => f.key == "buoyancy_compartments"))
                    r.failures.Add("Contract omits the buoyancy document needed to assemble compartments");
                var compartments = ship.GetComponentsInChildren<ShipCompartment>();
                r.compartments = compartments.Length;
                // Independent game-facing requirements: four magazines, seven boilers, two engines, steering.
                if (compartments.Length != 14) r.failures.Add("Expected 14 floodable compartments; found " + compartments.Length);
                var steering = compartments.FirstOrDefault(c => c.compartmentId == "Steering_Gear");
                if (steering == null || !steering.dataFromBuoyancyFile || steering.floodableVolumeM3 <= 0)
                    r.failures.Add("Steering_Gear cannot consume its floodable-volume data");
                foreach (var c in compartments)
                {
                    if (!c.dataFromBuoyancyFile) r.failures.Add(c.name + " uses fallback buoyancy data");
                    c.Flood(c.floodableVolumeM3 * 0.25f);
                    if (Mathf.Abs(c.floodFraction - .25f) > .001f) r.failures.Add(c.name + " flooding does not consume volume");
                    c.Flood(c.floodableVolumeM3 * 2);
                    if (c.floodFraction != 1) r.failures.Add(c.name + " overflows its capacity");
                }
                var proxy = ship.GetComponentsInChildren<Transform>().FirstOrDefault(t => t.name == "Hull_Collision_Proxy");
                var hullColliders = proxy == null ? new Collider[0] : proxy.GetComponentsInChildren<Collider>();
                r.hullColliders = hullColliders.Length;
                if (hullColliders.Length == 0) r.failures.Add("No hull-level query proxy");
                else
                {
                    Physics.SyncTransforms();
                    // Hit surface midships and narrow ends from outside; a ray beyond the beam must miss.
                    var rays = new[] {
                        new Ray(new Vector3(40, 0, 0), Vector3.left),
                        new Ray(new Vector3(-40, 0, 0), Vector3.right),
                        new Ray(new Vector3(0, 0, 130), Vector3.back),
                        new Ray(new Vector3(0, 0, -130), Vector3.forward),
                        new Ray(new Vector3(0, 25, 70), Vector3.down),
                        new Ray(new Vector3(0, -25, -30), Vector3.up) };
                    foreach (var ray in rays)
                    {
                        r.colliderRays++;
                        if (!hullColliders.Any(c => c.Raycast(ray, out _, 260))) r.failures.Add("Hull proxy missed " + ray);
                    }
                    if (hullColliders.Any(c => c.Raycast(new Ray(new Vector3(25, 0, 130), Vector3.back), out _, 260)))
                        r.failures.Add("Hull proxy hits an empty lane outside the beam");
                    foreach (var collider in hullColliders)
                    {
                        var mc = collider as MeshCollider;
                        if (mc == null || !mc.convex || mc.sharedMesh == null || !mc.isTrigger)
                            r.failures.Add("Hull proxy is not a convex query trigger");
                        else if (mc.sharedMesh.triangles.Length / 3 > 255)
                            r.failures.Add("Hull proxy exceeds the convex triangle budget");
                    }
                }
                var group = ship.GetComponent<LODGroup>();
                if (group == null || group.lodCount != 4) throw new InvalidOperationException("Expected four LODs");
                var levels = group.GetLODs();
                for (int level = 0; level < 4; level++)
                    foreach (var mr in levels[level].renderers)
                        if (mr == null || !mr.enabled) r.failures.Add("LOD" + level + " contains a missing or disabled renderer: " + (mr ? mr.name : "null"));
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(.4f, .4f, .4f);
                RenderSettings.fog = false;
                var cameraGo = new GameObject("AcceptanceCamera");
                var camera = cameraGo.AddComponent<Camera>();
                camera.GetUniversalAdditionalCameraData();
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(.12f, .16f, .2f, 1);
                camera.orthographic = true;
                camera.orthographicSize = 72;
                camera.aspect = 16f / 9f;
                camera.nearClipPlane = .1f;
                camera.farClipPlane = 2000;
                var lamp = new GameObject("AcceptanceLight").AddComponent<Light>();
                lamp.type = LightType.Directional;
                lamp.intensity = 1.5f;
                var target = new Vector3(0, 16, 0);
                var directions = new[] { new Vector3(1, .1f, 0), new Vector3(0, 1, 0), new Vector3(1, .6f, 1) };
                var names = new[] { "side", "top", "overview" };
                for (int view = 0; view < names.Length; view++)
                {
                    camera.transform.position = target + directions[view].normalized * 500;
                    camera.transform.LookAt(target, view == 1 ? Vector3.forward : Vector3.up);
                    lamp.transform.rotation = camera.transform.rotation * Quaternion.Euler(-25, 25, 0);
                    bool[] reference = null;
                    for (int level = 0; level < 4; level++)
                    {
                        group.ForceLOD(level);
                        var result = Render(camera, names[view], level, out var mask);
                        if (level == 0) reference = mask;
                        int intersection = 0, union = 0, basePixels = 0;
                        for (int i = 0; i < mask.Length; i++)
                        {
                            if (mask[i] && reference[i]) intersection++;
                            if (mask[i] || reference[i]) union++;
                            if (reference[i]) basePixels++;
                        }
                        result.coverageAgainstLod0 = (float)intersection / Mathf.Max(1, basePixels);
                        result.intersectionOverUnion = (float)intersection / Mathf.Max(1, union);
                        result.renderers = levels[level].renderers.Length;
                        foreach (var mr in levels[level].renderers)
                        {
                            var mesh = mr.GetComponent<MeshFilter>().sharedMesh;
                            result.triangles += mesh.triangles.Length / 3;
                            result.submeshes += mesh.subMeshCount;
                        }
                        if (result.pixels < 2000) r.failures.Add(result.file + " is mostly empty");
                        // LOD1 must preserve the mesh exactly; distant LODs may omit small fittings.
                        float minimum = level == 1 ? .97f : .70f;
                        if (level > 0 && result.intersectionOverUnion < minimum)
                            r.failures.Add(result.file + " lost ship silhouette; IoU=" + result.intersectionOverUnion);
                        r.images.Add(result);
                    }
                }
                group.ForceLOD(-1);
            }
            catch (Exception e) { r.failures.Add(e.ToString()); }
            finally
            {
                if (ship) UnityEngine.Object.DestroyImmediate(ship);
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            }
            r.status = r.failures.Count == 0 ? "passed" : "failed";
            File.WriteAllText(Path.Combine(OutputDirectory, "runtime_acceptance.json"), JsonUtility.ToJson(r, true));
            Debug.Log("[Naval] Runtime acceptance " + r.status + "\n" + string.Join("\n", r.failures));
            return r;
        }

        private static ImageCheck Render(Camera camera, string view, int level, out bool[] mask)
        {
            const int width = 1280, height = 720;
            var texture = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
            var previous = RenderTexture.active;
            var shot = new Texture2D(width, height, TextureFormat.RGBA32, false);
            try
            {
                texture.Create();
                camera.targetTexture = texture;
                camera.Render();
                RenderTexture.active = texture;
                shot.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                shot.Apply();
                string file = view + "_LOD" + level + ".png";
                File.WriteAllBytes(Path.Combine(OutputDirectory, file), shot.EncodeToPNG());
                var pixels = shot.GetPixels32();
                var background = pixels[0]; // Compare readback to readback, not linear clear-color values.
                mask = new bool[pixels.Length];
                int count = 0;
                for (int i = 0; i < pixels.Length; i++)
                {
                    var p = pixels[i];
                    mask[i] = Math.Abs(p.r - background.r) + Math.Abs(p.g - background.g) + Math.Abs(p.b - background.b) > 18;
                    if (mask[i]) count++;
                }
                return new ImageCheck { view = view, lod = level, file = file, pixels = count };
            }
            finally
            {
                camera.targetTexture = null;
                RenderTexture.active = previous;
                texture.Release();
                UnityEngine.Object.DestroyImmediate(texture);
                UnityEngine.Object.DestroyImmediate(shot);
            }
        }
    }
}
