---
feature: damage-range-sweep
status: delivered
updated: 2026-09-20
branch: feature/damage-range-sweep
commits: 84443b4..HEAD
---

# 损伤试验场全因子扫描测试

## Report

**What was built** — C1–C6 因子扫描（装甲×速度×角度、多层装甲、引信、材料×角度、破片、种子），`DamageRangeSweep`/`Runner`/EditMode 测试；CSV + SUMMARY 产物。方针：**扫描结果不直接用于主战斗数值**，而是暴露试验场模型缺口并迭代模型。

**Verification** — v1 `20260920T064657Z`：C6 锅炉恒 1.0（损伤饱和）。v2：降低 blast 上限后 C1 双舱全毁 0/96，但种子仍无方差。v4 `20260920T065716Z`：破片种子耦合修复后 **MODEL_OK**（C6 损伤和 min=0.337 median=0.712 max=0.900，unique_triples=11）。EditMode **18/18 Passed**（含 Sweep 5 + DamageRange 10 + Penetration 3）。`historically_certified=false`。

**Journey log** — (1) 未调模型前，扫描只能证明「结果不可用」。(2) 损伤饱和会掩盖一切敏感度。(3) 破片 PRNG 必须真正吃 seed。(4) C6 路径擦伤会吞掉破片方差，应隔离「开放起爆」战役。(5) 扫描是完善试验场的手段，不是战斗平衡表。

## [S1] Problem
试验场半成品，缺大范围因子测试；结果易被误用为战斗数值。

## [S2] Design
可复现 C1–C6 扫描 → 模型缺口 findings → 修试验场 → 复扫；明确禁止直接移植 CSV 到 ShipHitResolver。

## [S3] Out of Scope
主战斗契约合并、史实穿深校准、15 舰性能。

## Tasks
- [x] T1 Sweep runner + 批处理输出
- [x] T2 Campaigns C1–C6
- [x] T3 EditMode 18/18
- [x] T4 v1→v4 测中完善模型 + README_扫描完善.md
