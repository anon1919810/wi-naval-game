---
feature: plimsoll-damage-loop
status: designed
updated: 2026-09-21
branch: feature/plimsoll-damage-loop
commits: cc266fe..cc266fe
---

# Plimsoll 长任务 · 破损稳性闭环 + 工程化收口

> 用户离开期间可无人值守推进的长任务。范围：PLAN **4.2–4.4** 与 **5.1/5.2/5.4**。
> 前置已在 master：2.2 纵倾平衡、3.x FSC、4.1 进水组合（`cc266fe`）。

## Report

## [S1] Problem

4.1 只给出进水后的重量/重心/FSC，**不能**回答：船破损后吃水纵倾多少、剩余稳性如何、典型进水场景是否可复现。工程上测试仍靠手工逐文件调用，L1 输出无 trace，包导入依赖 cwd。用户离开时需要一条自足、可验证、可续接的闭环。

## [S2] Design

### 4.2 破损后浮态（纵向 + 垂向；横倾小角度估计）

输入：`hull`（StationedHull）、`ship`（Δ, KG, 可选 LCG/LCB/KM）、`tanks`（显式矩形进水舱）。

流程：

1. `combo = damage.flood_combination(ship, tanks)` → Δ′, KG_eff, FSC, lcg_solid, tcg_flood…
2. 目标体积 `V* = Δ′ / ρ`
3. 目标纵向浮心 = **破损后 LCG**（4.1 的 `lcg_solid_m`；若输入无 LCG，用原 `lcb_m` 或 0 并标 estimate）
4. `solve_trim_equilibrium(hull, V*, lcg)` → `(d, θ)`（复用 2.2）
5. 在 `(d, θ)` 上 `integrate` → 体积/浮心；**新 KM**：用该水线附近的正浮静水力
   `hydrostatics_upright(hull, waterline_z=d)` 的 KM 作一阶近似；纵倾对 KM 的影响标 estimate
6. 横倾（小角度）：`φ ≈ arctan( (δ·y) / (Δ′·GM′) )` 仅当 `GM′>0`；GM′ = KM′ − KG_eff
   否则 `heel_deg = null` 且 `gm_negative: true`
7. 输出契约 dict：浮态、残差、KM/GM、estimate 字段

失败：沿用 2.2/4.1 的 ValueError；GM≤0 时不抛错，标记不稳定。

### 4.3 剩余 GZ

- `gz_curve(hull, kg_eff, V*, angles)`，angles 默认 0..60 每 5°
- 可选 `free_surface_tanks`：若进水舱仍有自由液面，再叠一层 FSC（分母用 Δ′）
- 输出：曲线、`max_gz_m`/`angle_at_max_deg`、`range_deg`（GZ&gt;0 的连续区间）、甲板浸没角提示（相对水线几何若可估）
- **甲板以上**形状未验证 — 与现有限界一致，结果标 estimate

### 4.4 场景回归

场景 JSON（`tools/plimsoll/cases/damage_scenarios.json`）：

| id | 内容 |
|---|---|
| `single_boiler` | 单炉舱部分进水 |
| `double_boiler` | 相邻两炉舱 |
| `engine_room` | 机舱大体积进水 |

每场景：ship 基线 + tanks 列表 + 期望字段（可复现）。CLI/脚本 `damage_loop.run_scenario` 写出 `cases/out/<id>.result.json`。

验收：三次运行字节级可复现（无随机）；关键字段与手算/自洽检查一致。

### 5.1 L1 trace

`StationedHull.integrate` 返回值增加 `trace`：对 volume/xlcb/yb/zb/awp 等写 `formula`/`source`/`estimate`。测试断言键存在。

### 5.2 包化

`tools/plimsoll/__init__.py` 导出公共 API；测试改为 `sys.path` 指向 `tools` 后 `from plimsoll import ...` **或** 保持脚本式但增加 `run_all_tests.py` 从任意 cwd 可跑。验收：从仓库根 `python -c "import sys; sys.path.insert(0,'tools'); import plimsoll"` 成功。

### 5.4 一键回归

`tools/plimsoll/run_all_tests.py`：发现并执行全部 tests/*.py，汇总 PASS/FAIL，非零退出码。

### 纪律

纯函数；核心不 round；数值实现由主代理完成（不把数值交给子代理写）；变异验证；每完成一项回写 PLAN。

## [S3] Out of Scope

- 真实型线图接入
- 游戏侧 Unity 写回 / hydrostatics.json
- 5.3 sweep CLI（可后置）
- 7.x 阻力/耐波/穿深
- 非矩形舱、完整二维破损稳性规范计算

## Tasks

- [ ] T1: worktree + 本 spec — acceptance: 分支存在且 spec 可读 (covers: S2)
- [ ] T2: 4.2 `damage.solve_flooded_equilibrium` — acceptance: 方箱+单舱进水体积/纵倾/残差达标 (covers: S2)
- [ ] T3: 4.3 `damage.remaining_gz_curve` — acceptance: 有 GZ 表与 max/range 字段 (covers: S2; depends: T2)
- [ ] T4: 4.4 场景 JSON + runner + 落盘 — acceptance: 3 场景可复现运行 (covers: S2; depends: T2,T3)
- [ ] T5: 5.1 integrate trace — acceptance: 测试断言 trace 键存在 (covers: S2)
- [ ] T6: 5.2 + 5.4 包入口与 run_all_tests — acceptance: 一键回归汇总全绿 (covers: S2)
- [ ] T7: 测试 + 变异 + 全量回归 — acceptance: 新测试红/绿证据；旧套件不回归 (covers: S2; depends: T2–T6)
- [ ] T8: review + finalize + PLAN/交接 — acceptance: review 无 critical；spec delivered；PLAN 勾选 (covers: S2; depends: T7)
