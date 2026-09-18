using UnityEngine;

namespace Naval
{
    /// <summary>T7 + T5/T6 debug HUD for gameplay lab.</summary>
    [AddComponentMenu("Naval/Ship Gameplay HUD")]
    public sealed class ShipGameplayHUD : MonoBehaviour
    {
        public ShipTurretController[] turrets;
        public ShipFloatPrototype floater;
        public ShipCameraRig cameraRig;
        public ShipGunBattery battery;
        public LODGroup lodGroup;
        public ShipSystemsState systems;
        public bool debugPanelVisible = true;

        string _lastHit = "";
        GUIStyle _style;

        void Start()
        {
            if (floater == null) floater = FindObjectOfType<ShipFloatPrototype>();
            if (cameraRig == null) cameraRig = FindObjectOfType<ShipCameraRig>();
            if (battery == null) battery = FindObjectOfType<ShipGunBattery>();
            if (systems == null) systems = FindObjectOfType<ShipSystemsState>();
            if (lodGroup == null && floater != null) lodGroup = floater.GetComponentInChildren<LODGroup>();
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();
        }

        void Update()
        {
            if (battery != null && !string.IsNullOrEmpty(battery.LastHitSummary))
                _lastHit = battery.LastHitSummary;
        }

        void OnGUI()
        {
            // AimUI owns the visible HUD; this panel is debug-only (F1 / explicit flag).
            if (!debugPanelVisible) return;
            if (_style == null)
            {
                _style = new GUIStyle(GUI.skin.label) { fontSize = 14, richText = false };
                _style.normal.textColor = Color.white;
            }

            float w = 640f;
            GUILayout.BeginArea(new Rect(12, 12, w, Screen.height - 24));
            GUILayout.Label("WI Naval · Gameplay Lab (T5 flood / T6 turrets / T7 camera+LOD / T9 penetration)", _style);

            if (cameraRig != null)
            {
                float bias = QualitySettings.lodBias;
                GUILayout.Label(string.Format(
                    "Camera: {0}  lodBias={1:0.##}  quality={2}  (Tab switch, RMB orbit, +/- zoom)",
                    cameraRig.mode, bias, QualitySettings.GetQualityLevel()), _style);
            }

            if (lodGroup != null)
            {
                var lods = lodGroup.GetLODs();
                int current = -1;
                // Approximate current LOD via first renderer enabled state is unreliable;
                // report thresholds + ForceLOD debug not required — show estimated relH if camera exists.
                float relH = -1f;
                var cam = cameraRig != null ? cameraRig.cam : Camera.main;
                if (cam != null)
                    relH = lodGroup.size * QualitySettings.lodBias /
                           (2f * Vector3.Distance(cam.transform.position, lodGroup.transform.position) *
                            Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad));
                if (relH >= 0f && lods != null)
                {
                    for (int i = 0; i < lods.Length; i++)
                        if (relH >= lods[i].screenRelativeTransitionHeight) { current = i; break; }
                    if (current < 0) current = lods.Length;
                }
                string thresholds = "";
                if (lods != null)
                    foreach (var l in lods) thresholds += l.screenRelativeTransitionHeight.ToString("0.00") + " ";
                GUILayout.Label(string.Format(
                    "LODGroup size={0:0.0} m  relH≈{1:0.000}  est.LOD={2}  thresholds[{3}]",
                    lodGroup.size, relH, current, thresholds.TrimEnd()), _style);
            }

            if (floater != null)
                GUILayout.Label("Float: " + floater.StatusText, _style);
            if (systems != null)
                GUILayout.Label("Systems: " + systems.StatusText(), _style);
            if (!string.IsNullOrEmpty(_lastHit))
                GUILayout.Label("Last hit: " + _lastHit, _style);

            if (turrets != null)
            {
                foreach (var t in turrets)
                {
                    if (t == null) continue;
                    GUILayout.Label(string.Format(
                        "Turret {0}: yaw={1:0.0} pitch={2:0.0} arc={3}{4}",
                        t.turretKey, t.yawCommandDeg, t.pitchCommandDeg,
                        t.ArcClear ? "CLEAR" : "BLOCKED",
                        string.IsNullOrEmpty(t.LastFireBlockReason) ? "" : " · " + t.LastFireBlockReason),
                        _style);
                }
            }

            GUILayout.Label("Keys: 1-4 select turret · arrows aim · Space/LMB fire · R reset · F1 HUD", _style);
            GUILayout.EndArea();
        }
    }
}
