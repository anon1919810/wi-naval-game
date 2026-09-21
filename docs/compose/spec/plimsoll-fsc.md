---
feature: plimsoll-fsc
status: delivered
updated: 2026-09-21
branch: feature/plimsoll-fsc
commits: ec80089..dd854de
---

# Plimsoll 阶段 3 · 自由液面修正（FSC）

## Report

**What was built** — 自由液面修正核心与稳性接入。新模块 `tools/plimsoll/freesurface.py`：矩形舱横向惯性矩 `i=L·b³/12`，空舱/满舱（fill≤0 或 ≥1）不计；`FSC=Σ(ρ_i·i_i)/Δ`（t/m³·m⁴/t → m，恒 ≥0）；`apply_fsc` 给出 `KG_eff=KG+FSC`。`geometric.gz_curve` 增加可选参数 `free_surface_tanks`，GZ 使用等效重心，行内输出 `fsc_m`/`kg_effective_m`；不传 tanks 时行为与合入前完全一致。PLAN 3.1/3.2 已勾选。游戏侧 `buoyancy_compartments.json` 无 L×b，**未**猜测几何。

**Verification** —
- `test_freesurface.py`：**16/16 PASS**（解析解、双舱叠加、空满为零、GZ 与手工 KG+FSC 对照、GZ 下降量 ≈ FSC·sinφ、非法输入）
- 回归：hydrostatics **28** · geometric **35** · offsets **16** — 均 OK（本分支合计 95）
- 变异：`b³`→`b²` FAIL 4 · 去掉 `/Δ` FAIL 3 · 满舱仍计 i FAIL 2 · 还原后全绿
- 独立 review：**success，无 critical**（复核 16/16）

**Journey log** —
1. 游戏侧 compartment 只有体积/形心、无自由液面尺寸 — 阶段 3 输入必须显式 L×b；反推形状留给阶段 4。
2. 默认 `fill_fraction=1.0`（满舱=无 FSC）偏乐观：阶段 4 进水模型应强制显式 fill。
3. FSC 与 L0/CLI 正交，回归面主要是 `geometric` + `freesurface`。
4. 单元与变异：`b` 三次方、`/Δ`、空满关闭是三条必须钉死的物理点。
5. 本分支基于 master（不含 2.2）；与 `feature/plimsoll-trim-22` 并行，合入顺序可互换。

## [S1] Problem

进水舱/液舱自由液面抬高等效重心，削弱 GM 与 GZ。PLAN 3.1/3.2 要求矩形舱惯性矩、FSC 求和，并把修正 KG 用于稳性曲线。没有 FSC，破损稳性会系统性偏乐观。

## [S2] Design

### 公式

- `i = L·b³/12`（L 沿船长，b 横向宽）；与灌注率无关；空/满 → `i_eff=0`
- `FSC = Σ(ρ_i·i_i)/Δ`；`KG_eff = KG + FSC`；`GM_eff = GM − FSC`
- `sea_density` 仅回显；分子用各舱 ρ_i

### API

`freesurface.tank_free_surface_inertia` / `free_surface_correction` / `apply_fsc`  
`geometric.gz_curve(..., free_surface_tanks=None)` — 无 tanks 行为不变

### 失败行为

`displacement_t≤0`、`L≤0`、`b<0`、`ρ<0`、`fsc_m<0` → ValueError；空满不报错。

### 纪律

纯函数、不四舍五入、`formula`/`source`；不从 compartment JSON 猜 L×b。

## [S3] Out of Scope

阶段 4 进水组合/新浮态/场景回归；舱容反推 L×b；非矩形/纵向 FS；CLI/游戏写回；2.2/2.3。

## Tasks

- [x] T1: `freesurface.py` 矩形 i 与 FSC 求和 — acceptance: 解析解通过 (covers: S2)
- [x] T2: `apply_fsc` + `gz_curve(free_surface_tanks=)` — acceptance: 与手工 KG+FSC 一致 (covers: S2; depends: T1)
- [x] T3: `tools/plimsoll/tests/test_freesurface.py` — acceptance: 16 项全绿 (covers: S2; depends: T1,T2)
- [x] T4: 回归 28+35+16 — acceptance: 仍全绿 (covers: S2; depends: T2)
- [x] T5: 变异验证 b² / 无Δ / 满舱 — acceptance: 均被抓住 (covers: S2; depends: T3)
- [x] T6: PLAN 3.1/3.2 与 README — acceptance: 文档与代码一致 (covers: S2; depends: T3,T4)
