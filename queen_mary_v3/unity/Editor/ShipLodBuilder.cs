using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Naval.EditorTools
{
    /// <summary>
    /// 给船体静态本体生成 LOD 链（把几十个网格按材质合并成 1 个渲染器）。
    ///
    /// 两条硬约束：
    ///  ① **炮塔链保留独立变换，列入 LOD0/1/2**（Turret → Elevation → Barrel，16 个对象）。
    ///     它们要转，一旦被合进 LOD 的静态网格就永远转不了了。
    ///     LODGroup 管理全部可见渲染器，炮塔层级不变。
    ///  ② **按材质合并**，不是按对象。合并后子网格数 = 材质数（本船 6），
    ///     所以是"1 个渲染器 + 6 个子网格 ≈ 6 次 draw call"，而不是 49 个子网格。
    ///     如果按对象合，子网格数就等于对象数，等于白做。
    ///
    /// 档位设计：
    ///   LOD0  原样（全细节）
    ///   LOD1  静态本体合并成 1 个渲染器 —— **三角形数不变**，省的是渲染器/剔除开销
    ///   LOD2  同上，但剔除小件（索具、网、甲板小配件、炮廓凹口…）—— 三角形数显著下降
    ///   LOD3  全部合并成一个扁平材质剪影 —— 炮塔在此档是**冻结**的（那个距离只有几个像素）。
    ///         实现方式：炮塔渲染器同时列进 LOD0/1/2 档，只在 LOD3 档缺席，LODGroup 才关得掉它们。
    /// </summary>
    public static class ShipLodBuilder
    {
        private const string MeshDir = "Assets/Meshes/Ships";

        /// <summary>各档的屏幕高度阈值（占屏幕高度比例）。**要对着真实相机调**，这里只是默认值。</summary>
        private static readonly float[] ScreenHeights = { 0.20f, 0.08f, 0.03f, 0.01f };

        /// <summary>LOD2 起可以丢掉的"小件"角色：远看只有几个像素，却是可观的对象数。</summary>
        private static readonly string[] DroppableRoles =
        {
            "rigging", "stowed_net", "stowed_net_mesh",
            "deck_detail", "deck_fitting",
            "casemate_opening", "sternwalk_rail", "fx_anchor",
        };

        public sealed class Result
        {
            public readonly List<string> Summary = new List<string>();
            public readonly List<string> Failures = new List<string>();
            public readonly List<string> Notes = new List<string>();
            public int Lod0Renderers;
            public int Lod1Renderers;
        }

        /// <summary>在 root 下挂 LODGroup 并生成合并网格。root 是实例化出来的船（尚未存成预制体）。</summary>
        public static Result Build(GameObject root, ShipContractData contract,
                                   Dictionary<string, string> roleByName)
        {
            var result = new Result();
            if (root == null || contract == null)
            {
                result.Failures.Add("LOD：root 或契约为空");
                return result;
            }

            // 炮塔链的名字：这些不能合入静态本体
            var turretChain = new HashSet<string>();
            foreach (var t in contract.turrets)
            {
                turretChain.Add(t.turret);
                turretChain.Add(t.pivot);
                turretChain.Add(t.barbette);
                foreach (var b in t.barrels) turretChain.Add(b);
            }

            // 收集静态可见网格：渲染开着、不在炮塔链里
            var staticRenderers = new List<MeshRenderer>();
            var turretRenderers = new List<MeshRenderer>();
            foreach (var mr in root.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (mr.transform == root.transform) continue;
                if (!mr.enabled) continue;                       // 仅碰撞件已经关了渲染，不参与
                if (turretChain.Contains(mr.name)) turretRenderers.Add(mr);
                else staticRenderers.Add(mr);
            }

            if (staticRenderers.Count == 0)
            {
                result.Failures.Add("LOD：一个静态可见网格都没找到");
                return result;
            }
            result.Lod0Renderers = staticRenderers.Count + turretRenderers.Count;

            Matrix4x4 rootInverse = root.transform.worldToLocalMatrix;

            // --- LOD1：静态本体全细节合并（按材质）-----------------------------
            Material[] materials;
            Mesh lod1 = MergeByMaterial(staticRenderers, rootInverse, null, out materials);
            if (lod1 == null || materials.Length == 0)
            {
                result.Failures.Add("LOD1：合并失败（没有可用网格）");
                return result;
            }

            // --- LOD2：剔除小件 -------------------------------------------------
            var droppable = new HashSet<string>();
            foreach (var mr in staticRenderers)
            {
                string role;
                if (roleByName.TryGetValue(mr.name, out role) && Array.IndexOf(DroppableRoles, role) >= 0)
                    droppable.Add(mr.name);
            }
            Material[] materials2;
            Mesh lod2 = MergeByMaterial(staticRenderers, rootInverse, droppable, out materials2);

            // --- LOD3：连炮塔一起合并的扁平剪影 ---------------------------------
            var allRenderers = new List<MeshRenderer>(staticRenderers);
            allRenderers.AddRange(turretRenderers);
            var silhouetteSkip = new HashSet<string>(droppable);
            foreach (var mr in staticRenderers)
                if (roleByName.TryGetValue(mr.name, out var role) &&
                    (role == "secondary_gun" || role == "boat" || role == "ventilator"))
                    silhouetteSkip.Add(mr.name);
            Material[] materials3;
            Mesh silhouette = MergeByMaterial(allRenderers, rootInverse, silhouetteSkip, out materials3);
            Material flat = materials3.Length > 0 ? materials3[0] : null;
            if (silhouette != null && flat != null)
            {
                // Every material submesh contributes geometry to the one-material silhouette.
                var parts = new CombineInstance[silhouette.subMeshCount];
                for (int s = 0; s < parts.Length; s++)
                    parts[s] = new CombineInstance { mesh = silhouette, subMeshIndex = s, transform = Matrix4x4.identity };
                var flatMesh = new Mesh { indexFormat = IndexFormat.UInt32, name = "silhouette" };
                flatMesh.CombineMeshes(parts, true, true);
                UnityEngine.Object.DestroyImmediate(silhouette);
                silhouette = flatMesh;
            }

            // --- 存成网格资产并挂到 root 下 --------------------------------------
            EnsureFolder(MeshDir);
            var lod1Go = AttachMesh(root, "_LOD1_Body", lod1, materials, SaveMesh(lod1, "_LOD1_Body"));
            GameObject lod2Go = null;
            if (lod2 != null) lod2Go = AttachMesh(root, "_LOD2_Body", lod2, materials2, SaveMesh(lod2, "_LOD2_Body"));
            GameObject lod3Go = null;
            if (silhouette != null && flat != null)
                lod3Go = AttachMesh(root, "_LOD3_Silhouette", silhouette, new[] { flat },
                                    SaveMesh(silhouette, "_LOD3_Silhouette"));

            // --- LODGroup -------------------------------------------------------
            var group = root.GetComponent<LODGroup>();
            if (group == null) group = root.AddComponent<LODGroup>();

            // 炮塔渲染器也必须**列进 LOD0/1/2 档**：LODGroup 只会开关"列在档里"的渲染器，
            // 不列就永远碰不到它们。而 LOD3 的剪影里已经含一份炮塔几何 —— 于是远档会变成
            // 「剪影里的冻结炮塔 + 真实炮塔仍在画」= 重复绘制 + 共面 z-fighting。
            // 列进来之后，LOD3 才真的关得掉它们，注释里那句"炮塔在此档冻结"才成立。
            var turretAsRenderers = new List<Renderer>();
            foreach (var mr in turretRenderers) turretAsRenderers.Add(mr);

            var levels = new List<LOD>();
            var lod0Renderers = new List<Renderer>(turretAsRenderers);
            foreach (var mr in staticRenderers) lod0Renderers.Add(mr);
            levels.Add(new LOD(ScreenHeights[0], lod0Renderers.ToArray()));

            var lod1Renderers = new List<Renderer>(turretAsRenderers);
            lod1Renderers.Add(lod1Go.GetComponent<MeshRenderer>());
            levels.Add(new LOD(ScreenHeights[1], lod1Renderers.ToArray()));

            if (lod2Go != null)
            {
                var lod2Renderers = new List<Renderer>(turretAsRenderers);
                lod2Renderers.Add(lod2Go.GetComponent<MeshRenderer>());
                levels.Add(new LOD(ScreenHeights[2], lod2Renderers.ToArray()));
            }
            if (lod3Go != null)
                levels.Add(new LOD(ScreenHeights[3], new Renderer[] { lod3Go.GetComponent<MeshRenderer>() }));
            group.SetLODs(levels.ToArray());
            group.RecalculateBounds();

            // 不变量：凡是被合进某个 LOD 网格的渲染器，必须至少出现在一个 LOD 档里。
            // 违反 = 原件在所有距离上都会和合并网格一起画（重复绘制 + z-fighting）。
            // 这类错误不抛异常、不报编译错，只在中远距的画面上现形 —— 所以要在这里拦住。
            var inAnyLevel = new HashSet<Renderer>();
            foreach (var lvl in levels)
                foreach (var r in lvl.renderers) inAnyLevel.Add(r);

            var notListed = new List<string>();
            foreach (var mr in staticRenderers)
                if (!inAnyLevel.Contains(mr)) notListed.Add(mr.name);
            if (lod3Go != null)
                foreach (var mr in turretRenderers)
                    if (!inAnyLevel.Contains(mr)) notListed.Add(mr.name);
            if (notListed.Count > 0)
                result.Failures.Add("LOD：" + string.Join("、", notListed) +
                                    " 的几何已被合进 LOD 网格，却没有出现在任何 LOD 档里 ——" +
                                    "远档会和合并网格重复绘制");

            // --- 统计与断言 -----------------------------------------------------
            int tri1 = TriangleCount(lod1);
            int tri2 = lod2 != null ? TriangleCount(lod2) : tri1;
            int tri3 = silhouette != null ? TriangleCount(silhouette) : tri2;
            int tri0 = 0;
            foreach (var mr in staticRenderers)
            {
                var mf = mr.GetComponent<MeshFilter>();
                if (mf != null && mf.sharedMesh != null) tri0 += mf.sharedMesh.triangles.Length / 3;
            }
            foreach (var mr in turretRenderers)
            {
                var mf = mr.GetComponent<MeshFilter>();
                if (mf != null && mf.sharedMesh != null) tri0 += mf.sharedMesh.triangles.Length / 3;
            }

            result.Lod1Renderers = 1 + turretRenderers.Count;
            result.Summary.Add(string.Format("LOD0  原样：{0} 个渲染器（{1} 静态 + {2} 炮塔链）/ {3} 三角形",
                result.Lod0Renderers, staticRenderers.Count, turretRenderers.Count, tri0));
            result.Summary.Add(string.Format("LOD1  静态本体按材质合并：{0} 渲染器 · 本体 {1} 子网格 · {2} 三角形（屏幕高度比例 {3}）",
                1 + turretRenderers.Count, materials.Length, tri1 + TurretTriangles(turretRenderers), ScreenHeights[1]));
            result.Summary.Add(string.Format("LOD2  再丢小件：{0} 渲染器 · 本体 {1} 子网格 · {2} 三角形",
                1 + turretRenderers.Count, materials2.Length, tri2 + TurretTriangles(turretRenderers)));
            result.Summary.Add(string.Format("LOD3  扁平剪影（炮塔冻结）：1 渲染器 · 1 子网格 · {0} 三角形（本档关掉 {1} 个炮塔渲染器）",
                tri3, turretRenderers.Count));

            result.Notes.Add("炮塔链（" + turretRenderers.Count + " 个渲染器）保留独立变换并列入 LOD0/1/2 —— " +
                             "它们要转，合进静态网格就废了。所以 LOD1/2 的渲染器下限就是它。");
            result.Notes.Add("屏幕高度阈值 " + string.Join(" / ", Array.ConvertAll(ScreenHeights, h => h.ToString("0.00"))) +
                             " 是默认值，**要对着真实相机调**。");

            if (lod2 != null && tri2 >= tri1)
                result.Failures.Add("LOD2 的三角形数没有比 LOD1 少 —— 小件剔除没生效（角色名对不上？）");
            if (tri3 >= tri2 + TurretTriangles(turretRenderers))
                result.Failures.Add("LOD3 的三角形数没有比 LOD2 少，剪影档没意义");

            return result;
        }

        // -------------------------------------------------------------- helpers

        private static int TurretTriangles(List<MeshRenderer> turretRenderers)
        {
            int total = 0;
            foreach (var mr in turretRenderers)
            {
                var mf = mr.GetComponent<MeshFilter>();
                if (mf != null && mf.sharedMesh != null) total += mf.sharedMesh.triangles.Length / 3;
            }
            return total;
        }

        private static int TriangleCount(Mesh mesh)
        {
            return mesh != null ? mesh.triangles.Length / 3 : 0;
        }

        /// <summary>
        /// 按**材质**分组合并：每种材质先各自合成一份，再拼成一个带 N 个子网格的网格。
        /// 于是渲染器只有 1 个、子网格数 = 材质数（本船 6），而不是几十个子网格。
        /// </summary>
        private static Mesh MergeByMaterial(List<MeshRenderer> renderers, Matrix4x4 rootInverse,
                                            HashSet<string> skip, out Material[] materials)
        {
            var byMaterial = new Dictionary<Material, List<CombineInstance>>();
            var order = new List<Material>();

            foreach (var mr in renderers)
            {
                if (skip != null && skip.Contains(mr.name)) continue;
                var mf = mr.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                Mesh mesh = mf.sharedMesh;
                Material[] mats = mr.sharedMaterials;
                if (mats == null || mats.Length == 0) continue;
                int subMeshes = Mathf.Min(mesh.subMeshCount, mats.Length);
                Matrix4x4 transform = rootInverse * mr.transform.localToWorldMatrix;

                for (int s = 0; s < subMeshes; s++)
                {
                    Material mat = mats[s];
                    if (mat == null) continue;
                    List<CombineInstance> list;
                    if (!byMaterial.TryGetValue(mat, out list))
                    {
                        list = new List<CombineInstance>();
                        byMaterial[mat] = list;
                        order.Add(mat);
                    }
                    list.Add(new CombineInstance { mesh = mesh, subMeshIndex = s, transform = transform });
                }
            }

            if (order.Count == 0) { materials = new Material[0]; return null; }

            var perMaterial = new List<Mesh>();
            foreach (var mat in order)
            {
                var partial = new Mesh();
                partial.CombineMeshes(byMaterial[mat].ToArray(), true, true);
                perMaterial.Add(partial);
            }

            var merged = new Mesh { indexFormat = IndexFormat.UInt32 };
            var final = new CombineInstance[perMaterial.Count];
            for (int i = 0; i < perMaterial.Count; i++)
                final[i] = new CombineInstance { mesh = perMaterial[i], subMeshIndex = 0, transform = Matrix4x4.identity };
            merged.CombineMeshes(final, false, true);
            merged.RecalculateBounds();
            merged.name = "merged_body";

            foreach (var m in perMaterial) UnityEngine.Object.DestroyImmediate(m);
            materials = order.ToArray();
            return merged;
        }

        private static GameObject AttachMesh(GameObject root, string name, Mesh mesh,
                                             Material[] materials, Mesh savedMesh)
        {
            var go = new GameObject(name);
            go.transform.SetParent(root.transform, false);
            var filter = go.AddComponent<MeshFilter>();
            filter.sharedMesh = savedMesh != null ? savedMesh : mesh;
            var renderer = go.AddComponent<MeshRenderer>();
            renderer.sharedMaterials = materials;

            // 远处的船不需要往场景里投阴影：省一整个 shadow pass
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            renderer.enabled = true;    // LODGroup culls levels; it does not enable disabled renderers.
            return go;
        }

        /// <summary>把合并网格存成资产（预制体引用不到内存里的网格）。</summary>
        private static Mesh SaveMesh(Mesh mesh, string suffix)
        {
            string path = MeshDir + "/HMS_Queen_Mary_1913" + suffix + ".asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing != null)
            {
                // Preserve GUIDs and references on repeat builds; let save errors fail the build.
                EditorUtility.CopySerialized(mesh, existing);
                EditorUtility.SetDirty(existing);
                return existing;
            }
            AssetDatabase.CreateAsset(mesh, path);
            return mesh;
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
