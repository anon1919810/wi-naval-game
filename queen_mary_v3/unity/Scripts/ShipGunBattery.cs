using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T5/T9 — Gun battery: raycast shells, evaluate penetration vs armour zones,
    /// flood compartments and update ShipSystemsState. Not a ballistic simulation.
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
        [Tooltip("When true, flood volume and systems come from penetration tables.")]
        public bool usePenetration = true;

        public string LastError { get; private set; }
        public string LastHitSummary { get; private set; }
        public ShipPenHit LastPenHit { get; private set; }

        readonly List<LineRenderer> _tracers = new List<LineRenderer>();

        ShipContractData _contract;
        ShipPenetrationFile _pen;
        ShipArmourZonesFile _zones;
        ShipSystemsState _systems;
        string _lastGunId = "main_343mm";

        void Start()
        {
            try { _contract = ShipContractData.Load(shipId); } catch { _contract = null; }
            _pen = ShipPenetrationFile.Load(shipId);
            _zones = ShipArmourZonesFile.Load(shipId);
            _systems = GetComponent<ShipSystemsState>();
            if (_systems == null) _systems = GetComponentInParent<ShipSystemsState>();
            if (_systems == null) _systems = gameObject.AddComponent<ShipSystemsState>();
        }

        void EnsureTables()
        {
            if (_pen == null) _pen = ShipPenetrationFile.Load(shipId);
            if (_zones == null) _zones = ShipArmourZonesFile.Load(shipId);
        }

        public bool FireTurret(string key, Transform yawNode, Transform pitchNode)
        {
            if (pitchNode == null)
            {
                LastError = "pitch node null";
                return false;
            }

            _lastGunId = ShipPenetration.GunIdForTurret(key);

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
            EnsureTables();
            if (_systems == null)
            {
                _systems = GetComponent<ShipSystemsState>();
                if (_systems == null) _systems = GetComponentInParent<ShipSystemsState>();
                if (_systems == null) _systems = gameObject.AddComponent<ShipSystemsState>();
            }

            Vector3 origin = barrel.position;
            Vector3 dir = ResolveFireDirection(barrel);

            var hits = Physics.RaycastAll(origin, dir, shellRangeM,
                ~0, QueryTriggerInteraction.Collide);
            System.Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));

            RaycastHit best = default;
            bool found = false;
            foreach (var h in hits)
            {
                if (h.transform.IsChildOf(transform) || h.transform == transform)
                {
                    if (h.distance < 25f) continue;
                }
                best = h;
                found = true;
                break;
            }

            Vector3 end = found ? best.point : origin + dir * shellRangeM;
            SpawnTracer(origin, end);
            var vfx = ShipCombatVfx.FindOrGlobal();
            vfx.PlayTracer(origin, end, dir, found);

            if (!found)
            {
                LastHitSummary = "miss";
                LastPenHit = new ShipPenHit { outcome = ShipPenOutcome.Miss, systemNote = "miss" };
                if (end.y > -1f) vfx.PlaySplash(new Vector3(end.x, Mathf.Max(0f, end.y), end.z));
                return false;
            }

            var compartment = best.collider.GetComponentInParent<ShipCompartment>();
            string targetName = best.collider.name;
            float rangeM = best.distance;
            float incidenceCos = Mathf.Abs(Vector3.Dot(best.normal, dir));

            if (usePenetration)
            {
                var penHit = ShipPenetration.Evaluate(
                    _pen, _zones, _lastGunId, rangeM, targetName, compartment, incidenceCos);
                LastPenHit = penHit;
                vfx.PlayImpact(best.point, penHit.outcome);

                if (penHit.outcome == ShipPenOutcome.NoPenetration)
                {
                    LastHitSummary = penHit.Summary();
                    return true;
                }

                if (compartment != null && penHit.floodM3 > 0f)
                {
                    compartment.Flood(penHit.floodM3);
                    if (penHit.outcome == ShipPenOutcome.Penetrated)
                        _systems.ApplyRole(penHit.role);
                    var floater = best.collider.GetComponentInParent<ShipFloatPrototype>();
                    if (floater != null) floater.RebuildFromCompartments();
                    LastHitSummary = penHit.Summary() + " | " + _systems.StatusText();
                    return true;
                }

                if (penHit.floodM3 > 0f)
                {
                    var anyFloat = best.collider.GetComponentInParent<ShipFloatPrototype>();
                    if (anyFloat != null)
                    {
                        anyFloat.RegisterSurfaceHit(best.point);
                        LastHitSummary = penHit.Summary() + " | surface flood proxy";
                        return true;
                    }
                }

                LastHitSummary = penHit.Summary();
                return true;
            }

            // Legacy path: fixed flood volume, no penetration gate.
            vfx.PlayImpact(best.point, compartment != null ? ShipPenOutcome.Penetrated : ShipPenOutcome.Partial);
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

            LastHitSummary = "struck " + targetName + " (no ShipCompartment)";
            var anyFloat2 = best.collider.GetComponentInParent<ShipFloatPrototype>();
            if (anyFloat2 != null) anyFloat2.RegisterSurfaceHit(best.point);
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

        /// <summary>
        /// Prefer the group-aim world bearing (matches crosshair/camera).
        /// Fallback: barrel local up (legacy asset space).
        /// </summary>
        Vector3 ResolveFireDirection(Transform barrel)
        {
            var aim = GetComponent<ShipMouseGroupAim>();
            if (aim == null) aim = GetComponentInParent<ShipMouseGroupAim>();
            if (aim == null) aim = FindObjectOfType<ShipMouseGroupAim>();
            if (aim != null)
            {
                float shipYaw = transform.eulerAngles.y;
                float worldYaw = shipYaw + aim.aimWorldYawDeg;
                // pitch positive = elevate barrels; Unity X rotation looks down when positive for forward —
                // use negative pitch so +elevation points up.
                Vector3 d = Quaternion.Euler(-aim.aimPitchDeg, worldYaw, 0f) * Vector3.forward;
                if (d.sqrMagnitude > 1e-6f) return d.normalized;
            }
            Vector3 up = barrel.up;
            return up.sqrMagnitude > 1e-6f ? up : barrel.forward;
        }
    }
}
