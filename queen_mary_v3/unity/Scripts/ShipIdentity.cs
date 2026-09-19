using UnityEngine;

namespace Naval
{
    /// <summary>
    /// A02 — Ship instance identity. DefinitionId may be equal across same-class ships;
    /// InstanceId must be unique in scene. Damage attribution uses InstanceId only.
    /// </summary>
    [AddComponentMenu("Naval/Ship Identity")]
    public sealed class ShipIdentity : MonoBehaviour
    {
        public string definitionId = "HMS_Queen_Mary_1913";
        public string instanceId = "";

        public string InstanceId
        {
            get
            {
                if (!string.IsNullOrEmpty(instanceId)) return instanceId;
                return gameObject.name;
            }
        }

        public ShipIdentity RootIdentity()
        {
            var id = GetComponentInParent<ShipIdentity>();
            return id != null ? id : this;
        }

        public static ShipIdentity FromTransform(Transform t)
        {
            return t != null ? t.GetComponentInParent<ShipIdentity>() : null;
        }

        public static bool SameShip(ShipIdentity a, ShipIdentity b)
        {
            if (a == null || b == null) return false;
            return a.InstanceId == b.InstanceId;
        }
    }
}
