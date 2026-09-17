using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// 把导入好的模型变成**能跑的船**：仅碰撞件关掉渲染、舱室挂上数据与碰撞体，
    /// 存成预制体，并生成 ShipDefinition 资产。
    ///
    /// 为什么需要这一步（一句话）：85 个网格里有 24 个在船壳内部、永远看不见，
    /// 现在却照样在渲染 —— 每艘船白扔 28% 的 draw call，还有戳出船壳的风险。
    ///
    /// 用法：菜单 Tools/Naval/Build runtime ship
    ///      批处理 -executeMethod Naval.EditorTools.ShipRuntimeBuilder.BuildBatch
    /// </summary>
    public static class ShipRuntimeBuilder
    {
        public const string ShipId = "HMS_Queen_Mary_1913";

        private const string ShipFolder = "Assets/Resources/Ships/" + ShipId;
        private const string ContractPath = ShipFolder + "/ship_contract.unity.json";
        private const string DamagePath = ShipFolder + "/damage_model.json";
        private const string BuoyancyPath = ShipFolder + "/buoyancy_compartments.json";
        private const string HydrostaticsPath = ShipFolder + "/hydrostatics.json";
        private const string PrefabDir = "Assets/Prefabs/Ships";
        /// <summary>构建出来的预制体路径。渲染校验会优先渲它（它才是游戏里真正出现的那个）。</summary>
        public const string PrefabPath = PrefabDir + "/" + ShipId + ".prefab";
        // 文件名不带点：静态预检会把"类名 + 点 + 后缀"的字符串误判成引用了未声明成员。
        private const string DefinitionPath = ShipFolder + "/" + ShipId + "_Definition.asset";
        private const string MaterialDir = "Assets/Materials/Naval";

        private const string ReportPath =
            @"C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3\ship_runtime_build.json";

        /// <summary>
        /// 只参与碰撞、不参与渲染的角色。这些部件都在船壳内部，永远看不见。
        /// **这个分类要对契约里的角色名负责**：下面有交叉检查，角色一旦改名会立刻报错而不是静默漏掉。
        /// </summary>
        private static readonly string[] CollisionOnlyRoles =
        {
            "armour_belt", "armour_bulkhead", "armour_deck",
            "boiler_room", "engine_room", "magazine",
            "steering_gear", "propulsion_underwater", "rudder",
        };

        /// <summary>其中真正算"损伤舱室"的角色（要挂 ShipCompartment 与进水数据）。</summary>
        private static readonly string[] CompartmentRoles = { "boiler_room", "engine_room", "magazine" };

        // ---------------------------------------------------------------- report

        [Serializable]
        public class Report
        {
            public string status;
            public string shipId;
            public string prefabPath;
            public string definitionPath;
            public int objectCount;
            public int meshCount;
            public int renderersDisabled;
            public int collidersAdded;
            public int compartments;
            public int compartmentsWithBuoyancyData;
            public string[] collisionOnlyRoles;
            public string[] unusedRoles;
            public string[] checksFailed;
            public string[] notes;
        }

        [Serializable] private class BuoyancyFile { public CompartmentRow[] compartments; }

        [Serializable]
        private class CompartmentRow
        {
            public string module;
            public string role;
            public float volume_m3;
            public float[] centroid_world_m;
            public float permeability;
            public float floodable_volume_m3;
        }

        [Serializable] private class HydroFile { public float displacement_t_at_1_025; }

        // ---------------------------------------------------------------- entry

        [MenuItem("Tools/Naval/Build runtime ship")]
        public static void BuildMenu()
        {
            var report = Build();
            EditorUtility.DisplayDialog("构建运行时船体",
                report.status == "passed"
                    ? string.Format("通过。\n关渲染 {0} 个，加碰撞体 {1} 个，舱室 {2} 个。\n{3}",
                        report.renderersDisabled, report.collidersAdded, report.compartments,
                        report.definitionPath)
                    : "失败 " + report.checksFailed.Length + " 项：\n - " +
                      string.Join("\n - ", report.checksFailed), "好");
        }

        public static void BuildBatch()
        {
            var report = Build();
            Debug.Log("[Naval] 运行时船体构建：" + report.status + "（关渲染 " + report.renderersDisabled +
                      "，碰撞体 " + report.collidersAdded + "，舱室 " + report.compartments + "）");
            if (Application.isBatchMode) EditorApplication.Exit(
                report.status == "passed" ? 0 : 1);
        }

        // ----------------------------------------------------------------- build

        public static Report Build()
        {
            var failures = new List<string>();
            var notes = new List<string>();
            var report = new Report { shipId = ShipId, collisionOnlyRoles = CollisionOnlyRoles };

            string projectRoot = Directory.GetParent(Application.dataPath).FullName;

            // --- 契约 ---------------------------------------------------------
            string contractFull = Path.Combine(projectRoot, ContractPath);
            if (!File.Exists(contractFull))
            {
                failures.Add("找不到契约 " + ContractPath);
                return Finish(report, failures, notes);
            }
            ShipContractData contract;
            try { contract = ShipContractData.Parse(File.ReadAllText(contractFull, Encoding.UTF8), ContractPath); }
            catch (Exception e)
            {
                failures.Add("契约解析失败：" + e.Message);
                return Finish(report, failures, notes);
            }

            // --- 角色名交叉检查（防止改名后静默漏掉）--------------------------
            var roleByName = new Dictionary<string, string>();
            var rolesInContract = new HashSet<string>();
            foreach (var group in contract.module_roles)
            {
                if (group == null) continue;
                rolesInContract.Add(group.role);
                foreach (var name in group.names) roleByName[name] = group.role;
            }
            var stale = new List<string>();
            foreach (var role in CollisionOnlyRoles)
                if (!rolesInContract.Contains(role)) stale.Add(role);
            if (stale.Count > 0)
                failures.Add("契约里没有这些角色：" + string.Join("、", stale) +
                             " —— 是角色改名了，还是这条分类过时了？别让它静默失效。");
            report.unusedRoles = stale.ToArray();

            // --- 模型 ---------------------------------------------------------
            string fbx = ShipFolder + "/" + contract.FbxFileName();
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
            if (model == null)
            {
                failures.Add("找不到模型 " + fbx);
                return Finish(report, failures, notes);
            }

            // --- 浮力 / 静水力 -----------------------------------------------
            var buoyancyByName = new Dictionary<string, CompartmentRow>();
            string buoyancyFull = Path.Combine(projectRoot, BuoyancyPath);
            if (File.Exists(buoyancyFull))
            {
                var file = JsonUtility.FromJson<BuoyancyFile>(File.ReadAllText(buoyancyFull, Encoding.UTF8));
                if (file != null && file.compartments != null)
                    foreach (var row in file.compartments) buoyancyByName[row.module] = row;
            }
            else notes.Add("没有 " + BuoyancyPath + "，舱室只能用包围盒估算体积，渗透率按 0 处理");

            // --- 实例化并改造 -------------------------------------------------
            GameObject instance = null;
            try
            {
                instance = UnityEngine.Object.Instantiate(model);
                report.objectCount = 0;
                report.meshCount = 0;

                foreach (var child in instance.GetComponentsInChildren<Transform>(true))
                {
                    if (child == instance.transform) continue;
                    report.objectCount++;
                    if (child.GetComponent<MeshFilter>() != null) report.meshCount++;

                    string role;
                    if (!roleByName.TryGetValue(child.name, out role)) continue;
                    if (Array.IndexOf(CollisionOnlyRoles, role) < 0) continue;

                    // 1) 关掉渲染：这些件在船壳内部，画了也看不见
                    var renderer = child.GetComponent<Renderer>();
                    if (renderer != null) { renderer.enabled = false; report.renderersDisabled++; }

                    // 2) 加碰撞体。用**盒体**而不是网格碰撞体：15 艘船 × 24 个网格碰撞体会压垮物理；
                    //    做成 trigger 是为了不让船与船互相卡住（射线检测记得传 QueryTriggerInteraction.Collide）。
                    var filter = child.GetComponent<MeshFilter>();
                    var collider = child.gameObject.AddComponent<BoxCollider>();
                    if (filter != null && filter.sharedMesh != null)
                    {
                        collider.center = filter.sharedMesh.bounds.center;
                        collider.size = filter.sharedMesh.bounds.size;
                    }
                    collider.isTrigger = true;
                    report.collidersAdded++;

                    // 3) 损伤舱室：把体积 / 渗透率 / 可进水体积钉到对象上
                    if (Array.IndexOf(CompartmentRoles, role) >= 0)
                    {
                        Vector3 size = collider.size;
                        Vector3 scale = child.lossyScale;
                        float fallback = size.x * scale.x * size.y * scale.y * size.z * scale.z;
                        var compartment = child.gameObject.AddComponent<ShipCompartment>();
                        compartment.compartmentId = child.name;
                        compartment.role = role;
                        CompartmentRow row;
                        if (buoyancyByName.TryGetValue(child.name, out row))
                        {
                            compartment.volumeM3 = row.volume_m3;
                            compartment.permeability = row.permeability;
                            compartment.floodableVolumeM3 = row.floodable_volume_m3;
                            compartment.belowWaterline = row.centroid_world_m != null &&
                                                         row.centroid_world_m.Length >= 3 &&
                                                         row.centroid_world_m[2] < 0f;
                            compartment.dataFromBuoyancyFile = true;
                            report.compartmentsWithBuoyancyData++;
                        }
                        else
                        {
                            compartment.volumeM3 = fallback;
                            compartment.permeability = 0f;
                            compartment.floodableVolumeM3 = 0f;
                            compartment.dataFromBuoyancyFile = false;
                            notes.Add("舱室 " + child.name + " 不在浮力表里，体积用包围盒估算 " +
                                      fallback.ToString("0") + " m³，渗透率按 0（暂不进水）");
                        }
                        compartment.belowWaterline |= child.position.y < 0f;
                        report.compartments++;
                    }
                }

                // --- 存预制体 --------------------------------------------------
                EnsureFolder(PrefabDir);
                var prefab = PrefabUtility.SaveAsPrefabAsset(instance, PrefabPath);
                if (prefab == null)
                {
                    failures.Add("预制体保存失败：" + PrefabPath);
                    return Finish(report, failures, notes);
                }
                report.prefabPath = PrefabPath;
                notes.Add("预制体已生成：" + PrefabPath);
            }
            catch (Exception e)
            {
                failures.Add("构建过程抛异常：" + e.Message);
                return Finish(report, failures, notes);
            }
            finally
            {
                if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
            }

            // --- ShipDefinition ------------------------------------------------
            report.definitionPath = DefinitionPath;
            try
            {
                WriteDefinition(contract);
                notes.Add("ShipDefinition 已更新：" + DefinitionPath);
            }
            catch (Exception e)
            {
                failures.Add("写 ShipDefinition 失败：" + e.Message);
            }

            if (report.renderersDisabled == 0)
                failures.Add("一个渲染器都没关 —— 仅碰撞分类没生效？检查角色名是否对得上");

            return Finish(report, failures, notes);
        }

        // -------------------------------------------------------------- helpers

        private static void WriteDefinition(ShipContractData contract)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;

            var definition = AssetDatabase.LoadAssetAtPath<ShipDefinition>(DefinitionPath);
            if (definition == null)
            {
                definition = ScriptableObject.CreateInstance<ShipDefinition>();
                AssetDatabase.CreateAsset(definition, DefinitionPath);
            }

            definition.shipId = contract.ship_id;
            definition.assetVersion = contract.asset_version;
            definition.contract = AssetDatabase.LoadAssetAtPath<TextAsset>(ContractPath);
            definition.prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            definition.lengthM = contract.length_m;
            definition.beamM = contract.beam_m;
            definition.draftM = contract.draft_m;
            definition.objectCount = contract.object_count;
            definition.meshCount = contract.mesh_count;

            var materials = new List<Material>();
            foreach (var guid in AssetDatabase.FindAssets("t:Material", new[] { MaterialDir }))
            {
                var mat = AssetDatabase.LoadAssetAtPath<Material>(AssetDatabase.GUIDToAssetPath(guid));
                if (mat != null) materials.Add(mat);
            }
            definition.materials = materials.ToArray();

            string hydroFull = Path.Combine(projectRoot, HydrostaticsPath);
            if (File.Exists(hydroFull))
                definition.displacementT = Mathf.RoundToInt(JsonUtility
                    .FromJson<HydroFile>(File.ReadAllText(hydroFull, Encoding.UTF8)).displacement_t_at_1_025);

            var bindings = new List<TurretBinding>();
            foreach (var t in contract.turrets)
                bindings.Add(new TurretBinding
                {
                    key = t.key, yawNode = t.turret, pitchNode = t.pivot, barrels = t.barrels,
                    restYawDeg = t.rest_yaw_deg,
                    minElevationDeg = t.min_elevation_deg,
                    maxElevationDeg = t.max_elevation_deg,
                });
            definition.turrets = bindings.ToArray();

            definition.builtUtc = DateTime.UtcNow.ToString("s") + "Z";
            definition.notes = "由 ShipRuntimeBuilder 生成，不要手填。仅碰撞件已关渲染，舱室已挂数据与 trigger 碰撞体。";

            EditorUtility.SetDirty(definition);
            AssetDatabase.SaveAssets();
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }

        private static Report Finish(Report report, List<string> failures, List<string> notes)
        {
            report.checksFailed = failures.ToArray();
            report.notes = notes.ToArray();
            report.status = failures.Count == 0 ? "passed" : "failed";

            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(ReportPath));
                File.WriteAllText(ReportPath, JsonUtility.ToJson(report, true), new UTF8Encoding(false));
                Debug.Log("[Naval] 构建报告已写入 " + ReportPath);
            }
            catch (Exception e) { Debug.LogError("[Naval] 报告写入失败：" + e.Message); }

            if (failures.Count == 0)
                Debug.Log(string.Format("[Naval] 运行时船体构建通过：关渲染 {0} 个，碰撞体 {1} 个，舱室 {2} 个",
                    report.renderersDisabled, report.collidersAdded, report.compartments));
            else
                Debug.LogError("[Naval] 运行时船体构建失败 " + failures.Count + " 项：\n - " +
                               string.Join("\n - ", failures));
            return report;
        }
    }
}
