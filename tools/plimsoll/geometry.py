"""Plimsoll · L1 船体几何与剖面性质

L1 与 L0 的根本区别：L0 只有长宽吃水和一个方形系数，靠形状假设反推；
L1 拿**站位剖面**（station sections）做真实积分。这一层是 Plimsoll 相对
SpringSharp 的差异化所在 —— 它只知道参数，我们知道船体长什么样。

表示法
------
船体用**一组站位剖面**表示：每个站位给一个 x 坐标和一个**闭合多边形**（在 y-z 平面内）。
这正是造船业的标准做法（横剖面图）。好处是：
  · 浸没体积/浮心 = 逐站「多边形被水线切」后的面积与矩，再沿 x 积分
  · 倾斜时水线在剖面内变成一条斜线，切削规则不变 —— 大角稳性自然成立
  · Bonjean 曲线（站剖面面积 vs 水线高）只是把同一套积分换个自变量

坐标：x 沿船长（+ 指向舰艏）、y 指向右舷、z 向上，单位 m。
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------- 多边形工具


def polygon_area_moments(poly):
    """闭合多边形的面积与一阶矩（对 y、z）。

    用格林公式（鞋带公式的推广）：
        A  = ½ Σ (y_i·z_{i+1} − y_{i+1}·z_i)
        Ay = 1/6 Σ (y_i + y_{i+1})(y_i·z_{i+1} − y_{i+1}·z_i)
        Az = 1/6 Σ (z_i + z_{i+1})(y_i·z_{i+1} − y_{i+1}·z_i)
    返回 (A, Ay, Az)。A 的符号取决于绕向，调用方按需取正。
    """
    n = len(poly)
    if n < 3:
        return 0.0, 0.0, 0.0
    two_a = 0.0
    ay6 = 0.0
    az6 = 0.0
    for i in range(n):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % n]
        cross = y0 * z1 - y1 * z0
        two_a += cross
        ay6 += (y0 + y1) * cross
        az6 += (z0 + z1) * cross
    return 0.5 * two_a, ay6 / 6.0, az6 / 6.0


def clip_below_line(poly, tan_phi, d):
    """保留多边形中 z ≤ y·tanφ + d 的部分（水线以下）。

    Sutherland–Hodgman 半平面裁剪：水线在剖面平面内是一条直线
    z = y·tanφ + d（φ 为横倾角，d 为该剖面的水线截距）。
    """
    if not poly:
        return []
    out = []
    n = len(poly)

    def inside(p):
        y, z = p
        return z <= y * tan_phi + d + 1e-12

    def intersect(p, q):
        # 线性插值求与 z = y·tanφ + d 的交点
        y0, z0 = p
        y1, z1 = q
        f0 = z0 - (y0 * tan_phi + d)
        f1 = z1 - (y1 * tan_phi + d)
        denom = f0 - f1
        if abs(denom) < 1e-15:
            return p
        t = f0 / denom
        return (y0 + t * (y1 - y0), z0 + t * (z1 - z0))

    for i in range(n):
        cur = poly[i]
        prev = poly[i - 1]
        cur_in = inside(cur)
        prev_in = inside(prev)
        if cur_in:
            if not prev_in:
                out.append(intersect(prev, cur))
            out.append(cur)
        elif prev_in:
            out.append(intersect(prev, cur))
    return out


# ---------------------------------------------------------------- 站位船体


class StationedHull:
    """一组站位剖面构成的船体。stations = [(x, polygon), ...]，x 递增。"""

    def __init__(self, stations, name=""):
        if len(stations) < 3:
            raise ValueError("至少需要 3 个站位")
        self.stations = [(float(x), list(poly)) for x, poly in stations]
        self.stations.sort(key=lambda s: s[0])
        for _, poly in self.stations:
            if len(poly) < 3:
                raise ValueError("每个剖面的多边形至少 3 个点")
        self.name = name

    @property
    def length(self):
        return self.stations[-1][0] - self.stations[0][0]

    def section_under_line(self, poly, tan_phi, d):
        """单个剖面在水线以下的 (面积, Ay, Az)。"""
        clipped = clip_below_line(poly, tan_phi, d)
        if len(clipped) < 3:
            return 0.0, 0.0, 0.0
        a, ay, az = polygon_area_moments(clipped)
        if a < 0:  # 统一取正，矩随之翻转
            a, ay, az = -a, -ay, -az
        return a, ay, az

    def integrate(self, phi_rad, d, trim_rad=0.0):
        """沿 x 积分，返回该浮态下的体积、浮心、浮心纵向位置与水线面面积。

        浮态由**一张水线平面**确定，在船体坐标里写成
            z = x·tanθ + y·tanφ + d
        其中 φ = 横倾（绕 x 轴，右舷下沉为正）、θ = 纵倾。

        **θ 的符号约定：θ > 0 = 艏倾（bow down）** ——
        水线在船体坐标里朝舰艏（+x）方向抬高，故逐站截距
            d(x) = d + x·tanθ
        艏部截距更大、浸没更深。

        关键点：固定 x 时水线在剖面内仍是**一条直线** `z = y·tanφ + d(x)`，
        与纯横倾只有截距不同 —— 所以倾斜用**同一套裁剪逻辑**，
        不需要第二种几何算法。这是把纵倾做成一个参数而不是新函数的原因。

        返回 `xlcb` = 浮心纵向位置（相对船体坐标原点）。纵倾平衡要用它。
        """
        tan_phi = math.tan(phi_rad)
        tan_trim = math.tan(trim_rad)
        # 水线面是斜平面：面积元 dx·dy 要乘 sqrt(1 + tan²φ + tan²θ)
        area_factor = math.sqrt(1.0 + tan_phi * tan_phi + tan_trim * tan_trim)
        xs = [x for x, _ in self.stations]
        areas, ays, azs, mxs, chords = [], [], [], [], []
        for x, poly in self.stations:
            d_x = d + x * tan_trim
            a, ay, az = self.section_under_line(poly, tan_phi, d_x)
            areas.append(a)
            ays.append(ay)
            azs.append(az)
            mxs.append(x * a)
            w = _line_chord_halfwidth(poly, tan_phi, d_x)
            chords.append(0.0 if w is None else 2.0 * w)
        vol = _trapz(areas, xs)
        awp = _trapz(chords, xs) * area_factor
        if vol <= 1e-12:
            return {"volume": 0.0, "yb": 0.0, "zb": 0.0, "xlcb": 0.0, "awp": awp}
        return {"volume": vol,
                "yb": _trapz(ays, xs) / vol,
                "zb": _trapz(azs, xs) / vol,
                "xlcb": _trapz(mxs, xs) / vol,
                "awp": awp}

    def solve_waterline(self, phi_rad, target_volume, lo=None, hi=None, tol=1e-9,
                        trim_rad=0.0):
        """解出使浸没体积等于 target_volume 的水线截距 d（二分法）。

        这是 GZ 曲线的核心步骤：**等体积倾斜**要求每个横倾角下都重新
        找到平衡水线，船才会既不浮起也不下沉。
        `trim_rad` 传入时按给定纵倾求解（纵倾平衡本身是阶段 2.2 的事）。
        """
        if lo is None or hi is None:
            zmin = min(z for _, poly in self.stations for _, z in poly)
            zmax = max(z for _, poly in self.stations for _, z in poly)
            span = max(1.0, zmax - zmin)
            lo, hi = zmin - span, zmax + span
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            v = self.integrate(phi_rad, mid, trim_rad)["volume"]
            if v < target_volume:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)

    def solve_trim_equilibrium(self, target_volume, target_lcb, *,
                               phi_rad=0.0,
                               theta_lo=None, theta_hi=None,
                               vol_tol=1e-9, lcb_tol=1e-6,
                               max_outer=80):
        """纵倾平衡（阶段 2.2）：同时解出水线截距 d 与纵倾角 θ。

        给定目标排水体积 V* 与目标浮心纵向位置 `target_lcb`（= LCG，
        **与 `integrate().xlcb` 同一船体坐标原点**），求 (d, θ) 使

            ∇(d, θ) = V*
            xlcb(d, θ) = target_lcb

        **θ > 0 = 艏倾（bow down）** —— 与 `integrate` / `solve_waterline` 一致。

        算法：嵌套求根，**不要与 `solve_waterline` 混成一层**。
          内层：固定 θ，`solve_waterline` 二分 d 使体积达标。
          外层：残差 r(θ) = xlcb − target_lcb，在 θ 上二分；括号不足时扩大。

        直壁方箱、整段浸没时闭式解为
            d* = keel + V*/(L·B)   （与 θ 无关）
            tanθ = 12·T·LCB / L² ,  T = V*/(L·B)
        可用作测试锚点。

        返回 dict（全精度，不取整）。失败（体积不可达、LCB 在 θ 限界内
        无法变号、外层未收敛）一律 `ValueError`，不返回伪解。
        """
        if not (target_volume > 1e-12):
            raise ValueError("target_volume 必须为正，收到 %r" % target_volume)

        if theta_lo is None:
            theta_lo = math.radians(-15.0)
        if theta_hi is None:
            theta_hi = math.radians(15.0)
        if not (theta_lo < theta_hi):
            raise ValueError("需要 theta_lo < theta_hi，收到 %r >= %r"
                             % (theta_lo, theta_hi))

        def evaluate(theta):
            d = self.solve_waterline(phi_rad, target_volume,
                                     tol=vol_tol, trim_rad=theta)
            r = self.integrate(phi_rad, d, theta)
            return d, r, r["xlcb"] - target_lcb

        # 扩大 θ 括号，直到 LCB 残差变号
        hard_lo, hard_hi = math.radians(-30.0), math.radians(30.0)
        lo, hi = theta_lo, theta_hi
        d_lo, r_lo, res_lo = evaluate(lo)
        d_hi, r_hi, res_hi = evaluate(hi)
        if r_lo["volume"] <= 0.0 or r_hi["volume"] <= 0.0:
            raise ValueError(
                "目标体积 %r 在 θ 限界处不可达（积分体积非正）" % target_volume)

        expand = 0
        while res_lo * res_hi > 0.0 and expand < 6:
            expand += 1
            span = hi - lo
            new_lo = max(hard_lo, lo - span)
            new_hi = min(hard_hi, hi + span)
            if new_lo == lo and new_hi == hi:
                break
            lo, hi = new_lo, new_hi
            d_lo, r_lo, res_lo = evaluate(lo)
            d_hi, r_hi, res_hi = evaluate(hi)

        if res_lo * res_hi > 0.0:
            raise ValueError(
                "目标 LCB=%.6f 在 θ∈[%.4f°, %.4f°] 内不可达："
                "残差两端同号（r_lo=%.6e, r_hi=%.6e）。"
                "检查 target_lcb 是否与 xlcb 同一坐标原点，或放宽 θ 限界。"
                % (target_lcb, math.degrees(lo), math.degrees(hi), res_lo, res_hi))

        theta_best = 0.5 * (lo + hi)
        d_best, r_best, res_best = evaluate(theta_best)
        outer_iterations = 0
        converged = False
        for outer_iterations in range(1, max_outer + 1):
            if abs(res_best) <= lcb_tol:
                converged = True
                break
            if res_lo * res_best <= 0.0:
                hi, res_hi = theta_best, res_best
            else:
                lo, res_lo = theta_best, res_best
            if hi - lo < 1e-15:
                break
            theta_best = 0.5 * (lo + hi)
            d_best, r_best, res_best = evaluate(theta_best)

        if not converged and abs(res_best) > lcb_tol:
            raise ValueError(
                "纵倾平衡未达 LCB 容差：|残差|=%.6e > tol=%.6e，"
                "θ=%.6f°，外层迭代 %d 次"
                % (abs(res_best), lcb_tol, math.degrees(theta_best), outer_iterations))

        return {
            "d_m": d_best,
            "trim_rad": theta_best,
            "trim_deg": math.degrees(theta_best),
            "volume_m3": r_best["volume"],
            "xlcb_m": r_best["xlcb"],
            "target_volume_m3": float(target_volume),
            "target_lcb_m": float(target_lcb),
            "volume_residual_m3": r_best["volume"] - target_volume,
            "lcb_residual_m": res_best,
            "outer_iterations": outer_iterations,
            "phi_rad": float(phi_rad),
            "hydrostatics": r_best,
        }

    def bonjean_curve(self, station_index, levels):
        """Bonjean 曲线：某站位剖面面积随水线高变化（正浮、无横倾）。

        造船业的标准工具，用于快速查任意吃水下的剖面面积。
        """
        x, poly = self.stations[station_index]
        out = []
        for z in levels:
            a, _, _ = self.section_under_line(poly, 0.0, z)
            out.append((z, a))
        return out


def _trapz(ys, xs):
    total = 0.0
    for i in range(len(xs) - 1):
        total += 0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
    return total


def _line_chord_halfwidth(poly, tan_phi, d, n=200):
    """求水线 z = y·tanφ + d 在剖面内的 y 跨度的一半。

    做法：把水线与多边形各边求交，取所有交点的 y 极值。简单稳健，
    不需要依赖裁剪结果的拓扑。
    """
    ys = []
    n_pts = len(poly)
    for i in range(n_pts):
        y0, z0 = poly[i]
        y1, z1 = poly[(i + 1) % n_pts]
        f0 = z0 - (y0 * tan_phi + d)
        f1 = z1 - (y1 * tan_phi + d)
        if (f0 > 0) == (f1 > 0):
            continue                      # 同侧，无交点
        denom = f0 - f1
        if abs(denom) < 1e-15:
            continue
        t = f0 / denom
        ys.append(y0 + t * (y1 - y0))
    if len(ys) < 2:
        return None
    return 0.5 * (max(ys) - min(ys))


# ---------------------------------------------------------------- 参照船体


def make_reference_hull(L, B, T, Cb, Cwp, depth=None, n_stations=161, deck=None,
                        spacing="cosine", n_section=96):
    """生成与 L0 形状模型**完全一致**的参照船体，用于交叉验证。

    水线半宽：y(x, T) = (B/2)·f(x),  f(x) = (1−(2x/L)²)^p，p 由 Cwp 反解
              → 水线面系数恰为 A(p) = Cwp，与 L0 同源
    剖面成形：y(x, z) = (B/2)·f(x)·(z/T)^(1/q),  z ≤ T
              q 由 ∇ 反解，使 Cb = Cwp·q/(q+1)
              → q = Cb / (Cwp − Cb)
    舷侧：z > T 至甲板为直壁（wall-sided），使大角稳性可算到甲板浸没之后

    站位间距 spacing：
      "cosine"（默认）—— 站位向两端加密，x = −(L/2)·cos θ。
        必须用这个：船体两端剖面面积按 s^p（p<1）衰减，端部斜率趋于无穷，
        均匀站位下梯形积分收敛很慢（实测 161 站仍有 −0.38% 的体积误差）。
      "uniform" —— 均匀站位，仅用于对比离散误差。

    这样构造出来，L1 的 ∇、Awp、I_T、BM_T 应当与 L0 **数值一致**（同一水线面），
    只有 KB 会不同 —— L0 用 Morrish 近似，L1 是精确积分。两者的差值就是
    Morrish 近似在这个船型上的误差，本身就是有价值的结论。
    """
    if not (0 < Cb < Cwp <= 1.0):
        raise ValueError("需要 0 < Cb < Cwp ≤ 1，收到 Cb=%r Cwp=%r" % (Cb, Cwp))
    if depth is None:
        depth = T * 1.6            # 甲板高，用于大角稳性
    if deck is None:
        deck = depth
    if spacing not in ("cosine", "uniform"):
        raise ValueError("spacing 只能是 cosine 或 uniform，收到 %r" % spacing)

    p = _shape_p(Cwp)
    q = Cb / (Cwp - Cb)

    stations = []
    for i in range(n_stations):
        t = i / (n_stations - 1.0)
        if spacing == "cosine":
            x = -0.5 * L * math.cos(math.pi * t)      # 两端加密
        else:
            x = -L / 2.0 + t * L
        u = 2.0 * x / L
        s = 1.0 - u * u
        if s < 0:
            s = 0.0
        f = s ** p
        half = 0.5 * B * f
        poly = _section_polygon(half, T, q, deck, n_sec=n_section)
        stations.append((x, poly))
    return StationedHull(stations, name="reference-L=%.1f" % L)


def _section_polygon(half_beam, T, q, deck, n_sec=24):
    """按 y = half·min(1, (z/T)^(1/q)) 造剖面（右舷上行 → 甲板 → 左舷下行）。"""
    pts = []
    if half_beam <= 1e-9:
        return [(0.0, 0.0), (0.0, deck), (0.0, deck)]   # 退化截面
    for j in range(n_sec + 1):
        z = T * j / n_sec
        y = half_beam * (z / T) ** (1.0 / q)
        pts.append((y, z))
    if deck > T:                     # 直壁段
        for j in range(1, 5):
            z = T + (deck - T) * j / 4.0
            pts.append((half_beam, z))
    top = pts[-1][1]
    pts.append((-half_beam, top))    # 甲板从左舷回来
    for (y, z) in reversed(pts[:-1]):
        pts.append((-y, z))
    return pts


def _shape_p(cwp):
    """与 L0 同一套反解：A(p) = √π·Γ(p+1)/(2·Γ(p+3/2)) = Cwp。"""
    def A(p):
        return 0.5 * math.sqrt(math.pi) * math.exp(
            math.lgamma(p + 1.0) - math.lgamma(p + 1.5))
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if A(mid) > cwp:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-14:
            break
    return 0.5 * (lo + hi)
