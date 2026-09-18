using System;
using System.Collections.Generic;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// Runtime view of firing_arcs.unity.json (flattened for JsonUtility).
    /// Intervals are relative to that turret rest_yaw zero, in degrees, yaw command space.
    /// Conservative geometry sample — not a ballistic or blast model.
    /// </summary>
    [Serializable]
    public class ShipFiringArcInterval
    {
        public float a;
        public float b;
    }

    [Serializable]
    public class ShipFiringArcElevation
    {
        public float elevation_deg;
        public float clear_fraction;
        public ShipFiringArcInterval[] intervals;
    }

    [Serializable]
    public class ShipFiringArcTurret
    {
        public string key;
        public string zero_bearing;
        public float rest_yaw_deg;
        public ShipFiringArcElevation[] by_elevation;
    }

    [Serializable]
    public class ShipFiringArcsData
    {
        public string method;
        public string accuracy;
        public float clearance_required_m;
        public float increment_deg;
        public string note;
        public ShipFiringArcTurret[] turrets;

        public const string ResourceFolder = "Ships";
        public const string FileName = "firing_arcs.unity.json";

        public static string RelativePath(string shipId) =>
            ResourceFolder + "/" + shipId + "/" + FileName;

        public static ShipFiringArcsData Load(string shipId)
        {
            string resPath = RelativePath(shipId);
            int dot = resPath.LastIndexOf(".json", StringComparison.Ordinal);
            if (dot >= 0) resPath = resPath.Substring(0, dot);
            var asset = Resources.Load<TextAsset>(resPath);
            if (asset == null) return null;
            return Parse(asset.text);
        }

        public static ShipFiringArcsData Parse(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            var data = JsonUtility.FromJson<ShipFiringArcsData>(json);
            return data != null && data.turrets != null ? data : null;
        }

        public ShipFiringArcTurret Turret(string key)
        {
            if (turrets == null || string.IsNullOrEmpty(key)) return null;
            foreach (var t in turrets)
                if (t != null && t.key == key) return t;
            return null;
        }

        /// <summary>
        /// yawCommandDeg / elevationDeg are gameplay command angles relative to rest pose
        /// (same space as ShipTurretController). Uses nearest elevation sample.
        /// </summary>
        public bool IsYawClear(string key, float yawCommandDeg, float elevationDeg)
        {
            var turret = Turret(key);
            if (turret == null || turret.by_elevation == null || turret.by_elevation.Length == 0)
                return true; // no data: do not hard-block prototype control

            var sample = NearestElevation(turret, elevationDeg);
            if (sample == null || sample.intervals == null || sample.intervals.Length == 0)
                return true;

            float yaw = Normalize360(yawCommandDeg);
            foreach (var iv in sample.intervals)
            {
                if (iv == null) continue;
                if (IntervalContains(iv, yaw)) return true;
            }
            return false;
        }

        public static ShipFiringArcElevation NearestElevation(ShipFiringArcTurret turret, float elevationDeg)
        {
            ShipFiringArcElevation best = null;
            float bestDelta = float.MaxValue;
            foreach (var e in turret.by_elevation)
            {
                if (e == null) continue;
                float d = Mathf.Abs(e.elevation_deg - elevationDeg);
                if (d < bestDelta)
                {
                    bestDelta = d;
                    best = e;
                }
            }
            return best;
        }

        public static float Normalize360(float deg)
        {
            float v = deg % 360f;
            if (v < 0f) v += 360f;
            return v;
        }

        /// <summary>Interval [a,b] on the circle; treats b < a as wrap through 0.</summary>
        public static bool IntervalContains(ShipFiringArcInterval iv, float yaw01)
        {
            float a = Normalize360(iv.a);
            float b = Normalize360(iv.b);
            // Prototype slop: geometric scan is conservative and quantised at 5°.
            const float slop = 2.5f;
            if (Mathf.Approximately(a, b)) return true;
            if (a <= b) return yaw01 >= a - slop && yaw01 <= b + slop;
            return yaw01 >= a - slop || yaw01 <= b + slop;
        }
    }
}
