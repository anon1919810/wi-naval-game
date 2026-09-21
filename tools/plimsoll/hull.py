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
