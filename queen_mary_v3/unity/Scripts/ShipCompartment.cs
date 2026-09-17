using UnityEngine;

namespace Naval
{
    /// <summary>
    /// 挂在损伤舱室（锅炉舱 / 轮机舱 / 弹药库）上的运行时数据。
    ///
    /// 存在的理由：`damage_model.json` 与 `buoyancy_compartments.json` 里已经有体积、
    /// 渗透率、可进水体积——但那只是数字。要回答"这一炮打中了哪个舱、进不进水"，
    /// 世界里得有个**挂了这些数据的对象**可以测。这个组件就是把数据钉到对象上。
    ///
    /// 碰撞体在构建时生成（见 ShipRuntimeBuilder），默认做成 **trigger**：
    /// 每艘船二十多个舱室，如果是实体碰撞体，船与船之间会互相卡住。
    /// 射线检测时记得传 QueryTriggerInteraction.Collide。
    /// </summary>
    [AddComponentMenu("Naval/Ship Compartment")]
    public sealed class ShipCompartment : MonoBehaviour
    {
        public string compartmentId;
        public string role;

        [Tooltip("来自 buoyancy_compartments.json 的舱室体积（立方米）")]
        public float volumeM3;

        [Tooltip("渗透率：0 表示完全挡水，0.8 表示八成体积会进水")]
        public float permeability;

        [Tooltip("可进水体积 = 体积 × 渗透率")]
        public float floodableVolumeM3;

        [Tooltip("形心是否在设计水线（y = 0）以下 —— 决定这一舱破了会不会进水")]
        public bool belowWaterline;

        [Tooltip("是否用了 buoyancy_compartments.json 里的真实数据；false 表示只填了包围盒估算值")]
        public bool dataFromBuoyancyFile;

        [Range(0f, 1f), Tooltip("当前进水比例，0 = 完整，1 = 灌满可进水体积")]
        public float floodFraction;

        /// <summary>当前已进水的体积（立方米）。</summary>
        public float FloodedVolumeM3 => floodableVolumeM3 * floodFraction;

        /// <summary>命中这个舱室时按给定伤害增加进水量（伤害以立方米计）。</summary>
        public void Flood(float volumeM3)
        {
            if (floodableVolumeM3 <= 0f) return;
            floodFraction = Mathf.Clamp01(floodFraction + volumeM3 / floodableVolumeM3);
        }
    }
}
