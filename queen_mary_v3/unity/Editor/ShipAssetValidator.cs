using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Naval;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// 把 FBX 的实际形状与 ship_contract.unity.json 对上，并把 Unity 侧的轴向事实**实测**出来。
    ///
    /// 设计原则（这是本文件存在的理由）：
    ///  - **断言结果，不断言设置。** 「舰艏是否 +Z」用两个标志物的世界坐标差判定，
    ///    而不是检查导入设置里那个开关。设置可以被别人改，结果不会骗人。
    ///  - **测"游戏要用的约定"，不测同义反复。** 偏航/俯仰测的是**节点自身的哪个局部轴**
    ///    对应舰体竖直轴/横向轴，以及正负号；因为 Blender 的轴向转换会把内部旋转烘进节点，
    ///    局部 +Y 未必是舰体竖直轴。游戏拿到的就是这个可直接用的映射。
    ///  - **不确定的先测再冻结。** 符号第一次跑只记录；把测到的值填进 Baseline* 之后才成为阻塞断言。
    ///  - **契约是唯一字段来源。** 缺失的模块名一个不漏地列出，不做"大概能找到就行"。
    ///
    /// 用法：菜单 Tools/Naval/Validate ship asset
    ///      批处理：-batchmode -quit -projectPath <工程> -executeMethod Naval.EditorTools.ShipAssetValidator.ValidateBatch
    /// </summary>
    public static class ShipAssetValidator
    {
        public const string ShipId = "HMS_Queen_Mary_1913";

        private const string ShipFolder = "Assets/Resources/Ships/" + ShipId;
        // FBX 的文件名从契约读（ShipContractData.FbxFileName），这里不再硬编码 ——
        // v2/v3 文件名不同，写死会在换一代资产时静默对不上。
        private const string ContractPath = ShipFolder + "/ship_contract.unity.json";

        /// <summary>
        /// 报告写回资产目录，与资产本体放在一起。换机器只改这一行。
        /// 用 `_urp` 后缀而不是 `unity_verification.json`：后者是 v3 那边另一套导入工具的产物，
        /// 别互相覆盖 —— 两份证据讲的是不同的事（那边验导入，这边验契约/轴向/材质）。
        /// </summary>
        private static string ReportPath => Path.Combine(ShipRuntimeAcceptance.OutputDirectory, "unity_verification_urp.json");

        private const float ExpectLengthM = 213.4f;
        private const float ExpectBeamM = 27.2f;
        private const float ExpectHeightM = 15.0f;
        private const float DimToleranceM = 0.05f;
        private const float DirectionTolerance = 0.99f;
        private const float ProbeDeg = 10f;      // 测量时施加的试探角
        private const float ProbeMinEffect = 5f; // 小于这个幅度就认为该轴不是我们要找的轴

        // 2026-09-17 在 Unity 2022.3.62f3c1 里实测确认后冻结（FBX sha 1dcfdf26…）。
        // 冻结之后，任何改动导出轴向 / 翻转网格的行为都会立刻红。
        private const int BaselineYawSign = 1;          // 局部 +Z 轴，+10° 把炮口转向右舷
        private const int BaselinePitchSign = 1;        // 局部 +X 轴，+10° 抬高炮口
        private const int BaselineHullWindingSign = 1;  // 有符号体积为正（与 Blender 侧 +54,500.6 m³ 一致）

        // ---------------------------------------------------------------- report

        [Serializable]
        private class Vec3
        {
            public float x, y, z;
            public Vec3() { }
            public Vec3(Vector3 v) { x = v.x; y = v.y; z = v.z; }
        }

        [Serializable]
        private class TurretAxis
        {
            public string turret;
            public string yawAxis;
            public int yawSign;
            public string pitchAxis;
            public int pitchSign;
        }

        [Serializable]
        private class Report
        {
            public string unityVersion;
            public string status;
            public string shipId;
            public string assetVersion;
            public string sourceFbxPath;
            public string sourceFbxSha256;
            public int transformCount;
            public int meshCount;
            public int contractObjectCount;
            public int contractMeshCount;
            public string[] extraNodeNames;
            public Vec3 hullSizeMetres;
            public Vec3 hullMinMetres;
            public Vec3 hullMaxMetres;
            public Vec3 bowDirection;
            public float hullKeelY_m;
            public float hullDeckY_m;
            public bool upIsPositiveY;
            public float steeringGearY_m;
            public float hullSignedVolumeM3;
            public int hullWindingSign;
            public Vec3 rootEuler;
            public Vec3 rootScale;
            public string yawAxisLocalInNode;
            public int unityLocalYawSign;
            public string elevationAxisLocalInNode;
            public int unityLocalPitchSign;
            public bool yawAroundShipVertical;
            public bool positiveCommandTurnsStarboard;
            public bool elevationRaisesBarrel;
            public Vec3 starboardDirection;
            public int contractNamesChecked;
            public TurretAxis[] turretAxes;
            public string[] shadersInUse;
            public int renderersWithNonUrpShader;
            public string[] materialsWithoutUrpShader;
            public string[] missingContractNames;
            public string[] checksFailed;
            public string[] notes;
        }

        // ---------------------------------------------------------------- entry

        [MenuItem("Tools/Naval/Validate ship asset")]
        public static void ValidateMenu()
        {
            var report = Validate();
            string summary = report.status == "passed"
                ? string.Format("通过。\n{0} transform / {1} mesh\n主尺度 {2:0.00} × {3:0.00} × {4:0.00} m\n" +
                                "偏航：局部 {5} 轴，符号 {6}\n俯仰：局部 {7} 轴，符号 {8}",
                    report.transformCount, report.meshCount,
                    report.hullSizeMetres.x, report.hullSizeMetres.y, report.hullSizeMetres.z,
                    report.yawAxisLocalInNode, report.unityLocalYawSign,
                    report.elevationAxisLocalInNode, report.unityLocalPitchSign)
                : "失败 " + report.checksFailed.Length + " 项：\n - " +
                  string.Join("\n - ", report.checksFailed);
            EditorUtility.DisplayDialog("玛丽王后号 · 资产验证", summary, "好");
        }

        public static bool ValidateForPipeline() => Validate().status == "passed";

        public static void ValidateBatch()
        {
            var report = Validate();
            if (Application.isBatchMode)
                EditorApplication.Exit(report.status == "passed" ? 0 : 1);
        }

        // ------------------------------------------------------------ validation

        private static Report Validate()
        {
            var failures = new List<string>();
            var notes = new List<string>();
            var report = new Report
            {
                unityVersion = Application.unityVersion,
                shipId = ShipId,
                sourceFbxPath = "(待从契约解析)",
            };

            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string contractFull = Path.Combine(projectRoot, ContractPath);
            if (!File.Exists(contractFull))
            {
                failures.Add("找不到契约：" + ContractPath);
                return Finish(report, failures, notes);
            }

            ShipContractData contract = null;
            try { contract = ShipContractData.Parse(File.ReadAllText(contractFull, Encoding.UTF8), ContractPath); }
            catch (Exception e) { failures.Add("契约解析失败：" + e.Message); }

            // FBX 路径从契约读，不硬编码：v2 与 v3 的文件名不同，写死会在换资产时静默对不上。
            string fbxPath = ShipFolder + "/" + (contract != null
                ? contract.FbxFileName()
                : ShipContractData.FallbackFbxName);
            string fbxFull = Path.Combine(projectRoot, fbxPath);
            report.sourceFbxPath = fbxPath;

            if (!File.Exists(fbxFull))
            {
                failures.Add("找不到 FBX：" + fbxPath + "（契约 file_refs 里写的是 " +
                             (contract != null ? contract.FbxFileName() : "?") + "）");
                return Finish(report, failures, notes);
            }

            report.sourceFbxSha256 = Sha256(fbxFull);
            report.assetVersion = contract != null ? contract.asset_version : "?";
            if (contract != null && contract.ship_id != ShipId)
                failures.Add("契约 ship_id = " + contract.ship_id + "，与目录名 " + ShipId + " 不一致");

            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath);
            if (model == null)
            {
                failures.Add("AssetDatabase 读不到模型：" + fbxPath + "（Unity 是否已导入完成？）");
                return Finish(report, failures, notes);
            }

            GameObject instance = UnityEngine.Object.Instantiate(model);
            try
            {
                var nodes = IndexByName(instance, notes);
                report.rootEuler = new Vec3(instance.transform.eulerAngles);
                report.rootScale = new Vec3(instance.transform.lossyScale);

                // Unity 导入模型时可能在真正的层级之外再包一层根节点，所以数"子节点"
                // （实例根本身不计），这样契约里那个对象数才是可以逐一对上的。
                int childTransforms = 0;
                var observed = new HashSet<string>();
                foreach (var t in instance.GetComponentsInChildren<Transform>(true))
                {
                    if (t == instance.transform) continue;
                    childTransforms++;
                    observed.Add(t.name);
                }
                report.transformCount = childTransforms;
                report.meshCount = instance.GetComponentsInChildren<MeshFilter>(true).Length;

                var required = RequiredNames(contract);
                var requiredSet = new HashSet<string>(required);
                report.contractNamesChecked = required.Count;
                var missing = new List<string>();
                foreach (var name in required)
                    if (!nodes.ContainsKey(name)) missing.Add(name);
                report.missingContractNames = missing.ToArray();
                if (missing.Count > 0)
                    failures.Add("契约里有 " + missing.Count + " 个名字在模型里找不到：" +
                                 string.Join(", ", missing.GetRange(0, Math.Min(8, missing.Count))));

                var extra = new List<string>();
                foreach (var name in observed)
                    if (!requiredSet.Contains(name)) extra.Add(name);
                extra.Sort();
                report.extraNodeNames = extra.ToArray();

                if (contract != null)
                {
                    report.contractObjectCount = contract.object_count;
                    report.contractMeshCount = contract.mesh_count;
                    if (childTransforms != contract.object_count)
                        failures.Add(string.Format("对象数不符：模型 {0} 个子 transform，契约 {1}{2}",
                            childTransforms, contract.object_count,
                            extra.Count > 0 ? "；契约里没有的节点：" + string.Join(", ", extra) : ""));
                    if (contract.mesh_count > 0 && report.meshCount != contract.mesh_count)
                        failures.Add(string.Format("网格数不符：模型 {0} 个 mesh，契约 {1}",
                            report.meshCount, contract.mesh_count));
                }

                CheckHull(instance, report, failures, notes);
                CheckOrientation(nodes, report, failures);
                CheckMaterials(instance, report, failures, notes);
                CheckPivots(nodes, contract, report, failures, notes);

                // 全局轴缩放必须是 1，否则米就不再是米
                Vector3 s = instance.transform.lossyScale;
                if (Mathf.Abs(s.x - 1f) > 1e-3f || Mathf.Abs(s.y - 1f) > 1e-3f || Mathf.Abs(s.z - 1f) > 1e-3f)
                    failures.Add(string.Format("根节点缩放 {0:0.####} / {1:0.####} / {2:0.####}，应为 1",
                        s.x, s.y, s.z));
            }
            finally { UnityEngine.Object.DestroyImmediate(instance); }

            return Finish(report, failures, notes);
        }

        // ------------------------------------------------------------- helpers

        private static Dictionary<string, Transform> IndexByName(GameObject root, List<string> notes)
        {
            var map = new Dictionary<string, Transform>();
            var duplicates = new List<string>();
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                if (map.ContainsKey(t.name)) { if (!duplicates.Contains(t.name)) duplicates.Add(t.name); continue; }
                map[t.name] = t;
            }
            if (duplicates.Count > 0)
                notes.Add("模型里有重名节点（按名查找会歧义）：" + string.Join(", ", duplicates));
            return map;
        }

        private static List<string> RequiredNames(ShipContractData contract)
        {
            var names = new List<string>();
            if (contract == null) return names;
            foreach (var t in contract.turrets)
            {
                names.Add(t.turret);
                names.Add(t.pivot);
                names.Add(t.barbette);
                foreach (var b in t.barrels) names.Add(b);
            }
            foreach (var g in contract.secondary_guns) names.Add(g.name);
            foreach (var role in contract.module_roles)
                foreach (var n in role.names) names.Add(n);
            return names;
        }

        private static bool TryWorldBounds(GameObject root, string name, out Bounds bounds)
        {
            foreach (var mr in root.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (mr.name != name) continue;
                bounds = mr.bounds;
                return true;
            }
            bounds = default;
            return false;
        }

        private static void CheckHull(GameObject instance, Report report,
                                      List<string> failures, List<string> notes)
        {
            if (!TryWorldBounds(instance, "Hull", out var b))
            {
                failures.Add("模型里找不到 Hull 的 Renderer，无法核对主尺度");
                return;
            }
            report.hullSizeMetres = new Vec3(b.size);
            report.hullMinMetres = new Vec3(b.min);
            report.hullMaxMetres = new Vec3(b.max);

            AssertClose(b.size.z, ExpectLengthM, DimToleranceM, "船长 Z", failures);
            AssertClose(b.size.x, ExpectBeamM, DimToleranceM, "船宽 X", failures);
            AssertClose(b.size.y, ExpectHeightM, DimToleranceM, "型深 Y", failures);
            AssertClose(b.max.y, ExpectHeightM - 9.9f, 0.15f, "主甲板相对水线高度", failures);
            AssertClose(b.min.y, -9.9f, 0.15f, "龙骨相对水线深度（即吃水）", failures);

            // 向上方向由"甲板高于龙骨"判定 —— 两个标志物的坐标差会被 143 m 的纵向间隔
            // 主导（司令塔在舰艏、舵机在舰艉），那种判据是错的，别再用。
            report.hullDeckY_m = b.max.y;
            report.hullKeelY_m = b.min.y;
            report.upIsPositiveY = b.max.y > b.min.y;
            if (!report.upIsPositiveY)
                failures.Add(string.Format("甲板 (y = {0:0.00}) 低于龙骨 (y = {1:0.00}) —— 船是倒着的",
                    b.max.y, b.min.y));

            // 有符号体积：量级必须对（翻面/里外翻转在尺寸检查里完全看不出来），
            // 但**符号不能硬断言** —— Blender 用逆时针为正面、Unity 用顺时针，导入时绕序可能被翻转。
            // 所以符号走"先记录、冻结后才断言"的路子，并把量级先卡住。
            float volume = SignedVolume(instance, "Hull");
            report.hullSignedVolumeM3 = volume;
            if (Mathf.Abs(volume) < 5000f || Mathf.Abs(volume) > 80000f)
                failures.Add(string.Format("Hull 有符号体积 {0:0.0} m³ 不在合理区间（5,000–80,000）——" +
                    "多半是网格不闭合或法线有问题", volume));
            int winding = volume > 0f ? 1 : -1;
            report.hullWindingSign = winding;
            if (BaselineHullWindingSign == 0)
                notes.Add("绕序符号 = " + winding + "（尚未冻结：确认外观正常后写进 BaselineHullWindingSign）");
            else if (winding != BaselineHullWindingSign)
                failures.Add(string.Format("绕序符号 {0} 与基线 {1} 不符 —— 网格可能翻面了",
                    winding, BaselineHullWindingSign));
        }

        /// <summary>
        /// URP 下最典型的**静默**故障：材质还挂着内置 Standard shader，整艘船渲染成品红。
        /// 几何、层级、坐标、对象数全都正常，所以其它检查一条都不会响 —— 必须有这条。
        /// </summary>
        private static void CheckMaterials(GameObject instance, Report report,
                                          List<string> failures, List<string> notes)
        {
            var shaders = new List<string>();
            var bad = new List<string>();
            foreach (var mr in instance.GetComponentsInChildren<MeshRenderer>(true))
            {
                var materials = mr.sharedMaterials;
                if (materials == null || materials.Length == 0) { bad.Add(mr.name + " -> (无材质)"); continue; }
                foreach (var mat in materials)
                {
                    string shader = mat != null && mat.shader != null ? mat.shader.name : "(无材质)";
                    if (shader != "(无材质)" && !shaders.Contains(shader)) shaders.Add(shader);
                    if (shader.IndexOf("Universal Render Pipeline/", StringComparison.Ordinal) != 0)
                        bad.Add(mr.name + " -> " + shader);
                }
            }
            shaders.Sort();
            report.shadersInUse = shaders.ToArray();
            report.renderersWithNonUrpShader = bad.Count;
            report.materialsWithoutUrpShader = bad.GetRange(0, Math.Min(10, bad.Count)).ToArray();

            if (bad.Count > 0)
                failures.Add(string.Format("{0} 个材质槽用的不是 URP shader（会渲染成品红）：{1}",
                    bad.Count, string.Join("、", report.materialsWithoutUrpShader)));
            else if (shaders.Count > 0)
                notes.Add("材质 shader：" + string.Join("、", shaders));
        }

        /// <summary>闭合网格的有符号体积：按三角形累加有符号四面体体积。</summary>
        private static float SignedVolume(GameObject root, string name)
        {
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.name != name || mf.sharedMesh == null) continue;
                Vector3[] v = mf.sharedMesh.vertices;
                int[] tris = mf.sharedMesh.triangles;
                var localToWorld = mf.transform.localToWorldMatrix;
                float sum = 0f;
                for (int i = 0; i + 2 < tris.Length; i += 3)
                {
                    Vector3 p0 = localToWorld.MultiplyPoint3x4(v[tris[i]]);
                    Vector3 p1 = localToWorld.MultiplyPoint3x4(v[tris[i + 1]]);
                    Vector3 p2 = localToWorld.MultiplyPoint3x4(v[tris[i + 2]]);
                    sum += Vector3.Dot(p0, Vector3.Cross(p1, p2)) / 6f;
                }
                return sum;
            }
            return 0f;
        }

        /// <summary>
        /// 舰艏方向用两个**有标注**的标志物判定：A 塔在 X 塔之前（Blender 里 Y = +60 对 −68）。
        /// 它们都在中轴线上，所以这个判据不受左右镜像问题影响，是干净的。
        /// 向上方向不在这里判 —— 由 Hull 的龙骨/甲板高低判（见 CheckHull），
        /// 因为"司令塔顶 − 舵机"那种坐标差会被 143 m 的纵向间隔主导，是个错判据。
        /// </summary>
        private static void CheckOrientation(Dictionary<string, Transform> nodes, Report report,
                                             List<string> failures)
        {
            if (!nodes.TryGetValue("Barbette_A", out var a) || !nodes.TryGetValue("Barbette_X", out var x))
            {
                failures.Add("缺少 Barbette_A / Barbette_X，无法判定舰艏方向");
                return;
            }
            Vector3 bow = (a.position - x.position).normalized;
            report.bowDirection = new Vec3(bow);
            if (bow.z < DirectionTolerance)
                failures.Add(string.Format("舰艏不是 +Z（实测 {0:0.000} {1:0.000} {2:0.000}）——" +
                    "A 塔本应在 X 塔之前。这个不对，transform.forward 就指向舰艉，所有静置偏航差 180°",
                    bow.x, bow.y, bow.z));

            if (!nodes.TryGetValue("Steering_Gear", out var low))
            {
                failures.Add("缺少 Steering_Gear，无法核对水线基准");
                return;
            }
            report.steeringGearY_m = low.position.y;
            if (low.position.y > -1f)
                failures.Add(string.Format("舵机在 y = {0:0.00}，应在水线（y = 0）以下，水线基准错了",
                    low.position.y));

            // 物理右舷必须朝 Unity +X：用左右舷的副炮**实测**（Casemate_Starboard_1 - Casemate_Port_1）。
            // 这条是从 v3 那一侧的校验器并过来的 —— 我原本没找到判据：
            // 船体左右对称，**任何对船体本身的检查都判不出左右**；但它们各自带了左右舷的名字，
            // 于是两个**有标注**的点一减就是答案。
            // 而且它与导出偏转自洽：绕竖轴转 180° 会同时翻 X 和 Z，所以舰艏 +Z 时右舷正是 +X。
            if (!nodes.TryGetValue("Casemate_Starboard_1", out var stbd) ||
                !nodes.TryGetValue("Casemate_Port_1", out var port))
            {
                failures.Add("找不到 Casemate_Starboard_1 / Casemate_Port_1，无法判定物理右舷");
                return;
            }
            Vector3 starboard = (stbd.position - port.position).normalized;
            report.starboardDirection = new Vec3(starboard);
            if (starboard.x < 0.99f)
                failures.Add(string.Format("物理右舷不在 Unity +X（实测 {0:0.000} {1:0.000} {2:0.000}）——" +
                    "左右舷反了的话，装甲与损伤分区会整体镜像", starboard.x, starboard.y, starboard.z));
        }

        private static void CheckPivots(Dictionary<string, Transform> nodes, ShipContractData contract,
                                        Report report, List<string> failures, List<string> notes)
        {
            if (contract == null) return;

            var yawAxes = new List<string>();
            var yawSigns = new List<int>();
            var pitchAxes = new List<string>();
            var pitchSigns = new List<int>();
            bool anyVerticalYaw = false;
            // 逐炮塔的轴表：整体一致性之外，还要能看出**某一座**塔是不是单独跑偏了
            // （合并列表取平均会把它盖住）。这一条同样是从 v3 那一侧并过来的。
            var perTurret = new Dictionary<string, TurretAxis>();

            foreach (var t in contract.turrets)
            {
                if (!nodes.TryGetValue(t.turret, out var yaw) ||
                    !nodes.TryGetValue(t.pivot, out var pitch) ||
                    !nodes.TryGetValue(t.barbette, out var barbette))
                {
                    failures.Add(t.key + " 炮塔的偏航/俯仰/炮座节点不齐，无法检查枢轴链");
                    continue;
                }
                if (yaw.parent == null || pitch.parent == null)
                {
                    failures.Add(t.key + " 炮塔的枢轴节点没有父节点，层级不完整");
                    continue;
                }
                if (pitch.parent != yaw)
                    failures.Add(t.pivot + " 的父节点是 " + (pitch.parent ? pitch.parent.name : "null") +
                                 "，应为 " + t.turret + "（俯仰必须挂在偏航之下）");
                if (IsDescendantOf(barbette, yaw))
                    failures.Add(t.barbette + " 在偏航节点之下，转炮塔会把炮座一起转掉（炮座应独立固定）");

                foreach (var b in t.barrels)
                {
                    if (!nodes.TryGetValue(b, out var barrel)) continue;
                    if (barrel.parent != pitch)
                        failures.Add(b + " 的父节点是 " + (barrel.parent ? barrel.parent.name : "null") +
                                     "，应为 " + t.pivot + "（炮管要能独立命名、独立受创）");
                    if (barrel.GetComponent<MeshFilter>() == null) continue;

                    var yawProbe = ProbeAxis(yaw, barrel, true);
                    if (yawProbe.axis == null)
                        failures.Add(t.key + " 炮塔找不到偏航轴（三个局部轴都转不动炮口方位）");
                    else
                    {
                        yawAxes.Add(yawProbe.axis);
                        yawSigns.Add(yawProbe.sign);
                        if (yawProbe.effectDeg >= ProbeMinEffect) anyVerticalYaw = true;
                    }

                    var pitchProbe = ProbeAxis(pitch, barrel, false);
                    if (pitchProbe.axis == null)
                        notes.Add(t.key + " 炮塔找不到俯仰轴，未能测出俯仰约定");
                    else { pitchAxes.Add(pitchProbe.axis); pitchSigns.Add(pitchProbe.sign); }

                    if (!perTurret.ContainsKey(t.key))
                        perTurret[t.key] = new TurretAxis
                        {
                            turret = t.key,
                            yawAxis = yawProbe.axis,
                            yawSign = yawProbe.sign,
                            pitchAxis = pitchProbe.axis,
                            pitchSign = pitchProbe.sign,
                        };

                    // 炮管原点必须**落在耳轴上**：允许**沿**耳轴有横向偏移（那就是两管间距），
                    // 但垂直于耳轴的两个分量必须为 0 —— 否则抬高炮口时炮管会绕错圆心。
                    //
                    // 这里踩过一次坑：v2 把横向间距烘进几何、炮管局部位置是 0；v3 改成把间距放在
                    // transform 上（±1.25 m，沿耳轴），更真实。旧检查写死"局部位置必须为 0"，
                    // 于是 v3 被判成"枢轴契约被破坏"——**那是把 v2 的实现细节误当成了契约**。
                    Vector3 lp = barrel.localPosition;
                    float offAxis;
                    float alongAxis;
                    if (pitchProbe.axis == "X") { offAxis = Mathf.Abs(lp.y) + Mathf.Abs(lp.z); alongAxis = lp.x; }
                    else if (pitchProbe.axis == "Y") { offAxis = Mathf.Abs(lp.x) + Mathf.Abs(lp.z); alongAxis = lp.y; }
                    else if (pitchProbe.axis == "Z") { offAxis = Mathf.Abs(lp.x) + Mathf.Abs(lp.y); alongAxis = lp.z; }
                    else { offAxis = lp.magnitude; alongAxis = 0f; }

                    if (offAxis > 1e-4f)
                        failures.Add(string.Format("{0} 原点偏离耳轴 {1:0.0000} m（垂直分量）——" +
                            "抬高炮口时炮管会绕错圆心", b, offAxis));
                    else
                    {
                        string spacing = "耳轴上的炮管间距：±" + Mathf.Abs(alongAxis).ToString("0.00") + " m";
                        if (!notes.Contains(spacing)) notes.Add(spacing);
                    }
                }
            }

            var axes = new List<TurretAxis>(perTurret.Values);
            axes.Sort((a2, b2) => string.Compare(a2.turret, b2.turret, StringComparison.Ordinal));
            report.turretAxes = axes.ToArray();

            report.yawAroundShipVertical = anyVerticalYaw;
            report.positiveCommandTurnsStarboard = yawAxes.Count > 0;

            if (yawAxes.Count > 0)
            {
                string axis = Agree(yawAxes);
                int sign = AgreeSign(yawSigns);
                report.yawAxisLocalInNode = axis;
                report.unityLocalYawSign = sign;
                if (axis == null)
                    failures.Add("各炮塔的偏航局部轴不一致（" + string.Join(" ", yawAxes) +
                                 "）——战斗系统无法用统一写法");
                if (sign == 0)
                    failures.Add("各炮塔的偏航符号不一致（" + string.Join(" ", yawSigns) + "）");
                if (sign != 0 && BaselineYawSign != 0 && sign != BaselineYawSign)
                    failures.Add(string.Format("偏航符号 {0} 与基线 {1} 不符——轴向约定变了", sign, BaselineYawSign));
                else if (sign != 0 && BaselineYawSign == 0)
                    notes.Add("偏航符号 = " + sign + "（尚未冻结：确认无误后写进 BaselineYawSign）");
            }

            if (pitchAxes.Count > 0)
            {
                string axis = Agree(pitchAxes);
                int sign = AgreeSign(pitchSigns);
                report.elevationAxisLocalInNode = axis;
                report.unityLocalPitchSign = sign;
                report.elevationRaisesBarrel = sign != 0;
                if (axis == null)
                    failures.Add("各炮塔的俯仰局部轴不一致（" + string.Join(" ", pitchAxes) + "）");
                if (sign == 0)
                    failures.Add("各炮塔的俯仰符号不一致（" + string.Join(" ", pitchSigns) + "）");
                if (sign != 0 && BaselinePitchSign != 0 && sign != BaselinePitchSign)
                    failures.Add(string.Format("俯仰符号 {0} 与基线 {1} 不符", sign, BaselinePitchSign));
                else if (sign != 0 && BaselinePitchSign == 0)
                    notes.Add("俯仰符号 = " + sign + "（尚未冻结：确认无误后写进 BaselinePitchSign）");
            }
        }

        private static string Agree(List<string> values)
        {
            for (int i = 1; i < values.Count; i++) if (values[i] != values[0]) return null;
            return values[0];
        }

        private static int AgreeSign(List<int> values)
        {
            for (int i = 1; i < values.Count; i++) if (values[i] != values[0]) return 0;
            return values[0];
        }

        private struct AxisProbe
        {
            public string axis;     // "X" / "Y" / "Z"：节点**自身局部**轴
            public int sign;        // +1 / -1：写进游戏代码的正负号
            public float effectDeg; // 该轴实际造成的方位角/仰角变化
        }

        /// <summary>
        /// 找出该节点自身哪个局部轴在转炮口，以及"正方向"对应的符号。
        ///
        /// 为什么必须实测：Blender 用 axis_up='Y' 导出时会把轴向转换烘进节点，
        /// 于是局部 +Y 未必是舰体竖直轴。游戏代码要的是 `localRotation = rest *
        /// Quaternion.AngleAxis(sign * angle, 局部某轴)` 里的那个轴和符号，不是根节点欧拉角。
        /// 后乘 = 在节点自身坐标系内旋转，正是游戏侧的自然写法。
        /// </summary>
        private static AxisProbe ProbeAxis(Transform node, Transform barrel, bool yaw)
        {
            var candidates = new[] { Vector3.right, Vector3.up, Vector3.forward };
            var names = new[] { "X", "Y", "Z" };
            var result = new AxisProbe { axis = null, sign = 0, effectDeg = 0f };

            Quaternion rest = node.localRotation;
            float before = yaw ? Azimuth(barrel) : Elevation(barrel);
            float bestEffect = 0f;

            for (int i = 0; i < candidates.Length; i++)
            {
                for (int s = 1; s >= -1; s -= 2)
                {
                    node.localRotation = rest * Quaternion.AngleAxis(s * ProbeDeg, candidates[i]);
                    float effect = yaw
                        ? Mathf.DeltaAngle(before, Azimuth(barrel))
                        : Elevation(barrel) - before;
                    node.localRotation = rest;

                    // 偏航：取让方位角朝正方向（向右舷）走的那一侧
                    // 俯仰：取让仰角上升的那一侧
                    if (effect > 0f && effect > bestEffect)
                    {
                        bestEffect = effect;
                        result.axis = names[i];
                        result.sign = s;
                        result.effectDeg = effect;
                    }
                }
            }
            node.localRotation = rest;
            return result;
        }

        private static bool IsDescendantOf(Transform node, Transform ancestor)
        {
            for (var t = node; t != null; t = t.parent) if (t == ancestor) return true;
            return false;
        }

        /// <summary>炮口方位角（世界水平面，+Z 为 0°，向右舷 +X 为正）。</summary>
        private static float Azimuth(Transform barrel)
        {
            Vector3 d = MuzzleEnd(barrel) - barrel.position;
            return Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
        }

        /// <summary>炮口仰角（度），水平为 0。</summary>
        private static float Elevation(Transform barrel)
        {
            Vector3 d = (MuzzleEnd(barrel) - barrel.position).normalized;
            return Mathf.Asin(Mathf.Clamp(d.y, -1f, 1f)) * Mathf.Rad2Deg;
        }

        /// <summary>炮管网格包围盒里离枢轴最远的角 = 炮口端。</summary>
        private static Vector3 MuzzleEnd(Transform barrel)
        {
            var mf = barrel.GetComponent<MeshFilter>();
            if (mf == null || mf.sharedMesh == null) return barrel.position;
            Bounds b = mf.sharedMesh.bounds;
            Vector3 pivot = barrel.position;
            Vector3 best = pivot;
            float bestSq = -1f;
            for (int i = 0; i < 8; i++)
            {
                var local = new Vector3(
                    (i & 1) == 0 ? b.min.x : b.max.x,
                    (i & 2) == 0 ? b.min.y : b.max.y,
                    (i & 4) == 0 ? b.min.z : b.max.z);
                Vector3 world = barrel.TransformPoint(local);
                float sq = (world - pivot).sqrMagnitude;
                if (sq > bestSq) { bestSq = sq; best = world; }
            }
            return best;
        }

        private static void AssertClose(float actual, float expected, float tolerance,
                                        string label, List<string> failures)
        {
            if (Mathf.Abs(actual - expected) > tolerance)
                failures.Add(string.Format("{0} 不符：实测 {1:0.000}，期望 {2:0.000}（容差 ±{3:0.000}）",
                    label, actual, expected, tolerance));
        }

        private static string Sha256(string path)
        {
            using (var sha = SHA256.Create())
            using (var stream = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }

        private static Report Finish(Report report, List<string> failures, List<string> notes)
        {
            report.checksFailed = failures.ToArray();
            report.status = failures.Count == 0 ? "passed" : "failed";
            report.notes = notes.ToArray();

            string json = JsonUtility.ToJson(report, true);
            try
            {
                string dir = Path.GetDirectoryName(ReportPath);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(ReportPath, json, new UTF8Encoding(false));
                Debug.Log("[Naval] 验证报告已写入 " + ReportPath);
            }
            catch (Exception e)
            {
                Debug.LogError("[Naval] 报告写入失败：" + e.Message + "\n报告内容：\n" + json);
            }

            if (failures.Count == 0)
                Debug.Log(string.Format("[Naval] 资产验证通过：{0} transform / {1} mesh；偏航 局部{2}轴 符号{3}；俯仰 局部{4}轴 符号{5}",
                    report.transformCount, report.meshCount,
                    report.yawAxisLocalInNode, report.unityLocalYawSign,
                    report.elevationAxisLocalInNode, report.unityLocalPitchSign));
            else
                Debug.LogError("[Naval] 资产验证失败 " + failures.Count + " 项：\n - " +
                               string.Join("\n - ", failures));
            return report;
        }
    }
}
