using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T11 — Same-prefab Queen Mary used as a target barge.
    /// Player guns raycast into this ship; flood/systems live on this instance.
    /// Optional slow straight-line sail for motion practice.
    /// </summary>
    [AddComponentMenu("Naval/Ship Target")]
    public sealed class ShipTargetShip : MonoBehaviour
    {
        public string displayName = "Target Queen Mary";
        public bool drift = false;
        [Tooltip("m/s along ship +Z when drift is on")]
        public float driftSpeedMps = 6f;

        public ShipFloatPrototype floater;
        public ShipSystemsState systems;
        public ShipGunBattery battery;

        public string StatusText { get; private set; } = "target idle";

        void Awake()
        {
            if (floater == null) floater = GetComponent<ShipFloatPrototype>();
            if (floater == null) floater = gameObject.AddComponent<ShipFloatPrototype>();
            if (systems == null) systems = GetComponent<ShipSystemsState>();
            if (systems == null) systems = gameObject.AddComponent<ShipSystemsState>();

            battery = GetComponent<ShipGunBattery>();
            if (battery != null) battery.enabled = false;

            foreach (var t in GetComponentsInChildren<ShipTurretController>(true))
                t.inputEnabled = false;
            var selector = GetComponent<ShipTurretSelector>();
            if (selector != null) Destroy(selector);

            RefreshStatus();
        }

        void Update()
        {
            if (drift && driftSpeedMps > 0f)
                transform.position += transform.forward * (driftSpeedMps * Time.deltaTime);
            RefreshStatus();
        }

        void RefreshStatus()
        {
            string flood = floater != null ? floater.StatusText : "no float";
            string sys = systems != null ? systems.StatusText() : "no systems";
            Vector3 p = transform.position;
            StatusText = string.Format("{0} @({1:0},{2:0},{3:0}) {4} | {5}",
                displayName, p.x, p.y, p.z, flood, sys);
        }

        public void ResetTarget()
        {
            if (floater != null) floater.ResetFlooding();
            if (systems != null) systems.ResetSystems();
        }
    }

    /// <summary>
    /// T11 — Optional target return fire along +Z toward player sector.
    /// Prototype: fixed interval, always fires if battery present, not AI.
    /// </summary>
    [AddComponentMenu("Naval/Ship Target Battery")]
    public sealed class ShipTargetBattery : MonoBehaviour
    {
        public ShipTargetShip target;
        public Transform playerRoot;
        public float fireIntervalSec = 8f;
        public string fireTurretKey = "X";
        public bool enabledFire = false;

        float _timer;
        ShipGunBattery _battery;
        ShipTurretController[] _turrets;

        void Start()
        {
            if (target == null) target = GetComponent<ShipTargetShip>();
            _battery = GetComponent<ShipGunBattery>();
            if (_battery != null) _battery.enabled = true;
            _turrets = GetComponentsInChildren<ShipTurretController>(true);
        }

        void Update()
        {
            if (!enabledFire || _battery == null) return;
            _timer += Time.deltaTime;
            if (_timer < fireIntervalSec) return;
            _timer = 0f;

            ShipTurretController pick = null;
            foreach (var t in _turrets)
                if (t != null && t.turretKey == fireTurretKey) { pick = t; break; }
            if (pick == null && _turrets != null && _turrets.Length > 0) pick = _turrets[0];
            if (pick == null) return;

            pick.inputEnabled = true;
            // Aim roughly toward player: yaw command from local direction.
            if (playerRoot != null)
            {
                Vector3 local = pick.transform.InverseTransformPoint(playerRoot.position);
                float yaw = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
                pick.yawCommandDeg = yaw;
                pick.pitchCommandDeg = 5f;
            }
            pick.TryFire();
            pick.inputEnabled = false;
        }
    }

    /// <summary>World-space style label for the target using OnGUI projection.</summary>
    [AddComponentMenu("Naval/Ship Target Label")]
    public sealed class ShipTargetLabel : MonoBehaviour
    {
        public ShipTargetShip target;
        public Camera cam;

        GUIStyle _style;

        void Start()
        {
            if (target == null) target = GetComponent<ShipTargetShip>();
            if (cam == null) cam = Camera.main;
        }

        void OnGUI()
        {
            if (target == null || cam == null) return;
            if (_style == null)
            {
                _style = new GUIStyle(GUI.skin.label) { fontSize = 12, alignment = TextAnchor.MiddleCenter };
                _style.normal.textColor = new Color(1f, 0.85f, 0.35f, 0.95f);
            }
            Vector3 world = target.transform.position + Vector3.up * 40f;
            Vector3 sp = cam.WorldToScreenPoint(world);
            if (sp.z < 1f) return;
            float x = sp.x - 160f;
            float y = Screen.height - sp.y - 36f;
            GUI.Label(new Rect(x, y, 320f, 40f), target.StatusText, _style);
        }
    }
}
