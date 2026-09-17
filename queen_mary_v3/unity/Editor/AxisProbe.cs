using System;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>
    /// 读出探针 FBX 里那几个**不对称**标记件落在 Unity 的哪个位置，从而定出
    /// Blender → Unity 的轴映射（含左右是否被镜像）。
    ///
    /// 为什么需要它：船体左右对称，**任何对船本身的检查都判不出左右舷**；
    /// 而导出开关的名字也不可靠——实测里 axis_forward 改了之后舰艏照样在 −Z。
    /// 所以让标记件说话：Blender 里 MARK_STARBOARD 在 +X，导入后它的 x 正负
    /// 就决定了右舷在 Unity 的哪一侧。
    ///
    /// 配套：queen_mary/probe_axis_convention.py（Blender 侧生成探针 FBX）
    /// 用法：菜单 Tools/Naval/Probe axis convention
    ///      批处理 -executeMethod Naval.EditorTools.AxisProbe.ProbeBatch
    /// </summary>
    public static class AxisProbe
    {
        // 探针模型的文件名刻意用 AxisProbeModel：静态预检会把"类名 + 点 + 扩展名"这种
        // 字符串误判成"引用了未声明成员"，留一条噪音会让预检失去门禁作用。
        private const string ProbeFbx = "Assets/_AxisProbe/AxisProbeModel.fbx";

        private const string BlenderReference =
            @"C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3\_axis_probe_blender.json";

        private const string OutputPath =
            @"C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3\_axis_probe_unity.txt";

        [MenuItem("Tools/Naval/Probe axis convention")]
        public static void ProbeMenu() { Report(Probe()); }

        public static void ProbeBatch()
        {
            var text = Probe();
            if (Application.isBatchMode) EditorApplication.Exit(string.IsNullOrEmpty(text) ? 1 : 0);
        }

        private static string Probe()
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(ProbeFbx);
            if (asset == null)
            {
                Debug.LogError("[Naval] 找不到探针模型 " + ProbeFbx +
                               "，先跑 queen_mary_v3/probe_axis_convention.py --out <工程>/Assets/_AxisProbe");
                return null;
            }

            var lines = new StringBuilder();
            lines.AppendLine("unity=" + Application.unityVersion);
            lines.AppendLine("probe=" + ProbeFbx);

            var instance = UnityEngine.Object.Instantiate(asset);
            try
            {
                foreach (var t in instance.GetComponentsInChildren<Transform>(true))
                {
                    Vector3 p = t.position;
                    lines.AppendLine(string.Format("{0} x={1:0.000} y={2:0.000} z={3:0.000}",
                        t.name, p.x, p.y, p.z));
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(instance); }

            if (File.Exists(BlenderReference))
            {
                lines.AppendLine("--- Blender reference (" + BlenderReference + ") ---");
                lines.AppendLine(File.ReadAllText(BlenderReference, Encoding.UTF8));
            }
            else
            {
                lines.AppendLine("Blender reference file missing: " + BlenderReference);
            }

            try { File.WriteAllText(OutputPath, lines.ToString(), new UTF8Encoding(false)); }
            catch (Exception e) { Debug.LogError("[Naval] 探针结果写入失败：" + e.Message); }

            return lines.ToString();
        }

        private static void Report(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
            Debug.Log("[Naval] 轴映射探针结果：\n" + text);
            EditorUtility.DisplayDialog("轴映射探针", text, "好");
        }
    }
}
