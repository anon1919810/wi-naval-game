"""Plimsoll · 阻力与功率（7.3，v0：**只做能真算的部分**）

诚实边界（先看这里）
--------------------
- **已实现**：Schoenherr 摩擦阻力（Taylor 法口径）、总阻力合成、有效功率、
  **由试航真值反解隐含剩余阻力系数**。
- **已实现**：调用方提供 Taylor-Gertler 数字化表时的四维插值；缺表/缺格
  必须传播诊断。图谱适用性与输入来源仍由调用方审核。
  缺表时 `residual_from_table()` 返回 **None + 警告**，不编造。
- **试航反解的限界**：需要假定推进系数 QPC（QM 无来源，1913 年汽轮机常见 0.5–0.6），
  该假定会**线性传递**到反解出的剩余阻力上 —— 警告里写明。

设计纪律（承 SPEC §2，含 §2.7 通用性）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；**不出现任何具体船只的常量**。
"""

from __future__ import annotations

import copy
import math

RHO_SEA = 1025.0           # kg/m³（海水，15°C 常用值）
NU_SEA_15C = 1.19e-6       # m²/s（海水 15°C 运动粘度）
KNOT_MPS = 0.514444
KNOT_MPS_EXACT = 1852.0 / 3600.0
HP_TO_KW = 0.7457
DELTA_CF_TAYLOR = 0.0004   # Taylor 法的粗糙度附加（0.4×10⁻³）


def _finite(v, what, positive=False):
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise ValueError("%s 必须是有限数值，收到 %r" % (what, v))
    try:
        number = float(v)
    except (OverflowError, ValueError) as exc:
        raise ValueError("%s 超出支持的数值范围" % what) from exc
    if not math.isfinite(number):
        raise ValueError("%s 必须是有限数值，收到 %r" % (what, v))
    if positive and number <= 0:
        raise ValueError("%s 必须为正，收到 %r" % (what, v))
    if number < 0:
        raise ValueError("%s 不能为负，收到 %r" % (what, v))
    return number


def _T(trace, key, value, formula, source, estimate=False):
    trace.append({"key": key, "value": value, "formula": formula,
                  "source": source, "estimate": estimate})


# ---------------------------------------------------------------- 摩擦阻力


def friction_coefficient(rn: float, *, method: str) -> dict:
    """Calculate a named Schoenherr friction convention.

    Args:
        rn (float): Reynolds number.
        method (str): Exact method identifier.

    Returns:
        (dict): Coefficient, method metadata, trace, and applicability warnings.
    """
    rn = _finite(rn, "rn", positive=True)
    if method == "conn_1953_schoenherr_approx":
        if rn < 1e5:
            raise ValueError("Rn=%.3e 过小，Conn 近似式不适用" % rn)
        cf = 0.4631 / math.log10(rn) ** 2.6
        formula = "Cf = 0.4631 / (log10 Re)^2.6"
        source = "Conn 1953 explicit approximation to the Karman-Schoenherr line"
        warnings = []
        if rn < 1e6 or rn > 1e9:
            warnings.append(
                "Rn=%.3e 在 Conn 1953 显式 Schoenherr 近似的既有项目区间"
                "（1e6–1e9）之外。" % rn
            )
    elif method == "schoenherr_implicit_ittc_0.242":
        if rn <= 1.0:
            raise ValueError("rn 必须大于 1 才能求解隐式 Schoenherr 方程")
        log_re = math.log10(rn)
        lower = 0.0
        upper = max(1.0, log_re / 0.242 + 1.0)
        for _ in range(90):
            middle = (lower + upper) / 2.0
            residual = 0.242 * middle + 2.0 * math.log10(middle) - log_re
            if residual > 0.0:
                upper = middle
            else:
                lower = middle
        inverse_root = (lower + upper) / 2.0
        cf = inverse_root**-2
        formula = "0.242 / sqrt(Cf) = log10(Re * Cf)"
        source = "8th ITTC proceedings, formal discussion, Table 2 convention"
        warnings = [
            "隐式方程可求解不等于湍流适用性已成立；调用方必须单独判断适用范围。"
        ]
    else:
        raise ValueError("未知摩擦线方法 %r" % method)
    trace = []
    _T(trace, "cf", cf, formula, source)
    return {
        "values": {"cf": cf, "rn": rn},
        "method": method,
        "trace": trace,
        "warnings": warnings,
    }


def schoenherr_cf(rn: float) -> dict:
    """Return the legacy Conn explicit approximation under its historical API."""
    return friction_coefficient(rn, method="conn_1953_schoenherr_approx")


def ittc1957_cf(rn: float) -> float:
    """ITTC-1957 摩擦线（用于与 Schoenherr 交叉校核）。Cf = 0.075/(lg Rn − 2)²。"""
    rn = _finite(rn, "rn", positive=True)
    return 0.075 / (math.log10(rn) - 2.0) ** 2


def friction_resistance(v_mps: float, l_wl_m: float, s_m2: float,
                        nu: float = NU_SEA_15C, rho: float = RHO_SEA,
                        delta_cf: float = 0.0,
                        method: str = "conn_1953_schoenherr_approx") -> dict:
    """摩擦阻力 Rf = ½·ρ·S·(Cf + ΔCf)·V²。"""
    v = _finite(v_mps, "v_mps", positive=True)
    L = _finite(l_wl_m, "l_wl_m", positive=True)
    S = _finite(s_m2, "s_m2", positive=True)
    nu = _finite(nu, "nu", positive=True)
    rho = _finite(rho, "rho", positive=True)
    dc = _finite(delta_cf, "delta_cf")

    rn = v * L / nu
    sc = friction_coefficient(rn, method=method)
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
            "method": method, "trace": trace, "warnings": list(sc["warnings"])}


# ---------------------------------------------------------------- 剩余阻力（图谱接入位）


def taylor_volume_ratio(length_volume_ratio: float) -> float:
    """Convert Taylor's printed L/volume^(1/3) heading to volume/L^3."""
    ratio = _finite(length_volume_ratio, "length_volume_ratio", positive=True)
    return 1.0 / ratio**3


def taylor_gertler_source_table(cr_table: dict, source_headings=None) -> dict:
    """Declare exact printed Taylor length-volume headings for strict use.

    The returned copy retains the raw stored axis and cells. Exact source
    headings are associated by index so interpolation does not inherit rounding
    from the compatibility ``volume/L^3`` axis.
    """
    if not isinstance(cr_table, dict):
        raise ValueError("cr_table must be an object")
    volumetric = cr_table.get("axes", {}).get("volumetric")
    if not isinstance(volumetric, list):
        raise ValueError("cr_table.axes.volumetric must be an array")
    if source_headings is None:
        if (cr_table.get("schema") != "plimsoll-cr-table-1"
                or "Molland" not in str(cr_table.get("source", ""))):
            raise ValueError("generic tables must provide their exact source_headings")
        source_headings = [10.0, 9.0, 8.0, 7.0, 6.0, 5.5]
    headings = [_finite(value, "source_heading", positive=True) for value in source_headings]
    if len(headings) != len(volumetric):
        raise ValueError("source_headings length must match the stored volume axis")
    for index, (stored, heading) in enumerate(zip(volumetric, headings)):
        stored_value = _finite(stored, "axes.volumetric[%d]" % index, positive=True)
        if not math.isclose(stored_value, taylor_volume_ratio(heading), rel_tol=0.0, abs_tol=5e-10):
            raise ValueError("source heading does not match stored node %d" % index)
    declared = copy.deepcopy(cr_table)
    declared["interpolation_coordinate"] = "l_over_volume_cuberoot"
    declared["source_axes"] = {"l_over_volume_cuberoot": headings}
    return declared


def _strict_taylor_residual(cr_table: dict, cp: float, bt: float,
                            volumetric: float, fn: float) -> dict:
    if cr_table.get("interpolation_coordinate") != "l_over_volume_cuberoot":
        raise ValueError(
            "strict Taylor tables must declare interpolation_coordinate="
            "'l_over_volume_cuberoot'"
        )
    axes = cr_table["axes"]
    declared_source_axis = cr_table.get("source_axes", {}).get("l_over_volume_cuberoot")
    if declared_source_axis is not None:
        if not isinstance(declared_source_axis, list) or len(declared_source_axis) != len(axes["volumetric"]):
            raise ValueError("source_axes.l_over_volume_cuberoot must align with axes.volumetric")
        volume_pairs = sorted(
            ((_finite(value, "source axis", positive=True), index)
             for index, value in enumerate(declared_source_axis)),
            key=lambda pair: pair[0],
        )
    else:
        volume_pairs = sorted(
            ((value ** (-1.0 / 3.0), index) for index, value in enumerate(axes["volumetric"])),
            key=lambda pair: pair[0],
        )
    interpolation_axes = [
        list(axes["cp"]),
        list(axes["bt"]),
        [pair[0] for pair in volume_pairs],
        list(axes["fn"]),
    ]
    values = [
        _finite(cp, "cp", positive=True),
        _finite(bt, "bt", positive=True),
        _finite(volumetric, "volumetric", positive=True) ** (-1.0 / 3.0),
        _finite(fn, "fn", positive=True),
    ]

    def locate(axis, value):
        if len(axis) < 2 or any(b <= a for a, b in zip(axis, axis[1:])):
            raise ValueError("strict Taylor axes must contain at least two increasing nodes")
        if value < axis[0] and not math.isclose(value, axis[0], rel_tol=1e-12, abs_tol=1e-12):
            return None
        if value > axis[-1] and not math.isclose(value, axis[-1], rel_tol=1e-12, abs_tol=1e-12):
            return None
        if math.isclose(value, axis[0], rel_tol=1e-12, abs_tol=1e-12):
            return 0, 0.0
        if math.isclose(value, axis[-1], rel_tol=1e-12, abs_tol=1e-12):
            return len(axis) - 2, 1.0
        for index in range(len(axis) - 1):
            if axis[index] <= value <= axis[index + 1]:
                fraction = (value - axis[index]) / (axis[index + 1] - axis[index])
                if math.isclose(fraction, 0.0, abs_tol=1e-12):
                    fraction = 0.0
                elif math.isclose(fraction, 1.0, abs_tol=1e-12):
                    fraction = 1.0
                return index, fraction
        return None

    locations = [locate(axis, value) for axis, value in zip(interpolation_axes, values)]
    if any(location is None for location in locations):
        diagnostic = {
            "code": "taylor.outside_table",
            "severity": "error",
            "path": "$",
            "message": "The request lies outside the populated Taylor table axes; strict mode does not clip.",
            "blocking": True,
        }
        return {
            "values": {"cr": None, "rr_n": None},
            "method": "taylor_gertler_source_axis_strict",
            "interpolation_coordinate": "l_over_volume_cuberoot",
            "complete": False,
            "trace": [],
            "warnings": [diagnostic["message"]],
            "diagnostics": [diagnostic],
        }
    indices = [location[0] for location in locations]
    fractions = [location[1] for location in locations]
    total = 0.0
    for mask in range(16):
        bits = [(mask >> bit) & 1 for bit in range(4)]
        weight = math.prod(
            fraction if bit else 1.0 - fraction
            for fraction, bit in zip(fractions, bits)
        )
        if weight == 0.0:
            continue
        selected = [index + bit for index, bit in zip(indices, bits)]
        volume_index = volume_pairs[selected[2]][1]
        cell = cr_table["cr"][selected[0]][selected[1]][volume_index][selected[3]]
        if cell is None:
            diagnostic = {
                "code": "taylor.missing_corner",
                "severity": "error",
                "path": "$.cr",
                "message": "A positive-weight interpolation corner is unavailable; strict mode does not renormalize.",
                "blocking": True,
            }
            return {
                "values": {"cr": None, "rr_n": None},
                "method": "taylor_gertler_source_axis_strict",
                "interpolation_coordinate": "l_over_volume_cuberoot",
                "complete": False,
                "trace": [],
                "warnings": [diagnostic["message"]],
                "diagnostics": [diagnostic],
            }
        total += weight * cell
    scale = _finite(cr_table.get("scale", 1.0), "scale", positive=True)
    coefficient = total * scale
    trace = []
    _T(
        trace,
        "cr",
        coefficient,
        "four-dimensional multilinear interpolation in (Cp, B/T, L/volume^(1/3), Fn)",
        cr_table.get("source", "declared Taylor table"),
        True,
    )
    return {
        "values": {"cr": coefficient, "rr_n": None},
        "method": "taylor_gertler_source_axis_strict",
        "interpolation_coordinate": "l_over_volume_cuberoot",
        "complete": True,
        "trace": trace,
        "warnings": [],
        "diagnostics": [],
    }


def residual_from_table(cr_table: dict | None, cp: float, bt: float,
                        volumetric: float, fn: float,
                        method: str = "legacy_volume_ratio_clip_renormalize") -> dict:
    """Taylor-Gertler 剩余阻力系数插值（四维：Cp、B/T、∇/L³、Fn）。

    `cr_table` 结构：{"axes": {"cp": [...], "bt": [...], "volumetric": [...], "fn": [...]},
                      "cr": [...嵌套列表，下标顺序同 axes...]}
    **没有表就返回 None + 警告** —— 不编造图谱数据。
    越界只做端点截断并警告（不外推，外推会静默编数据）。
    """
    if method == "taylor_gertler_source_axis_strict":
        if not cr_table:
            return {
                "values": {"cr": None, "rr_n": None},
                "method": method,
                "interpolation_coordinate": "l_over_volume_cuberoot",
                "complete": False,
                "trace": [],
                "warnings": ["Taylor table is unavailable."],
                "diagnostics": [{
                    "code": "taylor.table_missing",
                    "severity": "error",
                    "path": "$.cr_table",
                    "message": "Taylor table is unavailable.",
                    "blocking": True,
                }],
            }
        return _strict_taylor_residual(cr_table, cp, bt, volumetric, fn)
    if method != "legacy_volume_ratio_clip_renormalize":
        raise ValueError("未知 Taylor 插值方法 %r" % method)

    trace: list[dict] = []
    warnings: list[str] = []
    if not cr_table:
        _T(trace, "cr", None, "无图谱数据", "缺 Gertler Cr 表")
        warnings.append("缺 Taylor-Gertler 剩余阻力图谱（Gertler 1954 DTMB-806）："
                        "剩余阻力置空。**公开检索到的只有 OCR 乱码版本，不得照抄**；"
                        "需从正规教材附录/报告数字化后再接入 cr_table。")
        warnings.append("当前只能给出摩擦阻力；若要看总阻力，请用 "
                        "`implied_residual_from_trial()` 由试航真值反解。")
        return {"values": {"cr": None, "rr_n": None}, "trace": trace, "warnings": warnings,
                "method": method, "interpolation_coordinate": "volume_over_length_cubed",
                "complete": False, "diagnostics": []}

    axes = cr_table["axes"]
    grid = cr_table["cr"]
    keys = ("cp", "bt", "volumetric", "fn")
    vals = [float(cp), float(bt), float(volumetric), float(fn)]

    def _locate(key, x):
        ax = list(axes[key])
        if not ax:
            raise ValueError("axes.%s 为空" % key)
        if x <= ax[0]:
            return 0, 0.0, x < ax[0]
        if x >= ax[-1]:
            return len(ax) - 2, 1.0, x > ax[-1]
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
                        "误差方向未知，不代表图谱趋势。")

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
        if w == 0.0:
            continue
        cell = grid[sel[0]][sel[1]][sel[2]][sel[3]]
        if cell is None:
            skipped += 1
            continue
        wsum += w
        total += w * cell
    if wsum <= 0:
        _T(trace, "cr", None, "四维插值：全部角点缺格", cr_table.get("source", "无"), True)
        warnings.append("插值涉及的全部角点在表里都是缺格（—）：无法给出 Cr。")
        return {"values": {"cr": None, "rr_n": None}, "trace": trace, "warnings": warnings,
                "method": method, "interpolation_coordinate": "volume_over_length_cubed",
                "complete": False, "diagnostics": []}
    cr = total / wsum * scale
    if skipped:
        warnings.append("插值涉及 %d/16 个缺格（表中「—」）：已按可用角点重新归一化，"
                        "按原插值权重归一化，边界区精度下降。" % skipped)
    _T(trace, "cr", cr, "四维多线性插值 Cr(Cp, B/T, ∇/L³, Fn)%s"
       % ("，×%.0e 换算" % scale if scale != 1.0 else ""),
       cr_table.get("source", "Gertler 图谱数字化表"), True)
    return {"values": {"cr": cr, "rr_n": None}, "trace": trace, "warnings": warnings,
            "method": method, "interpolation_coordinate": "volume_over_length_cubed",
            "complete": True, "diagnostics": []}


def speed_power_curve(hull_params: dict, speeds_kn, cr_table: dict | None,
                      qpc: float = 0.55, nu: float = NU_SEA_15C,
                      rho: float = RHO_SEA, delta_cf: float = DELTA_CF_TAYLOR,
                      interpolation_method: str = "legacy_volume_ratio_clip_renormalize",
                      friction_method: str = "conn_1953_schoenherr_approx",
                      speed_conversion_method: str = "legacy_rounded_0.514444_m_s_per_kn") -> dict:
    """速度–阻力–功率曲线（Taylor-Gertler 口径）。

    `hull_params`：{lwl_m, s_m2, cp, bt, volumetric}，必须对应同一载荷；
      可附 estimate / sources / loading_condition，来源与假设由调用方负责。
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
    if speed_conversion_method == "legacy_rounded_0.514444_m_s_per_kn":
        knot_mps = KNOT_MPS
    elif speed_conversion_method == "international_knot_exact":
        knot_mps = KNOT_MPS_EXACT
    else:
        raise ValueError("未知航速换算方法 %r" % speed_conversion_method)

    speeds = [_finite(v, "speed_kn", positive=True) for v in speeds_kn]
    if not speeds or any(v <= 0 for v in speeds):
        raise ValueError("speeds_kn 必须是非空的正数序列")
    speeds = sorted(speeds)

    rows = []
    warnings = list(hull_params.get("warnings", []))
    diagnostics = []
    fr_lo, fr_hi = (cr_table or {}).get("range", {}).get("fr", [0.16, 0.58])
    clipped_lo = clipped_hi = False

    for speed_index, v_kn in enumerate(speeds):
        v = v_kn * knot_mps
        fr = v / math.sqrt(9.81 * L)
        strict = interpolation_method == "taylor_gertler_source_axis_strict"
        fr_use = fr if strict else min(max(fr, fr_lo), fr_hi)
        if fr < fr_lo and not strict:
            clipped_lo = True
        if fr > fr_hi and not strict:
            clipped_hi = True
        friction = friction_resistance(v, L, S, nu=nu, rho=rho, delta_cf=delta_cf,
                                       method=friction_method)
        rf = friction["values"]["rf_n"]
        resid = residual_from_table(cr_table, cp, bt, vol, fr_use,
                                    method=interpolation_method)
        row_warnings = list(friction["warnings"]) + list(resid["warnings"])
        row_diagnostics = []
        for diagnostic in resid.get("diagnostics", []):
            contextual = dict(diagnostic)
            contextual["source_path"] = diagnostic.get("path")
            contextual["path"] = f"$.speeds_kn[{speed_index}]"
            contextual["speed_kn"] = v_kn
            row_diagnostics.append(contextual)
        diagnostics.extend(row_diagnostics)
        if fr_use != fr:
            row_warnings.append("Fr=%.5f 超出表范围，按 %.5f 截断；误差方向未知。" % (fr, fr_use))
        cr = resid["values"]["cr"]
        if cr is None:
            rr = None
            rt = None
            row_warnings.append("剩余阻力不可用：总阻力及所需功率置空。")
        else:
            rr = residual_force(cr, v, S, rho=rho)["values"]["rr_n"]
            rt = rf + rr
        pe_kw = rt * v / 1000.0 if rt is not None else None
        warnings.extend("[%g kn] %s" % (v_kn, w) for w in row_warnings)
        rows.append({
            "speed_kn": v_kn, "fr": fr, "fr_used": fr_use,
            "rn": v * L / nu, "rf_kN": rf / 1000.0,
            "cr": cr, "rr_kN": (rr / 1000.0) if rr is not None else None,
            "rt_kN": rt / 1000.0 if rt is not None else None, "pe_kw": pe_kw,
            "pe_shp": pe_kw / HP_TO_KW if pe_kw is not None else None,
            "shp_required": pe_kw / HP_TO_KW / qpc if pe_kw is not None else None,
            "complete": cr is not None, "estimate": True,
            "methods": {"friction": friction_method, "interpolation": interpolation_method},
            "warnings": row_warnings,
            "diagnostics": row_diagnostics,
            "trace": [dict(t, estimate=bool(t["estimate"] or hull_params.get("estimate", True)))
                      for t in friction["trace"] + resid["trace"]],
        })

    trace = []
    _T(trace, "qpc_assumed", qpc, "SHP = EHP / QPC", "**推进系数为假定值，无来源**", True)
    _T(trace, "speeds", len(rows), "输入速度点数", "调用方给出")
    if clipped_lo:
        warnings.append("有速度点低于表的最低 Fr=%.2f：已端点截断（**不外推**），"
                        "低速段误差方向未知。" % fr_lo)
    if clipped_hi:
        warnings.append("有速度点高于表的最高 Fr=%.2f：已端点截断。" % fr_hi)
    if not cr_table:
        warnings.append("未提供 Cr 表：只有摩擦阻力，总阻力/功率**不完整**。")
    warnings.append("QPC=%.2f 为**假定值**（无来源）：所需 SHP 与 QPC 成反比，"
                    "引用时必须带上这一条。" % qpc)

    def available_max(key):
        return max((r[key] for r in rows if r[key] is not None), default=None)

    return {"rows": rows, "trace": trace, "warnings": warnings,
            "diagnostics": diagnostics,
            "methods": {"friction": friction_method,
                        "interpolation": interpolation_method,
                        "roughness": "declared_delta_cf_once",
                        "power": "effective_power_then_qpc_once",
                        "speed_conversion": speed_conversion_method},
            "estimate": True, "loading_condition": hull_params.get("loading_condition"),
            "input_sources": hull_params.get("sources", {}),
            "values": {"qpc": qpc, "points": len(rows),
                       "complete_points": sum(r["complete"] for r in rows),
                       "rt_max_kN": available_max("rt_kN"),
                       "pe_max_kw": available_max("pe_kw"),
                       "shp_max": available_max("shp_required")}}


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
    _T(trace, "r_total_n", r_total, "R_total = P_E / V", "由试航功率与假定 QPC 反推", True)
    _T(trace, "rr_n", rr, "Rr = R_total − Rf", "扣除已算出的摩擦阻力", True)
    _T(trace, "cr_implied", cr, "Cr = Rr / (½·ρ·S·V²)", "由试航真值反解", True)

    warnings = [
        "QPC=%.2f 是**假定值**（无来源）：Cr 随 QPC 线性变化 —— "
        "QPC 每 ±0.05，Rr 同向变化约 ±%.0f kN。结论须带此限界。" %
        (qpc, 0.05 / qpc * r_total / 1000.0),
        "本结果是**反解**（真值推导），不是从图谱预测；用于校验将来的图谱插值结果。",
    ]
    if rr <= 0:
        warnings.append("反解出 Rr ≤ 0：说明 QPC 假定过低或摩擦阻力偏大，链条自相矛盾。")

    return {"values": {"pe_kw": pe_w / 1000.0, "r_total_n": r_total, "rr_n": rr,
                       "cr_implied": cr, "v_mps": v},
            "trace": trace, "warnings": warnings}
