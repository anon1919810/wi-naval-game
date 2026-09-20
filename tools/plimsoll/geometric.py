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
设横倾角 φ（绕 x 轴向右舷倾），浮心 B 在船体坐标 (y_B, z_B)，重心 G 在 (0, KG) 中线上。
世界铅垂方向在船体坐标里是 n = (0, −sinφ, cosφ)；剖面内与 n 垂直的方向是 t = (0, cosφ, sinφ)。
复原力臂即 G 到浮力作用线的垂距：

    GZ = (B − G) · t = y_B·cosφ + (z_B − KG)·sinφ

小角度展开给出 GZ ≈ (KM − KG)·φ，与 L0 的 GM 定义自洽（方箱测试会断言这一点）。
"""

from __future__ import annotations

import math

RHO_SEA = 1.025
G = 9.80665


def properties_at_waterline(hull, phi_rad, d):
    """给定横倾角与水线截距，返回浮态量（无纵倾）。"""
    r = hull.integrate(phi_rad, d)
    return r


def solve_equilibrium(hull, phi_rad, target_volume, lo=None, hi=None, tol=1e-9):
    """等体积倾斜：解出使浸没体积等于目标值的水线截距。"""
    d = hull.solve_waterline(phi_rad, target_volume, lo=lo, hi=hi, tol=tol)
    return d, hull.integrate(phi_rad, d)


def hydrostatics_upright(hull, draught, rho=RHO_SEA):
    """正浮（φ=0）静水力：体积、KB、水线面面积、I_T、BM_T。

    I_T 由水线面在 y 方向的分布积分：I_T = (2/3)∫ y³ dx —— 对剖面做，
    即逐站取水线在半宽 y_w 下的 (2/3)·y_w³，再沿 x 积分。
    这与 L0 用 C_I·L·B³/12 是同一个量的两种算法，**必须一致**。
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

    return {
        "draught_m": draught,
        "volume_m3": vol,
        "displacement_t": vol * rho,
        "kb_m": r["zb"],
        "awp_m2": r["awp"],
        "it_m4": it,
        "bm_t_m": it / vol,
        "km_m": r["zb"] + it / vol,
    }


def gz_curve(hull, kg, target_volume, angles_deg, rho=RHO_SEA):
    """大角稳性 GZ 曲线。

    每个横倾角下**重解平衡水线**（等体积），再按 GZ = y_B·cosφ + (z_B−KG)·sinφ 求力臂。
    返回 [{angle_deg, gm_arm_m, yb_m, zb_m, waterline_d_m, volume_m3}, ...]
    """
    rows = []
    for a in angles_deg:
        phi = math.radians(a)
        d, r = solve_equilibrium(hull, phi, target_volume)
        gz = r["yb"] * math.cos(phi) + (r["zb"] - kg) * math.sin(phi)
        rows.append({
            "angle_deg": float(a),
            "gm_arm_m": gz,
            "yb_m": r["yb"],
            "zb_m": r["zb"],
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
