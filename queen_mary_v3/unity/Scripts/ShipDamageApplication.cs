using UnityEngine;

namespace Naval
{
    /// <summary>
    /// A02 — Apply completed penetration outcomes to the hit ship instance only.
    /// Never reads shooter-side cached systems for target module state.
    /// </summary>
    public static class ShipDamageApplication
    {
        public static bool Apply(ShipCompartment target, ShipPenHit hit)
        {
            if (target == null || hit.outcome == ShipPenOutcome.Miss)
                return false;

            var identity = target.GetComponentInParent<ShipIdentity>();
            if (identity == null)
            {
                Debug.LogError("[Naval] Damage target has no ShipIdentity: " + target.name);
                return false;
            }

            var systems = identity.GetComponent<ShipSystemsState>();
            if (systems == null) systems = identity.GetComponentInChildren<ShipSystemsState>();
            var floater = identity.GetComponent<ShipFloatPrototype>();
            if (floater == null) floater = identity.GetComponentInChildren<ShipFloatPrototype>();

            string moduleId = string.IsNullOrEmpty(target.compartmentId) ? target.name : target.compartmentId;
            if (string.IsNullOrEmpty(moduleId))
            {
                Debug.LogError("[Naval] Damage compartment missing module id");
                return false;
            }

            if (hit.floodM3 > 0f)
                target.Flood(hit.floodM3);

            if (hit.outcome == ShipPenOutcome.Penetrated)
            {
                if (systems == null)
                {
                    Debug.LogError("[Naval] Target identity " + identity.InstanceId + " missing ShipSystemsState");
                    return false;
                }
                systems.ApplyModule(moduleId, string.IsNullOrEmpty(hit.role) ? target.role : hit.role);
            }

            if (floater != null)
                floater.RebuildFromCompartments();

            return true;
        }
    }
}
