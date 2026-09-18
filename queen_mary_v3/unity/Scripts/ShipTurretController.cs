using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T6 — Turret yaw/pitch command + firing-arc gate.
    /// Command angles are relative to rest pose; apply uses documented Unity axes:
    /// yaw = rest * AngleAxis(yaw, Vector3.forward), pitch = rest * AngleAxis(pitch, Vector3.right).
    /// </summary>
    [AddComponentMenu("Naval/Ship Turret Controller")]
    public sealed class ShipTurretController : MonoBehaviour
    {
        public string shipId = "HMS_Queen_Mary_1913";
        public string turretKey = "A";

        [Tooltip("Yaw node, e.g. Turret_A. Auto-filled from contract when empty.")]
        public Transform yawNode;
        [Tooltip("Pitch node, e.g. Elevation_A.")]
        public Transform pitchNode;

        public float yawCommandDeg;
        public float pitchCommandDeg;
        public float yawRateDegPerSec = 12f;
        public float pitchRateDegPerSec = 6f;

        [Tooltip("Block Fire when current yaw is outside firing_arcs intervals.")]
        public bool gateFireOnArcs = true;

        Quaternion _restYaw = Quaternion.identity;
        Quaternion _restPitch = Quaternion.identity;
        bool _restCaptured;
        ShipContractData _contract;
        ShipFiringArcsData _arcs;
        ShipGunBattery _battery;

        public bool ArcClear { get; private set; }
        public string LastFireBlockReason { get; private set; }

        void Awake()
        {
            _battery = GetComponent<ShipGunBattery>();
            if (_battery == null) _battery = GetComponentInParent<ShipGunBattery>();
        }

        void Start()
        {
            EnsureBinding();
            CaptureRestIfNeeded();
            Apply();
        }

        void EnsureBinding()
        {
            if (_contract == null)
            {
                try { _contract = ShipContractData.Load(shipId); }
                catch { _contract = null; }
            }
            if (_arcs == null)
                _arcs = ShipFiringArcsData.Load(shipId);

            if ((yawNode == null || pitchNode == null) && _contract != null)
            {
                ShipTurret t = null;
                try { t = _contract.Turret(turretKey); } catch { t = null; }
                if (t != null)
                {
                    if (yawNode == null)
                    {
                        var yawTr = FindDeep(transform.root, t.turret);
                        if (yawTr != null) yawNode = yawTr;
                    }
                    if (pitchNode == null)
                    {
                        var pitchTr = FindDeep(transform.root, t.pivot);
                        if (pitchTr != null) pitchNode = pitchTr;
                    }
                }
            }
            CaptureRestIfNeeded();
        }

        static Transform FindDeep(Transform root, string name)
        {
            if (root == null || string.IsNullOrEmpty(name)) return null;
            if (root.name == name) return root;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            return null;
        }

        void CaptureRestIfNeeded()
        {
            if (_restCaptured || yawNode == null) return;
            _restYaw = yawNode.localRotation;
            if (pitchNode != null) _restPitch = pitchNode.localRotation;
            _restCaptured = true;

            // Clamp mechanical limits from contract when available.
            if (_contract != null)
            {
                try
                {
                    var t = _contract.Turret(turretKey);
                    if (t != null)
                    {
                        pitchCommandDeg = Mathf.Clamp(pitchCommandDeg, t.min_elevation_deg, t.max_elevation_deg);
                    }
                }
                catch { /* key missing */ }
            }
        }

        void Update()
        {
            EnsureBinding();
            CaptureRestIfNeeded();

            float yawIn = 0f, pitchIn = 0f;
            if (turretKey == "A" || turretKey == "Q")
            {
                yawIn = Input.GetAxisRaw("Horizontal");
                pitchIn = Input.GetAxisRaw("Vertical");
            }
            else if (turretKey == "B" || turretKey == "X")
            {
                // Secondary keys: B uses IKJL-like, X uses numpad-ish alternatives via axes.
                yawIn = (Input.GetKey(KeyCode.L) ? 1f : 0f) - (Input.GetKey(KeyCode.J) ? 1f : 0f);
                pitchIn = (Input.GetKey(KeyCode.I) ? 1f : 0f) - (Input.GetKey(KeyCode.K) ? 1f : 0f);
            }

            yawCommandDeg += yawIn * yawRateDegPerSec * Time.deltaTime;
            pitchCommandDeg += pitchIn * pitchRateDegPerSec * Time.deltaTime;

            if (_contract != null)
            {
                try
                {
                    var t = _contract.Turret(turretKey);
                    if (t != null)
                        pitchCommandDeg = Mathf.Clamp(pitchCommandDeg, t.min_elevation_deg, t.max_elevation_deg);
                }
                catch { }
            }

            ArcClear = _arcs == null || _arcs.IsYawClear(turretKey, yawCommandDeg, pitchCommandDeg);
            Apply();

            if (Input.GetKeyDown(KeyCode.Space) || Input.GetMouseButtonDown(0))
                TryFire();
        }

        void Apply()
        {
            if (yawNode == null) return;
            yawNode.localRotation = _restYaw * Quaternion.AngleAxis(yawCommandDeg, Vector3.forward);
            if (pitchNode != null)
                pitchNode.localRotation = _restPitch * Quaternion.AngleAxis(pitchCommandDeg, Vector3.right);
        }

        public bool TryFire()
        {
            EnsureBinding();
            CaptureRestIfNeeded();
            if (gateFireOnArcs && _arcs != null && !ArcClear)
            {
                LastFireBlockReason = "firing arc blocked yaw " + yawCommandDeg.ToString("0.0");
                return false;
            }
            if (_contract != null)
            {
                try
                {
                    var t = _contract.Turret(turretKey);
                    if (t != null && pitchCommandDeg > t.director_elevation_limit_deg + 0.01f)
                    {
                        // Not a hard block for prototype — 1913 director limit is informational.
                        LastFireBlockReason = "above 1913 director elevation (mount still allowed)";
                    }
                }
                catch { }
            }

            if (_battery == null) _battery = GetComponent<ShipGunBattery>();
            if (_battery == null) _battery = GetComponentInParent<ShipGunBattery>();
            if (_battery == null)
            {
                LastFireBlockReason = "no ShipGunBattery";
                return false;
            }

            if (yawNode == null || pitchNode == null)
            {
                LastFireBlockReason = "turret nodes not bound";
                return false;
            }

            bool ok = _battery.FireTurret(turretKey, yawNode, pitchNode);
            LastFireBlockReason = ok ? "" : (_battery.LastError ?? "fire failed");
            return ok;
        }

        void OnDrawGizmosSelected()
        {
            if (yawNode == null || pitchNode == null) return;
            Gizmos.color = ArcClear ? Color.green : Color.red;
            var origin = pitchNode.position;
            var dir = pitchNode.rotation * Vector3.up;
            // Barrel local +Y after pitch node; in Unity muzzle approx along pitchNode up after rest capture.
            // Use child barrel if present.
            Transform barrel = null;
            foreach (Transform child in pitchNode)
            {
                if (child.name.StartsWith("Barrel_" + turretKey)) { barrel = child; break; }
            }
            if (barrel != null)
            {
                origin = barrel.position;
                dir = barrel.up;
            }
            Gizmos.DrawLine(origin, origin + dir * 40f);
        }
    }
}
