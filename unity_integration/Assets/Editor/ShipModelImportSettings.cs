using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// 舰船 FBX 的导入设置由脚本统一钉死 —— 手点一定会漏，漏了就是运行时静默失效。
    ///
    /// 逐条理由：
    ///  - isReadable = true      ：运行时要在 mesh 上做查询（简化碰撞代理、射界 BVH、命中点定位）。
    ///                             Unity 默认对模型关闭 Read/Write 省内存，不开就抛异常。
    ///  - weldVertices = false   ：我们的硬边是靠**不共享顶点**做出来的（Blender 侧 FACET 平滑）。
    ///                             焊接会把硬边焊平，模型外观被改，而 Blender 端验证发现不了。
    ///  - optimizeMesh* = false  ：顶点顺序必须可预测，否则"同一次导出两次导入顶点数不同"，
    ///                             我们的 sha256 基线与对象计数就失去意义。
    ///  - meshCompression = Off  ：压缩会改顶点数据（量化），同样破坏可复现性。
    ///  - materialImportMode = ImportStandard：保留材质槽名（HullGrey / DeckGrey / DarkGrey …），
    ///                             供后续按名字替换管线材质，而不是靠下标猜。
    ///  - importAnimation/Cameras/Lights/BlendShapes = false：这份资产里没有这些，导入它们只会
    ///                             增加节点、改变对象计数。
    ///  - globalScale = 1 且 useFileScale = false：米就是米，不许出现 0.01 或 100 倍的静默缩放。
    ///
    /// **刻意不设置**：bakeAxisConversion。它会改变根节点旋转 → 轴向约定的实测值全部失效。
    /// 轴向由 ShipAssetValidator 按"结果"断言（舰艏是否 +Z、向上是否 +Y），而不是靠设置开关。
    /// </summary>
    public sealed class ShipModelImportSettings : AssetPostprocessor
    {
        private const string ShipModelDir = "/resources/ships/";

        private void OnPreprocessModel()
        {
            string path = assetPath.Replace('\\', '/').ToLowerInvariant();
            if (path.IndexOf(ShipModelDir, System.StringComparison.Ordinal) < 0) return;

            var importer = assetImporter as ModelImporter;
            if (importer == null) return;

            importer.isReadable = true;
            importer.weldVertices = false;
            importer.optimizeMeshVertices = false;
            importer.optimizeMeshPolygons = false;
            importer.meshCompression = ModelImporterMeshCompression.Off;

            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.importNormals = ModelImporterNormals.Import;
            importer.importTangents = ModelImporterTangents.None;
            importer.importAnimation = false;
            importer.animationType = ModelImporterAnimationType.None;
            importer.importCameras = false;
            importer.importLights = false;
            importer.importBlendShapes = false;
            importer.importVisibility = false;
            importer.addCollider = false;      // 碰撞体由脚本按损伤模块单独生成，不用自动凸包

            importer.globalScale = 1.0f;
            importer.useFileScale = false;

            importer.preserveHierarchy = true; // 层级即契约：枢轴父子链必须原样保留
            importer.keepQuads = false;
            importer.generateSecondaryUV = false;
        }
    }
}
