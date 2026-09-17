using System;
using UnityEngine;

namespace Naval
{
    /// <summary>一座主炮塔在层级里的绑定：偏航节点 / 俯仰节点 / 各炮管，以及射界限制。</summary>
    [Serializable]
    public class TurretBinding
    {
        public string key;              // A / B / Q / X
        public string yawNode;          // Turret_A
        public string pitchNode;        // Elevation_A
        public string[] barrels;        // Barrel_A_Port / Barrel_A_Starboard
        public float restYawDeg;
        public float minElevationDeg;
        public float maxElevationDeg;
    }

    /// <summary>
    /// 一种船型的定义（ScriptableObject = 工程里的一份数据资产，可在 Inspector 里引用）。
    ///
    /// 为什么需要它：在它之前，契约是运行时解析的 JSON、预制体是分开的、材质是分开的、
    /// LOD 距离压根没地方写 —— 游戏代码要自己去找齐这些，换一艘船更是无处下手。
    /// ShipDefinition 把它们收拢成一个"船型"，游戏代码只问它。
    ///
    /// 由 Editor 下的 ShipRuntimeBuilder 生成，不要手填。
    /// </summary>
    [CreateAssetMenu(menuName = "Naval/Ship Definition", fileName = "ShipDefinition")]
    public class ShipDefinition : ScriptableObject
    {
        public string shipId;
        public string assetVersion;

        [Tooltip("扁平契约（JsonUtility 可读）")]
        public TextAsset contract;

        [Tooltip("构建出来的运行时预制体：仅碰撞件已关渲染、舱室已挂数据与碰撞体")]
        public GameObject prefab;

        public Material[] materials;

        public float lengthM;
        public float beamM;
        public float draftM;
        public int displacementT;

        public int objectCount;
        public int meshCount;
        public int collisionOnlyCount;
        public int compartmentCount;

        public TurretBinding[] turrets;

        public string builtUtc;

        [TextArea(2, 6)]
        public string notes;

        public TurretBinding Turret(string key)
        {
            if (turrets != null)
                foreach (var t in turrets)
                    if (t != null && t.key == key) return t;
            return null;
        }
    }
}
