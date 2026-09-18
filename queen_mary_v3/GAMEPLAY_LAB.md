# Gameplay Lab · T5–T16 合成

场景：`Assets/Scenes/GameplayLab.unity`（`Tools/Naval/Build gameplay lab` 生成）。

## 布局

| 实例 | 名称 | 位置 | 说明 |
|---|---|---|---|
| 玩家舰 | `HMS_Queen_Mary_1913` | 原点 | 鼠标群炮 + 光标锁定 + **ShipCombatVfx** |
| 靶船 | `HMS_Queen_Mary_1913_Target` | (60, 0, 520) 或运行时补生 | 同模；穿深/进水；命中时渲染器短暂变暗 |

## 操作

| 输入 | 作用 |
|---|---|
| 鼠标左右 | 第三人称视角 + 四塔同罗经方位 |
| 空格/左键 | 齐射；盲区塔 SKIP |
| Esc / 点 Game 窗 | 释放/锁定光标 |
| Tab / R / T / F1 | 相机 / 重置 / 靶船漂移 / 调试 |

## 战斗特效（T16）

| 事件 | 画面 |
|---|---|
| 开火 | 炮口火光粒子 + **弧线曳光**（非激光直线） |
| miss | 弹道末端 **水花** |
| 命中 | **爆炸**（穿透更亮更久）+ 目标舰短暂变暗 |
| 音效 | 占位 `AudioClip` 可空；未指定则只走视觉 |

代码：`ShipCombatVfx.cs`（粒子/Trail 全代码生成）。Unity **无第一方海战材质包**；海面仍为 lab 平面，商店包另任务评估。

## 验收

编译 0 error CS；Play 开火可见炮口闪光与弧线；miss 有水花；hit 有爆炸与 HUD「命中：…」。
