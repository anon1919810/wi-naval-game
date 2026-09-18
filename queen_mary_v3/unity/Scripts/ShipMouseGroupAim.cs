using System.Text;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T12/T13 — Mouse sets ONE world bearing (0 = ship bow +Z) and pitch.
    /// Each turret converts that to its own command angle:
    ///   yawCommand = worldAimYaw - rest_yaw_deg
    /// so barrels converge on the same compass direction instead of rotating
    /// identically from each rest pose (which looked centre-symmetric).
    /// Fire: only turrets whose firing-arc CLEAR will shoot.
    /// </summary>
    [AddComponentMenu("Naval/Ship Mouse Group Aim")]
    public sealed class ShipMouseGroupAim : MonoBehaviour
    {
        public ShipTurretController[] turrets;
        public float mouseSensitivity = 0.45f;
        public bool invertPitch = false;

        [Tooltip("World aim yaw in degrees, 0 = ship bow (+Z). Mouse X adjusts this.")]
        public float aimWorldYawDeg = 0f;
        [Tooltip("Shared elevation command for all turrets.")]
        public float aimPitchDeg = 4f;
        public float minPitchDeg = -3f;
        public float maxPitchDeg = 20f;

        public string LastFireSummary { get; private set; } = "";
        public int LastFiredCount { get; private set; }
        public int LastSkippedCount { get; private set; }

        [Tooltip("Lock and hide the cursor so Mouse X/Y keep giving relative motion (Game view edge no longer caps yaw).")]
        public bool lockCursorOnStart = true;

        ShipContractData _contract;
        ShipFiringArcsData _arcs;

        public static void LockGameCursor()
        {
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
        }

        public static void UnlockGameCursor()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        void Start()
        {
            if (lockCursorOnStart) LockGameCursor();
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();
            foreach (var t in turrets)
            {
                if (t == null) continue;
                t.inputEnabled = true;
                t.useIndividualKeys = false;
                t.acceptFireKey = false;
            }
            try { _contract = ShipContractData.Load("HMS_Queen_Mary_1913"); } catch { _contract = null; }
            _arcs = ShipFiringArcsData.Load("HMS_Queen_Mary_1913");
            ApplyWorldAimToTurrets();
        }

        void Update()
        {
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();

            // Esc releases the cursor; click Game view to re-lock (this click does not fire).
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                UnlockGameCursor();
                return;
            }
            bool cursorFree = Cursor.lockState != CursorLockMode.Locked;
            if (cursorFree && Input.GetMouseButtonDown(0))
            {
                LockGameCursor();
                return;
            }
            if (cursorFree)
            {
                // No aim/fire while the cursor is free — deltas are unreliable at window edges.
                ApplyWorldAimToTurrets();
                return;
            }

            aimWorldYawDeg += Input.GetAxis("Mouse X") * mouseSensitivity;
            aimWorldYawDeg = Normalize360(aimWorldYawDeg);
            float dy = Input.GetAxis("Mouse Y") * mouseSensitivity * (invertPitch ? 1f : -1f);
            aimPitchDeg = Mathf.Clamp(aimPitchDeg + dy, minPitchDeg, maxPitchDeg);

            ApplyWorldAimToTurrets();

            if (Input.GetKeyDown(KeyCode.Space) || Input.GetMouseButtonDown(0))
                FireAllClear();
        }

        public float RestYawDeg(string turretKey)
        {
            if (_contract != null)
            {
                try
                {
                    var t = _contract.Turret(turretKey);
                    if (t != null) return t.rest_yaw_deg;
                }
                catch { }
            }
            if (_arcs != null)
            {
                var at = _arcs.Turret(turretKey);
                if (at != null) return at.rest_yaw_deg;
            }
            // A/B forward, Q/X aft (as-built).
            return (turretKey == "Q" || turretKey == "X") ? 180f : 0f;
        }

        void ApplyWorldAimToTurrets()
        {
            foreach (var t in turrets)
            {
                if (t == null) continue;
                float rest = RestYawDeg(t.turretKey);
                // command relative to rest so world bearing = rest + command
                t.yawCommandDeg = Normalize360(aimWorldYawDeg - rest);
                t.pitchCommandDeg = aimPitchDeg;
                t.SyncExternalCommands();
            }
        }

        public static float Normalize360(float deg)
        {
            float v = deg % 360f;
            if (v < 0f) v += 360f;
            return v;
        }

        public void FireAllClear()
        {
            if (turrets == null || turrets.Length == 0) return;
            ApplyWorldAimToTurrets();
            var sb = new StringBuilder();
            int fired = 0, skipped = 0;
            foreach (var t in turrets)
            {
                if (t == null) continue;
                t.SyncExternalCommands();
                if (!t.ArcClear)
                {
                    skipped++;
                    t.SetFireBlockReason(string.Format(
                        "blind zone — cmd yaw {0:0}° (rest {1:0}°)",
                        t.yawCommandDeg, RestYawDeg(t.turretKey)));
                    sb.Append(t.turretKey).Append("=SKIP ");
                    continue;
                }
                bool ok = t.TryFire();
                if (ok)
                {
                    fired++;
                    sb.Append(t.turretKey).Append("=FIRE ");
                }
                else
                {
                    skipped++;
                    sb.Append(t.turretKey).Append("=FAIL(").Append(t.LastFireBlockReason).Append(") ");
                }
            }
            LastFiredCount = fired;
            LastSkippedCount = skipped;
            LastFireSummary = string.Format(
                "world yaw {0:0}° · fired {1}/4 · skipped {2} · {3}",
                aimWorldYawDeg, fired, skipped, sb.ToString().Trim());
            Debug.Log("[Naval] Group fire: " + LastFireSummary);
        }
    }
}
