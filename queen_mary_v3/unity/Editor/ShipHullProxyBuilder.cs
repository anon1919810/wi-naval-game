using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Naval.EditorTools
{
    /// <summary>A coarse hull envelope for selection and broad-phase hit queries, derived from Hull geometry.</summary>
    public static class ShipHullProxyBuilder
    {
        public const string MeshPath = "Assets/Meshes/Ships/HMS_Queen_Mary_1913_HullProxy.asset";

        public static void Build(GameObject ship)
        {
            var hull = ship.GetComponentsInChildren<MeshFilter>().First(f => f.name == "Hull");
            var source = hull.sharedMesh;
            var matrix = ship.transform.worldToLocalMatrix * hull.transform.localToWorldMatrix;
            var vertices = source.vertices.Select(v => matrix.MultiplyPoint3x4(v)).ToArray();
            var triangles = source.triangles;
            float min = vertices.Min(v => v.z), max = vertices.Max(v => v.z);
            var points = new List<Vector3>();
            const int rings = 13, sides = 8;
            for (int ring = 0; ring < rings; ring++)
            {
                // Avoid the exact tip's zero-area section. Length loss is only 6 cm over 213.4 m.
                float z = Mathf.Lerp(min + .03f, max - .03f, (float)ring / (rings - 1));
                var section = new List<Vector3>();
                for (int i = 0; i < triangles.Length; i += 3)
                    for (int edge = 0; edge < 3; edge++)
                    {
                        var a = vertices[triangles[i + edge]];
                        var b = vertices[triangles[i + (edge + 1) % 3]];
                        if ((a.z - z) * (b.z - z) > 0 || Mathf.Abs(a.z - b.z) < .00001f) continue;
                        section.Add(Vector3.Lerp(a, b, (z - a.z) / (b.z - a.z)));
                    }
                if (section.Count == 0) throw new InvalidOperationException("Hull has no section at " + z);
                for (int side = 0; side < sides; side++)
                {
                    float angle = side * Mathf.PI * 2 / sides;
                    var direction = new Vector3(Mathf.Cos(angle), Mathf.Sin(angle), 0);
                    float support = section.Max(p => Vector3.Dot(p, direction));
                    var candidates = section.Where(p => Vector3.Dot(p, direction) >= support - .0001f).ToArray();
                    var sum = Vector3.zero;
                    foreach (var p in candidates) sum += p;
                    points.Add(sum / candidates.Length);
                }
            }
            var indices = new List<int>();
            for (int ring = 0; ring + 1 < rings; ring++)
                for (int side = 0; side < sides; side++)
                {
                    int a = ring * sides + side, b = ring * sides + (side + 1) % sides;
                    indices.AddRange(new[] { a, b, b + sides, a, b + sides, a + sides });
                }
            for (int side = 1; side + 1 < sides; side++)
            {
                indices.AddRange(new[] { 0, side + 1, side });
                int last = (rings - 1) * sides;
                indices.AddRange(new[] { last, last + side, last + side + 1 });
            }
            var mesh = new Mesh { name = "Hull_Collision_Proxy" };
            mesh.SetVertices(points);
            mesh.SetTriangles(indices, 0);
            mesh.RecalculateBounds();
            mesh.RecalculateNormals();
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(MeshPath);
            if (existing != null)
            {
                EditorUtility.CopySerialized(mesh, existing);
                UnityEngine.Object.DestroyImmediate(mesh);
                mesh = existing;
                EditorUtility.SetDirty(mesh);
            }
            else AssetDatabase.CreateAsset(mesh, MeshPath);
            var proxy = new GameObject("Hull_Collision_Proxy");
            proxy.transform.SetParent(ship.transform, false);
            var collider = proxy.AddComponent<MeshCollider>();
            collider.sharedMesh = mesh;
            collider.convex = true;
            collider.isTrigger = true;
        }
    }
}
