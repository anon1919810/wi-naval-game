using UnityEngine;

namespace Naval
{
    /// <summary>
    /// Editor-play safety: if the lab scene was not rebuilt after T11 merge,
    /// spawn the target Queen Mary at runtime so combat can still be tested.
    /// </summary>
    public static class ShipLabRuntime
    {
        public const string PrefabPath = "Assets/Prefabs/Ships/HMS_Queen_Mary_1913.prefab";
        public const string TargetName = "HMS_Queen_Mary_1913_Target";
        public static readonly Vector3 DefaultTargetPos = new Vector3(60f, 0f, 520f);
        public static readonly Quaternion DefaultTargetRot = Quaternion.Euler(0f, 190f, 0f);

        public static ShipTargetShip EnsureTargetShip()
        {
            var existing = Object.FindObjectOfType<ShipTargetShip>();
            if (existing != null) return existing;

            GameObject prefab = null;
#if UNITY_EDITOR
            prefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
#endif
            if (prefab == null) return null;

            var go = Object.Instantiate(prefab, DefaultTargetPos, DefaultTargetRot);
            go.name = TargetName;

            var floater = go.GetComponent<ShipFloatPrototype>();
            if (floater == null) floater = go.AddComponent<ShipFloatPrototype>();
            var systems = go.GetComponent<ShipSystemsState>();
            if (systems == null) systems = go.AddComponent<ShipSystemsState>();
            var battery = go.GetComponent<ShipGunBattery>();
            if (battery == null) battery = go.AddComponent<ShipGunBattery>();
            battery.enabled = false;
            foreach (var t in go.GetComponentsInChildren<ShipTurretController>(true))
            {
                t.inputEnabled = false;
                t.useIndividualKeys = false;
                t.acceptFireKey = false;
            }

            var marker = go.GetComponent<ShipTargetShip>();
            if (marker == null) marker = go.AddComponent<ShipTargetShip>();
            marker.displayName = "Target Queen Mary";
            marker.floater = floater;
            marker.systems = systems;
            marker.battery = battery;
            var tid = go.GetComponent<ShipIdentity>();
            if (tid == null) tid = go.AddComponent<ShipIdentity>();
            tid.definitionId = "HMS_Queen_Mary_1913";
            tid.instanceId = "target_01";

            var cam = Camera.main;
            var label = go.GetComponent<ShipTargetLabel>();
            if (label == null) label = go.AddComponent<ShipTargetLabel>();
            label.target = marker;
            label.cam = cam;

            var tb = go.GetComponent<ShipTargetBattery>();
            if (tb == null) tb = go.AddComponent<ShipTargetBattery>();
            tb.target = marker;
            tb.playerRoot = GameObject.Find("HMS_Queen_Mary_1913") != null
                ? GameObject.Find("HMS_Queen_Mary_1913").transform
                : null;
            tb.enabledFire = false;

            var aim = Object.FindObjectOfType<ShipAimUI>();
            if (aim != null) aim.target = marker;
            var shell = Object.FindObjectOfType<ShipInputShell>();
            if (shell != null) shell.target = marker;
            var rig = Object.FindObjectOfType<ShipCameraRig>();
            if (rig != null && (rig.fleetTargets == null || rig.fleetTargets.Length < 2))
            {
                var player = GameObject.Find("HMS_Queen_Mary_1913");
                if (player != null)
                    rig.fleetTargets = new[] { player.transform, go.transform };
            }

            Debug.Log("[Naval] Spawned runtime target ship at " + DefaultTargetPos);
            return marker;
        }
    }
}
