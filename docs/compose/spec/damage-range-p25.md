---
feature: damage-range-p25
status: delivered
updated: 2026-09-20
branch: feature/damage-range-p25
commits: cb55273..HEAD
---

# 试验场 P2.5 · 破片/爆炸/穿板

## Report

**What was built** — RangeSolver P2.5：`plate_transit` 穿板行程事件（可关）；爆炸点分类 `open_space` / `inside_module:ID`，舱内爆对宿主模块 blast bonus（默认 1.8×，上限 0.65）；破片带 `massKg/speedMps/energyJ`，模块破片伤按能量归一×剩余穿深累加；开放爆沿弹道轻度前向偏置。配置扩展 Validate 边界。图鉴 UI 增加「穿板行程」与破片能量摘要。

**Verification** — EditMode **28/28 Passed**（`p25_tests/editmode_p25.xml`），含 `DamageRangeP25Tests` 7 项：穿板有/无、破片质量能量、起爆 locus、舱内爆上限、seed 能量差、事件单调。仍为实验模型，`historically_certified=false`。

**Journey log** — (1) 没有质量/能量的破片无法调参。(2) 舱内/舱外爆炸必须先分类再算 blast。(3) 穿板时间应进入延迟引信，否则延迟语义失真。(4) 结果仍不可直接进主战斗。

## [S1] Problem
破片/爆炸/穿板规则不完整、不可观测。

## [S2] Design
transit + locus + energy-weighted fragments；详见 README_P25规则.md。

## [S3] Out of Scope
主战斗合并、史实校准、CFD/进水。

## Tasks
- [x] T1 Model rules
- [x] T2 View labels + energy line
- [x] T3 EditMode 28/28
- [x] T4 Docs + evidence XML
