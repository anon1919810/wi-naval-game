using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T5 — Prototype gun battery: raycast shells from turret barrels, flood ShipCompartment.
    /// Not a ballistic simulation. QueryTriggerInteraction.Collide is required for hull/compartment triggers.
    /// </summary>
    [AddComponentMenu("Naval/Ship Gun Battery")]
    public sealed class ShipGunBattery : MonoBehaviour
    {
        public string shipId = "HMS_Queen_Mary_1913";
        public float shellRangeM = 8000f;
        public float floodVolumePerHitM3 = 180f;
        public float tracerWidth = 0.35f;
        public float tracerSeconds = 0.35f;
        public bool alsoHitMeshColliders = true;

        public string LastError { get; private set; }
        public string LastHitSummary { get; private set; }
        readonly List<LineRenderer> _tracers = new List<LineRenderer>();

        ShipContractData _contract;

        void Start()
        {
            try { _contract = ShipContractData.Load(shipId); } catch { _contract = null; }
        }

        /// <summary>Fire both barrels of a turret. Returns true if at least one ray was cast.</summary>
        public bool FireTurret(string key, Transform yawNode, Transform pitchNode)
        {
            if (pitchNode == null)
            {
                LastError = "pitch node null";
                return false;
            }

            var barrels = new List<Transform>();
            foreach (Transform child in pitchNode)
                if (child.name.StartsWith("Barrel_" + key + "_"))
                    barrels.Add(child);
            if (barrels.Count == 0 && yawNode != null)
            {
                foreach (Transform t in yawNode.GetComponentsInChildren<Transform>(true))
                    if (t.name.StartsWith("Barrel_" + key + "_"))
                        barrels.Add(t);
            }
            if (barrels.Count == 0)
            {
                LastError = "no barrels for " + key;
                return false;
            }

            int hits = 0;
            foreach (var barrel in barrels)
                if (FireBarrel(barrel)) hits++;
            LastError = hits == 0 ? "no hits" : "";
            return true;
        }

        public bool FireBarrel(Transform barrel)
        {
            if (barrel == null) return false;

            // Barrel local +Y is muzzle direction in asset space; after Unity import the mesh
            // still has origin at trunnion and muzzle along local +Y of the barrel object.
            Vector3 origin = barrel.position;
            Vector3 dir = barrel.up;
            if (dir.sqrMagnitude < 1e-6f) dir = barrel.forward;

            var hits = Physics.RaycastAll(origin, dir, shellRangeM,
                ~0, QueryTriggerInteraction.Collide);
            System.Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));

            RaycastHit best = default;
            bool found = false;
            foreach (var h in hits)
            {
                if (h.transform.IsChildOf(transform) || h.transform == transform)
                {
                    // Ignore self-hit on own hull/trigger when muzzle starts inside proxy.
                    if (h.distance < 25f) continue;
                }
                best = h;
                found = true;
                break;
            }

            Vector3 end = found ? best.point : origin + dir * shellRangeM;
            SpawnTracer(origin, end);

            if (!found)
            {
                LastHitSummary = "miss";
                return false;
            }

            var compartment = best.collider.GetComponentInParent<ShipCompartment>();
            string targetName = best.collider.name;
            if (compartment != null)
            {
                compartment.Flood(floodVolumePerHitM3);
                LastHitSummary = compartment.compartmentId + " role=" + compartment.role +
                                 " flood=" + compartment.FloodedVolumeM3.ToString("0.0") +
                                 " m3 frac=" + compartment.floodFraction.ToString("0.00");
                var floater = best.collider.GetComponentInParent<ShipFloatPrototype>();
                if (floater != null) floater.RebuildFromCompartments();
                return true;
            }

            // Mesh hull / armour / proxy hit — counts as struck but no compartment data.
            LastHitSummary = "struck " + targetName + " (no ShipCompartment)";
            var anyFloat = best.collider.GetComponentInParent<ShipFloatPrototype>();
            if (anyFloat != null) anyFloat.RegisterSurfaceHit(best.point);
            return true;
        }

        void SpawnTracer(Vector3 a, Vector3 b)
        {
            var go = new GameObject("Tracer");
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = 2;
            lr.SetPosition(0, a);
            lr.SetPosition(1, b);
            lr.startWidth = tracerWidth;
            lr.endWidth = tracerWidth * 0.4f;
            lr.material = new Material(Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Sprites/Default"));
            lr.startColor = new Color(1f, 0.85f, 0.3f, 0.9f);
            lr.endColor = new Color(1f, 0.4f, 0.1f, 0.2f);
            _tracers.Add(lr);
            Destroy(go, tracerSeconds);
        }
    }
}
