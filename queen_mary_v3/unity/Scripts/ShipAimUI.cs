using System.Text;
using UnityEngine;

namespace Naval
{
    /// <summary>T10/T12 — Turret highlight only; does not draw UI.</summary>
    [AddComponentMenu("Naval/Ship Turret Selector")]
    public sealed class ShipTurretSelector : MonoBehaviour
    {
        public static readonly string[] DefaultOrder = { "A", "B", "Q", "X" };
        public string selectedKey = "A";
        public ShipTurretController[] turrets;
        public bool soloMode = false;

        public ShipTurretController Selected
        {
            get
            {
                if (turrets == null) return null;
                foreach (var t in turrets)
                    if (t != null && t.turretKey == selectedKey) return t;
                return null;
            }
        }

        void Start()
        {
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();
            ApplySelection();
        }

        void Update()
        {
            if (turrets == null || turrets.Length == 0)
                turrets = FindObjectsOfType<ShipTurretController>();
            if (Input.GetKeyDown(KeyCode.Alpha1)) selectedKey = "A";
            if (Input.GetKeyDown(KeyCode.Alpha2)) selectedKey = "B";
            if (Input.GetKeyDown(KeyCode.Alpha3)) selectedKey = "Q";
            if (Input.GetKeyDown(KeyCode.Alpha4)) selectedKey = "X";
            ApplySelection();
        }

        void ApplySelection()
        {
            if (turrets == null) return;
            foreach (var t in turrets)
            {
                if (t == null) continue;
                t.inputEnabled = soloMode ? (t.turretKey == selectedKey) : true;
            }
        }
    }

    /// <summary>
    /// Clean combat HUD: small crosshair, corner panels only — no text over the ship.
    /// F1 toggles extra debug lines.
    /// </summary>
    [AddComponentMenu("Naval/Ship Aim UI")]
    public sealed class ShipAimUI : MonoBehaviour
    {
        public ShipTurretSelector selector;
        public ShipGunBattery battery;
        public ShipFloatPrototype floater;
        public ShipSystemsState systems;
        public ShipCameraRig cameraRig;
        public ShipGameplayHUD hud;
        public ShipMouseGroupAim groupAim;
        public ShipTargetShip target;
        public bool showControlHint = true;
        public float controlHintSeconds = 12f;

        Texture2D _tex;
        GUIStyle _label;
        GUIStyle _labelDim;
        GUIStyle _cross;
        float _playTime;
        bool _debug;

        void Start()
        {
            _playTime = 0f;
            if (selector == null) selector = FindObjectOfType<ShipTurretSelector>();
            if (battery == null) battery = FindObjectOfType<ShipGunBattery>();
            if (floater == null) floater = FindObjectOfType<ShipFloatPrototype>();
            if (systems == null) systems = FindObjectOfType<ShipSystemsState>();
            if (groupAim == null) groupAim = FindObjectOfType<ShipMouseGroupAim>();
            if (cameraRig == null) cameraRig = FindObjectOfType<ShipCameraRig>();
            if (cameraRig != null && groupAim != null) cameraRig.aim = groupAim;
            if (target == null) target = FindObjectOfType<ShipTargetShip>();
            if (target == null) target = ShipLabRuntime.EnsureTargetShip();
            if (hud != null) hud.debugPanelVisible = false;
            if (_tex == null)
            {
                _tex = new Texture2D(1, 1);
                _tex.SetPixel(0, 0, Color.white);
                _tex.Apply();
            }
        }

        void Update()
        {
            _playTime += Time.deltaTime;
            if (Input.GetKeyDown(KeyCode.F1)) _debug = !_debug;
        }

        void OnGUI()
        {
            EnsureStyles();
            float w = Screen.width;
            float h = Screen.height;
            float cx = w * 0.5f;
            float cy = h * 0.5f;

            DrawCrosshair(cx, cy);

            // --- Top-left: guns + aim + hit (never over ship midline) ---
            var sb = new StringBuilder();
            if (groupAim != null)
            {
                sb.Append("方位 ").Append(groupAim.aimWorldYawDeg.ToString("0")).Append("°  仰角 ")
                  .Append(groupAim.aimPitchDeg.ToString("0.0")).Append("°\n");
                if (groupAim.turrets != null)
                {
                    sb.Append("炮塔 ");
                    foreach (var t in groupAim.turrets)
                    {
                        if (t == null) continue;
                        sb.Append(t.turretKey).Append(t.ArcClear ? "·可射  " : "·盲区  ");
                    }
                    sb.Append('\n');
                }
                if (!string.IsNullOrEmpty(groupAim.LastFireSummary))
                    sb.Append(groupAim.LastFireSummary).Append('\n');
            }
            if (battery != null && !string.IsNullOrEmpty(battery.LastHitSummary))
                sb.Append("命中：").Append(battery.LastHitSummary);

            GUI.Label(new Rect(16f, 12f, 420f, 90f), sb.ToString(), _label);

            // --- Top-right: self + target (compact) ---
            var rt = new StringBuilder();
            if (floater != null) rt.Append("我方 ").Append(floater.StatusText).Append('\n');
            if (systems != null) rt.Append(systems.StatusText()).Append('\n');
            if (target != null) rt.Append("靶船 ").Append(target.StatusText);
            GUI.Label(new Rect(w - 430f, 12f, 414f, 100f), rt.ToString(), _labelDim);

            // --- Bottom: controls (auto-hide) ---
            if (showControlHint && _playTime < controlHintSeconds)
            {
                float barH = 36f;
                GUI.color = new Color(0f, 0f, 0f, 0.45f);
                GUI.DrawTexture(new Rect(0f, h - barH, w, barH), _tex);
                GUI.color = Color.white;
                string hint =
                    "鼠标 转视角/炮塔   空格/左键 开火   Esc 释放鼠标   点游戏窗锁定   Tab 相机   R 重置   F1 调试";
                GUI.Label(new Rect(0f, h - barH + 8f, w, barH), hint, _labelDim);
            }

            if (_debug && groupAim != null)
            {
                GUI.Label(new Rect(16f, 100f, 480f, 80f),
                    "DEBUG aim yaw " + groupAim.aimWorldYawDeg.ToString("0.0") +
                    " pitch " + groupAim.aimPitchDeg.ToString("0.0") +
                    "\ncursor " + Cursor.lockState +
                    "\n" + (groupAim.LastFireSummary ?? ""), _labelDim);
            }
        }

        void EnsureStyles()
        {
            if (_label == null)
            {
                _label = new GUIStyle(GUI.skin.label) { fontSize = 13, richText = false };
                _label.normal.textColor = Color.white;
            }
            if (_labelDim == null)
            {
                _labelDim = new GUIStyle(GUI.skin.label) { fontSize = 12, richText = false };
                _labelDim.normal.textColor = new Color(0.85f, 0.9f, 0.95f, 0.85f);
            }
        }

        void DrawCrosshair(float cx, float cy)
        {
            const float arm = 9f;
            const float thick = 1.5f;
            var c = new Color(1f, 1f, 1f, 0.75f);
            var prev = GUI.color;
            GUI.color = c;
            GUI.DrawTexture(new Rect(cx - arm, cy - thick * 0.5f, arm * 2f, thick), _tex);
            GUI.DrawTexture(new Rect(cx - thick * 0.5f, cy - arm, thick, arm * 2f), _tex);
            GUI.color = new Color(1f, 0.8f, 0.2f, 0.9f);
            GUI.DrawTexture(new Rect(cx - 1.5f, cy - 1.5f, 3f, 3f), _tex);
            GUI.color = prev;
        }
    }

    /// <summary>Global shell: reset flood/systems, target drift, cursor helpers.</summary>
    [AddComponentMenu("Naval/Ship Input Shell")]
    public sealed class ShipInputShell : MonoBehaviour
    {
        public ShipFloatPrototype floater;
        public ShipSystemsState systems;
        public ShipGameplayHUD hud;
        public ShipAimUI aimUi;
        public ShipTargetShip target;

        void Start()
        {
            if (floater == null) floater = FindObjectOfType<ShipFloatPrototype>();
            if (systems == null) systems = FindObjectOfType<ShipSystemsState>();
            if (hud == null) hud = FindObjectOfType<ShipGameplayHUD>();
            if (aimUi == null) aimUi = FindObjectOfType<ShipAimUI>();
            if (target == null && aimUi != null) target = aimUi.target;
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.R))
            {
                if (floater != null) floater.ResetFlooding();
                if (systems != null) systems.ResetSystems();
                if (target != null) target.ResetTarget();
                else
                {
                    var t = FindObjectOfType<ShipTargetShip>();
                    if (t != null) t.ResetTarget();
                }
            }
            if (Input.GetKeyDown(KeyCode.T))
            {
                var t = target != null ? target : FindObjectOfType<ShipTargetShip>();
                if (t != null) t.drift = !t.drift;
            }
            if (Input.GetKeyDown(KeyCode.F1) && hud != null)
                hud.debugPanelVisible = !hud.debugPanelVisible;
        }
    }
}
