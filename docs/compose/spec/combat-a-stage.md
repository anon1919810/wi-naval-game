---
feature: combat-a-stage
status: delivered
updated: 2026-09-19
branch: feature/combat-a-stage
commits: fdae103..HEAD
---

# 战斗正确性 A 阶段

## Report

**What was built** — A01–A05 落地：`Naval.Runtime` + Edit/Play 测试与 `verify_combat.ps1`；`ShipIdentity`/`ShipDamageApplication` 保证伤害只作用命中舰实例；`EffectiveArmourMm` 与 `ShipHitResolver` 分层预算；`ApplyModule` 模块去重；`FloatPose` 分离浮态与航行根；`ShipCombatAcceptance` 可构建 Windows 播放器。射击仍为**即时射线原型**（标明限制，B 阶段再上弹道）。

**Verification** — EditMode **3/3 Passed**（穿深表插值、斜角装甲、分层预算）；PlayMode **5/5 Passed**（舱室容量、伤害归属、无身份失败、模块去重、浮态不改航行根）。播放器构建 **Succeeded errors=0** → `runtime_acceptance/combat_a/player/player/QueenMaryCombatLab.exe`。场景含 `player_01`+`target_01`。独立播放器 smoke 自动跑默认关闭（`autoRunOnStart=false`），人工 Play 已确认 Lab 可玩。

**Journey log** — (1) 测试脚本缺 `using UnityEngine` 会把工程打进 Safe Mode。(2) `Debug.LogError` 会让 PlayMode 测试失败，需 `LogAssert.Expect`。(3) `Apply` 在目标缺 `ShipSystemsState` 时返回 false，测试必须挂齐组件。(4) 损伤代理可进 Exterior/Gameplay FBX，展示 Exterior 保持纯外观。(5) Unity 批处理在 Package Manager/许可异常时无 XML，先修编译与包解析再跑测试。

## [S1] Problem
无身份/分层命中/浮态分离与可执行 C# 战斗测试。

## [S2] Design
见 `queen_mary_v3/docs/combat_acceptance.md` 与计划 A01–A05。

## [S3] Out of Scope
B 弹道、完整稳性、舰队 AI、史实认证。

## Tasks
- [x] T1–T5 A01–A05 实现
- [x] T6 EditMode 3/3 + PlayMode 5/5
- [x] T7 独立播放器构建 Succeeded（smoke 运行时默认关，人工 Lab 已验证）
