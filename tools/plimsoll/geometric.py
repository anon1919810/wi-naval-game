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


def top_z(hull):
    """船体最高点（自船体坐标原点量）。与 `keel_z` 一起界定合法水线范围。"""
    return max(z for _, poly in hull.stations for _, z in poly)


def properties_at_waterline(hull, phi_rad, d):
    """给定横倾角与水线截距，返回浮态量（无纵倾）。"""
    r = hull.integrate(phi_rad, d)
    return r


def solve_equilibrium(hull, phi_rad, target_volume, lo=None, hi=None, tol=1e-9,
                      trim_rad=0.0):
    """等体积倾斜：解出使浸没体积等于目标值的水线截距。

    `trim_rad` 为给定的纵倾角（θ > 0 = 艏倾）。**解 θ 本身请用
    `solve_trim_equilibrium`（阶段 2.2）**：那要同时满足体积与纵向力矩，
    是二维求根，与这里的一维求 d 不是同一层的事，不要混在一起。
    """
    d = hull.solve_waterline(phi_rad, target_volume, lo=lo, hi=hi, tol=tol,
                             trim_rad=trim_rad)
    return d, hull.integrate(phi_rad, d, trim_rad)


def solve_trim_equilibrium(hull, target_volume, target_lcb, **kwargs):
    """纵倾平衡（阶段 2.2）：给定排水体积与 LCB(=LCG)，解出 (d, θ)。

    与 `solve_equilibrium` 的分工：
      · `solve_equilibrium` —— 固定 φ（及可选固定 θ），**一维**求 d，体积达标。
      · 本函数 —— 体积与纵向力矩**同时**平衡，**二维**求 (d, θ)。

    `target_lcb` 必须与 `integrate().xlcb` 使用**同一船体坐标原点**。
    θ > 0 = 艏倾。返回完整契约字典（见 `StationedHull.solve_trim_equilibrium`）。
    """
    return hull.solve_trim_equilibrium(target_volume, target_lcb, **kwargs)


def hydrostatics_upright(hull, waterline_z, rho=RHO_SEA):
    """正浮（水线水平）静水力：体积、KB、水线面面积、I_T、BM_T、KM。

    **`waterline_z` 是「船体坐标里的 z」，不是吃水。**
    型值表船体的水线在 z = 0、龙骨在 z ≈ −9.9，所以传 0.0 才对；
    传"吃水 9.9"会静默取到整只船体（含水线以上），`I_T` 归零而**不报错** ——
    这类静默错误已经踩过一次，故此处加了区间校验与零值校验。
    真实吃水（自龙骨量）在返回值的 `draught_m` 里。
    """
    kz, tz = keel_z(hull), top_z(hull)
    if not (kz <= waterline_z <= tz):
        raise ValueError(
            "waterline_z=%.3f 超出船体 z 范围 [%.3f, %.3f]。"
            "注意此参数是【船体坐标 z】而非吃水；型值表船体的水线在 z=0、龙骨在 %.1f 附近。"
            % (waterline_z, kz, tz, kz))

    r = hull.integrate(0.0, waterline_z)
    vol = r["volume"]
    if vol <= 1e-12:
        raise ValueError("水线 z=%.3f 以下没有浸没体积，检查站位剖面" % waterline_z)

    xs = [x for x, _ in hull.stations]
    it_terms = []
    for x, poly in hull.stations:
        half = _waterline_halfbeam(poly, waterline_z)
        it_terms.append((2.0 / 3.0) * half ** 3)
    it = _trapz(it_terms, xs)
    if it <= 1e-9:
        raise ValueError(
            "水线 z=%.3f 与船体不相交（逐站半宽全为 0）→ I_T 归零，BM_T 会算成 0。"
            "通常意味着水线落在剖面定义域之外。" % waterline_z)

    kb = r["zb"] - kz
    bm_t = it / vol
    return {
        "waterline_z_m": waterline_z,
        "draught_m": waterline_z - kz,     # 自龙骨量的真实吃水
        "volume_m3": vol,
        "displacement_t": vol * rho,
        "kb_m": kb,
        "awp_m2": r["awp"],
        "it_m4": it,
        "bm_t_m": bm_t,
        "km_m": kb + bm_t,
        "vcb_rel_waterline_m": r["zb"],
        "keel_z_m": kz,
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


def _waterline_halfbeam(poly, z, eps=1e-9):
    """水线 z 处的半宽（= 该高度上剖面 y 跨度的一半）。

    注意**不是**"水线以下最宽处"：水线高于舷侧时，该处的 y 跨度只会是甲板宽度。
    实现同时收集两类点：
      · 与多边形各边的交点；
      · 恰好落在水线上的顶点（水线正好切在剖面顶/底时的退化情形，
        此时严格穿越判据会把边全部跳过，必须靠顶点兜住）。
    找不到任何交点时返回 0.0 —— 调用方 `hydrostatics_upright` 会据此报错，
    不再让"水线与船体不相交"静默变成 I_T = 0。
    """
    ys = []
    for (y, zz) in poly:
        if abs(zz - z) <= eps:
            ys.append(y)
    n = len(poly)
    for i in range(n):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % n]
        if (z0 - z > eps) == (z1 - z > eps):
            continue                      # 同侧（含端点在线上），无穿越
        dz = z1 - z0
        if abs(dz) < 1e-15:
            continue
        t = (z - z0) / dz
        ys.append(y0 + t * (y1 - y0))
    if not ys:
        return 0.0
    return 0.5 * (max(ys) - min(ys))
