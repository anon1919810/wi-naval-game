using System;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// T9 — Prototype penetration: range→mm table + zone armour mm + system effects.
    /// Estimate curves, not certified ballistic tables. No ricochet model.
    /// </summary>
    [Serializable]
    public class ShipPenetrationGun
    {
        public string id;
        public int calibre_mm;
        public string label;
        public float muzzle_velocity_mps;
        public float shell_weight_lb;
        public float max_range_m;
        public string source;
        public float[] samples_m;
        public float[] penetration_mm;
    }

    [Serializable]
    public class ShipPenetrationThresholds
    {
        public float penetrate_ratio = 1f;
        public float partial_ratio = 0.5f;
    }

    [Serializable]
    public class ShipPenetrationFlood
    {
        public float magazine = 400f;
        public float boiler_room = 200f;
        public float engine_room = 250f;
        public float steering_gear = 120f;
        public float hull_generic = 150f;
        public float partial = 40f;
        public float no_penetration = 0f;
    }

    [Serializable]
    public class ShipPenetrationFile
    {
        public string asset;
        public string note;
        public string accuracy;
        public bool historically_certified;
        public ShipPenetrationGun[] guns;
        public ShipPenetrationThresholds thresholds;
        public ShipPenetrationFlood flood_m3;

        public const string FileName = "penetration_main.json";
        public const string ResourceFolder = "Ships";

        public static string RelativePath(string shipId) =>
            ResourceFolder + "/" + shipId + "/" + FileName;

        public static ShipPenetrationFile Load(string shipId)
        {
            string resPath = RelativePath(shipId);
            int dot = resPath.LastIndexOf(".json", StringComparison.Ordinal);
            if (dot >= 0) resPath = resPath.Substring(0, dot);
            var asset = Resources.Load<TextAsset>(resPath);
            if (asset == null) return null;
            return Parse(asset.text);
        }

        public static ShipPenetrationFile Parse(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            var data = JsonUtility.FromJson<ShipPenetrationFile>(json);
            return data != null && data.guns != null && data.guns.Length > 0 ? data : null;
        }

        public ShipPenetrationGun Gun(string id)
        {
            if (guns == null || string.IsNullOrEmpty(id)) return null;
            foreach (var g in guns)
                if (g != null && g.id == id) return g;
            return null;
        }

        public static float PenetrationMm(ShipPenetrationGun gun, float rangeM)
        {
            if (gun == null || gun.samples_m == null || gun.penetration_mm == null ||
                gun.samples_m.Length == 0 ||
                gun.samples_m.Length != gun.penetration_mm.Length)
                return 0f;
            float r = Mathf.Max(0f, rangeM);
            var s = gun.samples_m;
            var p = gun.penetration_mm;
            if (r <= s[0]) return p[0];
            if (r >= s[s.Length - 1]) return p[p.Length - 1];
            for (int i = 0; i < s.Length - 1; i++)
            {
                if (r >= s[i] && r <= s[i + 1])
                {
                    float t = (r - s[i]) / Mathf.Max(1e-3f, s[i + 1] - s[i]);
                    return Mathf.Lerp(p[i], p[i + 1], t);
                }
            }
            return p[p.Length - 1];
        }
    }

    /// <summary>
    /// Flattened armour zone tables for JsonUtility (parallel arrays).
    /// </summary>
    [Serializable]
    public class ShipArmourZonesFile
    {
        public string asset;
        public string accuracy;
        public bool historically_certified;
        public string source_note;
        public string[] zone_ids;
        public float[] zone_mm;
        public string[] zone_source;
        public string[] name_contains;
        public string[] name_zone;
        public string[] compartment_key;
        public float[] compartment_mm;
        public string[] role_key;
        public string[] role_zone;

        public const string FileName = "armour_zones.json";
        public const string ResourceFolder = "Ships";

        public static string RelativePath(string shipId) =>
            ResourceFolder + "/" + shipId + "/" + FileName;

        public static ShipArmourZonesFile Load(string shipId)
        {
            string resPath = RelativePath(shipId);
            int dot = resPath.LastIndexOf(".json", StringComparison.Ordinal);
            if (dot >= 0) resPath = resPath.Substring(0, dot);
            var asset = Resources.Load<TextAsset>(resPath);
            if (asset == null) return null;
            try { return JsonUtility.FromJson<ShipArmourZonesFile>(asset.text); }
            catch { return null; }
        }

        public float ZoneMm(string zoneId)
        {
            if (string.IsNullOrEmpty(zoneId) || zone_ids == null || zone_mm == null) return 20f;
            for (int i = 0; i < zone_ids.Length && i < zone_mm.Length; i++)
                if (zone_ids[i] == zoneId) return zone_mm[i];
            return ZoneMm("unknown");
        }

        public string ZoneIdForName(string objectName)
        {
            if (string.IsNullOrEmpty(objectName) || name_contains == null || name_zone == null)
                return "unknown";
            for (int i = 0; i < name_contains.Length && i < name_zone.Length; i++)
            {
                if (string.IsNullOrEmpty(name_contains[i])) continue;
                if (objectName.IndexOf(name_contains[i], StringComparison.OrdinalIgnoreCase) >= 0)
                    return name_zone[i];
            }
            return "unknown";
        }

        public float CompartmentSideMm(string module)
        {
            if (string.IsNullOrEmpty(module) || compartment_key == null || compartment_mm == null)
                return -1f;
            for (int i = 0; i < compartment_key.Length && i < compartment_mm.Length; i++)
                if (compartment_key[i] == module) return compartment_mm[i];
            return -1f;
        }

        public string RoleZone(string role)
        {
            if (string.IsNullOrEmpty(role) || role_key == null || role_zone == null)
                return "unknown";
            for (int i = 0; i < role_key.Length && i < role_zone.Length; i++)
                if (role_key[i] == role) return role_zone[i];
            return "unknown";
        }
    }

    public enum ShipPenOutcome
    {
        Miss = 0,
        NoPenetration = 1,
        Partial = 2,
        Penetrated = 3,
    }

    public struct ShipPenHit
    {
        public ShipPenOutcome outcome;
        public string gunId;
        public float rangeM;
        public float penetrationMm;
        public float armourMm;
        public string zoneId;
        public string targetName;
        public string compartmentId;
        public string role;
        public float floodM3;
        public string systemNote;

        public string Summary()
        {
            return string.Format(
                "{0} gun={1} range={2:0}m pen={3:0}mm armour={4:0}mm zone={5} target={6} compartment={7} flood={8:0}m3 {9}",
                outcome, gunId, rangeM, penetrationMm, armourMm, zoneId, targetName,
                string.IsNullOrEmpty(compartmentId) ? "-" : compartmentId,
                floodM3, systemNote);
        }
    }

    /// <summary>Aggregate machinery / steering / magazine state. Prototype only.</summary>
    [AddComponentMenu("Naval/Ship Systems State")]
    public sealed class ShipSystemsState : MonoBehaviour
    {
        public int boilerRoomsHit;
        public int engineRoomsHit;
        public bool magazineHit;
        public bool steeringHit;
        public string status = "intact";

        public float SpeedFactor
        {
            get
            {
                float f = 1f;
                f -= Mathf.Clamp(boilerRoomsHit, 0, 7) * 0.08f;
                f -= Mathf.Clamp(engineRoomsHit, 0, 2) * 0.15f;
                if (magazineHit) f -= 0.25f;
                return Mathf.Clamp(f, 0.2f, 1f);
            }
        }

        public float SteerFactor => steeringHit ? 0.25f : 1f;

        public void ApplyRole(string role)
        {
            if (role == "boiler_room") { boilerRoomsHit = Mathf.Min(7, boilerRoomsHit + 1); status = "boiler_hit"; }
            else if (role == "engine_room") { engineRoomsHit = Mathf.Min(2, engineRoomsHit + 1); status = "engine_hit"; }
            else if (role == "magazine") { magazineHit = true; status = "magazine_critical"; }
            else if (role == "steering_gear") { steeringHit = true; status = "steering_damaged"; }
        }

        public void ResetSystems()
        {
            boilerRoomsHit = 0;
            engineRoomsHit = 0;
            magazineHit = false;
            steeringHit = false;
            status = "intact";
        }

        public string StatusText()
        {
            return string.Format("{0} · boilers {1}/7 · engines {2}/2 · mag {3} · steer {4} · speed×{5:0.00}",
                status, boilerRoomsHit, engineRoomsHit, magazineHit ? "HIT" : "ok",
                steeringHit ? "HIT" : "ok", SpeedFactor);
        }
    }

    public static class ShipPenetration
    {
        public static string GunIdForTurret(string turretKey)
        {
            if (turretKey == "A" || turretKey == "B" || turretKey == "Q" || turretKey == "X")
                return "main_343mm";
            return "secondary_102mm";
        }

        public static ShipPenHit Evaluate(
            ShipPenetrationFile penFile,
            ShipArmourZonesFile zones,
            string gunId,
            float rangeM,
            string colliderName,
            ShipCompartment compartment,
            float incidenceCos)
        {
            var hit = new ShipPenHit
            {
                gunId = gunId,
                rangeM = rangeM,
                targetName = colliderName ?? "",
                outcome = ShipPenOutcome.Miss,
            };

            var gun = penFile != null ? penFile.Gun(gunId) : null;
            hit.penetrationMm = ShipPenetrationFile.PenetrationMm(gun, rangeM);

            float armour = 20f;
            string zoneId = "unknown";
            if (zones != null)
            {
                if (compartment != null && !string.IsNullOrEmpty(compartment.compartmentId))
                {
                    float side = zones.CompartmentSideMm(compartment.compartmentId);
                    hit.compartmentId = compartment.compartmentId;
                    hit.role = compartment.role;
                    if (side > 0f)
                    {
                        armour = side;
                        zoneId = zones.RoleZone(compartment.role);
                        if (string.IsNullOrEmpty(zoneId) || zoneId == "unknown")
                            zoneId = side >= 200f ? "belt_main" : "hull_unprotected";
                    }
                    else
                    {
                        zoneId = zones.RoleZone(compartment.role);
                        armour = zones.ZoneMm(zoneId);
                    }
                }
                else
                {
                    zoneId = zones.ZoneIdForName(colliderName);
                    armour = zones.ZoneMm(zoneId);
                    hit.role = zoneId == "superstructure" || zoneId == "uptake"
                        ? "superstructure" : "hull_envelope";
                }
            }
            hit.zoneId = zoneId;

            if (incidenceCos > 0.05f)
                armour = armour / Mathf.Clamp(incidenceCos, 0.25f, 1f);
            hit.armourMm = armour;

            float penetrateRatio = penFile != null && penFile.thresholds != null
                ? Mathf.Max(0.01f, penFile.thresholds.penetrate_ratio) : 1f;
            float partialRatio = penFile != null && penFile.thresholds != null
                ? penFile.thresholds.partial_ratio : 0.5f;

            if (hit.penetrationMm >= armour * penetrateRatio)
            {
                hit.outcome = ShipPenOutcome.Penetrated;
                hit.floodM3 = FloodForRole(penFile, hit.role);
                hit.systemNote = "PENETRATED";
            }
            else if (hit.penetrationMm >= armour * partialRatio)
            {
                hit.outcome = ShipPenOutcome.Partial;
                hit.floodM3 = penFile != null && penFile.flood_m3 != null
                    ? penFile.flood_m3.partial : 40f;
                hit.systemNote = "partial damage";
            }
            else
            {
                hit.outcome = ShipPenOutcome.NoPenetration;
                hit.floodM3 = 0f;
                hit.systemNote = "no penetration";
            }
            return hit;
        }

        static float FloodForRole(ShipPenetrationFile penFile, string role)
        {
            var f = penFile != null ? penFile.flood_m3 : null;
            if (f == null)
            {
                if (role == "magazine") return 400f;
                if (role == "boiler_room") return 200f;
                if (role == "engine_room") return 250f;
                if (role == "steering_gear") return 120f;
                return 150f;
            }
            if (role == "magazine") return f.magazine;
            if (role == "boiler_room") return f.boiler_room;
            if (role == "engine_room") return f.engine_room;
            if (role == "steering_gear") return f.steering_gear;
            return f.hull_generic;
        }
    }
}
