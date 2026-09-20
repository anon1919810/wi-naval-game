---
feature: damage-range-sweep
status: designed
updated: 2026-09-20
branch: feature/damage-range-sweep
commits: <base-sha>..<head-sha>
---

# 损伤试验场全因子扫描测试

## Report

## [S1] Problem

试验场已有可玩 UI，但缺少**大范围、可复现**的因子扫描：装甲/速度/角度/引信/材料/破片种子如何影响穿透、起爆与模块损伤，尚无批量 CSV/结论报告。

## [S2] Design

### S2.1 可测因子（RangeConfig）

| 因子 | 字段 | 建议档位 |
|---|---|---|
| 外带装甲 | outerMm | 0 / 90 / 180 / 229 / 300 / 600 |
| 内舱壁 | innerMm | 0 / 25 / 50 / 102 |
| 后舱壁 | rearMm | 0 / 40 / 102 |
| 撞击速度 | speed | 200 / 400 / 600 / 800 m/s |
| 入射角 | angleDeg | 0 / 10 / 20 / 30° |
| 参考穿深 | referencePenMm | 200 / 400 / 600 |
| 材料阻力 | resistance | 0.5 / 1.0 / 1.5 |
| 引信 | fuseMode + fuseDelay | Contact/Delay/Dud × 0–0.03 s |
| 破片样本 | fragmentSamples + seed | 16–512 × 多种子 |

### S2.2 扫描战役（控制规模，非暴力全笛卡尔）

| Campaign | 组合 | 目的 |
|---|---|---|
| C1 装甲×速度×角度 | outer × speed × angle | 主穿深趋势、停弹/穿透边界 |
| C2 多层装甲 | outer×inner×rear | 三层预算与模块进弹 |
| C3 引信 | mode × delay × outer | 起爆位置与模块损伤 |
| C4 材料×角度 | resistance × angle × outer | 等效厚度敏感度 |
| C5 破片稳定性 | samples × blast × seeds | 权重归一与损伤方差 |
| C6 种子复现 | 同配置多种子 | Signature 一致性 |

每发记录：配置、`stopped/exploded`、`finalSpeed`、事件摘要、各模块 damage/state、破片命中分布。

### S2.3 产物

- `DamageRangeSweep.cs`：纯逻辑网格 + Editor 菜单 + `RunBatch`
- 输出：`damage_range/sweeps/<runId>/` → `campaigns.csv`、`summary.json`、`SUMMARY.md`
- EditMode：`DamageRangeSweepTests.cs`（单调性/边界/复现）
- 口径：实验代理，`historically_certified=false`；耗时非游戏 FPS

## [S3] Out of Scope

替换 ShipHitResolver、史实校准、15 舰性能、完整弹道。

## Tasks

- [ ] T1 Sweep 数据结构 + 批量 Runner — acceptance: 批处理写出 CSV/JSON
- [ ] T2 Campaigns C1–C6 — acceptance: 每战役行数与档位符合设计
- [ ] T3 回归断言测试 — acceptance: EditMode 断言通过
- [ ] T4 跑通 Unity 扫描并写 SUMMARY 结论 — acceptance: 真实 runId 证据入库
