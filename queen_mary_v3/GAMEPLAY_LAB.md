# Gameplay Lab · 鼠标群炮塔控制（T12）

场景：`Assets/Scenes/GameplayLab.unity`

## 操作（本分支）

| 输入 | 作用 |
|---|---|
| **鼠标移动** | **同时驱动 A/B/Q/X 四座主炮塔**（相同 yaw/pitch 命令） |
| **Space / 左键** | **齐射**：仅对射界 CLEAR 的塔开火；盲区塔自动跳过（显示 SKIP） |
| **右键拖动** | 环绕相机（此时**不**转炮塔） |
| **Tab** | 战术 / 舰队相机 |
| **R** | 重置进水与系统 |
| **F1** | 调试 HUD |

准星下方显示：`Turrets ALL · A✓ B✓ Q✗ X✓`（✗ = 射击盲区，开火时跳过）。

## 实现要点

- `ShipMouseGroupAim`：鼠标增量写入所有 `ShipTurretController.yawCommandDeg/pitchCommandDeg`
- `ShipTurretController`：`useIndividualKeys=false`、`acceptFireKey=false`（不再单塔抢输入）
- `FireAllClear()`：`ArcClear` 为 false 的塔只记 `SKIP`，不调用 `TryFire`
- 射界数据仍来自 `firing_arcs.unity.json`（保守几何扫描）

## 验证

Unity `ShipGameplayLabBuilder.BuildBatch` 应输出 OK 且 **0 error CS**，并在场景中挂上 `ShipMouseGroupAim`。
