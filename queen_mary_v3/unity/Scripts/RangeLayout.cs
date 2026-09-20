using System;
using System.Collections.Generic;
using UnityEngine;

namespace Naval.DamageLab
{
    /// <summary>
    /// Layout + codex presets for the damage range lab (JSON-friendly for JsonUtility).
    /// Experimental only; historically_certified=false.
    /// </summary>
    [Serializable]
    public sealed class RangePlateDef
    {
        public string id;
        public float x;
        public string display_name;
    }

    [Serializable]
    public sealed class RangeModuleDef
    {
        public string id;
        public float[] center;
        public float[] size;
        public string display_name;
        public string codex_note;
    }

    [Serializable]
    public sealed class RangeCodexPreset
    {
        public string id;
        public string title;
        public string tag;
        public string teach;
        public RangeConfig config;
        public RangeConfig compare_config;
    }

    [Serializable]
    public sealed class RangeLayout
    {
        public string schema = "damage-range-layout-1";
        public bool historically_certified = false;
        public string note;
        public RangePlateDef[] plates;
        public RangeModuleDef[] modules;
        public RangeCodexPreset[] codex_presets;

        public const string FileName = "range_layout.json";

        public static RangeLayout LoadFromResources()
        {
            var ta = Resources.Load<TextAsset>("DamageRange/range_layout");
            if (ta == null) ta = Resources.Load<TextAsset>("Ships/HMS_Queen_Mary_1913/range_layout");
            if (ta == null) return null;
            return JsonUtility.FromJson<RangeLayout>(ta.text);
        }

        public static RangeLayout LoadFromFile(string path)
        {
            if (string.IsNullOrEmpty(path) || !System.IO.File.Exists(path)) return null;
            return JsonUtility.FromJson<RangeLayout>(System.IO.File.ReadAllText(path));
        }

        public List<RangeModule> BuildModules()
        {
            var list = new List<RangeModule>();
            if (modules == null) return list;
            foreach (var m in modules)
            {
                if (m == null || string.IsNullOrEmpty(m.id)) continue;
                var c = m.center != null && m.center.Length >= 3
                    ? new DVec(m.center[0], m.center[1], m.center[2]) : new DVec(0, 0, 0);
                var s = m.size != null && m.size.Length >= 3
                    ? new DVec(m.size[0], m.size[1], m.size[2]) : new DVec(1, 1, 1);
                list.Add(new RangeModule(m.id, c, s));
            }
            return list;
        }

        public RangeCodexPreset FindPreset(string id)
        {
            if (codex_presets == null || string.IsNullOrEmpty(id)) return null;
            foreach (var p in codex_presets) if (p != null && p.id == id) return p;
            return null;
        }
    }
}
