---
feature: plimsoll-trim-22
status: delivered
updated: 2026-09-21
branch: feature/plimsoll-trim-22
commits: ec80089..9821f87
---

# Plimsoll 阶段 2.2 · 纵倾平衡求解

## Report

**What was built** — 在 L1 几何法上增加纵倾平衡：给定排水体积 `target_volume` 与浮心纵向位置 `target_lcb`（= LCG，须与 `integrate().xlcb` 同一船体坐标原点），嵌套求根解出水线截距 `d` 与纵倾角 `θ`（θ>0=艏倾）。内层沿用 `solve_waterline` 按体积解 d；外层二分 θ 使 `xlcb` 对齐 LCG。API：`StationedHull.solve_trim_equilibrium` 与 `geometric.solve_trim_equilibrium`。成功解必须**同时**满足体积残差与 LCB 残差；目标体积超可浸没范围时在求解前 θ 网格探测即抛错，不返回伪解。`PLAN.md` 阶段 2.2 已勾选。

**Verification** —
- `test_trim_equilibrium.py`：**13/13 PASS**（方箱 LCB=0/±闭式解、往返、超容积、双门闩、不对称 d(θ) 哨兵）
- 回归：`test_hydrostatics.py` 28 · `test_geometric.py` 35 · `test_offsets_import.py` 16 — **均 OK**（合计 92）
- 变异验证：残差强制 0 → **6 FAIL**；内层 θ 强制 0 → **2 FAIL/ERROR**（体积残差）；仅去掉末尾体积门闩仍 PASS（`volume_reachable` 探测独立抓住超容积）
- 独立 review：首轮 critical（体积未门闩 / 超容积未抛错）→ 修复提交 `9821f87`；复审 **success，无新 critical**

**Journey log** —
1. 方箱闭式解下 θ 与解析解应用**相对误差**：数值 LCB 被积函数含 x·A(x)，梯形积分对二次不精确（~1e-3），逐位断言会假红。
2. **对称船体测不出内层丢掉 θ**：d*(+θ)=d*(−θ)；变异哨兵必须用不对称船体（∫xB dx≠0）。
3. 超容积时 LCB 残差可能同号且数值极小，若先查 LCB 会误报「LCB 不可达」——**体积可达性探测必须前置于 LCB 括号逻辑**。
4. 嵌套求根的变异验证要覆盖**两层**：只打外层残差不够；内层 ignore-θ 在对称几何上是盲区。
5. PowerShell `Get-Content`/`Set-Content` 改含中文 docstring 的源文件会弄坏 UTF-8——变异注入请用 Python 读写。

## [S1] Problem

`integrate()` / `solve_waterline()`（阶段 2.1）只能在**给定**纵倾角 θ 下解出水线截距 d，使浸没体积达标。真实浮态是：已知排水量与重心纵向位置 LCG，要**同时**解出吃水与纵倾，使体积与纵向力矩同时平衡。缺少该能力时，破损进水、装卸载荷后的浮态无法在 Plimsoll 内闭环。

## [S2] Design

### 物理与符号

- 水线平面：`z = x·tanθ + y·tanφ + d`；**θ > 0 = 艏倾（bow down）**。
- `xlcb`：浮心纵向位置，相对船体坐标原点；`target_lcb` 必须同坐标系。
- `phi_rad` 默认 0；允许固定横倾，θ 求解与横倾正交。

### 算法（二维求根，不与 2.1 混写）

- **内层**：固定 θ，`solve_waterline` 解 d 使 ∇(d,θ)=V*。
- **外层**：残差 r(θ)=xlcb−target_lcb，θ 二分；默认 ±15°，可扩至硬限界 ±30°；调用方限界先夹入硬限界。
- **体积门闩**：求解前与扩大括号后，在 θ 网格上探测 V* 可达性；不可达 → `ValueError`（体积优先，避免误报 LCB）。
- **成功双门闩**：|∇−V*|≤volume_eq_tol **且** |xlcb−target_lcb|≤lcb_tol，否则 `ValueError`。
- **禁止**：把解 θ 写进 `solve_waterline`；核心四舍五入；伪解返回。

### 方箱闭式解（整段浸没）

| 量 | 闭式 |
|---|---|
| 中线水线高 | `d* = k + T`，`T=V*/(L·B)`（与 θ 无关） |
| 纵倾 | `tanθ = 12·T·LCB/L²` |
| 浮心 | `xlcb = tanθ·L²/(12T)` |

### API 契约

`StationedHull.solve_trim_equilibrium(...)` / `geometric.solve_trim_equilibrium(...)` 返回：`d_m`, `trim_rad`, `trim_deg`, `volume_m3`, `xlcb_m`, `target_*`, `volume_residual_m3`, `lcb_residual_m`, `volume_eq_tol_m3`, `outer_iterations`, `phi_rad`, `hydrostatics`。

### 失败行为

V*≤0、超可浸没、LCB 不可达、外层未收敛 → `ValueError`，不返回伪解。

### 纪律

纯函数、无 GUI/Unity/网络；全精度 float；符号与坐标系写入 docstring；变异验证通过后方可交付。

## [S3] Out of Scope

- 阶段 2.3 大纵倾 LWL 耦合专项；阶段 3–4 FSC/破损稳性；CLI 扩展；游戏侧接入；L1 trace（5.1）。

## Tasks

- [x] T1: 在 `geometry.py` 实现 `StationedHull.solve_trim_equilibrium`（嵌套求根 + θ 括号扩大 + 体积/LCB 双门闩 + 失败抛错）— acceptance: 方箱正 LCB 返回 (d,θ) 且双残差达标 (covers: S2)
- [x] T2: 在 `geometric.py` 增加纯函数包装 — acceptance: 包装调用得同一 (d,θ) (covers: S2; depends: T1)
- [x] T3: 测试 `tests/test_trim_equilibrium.py`：方箱闭式解；θ 与 LCB 同号；双门闩；超容积抛错；参照船体往返；不对称 d(θ) 哨兵；不可达抛错 — acceptance: 13 项全绿 (covers: S2; depends: T1,T2)
- [x] T4: 回归既有三套测试 — acceptance: 28+35+16 仍全绿 (covers: S2; depends: T1,T2)
- [x] T5: 变异验证 — 残差恒 0 / 内层 θ 丢弃 均被抓住；记录于 Report — acceptance: 设计缺陷被测试抓住 (covers: S2; depends: T3)
- [x] T6: 更新 `PLAN.md` 勾选 2.2 与 `tools/plimsoll/README.md` — acceptance: 2.2 标完成并附结论 (covers: S2; depends: T3,T4)
