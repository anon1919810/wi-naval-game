using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace Naval
{
    /// <summary>Asset-only rendering benchmark; no combat, AI, ocean simulation or dynamic rigid bodies.</summary>
    public sealed class ShipFleetBenchmark : MonoBehaviour
    {
        public GameObject shipPrefab;
        public Camera benchmarkCamera;
        public const int ShipCount = 15;

        [Serializable] public class Timing
        {
            public int samples;
            public double medianMs, p95Ms, p99Ms, meanMs;
            public bool available;
        }
        [Serializable] public class Stage
        {
            public string mode, screenshot;
            public int shipsInFrustum, hullColliders, compartmentColliders, shipPixels, gpuCompletedFrames;
            public int[] estimatedLodCounts;
            /// <summary>逐船的屏幕高度比例（LOD 选择的实际输入量）。记下来才能核对档位判得对不对。</summary>
            public float[] lodRelatives;
            public int estimatedTriangles, estimatedSubmeshes;
            public Timing frame, cpu, gpu, synchronizedRender;
            public double fpsFromMeanFrameTime;
            public int width, height;
        }

        private RenderTexture renderTarget;
        private double lastRenderMs;
        private int completedFrames, gpuReadbackErrors;

        private void LateUpdate()
        {
            if (renderTarget == null) return;
            var watch = System.Diagnostics.Stopwatch.StartNew();
            benchmarkCamera.Render();
            // One-pixel readback is a CPU/GPU completion fence even when Windows hides the window.
            // It deliberately serializes CPU/GPU work, so report this as a conservative offscreen test.
            var request = AsyncGPUReadback.Request(renderTarget, 0, 0, 1, 0, 1, 0, 1);
            request.WaitForCompletion();
            watch.Stop();
            if (request.hasError) gpuReadbackErrors++;
            else completedFrames++;
            lastRenderMs = watch.Elapsed.TotalMilliseconds;
        }
        [Serializable] public class Report
        {
            public string status, startedUtc, completedUtc, unityVersion, cpu, gpu, graphicsApi, scope;
            public int shipCount, width, height, vSyncCount, targetFrameRate;
            public bool developmentBuild, frameTimingEnabled;
            /// <summary>LOD 选择受质量档位影响：不记下来，estimatedLodCounts 就没法复现。</summary>
            public double lodBias;
            public int maximumLodLevel, qualityLevel;
            public List<Stage> stages = new List<Stage>();
            public List<string> failures = new List<string>();
            public List<string> notes = new List<string>();
        }

        private IEnumerator Start()
        {
            string output = Path.Combine(Application.persistentDataPath, "FleetBenchmark");
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; i++)
                if (args[i] == "-shipReportDirectory") output = Path.GetFullPath(args[i + 1]);
            Directory.CreateDirectory(output);
            Application.runInBackground = true;
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            Screen.SetResolution(1920, 1080, FullScreenMode.Windowed);
            var r = new Report {
                status = "running", startedUtc = DateTime.UtcNow.ToString("o"), unityVersion = Application.unityVersion,
                cpu = SystemInfo.processorType, gpu = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                shipCount = ShipCount, vSyncCount = QualitySettings.vSyncCount, targetFrameRate = Application.targetFrameRate,
                developmentBuild = Debug.isDebugBuild, frameTimingEnabled = FrameTimingManager.IsFeatureEnabled(),
                lodBias = QualitySettings.lodBias, maximumLodLevel = QualitySettings.maximumLODLevel,
                qualityLevel = QualitySettings.GetQualityLevel(),
                scope = "Standalone URP 1920x1080 offscreen rendering. Camera.Render plus synchronous one-pixel GPU readback each frame prevents hidden-window render skipping. CPU/GPU work is deliberately serialized and includes synchronization overhead; this is not interactive game FPS. Flat sea, fixed camera, 15 stationary ships; no AI/combat/waves/dynamic rigidbody contacts. Forced LODs use the same camera."
            };
            if (!SystemInfo.supportsAsyncGPUReadback) r.failures.Add("GPU readback is unsupported; timing cannot be trusted");
            renderTarget = new RenderTexture(1920, 1080, 24, RenderTextureFormat.ARGB32);
            renderTarget.Create();
            benchmarkCamera.enabled = false;
            benchmarkCamera.targetTexture = renderTarget;
            var groups = new List<LODGroup>();
            for (int row = 0; row < 3; row++)
                for (int col = 0; col < 5; col++)
                {
                    var ship = Instantiate(shipPrefab, new Vector3((col - 2) * 85, 0, (row - 1) * 265), Quaternion.identity);
                    ship.name = "QueenMary_" + groups.Count.ToString("00");
                    groups.Add(ship.GetComponent<LODGroup>());
                }
            // Ship meshes retain their below-waterline hull; an opaque flat sea hides it as gameplay would.
            Physics.SyncTransforms();
            yield return null;
            r.width = Screen.width; r.height = Screen.height;
            var modes = new[] { -1, 0, 1, 2, 3 };
            foreach (int forced in modes)
            {
                foreach (var group in groups) group.ForceLOD(forced);
                var name = forced < 0 ? "automatic" : "forced_LOD" + forced;
                // Exclude loading, first-use shader work, and capture operations from samples.
                float warmupEnd = Time.realtimeSinceStartup + 2;
                while (Time.realtimeSinceStartup < warmupEnd) yield return null;
                var frames = new List<double>();
                var cpuTimes = new List<double>();
                var gpuTimes = new List<double>();
                var renderTimes = new List<double>();
                int startCompletedFrames = completedFrames;
                var timings = new FrameTiming[1];
                ulong lastTimestamp = 0;
                float sampleEnd = Time.realtimeSinceStartup + 8;
                while (Time.realtimeSinceStartup < sampleEnd || frames.Count < 600)
                {
                    yield return null;
                    frames.Add(Time.unscaledDeltaTime * 1000.0);
                    renderTimes.Add(lastRenderMs);
                    FrameTimingManager.CaptureFrameTimings();
                    if (FrameTimingManager.GetLatestTimings(1, timings) != 0 && timings[0].frameStartTimestamp != lastTimestamp)
                    {
                        lastTimestamp = timings[0].frameStartTimestamp;
                        if (timings[0].cpuFrameTime > 0) cpuTimes.Add(timings[0].cpuFrameTime);
                        if (timings[0].gpuFrameTime > 0) gpuTimes.Add(timings[0].gpuFrameTime);
                    }
                }
                var stage = new Stage { mode = name, frame = Summarize(frames), cpu = Summarize(cpuTimes), gpu = Summarize(gpuTimes), synchronizedRender = Summarize(renderTimes), gpuCompletedFrames = completedFrames - startCompletedFrames, estimatedLodCounts = new int[5], lodRelatives = new float[groups.Count], width = renderTarget.width, height = renderTarget.height };
                stage.fpsFromMeanFrameTime = 1000 / stage.frame.meanMs;
                var planes = GeometryUtility.CalculateFrustumPlanes(benchmarkCamera);
                int shipIndex = 0;
                foreach (var group in groups)
                {
                    var hull = Array.Find(group.GetComponentsInChildren<MeshRenderer>(), mr => mr.name == "Hull");
                    if (hull != null && GeometryUtility.TestPlanesAABB(planes, hull.bounds)) stage.shipsInFrustum++;
                    stage.hullColliders += group.GetComponentsInChildren<MeshCollider>().Length;
                    stage.compartmentColliders += group.GetComponentsInChildren<BoxCollider>().Length;
                    float relative = RelativeHeight(group, benchmarkCamera);
                    stage.lodRelatives[shipIndex++] = relative;
                    int level = forced >= 0 ? forced : LevelFromRelative(group, relative);
                    stage.estimatedLodCounts[level]++;
                    if (level >= group.lodCount) continue;
                    foreach (var mr in group.GetLODs()[level].renderers)
                    {
                        var mesh = mr.GetComponent<MeshFilter>().sharedMesh;
                        stage.estimatedTriangles += mesh.triangles.Length / 3;
                        stage.estimatedSubmeshes += mesh.subMeshCount;
                    }
                }
                if (stage.shipsInFrustum != ShipCount) r.failures.Add(name + " does not frame all 15 ships");
                if (stage.width != 1920 || stage.height != 1080) r.failures.Add(name + " is not 1920x1080");
                if (stage.frame.samples < 600) r.failures.Add(name + " has too few samples");
                if (stage.gpuCompletedFrames < frames.Count - 1 || gpuReadbackErrors != 0) r.failures.Add(name + " did not complete GPU rendering for every sample");
                r.stages.Add(stage);
                var previousTarget = RenderTexture.active;
                RenderTexture.active = renderTarget;
                var shot = new Texture2D(1920, 1080, TextureFormat.RGBA32, false);
                shot.ReadPixels(new Rect(0, 0, 1920, 1080), 0, 0);
                shot.Apply();
                RenderTexture.active = previousTarget;
                int magentaPixels = 0;
                foreach (var p in shot.GetPixels32())
                {
                    if (p.r > 18 && p.r > p.g * .8f && p.r > p.b * .7f) stage.shipPixels++;
                    if (p.r > p.g + 65 && p.b > p.g + 65) magentaPixels++;
                }
                if (stage.shipPixels < 2000) r.failures.Add(name + " rendered no visible fleet (black/empty image)");
                if (magentaPixels > 1000) r.failures.Add(name + " has magenta error-shader pixels");
                stage.screenshot = name + ".png";
                File.WriteAllBytes(Path.Combine(output, stage.screenshot), shot.EncodeToPNG());
                Destroy(shot);
                File.WriteAllText(Path.Combine(output, name + "_frames_ms.csv"), "frame_ms\n" + string.Join("\n", frames.ConvertAll(x => x.ToString("F6", System.Globalization.CultureInfo.InvariantCulture))));
                File.WriteAllText(Path.Combine(output, "fleet_benchmark.json"), JsonUtility.ToJson(r, true));
            }
            // 自动档若 15 艘船全落在同一档，说明这个相机 + 这个 lodBias 只测到一个细节层级。
            // 不是错误，但必须写进报告 —— 否则读报告的人会以为"自动档验证了 LOD 切换"。
            var automatic = r.stages.Find(s => s.mode == "automatic");
            if (automatic != null && groups.Count > 0)
            {
                int used = 0;
                foreach (int c in automatic.estimatedLodCounts) if (c > 0) used++;
                if (used <= 1)
                {
                    float min = float.MaxValue, max = 0;
                    foreach (float v in automatic.lodRelatives) { if (v < min) min = v; if (v > max) max = v; }
                    var lods = groups[0].GetLODs();
                    int level = Array.FindIndex(automatic.estimatedLodCounts, c => c > 0);
                    var thresholds = new List<string>();
                    foreach (var l in lods) thresholds.Add(l.screenRelativeTransitionHeight.ToString("0.00"));
                    string next = "n/a";
                    if (level >= 0 && level < lods.Length && lods[level].screenRelativeTransitionHeight > 0)
                    {
                        float need = groups[0].size * (float)r.lodBias /
                            (2 * lods[level].screenRelativeTransitionHeight * Mathf.Tan(benchmarkCamera.fieldOfView * .5f * Mathf.Deg2Rad));
                        next = need.ToString("0") + " m";
                    }
                    r.notes.Add("自动档 15 艘船全部落在同一个 LOD 档（屏幕高度比例 " + min.ToString("0.000") + "–" + max.ToString("0.000") +
                        "，档位阈值 " + string.Join("/", thresholds.ToArray()) + "，lodBias " + r.lodBias.ToString("0.##") +
                        "，质量档位 " + r.qualityLevel + "）。编队纵深仅数百米、相机在 1.4–1.9 km，故这一阶段只测到单一细节层级；" +
                        "要掉进下一档需退到 " + next + " 以外。LOD 的实际收益请看 forced_LOD* 阶段。");
                    Debug.Log("[Naval] fleet benchmark note: " + r.notes[r.notes.Count - 1]);
                }
            }
            foreach (var group in groups) group.ForceLOD(-1);
            r.status = r.failures.Count == 0 ? "completed" : "failed";
            r.completedUtc = DateTime.UtcNow.ToString("o");
            File.WriteAllText(Path.Combine(output, "fleet_benchmark.json"), JsonUtility.ToJson(r, true));
            benchmarkCamera.targetTexture = null;
            renderTarget.Release();
            Destroy(renderTarget);
            renderTarget = null;
            Application.Quit(r.failures.Count == 0 ? 0 : 1);
        }

        private static Timing Summarize(List<double> values)
        {
            if (values.Count == 0) return new Timing { available = false };
            values.Sort();
            double sum = 0;
            foreach (var value in values) sum += value;
            return new Timing {
                available = true, samples = values.Count, meanMs = sum / values.Count,
                medianMs = values[(int)Math.Floor((values.Count - 1) * .5)],
                p95Ms = values[(int)Math.Ceiling((values.Count - 1) * .95)],
                p99Ms = values[(int)Math.Ceiling((values.Count - 1) * .99)] };
        }

        /// <summary>LOD 选择的实际输入量：包围盒尺寸 × lodBias / (2 × 距离 × tan(fov/2))。</summary>
        public static float RelativeHeight(LODGroup group, Camera camera)
        {
            float distance = Vector3.Distance(camera.transform.position, group.transform.TransformPoint(group.localReferencePoint));
            if (distance <= 0) return 0;
            return group.size * QualitySettings.lodBias / (2 * distance * Mathf.Tan(camera.fieldOfView * .5f * Mathf.Deg2Rad));
        }

        /// <summary>Diagnostic estimate from the LODGroup's own thresholds; not a GPU draw-call counter.</summary>
        private static int LevelFromRelative(LODGroup group, float relative)
        {
            var levels = group.GetLODs();
            for (int i = 0; i < levels.Length; i++) if (relative >= levels[i].screenRelativeTransitionHeight) return i;
            return levels.Length;
        }
    }
}
