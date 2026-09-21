---
feature: plimsoll-fsc
status: designed
updated: 2026-09-21
branch: feature/plimsoll-fsc
commits: ec80089..ec80089
---

# Plimsoll 阶段 3 · 自由液面修正（FSC）

## Report

## [S1] Problem

进水舱/液舱的自由液面会抬高重心等效位置，显著降低初稳性与大角稳性。PLAN 阶段 3 要求：

1. **3.1** 由舱室几何算自由液面惯性矩，`FSC = Σ(ρ_i·i_i)/Δ`
2. **3.2** 用修正后的 KG 计算 GM 与 GZ，并量化与未修正的差异

没有 FSC，破损稳性（阶段 4）的结果会系统性偏乐观。

## [S2] Design

### 公式（矩形舱，横向自由液面）

- 横向惯性矩（对水线面中和轴）：`i = L · b³ / 12`  
  `L` = 沿船长方向舱长（m），`b` = 横向舱宽（m）。**与灌注率无关**（矩形、自由液面）。
- 自由液面修正（重心升高）：`FSC = Σ(ρ_fluid,i · i_i) / Δ`  
  `ρ` 单位 t/m³，`i` 单位 m⁴，`Δ` 单位 t → FSC 单位 **m**。
- **空舱或满舱**（fill_fraction ≤ 0 或 ≥ 1）：无自由液面，`i_eff = 0`。
- 修正后：`KG_eff = KG + FSC`；`GM_eff = KM − KG_eff`；GZ 用 `KG_eff`。
- FSC **恒 ≥ 0**（只降低稳性，不提高）。

### 舱室输入 schema（纯 dict）

```python
{
  "id": "tank_1",              # 可选，用于回显
  "length_m": 20.0,            # 沿船长
  "beam_m": 10.0,              # 横向宽度（自由液面惯性的 b）
  "fluid_density_t_m3": 1.025, # 舱内液体密度
  "fill_fraction": 0.7,        # 0–1；越界或空/满 → 无 FSC
  "permeability": 1.0,         # 可选；仅在 fill 计算有效液体时用，本阶段不改 i
}
```

说明：`queen_mary_v3/buoyancy_compartments.json` **没有** L×b 自由液面尺寸，只有体积与形心。本阶段输入必须显式给 `length_m`/`beam_m`；由舱容反推形状属阶段 4，**不在此轮猜测几何**。

### API（新模块 `tools/plimsoll/freesurface.py`）

```python
def tank_free_surface_inertia(tank: dict) -> dict
    # → {tank_id, length_m, beam_m, i_m4, i_effective_m4, active, fill_fraction, formula, source}

def free_surface_correction(tanks: list, displacement_t: float,
                            sea_density_t_m3=1.025) -> dict
    # → {fsc_m, displacement_t, n_tanks, n_active, tanks: [...],
    #    formula, source}

def apply_fsc(kg_m: float, fsc_m: float) -> dict
    # → {kg_m, fsc_m, kg_effective_m, gm_delta_m: -fsc}
```

### 稳性接入（3.2）

- `geometric.gz_curve(hull, kg, target_volume, angles_deg, free_surface_tanks=None, ...)`
  - 若提供 tanks：`fsc = free_surface_correction(tanks, displacement_t=target_volume*RHO_SEA)`  
    `kg_eff = kg + fsc["fsc_m"]`；行内输出增加 `kg_effective_m`, `fsc_m`
  - 未提供 tanks：行为与现网一致（回归）
- L0：`hydrostatics` 路径可在测试中用 `GM_eff = GM − FSC` 对照，不必改 CLI 本轮

### 失败行为

- `displacement_t ≤ 0` → ValueError
- `length_m ≤ 0` 或 `beam_m < 0` → ValueError
- `fluid_density_t_m3 < 0` → ValueError
- 空/满舱：**不**报错，`active=False`, `i_effective_m4=0`

### 纪律

纯函数；核心不四舍五入；每项 `formula`/`source`；θ/坐标约定不变；不 import Unity。

## [S3] Out of Scope

- 阶段 4 破损进水组合、新浮态求解、剩余 GZ 场景回归
- 由舱容/形心反推 L×b
- 非矩形自由液面、纵向自由液面修正（MCT 耦合）
- CLI result.json 字段、游戏侧写回
- 阶段 2.2/2.3（独立分支 `feature/plimsoll-trim-22`）

## Tasks

- [ ] T1: 新建 `freesurface.py`：矩形 `i=L·b³/12`、空/满关闭、FSC 求和 — acceptance: 解析解单测通过 (covers: S2)
- [ ] T2: `apply_fsc` 与 `geometric.gz_curve` 可选 `free_surface_tanks` — acceptance: 有 tanks 时 GM/GZ 下降且等于 KM−(KG+FSC) (covers: S2; depends: T1)
- [ ] T3: 测试 `tests/test_freesurface.py`：单舱解析、双舱叠加、空满为零、GZ 对照、非法输入抛错 — acceptance: 新文件全绿 (covers: S2; depends: T1,T2)
- [ ] T4: 回归 hydrostatics/geometric/offsets（本分支基于 master，无 2.2 测试）— acceptance: 28+35+16 仍绿 (covers: S2; depends: T2)
- [ ] T5: 变异验证 — `b³`→`b²`、去掉 `/Δ`、空舱仍计 i，对应测试变红 — acceptance: ≥2 处设计缺陷被抓住 (covers: S2; depends: T3)
- [ ] T6: 更新 PLAN 勾选 3.1/3.2 与 README 限界 — acceptance: 文档与代码一致 (covers: S2; depends: T3,T4)
