"""Plimsoll · Hull 页派生量（v0：湿面积 / 长宽比 / 自然航速）

SPS Hull 页缺的三项（COVERAGE.md §2.1）：**Wetted surface area**、**Length:Beam**、
**Natural Speed**。本模块补齐，且**两条来源都给**：

- Wetted surface：
  1) **参数法（L0）** Mumford 经验式 `S = L·(1.7·T + Cb·B)` —— 只需主尺度，estimate；
  2) **几何法（L1）** 逐站把剖面裁到水线以下、取湿周长（**扣除贴在水线上的闭合边**），
     沿 x 梯形积分 —— 有型线时优先用这个。
- Length:Beam：`Lwl / B`，定义式，无估计成分。
- Natural Speed：**两个口径并列**（不二选一，因为 SPS 的常数没有公开出处）：
  1) **Froude 兴波速度（有源）** `V = √(g·L/2π)` —— 波长等于水线长时的深水波速，
     即教科书 hull speed（1.34·√L_ft / 2.428·√L_m）；
  2) **SPS 惯例（estimate）** `V = k·√L_ft`，k 默认 1.09（S/L ratio ~1.1，
     兴波阻力显著上升的门槛；**1.09 这个常数无公开文献出处，标 estimate**）。
  同时输出 `froude_at_natural`，方便对着 Froude 数判断是否可信。

设计纪律（承 SPEC §2，含 §2.7 通用性）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；**不出现任何具体船只的常量**。
"""

from __future__ import annotations

import math

G = 9.81                    # m/s²
KNOT_MPS = 0.514444         # 1 kn = 0.514444 m/s（国际定义 1852 m/h）
FT_PER_M = 3.280839895      # 1 m = 3.280839895 ft（1 ft = 0.3048 m 精确反算）
SLR_SPS = 1.09              # SPS 惯例常数（kn / √ft）—— 无公开出处，estimate


def _req(hull: dict, key: str) -> float:
    v = hull.get(key)
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0:
        raise ValueError("hull.%s 缺失或不是正的有限值，收到 %r" % (key, v))
    return float(v)


def _draught(hull: dict) -> float:
    for k in ("draught_normal_m", "draught_m"):
        if hull.get(k) is not None:
            return _req(hull, k)
    raise ValueError("hull 缺 draught_normal_m / draught_m")


def _T(trace, key, value, formula, source, estimate=False):
    trace.append({"key": key, "value": value, "formula": formula,
                  "source": source, "estimate": estimate})


# ---------------------------------------------------------------- 长宽比


def form_ratios(hull: dict) -> dict:
    """Length:Beam（SPS Hull 页输出项）。定义式，无估计成分。"""
    L = _req(hull, "lwl_m")
    B = _req(hull, "beam_m")
    T = _draught(hull)
    trace = []
    _T(trace, "length_beam", L / B, "L:B = Lwl / B", "定义式")
    _T(trace, "beam_draught", B / T, "B:T = B / T", "定义式（附带，非 SPS 字段）")
    return {
        "values": {"length_beam": L / B, "beam_draught": B / T},
        "trace": trace,
        "warnings": [],
    }


# ---------------------------------------------------------------- 自然航速


def natural_speed(hull: dict, slr: float = SLR_SPS) -> dict:
    """自然航速：Froude 兴波速度（有源）+ SPS 惯例（estimate），两个口径并列。"""
    L = _req(hull, "lwl_m")
    L_ft = L * FT_PER_M
    trace = []
    warnings = []

    # 1) Froude：λ = Lwl 的深水波速
    hull_speed_mps = math.sqrt(G * L / (2.0 * math.pi))
    hull_speed_kn = hull_speed_mps / KNOT_MPS
    _T(trace, "hull_speed_kn", hull_speed_kn,
       "V = √(g·Lwl / 2π) ÷ 0.514444",
       "深水波速 λ=Lwl（Froude 兴波速度，教科书 hull speed；等价 1.34·√L_ft）")

    # 2) SPS 惯例
    natural_kn = slr * math.sqrt(L_ft)
    _T(trace, "natural_speed_kn", natural_kn, "V = k·√Lwl(ft)，k=%.3f" % slr,
       "SPS 惯例常数（S/L ratio≈1.1 门槛）；**该常数无公开文献出处**", True)

    froude_at_natural = (natural_kn * KNOT_MPS) / math.sqrt(G * L)
    _T(trace, "froude_at_natural", froude_at_natural,
       "Fn = V(m/s) / √(g·Lwl)", "由上面两项推得", True)

    warnings.append("Natural speed 的 k=%.3f 是 SPS 惯例常数，无公开文献出处（标 estimate）；"
                    "可信度更高的口径是同表给出的 hull_speed_kn（Froude 兴波速度）。" % slr)
    if froude_at_natural > 0.45:
        warnings.append("自然航速对应 Fn=%.3f 偏高：该船已超出排水型船的常规区间，"
                        "经验式可能不适用。" % froude_at_natural)

    return {
        "values": {"natural_speed_kn": natural_kn, "hull_speed_kn": hull_speed_kn,
                   "froude_at_natural": froude_at_natural, "slr": slr,
                   "lwl_ft": L_ft},
        "trace": trace,
        "warnings": warnings,
    }


# ---------------------------------------------------------------- 湿面积


def wetted_surface_parametric(hull: dict, coeff: float = 1.7) -> dict:
    """Mumford 经验式湿面积（L0，只需主尺度）。"""
    L = _req(hull, "lwl_m")
    B = _req(hull, "beam_m")
    T = _draught(hull)
    Cb = _req(hull, "block_coeff")
    S = L * (coeff * T + Cb * B)
    trace = []
    _T(trace, "wetted_surface_m2", S, "S = L·(c·T + Cb·B)，c=%.2f" % coeff,
       "Mumford 经验式（造船学教科书；与 ∇/T + 1.7·L·T 同形）", True)
    return {
        "values": {"wetted_surface_m2": S, "coeff": coeff},
        "trace": trace,
        "warnings": ["湿面积经验式精度约 ±5%~10%，且对形状不敏感；有型线时优先用 "
                     "`wetted_surface_from_hull()`（逐站湿周长积分）。"],
    }


def waterline_length(hull, z: float = 0.0, eps: float = 1e-6) -> dict:
    """从型线真算水线长：在给定水线高 z 上，船体剖面半宽 > 0 的纵向跨度。

    端点用相邻站线性插值到零（而不是取整站位置），否则会系统性偏短一个站距。
    ⚠️ 口径提醒：型线文件的 z=0 是**该型线自己的设计水线**（QM 型线对应满载吃水 9.9 m），
    所以这里算出的不是案例里"正常吃水"的 Lwl，两者不可直接混用 —— 已在 warnings 里点明。
    """
    import geometric as GM

    xs = [float(x) for x, _ in hull.stations]
    hb = [GM._waterline_halfbeam(poly, z) for _, poly in hull.stations]

    idx = [i for i, v in enumerate(hb) if v > eps]
    trace = []
    if not idx:
        _T(trace, "lwl_at_z_m", 0.0, "无剖面与 z=%.3f 相交" % z, "型线逐站半宽")
        return {"values": {"lwl_at_z_m": 0.0, "z_m": z},
                "trace": trace,
                "warnings": ["水线 z=%.3f 与船体无交点：船体定义或水线高有误。" % z]}

    i0, i1 = idx[0], idx[-1]

    def _cross(i, j):
        """在 i（内侧有宽度）与 j（外侧为零）之间线性插值零点。"""
        xi, xj = xs[i], xs[j]
        vi, vj = hb[i], hb[j]
        if abs(vi - vj) < 1e-12:
            return xi
        return xi + (xj - xi) * vi / (vi - vj)

    lo = _cross(i0, i0 - 1) if i0 > 0 else xs[i0]
    hi = _cross(i1, i1 + 1) if i1 < len(xs) - 1 else xs[i1]
    length = hi - lo

    warnings = []
    _T(trace, "lwl_at_z_m", length, "L = x(半宽→0, 艉) → x(半宽→0, 艏)，端点线性插值",
       "型线逐站半宽（%d 站）" % len(xs))
    if i0 == 0 or i1 == len(xs) - 1:
        warnings.append("水线两端在首/末站仍有宽度：船体在该处未收拢，"
                        "水线长被站端点截断（偏短）。")
    warnings.append("此水线长对应 z=%.3f（型线自己的设计水线，QM 型线 = 满载吃水），"
                    "与案例里『正常吃水』的 Lwl 口径不同，勿直接混用。" % z)

    return {"values": {"lwl_at_z_m": length, "z_m": z}, "trace": trace, "warnings": warnings}


def form_coefficients(hull, z: float = 0.0) -> dict:
    """从型线真算船型系数（L1 几何法）——7.3 阻力模型的地基。

    给出：排水体积 ∇、最大横剖面面积 Am、浮心纵向位置 LCB、
    **Cb / Cp / Cm**。全部由逐站剖面在水线 z 以下积分得到，不查文献、不猜。

    口径（必须写清，否则系数没有意义）：
      Cp = ∇ / (Am · Lwl)      —— L 取**该水线处的水线长**（见 waterline_length）
      Cm = Am / (Bwl · T)      —— Bwl 为该水线处的最大水线宽，T = z − 龙骨 z
      Cb = ∇ / (Lwl · Bwl · T)
    ⚠️ 型线的 z=0 是**它自己的设计水线**（QM 型线 = 满载吃水 9.9），
      所以这里得到的系数是满载口径，与案例里正常吃水（8.5）的 Cb 不是一回事。
    """
    import geometry as GE
    import geometric as GM

    xs, areas, hbs = [], [], []
    for x, poly in hull.stations:
        sub = GE.clip_below_line(poly, 0.0, z)
        a = abs(GE.polygon_area_moments(sub)[0]) if len(sub) >= 3 else 0.0
        xs.append(float(x))
        areas.append(a)
        hbs.append(GM._waterline_halfbeam(poly, z))

    vol = GM._trapz(areas, xs)
    if vol <= 0:
        raise ValueError("水线 z=%.3f 处排水体积为 0：船体或水线高有误" % z)
    moment = GM._trapz([x * a for x, a in zip(xs, areas)], xs)
    lcb_x = moment / vol

    am = max(areas)
    x_am = xs[areas.index(am)]
    b_wl = 2.0 * max(hbs)
    keel = min(zz for _, poly in hull.stations for _, zz in poly)
    T = z - keel
    L = waterline_length(hull, z)["values"]["lwl_at_z_m"]
    if b_wl <= 0 or T <= 0 or L <= 0:
        raise ValueError("无法定出 Bwl/T/Lwl（B=%.3f T=%.3f L=%.3f）" % (b_wl, T, L))

    cb = vol / (L * b_wl * T)
    cp = vol / (am * L)
    cm = am / (b_wl * T)

    trace = []
    _T(trace, "volume_m3", vol, "∇ = ∫ A(x) dx（逐站剖面面积，梯形）", "型线积分")
    _T(trace, "midship_area_m2", am, "Am = max A(x) @ x=%.2f" % x_am, "型线积分")
    _T(trace, "lcb_x_m", lcb_x, "LCB = ∫ x·A(x) dx / ∇", "型线积分（船体 x 坐标）")
    _T(trace, "beam_wl_m", b_wl, "Bwl = 2·max 水线半宽", "型线")
    _T(trace, "draught_at_wl_m", T, "T = 水线 z − 龙骨 z", "型线")
    _T(trace, "cb", cb, "Cb = ∇ / (Lwl·Bwl·T)", "定义式（L 取该水线长）")
    _T(trace, "cp", cp, "Cp = ∇ / (Am·Lwl)", "定义式（L 取该水线长）")
    _T(trace, "cm", cm, "Cm = Am / (Bwl·T)", "定义式")

    return {
        "values": {"volume_m3": vol, "midship_area_m2": am, "x_of_max_area_m": x_am,
                   "lcb_x_m": lcb_x, "beam_wl_m": b_wl, "draught_at_wl_m": T,
                   "lwl_m": L, "cb": cb, "cp": cp, "cm": cm},
        "trace": trace,
        "warnings": ["以上为 z=%.3f 处的系数（型线的设计水线口径），"
                     "与案例『正常吃水』的系数口径不同。" % z],
    }


def half_angle_of_entrance(hull, z: float = 0.0, at_frac: float = 0.20) -> dict:
    """半进流角 iE（度）—— 只给一个**显式约定**，不假装只有一个口径。

    约定：在艏部水线上取「半宽 = at_frac × 最大半宽」的那一点，用相邻站中心差分求
    dhb/dx，iE = atan(|dhb/dx|)。默认 at_frac = 0.20（≈ NavCad 等采用的
    「离中线 Bwl/10」口径）。

    ⚠️ 诚实前提：**半进流角没有统一定义**（艏端切线、B/10、B/4 各派都有），
    不同口径的数不可直接互比。这里的值只在我们自己这条链里自洽。
    ⚠️ 若水线在艏端**没有收拢**（型线被截断，首尾站仍有宽度）→ 取不到该点，
    **返回 None + 警告**，不编一个角度出来。
    """
    import geometric as GM

    xs = [float(x) for x, _ in hull.stations]
    hb = [GM._waterline_halfbeam(poly, z) for _, poly in hull.stations]
    hb_max = max(hb) if hb else 0.0
    target = at_frac * hb_max

    trace = []
    warnings = []
    if hb_max <= 0:
        _T(trace, "iE_deg", None, "无半宽数据", "型线")
        return {"values": {"iE_deg": None, "at_frac": at_frac}, "trace": trace,
                "warnings": ["水线 z=%.3f 处无半宽：无法定半进流角。" % z]}

    # 从艏端（x 最大）向内找第一个低于 target 的站，与相邻站线性定位
    n = len(xs)
    idx = None
    for i in range(n - 1, -1, -1):
        if hb[i] < target:
            idx = i
            break
    if idx is None:
        _T(trace, "iE_deg", None, "艏端未收拢，取不到 %.0f%% 半宽点" % (100 * at_frac), "型线")
        warnings.append("艏端水线未收拢（首站半宽 %.2f m 已 ≥ 目标 %.2f m）："
                        "型线在艏部被截断，半进流角无法确定 —— 不编造角度。"
                        % (hb[-1], target))
        return {"values": {"iE_deg": None, "at_frac": at_frac, "hb_max_m": hb_max},
                "trace": trace, "warnings": warnings}

    i = min(max(idx, 1), n - 2)
    slope = (hb[i + 1] - hb[i - 1]) / (xs[i + 1] - xs[i - 1])
    ie = math.degrees(math.atan(abs(slope)))
    _T(trace, "iE_deg", ie,
       "iE = atan(|dhb/dx|) @ 半宽=%.0f%%·半宽max (x≈%.1f)" % (100 * at_frac, xs[i]),
       "型线差分（约定：离中线 Bwl/10 量法；**口径不唯一**）", True)
    warnings.append("半进流角口径不唯一（艏端切线 / B/10 / B/4 各派不同），"
                    "本值按 at_frac=%.2f 约定，跨来源比较前先对齐口径。" % at_frac)
    return {"values": {"iE_deg": ie, "at_frac": at_frac, "hb_max_m": hb_max,
                       "x_at_m": xs[i]}, "trace": trace, "warnings": warnings}


def _submerged_girth(poly, tan_phi: float, d: float, eps: float = 1e-9) -> float:
    """湿周长：裁到水线以下的多边形周长，**扣除贴在水线上的闭合边**（那一段不湿）。

    `poly` 是 (y, z) 剖面；水线为 z = tan_phi·y + d。
    """
    n = len(poly)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        (y1, z1) = poly[i]
        (y2, z2) = poly[(i + 1) % n]
        on = lambda y, z: abs(z - (tan_phi * y + d)) < eps
        if on(y1, z1) and on(y2, z2):
            continue  # 这段是裁剪补出来的水线闭合边，不是船壳
        total += math.hypot(y2 - y1, z2 - z1)
    return total


def wetted_surface_from_hull(hull, phi_rad: float = 0.0, d: float = 0.0) -> dict:
    """几何法湿面积（L1）：逐站湿周长沿 x 梯形积分。

    `hull` 是 `geometry.StationedHull`（有 .stations = [(x, poly), ...]）。
    横倾/纵倾可由 `phi_rad`、`d` 给出（默认正浮、设计水线）。
    """
    import geometry as GE

    tan_phi = math.tan(phi_rad)
    xs, gs = [], []
    for x, poly in hull.stations:
        sub = GE.clip_below_line(poly, tan_phi, d)
        xs.append(float(x))
        gs.append(_submerged_girth(sub, tan_phi, d) if len(sub) >= 3 else 0.0)

    order = sorted(range(len(xs)), key=lambda i: xs[i])
    xs = [xs[i] for i in order]
    gs = [gs[i] for i in order]

    S = 0.0
    for i in range(len(xs) - 1):
        S += 0.5 * (gs[i] + gs[i + 1]) * (xs[i + 1] - xs[i])

    trace = []
    _T(trace, "wetted_surface_m2", S,
       "S = ∫ g(x) dx（g = 逐站湿周长，梯形积分，%d 站）" % len(xs),
       "型值表逐站积分（形状来源见型线文件；若型线本身是 estimate 则此项同标 estimate）")
    return {
        "values": {"wetted_surface_m2": S, "stations": len(xs)},
        "trace": trace,
        "warnings": [],
    }


def sps_view(length_beam: float | None = None, wetted_m2: float | None = None,
             natural_kn: float | None = None) -> dict:
    """把上面几项排成 SPS Hull 页的输出行（缺项置 None，不冒充 0）。"""
    return {
        "length_beam": length_beam,
        "wetted_surface_m2": wetted_m2,
        "natural_speed_kn": natural_kn,
    }
