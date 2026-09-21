---
feature: plimsoll-damage-loop
status: delivered
updated: 2026-09-21
branch: feature/plimsoll-damage-loop
commits: cc266fe..0f48727
---

# Plimsoll 长任务 · 破损稳性闭环 + 工程化收口

## Report

**What was built** — 在 master（2.2+FSC+4.1，`cc266fe`）之上完成破损稳性闭环与工程收口：`damage.solve_flooded_equilibrium`（4.1 组合 + 2.2 纵倾平衡；KM≈upright(d) 标 estimate；小角度横倾）；`remaining_gz_curve`（**FSC 只计一次**：kg_eff 路径禁止再传 tanks，双计抛错；键名映射 `flood_tanks_to_fs_tanks`）；三场景 `run_damage_scenarios.py` 落盘可复现；`integrate()["trace"]`；`plimsoll` 包入口（path bootstrap + 可调用 API）；`run_all_tests.py` 一键回归。

**Verification** —
- `test_damage_loop.py`：**11/11**（浮态自洽、艏倾符号、GZ 字段、FSC 单次、包可调用、场景可复现）
- `run_all_tests.py`：**PLIMSOLL_REGRESSION run=129 fail=0**
- 场景 ×3 写出 `cases/out/*.result.json`，`stable=True`
- 变异：LCG 恒 0、忽略 FSC、双计路径 → 测试红
- Review critical（FSC 静默 no-op/双计、包导入假绿）→ 修复后复审 **无 critical**

**Journey log** —
1. `flood_fraction`（damage）与 `fill_fraction`（freesurface）混用会**静默**关闭 FS — 必须显式映射。
2. FSC **只允许计一次**：场景固定走 4.1 的 kg_eff，GZ 不再叠舱。
3. 包 `__init__` 必须 bootstrap `sys.path`（内部是脚式模块名）；验收要 **call** API，不能只 hasattr。
4. 传 `free_surface_tanks` 时强制显式 `fsc_already_in_kg`，避免无人值守下的双计。
5. KM 为 upright 近似；横倾仅小角度 — 结果标 estimate，勿当规范计算。

## [S1] Problem

4.1 无浮态/剩余 GZ/场景；工程侧无一键回归与 L1 trace。用户离开期间需自足闭环。

## [S2] Design

4.2：Δ′/LCG → `solve_trim_equilibrium`；KM≈upright(d)；heel=atan(Σδy/(Δ′·GM′))（GM≤0 → null）。  
4.3：GZ @ kg_eff + V*；**FSC 单次**；双计 ValueError；`flood_tanks_to_fs_tanks` 供实心 KG + GZ 层 FS。  
4.4：`damage_scenarios.json` 三场景 + runner 落盘。  
5.1：`integrate` trace。5.2：包入口可调用。5.4：`run_all_tests.py`。

## [S3] Out of Scope

5.3 sweep CLI；真实型线；游戏写回；完整规范破损稳性；7.x。

## Tasks

- [x] T1: worktree + spec
- [x] T2: 4.2 `solve_flooded_equilibrium`
- [x] T3: 4.3 `remaining_gz_curve`（FSC 单次契约）
- [x] T4: 4.4 场景 JSON + runner
- [x] T5: 5.1 integrate trace
- [x] T6: 5.2 包入口 + 5.4 一键回归
- [x] T7: 测试+变异+回归 129
- [x] T8: review 无 critical + PLAN/交接
