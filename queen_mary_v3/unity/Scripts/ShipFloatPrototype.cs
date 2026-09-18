using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T5 — Prototype flood → sinkage/trim. NOT a full hydrostatic solver.
    /// Uses hydrostatics waterplane area + simplified longitudinal second moment.
    /// Ship root is expected at design waterline (Y=0 local when undamaged).
    /// </summary>
    [AddComponentMenu("Naval/Ship Float Prototype")]
    public sealed class ShipFloatPrototype : MonoBehaviour
    {
        public string shipId = "HMS_Queen_Mary_1913";

        [Tooltip("Waterplane area m^2 from hydrostatics.json (default Queen Mary estimate).")]
        public float waterplaneAreaM2 = 4610.4f;
        [Tooltip("Ship length for crude I_L ≈ A * L^2 / 12.")]
        public float lengthM = 213.4f;
        [Tooltip("Optional metacentric-ish restoring lever for trim display (m).")]
        public float trimRestoringM = 1.5f;
        public float maxSinkageM = 4.5f;
        public float maxTrimDeg = 8f;

        public float FloodedVolumeM3 { get; private set; }
        public float SinkageM { get; private set; }
        public float TrimDeg { get; private set; }
        public string StatusText { get; private set; } = "intact";

        Vector3 _initialLocalPos;
        Quaternion _initialLocalRot;
        bool _captured;
        ShipCompartment[] _compartments;

        void Awake()
        {
            CaptureInitial();
            RebuildFromCompartments();
        }

        void CaptureInitial()
        {
            if (_captured) return;
            _initialLocalPos = transform.localPosition;
            _initialLocalRot = transform.localRotation;
            _captured = true;
        }

        public void RebuildFromCompartments()
        {
            CaptureInitial();
            if (_compartments == null || _compartments.Length == 0)
                _compartments = GetComponentsInChildren<ShipCompartment>(true);

            float volume = 0f;
            float moment = 0f; // about local Z = bow axis (longitudinal trim)
            float rollMoment = 0f;
            int floodedCount = 0;
            foreach (var c in _compartments)
            {
                if (c == null) continue;
                float v = c.FloodedVolumeM3;
                if (v <= 0.001f) continue;
                volume += v;
                floodedCount++;
                // Compartment world position → local to ship root.
                Vector3 local = transform.InverseTransformPoint(c.transform.position);
                moment += v * local.z;
                rollMoment += v * local.x;
            }

            FloodedVolumeM3 = volume;
            float area = Mathf.Max(waterplaneAreaM2, 1f);
            SinkageM = Mathf.Min(volume / area, maxSinkageM);

            // Crude longitudinal second moment of waterplane.
            float IL = area * lengthM * lengthM / 12f;
            float trimRad = IL > 1f ? moment / IL : 0f;
            if (trimRestoringM > 0.05f)
                trimRad = moment / (area * trimRestoringM * lengthM * 0.15f + IL * 0.05f);
            TrimDeg = Mathf.Clamp(trimRad * Mathf.Rad2Deg, -maxTrimDeg, maxTrimDeg);

            // +Z bow: positive moment (flood aft, local.z < 0) → stern down → bow up.
            // Unity +X rotation raises +Z (bow) for right-hand rule; stern-down = +pitch.
            // moment = Σ v * z; aft z<0 → negative moment → bow up (positive rotation.x).
            float pitchDeg = TrimDeg;

            // Roll: flood on port (-X) should list port down = rotate about +Z.
            float rollDeg = Mathf.Clamp(rollMoment / area * 0.02f, -maxTrimDeg, maxTrimDeg);

            transform.localPosition = _initialLocalPos + new Vector3(0f, -SinkageM, 0f);
            transform.localRotation = _initialLocalRot *
                Quaternion.Euler(pitchDeg, 0f, rollDeg);

            StatusText = string.Format(
                "flood {0:0} m3 · sink {1:0.00} m · trim {2:0.0}° · compartments {3}",
                volume, SinkageM, pitchDeg, floodedCount);
        }

        public void RegisterSurfaceHit(Vector3 worldPoint)
        {
            // Surface hit without compartment: tiny progressive flooding for feedback.
            var nearest = FindNearestCompartment(worldPoint);
            if (nearest != null)
            {
                nearest.Flood(Mathf.Max(20f, floodableProxyM3 * 0.02f));
                RebuildFromCompartments();
            }
        }

        [Tooltip("Used when a non-compartment hit auto-floods the nearest compartment slightly.")]
        public float floodableProxyM3 = 600f;

        ShipCompartment FindNearestCompartment(Vector3 world)
        {
            if (_compartments == null || _compartments.Length == 0)
                _compartments = GetComponentsInChildren<ShipCompartment>(true);
            ShipCompartment best = null;
            float bestD = float.MaxValue;
            foreach (var c in _compartments)
            {
                if (c == null) continue;
                float d = (c.transform.position - world).sqrMagnitude;
                if (d < bestD)
                {
                    bestD = d;
                    best = c;
                }
            }
            return best;
        }

        [ContextMenu("Reset flooding")]
        public void ResetFlooding()
        {
            foreach (var c in GetComponentsInChildren<ShipCompartment>(true))
                c.floodFraction = 0f;
            RebuildFromCompartments();
        }
    }
}
