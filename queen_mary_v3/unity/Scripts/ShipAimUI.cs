using System.Text;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T10/T12 — Optional turret highlight. Solo mode gates input to one turret;
    /// default (soloMode=false) keeps all turrets live for mouse group-aim.
    /// </summary>
    [AddComponentMenu("Naval/Ship Turret Selector")]
    public sealed class ShipTurretSelector : MonoBehaviour
    {
        public static readonly string[] DefaultOrder = { "A", "B", "Q", "X" };

        public string selectedKey = "A";
        public ShipTurretController[] turrets;
        [Tooltip("If true, only the selected turret is live. Group mouse-aim uses false.")]
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
            if (Input.GetKeyDown(KeyCode.LeftBracket)) Cycle(-1);
            if (Input.GetKeyDown(KeyCode.RightBracket)) Cycle(1);

            ApplySelection();
        }

        void Cycle(int dir)
        {
            var order = DefaultOrder;
            int idx = System.Array.IndexOf(order, selectedKey);
            if (idx < 0) idx = 0;
            idx = (idx + dir + order.Length) % order.Length;
            selectedKey = order[idx];
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

    /// <summary>T10/T12 — Crosshair + per-turret arc status + command bar.</summary>
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
        public string commandHint =
            "Mouse L/R: rotate VIEW + turrets (same bearing) · U/D: elevation\n" +
            "RMB: look up/down · Space/LMB fire · Tab camera · F1 debug HUD";

        Texture2D _tex;
        GUIStyle _center;
        GUIStyle _small;

        void Start()
        {
            if (selector == null) selector = FindObjectOfType<ShipTurretSelector>();
            if (battery == null) battery = FindObjectOfType<ShipGunBattery>();
            if (floater == null) floater = FindObjectOfType<ShipFloatPrototype>();
            if (systems == null) systems = FindObjectOfType<ShipSystemsState>();
            if (cameraRig == null) cameraRig = FindObjectOfType<ShipCameraRig>();
            if (groupAim == null) groupAim = FindObjectOfType<ShipMouseGroupAim>();
            if (hud == null) hud = GetComponent<ShipGameplayHUD>();
            if (hud != null && groupAim != null) hud.debugPanelVisible = false;
            if (_tex == null)
            {
                _tex = new Texture2D(1, 1);
                _tex.SetPixel(0, 0, Color.white);
                _tex.Apply();
            }
        }

        void OnGUI()
        {
            if (_center == null)
            {
                _center = new GUIStyle(GUI.skin.label)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 22,
                    fontStyle = FontStyle.Bold,
                };
                _center.normal.textColor = Color.white;
            }
            if (_small == null)
            {
                _small = new GUIStyle(GUI.skin.label) { fontSize = 12 };
                _small.normal.textColor = new Color(0.9f, 0.92f, 0.95f, 0.95f);
            }

            float cx = Screen.width * 0.5f;
            float cy = Screen.height * 0.5f;
            DrawCross(cx, cy, 18f, 2f, new Color(1f, 1f, 1f, 0.85f));
            DrawCross(cx, cy, 6f, 2f, new Color(1f, 0.75f, 0.2f, 0.95f));

            bool anyBlocked = false;
            string arcTxt;
            if (groupAim != null && groupAim.turrets != null)
            {
                var line = new StringBuilder("Turrets ALL · ");
                foreach (var t in groupAim.turrets)
                {
                    if (t == null) continue;
                    line.Append(t.turretKey).Append(t.ArcClear ? "✓ " : "✗ ");
                    if (!t.ArcClear) anyBlocked = true;
                }
                arcTxt = line.ToString();
            }
            else
            {
                var sel = selector != null ? selector.Selected : null;
                bool arc = sel == null || sel.ArcClear;
                anyBlocked = !arc;
                arcTxt = "Turret " + (selector != null ? selector.selectedKey : "-") +
                         " · " + (arc ? "ARC CLEAR" : "ARC BLOCKED");
            }

            Color arcCol = anyBlocked
                ? new Color(1f, 0.55f, 0.3f)
                : new Color(0.45f, 0.95f, 0.45f);
            var prev = _center.normal.textColor;
            _center.normal.textColor = arcCol;
            GUI.Label(new Rect(cx - 240f, cy + 28f, 480f, 28f), arcTxt, _center);
            _center.normal.textColor = prev;

            string block = "";
            if (groupAim != null && !string.IsNullOrEmpty(groupAim.LastFireSummary))
                block = groupAim.LastFireSummary;
            else if (selector != null && selector.Selected != null &&
                     !string.IsNullOrEmpty(selector.Selected.LastFireBlockReason))
                block = selector.Selected.LastFireBlockReason;
            if (!string.IsNullOrEmpty(block))
                GUI.Label(new Rect(cx - 280f, cy + 54f, 560f, 20f), block, _small);

            float barH = 52f;
            GUI.Box(new Rect(12f, Screen.height - barH - 12f, 760f, barH), "");
            GUI.Label(new Rect(20f, Screen.height - barH - 6f, 740f, 44f), commandHint, _small);

            string status = "";
            if (cameraRig != null)
                status += "Cam " + cameraRig.mode + "  lodBias " + QualitySettings.lodBias.ToString("0.##") + "\n";
            if (floater != null) status += "Float: " + floater.StatusText + "\n";
            if (systems != null) status += "Sys: " + systems.StatusText() + "\n";
            if (groupAim != null && !string.IsNullOrEmpty(groupAim.LastFireSummary))
                status += "Fire: " + groupAim.LastFireSummary + "\n";
            else if (groupAim != null)
                status += string.Format("Aim world yaw {0:0}°  pitch {1:0.0}°\n",
                    groupAim.aimWorldYawDeg, groupAim.aimPitchDeg);
            if (battery != null && !string.IsNullOrEmpty(battery.LastHitSummary))
                status += "Hit: " + battery.LastHitSummary;
            if (!string.IsNullOrEmpty(status))
                GUI.Label(new Rect(Screen.width - 560f, 12f, 548f, 130f), status, _small);
        }

        void DrawCross(float x, float y, float size, float thick, Color color)
        {
            var prev = GUI.color;
            GUI.color = color;
            GUI.DrawTexture(new Rect(x - size, y - thick * 0.5f, size * 2f, thick), _tex);
            GUI.DrawTexture(new Rect(x - thick * 0.5f, y - size, thick, size * 2f), _tex);
            GUI.color = prev;
        }
    }

    /// <summary>T10 — Reset flood/systems, toggle debug HUD.</summary>
    [AddComponentMenu("Naval/Ship Input Shell")]
    public sealed class ShipInputShell : MonoBehaviour
    {
        public ShipFloatPrototype floater;
        public ShipSystemsState systems;
        public ShipGameplayHUD hud;
        public ShipAimUI aimUi;

        void Start()
        {
            if (floater == null) floater = FindObjectOfType<ShipFloatPrototype>();
            if (systems == null) systems = FindObjectOfType<ShipSystemsState>();
            if (hud == null) hud = FindObjectOfType<ShipGameplayHUD>();
            if (aimUi == null) aimUi = FindObjectOfType<ShipAimUI>();
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.R))
            {
                if (floater != null) floater.ResetFlooding();
                if (systems != null) systems.ResetSystems();
                Debug.Log("[Naval] Reset flood + systems");
            }
            if (Input.GetKeyDown(KeyCode.F1))
            {
                if (hud != null) hud.debugPanelVisible = !hud.debugPanelVisible;
            }
        }
    }
}
