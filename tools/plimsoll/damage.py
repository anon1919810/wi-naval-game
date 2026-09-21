"""Plimsoll · 破损稳性前置 · 进水组合模型（阶段 4.1）

给定船体初始排水量/KG 与若干**显式几何**的进水舱，计算：
  · 进水增重 δ 与进水形心
  · 实心合成重心 KG_solid'
  · 自由液面修正 FSC（分母用**进水后**排水量 Δ'）
  · KG_eff = KG_solid' + FSC
  · 若提供 KM，则 GM' = KM − KG_eff

**不在本模块**：解新吃水/纵倾/横倾（4.2）、剩余 GZ（4.3）。
舱室必须给 L×b×H；`queen_mary_v3/buoyancy_compartments.json` 无自由液面
尺寸，**禁止**在此猜几何。

公式
----
    V_tank = L·b·H
    V_perm = μ · V_tank
    V_flood = flood_fraction · V_perm
    δ = ρ · V_flood
    kg_flood = keel_to_bottom + flood_fraction · H   （自舱底起充的矩形）
    Δ' = Δ + δ
    KG_solid' = (Δ·KG + δ·kg_flood) / Δ'
    FSC = Σ(ρ_i · i_i) / Δ' ,  i = L·b³/12（仅 0<flood_fraction<1 且 free_surface）
    KG_eff = KG_solid' + FSC
"""

from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

RHO_SEA = 1.025


def flood_tank_state(tank: dict) -> dict:
    """单舱进水状态（矩形代理）。未进水（flood_fraction=0）时 δ=0。"""
    if not isinstance(tank, dict):
        raise ValueError("tank 必须是 dict")

    def _f(key, default=None):
        if key not in tank and default is None:
            raise ValueError("tank 缺少字段 %s" % key)
        return float(tank.get(key, default))

    L = _f("length_m")
    b = _f("beam_m")
    H = _f("height_m")
    z0 = float(tank.get("keel_to_bottom_m", 0.0))
    x = float(tank.get("x_m", 0.0))
    y = float(tank.get("y_m", 0.0))
    mu = float(tank.get("permeability", 1.0))
    frac = float(tank.get("flood_fraction", 0.0))
    rho = float(tank.get("fluid_density_t_m3", RHO_SEA))
    want_fs = bool(tank.get("free_surface", True))
    tank_id = tank.get("id", "")

    if L <= 0.0 or b <= 0.0 or H <= 0.0:
        raise ValueError("length_m/beam_m/height_m 必须为正，tank=%r" % tank_id)
    if not (0.0 <= mu <= 1.0):
        raise ValueError("permeability 必须在 [0,1]，tank=%r 收到 %r" % (tank_id, mu))
    if not (0.0 <= frac <= 1.0):
        raise ValueError("flood_fraction 必须在 [0,1]，tank=%r 收到 %r" % (tank_id, frac))
    if rho < 0.0:
        raise ValueError("fluid_density_t_m3 不能为负，tank=%r" % tank_id)

    v_tank = L * b * H
    v_perm = mu * v_tank
    v_flood = frac * v_perm
    delta = rho * v_flood
    kg_f = z0 + frac * H

    fs_active = want_fs and (0.0 < frac < 1.0) and (b > 0.0)
    i_full = L * (b ** 3) / 12.0
    i_eff = i_full if fs_active else 0.0

    return {
        "tank_id": tank_id,
        "length_m": L,
        "beam_m": b,
        "height_m": H,
        "permeability": mu,
        "flood_fraction": frac,
        "fluid_density_t_m3": rho,
        "volume_tank_m3": v_tank,
        "volume_perm_m3": v_perm,
        "volume_flood_m3": v_flood,
        "added_displacement_t": delta,
        "kg_flood_m": kg_f,
        "x_m": x,
        "y_m": y,
        "free_surface_active": fs_active,
        "i_effective_m4": i_eff,
        "rho_times_i": rho * i_eff,
        "formula": "δ=ρ·μ·f·L·b·H；kg_f=z0+f·H；FS 仅 0<f<1",
        "source": "rectangular flood proxy; explicit geometry required",
    }


def flood_combination(ship: dict, tanks=None) -> dict:
    """进水组合：增重 + 合成 KG + FSC（+ 可选 GM）。

    `ship` = {displacement_t, kg_m, km_m optional, lcb_m optional, lcg_m optional}
    """
    if not isinstance(ship, dict):
        raise ValueError("ship 必须是 dict")
    if "displacement_t" not in ship or "kg_m" not in ship:
        raise ValueError("ship 需要 displacement_t 与 kg_m")
    delta0 = float(ship["displacement_t"])
    kg0 = float(ship["kg_m"])
    if not (delta0 > 0.0):
        raise ValueError("displacement_t 必须为正，收到 %r" % delta0)

    km = ship.get("km_m")
    km = None if km is None else float(km)
    lcb0 = ship.get("lcb_m")
    lcb0 = None if lcb0 is None else float(lcb0)
    lcg0 = ship.get("lcg_m")
    lcg0 = None if lcg0 is None else float(lcg0)

    if tanks is None:
        tanks = []
    if not isinstance(tanks, (list, tuple)):
        raise ValueError("tanks 必须是列表")

    rows = []
    sum_delta = 0.0
    sum_moment_kg = 0.0
    sum_rho_i = 0.0
    sum_delta_x = 0.0
    sum_delta_y = 0.0
    for t in tanks:
        row = flood_tank_state(t)
        rows.append(row)
        sum_delta += row["added_displacement_t"]
        sum_moment_kg += row["added_displacement_t"] * row["kg_flood_m"]
        sum_rho_i += row["rho_times_i"]
        sum_delta_x += row["added_displacement_t"] * row["x_m"]
        sum_delta_y += row["added_displacement_t"] * row["y_m"]

    delta1 = delta0 + sum_delta
    if delta1 <= 0.0:
        raise ValueError("进水后排水量非正")
    kg_solid = (delta0 * kg0 + sum_moment_kg) / delta1
    fsc = sum_rho_i / delta1
    kg_eff = kg_solid + fsc

    gm = None if km is None else (km - kg_eff)

    lcg_solid = None
    lcb_out = None
    if lcg0 is not None and lcb0 is not None:
        # 实心合成纵向重心；进水形心 x 作为额外力矩
        lcg_solid = (delta0 * lcg0 + sum_delta_x) / delta1
        lcb_out = lcb0  # 4.1 不求新浮态，LCB 不自动变

    return {
        "displacement_before_t": delta0,
        "kg_before_m": kg0,
        "added_displacement_t": sum_delta,
        "displacement_after_t": delta1,
        "kg_solid_m": kg_solid,
        "fsc_m": fsc,
        "kg_effective_m": kg_eff,
        "km_m": km,
        "gm_m": gm,
        "lcg_solid_m": lcg_solid,
        "lcb_m": lcb_out,
        "tcg_flood_m": (sum_delta_y / delta1) if sum_delta else 0.0,
        "n_tanks": len(rows),
        "tanks": rows,
        "formula": "KG_eff=(Δ·KG+Σδ·kg_f)/(Δ+Σδ)+FSC; FSC=Σ(ρi)/(Δ+Σδ)",
        "source": "stage 4.1 flood combination; rectangular tanks; no new equilibrium",
        "estimate": {
            "km_m": "若调用方未重算破损后 KM，此处沿用输入，属近似",
            "geometry": "舱室为矩形代理；来源须由调用方标注",
        },
    }


def solve_flooded_equilibrium(hull, ship, tanks=None, rho=RHO_SEA, **trim_kwargs):
    """阶段 4.2：破损后浮态（纵向/垂向平衡 + 小角度横倾估计）。

    组合 4.1 进水 → 目标体积与 LCG → 2.2 `solve_trim_equilibrium`。
    新 KM 用该截距处正浮 `hydrostatics_upright` 作一阶近似（纵倾影响标 estimate）。
    横倾：GM′>0 时 φ≈atan(HeelMoment/(Δ′·GM′))，HeelMoment=Σδ·y（t·m）。
    GM′≤0 时不抛错，`gm_negative=True`，`heel_deg=None`。
    """
    import geometric as M

    combo = flood_combination(ship, tanks or [])
    rho = float(rho)
    vol_target = combo["displacement_after_t"] / rho

    lcg = combo.get("lcg_solid_m")
    estimates = dict(combo.get("estimate") or {})
    if lcg is None:
        lcg = combo.get("lcb_m")
        estimates["lcg"] = "ship.lcg_m/lcb_m 缺失，纵向目标用 %r" % lcg
        if lcg is None:
            lcg = 0.0
            estimates["lcg"] = "无纵向输入，目标 LCG 取 0"

    trim_kwargs = dict(trim_kwargs)
    sol = hull.solve_trim_equilibrium(vol_target, float(lcg), **trim_kwargs)
    d = sol["d_m"]
    theta = sol["trim_rad"]

    # 正浮 KM 近似（水线截距 d）
    kz = min(z for _, poly in hull.stations for _, z in poly)
    try:
        hs = M.hydrostatics_upright(hull, d)
        km_new = hs["km_m"]
        draught = hs["draught_m"]
        estimates["km_m"] = "hydrostatics_upright(d)，未计入纵倾对 KM 的影响"
    except ValueError:
        # 纵倾很大时 d 可能仍在体内但 upright 校验失败 → 退回 integrate
        r_up = hull.integrate(0.0, min(max(d, kz + 1e-6),
                                       max(z for _, poly in hull.stations for _, z in poly)))
        vol_up = r_up["volume"]
        km_new = None
        draught = d - kz
        estimates["km_m"] = "upright 静水力不可用，KM 为 null"

    kg_eff = combo["kg_effective_m"]
    gm_prime = None if km_new is None else (km_new - kg_eff)
    heel_moment = sum(row["added_displacement_t"] * row["y_m"]
                      for row in combo["tanks"])
    heel_deg = None
    gm_negative = gm_prime is not None and gm_prime <= 0.0
    if gm_prime is not None and gm_prime > 0.0 and combo["displacement_after_t"] > 0.0:
        heel_rad = math.atan(heel_moment / (combo["displacement_after_t"] * gm_prime))
        heel_deg = math.degrees(heel_rad)

    r = hull.integrate(0.0, d, theta)
    return {
        "combination": combo,
        "target_volume_m3": vol_target,
        "target_lcg_m": float(lcg),
        "waterline_d_m": d,
        "trim_rad": theta,
        "trim_deg": sol.get("trim_deg"),
        "draught_m": draught,
        "volume_m3": r["volume"],
        "xlcb_m": r["xlcb"],
        "volume_residual_m3": sol.get("volume_residual_m3"),
        "lcb_residual_m": sol.get("lcb_residual_m"),
        "km_m": km_new,
        "kg_effective_m": kg_eff,
        "gm_m": gm_prime,
        "gm_negative": bool(gm_negative),
        "heel_moment_t_m": heel_moment,
        "tcg_flood_m": combo["tcg_flood_m"],
        "heel_deg": heel_deg,
        "rho_t_m3": rho,
        "formula": "solve_trim(V*=Δ'/ρ, LCG); KM≈upright@d; heel≈atan(M/(Δ'·GM'))",
        "source": "stage 4.2 flooded equilibrium",
        "estimate": estimates,
        "trim_solution": sol,
    }


def remaining_gz_curve(hull, kg_effective_m, target_volume_m3,
                       angles_deg=None, rho=RHO_SEA,
                       free_surface_tanks=None,
                       fsc_already_in_kg=None):
    """阶段 4.3：在（破损后）目标体积与 KG_eff 下的剩余 GZ 曲线。

    **FSC 只计一次（关键）**：
    - 若 `kg_effective_m` 来自 4.1 `flood_combination`（已含 FSC），
      必须 **`fsc_already_in_kg=True`（默认：当 free_surface_tanks 为 None 时
      视为 True）**，**不要**再传同一批舱给 `free_surface_tanks`。
    - 若 `kg_effective_m` 只是实心合成 KG（不含 FS），且要显式在 GZ 层加 FS，
      传 `free_surface_tanks` 并设 `fsc_already_in_kg=False`。
      舱室键需用 freesurface 的 `fill_fraction`（或调用
      `flood_tanks_to_fs_tanks` 映射 `flood_fraction`→`fill_fraction`）。

    禁止：kg 已含 FSC，又传入同一批舱 → **双计**。此时抛 ValueError。
    """
    import geometric as M

    if angles_deg is None:
        angles_deg = [float(a) for a in range(0, 65, 5)]

    if fsc_already_in_kg is None:
        if free_surface_tanks:
            raise ValueError(
                "传入 free_surface_tanks 时必须显式设置 fsc_already_in_kg："
                "False=kg 为实心且在 GZ 层加 FS；True=禁止再传 tanks（会双计）。")
        fsc_already_in_kg = True

    if fsc_already_in_kg and free_surface_tanks:
        raise ValueError(
            "FSC 双计风险：kg_effective_m 已含自由液面修正时，"
            "不得再传 free_surface_tanks。"
            "要么 kg=KG_solid + tanks，要么 kg=KG_eff 且 tanks=None。")

    rows = M.gz_curve(hull, float(kg_effective_m), float(target_volume_m3),
                      angles_deg, rho=rho,
                      free_surface_tanks=free_surface_tanks)
    max_gz = None
    angle_at_max = None
    range_deg = 0.0
    for row in rows:
        gz = row["gm_arm_m"]
        if max_gz is None or gz > max_gz:
            max_gz = gz
            angle_at_max = row["angle_deg"]
        if gz > 0.0:
            range_deg = max(range_deg, row["angle_deg"])
    return {
        "kg_effective_m": float(kg_effective_m),
        "target_volume_m3": float(target_volume_m3),
        "angles_deg": list(angles_deg),
        "rows": rows,
        "max_gz_m": max_gz,
        "angle_at_max_deg": angle_at_max,
        "range_deg": range_deg if (max_gz is not None and max_gz > 0.0) else 0.0,
        "fsc_already_in_kg": bool(fsc_already_in_kg),
        "formula": "GZ at equal-volume waterlines with KG (FSC applied once)",
        "source": "stage 4.3 remaining GZ",
        "estimate": {
            "deck": "甲板以上形状未外部验证，大角度 GZ 仍属 estimate",
        },
    }


def flood_tanks_to_fs_tanks(tanks):
    """damage 舱室 → freesurface 舱室（键映射，避免静默 no-op）。

    `flood_fraction` → `fill_fraction`；其余 L/b/ρ 透传。
    仅在「GZ 层加 FS、且 kg 为实心合成」时使用。
    """
    out = []
    for t in tanks or []:
        t = dict(t)
        if "fill_fraction" not in t and "flood_fraction" in t:
            t["fill_fraction"] = t["flood_fraction"]
        out.append(t)
    return out


def run_damage_scenario(hull, scenario: dict):
    """阶段 4.4：跑一个场景 → 浮态 + 剩余 GZ（可复现）。

    **FSC 只走 4.1 一次**：GZ 使用 `kg_effective_m`，**不再**传入进水舱
    作为 `free_surface_tanks`（避免双计，也避免 flood/fill 键名静默失配）。
    """
    ship = scenario["ship"]
    tanks = scenario["tanks"]
    eq = solve_flooded_equilibrium(hull, ship, tanks)
    gz = remaining_gz_curve(hull, eq["kg_effective_m"], eq["target_volume_m3"],
                            free_surface_tanks=None,
                            fsc_already_in_kg=True)
    return {
        "id": scenario.get("id", ""),
        "equilibrium": eq,
        "remaining_gz": gz,
        "stable": (not eq["gm_negative"]) and (gz["max_gz_m"] or 0.0) > 0.0,
    }
