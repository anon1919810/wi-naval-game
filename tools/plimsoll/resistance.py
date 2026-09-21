"""Plimsoll · 阻力与功率（7.3，v0：**只做能真算的部分**）

诚实边界（先看这里）
--------------------
- **已实现**：Schoenherr 摩擦阻力（Taylor 法口径）、总阻力合成、有效功率、
  **由试航真值反解隐含剩余阻力系数**。
- **未实现**：Taylor-Gertler 剩余阻力图谱插值 —— Gertler (1954) DTMB-806 的 Cr 图谱
  只在教科书附录里，公开检索到的都是 OCR 乱码版本；**照乱码抄数就是编数据**，
  故本模块留出 `cr_table` 接入位（四维插值已实现并有测试），图谱数字化后直接插上。
  缺表时 `residual_from_table()` 返回 **None + 警告**，不编造。
- **试航反解的限界**：需要假定推进系数 QPC（QM 无来源，1913 年汽轮机常见 0.5–0.6），
  该假定会**线性传递**到反解出的剩余阻力上 —— 警告里写明。

设计纪律（承 SPEC §2，含 §2.7 通用性）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；**不出现任何具体船只的常量**。
"""

from __future__ import annotations

import math

RHO_SEA = 1025.0           # kg/m³（海水，15°C 常用值）
NU_SEA_15C = 1.19e-6       # m²/s（海水 15°C 运动粘度）
KNOT_MPS = 0.514444
HP_TO_KW = 0.7457
DELTA_CF_TAYLOR = 0.0004   # Taylor 法的粗糙度附加（0.4×10⁻³）


def _finite(v, what, positive=False):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ValueError("%s 必须是有限数值，收到 %r" % (what, v))
    if positive and v <= 0:
        raise ValueError("%s 必须为正，收到 %r" % (what, v))
    if v < 0:
        raise ValueError("%s 不能为负，收到 %r" % (what, v))
    return float(v)


def _T(trace, key, value, formula, source, estimate=False):
    trace.append({"key": key, "value": value, "formula": formula,
                  "source": source, "estimate": estimate})


# ---------------------------------------------------------------- 摩擦阻力


def schoenherr_cf(rn: float) -> dict:
    """Schoenherr（桑海）摩擦阻力系数：Cf = 0.4631 / (lg Rn)^2.6。

    Taylor 法配的就是这条线（不是 ITTC-1957）。适用 Rn ≈ 1e6 – 1e9，
    超出区间只给警告不拒绝（量级仍有参考价值）。
    """
    rn = _finite(rn, "rn", positive=True)
    if rn < 1e5:
        raise ValueError("Rn=%.3e 过小，摩擦线不适用" % rn)
    cf = 0.4631 / (math.log10(rn) ** 2.6)
    trace = []
    _T(trace, "cf", cf, "Cf = 0.4631 / (lg Rn)^2.6",
       "Schoenherr（桑海）近似式，Rn=1e6–1e9（Taylor-Gertler 法配套摩擦线）")
    warnings = []
    if rn < 1e6 or rn > 1e9:
        warnings.append("Rn=%.3e 在 Schoenherr 适用区间（1e6–1e9）之外，Cf 仅作量级参考。" % rn)
    return {"values": {"cf": cf, "rn": rn}, "trace": trace, "warnings": warnings}


def ittc1957_cf(rn: float) -> float:
    """ITTC-1957 摩擦线（用于与 Schoenherr 交叉校核）。Cf = 0.075/(lg Rn − 2)²。"""
    rn = _finite(rn, "rn", positive=True)
    return 0.075 / (math.log10(rn) - 2.0) ** 2


def friction_resistance(v_mps: float, l_wl_m: float, s_m2: float,
                        nu: float = NU_SEA_15C, rho: float = RHO_SEA,
                        delta_cf: float = 0.0) -> dict:
    """摩擦阻力 Rf = ½·ρ·S·(Cf + ΔCf)·V²。"""
    v = _finite(v_mps, "v_mps", positive=True)
    L = _finite(l_wl_m, "l_wl_m", positive=True)
    S = _finite(s_m2, "s_m2", positive=True)
    nu = _finite(nu, "nu", positive=True)
    rho = _finite(rho, "rho", positive=True)
    dc = _finite(delta_cf, "delta_cf")

    rn = v * L / nu
    sc = schoenherr_cf(rn)
    cf = sc["values"]["cf"]
    cf_total = cf + dc
    rf = 0.5 * rho * S * cf_total * v * v

    trace = list(sc["trace"])
    _T(trace, "rn", rn, "Rn = V·L / ν", "定义式（ν=%.3e 由调用方给出）" % nu)
    if dc:
        _T(trace, "cf_total", cf_total, "Cf,total = Cf + ΔCf",
           "ΔCf=%.1e（粗糙度附加；Taylor 法取 0.4e-3）" % dc, True)
    _T(trace, "rf_n", rf, "Rf = ½·ρ·S·Cf,total·V²", "摩擦阻力定义式")

    return {"values": {"rn": rn, "cf": cf, "cf_total": cf_total, "rf_n": rf,
                       "rf_kN": rf / 1000.0},
            "trace": trace, "warnings": list(sc["warnings"])}


# ---------------------------------------------------------------- 剩余阻力（图谱接入位）


def residual_from_table(cr_table: dict | None, cp: float, bt: float,
                        volumetric: float, fn: float) -> dict:
    """Taylor-Gertler 剩余阻力系数插值（四维：Cp、B/T、∇/L³、Fn）。

    `cr_table` 结构：{"axes": {"cp": [...], "bt": [...], "volumetric": [...], "fn": [...]},
                      "cr": [...嵌套列表，下标顺序同 axes...]}
    **没有表就返回 None + 警告** —— 不编造图谱数据。
    越界只做端点截断并警告（不外推，外推会静默编数据）。
    """
    trace: list[dict] = []
    warnings: list[str] = []
    if not cr_table:
        _T(trace, "cr", None, "无图谱数据", "缺 Gertler Cr 表")
        warnings.append("缺 Taylor-Gertler 剩余阻力图谱（Gertler 1954 DTMB-806）："
                        "剩余阻力置空。**公开检索到的只有 OCR 乱码版本，不得照抄**；"
                        "需从正规教材附录/报告数字化后再接入 cr_table。")
        warnings.append("当前只能给出摩擦阻力；若要看总阻力，请用 "
                        "`implied_residual_from_trial()` 由试航真值反解。")
        return {"values": {"cr": None, "rr_n": None}, "trace": trace, "warnings": warnings}

    axes = cr_table["axes"]
    grid = cr_table["cr"]
    keys = ("cp", "bt", "volumetric", "fn")
    vals = [float(cp), float(bt), float(volumetric), float(fn)]

    def _locate(key, x):
        ax = list(axes[key])
        if not ax:
            raise ValueError("axes.%s 为空" % key)
        if x <= ax[0]:
            return 0, 0.0, True
        if x >= ax[-1]:
            return len(ax) - 2, 1.0, True
        for i in range(len(ax) - 1):
            if ax[i] <= x <= ax[i + 1]:
                t = 0.0 if ax[i + 1] == ax[i] else (x - ax[i]) / (ax[i + 1] - ax[i])
                return i, t, False
        raise ValueError("无法在 axes.%s 定位 %r" % (key, x))

    idx, frac, clipped = [], [], []
    for k, x in zip(keys, vals):
        i, t, c = _locate(k, x)
        idx.append(i); frac.append(t); clipped.append(c)
    if any(clipped):
        warnings.append("插值点在图谱边界之外：已按端点截断（**不外推**），"
                        "结果偏保守且不代表图谱趋势。")

    # 四维多线性插值。**表里有缺格（"—"）→ 用可用角点重新归一化**，
    # 不当 0 也不崩（当 0 会把阻力压低；崩掉会让整条链不可用）。
    total = 0.0
    wsum = 0.0
    skipped = 0
    scale = cr_table.get("scale", 1.0)     # 表内单位换算（如 CR×1000 → scale=1e-3）
    for m in range(16):
        bits = [(m >> b) & 1 for b in range(4)]
        w = 1.0
        sel = []
        for b, bit in enumerate(bits):
            w *= (frac[b] if bit else (1.0 - frac[b]))
            sel.append(idx[b] + bit)
        cell = grid[sel[0]][sel[1]][sel[2]][sel[3]]
        if cell is None:
            skipped += 1
            continue
        wsum += w
        total += w * cell
    if wsum <= 0:
        _T(trace, "cr", None, "四维插值：全部角点缺格", cr_table.get("source", "无"), True)
        warnings.append("插值涉及的全部角点在表里都是缺格（—）：无法给出 Cr。")
        return {"values": {"cr": None, "rr_n": None}, "trace": trace, "warnings": warnings}
    cr = total / wsum * scale
    if skipped:
        warnings.append("插值涉及 %d/16 个缺格（表中「—」）：已按可用角点重新归一化，"
                        "等权近似，边界区精度下降。" % skipped)
    _T(trace, "cr", cr, "四维多线性插值 Cr(Cp, B/T, ∇/L³, Fn)%s"
       % ("，×%.0e 换算" % scale if scale != 1.0 else ""),
       cr_table.get("source", "Gertler 图谱数字化表"), True)
    return {"values": {"cr": cr, "rr_n": None}, "trace": trace, "warnings": warnings}


def speed_power_curve(hull_params: dict, speeds_kn, cr_table: dict | None,
                      qpc: float = 0.55, nu: float = NU_SEA_15C,
                      rho: float = RHO_SEA, delta_cf: float = DELTA_CF_TAYLOR) -> dict:
    """速度–阻力–功率曲线（Taylor-Gertler 口径）。

    `hull_params`：{lwl_m, s_m2, cp, bt, volumetric}（**船型参数必须用史实口径**，
      理由见 cases/queen_mary_1913_resistance.json 的 _note：模型型线的 Cp 受 Cm 异常污染）。
    `cr_table`：plimsoll-cr-table-1 案例（缺则只剩摩擦阻力，并为每条给出警告）。
    `qpc`：推进系数（**假定值**），SHP = EHP / QPC；本函数会把该假定写进 warnings。
    Fr 超出表范围（0.16–0.58）时**端点截断**并警告，不外推。
    """
    L = _finite(hull_params.get("lwl_m"), "lwl_m", positive=True)
    S = _finite(hull_params.get("s_m2"), "s_m2", positive=True)
    cp = _finite(hull_params.get("cp"), "cp", positive=True)
    bt = _finite(hull_params.get("bt"), "bt", positive=True)
    vol = _finite(hull_params.get("volumetric"), "volumetric", positive=True)
    qpc = _finite(qpc, "qpc", positive=True)

    speeds = [float(v) for v in speeds_kn]
    if not speeds or any(v <= 0 for v in speeds):
        raise ValueError("speeds_kn 必须是非空的正数序列")
    speeds = sorted(speeds)

    rows = []
    warnings = []
    fr_lo, fr_hi = (cr_table or {}).get("range", {}).get("fr", [0.16, 0.58])
    clipped_lo = clipped_hi = False

    for v_kn in speeds:
        v = v_kn * KNOT_MPS
        fr = v / math.sqrt(9.81 * L)
        fr_use = min(max(fr, fr_lo), fr_hi)
        if fr < fr_lo:
            clipped_lo = True
        if fr > fr_hi:
            clipped_hi = True
        rf = friction_resistance(v, L, S, nu=nu, rho=rho, delta_cf=delta_cf)["values"]["rf_n"]
        resid = residual_from_table(cr_table, cp, bt, vol, fr_use)
        cr = resid["values"]["cr"]
        if cr is None:
            rr = None
            rt = rf
        else:
            rr = residual_force(cr, v, S, rho=rho)["values"]["rr_n"]
            rt = rf + rr
        pe_kw = rt * v / 1000.0
        rows.append({
            "speed_kn": v_kn, "fr": fr, "fr_used": fr_use,
            "rn": v * L / nu, "rf_kN": rf / 1000.0,
            "cr": cr, "rr_kN": (rr / 1000.0) if rr is not None else None,
            "rt_kN": rt / 1000.0, "pe_kw": pe_kw, "pe_shp": pe_kw / HP_TO_KW,
            "shp_required": pe_kw / HP_TO_KW / qpc,
        })

    trace = []
    _T(trace, "qpc_assumed", qpc, "SHP = EHP / QPC", "**推进系数为假定值，无来源**", True)
    _T(trace, "speeds", len(rows), "输入速度点数", "调用方给出")
    if clipped_lo:
        warnings.append("有速度点低于表的最低 Fr=%.2f：已端点截断（**不外推**），"
                        "低速段阻力偏保守。" % fr_lo)
    if clipped_hi:
        warnings.append("有速度点高于表的最高 Fr=%.2f：已端点截断。" % fr_hi)
    if not cr_table:
        warnings.append("未提供 Cr 表：只有摩擦阻力，总阻力/功率**不完整**。")
    warnings.append("QPC=%.2f 为**假定值**（无来源）：所需 SHP 与 QPC 成反比，"
                    "引用时必须带上这一条。" % qpc)

    return {"rows": rows, "trace": trace, "warnings": warnings,
            "values": {"qpc": qpc, "points": len(rows),
                       "rt_max_kN": max(r["rt_kN"] for r in rows),
                       "pe_max_kw": max(r["pe_kw"] for r in rows),
                       "shp_max": max(r["shp_required"] for r in rows)}}


def residual_force(cr: float, v_mps: float, s_m2: float, rho: float = RHO_SEA) -> dict:
    """剩余阻力 Rr = ½·ρ·S·Cr·V²（把系数变成力）。"""
    cr = _finite(cr, "cr")
    v = _finite(v_mps, "v_mps", positive=True)
    S = _finite(s_m2, "s_m2", positive=True)
    rr = 0.5 * rho * S * cr * v * v
    trace = []
    _T(trace, "rr_n", rr, "Rr = ½·ρ·S·Cr·V²", "剩余阻力定义式")
    return {"values": {"rr_n": rr, "rr_kN": rr / 1000.0}, "trace": trace, "warnings": []}


# ---------------------------------------------------------------- 合成与功率


def effective_power(r_total_n: float, v_mps: float) -> dict:
    """有效功率（EHP）P = R·V。"""
    r = _finite(r_total_n, "r_total_n")
    v = _finite(v_mps, "v_mps", positive=True)
    p_w = r * v
    trace = []
    _T(trace, "pe_kw", p_w / 1000.0, "P_E = R·V", "有效功率定义式")
    _T(trace, "pe_shp", p_w / 1000.0 / HP_TO_KW, "shp = kW / 0.7457", "1 hp = 745.7 W")
    return {"values": {"pe_kw": p_w / 1000.0, "pe_shp": p_w / 1000.0 / HP_TO_KW},
            "trace": trace, "warnings": []}


def implied_residual_from_trial(shp: float, v_kn: float, rf_n: float,
                                s_m2: float, qpc: float = 0.55,
                                rho: float = RHO_SEA) -> dict:
    """由试航真值**反解**隐含剩余阻力系数 Cr —— 真值推导，不是查表。

    链：SHP × QPC = EHP → R_total = EHP / V → Rr = R_total − Rf → Cr = Rr/(½ρSV²)。
    ⚠️ QPC（推进系数）对 QM **无来源**，1913 年汽轮机常取 0.5–0.6；
      该假定会线性传递到 Cr 上 —— 结论必须带着这个限界引用。
    """
    shp = _finite(shp, "shp", positive=True)
    v_kn = _finite(v_kn, "v_kn", positive=True)
    rf = _finite(rf_n, "rf_n")
    S = _finite(s_m2, "s_m2", positive=True)
    qpc = _finite(qpc, "qpc", positive=True)

    v = v_kn * KNOT_MPS
    pe_w = shp * HP_TO_KW * 1000.0 * qpc
    r_total = pe_w / v
    rr = r_total - rf
    cr = rr / (0.5 * rho * S * v * v)

    trace = []
    _T(trace, "pe_kw", pe_w / 1000.0, "P_E = SHP × QPC × 0.7457",
       "试航 SHP=%.0f，QPC=%.2f（**假定值，无来源**）" % (shp, qpc), True)
    _T(trace, "r_total_n", r_total, "R_total = P_E / V", "由试航功率反推")
    _T(trace, "rr_n", rr, "Rr = R_total − Rf", "扣除已算出的摩擦阻力", True)
    _T(trace, "cr_implied", cr, "Cr = Rr / (½·ρ·S·V²)", "由试航真值反解", True)

    warnings = [
        "QPC=%.2f 是**假定值**（QM 无来源）：Cr 随 QPC 线性变化 —— "
        "QPC 每 ±0.05，Rr 约 ∓%.0f kN。结论须带此限界。" % (qpc, 0.05 / qpc * (r_total - rf) / 1000.0),
        "本结果是**反解**（真值推导），不是从图谱预测；用于校验将来的图谱插值结果。",
    ]
    if rr <= 0:
        warnings.append("反解出 Rr ≤ 0：说明 QPC 假定过低或摩擦阻力偏大，链条自相矛盾。")

    return {"values": {"pe_kw": pe_w / 1000.0, "r_total_n": r_total, "rr_n": rr,
                       "cr_implied": cr, "v_mps": v},
            "trace": trace, "warnings": warnings}
