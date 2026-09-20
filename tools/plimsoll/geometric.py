"""Plimsoll · L1 几何法静水力与大角稳性

与 L0 的分工：
  L0  参数化 —— 只有 L/B/T/Cb/Cwp，靠形状假设反推。快，但对船体形状是"猜"的。
  L1  几何法 —— 有站位剖面，逐站积分。慢，但静水力是**算出来的**。

本模块提供两件 SpringSharp 没有的东西：
  1. **真实静水力**：由剖面几何积分得到 ∇、KB、Awp、I_T、BM_T，不用经验近似。
  2. **大角稳性 GZ 曲线**：等体积倾斜 —— 每个横倾角下重解平衡水线，
     再算复原力臂。战损进水的船横倾很大，小角度 GM 此时早已失效。

GZ 的定义（须与实现严格一致）
------------------------------
**坐标系约定（易错，务必看清）**：站位剖面用船体自身坐标，本例中 **水线在 z = 0、向上为正**，
龙骨在 z ≈ −9.9。所以积分出的浮心 z 是"相对水线"的（为负）。
而造船学的 **KB / KG 都是自龙骨向上量**。两者差一个龙骨高度，
实现里统一用 `keel_z` 换算 —— 不换算会把 KB 算成负数。

设横倾角 φ（绕 x 轴向右舷倾），浮心 B 在船体坐标 (y_B, z_B_rel)，重心 G 在中线上、
自龙骨高 KG。世界铅垂方向在船体坐标里是 n = (0, −sinφ, cosφ)；
剖面内与 n 垂直的方向是 t = (0, cosφ, sinφ)。复原力臂即 G 到浮力作用线的垂距：

    GZ = (B − G) · t = y_B·cosφ + (z_B − KG)·sinφ      （z_B 与 KG 都自龙骨量）

小角度展开给出 GZ ≈ (KM − KG)·φ，与初稳性高的定义自洽（方箱测试会断言这一点）。
"""

from __future__ import annotations

import math

RHO_SEA = 1.025
G = 9.80665


def keel_z(hull):
    """船体最低点（自船体坐标原点量）。KB / KG 都以此为基准。

    ⚠️ 这个换算必须做：站位剖面的 z 是以**水线为 0**给的（龙骨在负值），
    而 KB / KG 是**自龙骨向上**量。不做换算，装了真实型线后 KB 会算成负数，
    KM 随之偏小，GM 直接变成负的（船"不稳定"）—— 这个错误在
    合成船体上不会暴露，因为那种船体的龙骨恰好在 z=0。
    """
    return min(z for _, poly in hull.stations for _, z in poly)


def properties_at_waterline(hull, phi_rad, d):
    """给定横倾角与水线截距，返回浮态量（无纵倾）。"""
    r = hull.integrate(phi_rad, d)
    return r


def solve_equilibrium(hull, phi_rad, target_volume, lo=None, hi=None, tol=1e-9):
    """等体积倾斜：解出使浸没体积等于目标值的水线截距。"""
    d = hull.solve_waterline(phi_rad, target_volume, lo=lo, hi=hi, tol=tol)
    return d, hull.integrate(phi_rad, d)


def hydrostatics_upright(hull, draught, rho=RHO_SEA):
    """正浮（φ=0）静水力：体积、KB、水线面面积、I_T、BM_T、KM。

    KB / KM 以**龙骨**为基准（见 `keel_z` 的说明）。
    I_T 由水线面在 y 方向的分布积分：I_T = (2/3)∫ y³ dx —— 逐站取水线半宽，
    再沿 x 积分。这与 L0 用 C_I·L·B³/12 是同一个量的两种算法。
    """
    r = hull.integrate(0.0, draught)
    vol = r["volume"]
    if vol <= 1e-12:
        raise ValueError("水线 %.3f m 以下没有浸没体积，检查站位剖面" % draught)

    xs = [x for x, _ in hull.stations]
    it_terms = []
    for x, poly in hull.stations:
        half = _waterline_halfbeam(poly, draught)
        it_terms.append((2.0 / 3.0) * half ** 3)
    it = _trapz(it_terms, xs)

    kb = r["zb"] - keel_z(hull)
    bm_t = it / vol
    return {
        "draught_m": draught,
        "volume_m3": vol,
        "displacement_t": vol * rho,
        "kb_m": kb,
        "awp_m2": r["awp"],
        "it_m4": it,
        "bm_t_m": bm_t,
        "km_m": kb + bm_t,
        "vcb_rel_waterline_m": r["zb"],
        "keel_z_m": keel_z(hull),
    }


def gz_curve(hull, kg, target_volume, angles_deg, rho=RHO_SEA):
    """大角稳性 GZ 曲线。

    每个横倾角下**重解平衡水线**（等体积），再按
    `GZ = y_B·cosφ + (z_B − KG)·sinφ` 求力臂；`kg` 自龙骨量，
    故 `z_B` 也要用 `keel_z` 换算（见模块 docstring）。
    """
    kz = keel_z(hull)
    rows = []
    for a in angles_deg:
        phi = math.radians(a)
        d, r = solve_equilibrium(hull, phi, target_volume)
        zb_keel = r["zb"] - kz
        gz = r["yb"] * math.cos(phi) + (zb_keel - kg) * math.sin(phi)
        rows.append({
            "angle_deg": float(a),
            "gm_arm_m": gz,
            "yb_m": r["yb"],
            "zb_m": zb_keel,
            "waterline_d_m": d,
            "volume_m3": r["volume"],
        })
    return rows


def gz_initial_slope(gz_rows):
    """由 GZ 曲线在 0° 附近求初始斜率 ≈ GM（用于与 L0 的 GM 交叉验证）。"""
    by = {round(r["angle_deg"], 6): r["gm_arm_m"] for r in gz_rows}
    if 0.0 not in by:
        raise ValueError("GZ 曲线必须包含 0°")
    for a in (5.0, 10.0, 4.0, 2.0, 1.0):
        if a in by:
            return by[a] / math.sin(math.radians(a))
    raise ValueError("GZ 曲线缺少足够小的角度用于求初始斜率")


def _trapz(ys, xs):
    total = 0.0
    for i in range(len(xs) - 1):
        total += 0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
    return total


def _waterline_halfbeam(poly, z):
    """正浮水线 z 处的半宽（取水线以下最宽处，即该 z 处截面的半宽）。"""
    ys = []
    n = len(poly)
    for i in range(n):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % n]
        if (z0 - z > 0) == (z1 - z > 0):
            continue
        if abs(z1 - z0) < 1e-15:
            continue
        t = (z - z0) / (z1 - z0)
        ys.append(abs(y0 + t * (y1 - y0)))
    return max(ys) if ys else 0.0
