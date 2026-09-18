# Gameplay Lab · T5/T6/T7/T9 原型

场景：Unity 工程 `Assets/Scenes/GameplayLab.unity`（由 `Tools/Naval/Build gameplay lab` 生成）。

## 已实现

| 任务 | 组件 | 行为 |
|---|---|---|
| T5 命中进水 | `ShipGunBattery` + `ShipCompartment` + `ShipFloatPrototype` | Space/LMB 从炮管射线（`QueryTriggerInteraction.Collide`）→ 舱室进水 → 吃水/纵倾/横倾原型 |
| T6 炮塔+射界 | `ShipTurretController` + `ShipFiringArcs` + `firing_arcs.unity.json` | 命令角叠加在 rest 旋转上；yaw 落在射界外时禁止开火 |
| T7 相机+LOD | `ShipCameraRig` + HUD | Tab 切换战术（~120 m，lodBias=1）/ 舰队（~1700 m，lodBias=1）；HUD 显示 relH 与估计 LOD |
| T9 穿深 | `ShipPenetration` + `penetration_main.json` + `armour_zones.json` + `ShipSystemsState` | 距离→穿深 vs 区域装甲；穿透按 role 进水并累计系统状态；未穿不进水 |

## 操作

- **Tab**：战术 ↔ 舰队相机  
- **右键拖动**：环绕；**+/-**：拉近拉远  
- **A/Q 炮塔**：方向键（Horizontal/Vertical）转 yaw/pitch  
- **B 炮塔**：I/J/K/L  
- **Space 或左键**：尝试开火（射界门控 + 穿深判定）  
- **R**：组件 ContextMenu `Reset flooding` / 可扩展重置系统状态  

> 控制面是原型：多塔同键会抢输入。验收时可只开一个 `ShipTurretController`。

## 验证

- `verify_firing_arcs_runtime.py` → `firing_arcs_runtime_ok`
- `verify_penetration.py` → `penetration_tables_ok`（主炮 2 km 可穿主带 229 mm，20 km 不可穿；副炮穿不透主带、可穿上层）
- Unity `ShipGameplayLabBuilder.BuildBatch` → OK，**0 error CS**
- **非完整仿真**：浮态近似；穿深为 estimate 曲线、正对近似、无跳弹；射界为保守几何扫描

## 运行

1. Unity 打开 `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval`  
2. 打开 `Assets/Scenes/GameplayLab.unity`  
3. Play  

数据：`Assets/Resources/Ships/HMS_Queen_Mary_1913/penetration_main.json` 与 `armour_zones.json`。

