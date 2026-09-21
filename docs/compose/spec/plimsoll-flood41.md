---
feature: plimsoll-flood41
status: delivered
updated: 2026-09-21
branch: feature/plimsoll-flood41
commits: cf62d9b..5bb9250
---

# Plimsoll 阶段 4.1 · 进水组合模型

## Report

**What was built** — 新模块 `tools/plimsoll/damage.py`：给定船体 Δ/KG（及可选 KM/LCG）与若干**显式矩形几何**的进水舱，计算进水增重 `δ=ρ·μ·f·L·b·H`、进水形心 `kg_f=z0+f·H`、实心合成 `KG_solid'=(Δ·KG+Σδ·kg_f)/Δ'`、自由液面 `FSC=Σ(ρi)/Δ'`（**分母为进水后排水量**）、`KG_eff=KG_solid'+FSC`，以及调用方提供 KM 时的 `GM'`。空舱/满舱/μ=0 的自由液面与增重按公式关闭。**不**求解新吃水/纵倾/横倾（4.2），**不**从游戏 compartment JSON 猜 L×b。PLAN 4.1 已勾选。

**Verification** —
- `test_flood_combination.py`：**10/10 PASS**（两舱手算、FSC 用 Δ' 而非 Δ 的差分、空列表恒等、非法输入）
- 回归：hydrostatics 28 · geometric 35 · offsets 16 · trim 13 · freesurface 16 — **均 OK**（分支上合计 118）
- 变异：忽略 permeability FAIL 3 · FSC 分母用 Δ FAIL 2 · 满舱仍计 FS FAIL 2 · 还原后全绿
- 独立 review：**success，无 critical**

**Journey log** —
1. `kg_f=z0+f·H` **有意与 μ 无关**（水从舱底起充的几何高度）；4.2 不要“修正”这一点。
2. FSC 分母必须是 **Δ′**；阶段 3 的 `free_surface_correction(tanks, Δ)` 默认用输入 Δ，调用时必须传进水后排水量。
3. 4.1 不重算破损后 KM；若调用方沿用原 KM，结果带 `estimate` 边界。
4. 自由液面用整舱 L×b（μ&lt;1 时偏保守），与增重路径的 μ 分离。
5. 字段名：进水用 `flood_fraction`，FSC 模块用 `fill_fraction`，对接时需映射。

## [S1] Problem

破损稳性需要先得到进水后的增重、重心与 FSC。compartment JSON 无自由液面尺寸，模型必须显式几何。

## [S2] Design

矩形舱：`V_tank=L·b·H`，`V_flood=μ·f·V_tank`，`δ=ρ·V_flood`，`kg_f=z0+f·H`，`Δ′=Δ+Σδ`，`KG_solid′=(Δ·KG+Σδ·kg_f)/Δ′`，`FSC=Σ(ρ·i)/Δ′`（仅 0&lt;f&lt;1），`KG_eff=KG_solid′+FSC`，`GM=KM−KG_eff`（KM 可选）。

API：`damage.flood_tank_state` / `damage.flood_combination`。

失败：非法 μ/f/尺寸/排水量 → ValueError。

## [S3] Out of Scope

4.2 新浮态、4.3 剩余 GZ、4.4 场景回归；非矩形舱；横倾角求解。

## Tasks

- [x] T1: `flood_tank_state` 解析解 — acceptance: δ 与 kg_f 手算一致 (covers: S2)
- [x] T2: `flood_combination` 合成 KG+FSC+可选 GM — acceptance: 两舱手算对照 (covers: S2; depends: T1)
- [x] T3: `tools/plimsoll/tests/test_flood_combination.py` — acceptance: 10 项全绿 (covers: S2; depends: T1,T2)
- [x] T4: 回归既有测试 — acceptance: 28+35+16+13+16 仍绿 (covers: S2; depends: T2)
- [x] T5: 变异 μ / Δ′ / 满舱 FS — acceptance: 均被抓住 (covers: S2; depends: T3)
- [x] T6: PLAN 4.1 与 README — acceptance: 文档与代码一致 (covers: S2; depends: T3,T4)
