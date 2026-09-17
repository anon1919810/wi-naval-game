using System;
using System.IO;
using UnityEngine;

namespace Naval
{
    /// <summary>
    /// 单座主炮塔的契约数据。字段名与 ship_contract.unity.json 的键**逐字一致** —— 这是硬要求，
    /// JsonUtility 只认字段名，改字段名就等于改契约。
    /// 坐标系约定（在 Unity 侧成立，已由 ShipAssetValidator 实测断言）：
    ///   X = 右舷为正，Y = 向上为正，Z = 舰艏为正，Y = 0 即设计水线。
    /// </summary>
    [Serializable]
    public class ShipTurret
    {
        public string key;          // "A" / "B" / "Q" / "X"
        public string turret;       // 偏航节点名，例如 Turret_A
        public string pivot;        // 俯仰节点名，例如 Elevation_A
        public string barbette;     // 炮座固定件名，例如 Barbette_A
        public string[] barrels;    // 两根炮管，各自可独立命名/独立伤害
        public float base_z_m;      // 炮座甲板高度（甲板为 y）
        public float rest_yaw_deg;  // 静置偏航：A/B 为 0（朝艏），Q/X 为 180（朝艉）
        public float trunnion_local_y_m;   // 耳轴在炮塔内的局部纵向位置
        public float barrel_end_local_y_m; // 炮口在炮管局部纵向轴上的位置
        public float turret_height_m;
        public float min_elevation_deg;            // 炮架机械下限
        public float max_elevation_deg;            // 炮架机械上限
        public float director_elevation_limit_deg; // 1913 年指挥仪实际限制（棱镜 1916 年才装）
    }

    [Serializable]
    public class ShipSecondaryGun
    {
        public string name;      // Casemate_Port_1 …
        public string side;      // Port / Starboard
        public float axis_z_m;   // 炮口枢轴高度（水线以上为正）
    }

    /// <summary>ship_contract.json 里 module_names_by_role 是字典，JsonUtility 读不了，故拍平成数组。</summary>
    [Serializable]
    public class ShipModuleRole
    {
        public string role;
        public string[] names;
    }

    [Serializable]
    public class ShipFileRef
    {
        public string key;
        public string path;
    }

    /// <summary>
    /// 材质规格。色值是**线性**的 —— Blender 的 Base Color 与 URP 的 _BaseColor 都是线性值，
    /// 所以直接搬运、不做 sRGB 转换。这张表来自 Blender 的 MATERIAL_SPECS，不要在 C# 里另抄一份。
    /// </summary>
    [Serializable]
    public class ShipMaterialSpec
    {
        public string name;
        public float[] base_color;   // 线性 RGB，长度 3
        public float roughness;
        public float metallic;
    }

    /// <summary>
    /// 资产契约。它是 Unity 侧唯一的字段来源 —— 不要手抄字段、不要另行硬编码尺度。
    /// 运行时：ShipContractData.Load("HMS_Queen_Mary_1913")
    /// </summary>
    [Serializable]
    public class ShipContractData
    {
        public string ship_id;
        public string asset_version;
        public string configuration;
        public bool historically_certified;   // 灰盒 = false。别把 false 当成"已考证"。
        public float length_m;
        public float beam_m;
        public float draft_m;
        public float main_deck_z_m;
        public float forecastle_z_m;
        public int main_gun_calibre_mm;
        public int secondary_gun_calibre_mm;
        public float speed_knots;
        public int boilers;
        public int boiler_rooms;
        public int shafts;
        public int torpedo_tubes;
        public int object_count;
        public int mesh_count;
        public string offsets_source;         // builtin_estimate = 型值仍是估算，等图纸
        public string casemate_placement;     // between_decks / forecastle_deck
        public ShipTurret[] turrets;
        public ShipSecondaryGun[] secondary_guns;
        public ShipMaterialSpec[] materials;
        public ShipModuleRole[] module_roles;
        public ShipFileRef[] file_refs;
        public string[] notes;
        public string unity_note;

        public const string Folder = "Ships";

        public static string RelativePath(string shipId) =>
            Folder + "/" + shipId + "/ship_contract.unity.json";

        /// <summary>运行时加载（文件需位于 Assets/Resources/ 下）。</summary>
        public static ShipContractData Load(string shipId)
        {
            string resPath = RelativePath(shipId);
            int dot = resPath.LastIndexOf(".json", StringComparison.Ordinal);
            if (dot >= 0) resPath = resPath.Substring(0, dot);
            var asset = Resources.Load<TextAsset>(resPath);
            if (asset == null)
                throw new FileNotFoundException("找不到契约：" + resPath +
                    "（请确认 json 已放在 Assets/Resources/Ships/ 下并被 Unity 导入）");
            return Parse(asset.text, resPath);
        }

        public static ShipContractData Parse(string json, string label = "契约")
        {
            var data = JsonUtility.FromJson<ShipContractData>(json);
            if (data == null || string.IsNullOrEmpty(data.ship_id))
                throw new InvalidDataException(label + " 解析失败：ship_id 为空");
            return data;
        }

        public ShipTurret Turret(string key)
        {
            foreach (var t in turrets) if (t.key == key) return t;
            throw new ArgumentException("契约里没有 " + key + " 炮塔");
        }

        public string[] ModuleNames(string role)
        {
            foreach (var r in module_roles) if (r.role == role) return r.names;
            return Array.Empty<string>();
        }

        /// <summary>炮塔的偏航节点 transform 路径，供战斗系统按名装配。</summary>
        public string TurretNode(string key) => Turret(key).turret;
        public string PivotNode(string key) => Turret(key).pivot;
    }
}
