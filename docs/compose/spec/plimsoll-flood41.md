---
feature: plimsoll-flood41
status: designed
updated: 2026-09-21
branch: feature/plimsoll-flood41
commits: cf62d9b..cf62d9b
---

# Plimsoll 阶段 4.1 · 进水组合模型

## Report

## [S1] Problem

破损稳性（阶段 4 总目标）需要先回答：若干舱室进水后，**增加了多少重量、重心在哪、自由液面修正多少**。没有可脚本化、可溯源的进水组合，后续新浮态（4.2）与剩余 GZ（4.3）无从谈起。

游戏侧 `buoyancy_compartments.json` 只有体积/形心，**无自由液面 L×b** —— 本模型要求舱室输入显式给几何。

## [S2] Design

### 舱室进水输入（显式几何，禁止反推）

```python
{
  "id": "boiler_room_1",
  "length_m": 12.0,          # 沿船长（自由液面 L）
  "beam_m": 20.0,            # 横向宽（自由液面 b）
  "height_m": 6.0,           # 舱室垂向
  "keel_to_bottom_m": 2.0,   # 舱底自龙骨高（可选，缺 0）
  "x_m": 13.0,               # 舱室形心纵向（船体坐标，+艏）
  "y_m": 0.0,                # 横向
  "permeability": 0.8,       # 0–1，结构/设备占舱系数
  "flood_fraction": 0.5,     # 舱容被水充满的比例（0–1）；0=未进水
  "fluid_density_t_m3": 1.025,
  "free_surface": true,      # 默认：部分进水且 flood_fraction∈(0,1) 时计 FS
}
```

### 公式

- 舱室几何容积：`V_tank = L · b · H`（矩形代理；`permeability` 可进水体积 `V_perm = μ · V_tank`）
- 进水体积：`V_flood = flood_fraction · V_perm`
- 进水重量：`δ = ρ · V_flood`（t）
- 进水形心垂向（矩形、均匀进水）：`kg_f = keel_to_bottom + flood_fraction · H`（**在可进水段内量**时用 `keel_to_bottom + μ 无关的几何高度`：水从舱底起充，高度 = flood_fraction * H）
- 进水纵向/横向：`x_f = x_m`, `y_f = y_m`（形心不随灌注沿垂向移动时；纵向/横向用舱室形心）
- 合成（实心部分）：`Δ' = Δ + δ`，`KG_solid' = (Δ·KG + δ·kg_f) / Δ'`
- 自由液面：对 `0 < flood_fraction < 1` 且 `free_surface=true` 的舱，
  用 `freesurface`：`i = L·b³/12`，`FSC = Σ(ρ·i)/Δ'`
- **KG_eff = KG_solid' + FSC**
- `GM' = KM' − KG_eff`（若提供 `km_m`；否则只给 KG_eff 与 FSC，**不**假装算出新浮态 KM）

**明确不做（4.2/4.3）**：解新吃水/纵倾/横倾；重算 KM；GZ 曲线。KM 若变化，4.1 只在调用方提供时用给定值，否则输出 `km_m: null` 并标 estimate 边界。

### API（`tools/plimsoll/damage.py`）

```python
def flood_tank_state(tank: dict) -> dict
    # 单舱：V_flood, δ, kg_f, free-surface 惯性是否 active

def flood_combination(ship: dict, tanks: list) -> dict
    # ship: {displacement_t, kg_m, km_m optional, lcb_m optional, lcg_m optional}
    # → added_displacement_t, kg_solid_m, fsc_m, kg_effective_m,
    #   gm_m (if km given), tanks:[...], formula/source 每项
```

### 失败行为

- `displacement_t≤0`, `length/beam/height≤0`, `permeability` 不在 [0,1], `flood_fraction` 不在 [0,1] → ValueError
- 空 tanks 列表：合法，FSC=0，KG 不变

### 纪律

纯函数；复用 `freesurface.tank_free_surface_inertia`；不 round；不猜 compartment JSON 几何。

## [S3] Out of Scope

- 4.2 新浮态 (d, θ, φ) 求解
- 4.3 剩余 GZ
- 4.4 场景回归落盘
- 非矩形舱、边舱渗透连通、不对称进水的横倾求解（输出 y_f 供后续用，本阶段不算横倾角）

## Tasks

- [ ] T1: `damage.py` 单舱进水状态 — acceptance: 矩形舱 δ=ρ·μ·f·L·b·H 解析解 (covers: S2)
- [ ] T2: `flood_combination` 合成 KG_solid + FSC + 可选 GM — acceptance: 两舱手算对照 (covers: S2; depends: T1)
- [ ] T3: 测试 `tests/test_flood_combination.py` — acceptance: 解析解/FS 开关/非法输入全绿 (covers: S2; depends: T1,T2)
- [ ] T4: 回归四套既有测试 — acceptance: 28+35+16+13+16 仍绿 (covers: S2; depends: T2)
- [ ] T5: 变异 — 忽略 permeability、FSC 用 Δ 而非 Δ'、满舱仍计 FS — acceptance: 对应测试红 (covers: S2; depends: T3)
- [ ] T6: PLAN 勾选 4.1 + README — acceptance: 文档与代码一致 (covers: S2; depends: T3,T4)
