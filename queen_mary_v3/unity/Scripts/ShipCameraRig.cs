using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T7/T13 — Camera modes. Default: ship-centred third person (locked above hull centre).
    /// Tab cycles ThirdPerson → TacticalChase → FleetOverview.
    /// </summary>
    [AddComponentMenu("Naval/Ship Camera Rig")]
    public sealed class ShipCameraRig : MonoBehaviour
    {
        public enum CameraMode
        {
            ShipThirdPerson = 0,
            TacticalChase = 1,
            FleetOverview = 2,
        }

        public Transform target;
        public Camera cam;
        public CameraMode mode = CameraMode.ShipThirdPerson;

        [Header("Third person (ship-centred)")]
        [Tooltip("Local offset from ship root: up and slightly aft, looking over the bow.")]
        public Vector3 thirdPersonLocalOffset = new Vector3(0f, 32f, -42f);
        [Tooltip("Look-at offset in ship local space (ahead of centre).")]
        public Vector3 thirdPersonLookLocal = new Vector3(0f, 8f, 90f);
        public float thirdPersonLodBias = 1f;

        [Header("Tactical orbit 50-200 m")]
        public float tacticalDistance = 120f;
        public float tacticalHeight = 35f;
        public float tacticalYaw = 25f;
        public float tacticalLodBias = 1f;

        [Header("Fleet ~1-2 km")]
        public float fleetDistance = 1700f;
        public float fleetHeight = 420f;
        public float fleetYaw = 40f;
        public float fleetLodBias = 1f;

        public Transform[] fleetTargets;
        public float mouseSensitivity = 2.5f;
        public bool applyQualityBias = true;
        [Tooltip("Allow RMB orbit only in chase/fleet modes.")]
        public bool allowOrbitOutsideThirdPerson = true;

        float _yaw;
        float _pitch = 18f;

        void Awake()
        {
            if (cam == null) cam = GetComponentInChildren<Camera>();
            if (cam == null) cam = Camera.main;
        }

        void Start()
        {
            if (target == null)
            {
                var lod = FindObjectOfType<LODGroup>();
                if (lod != null) target = lod.transform;
                if (target == null)
                {
                    var ship = GameObject.Find("HMS_Queen_Mary_1913");
                    if (ship != null) target = ship.transform;
                }
            }
            ApplyMode(true);
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Tab))
            {
                mode = (CameraMode)(((int)mode + 1) % 3);
                ApplyMode(true);
            }

            bool orbitAllowed = mode != CameraMode.ShipThirdPerson || !allowOrbitOutsideThirdPerson
                ? mode != CameraMode.ShipThirdPerson
                : false;
            // RMB orbit only in non-third-person modes.
            if (mode != CameraMode.ShipThirdPerson && Input.GetMouseButton(1))
            {
                _yaw += Input.GetAxis("Mouse X") * mouseSensitivity;
                _pitch = Mathf.Clamp(_pitch - Input.GetAxis("Mouse Y") * mouseSensitivity, 8f, 75f);
            }
            if (Input.GetKey(KeyCode.Equals) || Input.GetKey(KeyCode.KeypadPlus)) Zoom(-1);
            if (Input.GetKey(KeyCode.Minus) || Input.GetKey(KeyCode.KeypadMinus)) Zoom(1);

            LateFollow();
        }

        void Zoom(int dir)
        {
            if (mode == CameraMode.ShipThirdPerson)
            {
                thirdPersonLocalOffset.z = Mathf.Clamp(thirdPersonLocalOffset.z + dir * 6f, -80f, -18f);
                thirdPersonLocalOffset.y = Mathf.Clamp(thirdPersonLocalOffset.y + dir * 2f, 18f, 55f);
            }
            else if (mode == CameraMode.TacticalChase)
                tacticalDistance = Mathf.Clamp(tacticalDistance + dir * 25f, 40f, 250f);
            else
                fleetDistance = Mathf.Clamp(fleetDistance + dir * 120f, 400f, 4000f);
        }

        void LateFollow()
        {
            if (cam == null) return;
            Vector3 shipPos = target != null ? target.position : Vector3.zero;
            Quaternion shipRot = target != null ? target.rotation : Quaternion.identity;

            if (mode == CameraMode.ShipThirdPerson)
            {
                // Locked to ship centre + upper superstructure; follows ship heading.
                Vector3 pos = shipPos + shipRot * thirdPersonLocalOffset;
                Vector3 look = shipPos + shipRot * thirdPersonLookLocal;
                cam.transform.position = Vector3.Lerp(cam.transform.position, pos,
                    1f - Mathf.Exp(-12f * Time.deltaTime));
                cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation,
                    Quaternion.LookRotation(look - cam.transform.position, Vector3.up),
                    1f - Mathf.Exp(-12f * Time.deltaTime));
                return;
            }

            Vector3 focus = shipPos;
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
            Vector3 pos2 = focus + rot * new Vector3(0f, 0f, -dist);
            if (mode == CameraMode.FleetOverview)
                pos2 += Vector3.up * height * 0.25f;

            cam.transform.position = Vector3.Lerp(cam.transform.position, pos2, 1f - Mathf.Exp(-8f * Time.deltaTime));
            cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation,
                Quaternion.LookRotation(focus - cam.transform.position, Vector3.up),
                1f - Mathf.Exp(-8f * Time.deltaTime));
        }

        public void ApplyMode(bool snap)
        {
            if (applyQualityBias)
            {
                if (mode == CameraMode.ShipThirdPerson)
                    QualitySettings.lodBias = thirdPersonLodBias;
                else if (mode == CameraMode.TacticalChase)
                    QualitySettings.lodBias = tacticalLodBias;
                else
                    QualitySettings.lodBias = fleetLodBias;
            }
            if (mode == CameraMode.TacticalChase)
            {
                _yaw = tacticalYaw;
                _pitch = 18f;
            }
            else if (mode == CameraMode.FleetOverview)
            {
                _yaw = fleetYaw;
                _pitch = 32f;
            }
            if (snap) LateFollow();
        }
    }
}
