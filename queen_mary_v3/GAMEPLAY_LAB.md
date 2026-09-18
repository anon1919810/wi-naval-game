# Gameplay Lab · T5–T12 合成

场景：`Assets/Scenes/GameplayLab.unity`（`Tools/Naval/Build gameplay lab` 生成）。

## 布局

| 实例 | 名称 | 位置 | 说明 |
|---|---|---|---|
| 玩家舰 | `HMS_Queen_Mary_1913` | 原点 | 鼠标群炮 + 光标锁定 |
| 靶船 | `HMS_Queen_Mary_1913_Target` | **(60, 0, 520)**，约 190° | 同模；默认第三人称沿舰艏即可看见 |

## 操作

| 输入 | 作用 |
|---|---|
| **鼠标左右** | 第三人称视角绕船心转 + 四塔同罗经方位 |
| **鼠标上下** | 炮管俯仰 |
| **右键+上下** | 第三人称俯仰微调（不转炮） |
| **Space / 左键** | 齐射；射界盲区塔 SKIP |
| **Esc** | 解锁光标 |
| **点击 Game 视图** | 重新锁定光标（该次点击不开火） |
| **Tab** | 第三人称 → 战术 → 舰队 |
| **R** | 重置玩家+靶船 |
| **T** | 靶船慢速直航开关 |
| **F1** | 调试 HUD |

## 实现

- `ShipMouseGroupAim`：`yawCommand = worldAimYaw − rest_yaw`；`FireAllClear`
- `ShipCameraRig` ShipThirdPerson：相机随 aim 方位绕船心；Start 自动接 `aim`
- `ShipTargetShip` / Label / Battery（返击默认关）
- 穿深：`penetration_main.json` + `armour_zones.json`

## 验收

Unity 重建 Lab 后 Play：锁鼠标 → 转方位打靶船 → TARGET 进水/`Penetrated` → 盲区塔 SKIP。
