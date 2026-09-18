---
feature: combat-vfx
status: designed
updated: 2026-09-19
branch: feature/t16-combat-vfx
commits: <base-sha>..<head-sha>
---

# 战斗 VFX 可读性（T16）

## Report

## [S1] Problem

灰盒 lab 里开火只有一条短直线曳光，像激光；无炮口闪光、无水花/爆炸、损伤只有文字。玩家看不出「谁开火、打在哪、伤多重」。是否必须完整建模：否——缺的是特效层。

## [S2] Design

### S2.1 视觉分层（L1–L3）

| 层 | 行为 | 挂点 |
|---|---|---|
| L1 弹道 | 从炮口到落点的**弧线曳光**（TrailRenderer 或多段 Line），颜色暖黄，寿命 0.25–0.6 s | `ShipGunBattery.FireBarrel` 命中/未命中路径 |
| L1 水花 | 未命中或近失：落点白色/淡蓝粒子柱，寿命 ~1 s | 未命中 `end` 点 |
| L1 命中爆炸 | 穿透/击中：橙红爆闪 + 短烟，尺度随 range 略缩放 | 命中 `best.point` |
| L2 炮口 | 开火瞬间炮口火光 + 少量烟，每根炮管一次 | `barrel.position` 沿射击方向 |
| L3 损伤可视 | 靶船 `ShipTargetShip`/`ShipFloatPrototype`/`ShipSystemsState` 驱动：进水→船体本地下沉已有；HUD 命中结果加粗色；可选舰体材质变暗（Renderer 拉暗） | AimUI / 靶船 Renderer |

### S2.2 实现契约

- 新文件：`queen_mary_v3/unity/Scripts/ShipCombatVfx.cs`
  - `static ShipCombatVfx Instance` 或 `FindObjectOfType`；`EnsureOn(GameObject ship)`
  - API：`PlayMuzzle(Vector3 origin, Vector3 dir)`、`PlayTracer(Vector3 a, Vector3 b, bool hit)`、`PlayImpact(Vector3 p, ShipPenOutcome outcome)`、`PlaySplash(Vector3 p)`
  - 粒子/Trail **代码生成**（URP Unlit/简单颜色），无商店资源
  - 占位音：`AudioSource.PlayOneShot`；`AudioClip fireClip/hitClip/splashClip` 可空；空则不播并记日志一次
- `ShipGunBattery` 在 SpawnTracer 后调用 VFX；`ResolveFireDirection` 结果作为弹道方向
- `ShipGameplayLabBuilder` 在玩家舰与靶船上 `Ensure`
- **不改** Blender 网格 / 装甲几何

### S2.3 可读性规格（可验收）

| 事件 | 玩家应看到 |
|---|---|
| 齐射且有 CLEAR 塔 | 至少一处炮口闪光；多条弧线飞出 |
| miss | 弹道末端水花 |
| struck / partial / penetrated | 命中点爆炸色不同（穿透更亮更久） |
| 靶船被穿透 | 右上 `命中：…` + 靶船 Status 变化；可选船体变暗 |

### S2.4 海战材质包

Unity **无第一方「海战专用材质包」**；Asset Store 有第三方海面/军舰/VFX 包。本轮**不引入商店包**；海面仍用 lab 蓝色平面。若后续要真实海面，单独任务评估 Crest/KWS 等与 URP 14 兼容性。

## [S3] Out of Scope

- 完整高模舰船、PBR 贴图
- 真实弹道认证 / 爆风
- 资产商店依赖
- 联机特效同步
- 复杂音效设计（仅占位）

## Tasks

- [x] T1: `ShipCombatVfx.cs` 粒子/曳光/音效占位 API — acceptance: 类可编译；Ensure 后场上有 VFX 根节点 (covers: S2.2)
- [x] T2: `ShipGunBattery` 接入 muzzle/tracer/impact/splash — acceptance: 开火时代码路径调用 VFX；miss→splash，hit→impact (covers: S2.1, S2.3)
- [x] T3: LabBuilder 两舰挂 VFX + AimUI/靶船损伤提示 — acceptance: 构建场景含 VFX；HUD 显示命中结果 (covers: S2.1, S2.3)
- [ ] T4: Unity 编译 + 文档 — acceptance: 0 error CS；`GAMEPLAY_LAB.md` 更新操作/特效说明 (covers: S2.4; depends: T1-T3)
