---
feature: plimsoll-trim-22
status: designed
updated: 2026-09-21
branch: feature/plimsoll-trim-22
commits: ec80089..ec80089
---

# Plimsoll 阶段 2.2 · 纵倾平衡求解

## Report

## [S1] Problem

`integrate()` / `solve_waterline()`（阶段 2.1）只能在**给定**纵倾角 θ 下解出水线截距 d，使浸没体积达标。真实浮态是：已知排水量与重心纵向位置 LCG，要**同时**解出吃水与纵倾，使

1. 浸没体积 ∇ = 目标排水体积，且
2. 浮心纵向位置 **LCB = LCG**（纵向力矩平衡）。

缺少该能力时，破损进水、装卸载荷后的浮态无法在 Plimsoll 内闭环，也无法为阶段 4 破损稳性提供平衡浮态。

## [S2] Design

### 物理与符号

- 水线平面：`z = x·tanθ + y·tanφ + d`；**θ > 0 = 艏倾（bow down）**（与 2.1 一致）。
- `xlcb`：浮心纵向位置，**相对船体坐标原点**（x 向舰艏为正）。
- 目标 `target_lcb` 必须与 `xlcb` **同一坐标系**；型值表船体与合成参照船体原点不同，调用方负责对齐。
- `phi_rad` 默认 0（正浮）；允许传入固定横倾，θ 求解与横倾正交（沿用同一裁剪）。

### 算法（二维求根，不与 2.1 混写）

**嵌套求根**（PLAN 指定做法）：

- **内层**：固定 θ，调用已有 `hull.solve_waterline(phi, target_volume, trim_rad=θ)`，二分出 d 使 ∇(d,θ)=V*。
- **外层**：残差 `r(θ) = xlcb(d*(θ), θ) − target_lcb`。在 `[θ_lo, θ_hi]` 上对 θ 二分；括号不足时在限界内扩大搜索，仍变号失败则抛 `ValueError`（说明目标 LCB 不可达）。
- **θ 限界**：默认 ±15°；扩大上限至 ±30°。调用方可收紧。
- **收敛**：`|r(θ)| ≤ lcb_tol` 或外层迭代耗尽；耗尽且未达标则报错，不返回伪解。
- **禁止**：把解 θ 写进 `solve_waterline`；对返回值做四舍五入；用“看起来合理”的容差放过未达标解。

### 方箱闭式解（解析验收锚）

直壁方箱、整段沿船长均浸没、龙骨 z=k、中线吃水 T=V/(L·B)：

| 量 | 闭式 |
|---|---|
| 中线水线高 | `d* = k + T`（**与 θ 无关**） |
| 纵倾 | `tanθ = 12 · T · LCB / L²` |
| 浮心 | `xlcb = tanθ · L² / (12 T)` |

整段浸没条件：`|tanθ| ≤ 2T/L`（两端不出水/不露底）。测试用例必须满足该条件。

### API 契约

```python
# geometry.py — StationedHull
def solve_trim_equilibrium(self, target_volume, target_lcb, *,
                           phi_rad=0.0,
                           theta_lo=None, theta_hi=None,
                           vol_tol=1e-9, lcb_tol=1e-6,
                           max_outer=80) -> dict

# geometric.py — 纯函数包装（dict 进出，与 solve_equilibrium 同风格）
def solve_trim_equilibrium(hull, target_volume, target_lcb, **kwargs) -> dict
```

返回字典（全精度 float，不取整）：

| 键 | 含义 |
|---|---|
| `d_m` | 平衡水线截距（船体坐标 z） |
| `trim_rad` / `trim_deg` | 纵倾角，θ>0=艏倾 |
| `volume_m3` | 平衡体积 |
| `xlcb_m` | 平衡浮心纵向位置 |
| `target_volume_m3` / `target_lcb_m` | 输入回显 |
| `volume_residual_m3` / `lcb_residual_m` | 残差（验收看这个） |
| `outer_iterations` | 外层迭代次数 |
| `phi_rad` | 本次求解使用的横倾 |
| `hydrostatics` | `integrate(phi, d, θ)` 的完整结果 |

### 失败行为

- 目标体积 ≤ 0 或超出船体可浸没范围 → `ValueError`
- θ 在限界内无法使 LCB 残差变号 → `ValueError`（写明已试范围与残差符号）
- 外层耗尽仍未达 `lcb_tol` → `ValueError`（附最终残差）

### 纪律

核心纯函数、无 GUI/Unity/网络依赖；不做四舍五入；模块 docstring 写明符号约定与坐标系；**变异验证**（见 Tasks）通过前不得声称完成。

## [S3] Out of Scope

- 阶段 2.3：大纵倾下 LWL 变化的专项耦合分析（本阶段只保证体积/LCB 平衡收敛）
- 自由液面、破损进水、重量分组（阶段 3–4）
- CLI / result.json 字段扩展
- 游戏侧 `ShipFloatPrototype` / `hydrostatics.json` 写回
- L1 输出 trace 补全（阶段 5.1，可并行但不阻塞本交付）

## Tasks

- [ ] T1: 在 `geometry.py` 实现 `StationedHull.solve_trim_equilibrium`（嵌套求根 + θ 括号扩大 + 失败抛错）— acceptance: 方箱正 LCB 案例返回 (d,θ) 且体积/LCB 残差达标 (covers: S2)
- [ ] T2: 在 `geometric.py` 增加纯函数包装，返回契约字典 — acceptance: 从 hull 包装调用可得同一 (d,θ) (covers: S2; depends: T1)
- [ ] T3: 测试 `tests/test_trim_equilibrium.py`：方箱 LCB=0 / ±LCB 闭式解；θ 与 LCB 同号；体积与 LCB 双达标；参照船体由已知 θ 往返还原；不可达目标抛错 — acceptance: 新文件全绿 (covers: S2; depends: T1,T2)
- [ ] T4: 回归既有三套测试 — acceptance: hydrostatics 28 + geometric 35 + offsets 16 仍全绿 (covers: S2; depends: T1,T2)
- [ ] T5: 变异验证 — 将外层残差改为恒 0、或只断言体积不查 LCB，确认对应测试变红；记录于 spec Report — acceptance: 至少一条设计缺陷被测试抓住 (covers: S2; depends: T3)
- [ ] T6: 更新 `PLAN.md` 勾选 2.2 与 `tools/plimsoll/README.md` 限界/能力说明 — acceptance: 2.2 标为完成并附结论摘要 (covers: S2; depends: T3,T4)
