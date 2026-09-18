# Gameplay Lab · T5/T6/T7/T9/T10 原型

场景：Unity 工程 `Assets/Scenes/GameplayLab.unity`（由 `Tools/Naval/Build gameplay lab` 生成）。

## 已实现

| 任务 | 组件 | 行为 |
|---|---|---|
| T5 命中进水 | `ShipGunBattery` + `ShipCompartment` + `ShipFloatPrototype` | Space/LMB 射线 → 舱室进水 → 吃水/纵倾原型 |
| T6 炮塔+射界 | `ShipTurretController` + `ShipFiringArcs` | rest 上叠加命令角；射界外禁止开火 |
| T7 相机+LOD | `ShipCameraRig` + HUD | Tab 战术/舰队；显示 relH 与估计 LOD |
| T9 穿深 | `ShipPenetration` + JSON 表 + `ShipSystemsState` | 距离→穿深 vs 装甲；穿透才进水并累计系统 |
| T10 操作壳 | `ShipAimUI` + `ShipTurretSelector` + `ShipInputShell` | 准星、仅选中塔吃输入、重置、命令条 |

## 操作（无需 Inspector）

| 键 | 作用 |
|---|---|
| **1 / 2 / 3 / 4** | 选中炮塔 A / B / Q / X（仅选中塔接受瞄准与开火） |
| **[ / ]** | 循环切换炮塔 |
| **方向键** | 选中塔 yaw/pitch |
| **Space / 左键** | 开火（射界 + 穿深判定） |
| **Tab** | 战术 ↔ 舰队相机 |
| **右键拖动** | 环绕相机；**+/-** 缩放 |
| **R** | 重置进水 + 系统状态 |
| **F1** | 显示/隐藏左上调试 HUD |

屏幕中央：准星 + 当前塔 ARC CLEAR/BLOCKED；右上：相机/浮态/系统/最后命中；底部：命令条。

## 验证

- `verify_penetration.py` / `verify_firing_arcs_runtime.py`
- Unity `ShipGameplayLabBuilder.BuildBatch` 编译与场景生成
- **非完整仿真**：穿深 estimate、正对近似；无装填/弹药；无 AI

## 运行

1. 打开 `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval`
2. 打开 `Assets/Scenes/GameplayLab.unity`
3. Play：按 **1** 选 A 塔 → 方向键瞄准 → **Space** 开火 → 看准星下方 ARC 与右上命中/系统状态
