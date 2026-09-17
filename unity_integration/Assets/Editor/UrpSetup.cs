using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Naval;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Naval.EditorTools
{
    /// <summary>
    /// 把工程切到 URP，并把舰船材质建成 URP/Lit。
    ///
    /// 三件事，按依赖顺序：
    ///   1. 建 UniversalRendererData + UniversalRenderPipelineAsset（Assets/Settings/），
    ///      并设为 GraphicsSettings.defaultRenderPipeline。
    ///      —— 只设默认管线就够了：各质量档的 renderPipeline 若为 null 会继承默认值。
    ///   2. 按**契约里的 materials 表**建 URP/Lit 材质（灰度值不在 C# 里重复一遍，
    ///      Blender 侧 MATERIAL_SPECS 是唯一来源）。
    ///   3. 重导舰船 FBX，好让 ShipMaterialRemap 把这些材质贴上去。
    ///
    /// 材质色值是**线性**的：Blender 的 Base Color 是线性值，URP 的 _BaseColor 也是线性值，
    /// 所以直接搬运，不做 sRGB 转换。灰盒的深灰看起来就该是深灰。
    ///
    /// 用法：菜单 Tools/Naval/Set up URP
    ///      批处理 -executeMethod Naval.EditorTools.UrpSetup.SetUpBatch
    /// </summary>
    public static class UrpSetup
    {
        public const string ShipId = "HMS_Queen_Mary_1913";

        private const string SettingsDir = "Assets/Settings";
        private const string MaterialDir = "Assets/Materials/Naval";
        private const string RendererPath = SettingsDir + "/QueenMary_UniversalRenderer.asset";
        private const string PipelinePath = SettingsDir + "/QueenMary_URP.asset";
        private const string ContractPath =
            "Assets/Resources/Ships/" + ShipId + "/ship_contract.unity.json";
        // FBX 的文件名从契约读（ShipContractData.FbxFileName），不硬编码 ——
        // v2 与 v3 的文件名不同，写死会在换一代资产时静默对不上。

        private const string LitShader = "Universal Render Pipeline/Lit";

        /// <summary>URP 包里的默认后处理数据。（URP 内部的 GetDefaultPostProcessData 就是加载它。）</summary>
        private const string DefaultPostProcessDataPath =
            "Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset";

        [MenuItem("Tools/Naval/Set up URP")]
        public static void SetUpMenu()
        {
            var report = SetUp();
            EditorUtility.DisplayDialog("切换到 URP", report, "好");
        }

        public static void SetUpBatch()
        {
            string report = SetUp();
            Debug.Log("[Naval] URP 装配：\n" + report);
            if (Application.isBatchMode) EditorApplication.Exit(
                report.Contains("失败") ? 1 : 0);
        }

        public static string SetUp()
        {
            var log = new StringBuilder();

            // --- 1. 管线资产 -------------------------------------------------
            EnsureFolder(SettingsDir);
            Shader shader = Shader.Find(LitShader);
            if (shader == null)
            {
                log.AppendLine("失败：找不到 shader " + LitShader +
                               "。URP 包没装上？先确认 Packages/manifest.json 里有 " +
                               "com.unity.render-pipelines.universal。");
                return log.ToString();
            }
            log.AppendLine("URP shader 就位：" + shader.name);

            var rendererData = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(RendererPath);
            if (rendererData == null)
            {
                rendererData = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(rendererData, RendererPath);
                log.AppendLine("新建 renderer data：" + RendererPath);
            }
            else log.AppendLine("复用 renderer data：" + RendererPath);

            // URP 的 UniversalRenderPipelineAsset.Create() 只给**管线资产**补资源引用
            // （它内部调 ReloadAllNullIn(instance, packagePath)），**传进去的 renderer data 不补**。
            // 官方创建流程（UniversalRenderPipelineAsset.CreateRendererData）还多做一件事：
            //     rendererData.postProcessData = PostProcessData.GetDefaultPostProcessData();
            // 那个方法是 internal，但它内部就是一句 LoadAssetAtPath，所以这里用公开 API 复刻。
            // 漏掉它 → 后处理数据为空 → ReloadAllNullIn 返回 false（实测过）。
            if (rendererData.postProcessData == null)
            {
                var postProcess = AssetDatabase.LoadAssetAtPath<PostProcessData>(DefaultPostProcessDataPath);
                if (postProcess != null)
                {
                    rendererData.postProcessData = postProcess;
                    log.AppendLine("已指派默认后处理数据：" + DefaultPostProcessDataPath);
                }
                else
                {
                    log.AppendLine("警告：找不到默认后处理数据 " + DefaultPostProcessDataPath +
                                   "（后处理会不可用）");
                }
            }

            bool reloaded = ResourceReloader.ReloadAllNullIn(
                rendererData, UniversalRenderPipelineAsset.packagePath);
            EditorUtility.SetDirty(rendererData);
            AssetDatabase.SaveAssets();

            // ⚠️ ReloadAllNullIn 的返回值是「**有没有东西被重载**」，不是「是否还有空引用」
            //（源码注释：True if something have been reloaded）。第二次跑必然返回 false，
            // 拿它当完整性判据会造成**永久误报** —— 所以完整性要查具体字段。
            var shaders = rendererData.shaders;
            bool shaderReady = shaders != null && shaders.blitPS != null && shaders.copyDepthPS != null
                               && shaders.samplingPS != null && shaders.fallbackErrorPS != null;
            log.AppendLine(string.Format(
                "renderer data 资源：本次重载={0}；shader 引用 {1}；后处理数据 {2}",
                reloaded,
                shaderReady ? "已就位" : "有缺失 —— 运行时可能黑屏",
                rendererData.postProcessData != null ? "已就位" : "为空（后处理不可用）"));
            if (!shaderReady)
                log.AppendLine("警告：renderer data 的 shader 引用不完整，别当成通过");

            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if (pipeline == null)
            {
                pipeline = UniversalRenderPipelineAsset.Create(rendererData);
                AssetDatabase.CreateAsset(pipeline, PipelinePath);
                log.AppendLine("新建 URP 资产：" + PipelinePath);
            }
            else log.AppendLine("复用 URP 资产：" + PipelinePath);

            if (GraphicsSettings.defaultRenderPipeline != pipeline)
            {
                GraphicsSettings.defaultRenderPipeline = pipeline;
                log.AppendLine("已设为默认渲染管线（各质量档未单独指定时会继承它）");
            }
            else log.AppendLine("默认渲染管线已经是它了");

            AssetDatabase.SaveAssets();

            // --- 2. 按契约建材质 ---------------------------------------------
            var contract = LoadContract(log);
            if (contract == null) return log.ToString();

            if (contract.materials == null || contract.materials.Length == 0)
            {
                log.AppendLine("失败：契约里没有 materials 表。先重建资产（queen_mary.py 会写这张表）。");
                return log.ToString();
            }

            EnsureFolder(MaterialDir);
            int created = 0, updated = 0;
            foreach (var spec in contract.materials)
            {
                string path = MaterialDir + "/" + spec.name + ".mat";
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (mat == null)
                {
                    mat = new Material(shader);
                    AssetDatabase.CreateAsset(mat, path);
                    created++;
                }
                else
                {
                    if (mat.shader != shader) mat.shader = shader;
                    updated++;
                }
                var colour = new Color(spec.base_color[0], spec.base_color[1], spec.base_color[2], 1f);
                mat.SetColor("_BaseColor", colour);
                mat.SetFloat("_Smoothness", Mathf.Clamp01(1f - spec.roughness));
                mat.SetFloat("_Metallic", spec.metallic);
                EditorUtility.SetDirty(mat);
                log.AppendLine(string.Format("材质 {0}：灰度 {1:0.000}（线性），粗糙度 {2:0.00}",
                    spec.name, spec.base_color[0], spec.roughness));
            }
            AssetDatabase.SaveAssets();
            log.AppendLine(string.Format("材质新建 {0} 个、复用更新 {1} 个，位于 {2}", created, updated, MaterialDir));

            // --- 3. 重导模型，让材质贴上去 -------------------------------------
            string fbxPath = "Assets/Resources/Ships/" + ShipId + "/" + contract.FbxFileName();
            if (AssetDatabase.LoadAssetAtPath<GameObject>(fbxPath) == null)
            {
                log.AppendLine("失败：找不到模型 " + fbxPath);
                return log.ToString();
            }
            AssetDatabase.ImportAsset(fbxPath, ImportAssetOptions.ForceUpdate |
                                                ImportAssetOptions.ForceSynchronousImport);
            log.AppendLine("已重导模型，让材质重映射生效：" + fbxPath);

            return log.ToString();
        }

        private static ShipContractData LoadContract(StringBuilder log)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string full = Path.Combine(projectRoot, ContractPath);
            if (!File.Exists(full))
            {
                log.AppendLine("失败：找不到契约 " + ContractPath);
                return null;
            }
            try { return ShipContractData.Parse(File.ReadAllText(full, Encoding.UTF8), ContractPath); }
            catch (Exception e)
            {
                log.AppendLine("失败：契约解析错误 " + e.Message);
                return null;
            }
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            string leaf = Path.GetFileName(path);
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }
    }
}
