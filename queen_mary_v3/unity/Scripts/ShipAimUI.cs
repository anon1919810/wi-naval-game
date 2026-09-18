using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T10 — Selects the active main turret so only one controller consumes fire/aim input.
    /// Keys: Alpha1=A, Alpha2=B, Alpha3=Q, Alpha4=X, or Q/E cycle (Q conflicts with turret Q —
    /// use 1-4 primarily; Tab is reserved for camera).
    /// </summary>
    [AddComponentMenu("Naval/Ship Turret Selector")]
    public sealed class ShipTurretSelector : MonoBehaviour
    {
        public static readonly string[] DefaultOrder = { "A", "B", "Q", "X" };

        public string selectedKey = "A";
        public ShipTurretController[] turrets;

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
                t.inputEnabled = (t.turretKey == selectedKey);
            }
        }
    }

    /// <summary>
    /// T10 — Screen crosshair + compact command legend + aim/fire status.
    /// Does not require Inspector wiring when placed on the HUD object.
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
            if (hud == null) hud = GetComponent<ShipGameplayHUD>();
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

            var sel = selector != null ? selector.Selected : null;
            string key = selector != null ? selector.selectedKey : "-";
            bool arc = sel == null || sel.ArcClear;
            string arcTxt = arc ? "ARC CLEAR" : "ARC BLOCKED";
            Color arcCol = arc ? new Color(0.45f, 0.95f, 0.45f) : new Color(1f, 0.35f, 0.3f);

            var prev = _center.normal.textColor;
            _center.normal.textColor = arcCol;
            GUI.Label(new Rect(cx - 160f, cy + 28f, 320f, 28f), "Turret " + key + " · " + arcTxt, _center);
            _center.normal.textColor = prev;

            string block = sel != null && !string.IsNullOrEmpty(sel.LastFireBlockReason)
                ? sel.LastFireBlockReason : "";
            if (!string.IsNullOrEmpty(block))
                GUI.Label(new Rect(cx - 200f, cy + 54f, 400f, 20f), block, _small);

            // Bottom command bar
            float barH = 52f;
            GUI.Box(new Rect(12f, Screen.height - barH - 12f, 720f, barH), "");
            GUI.Label(new Rect(20f, Screen.height - barH - 6f, 700f, 44f),
                "1-4 / [ ]  select turret   ·   Arrows aim selected   ·   Space/LMB fire\n" +
                "Tab camera   ·   RMB orbit  +/- zoom   ·   R reset flood+systems   ·   F1 toggle HUD",
                _small);

            // Top-right compact status
            string status = "";
            if (cameraRig != null)
                status += "Cam " + cameraRig.mode + "  lodBias " + QualitySettings.lodBias.ToString("0.##") + "\n";
            if (floater != null) status += floater.StatusText + "\n";
            if (systems != null) status += systems.StatusText() + "\n";
            if (battery != null && !string.IsNullOrEmpty(battery.LastHitSummary))
                status += "Hit: " + battery.LastHitSummary;
            if (!string.IsNullOrEmpty(status))
                GUI.Label(new Rect(Screen.width - 520f, 12f, 508f, 110f), status, _small);
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

    /// <summary>
    /// T10 — Global shell commands: reset flooding/systems, toggle debug HUD.
    /// </summary>
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
