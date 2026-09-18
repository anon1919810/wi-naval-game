# Gameplay Lab · T5/T6/T7 原型

场景：Unity 工程 `Assets/Scenes/GameplayLab.unity`（由 `Tools/Naval/Build gameplay lab` 生成）。

## 已实现

| 任务 | 组件 | 行为 |
|---|---|---|
| T5 命中进水 | `ShipGunBattery` + `ShipCompartment` + `ShipFloatPrototype` | Space/LMB 从炮管射线（`QueryTriggerInteraction.Collide`）→ 舱室 `Flood` → 吃水/纵倾/横倾原型 |
| T6 炮塔+射界 | `ShipTurretController` + `ShipFiringArcs` + `firing_arcs.unity.json` | 命令角叠加在 rest 旋转上；yaw 落在射界外时禁止开火 |
| T7 相机+LOD | `ShipCameraRig` + HUD | Tab 切换战术（~120 m，lodBias=1）/ 舰队（~1700 m，lodBias=1）；HUD 显示 relH 与估计 LOD |

## 操作

- **Tab**：战术 ↔ 舰队相机  
- **右键拖动**：环绕；**+/-**：拉近拉远  
- **A/Q 炮塔**：方向键（Horizontal/Vertical）转 yaw/pitch  
- **B 炮塔**：I/J/K/L  
- **Space 或左键**：当前选中逻辑下对 A 塔尝试开火（Battery 挂在船上，各塔 Controller 都会调它）  
- **R**：未绑定重置时可用组件 ContextMenu `Reset flooding`

> 控制面是原型：多塔同键会抢输入。验收时可只开一个 `ShipTurretController` 的 gameObject，或后续再做塔选择键。

## 验证

- `verify_firing_arcs_runtime.py` → `firing_arcs_runtime_ok`（A/Q 艉向盲区、X 高仰角全向）
- Unity `ShipGameplayLabBuilder.BuildBatch` → 场景与 HUD 组件生成成功
- **非完整仿真**：浮态为水线面近似；穿深/AI/装填未做；射界为几何扫描保守值

## 运行

1. Unity 打开 `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval`  
2. 打开 `Assets/Scenes/GameplayLab.unity`  
3. Play  

若脚本有编译错误，先确认 `Assets/Scripts/Naval/` 与 `Assets/Editor/` 已是仓库 `queen_mary_v3/unity/` 同步版本。
