using System.Text;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T12 — Mouse drives ALL player main turrets at once (same yaw/pitch command).
    /// Fire (Space / LMB) only fires turrets whose firing arc is CLEAR; blocked turrets are skipped.
    /// Right-mouse is reserved for camera orbit and does not aim turrets.
    /// </summary>
    [AddComponentMenu("Naval/Ship Mouse Group Aim")]
    public sealed class ShipMouseGroupAim : MonoBehaviour
    {
        public ShipTurretController[] turrets;
        public float mouseSensitivity = 0.22f;
        public bool invertPitch = false;
        [Tooltip("Skip aiming while RMB held (camera orbit).")]
        public bool pauseWhileOrbit = true;

        public string LastFireSummary { get; private set; } = "";
        public int LastFiredCount { get; private set; }
        public int LastSkippedCount { get; private set; }

        ShipGunBattery _battery;

        void Start()
        {
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();
            // Group aim owns all turrets; disable per-turret keyboard/fire keys.
            foreach (var t in turrets)
            {
                if (t == null) continue;
                t.inputEnabled = true;
                t.useIndividualKeys = false;
                t.acceptFireKey = false;
            }
            _battery = GetComponent<ShipGunBattery>();
            if (_battery == null) _battery = FindObjectOfType<ShipGunBattery>();
        }

        void Update()
        {
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();

            bool orbiting = Input.GetMouseButton(1);
            if (!(pauseWhileOrbit && orbiting))
            {
                float dx = Input.GetAxis("Mouse X") * mouseSensitivity;
                float dy = Input.GetAxis("Mouse Y") * mouseSensitivity * (invertPitch ? 1f : -1f);
                foreach (var t in turrets)
                {
                    if (t == null) continue;
                    t.yawCommandDeg += dx;
                    t.pitchCommandDeg += dy;
                }
            }

            foreach (var t in turrets)
            {
                if (t == null) continue;
                t.SyncExternalCommands();
            }

            if (Input.GetKeyDown(KeyCode.Space) || Input.GetMouseButtonDown(0))
                FireAllClear();
        }

        /// <summary>Fire every turret that is not in a firing-arc blind zone.</summary>
        public void FireAllClear()
        {
            if (turrets == null || turrets.Length == 0) return;
            var sb = new StringBuilder();
            int fired = 0, skipped = 0;
            foreach (var t in turrets)
            {
                if (t == null) continue;
                t.SyncExternalCommands();
                if (!t.ArcClear)
                {
                    skipped++;
                    t.SetFireBlockReason("blind zone — not fired");
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
            LastFireSummary = string.Format("fired {0}/4 · skipped {1} · {2}", fired, skipped, sb.ToString().Trim());
            Debug.Log("[Naval] Group fire: " + LastFireSummary);
        }
    }
}
