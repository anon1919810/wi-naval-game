using UnityEditor;
using System.IO;
using System.Collections.Generic;
using UnityEngine.Rendering;

namespace Naval.EditorTools
{
    public static class ShipDeliveryChecks
    {
        public static void RunBatch()
        {
            bool valid = ShipAssetValidator.ValidateForPipeline();
            bool rendered = ShipPreviewRender.RenderForPipeline();
            if (valid && rendered) ExportRuntime();
            EditorApplication.Exit(valid && rendered ? 0 : 1);
        }

        public static void ExportBatch()
        {
            ExportRuntime();
            EditorApplication.Exit(0);
        }

        private static void ExportRuntime()
        {
            Directory.CreateDirectory(ShipRuntimeAcceptance.OutputDirectory);
            string folder = "Assets/Resources/Ships/" + ShipRuntimeBuilder.ShipId;
            var paths = new List<string> {
                ShipRuntimeBuilder.PrefabPath,
                folder + "/" + ShipRuntimeBuilder.ShipId + "_Definition.asset",
                folder + "/ship_contract.json", folder + "/ship_contract.unity.json",
                AssetDatabase.GetAssetPath(GraphicsSettings.currentRenderPipeline)
            };
            foreach (var reference in ShipContractData.Load(ShipRuntimeBuilder.ShipId).file_refs)
                paths.Add(folder + "/" + reference.path);
            const string scene = "Assets/Scenes/QueenMaryFleetBenchmark.unity";
            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(scene) != null) paths.Add(scene);
            AssetDatabase.ExportPackage(paths.ToArray(), Path.Combine(ShipRuntimeAcceptance.OutputDirectory, "QueenMary_Runtime_URP.unitypackage"),
                ExportPackageOptions.IncludeDependencies | ExportPackageOptions.Recurse);
        }
    }
}
