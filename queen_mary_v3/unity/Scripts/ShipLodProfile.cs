using System;
using System.IO;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// One camera/scenario LOD authoring profile. Field names match lod_profiles.json
    /// for JsonUtility. screenHeights are LOD.screenRelativeTransitionHeight values.
    /// </summary>
    [Serializable]
    public class ShipLodExpectedAt
    {
        public float distance_m;
        public float fov_deg;
        public int expectedLod;
    }

    [Serializable]
    public class ShipLodProfile
    {
        public string id;
        public string description;
        public float[] screenHeights;
        public float recommendedLodBias;
        public ShipLodExpectedAt[] expectedAt;

        public float[] ScreenHeightsOrFallback()
        {
            if (screenHeights != null && screenHeights.Length >= 4)
            {
                var copy = new float[4];
                Array.Copy(screenHeights, copy, 4);
                return copy;
            }
            return DefaultHeights();
        }

        public static float[] DefaultHeights()
        {
            // Legacy defaults retained only if lod_profiles.json is missing.
            return new[] { 0.20f, 0.08f, 0.03f, 0.01f };
        }
    }

    [Serializable]
    public class ShipLodProfiles
    {
        public string ship_id;
        public string default_profile;
        public string formula;
        public string[] notes;
        public ShipLodProfile[] profiles;

        public const string FileName = "lod_profiles.json";
        public const string ResourceFolder = "Ships";

        public static string RelativePath(string shipId)
        {
            return ResourceFolder + "/" + shipId + "/" + FileName;
        }

        public static ShipLodProfiles Load(string shipId)
        {
            string resPath = RelativePath(shipId);
            int dot = resPath.LastIndexOf(".json", StringComparison.Ordinal);
            if (dot >= 0) resPath = resPath.Substring(0, dot);
            var asset = Resources.Load<TextAsset>(resPath);
            if (asset == null) return null;
            return Parse(asset.text);
        }

        public static ShipLodProfiles Parse(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            var data = JsonUtility.FromJson<ShipLodProfiles>(json);
            return data != null && data.profiles != null && data.profiles.Length > 0 ? data : null;
        }

        public ShipLodProfile Find(string id)
        {
            if (profiles == null) return null;
            foreach (var p in profiles)
                if (p != null && p.id == id) return p;
            return null;
        }

        /// <summary>Resolve requested profile id, else default_profile, else first entry.</summary>
        public ShipLodProfile Resolve(string requestedId)
        {
            if (!string.IsNullOrEmpty(requestedId))
            {
                var hit = Find(requestedId);
                if (hit != null) return hit;
            }
            if (!string.IsNullOrEmpty(default_profile))
            {
                var def = Find(default_profile);
                if (def != null) return def;
            }
            return profiles != null && profiles.Length > 0 ? profiles[0] : null;
        }

        /// <summary>
        /// relH = size * lodBias / (2 * d * tan(fov/2)). Same convention as ShipFleetBenchmark.
        /// </summary>
        public static float RelativeHeight(float lodGroupSize, float lodBias, float distanceM, float fovDeg)
        {
            if (distanceM <= 0f) return 0f;
            return lodGroupSize * lodBias /
                   (2f * distanceM * Mathf.Tan(fovDeg * 0.5f * Mathf.Deg2Rad));
        }

        public static int LevelFromRelative(float relH, float[] screenHeights)
        {
            if (screenHeights == null) return 0;
            for (int i = 0; i < screenHeights.Length; i++)
                if (relH >= screenHeights[i]) return i;
            return screenHeights.Length;
        }
    }
}
