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
