using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// A03 — Ordered hit path + layered armour budget (mm). Pure of presentation.
    /// </summary>
    public static class ShipHitResolver
    {
        public class LayerHit
        {
            public string layerId;
            public string objectId;
            public float armourMm;
            public float enterDist;
            public float exitDist;
            public ShipCompartment compartment;
        }

        public class PathResult
        {
            public ShipCompartment damagedModule;
            public float budgetBeforeMm;
            public float budgetAfterMm;
            public string stopReason;
            public List<LayerHit> layers = new List<LayerHit>();
        }

        /// <summary>
        /// Consume ordered layers; each physical layerId costs armour once.
        /// Stop on insufficient budget or first damaged compartment (A-stage rule).
        /// </summary>
        public static PathResult ResolveBudget(List<LayerHit> ordered, float penetrationMm,
                                              float incidenceCos, HashSet<string> visitedLayers = null)
        {
            var result = new PathResult { budgetBeforeMm = penetrationMm };
            float budget = penetrationMm;
            if (visitedLayers == null) visitedLayers = new HashSet<string>();
            if (ordered == null || ordered.Count == 0)
            {
                result.budgetAfterMm = budget;
                result.stopReason = "no_layers";
                return result;
            }

            foreach (var layer in ordered)
            {
                if (layer == null) continue;
                result.layers.Add(layer);
                float eff = ShipPenetration.EffectiveArmourMm(layer.armourMm, incidenceCos);
                bool isModule = layer.compartment != null;
                if (!isModule && !string.IsNullOrEmpty(layer.layerId) && visitedLayers.Contains(layer.layerId))
                    continue;

                if (eff > budget)
                {
                    result.budgetAfterMm = 0f;
                    result.stopReason = "blocked_at_" + (layer.layerId ?? layer.objectId);
                    return result;
                }

                if (!isModule)
                {
                    visitedLayers.Add(layer.layerId);
                    budget -= eff;
                    result.budgetAfterMm = budget;
                    continue;
                }

                // Module: A-stage stops at first reachable damaged module.
                result.damagedModule = layer.compartment;
                result.budgetAfterMm = budget - eff;
                result.stopReason = "module_" + (layer.compartment.compartmentId ?? layer.objectId);
                return result;
            }

            result.budgetAfterMm = budget;
            result.stopReason = "path_clear_no_module";
            return result;
        }

        /// <summary>OBB slab interval in local space for a BoxCollider path.</summary>
        public static bool BoxIntervalLocal(BoxCollider box, Vector3 originLocal, Vector3 dirLocal,
                                            out float tEnter, out float tExit)
        {
            tEnter = tExit = 0f;
            if (box == null || dirLocal.sqrMagnitude < 1e-12f) return false;
            Vector3 c = box.center;
            Vector3 e = box.size * 0.5f;
            Vector3 o = originLocal - c;
            tEnter = float.NegativeInfinity;
            tExit = float.PositiveInfinity;
            for (int i = 0; i < 3; i++)
            {
                float o1 = i == 0 ? o.x : i == 1 ? o.y : o.z;
                float d1 = i == 0 ? dirLocal.x : i == 1 ? dirLocal.y : dirLocal.z;
                float ext = i == 0 ? e.x : i == 1 ? e.y : e.z;
                if (Mathf.Abs(d1) < 1e-8f)
                {
                    if (Mathf.Abs(o1) > ext) return false;
                    continue;
                }
                float t0 = (-ext - o1) / d1;
                float t1 = (ext - o1) / d1;
                if (t0 > t1) { var tmp = t0; t0 = t1; t1 = tmp; }
                tEnter = Mathf.Max(tEnter, t0);
                tExit = Mathf.Min(tExit, t1);
                if (tEnter > tExit) return false;
            }
            return tExit >= 0f;
        }
    }
}
