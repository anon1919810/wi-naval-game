using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Naval.EditorTools
{
    /// <summary>
    /// Builds a playable gameplay lab scene: ship prefab + float/turrets/battery + camera + sea + HUD.
    /// Menu: Tools/Naval/Build gameplay lab
    /// Batch: Naval.EditorTools.ShipGameplayLabBuilder.BuildBatch
    /// </summary>
    public static class ShipGameplayLabBuilder
    {
        public const string ShipId = "HMS_Queen_Mary_1913";
        public const string PrefabPath = "Assets/Prefabs/Ships/" + ShipId + ".prefab";
        public const string ScenePath = "Assets/Scenes/GameplayLab.unity";

        [MenuItem("Tools/Naval/Build gameplay lab")]
        public static void BuildMenu()
        {
            var report = Build();
            EditorUtility.DisplayDialog("Gameplay lab",
                report, "OK");
        }

        public static void BuildBatch()
        {
            string report = Build();
            Debug.Log("[Naval] Gameplay lab: " + report);
            if (Application.isBatchMode)
                EditorApplication.Exit(report.StartsWith("OK") ? 0 : 1);
        }

        public static string Build()
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            if (prefab == null)
                return "FAIL missing prefab " + PrefabPath;

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var sea = GameObject.CreatePrimitive(PrimitiveType.Plane);
            sea.name = "Sea";
            sea.transform.localScale = new Vector3(40f, 1f, 40f);
            var seaMat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
            seaMat.color = new Color(0.05f, 0.12f, 0.18f);
            sea.GetComponent<MeshRenderer>().sharedMaterial = seaMat;

            var ship = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            ship.name = ShipId;
            ship.transform.position = Vector3.zero;

            var floater = ship.GetComponent<ShipFloatPrototype>();
            if (floater == null) floater = ship.AddComponent<ShipFloatPrototype>();
            var battery = ship.GetComponent<ShipGunBattery>();
            if (battery == null) battery = ship.AddComponent<ShipGunBattery>();

            string[] keys = { "A", "B", "Q", "X" };
            var controllers = new ShipTurretController[keys.Length];
            for (int i = 0; i < keys.Length; i++)
            {
                string key = keys[i];
                var yaw = FindDeep(ship.transform, "Turret_" + key);
                var hostGo = yaw != null ? yaw.gameObject : ship;
                var ctrl = hostGo.GetComponent<ShipTurretController>();
                if (ctrl == null) ctrl = hostGo.AddComponent<ShipTurretController>();
                ctrl.shipId = ShipId;
                ctrl.turretKey = key;
                ctrl.yawNode = yaw;
                ctrl.pitchNode = FindDeep(ship.transform, "Elevation_" + key);
                ctrl.inputEnabled = true;
                ctrl.useIndividualKeys = false;
                ctrl.acceptFireKey = false;
                controllers[i] = ctrl;
            }

            var selector = ship.GetComponent<ShipTurretSelector>();
            if (selector == null) selector = ship.AddComponent<ShipTurretSelector>();
            selector.turrets = controllers;
            selector.selectedKey = "A";
            // Group mouse aim drives all four; selector no longer gates input.
            foreach (var c in controllers) if (c != null) c.inputEnabled = true;

            var systems = ship.GetComponent<ShipSystemsState>();
            if (systems == null) ship.AddComponent<ShipSystemsState>();
            ShipCombatVfx.EnsureOn(ship);

            var camGo = new GameObject("GameplayCamera");
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = 50f;
            cam.farClipPlane = 12000f;
            camGo.tag = "MainCamera";
            camGo.AddComponent<AudioListener>();
            var rig = camGo.AddComponent<ShipCameraRig>();
            rig.target = ship.transform;
            rig.cam = cam;
            rig.mode = ShipCameraRig.CameraMode.ShipThirdPerson;
            rig.thirdPersonHeight = 34f;
            rig.thirdPersonBack = 48f;
            rig.thirdPersonLookHeight = 10f;
            rig.thirdPersonLookAhead = 120f;
            rig.thirdPersonLodBias = 1f;
            rig.tacticalDistance = 140f;
            rig.tacticalLodBias = 1f;
            rig.fleetDistance = 1700f;
            rig.fleetLodBias = 1f;
            rig.applyQualityBias = true;

            var lightGo = new GameObject("Sun");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50f, 30f, 0f);

            var hudGo = new GameObject("GameplayHUD");
            var hud = hudGo.AddComponent<ShipGameplayHUD>();
            hud.turrets = controllers;
            hud.floater = floater;
            hud.cameraRig = rig;
            hud.battery = battery;
            hud.lodGroup = ship.GetComponentInChildren<LODGroup>();
            hud.systems = ship.GetComponent<ShipSystemsState>();

            var aim = hudGo.AddComponent<ShipAimUI>();
            aim.selector = selector;
            aim.battery = battery;
            aim.floater = floater;
            aim.systems = hud.systems;
            aim.cameraRig = rig;
            aim.hud = hud;
            aim.groupAim = ship.AddComponent<ShipMouseGroupAim>();
            aim.groupAim.turrets = controllers;
            rig.aim = aim.groupAim;
            hud.debugPanelVisible = false;

            var shell = hudGo.AddComponent<ShipInputShell>();
            shell.floater = floater;
            shell.systems = hud.systems;
            shell.hud = hud;
            shell.aimUi = aim;

            // T11 — second Queen Mary as target barge (same prefab).
            var targetGo = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            targetGo.name = ShipId + "_Target";
            // Ahead and slightly starboard so default third-person (look along bow) sees the target.
            targetGo.transform.position = new Vector3(60f, 0f, 520f);
            targetGo.transform.rotation = Quaternion.Euler(0f, 190f, 0f);
            var targetFloater = targetGo.GetComponent<ShipFloatPrototype>();
            if (targetFloater == null) targetFloater = targetGo.AddComponent<ShipFloatPrototype>();
            var targetSystems = targetGo.GetComponent<ShipSystemsState>();
            if (targetSystems == null) targetSystems = targetGo.AddComponent<ShipSystemsState>();
            var targetBattery = targetGo.GetComponent<ShipGunBattery>();
            if (targetBattery == null) targetBattery = targetGo.AddComponent<ShipGunBattery>();
            targetBattery.enabled = false;
            foreach (var tc in targetGo.GetComponentsInChildren<ShipTurretController>(true))
                tc.inputEnabled = false;
            var tSel = targetGo.GetComponent<ShipTurretSelector>();
            if (tSel != null) Object.DestroyImmediate(tSel);

            var marker = targetGo.GetComponent<ShipTargetShip>();
            if (marker == null) marker = targetGo.AddComponent<ShipTargetShip>();
            marker.displayName = "Target Queen Mary";
            marker.drift = false;
            marker.driftSpeedMps = 6f;
            marker.floater = targetFloater;
            marker.systems = targetSystems;
            marker.battery = targetBattery;
            ShipCombatVfx.EnsureOn(targetGo);

            var tLabel = targetGo.GetComponent<ShipTargetLabel>();
            if (tLabel == null) tLabel = targetGo.AddComponent<ShipTargetLabel>();
            tLabel.target = marker;
            tLabel.cam = cam;

            var tBat = targetGo.GetComponent<ShipTargetBattery>();
            if (tBat == null) tBat = targetGo.AddComponent<ShipTargetBattery>();
            tBat.target = marker;
            tBat.playerRoot = ship.transform;
            tBat.enabledFire = false;

            aim.target = marker;
            shell.target = marker;
            rig.fleetTargets = new[] { ship.transform, targetGo.transform };

            EnsureFolder("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(ScenePath, true)
            };

            var note = "Gameplay lab built " + System.DateTime.UtcNow.ToString("o") +
                       "\nPlayer " + ship.name + " @origin; Target " + targetGo.name + " @ (60,0,520)" +
                       "\nT11+T12: same-prefab target + mouse world-bearing group fire.\n";
            File.WriteAllText(Path.Combine(Application.dataPath, "../GameplayLab_Note.txt"), note);

            return "OK scene " + ScenePath + " ship " + ship.name +
                   " target " + targetGo.name +
                   " turrets " + controllers.Length +
                   " float/flood + battery + camera rig + HUD + target label";
        }

        static Transform FindDeep(Transform root, string name)
        {
            if (root == null) return null;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                if (t.name == name) return t;
            return null;
        }

        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            if (!AssetDatabase.IsValidFolder(parent)) EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
