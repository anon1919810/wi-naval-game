---
feature: damage-range-p0
status: delivered
updated: 2026-09-20
branch: master
commits: 77c7ab1..HEAD
---

# DamageRange P0 验收与入库

## Report

**What was built** — 独立损伤试验场：`RangeSolver`（穿透预算、三层装甲、引信、爆炸/破片代理）、`DamageRangeView` 剖视 UI/回放/JSON 导出、`DamageRangeBuilder` 场景与播放器批处理、EditMode 测试与 `damage_range/` 离线证据。与 GameplayLab 主战斗分离；`historically_certified: false`。

**Verification** — Unity `DamageRangeBuilder.BuildBatch`：`build_result.txt` **Succeeded errors=0**；`QueenMaryDamageRange.exe` 已生成；`solver_benchmark.txt` 200 次串行求解。EditMode **13/13 Passed**（含 DamageRangeTests 10 + 既有 PenetrationDataTests 3），XML：`queen_mary_v3/damage_range/unity_acceptance/editmode_damagerange.xml`。求解器离线：`solver_verification.json` 10/10 + RangeChecks 19/19。

**Journey log** — (1) 试验场不可替代主战斗结算器。(2) 视觉板厚与计算厚度分离。(3) `unityRuntimeVerified` 在旧 JSON 为 false，本轮批处理+Test Runner 已补证。(4) OpenOnLoad 会尝试自动打开场景，可删文件只留菜单。

## [S1] Problem
Damage Range 源码与求解器已完成，但缺 Unity 批处理/测试证据且文件未入库。

## [S2] Design
见 `交接_损伤试验场_2026-09-20.md` 与 `queen_mary_v3/damage_range/README_损伤试验场.md`。

## [S3] Out of Scope
主战斗契约接入、B 阶段弹道、史实装甲认证。

## Tasks
- [x] T1 Sync DamageRange scripts into Unity
- [x] T2 BuildBatch scene + player — Succeeded
- [x] T3 EditMode DamageRangeTests — 13/13 XML
- [x] T4 Commit sources, evidence, handover, README
