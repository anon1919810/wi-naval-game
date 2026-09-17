using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// 把舰船 FBX 上的材质槽换成 URP 材质。
    ///
    /// 为什么需要这一步：Blender 导出的 FBX 里材质是内嵌的、走 Built-in 的 Standard shader，
    /// 在 URP 下**整艘船会渲染成品红**（shader 找不到的默认表现）。而且这个是静默的 ——
    /// 场景里船在、三角形也在，只是颜色全错，不看画面就发现不了。
    ///
    /// 做法：按名字把材质槽指到 `Assets/Materials/Naval/<名字>.mat`。
    /// 材质由 UrpSetup 按**契约里的 materials 表**创建，所以灰度值只有 Blender 一个来源。
    /// 材质资产必须先存在，本回调才认得出来 —— 所以 UrpSetup 在建完材质后会重导模型。
    ///
    /// 找不到对应材质时返回 null（保留默认），并打一条警告把缺失的名字列出来：
    /// 宁可吵，也不要静默出品红。验证器还有一条"所有 renderer 的 shader 必须是 URP"兜底。
    /// </summary>
    public sealed class ShipMaterialRemap : AssetPostprocessor
    {
        private const string ShipModelDir = "/resources/ships/";
        private const string MaterialDir = "Assets/Materials/Naval";

        private static readonly List<string> Reported = new List<string>();

        private void OnPreprocessModel()
        {
            if (!IsShipModel()) return;

            var importer = assetImporter as ModelImporter;
            if (importer == null) return;

            // ImportStandard 保留材质槽名（HullGrey / DeckGrey …），这是按名重映射的前提。
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        }

        /// <summary>返回 URP 材质替换掉导入的 Standard 材质；返回 null 则保留默认。</summary>
        private Material OnAssignMaterialModel(Material material, Renderer renderer)
        {
            if (!IsShipModel() || material == null) return null;

            string path = MaterialDir + "/" + material.name + ".mat";
            var replacement = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (replacement != null)
            {
                Reported.Remove(material.name);
                return replacement;
            }

            if (!Reported.Contains(material.name))
            {
                Reported.Add(material.name);
                Debug.LogWarning("[Naval] FBX 里的材质 " + material.name + " 没有对应的 URP 材质（" +
                                 path + "）。它会用内置 Shader 渲染 —— 在 URP 下就是品红。" +
                                 "跑一次 Tools > Naval > Set up URP 即可建出来。");
            }
            return null;
        }

        private bool IsShipModel()
        {
            return assetPath.Replace('\\', '/').ToLowerInvariant()
                .IndexOf(ShipModelDir, StringComparison.Ordinal) >= 0;
        }
    }
}
