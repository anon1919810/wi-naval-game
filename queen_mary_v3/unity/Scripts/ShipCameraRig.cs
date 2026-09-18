using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T7 — Tactical chase / fleet overview camera + LOD quality alignment.
    /// Tab toggles mode; each mode can push QualitySettings.lodBias to match lod_profiles.json.
    /// </summary>
    [AddComponentMenu("Naval/Ship Camera Rig")]
    public sealed class ShipCameraRig : MonoBehaviour
    {
        public enum CameraMode
        {
            TacticalChase = 0,
            FleetOverview = 1,
        }

        public Transform target;
        public Camera cam;
        public CameraMode mode = CameraMode.TacticalChase;

        [Header("Tactical 50-200 m")]
        public float tacticalDistance = 120f;
        public float tacticalHeight = 35f;
        public float tacticalYaw = 25f;
        public float tacticalLodBias = 1f;

        [Header("Fleet ~1-2 km")]
        public float fleetDistance = 1700f;
        public float fleetHeight = 420f;
        public float fleetYaw = 40f;
        public float fleetLodBias = 1f;

        [Header("Optional second ship for fleet framing")]
        public Transform[] fleetTargets;

        public float mouseSensitivity = 2.5f;
        public bool applyQualityBias = true;

        float _yaw;
        float _pitch = 18f;

        void Awake()
        {
            if (cam == null) cam = GetComponentInChildren<Camera>();
            if (cam == null) cam = Camera.main;
            _yaw = tacticalYaw;
        }

        void Start()
        {
            if (target == null)
            {
                var def = FindObjectOfType<ShipDefinition>();
                if (def != null && def.prefab != null)
                {
                    var inst = GameObject.Find(def.prefab.name) ?? GameObject.Find("HMS_Queen_Mary_1913");
                    if (inst != null) target = inst.transform;
                }
                if (target == null)
                {
                    var lod = FindObjectOfType<LODGroup>();
                    if (lod != null) target = lod.transform;
                }
            }
            ApplyMode(true);
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Tab))
            {
                mode = mode == CameraMode.TacticalChase ? CameraMode.FleetOverview : CameraMode.TacticalChase;
                ApplyMode(true);
            }
            if (Input.GetMouseButton(1))
            {
                _yaw += Input.GetAxis("Mouse X") * mouseSensitivity;
                _pitch = Mathf.Clamp(_pitch - Input.GetAxis("Mouse Y") * mouseSensitivity, 8f, 75f);
            }
            if (Input.GetKey(KeyCode.Equals) || Input.GetKey(KeyCode.KeypadPlus))
                Zoom(-1);
            if (Input.GetKey(KeyCode.Minus) || Input.GetKey(KeyCode.KeypadMinus))
                Zoom(1);

            LateFollow();
        }

        void Zoom(int dir)
        {
            if (mode == CameraMode.TacticalChase)
                tacticalDistance = Mathf.Clamp(tacticalDistance + dir * 25f, 40f, 250f);
            else
                fleetDistance = Mathf.Clamp(fleetDistance + dir * 120f, 400f, 4000f);
        }

        void LateFollow()
        {
            if (cam == null) return;
            Vector3 focus = target != null ? target.position : Vector3.zero;
            if (mode == CameraMode.FleetOverview && fleetTargets != null && fleetTargets.Length > 0)
            {
                Vector3 sum = Vector3.zero;
                int n = 0;
                foreach (var t in fleetTargets)
                {
                    if (t == null) continue;
                    sum += t.position;
                    n++;
                }
                if (n > 0) focus = sum / n;
            }

            float dist = mode == CameraMode.TacticalChase ? tacticalDistance : fleetDistance;
            float height = mode == CameraMode.TacticalChase ? tacticalHeight : fleetHeight;
            Quaternion rot = Quaternion.Euler(_pitch, _yaw, 0f);
            Vector3 pos = focus + rot * (Vector3.back * dist) + Vector3.up * (height - dist * Mathf.Sin(_pitch * Mathf.Deg2Rad) * 0.15f);
            // Prefer pure orbit: focus + back*dist with pitch/yaw already in rot.
            pos = focus + rot * new Vector3(0f, 0f, -dist);
            if (mode == CameraMode.FleetOverview)
                pos += Vector3.up * height * 0.25f;

            cam.transform.position = Vector3.Lerp(cam.transform.position, pos, 1f - Mathf.Exp(-8f * Time.deltaTime));
            cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation,
                Quaternion.LookRotation(focus - cam.transform.position, Vector3.up),
                1f - Mathf.Exp(-8f * Time.deltaTime));
        }

        public void ApplyMode(bool snap)
        {
            if (applyQualityBias)
            {
                QualitySettings.lodBias = mode == CameraMode.TacticalChase ? tacticalLodBias : fleetLodBias;
            }
            if (mode == CameraMode.TacticalChase)
            {
                _yaw = tacticalYaw;
                _pitch = 18f;
            }
            else
            {
                _yaw = fleetYaw;
                _pitch = 32f;
            }
            if (snap) LateFollow();
        }
    }
}
