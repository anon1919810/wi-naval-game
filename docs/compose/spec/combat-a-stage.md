---
feature: combat-a-stage
status: in-progress
updated: 2026-09-19
branch: feature/combat-a-stage
commits: fdae103..HEAD
---

# 战斗正确性 A 阶段

## Report

## [S1] Problem
Lab 战斗缺少实例身份、目标归属、分层命中与可执行 C# 测试；进水可能改航行根节点。

## [S2] Design
对齐 `2026-09-19-queen-mary-combat-correctness.md` A01–A05：asmdef+测试、`ShipIdentity`/`ShipDamageApplication`、`EffectiveArmourMm`/`ShipHitResolver`、`ApplyModule` 去重、`FloatPose`、`ShipCombatAcceptance`/`SmokeRunner`。射线模式保留并标注为原型。

## [S3] Out of Scope
B 阶段飞行弹道、完整 DOTS/AI、史实认证。

## Tasks
- [x] T1 A01 asmdef + tests + verify_combat.ps1 — (covers: plan A01)
- [x] T2 A02 identity + damage application — (covers: A02)
- [x] T3 A03 armour incidence + hit resolver — (covers: A03)
- [x] T4 A04 module dedup + FloatPose — (covers: A04)
- [x] T5 A05 smoke + player builder entry — (covers: A05)
- [ ] T6 Run verify_combat EditMode/PlayMode XML green — blocked until Unity editor closed (covers: A01 exit)
- [ ] T7 Standalone player smoke JSON — after T6 (covers: A05)
