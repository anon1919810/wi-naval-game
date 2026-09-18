# Gameplay Lab · T5–T11 原型

场景：`Assets/Scenes/GameplayLab.unity`（`Tools/Naval/Build gameplay lab` 生成）。

## 布局（T11）

| 实例 | 名称 | 位置 | 说明 |
|---|---|---|---|
| 玩家舰 | `HMS_Queen_Mary_1913` | 原点 | 可选塔开火 |
| 靶船 | `HMS_Queen_Mary_1913_Target` | (420, 0, 280)，朝向约 210° | **同一预制体**；炮塔输入全关；穿深/进水算在这艘船上 |

## 操作

| 键 | 作用 |
|---|---|
| **1–4 / [ ]** | 选炮塔 A/B/Q/X |
| **方向键** | 瞄准选中塔 |
| **Space / 左键** | 开火（射界门控 + 穿深 → 目标舰舱室） |
| **Tab** | 战术 / 舰队相机（舰队会框住两舰） |
| **右键 / +−** | 环绕 / 缩放 |
| **R** | 重置玩家+靶船进水与系统 |
| **T** | 靶船慢速直航开关（约 6 m/s 沿舰艏 +Z） |
| **F1** | 调试 HUD |

屏幕：中央准星与 ARC；右上 **You / TARGET** 状态；靶船上方黄字标签。

## 玩法循环

1. Play → 默认 A 塔  
2. 转向靶船方向（侧向约数百米）  
3. Space 开火 → `Last hit` 看 `Penetrated` / `NoPenetration`  
4. TARGET 行观察靶船进水与系统损伤  
5. Tab 拉远看两舰剪影与 LOD  

## 已实现对照

| 任务 | 要点 |
|---|---|
| T5–T7 | 进水原型、炮塔+射界、相机+LOD |
| T9 | 穿深表 vs 装甲，穿透才进水 + `ShipSystemsState` |
| T10 | 准星、炮塔选择、输入壳 |
| T11 | 同模靶船、标签、双船重置、可选漂移 |

## 验证

- 离线：`verify_penetration.py`、`verify_firing_arcs_runtime.py`
- Unity：`ShipGameplayLabBuilder.BuildBatch` 场景含 **player + target**
- 非完整仿真：无智能 AI（`ShipTargetBattery` 默认关）、无装填、穿深为 estimate

## 靶船返击（可选）

靶船上有 `ShipTargetBattery`：`enabledFire=true` 时按间隔用 X 塔向玩家方向打一轮。默认关闭。
