---
feature: v4-unity-accept-replace
status: delivered
updated: 2026-09-19
branch: feature/v4-accept-replace
commits: 46b3fdc..HEAD
---

# v4 Unity 验收与灰盒替换

## Report

**What was built** — ① `queen_mary_v4` 增加 **Gameplay FBX**（外观+损伤/装甲代理），Exterior 仍为展示用纯外观以通过 42/42 独立验证。② Unity 批处理 `ShipV4Acceptance`：13/13 通过（节点/8 炮口/尺度/艏向 +Z/逻辑模块名/材质槽）。③ `ShipRuntimeBuilder` 优先加载 v4 Gameplay FBX 合成原 Prefab 路径；LOD 合并改用 UInt32 索引以支持 ~8 万三角。④ GameplayLab 重建成功，含 v4 外观、14 舱室碰撞、炮塔链 LOD。

**Verification** — `rebuild_v4.ps1 -SkipRender` 独立验证 42/42；`v4_unity_acceptance.json` **passed 13/13**；`ship_runtime_build.json` **passed**（24 关渲染 / 25 碰撞 / 14 舱室，LOD0 81,688 三角）；Lab `BuildBatch` OK，0 error CS。`unity_runtime_tested` 人机目视 Play 仍建议用户确认材质观感。

**Journey log** — (1) Exterior 展示 FBX 不含代理会卡死运行时构建。(2) 应用与展示分文件：Gameplay vs Exterior。(3) 整舰包围盒高度含桅杆 ~50 m，不是船体高 15 m。(4) v4 面数使 LOD 合并必须 UInt32。(5) 回退：删 v4 Gameplay FBX 或改 builder 契约路径即可回 v3。

## [S1] Problem

v4 未 Unity 验收；Lab 仍用 v3 灰盒。

## [S2] Design

- 验收批处理 + 报告 JSON；全绿才换运行时 FBX
- `QueenMary_v4_Gameplay.fbx` = exterior visuals + 03/04 代理
- Builder 优先 v4；缺文件回退契约 v3
- GunBattery 炮口起点优先 `Muzzle_*`
- v3 资产保留

## [S3] Out of Scope

A 阶段战斗正确性、v4 专属 LOD 重调、Interior 作碰撞真值。

## Tasks

- [x] T1 sync_v4 + 资源目录
- [x] T2 ShipV4Acceptance 13/13
- [x] T3 材质槽名对齐 Naval（报告非 URP 槽）
- [x] T4 Prefab/Lab 改 v4 + Muzzle 开火起点 + LOD UInt32
- [x] T5 GAMEPLAY_LAB / 本 spec 说明
