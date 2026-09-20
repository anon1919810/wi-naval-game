"""hullwright · L0 参数化静水力核心

设计纪律（见 docs/sps-replacement/SPEC.md）：
  - 纯函数：输入 dict → 输出 dict。不 import GUI / Unity / 网络库。
  - 零隐藏常量：核心里的每个系数要么来自输入，要么来自带引用的公式。
  - 每个输出项附 formula / source / estimate 标记，便于溯源。
  - **核心不做四舍五入**：值保持 float 全精度，显示层的取整由 CLI 负责。

L0 的船体形状模型（关键设计）
--------------------------------
没有型线图时，唯一诚实的做法是**明确声明形状假设**，而不是塞经验魔数。
本模块用「一参数水线面形状模型」：

    半宽分布   f(x) = (1 − (2x/L)²)^p ,   x ∈ [−L/2, L/2]

它只有一个参数 p，并且可以**解析**求出各阶矩（用 Γ 函数），于是：

    水线面系数      Cwp = A(p)  = ∫₀¹ (1−u²)^p du
    横向惯性矩系数  C_I = A(3p)
    纵向惯性矩      I_L = √π·B·L³·Γ(p+1) / (16·Γ(p+5/2))

给定 Cwp 即可反解 p，其余量全部随之确定——不存在"再挑几个系数"的自由度。

自洽性检验：p = 0 时 f ≡ 1（方箱），应有
    Cwp = 1,  C_I = 1,  I_T = L·B³/12,  I_L = B·L³/12
`_selfcheck_box()` 会断言这一点。

来源：形状模型与矩积分为本模块推导；KB 用 Morrish 近似；TPC / MCT1cm /
横摇周期为造船学标准公式。
"""

from __future__ import annotations

import math

RHO_SEA = 1.025  # t/m³，海水
G = 9.80665       # m/s²


# ---------------------------------------------------------------- 形状模型


def _gamma_ratio(a: float, b: float) -> float:
    """Γ(a)/Γ(b)，全程在对数域计算 —— 大参数下 Γ 本身会溢出，比值不会。"""
    return math.exp(math.lgamma(a) - math.lgamma(b))


def _A(p: float) -> float:
    """∫₀¹ (1−u²)^p du = √π·Γ(p+1) / (2·Γ(p+3/2))"""
    return 0.5 * math.sqrt(math.pi) * _gamma_ratio(p + 1.0, p + 1.5)


def shape_p_from_cwp(cwp: float) -> float:
    """由水线面系数反解形状参数 p（A(p) 对 p 单调递减，用二分法）。"""
    if not (0.30 <= cwp <= 1.0):
        raise ValueError("waterplane_coeff 必须在 0.30–1.00 之间，收到 %r" % cwp)
    lo, hi = 0.0, 100.0
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if _A(mid) > cwp:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-14:
            break
    return 0.5 * (lo + hi)


def waterplane_coeffs(cwp: float) -> dict:
    """该 Cwp 对应的形状参数与各系数（全部由同一个 p 导出）。"""
    p = shape_p_from_cwp(cwp)
    c_i = _A(3.0 * p)
    i_l_per_bl3 = (math.sqrt(math.pi) * _gamma_ratio(p + 1.0, p + 2.5) / 16.0)
    return {"p": p, "c_i": c_i, "i_l_per_B_L3": i_l_per_bl3}


# ---------------------------------------------------------------- 主计算


def compute(hull: dict) -> dict:
    """参数化静水力。

    必填：lwl_m, beam_m, draught_normal_m(或 draught_m), block_coeff
    选填：waterplane_coeff, displacement_normal_t, kg_m, roll_gyration_coeff
    """
    trace: list[dict] = []
    warnings: list[str] = []

    def T(key, value, formula, source, estimate=False):
        trace.append({"key": key, "value": value, "formula": formula,
                      "source": source, "estimate": estimate})

    L = float(hull["lwl_m"])
    B = float(hull["beam_m"])
    Td = float(hull.get("draught_normal_m", hull.get("draught_m")))
    Cb = float(hull["block_coeff"])

    for name, v in (("lwl_m", L), ("beam_m", B), ("draught_m", Td), ("block_coeff", Cb)):
        if not math.isfinite(v) or v <= 0:
            raise ValueError("%s 必须为正的有限值，收到 %r" % (name, v))
    if not (0.20 <= Cb <= 1.00):
        raise ValueError("block_coeff 应在 0.20–1.00，收到 %r" % Cb)

    cwp_supplied = hull.get("waterplane_coeff")
    if cwp_supplied is None:
        Cwp, cwp_est = 0.80, True
        warnings.append("未提供 waterplane_coeff，按典型值 0.80 计算（estimate）。"
                        "取得型线后应用几何法（L1）替换。")
    else:
        Cwp, cwp_est = float(cwp_supplied), False

    coeffs = waterplane_coeffs(Cwp)
    p, C_I = coeffs["p"], coeffs["c_i"]

    T("waterplane_shape_p", p, "solve A(p) = Cwp, A(p) = √π·Γ(p+1)/(2·Γ(p+3/2))",
      "本模块的一参数水线面形状模型 f(x) = (1−(2x/L)²)^p", cwp_est)
    T("waterplane_inertia_coeff_C_I", C_I, "C_I = A(3p)，I_T = C_I·L·B³/12",
      "同一形状模型的解析积分", cwp_est)

    # --- 排水体积与质量
    vol = L * B * Td * Cb
    mass = vol * RHO_SEA
    T("displacement_volume_m3", vol, "∇ = Lwl · B · T · Cb", "排水体积定义")
    T("displacement_t", mass, "Δ = ∇ · ρ", "ρ = 1.025 t/m³（海水）")

    given_disp = hull.get("displacement_normal_t")
    if given_disp:
        given_disp = float(given_disp)
        dev = 100.0 * (mass - given_disp) / given_disp
        T("displacement_input_t", given_disp, "—", "输入（来源见 hull.sources）")
        T("displacement_deviation_pct", dev,
          "(Δ_算 − Δ_给) / Δ_给 × 100", "一致性检查")
        if abs(dev) > 5.0:
            warnings.append(
                "算得排水量 %.0f t 与输入 %.0f t 相差 %.1f%%。L/B/T/Cb 与排水量口径不一致"
                "（常见原因：长度用了总长而非水线长，或吨位混用长吨/公吨）。请先统一口径。"
                % (mass, given_disp, dev))

    # --- 水线面与每厘米吨数
    awp = Cwp * L * B
    tpc = awp * RHO_SEA / 100.0
    T("awp_m2", awp, "Awp = Cwp · Lwl · B", "水线面面积定义", cwp_est)
    T("tpc_t_per_cm", tpc, "TPC = Awp · ρ / 100", "每厘米吃水吨数定义", cwp_est)

    # --- 浮心高（Morrish 近似）
    kb = Td * (5.0 / 6.0 - Cb / (3.0 * Cwp))
    T("kb_m", kb, "KB = T · (5/6 − Cb/(3·Cwp))",
      "Morrish 近似；方箱 Cb=Cwp=1 时退化为 T/2", cwp_est)
    if kb <= 0:
        warnings.append("KB ≤ 0：Cb/Cwp 组合超出该近似的适用范围。")

    # --- 横稳心半径
    bm_t = C_I * B * B / (12.0 * Cb * Td)
    T("bm_t_m", bm_t, "BM_T = C_I · B² / (12 · Cb · T)",
      "由 I_T/∇ 导出；方箱 C_I=1 时退化为 B²/(12T)", cwp_est)

    # --- 纵稳心半径与每厘米纵倾力矩
    i_l = coeffs["i_l_per_B_L3"] * B * L ** 3
    bm_l = i_l / vol
    mct = mass * bm_l / (100.0 * L)
    T("il_m4", i_l, "I_L = √π·B·L³·Γ(p+1)/(16·Γ(p+5/2))",
      "同一水线面形状模型的解析积分（方箱 = B·L³/12）", cwp_est)
    T("bm_l_m", bm_l, "BM_L = I_L / ∇", "纵稳心半径定义")
    T("mct1cm_t_m_per_cm", mct, "MCT1cm = Δ · BM_L / (100 · L)", "每厘米纵倾力矩")

    # --- 稳心高（需要 KG；KG 属 L2 重量分组）
    km = kb + bm_t
    T("km_m", km, "KM = KB + BM_T", "横稳心高定义")
    gm = None
    kg = hull.get("kg_m")
    if kg is not None:
        kg = float(kg)
        gm = km - kg
        kg_est = bool(hull.get("kg_is_estimate", True))
        T("kg_m", kg, "—", "输入（重量分组属 L2，此处应为估算或实测）", kg_est)
        T("gm_m", gm, "GM = KM − KG", "初稳性高定义", kg_est)
        if gm <= 0:
            warnings.append("GM ≤ 0：按此 KG 该船初稳性不足（会翻）。请核对 KG。")
    else:
        warnings.append("未提供 kg_m，无法给出 GM。KG 属重量分组（L2）；"
                        "L0 阶段请以实测或公开数据填入，并设 kg_is_estimate。")

    # --- 横摇固有周期
    fxx = float(hull.get("roll_gyration_coeff", 0.38))
    if gm is not None and gm > 0:
        k_xx = fxx * B
        t_roll = 2.0 * math.pi * k_xx / math.sqrt(G * gm)
        T("roll_gyration_m", k_xx, "k_xx = %.2f · B" % fxx,
          "经验系数（0.35–0.40 常见），可用 roll_gyration_coeff 覆盖", True)
        T("roll_period_s", t_roll, "T = 2π·k_xx / √(g·GM)",
          "横摇固有周期（小角度）", True)

    return {
        "values": {t["key"]: t["value"] for t in trace},
        "trace": trace,
        "warnings": warnings,
        "shape_model": {"waterplane_coeff": Cwp, "p": p,
                        "note": "半宽分布 f(x) = (1−(2x/L)²)^p"},
    }


def sensitivity_kg(hull: dict, kg_values) -> list[dict]:
    """KG → GM / 横摇周期 的敏感性。

    为什么必须给这个：GM = KM − KG，而 KM 是几何量（我们算得出），KG 是重量分组结果
    （L2 才做得出）。在 L2 之前 KG 只能是先验估计，所以把「结论对 KG 有多敏感」
    明明白白摊开，比给一个假装精确的 GM 诚实得多。
    """
    rows = []
    for kg in kg_values:
        h = dict(hull)
        h["kg_m"] = float(kg)
        out = compute(h)
        v = out["values"]
        rows.append({
            "kg_m": float(kg),
            "gm_m": v.get("gm_m"),
            "km_m": v["km_m"],
            "roll_period_s": v.get("roll_period_s"),
            "stable": (v.get("gm_m") or -1) > 0,
        })
    return rows


# ---------------------------------------------------------------- 自检


def _selfcheck_box() -> None:
    """方箱退化检验：Cb=Cwp=1 时必须得到教科书解析值（全精度比对）。"""
    out = compute({"lwl_m": 100.0, "beam_m": 10.0, "draught_m": 10.0,
                   "block_coeff": 1.0, "waterplane_coeff": 1.0})
    v = out["values"]
    assert abs(v["displacement_volume_m3"] - 10000.0) < 1e-9, v
    assert abs(v["awp_m2"] - 1000.0) < 1e-9, v
    assert abs(v["kb_m"] - 5.0) < 1e-9, v                              # T/2
    assert abs(v["bm_t_m"] - 10.0 ** 2 / (12 * 10)) < 1e-9, v          # B²/(12T)
    assert abs(v["il_m4"] - 10.0 * 100.0 ** 3 / 12) < 1e-6, v          # B·L³/12
    assert abs(out["shape_model"]["p"]) < 1e-6, out                      # p→0


def _selfcheck_monotonic() -> None:
    """单调性：Cwp 增大时 C_I 必须增大（形状变饱满 → 惯性矩系数变大）。"""
    prev = -1.0
    for cwp in (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00):
        c = waterplane_coeffs(cwp)
        assert c["c_i"] > prev, (cwp, c["c_i"], prev)
        prev = c["c_i"]


if __name__ == "__main__":
    _selfcheck_box()
    _selfcheck_monotonic()
    print("hullwright L0 自检通过：")
    print("  · 方箱退化 → 与解析值 T/2、B²/(12T)、B·L³/12 全精度一致")
    print("  · Cwp 单调 → C_I 单调递增")
