"""Plimsoll · 自由液面修正（FSC）· 阶段 3

问题：舱内液体（或进水）的自由液面在横倾时移动，等效于把重心抬高，
初稳性与大角稳性都被削弱。SpringSharp 对此无系统校验路径。

公式（矩形舱、横向自由液面，造船学标准）
------------------------------------------
    惯性矩   i = L · b³ / 12
             L = 舱长（沿船长，m），b = 舱宽（横向，m）
             与灌注率无关；空舱/满舱无自由液面 → i_eff = 0
    修正量   FSC = Σ(ρ_i · i_i) / Δ
             ρ_i 舱内液体密度 t/m³，Δ 船舶排水量 t
             → FSC 单位 m，**恒 ≥ 0**，加在 KG 上
    等效     KG_eff = KG + FSC ，  GM_eff = KM − KG_eff = GM − FSC

输入舱室 dict 字段见模块内 `tank_free_surface_inertia`。
本模块纯函数，不依赖几何积分器；`geometric.gz_curve` 可选接入。
"""

from __future__ import annotations

RHO_SEA = 1.025  # t/m³


def tank_free_surface_inertia(tank: dict) -> dict:
    """单舱自由液面横向惯性矩。

    必填：`length_m`（沿船长）、`beam_m`（横向宽度）。
    可选：`fluid_density_t_m3`（默认 1.025）、`fill_fraction`（默认 1.0 → 视为满舱关闭）、
          `id`。
    空舱（fill≤0）或满舱（fill≥1）→ `active=False`，`i_effective_m4=0`。
    """
    if not isinstance(tank, dict):
        raise ValueError("tank 必须是 dict，收到 %r" % type(tank))
    L = float(tank.get("length_m", 0.0))
    b = float(tank.get("beam_m", 0.0))
    rho = float(tank.get("fluid_density_t_m3", RHO_SEA))
    fill = tank.get("fill_fraction", 1.0)
    fill = float(fill)
    tank_id = tank.get("id", "")

    if L <= 0.0:
        raise ValueError("length_m 必须为正，tank=%r 收到 %r" % (tank_id, L))
    if b < 0.0:
        raise ValueError("beam_m 不能为负，tank=%r 收到 %r" % (tank_id, b))
    if rho < 0.0:
        raise ValueError("fluid_density_t_m3 不能为负，tank=%r 收到 %r" % (tank_id, rho))

    i_full = L * (b ** 3) / 12.0
    active = (b > 0.0) and (0.0 < fill < 1.0)
    # 默认 fill=1.0 表示满舱：无自由液面。调用方若只想表达「始终有自由液面」
    # 应显式传 (0,1) 开区间内的 fill_fraction。
    i_eff = i_full if active else 0.0
    return {
        "tank_id": tank_id,
        "length_m": L,
        "beam_m": b,
        "fluid_density_t_m3": rho,
        "fill_fraction": fill,
        "i_m4": i_full,
        "i_effective_m4": i_eff,
        "active": active,
        "formula": "i = L·b³/12；空/满舱 i_eff=0",
        "source": "standard free-surface inertia (rectangular tank)",
    }


def free_surface_correction(tanks, displacement_t, sea_density_t_m3=RHO_SEA):
    """FSC = Σ(ρ_i · i_eff,i) / Δ 。

    `tanks` 为舱室 dict 列表；`displacement_t` 为排水量（t）。
    `sea_density_t_m3` 仅作回显/默认，**不进入** Σ(ρ_i·i_i) 的分子
    （分子已用各舱自己的 ρ_i）。
    """
    if displacement_t is None or not (float(displacement_t) > 0.0):
        raise ValueError("displacement_t 必须为正，收到 %r" % displacement_t)
    displacement_t = float(displacement_t)
    if tanks is None:
        tanks = []
    if not isinstance(tanks, (list, tuple)):
        raise ValueError("tanks 必须是列表，收到 %r" % type(tanks))

    rows = []
    total_num = 0.0
    n_active = 0
    for t in tanks:
        row = tank_free_surface_inertia(t)
        contrib = row["fluid_density_t_m3"] * row["i_effective_m4"]
        row["rho_times_i"] = contrib
        row["fsc_contrib_m"] = contrib / displacement_t
        if row["active"]:
            n_active += 1
        total_num += contrib
        rows.append(row)

    fsc = total_num / displacement_t
    return {
        "fsc_m": fsc,
        "displacement_t": displacement_t,
        "sea_density_t_m3": float(sea_density_t_m3),
        "n_tanks": len(rows),
        "n_active": n_active,
        "sum_rho_i": total_num,
        "tanks": rows,
        "formula": "FSC = Σ(ρ_i·i_i)/Δ",
        "source": "free-surface correction; rectangular tanks",
    }


def apply_fsc(kg_m, fsc_m):
    """把 FSC 加到 KG 上。返回等效重心与 GM 变化量（fsc 使 GM 减小 fsc）。"""
    kg_m = float(kg_m)
    fsc_m = float(fsc_m)
    if fsc_m < 0.0:
        raise ValueError("fsc_m 不应为负（自由液面只降低稳性），收到 %r" % fsc_m)
    return {
        "kg_m": kg_m,
        "fsc_m": fsc_m,
        "kg_effective_m": kg_m + fsc_m,
        "gm_delta_m": -fsc_m,
        "formula": "KG_eff = KG + FSC",
        "source": "free-surface correction",
    }
