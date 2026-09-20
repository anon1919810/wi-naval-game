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

    def integrate(self, phi_rad, d, waterline_offset=None):
        """沿 x 积分，返回该浮态下的体积与浮心。

        waterline_offset: 可选。水线截距 d 通常是「随 x 变化」的（纵倾），
        这里先用常量 d（无纵倾）。纵倾留待后续。
        返回 dict：volume, yb, zb, awp（水线面面积，按倾斜平面换算）
        """
        tan_phi = math.tan(phi_rad)
        cos_phi = math.cos(phi_rad)
        xs = [x for x, _ in self.stations]
        areas, ays, azs, chords = [], [], [], []
        for x, poly in self.stations:
            a, ay, az = self.section_under_line(poly, tan_phi, d)
            areas.append(a)
            ays.append(ay)
            azs.append(az)
            # 水线在剖面内的 y 跨度（用于水线面面积）
            w = _line_chord_halfwidth(poly, tan_phi, d)
            if w is None:
                chords.append(0.0)
            else:
                chords.append(2.0 * w)
        vol = _trapz(areas, xs)
        my = _trapz(ays, xs)
        mz = _trapz(azs, xs)
        awp = _trapz(chords, xs) / cos_phi if cos_phi > 1e-9 else 0.0
        if vol <= 1e-12:
            return {"volume": 0.0, "yb": 0.0, "zb": 0.0, "awp": 0.0}
        return {"volume": vol, "yb": my / vol, "zb": mz / vol, "awp": awp}

    def solve_waterline(self, phi_rad, target_volume, lo=None, hi=None, tol=1e-9):
        """解出使浸没体积等于 target_volume 的水线截距 d（二分法）。

        这是 GZ 曲线的核心步骤：**等体积倾斜**要求每个横倾角下都重新
        找到平衡水线，船才会既不浮起也不下沉。
        """
        if lo is None or hi is None:
            zmin = min(z for _, poly in self.stations for _, z in poly)
            zmax = max(z for _, poly in self.stations for _, z in poly)
            lo, hi = zmin - abs(zmin) - 1.0, zmax * 2.0 + 1.0
        # 保证体积单调（d 越大浸没越多）
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            v = self.integrate(phi_rad, mid)["volume"]
            if v < target_volume:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return 0.5 * (lo + hi)

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
