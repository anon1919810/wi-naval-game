using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Naval.EditorTools
{
    /// <summary>
    /// 把舰船在 Unity / URP 里真渲一遍，存图 + **逐像素检查**。
    ///
    /// 存在的理由：在这之前，"URP 下看着对不对"只有材质指向层面的证据，没有像素层面的。
    /// 而 URP 最典型的两个故障都是**静默**的，靠读代码或读对象数都发现不了：
    ///   · 材质 shader 不对 → 整船**品红**（几何/层级/坐标全对）
    ///   · 管线或 renderer data 配错 → 画面**全黑**或只有背景
    /// 这两件事在像素上一眼可判，所以让机器去判，而不是靠人看图。
    ///
    /// 判据（都是阻塞级）：
    ///   · 品红像素占比 < 2%。判据是「红蓝都高且明显高于绿」——灰色船体 r≈g≈b，永不误报。
    ///   · 舰船像素占比 > 1%，否则认为什么都没渲出来。
    ///   · 包围盒必须完整落在画面内（自动取景，不够就往后拉）。
    ///
    /// 另外每个视角额外记录两件**事实**（只报告、不断言，用来自查）：
    ///   · 舰艏在画面哪一侧（把 Barbette_A / Barbette_X 投影到视口比大小）
    ///   · 画面里出现多少级灰（证明确实按部位用了不同材质，而不是一片平灰）
    ///
    /// 用法：菜单 Tools/Naval/Render URP check images
    ///      批处理 -executeMethod Naval.EditorTools.ShipPreviewRender.RenderBatch
    /// </summary>
    public static class ShipPreviewRender
    {
        public const string ShipId = "HMS_Queen_Mary_1913";

        private const string ShipFolder = "Assets/Resources/Ships/" + ShipId;
        private const string ContractPath = ShipFolder + "/ship_contract.unity.json";
        // FBX 的文件名从契约读（ShipContractData.FbxFileName），不硬编码 ——
        // v2 与 v3 的文件名不同，写死会在换一代资产时静默对不上。

        /// <summary>图片与报告的落点：v3 资产目录。换机器/换代只改这两行。</summary>
        private static string OutputDir => Path.Combine(ShipRuntimeAcceptance.OutputDirectory, "unity_preview");
        private static string ReportPath => Path.Combine(ShipRuntimeAcceptance.OutputDirectory, "unity_render_check.json");

        private const int Width = 1280;
        private const int Height = 720;
        private const float MagentaLimit = 0.02f;   // 品红像素占比上限
        private const float OccupancyMin = 0.01f;   // 舰船像素占比下限

        private static readonly Color Background = new Color(0.16f, 0.18f, 0.21f, 1f);
        private static readonly Color Ambient = new Color(0.34f, 0.36f, 0.40f, 1f);

        // ---------------------------------------------------------------- report

        [Serializable]
        private class ViewResult
        {
            public string name;
            public string file;
            public int magentaPixels;
            public float magentaFraction;
            public float shipFraction;
            public float meanLuminance;
            public string greyLevels;      // 量化灰度级数，证明多种材质确实生效
            public bool fullyFramed;       // 包围盒是否完整在画面内
            public string bowOnScreen;     // "left" / "right"：舰艏出现在画面哪一侧
            public float cameraDistance_m;
        }

        [Serializable]
        private class Report
        {
            public string unityVersion;
            public string status;
            public string renderPipeline;
            public string renderPipelineAsset;
            public string shadersSeen;
            public int viewsRendered;
            public string[] checksFailed;
            public string[] notes;
            public ViewResult[] views;
        }

        // ---------------------------------------------------------------- entry

        [MenuItem("Tools/Naval/Render URP check images")]
        public static void RenderMenu()
        {
            var report = RenderAll();
            EditorUtility.DisplayDialog("URP 渲染校验",
                report.status == "passed"
                    ? string.Format("通过，{0} 个视角已出图。\n{1}", report.viewsRendered, OutputDir)
                    : "失败 " + report.checksFailed.Length + " 项：\n - " +
                      string.Join("\n - ", report.checksFailed), "好");
        }

        public static bool RenderForPipeline() => RenderAll().status == "passed";

        public static void RenderBatch()
        {
            var report = RenderAll();
            Debug.Log("[Naval] URP 渲染校验：" + report.status + "（" +
                      report.viewsRendered + " 个视角，失败 " + report.checksFailed.Length + " 项）");
            if (Application.isBatchMode) EditorApplication.Exit(
                report.status == "passed" ? 0 : 1);
        }

        // ------------------------------------------------------------ rendering

        private static Report RenderAll()
        {
            var failures = new List<string>();
            var notes = new List<string>();
            var report = new Report
            {
                unityVersion = Application.unityVersion,
                renderPipeline = GraphicsSettings.currentRenderPipeline != null
                    ? GraphicsSettings.currentRenderPipeline.GetType().Name
                    : "(Built-in)",
                renderPipelineAsset = GraphicsSettings.defaultRenderPipeline != null
                    ? GraphicsSettings.defaultRenderPipeline.name
                    : "(none)",
            };

            if (GraphicsSettings.defaultRenderPipeline == null)
                failures.Add("工程没有指定渲染管线（GraphicsSettings.defaultRenderPipeline 为空）——" +
                             "先跑 Tools > Naval > Set up URP");

            string modelPath = ResolveModelPath(notes);
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
            if (model == null)
            {
                failures.Add("找不到模型 " + modelPath);
                return Finish(report, failures, notes, null);
            }

            Directory.CreateDirectory(OutputDir);

            // 不新建场景。批处理里当前场景是"未保存的未命名场景"，Unity 会拒绝再加附加场景
            // （实测 InvalidOperationException: Cannot create a new scene additively with an
            //  untitled scene unsaved）。改成把临时物件放进当前场景、渲完销毁：
            // 两种调用方式都稳，而且从菜单跑时**不会把你正开着的场景换掉**。
            var results = new List<ViewResult>();
            var shaderNames = new List<string>();
            AmbientMode previousAmbientMode = RenderSettings.ambientMode;
            Color previousAmbientLight = RenderSettings.ambientLight;
            GameObject instance = null;

            try
            {
                instance = UnityEngine.Object.Instantiate(model);
                instance.transform.position = Vector3.zero;

                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = Ambient;

                Bounds bounds = WorldBounds(instance);
                notes.Add(string.Format("模型包围盒：中心 {0}，尺寸 {1:0.0} × {2:0.0} × {3:0.0} m",
                    bounds.center.ToString("F1"), bounds.size.x, bounds.size.y, bounds.size.z));

                foreach (var mr in instance.GetComponentsInChildren<MeshRenderer>(true))
                {
                    foreach (var mat in mr.sharedMaterials)
                    {
                        if (mat == null || mat.shader == null) continue;
                        if (!shaderNames.Contains(mat.shader.name)) shaderNames.Add(mat.shader.name);
                    }
                }
                shaderNames.Sort();
                report.shadersSeen = string.Join("、", shaderNames);

                foreach (var view in Views(bounds))
                {
                    var result = RenderView(instance, bounds, view, failures);
                    if (result != null) results.Add(result);
                }
            }
            catch (Exception e)
            {
                failures.Add("渲染过程抛异常：" + e.Message);
            }
            finally
            {
                if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
                RenderSettings.ambientMode = previousAmbientMode;
                RenderSettings.ambientLight = previousAmbientLight;
            }

            report.views = results.ToArray();
            report.viewsRendered = results.Count;
            if (results.Count == 0) failures.Add("一个视角都没渲出来");

            return Finish(report, failures, notes, results);
        }

        private struct View
        {
            public string name;
            public bool orthographic;
            public Vector3 direction;    // 相机相对中心的方位（会被归一化）
            public float startDistance;  // 起始距离（米）
            public Vector3 up;           // 画面里的"上"；正俯视必须换一个，否则与视线平行会让 LookAt 退化
        }

        private static List<View> Views(Bounds b)
        {
            float len = Mathf.Max(b.size.z, 1f);
            float span = b.size.magnitude;
            return new List<View>
            {
                new View { name = "Overview", orthographic = false,
                    direction = new Vector3(0.62f, 0.42f, 0.66f), startDistance = span * 1.1f,
                    up = Vector3.up },
                // 正侧视：摄像机在 +X（右舷侧）。此处向上为 +Y、舰艏 +Z，
                // 所以画面里舰艏应在**右侧** —— 报告里的 bowOnScreen 会如实写出实际值。
                new View { name = "Starboard", orthographic = true,
                    direction = new Vector3(1f, 0f, 0f), startDistance = len * 2f,
                    up = Vector3.up },
                // 正俯视：视线朝下，"上"取 -X。这样船长（Z）横放在画面里、且舰艏落在右侧，
                // 与侧视图一致；同时避免 LookAt 的 up 与视线平行而退化。
                // （第一版取的是 +Z，结果 213 m 的船长被竖着装不下，自动取景怎么拉都不行。）
                new View { name = "Top", orthographic = true,
                    direction = new Vector3(0f, 1f, 0f), startDistance = len * 2f,
                    up = Vector3.left },
                new View { name = "Bow", orthographic = false,
                    direction = new Vector3(0.18f, 0.20f, 0.96f), startDistance = len * 1.3f,
                    up = Vector3.up },
                new View { name = "Stern_Aft", orthographic = false,
                    direction = new Vector3(0.22f, 0.16f, -0.95f), startDistance = len * 1.3f,
                    up = Vector3.up },
            };
        }

        private static ViewResult RenderView(GameObject ship, Bounds bounds, View view,
                                            List<string> failures)
        {
            var camGo = new GameObject("PreviewCamera_Temporary");
            var lightGo = new GameObject("PreviewKey_Temporary");
            var cam = camGo.AddComponent<Camera>();
            var key = lightGo.AddComponent<Light>();
            // 显式声明这是 URP 相机：URP 会给没有附加数据的相机补默认值，
            // 但显式取一次最保险，也说明这里是按 URP 走的。
            cam.GetUniversalAdditionalCameraData();

            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Background;
            cam.aspect = (float)Width / Height;
            cam.nearClipPlane = 0.5f;
            cam.farClipPlane = 20000f;
            cam.orthographic = view.orthographic;

            // 每个视角带一盏**跟着相机走**的主光。第一版用一盏固定的全局太阳，
            // 结果朝相机那一面全在阴影里，出图几乎只剩剪影 —— 校验图读不出细节就等于没校验。
            key.type = LightType.Directional;
            key.color = new Color(1f, 0.97f, 0.92f, 1f);
            key.intensity = 1.25f;
            key.shadows = LightShadows.Soft;

            Vector3 centre = bounds.center;
            Vector3 dir = view.direction.normalized;
            float distance = view.startDistance;

            var rt = new RenderTexture(Width, Height, 24, RenderTextureFormat.ARGB32);
            rt.Create();
            var previous = RenderTexture.active;
            Texture2D shot = null;
            ViewResult result = null;
            bool framed = false;
            float usedDistance = distance;
            float framingScale = 1.12f;
            string bowSide = "unknown";

            try
            {
                // 自动取景：装不下就放宽构图。**正交相机要放的是 orthographicSize，不是距离** ——
                // 正交下距离不影响画面大小，第一版拉距离拉 8 次也没用（实测 Top 视图就是这么挂的）。
                for (int attempt = 0; attempt < 8; attempt++)
                {
                    PlaceCamera(cam, key, centre, dir, view.up, distance, view.orthographic,
                                bounds, framingScale);
                    framed = IsFramed(cam, bounds);
                    usedDistance = view.orthographic ? bounds.size.magnitude * 2f : distance;
                    if (framed) break;
                    if (view.orthographic) framingScale *= 1.18f;
                    else distance *= 1.18f;
                }

                // 必须在相机还有效时算：下面 finally 会把 camGo 销毁掉。
                bowSide = BowSide(cam, ship);

                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                shot = new Texture2D(Width, Height, TextureFormat.RGBA32, false);
                shot.ReadPixels(new Rect(0, 0, Width, Height), 0, 0);
                shot.Apply();
            }
            finally
            {
                RenderTexture.active = previous;
                cam.targetTexture = null;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(camGo);
                UnityEngine.Object.DestroyImmediate(lightGo);
            }

            if (shot == null)
            {
                failures.Add(view.name + "：读不回像素");
                return null;
            }

            string file = Path.Combine(OutputDir, view.name + ".png");
            File.WriteAllBytes(file, shot.EncodeToPNG());

            var pixels = shot.GetPixels32();
            Color measuredBackground = pixels[0]; // Readback already includes color-space conversion.
            int magenta = 0, shipPixels = 0;
            double luminance = 0;
            var greys = new HashSet<int>();
            foreach (var p in pixels)
            {
                float r = p.r / 255f, g = p.g / 255f, bl = p.b / 255f;
                if (r > 0.35f && bl > 0.35f && r - g > 0.25f && bl - g > 0.25f) magenta++;
                if (Mathf.Abs(r - measuredBackground.r) > 0.02f || Mathf.Abs(g - measuredBackground.g) > 0.02f ||
                    Mathf.Abs(bl - measuredBackground.b) > 0.02f)
                {
                    shipPixels++;
                    greys.Add(Mathf.RoundToInt(((r + g + bl) / 3f) * 31f));
                }
                luminance += (0.2126 * r + 0.7152 * g + 0.0722 * bl);
            }
            UnityEngine.Object.DestroyImmediate(shot);

            int total = pixels.Length;
            result = new ViewResult
            {
                name = view.name,
                file = "unity_preview/" + view.name + ".png",
                magentaPixels = magenta,
                magentaFraction = (float)magenta / total,
                shipFraction = (float)shipPixels / total,
                meanLuminance = (float)(luminance / total),
                greyLevels = greys.Count + " 级灰",
                fullyFramed = framed,
                bowOnScreen = bowSide,
                cameraDistance_m = usedDistance,
            };

            if (result.magentaFraction > MagentaLimit)
                failures.Add(string.Format("{0}：品红像素占 {1:0.0}% —— 材质 shader 不对，整船在冲你喊救命",
                    view.name, result.magentaFraction * 100f));
            if (result.shipFraction < OccupancyMin)
                failures.Add(string.Format("{0}：舰船像素只占 {1:0.00}% —— 基本什么都没渲出来（管线配错？）",
                    view.name, result.shipFraction * 100f));
            if (!framed)
                failures.Add(view.name + "：拉远 8 次仍装不下整条船，取景参数需要调");

            return result;
        }

        // ------------------------------------------------------------- helpers

        private static void PlaceCamera(Camera cam, Light key, Vector3 centre, Vector3 dir,
                                        Vector3 up, float distance, bool orthographic,
                                        Bounds bounds, float framingScale)
        {
            cam.transform.position = centre + dir * (orthographic ? bounds.size.magnitude * 2f : distance);
            cam.transform.LookAt(centre, up);
            key.transform.rotation = cam.transform.rotation * Quaternion.Euler(-28f, 34f, 0f);

            if (orthographic)
            {
                // 正交：竖向要装下 船长/宽高比，再乘余量倍数
                float needed = Mathf.Max(bounds.size.z / cam.aspect, bounds.size.y) * 0.5f;
                cam.orthographicSize = needed * framingScale;
            }
        }

        /// <summary>包围盒八个角是否都在视口内（留一点边距）。</summary>
        private static bool IsFramed(Camera cam, Bounds bounds)
        {
            for (int i = 0; i < 8; i++)
            {
                var corner = new Vector3(
                    (i & 1) == 0 ? bounds.min.x : bounds.max.x,
                    (i & 2) == 0 ? bounds.min.y : bounds.max.y,
                    (i & 4) == 0 ? bounds.min.z : bounds.max.z);
                Vector3 v = cam.WorldToViewportPoint(corner);
                if (v.z <= 0f) return false;
                if (v.x < -0.02f || v.x > 1.02f || v.y < -0.02f || v.y > 1.02f) return false;
            }
            return true;
        }

        /// <summary>
        /// 舰艏出现在画面哪一侧（把两个**有标注**的炮座投影到视口比大小）。
        /// 正对舰艏/舰艉的视角里两个炮座在画面上几乎重合，这时给 "head-on" 而不是
        /// 编一个 left/right —— 那种数据看着像结论，其实没有信息量。
        /// </summary>
        private static string BowSide(Camera cam, GameObject ship)
        {
            Transform bow = FindByName(ship, "Barbette_A");
            Transform stern = FindByName(ship, "Barbette_X");
            if (bow == null || stern == null) return "unknown";
            Vector3 b = cam.WorldToViewportPoint(bow.position);
            Vector3 s = cam.WorldToViewportPoint(stern.position);
            if (Mathf.Abs(b.x - s.x) < 0.05f) return "head-on";
            return b.x > s.x ? "right" : "left";
        }

        /// <summary>
        /// 优先渲染**构建好的预制体**（它才是游戏里真正会出现的那个东西），
        /// 没有预制体才退回 FBX。这样"关掉仅碰撞件之后船看着还正常吗"能被像素验到。
        /// 读不到契约就退回默认名 —— 但**会记一条提示**，不静默。
        /// </summary>
        private static string ResolveModelPath(List<string> notes)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(ShipRuntimeBuilder.PrefabPath);
            if (prefab != null)
            {
                notes.Add("渲染对象是构建好的预制体：" + ShipRuntimeBuilder.PrefabPath);
                return ShipRuntimeBuilder.PrefabPath;
            }
            notes.Add("还没有预制体（先跑 Build runtime ship），退回渲染原始 FBX");
            return ResolveFbxPath(notes);
        }

        /// <summary>
        /// FBX 路径从契约读，不硬编码文件名（v2/v3 文件名不同）。
        /// 读不到契约就退回默认名 —— 但**会记一条提示**，不静默。
        /// </summary>
        private static string ResolveFbxPath(List<string> notes)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string full = Path.Combine(projectRoot, ContractPath);
            if (!File.Exists(full))
            {
                notes.Add("找不到契约 " + ContractPath + "，退回默认 FBX 名");
                return ShipFolder + "/" + ShipContractData.FallbackFbxName;
            }
            try
            {
                var contract = ShipContractData.Parse(File.ReadAllText(full, Encoding.UTF8), ContractPath);
                return ShipFolder + "/" + contract.FbxFileName();
            }
            catch (Exception e)
            {
                notes.Add("契约解析失败，退回默认 FBX 名：" + e.Message);
                return ShipFolder + "/" + ShipContractData.FallbackFbxName;
            }
        }

        private static Transform FindByName(GameObject root, string name)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            return null;
        }

        private static Bounds WorldBounds(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0) return new Bounds(Vector3.zero, Vector3.one);
            var bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);
            return bounds;
        }

        private static Report Finish(Report report, List<string> failures, List<string> notes,
                                     List<ViewResult> results)
        {
            report.checksFailed = failures.ToArray();
            report.status = failures.Count == 0 ? "passed" : "failed";
            if (results != null && results.Count > 0)
                notes.Add("舰艏在画面中的位置：" + string.Join("、", results.ConvertAll(
                    r => r.name + "=" + r.bowOnScreen)));
            report.notes = notes.ToArray();

            string json = JsonUtility.ToJson(report, true);
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(ReportPath));
                File.WriteAllText(ReportPath, json, new UTF8Encoding(false));
                Debug.Log("[Naval] 渲染校验报告已写入 " + ReportPath);
            }
            catch (Exception e)
            {
                Debug.LogError("[Naval] 报告写入失败：" + e.Message + "\n" + json);
            }

            if (failures.Count == 0)
                Debug.Log(string.Format("[Naval] 渲染校验通过：{0} 个视角，管线 {1}，shader {2}",
                    report.viewsRendered, report.renderPipeline, report.shadersSeen));
            else
                Debug.LogError("[Naval] 渲染校验失败 " + failures.Count + " 项：\n - " +
                               string.Join("\n - ", failures));
            return report;
        }
    }
}
