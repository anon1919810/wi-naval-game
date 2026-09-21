"""Plimsoll · Engines 页（v0：主机/锅炉/燃料/续航 —— **阻力模型不在本模块**）

SPS Engines 页（COVERAGE.md §2.6）：Max/Cruise speed、轴数、**Friction/Wave resistance**、
Power (hp/kW)（输出）、锅炉/主机型式、Range、%Coal、Engine factor（输入）、
Engine weight / Bunker / Displacement factor（输出）。

Plimsoll 的做法（诚实记录）
---------------------------
- **有源就给**：轴数、主机/锅炉型式、设计/试航功率、燃料（煤/油）、续航。
  shp → kW 用 `1 hp = 745.7 W`（机械马力国际定义，精确）。
- **量级校核（estimate）**：海军部系数 `C = Δ^(2/3)·V³ / P`（Δ 吨、V 节、P shp）
  —— 经典经验式，只用来判断功率–航速是否自洽，**不当设计依据**；
  同时给出最大航速对应的 Froude 数。
- **明确不做**：Friction/Wave resistance、Engine weight、Displacement factor
  —— 阻力需要 Holtrop-Mennen / Taylor（PLAN **7.3**，独立项），主机重量无来源。
  本模块只在 warnings 里点名，**不估算、不冒充**。
- Engine factor（SPS 输入）是 SPS 自有的经验系数，无公开定义 → 不做。

设计纪律（承 SPEC §2，含 §2.7 通用性）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；**不出现任何具体船只的常量**。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-engines-1"
HP_TO_KW = 0.7457          # 1 hp = 745.7 W（机械马力国际定义）
KNOT_MPS = 0.514444        # 1 kn = 0.514444 m/s
G = 9.81


def _finite(v, what, positive=False):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ValueError("%s 必须是有限数值，收到 %r" % (what, v))
    if positive and v <= 0:
        raise ValueError("%s 必须为正，收到 %r" % (what, v))
    if v < 0:
        raise ValueError("%s 不能为负，收到 %r" % (what, v))
    return float(v)


def _int_positive(v, what):
    if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
        raise ValueError("%s 必须为正整数，收到 %r" % (what, v))
    return v


def _T(trace, key, value, formula, source, estimate=False):
    trace.append({"key": key, "value": value, "formula": formula,
                  "source": source, "estimate": estimate})


def compute(case: dict) -> dict:
    """Engines 案例 → 功率换算、燃料构成、续航、量级校核。"""
    trace: list[dict] = []
    warnings: list[str] = []

    if case.get("schema") != SCHEMA:
        raise ValueError("schema 必须是 %s，收到 %r" % (SCHEMA, case.get("schema")))

    shafts = _int_positive(case.get("shafts"), "shafts")
    _T(trace, "shafts", shafts, "输入", case.get("shafts_source", "无来源"))

    # ---------------- 功率（每个导出量只算一次：trace 与 values 共用同一变量）
    p_design = case.get("power_design_shp")
    p_trial = case.get("power_trial_shp")
    p_design_kw = p_trial_kw = None
    for key, val, src_key in (("power_design_shp", p_design, "power_design_source"),
                              ("power_trial_shp", p_trial, "power_trial_source")):
        if val is None:
            warnings.append("%s 未提供：置空。" % key)
            continue
        v = _finite(val, key, positive=True)
        kw = v * HP_TO_KW
        if key == "power_design_shp":
            p_design, p_design_kw = v, kw
        else:
            p_trial, p_trial_kw = v, kw
        _T(trace, key, v, "输入", case.get(src_key, "无来源"))
        _T(trace, key.replace("_shp", "_kw"), kw, "kW = shp × 0.7457",
           "1 hp = 745.7 W（机械马力国际定义）")

    # ---------------- 航速
    v_max = case.get("max_speed_kn")
    v_cruise = case.get("cruise_speed_kn")
    for key in ("max_speed_kn", "cruise_speed_kn"):
        val = v_max if key == "max_speed_kn" else v_cruise
        if val is None:
            warnings.append("%s 未提供：置空（巡航速度常无来源）。" % key)
            continue
        vv = _finite(val, key, positive=True)
        if key == "max_speed_kn":
            v_max = vv
        else:
            v_cruise = vv
        _T(trace, key, vv, "输入",
           case.get(key.replace("_kn", "_source"), "无来源"))

    # ---------------- 燃料
    coal = case.get("coal_t")
    oil = case.get("oil_t")
    coal = _finite(coal, "coal_t") if coal is not None else None
    oil = _finite(oil, "oil_t") if oil is not None else None
    fuel_total = None
    pct_coal = None
    if coal is None and oil is None:
        warnings.append("燃料（coal_t / oil_t）均未给：Bunker 置空。")
    else:
        fuel_total = (coal or 0.0) + (oil or 0.0)
        _T(trace, "bunker_total_t", fuel_total, "Bunker = 煤 + 油",
           case.get("fuel_source", "无来源"))
        if coal is not None and fuel_total > 0:
            pct_coal = 100.0 * coal / fuel_total
            _T(trace, "pct_coal", pct_coal, "%Coal = 煤 / (煤 + 油) ×100",
               case.get("fuel_source", "无来源"))
        else:
            pct_coal = None
        if coal is not None:
            _T(trace, "coal_t", coal, "输入", case.get("fuel_source", "无来源"))
        if oil is not None:
            _T(trace, "oil_t", oil, "输入", case.get("fuel_source", "无来源"))

    # ---------------- 续航
    rng = case.get("range_nm")
    rng_kn = case.get("range_at_speed_kn")
    if rng is None:
        warnings.append("range_nm 未提供：续航置空。")
    else:
        _T(trace, "range_nm", _finite(rng, "range_nm", positive=True), "输入",
           case.get("range_source", "无来源"))
        if rng_kn is None:
            warnings.append("range_at_speed_kn 未提供：续航未注明对应航速，可比性差。")

    # ---------------- 量级校核（estimate）
    disp = case.get("displacement_normal_t")
    adm = None
    if disp and v_max and (p_design or p_trial):
        p = p_design or p_trial
        adm = (float(disp) ** (2.0 / 3.0)) * float(v_max) ** 3 / float(p)
        _T(trace, "admiralty_coeff", adm, "C = Δ^(2/3)·V³ / P（Δ 吨、V 节、P shp）",
           "海军部系数经验式，仅作功率–航速量级校核", True)
        warnings.append("海军部系数 %.0f 只是量级校核（经验式，随船型差异极大），"
                        "不能当设计依据。" % adm)
    if v_max and disp and case.get("lwl_m"):
        v_mps = float(v_max) * KNOT_MPS
        fn = v_mps / math.sqrt(G * float(case["lwl_m"]))
        _T(trace, "froude_at_max", fn, "Fn = V(m/s) / √(g·Lwl)", "最大航速对应的 Froude 数", True)

    # ---------------- 明确不做
    warnings.append("Friction/Wave resistance 未实现：需要 Holtrop-Mennen / Taylor 阻力模型"
                    "（PLAN 7.3，独立项），本模块不估算。")
    if case.get("engine_weight_t") is None:
        warnings.append("Engine weight 未提供：主机重量无来源，置空（不估算）。")
    else:
        _T(trace, "engine_weight_t", _finite(case["engine_weight_t"], "engine_weight_t",
                                             positive=True), "输入",
           case.get("engine_weight_source", "无来源"))

    values = {
        "shafts": shafts,
        "power_design_shp": p_design, "power_trial_shp": p_trial,
        "power_design_kw": p_design_kw, "power_trial_kw": p_trial_kw,
        "max_speed_kn": v_max, "cruise_speed_kn": v_cruise,
        "coal_t": coal, "oil_t": oil, "bunker_total_t": fuel_total,
        "pct_coal": pct_coal,
        "range_nm": rng, "range_at_speed_kn": rng_kn,
        "admiralty_coeff": adm,
        "engine_weight_t": case.get("engine_weight_t"),
    }
    return {"values": values, "trace": trace, "warnings": warnings}


def sps_view(result: dict) -> dict:
    """compute() 结果 → SPS Engines 页视图（缺项保持 None）。"""
    v = result["values"]
    return {
        "max_speed_kn": v["max_speed_kn"], "cruise_speed_kn": v["cruise_speed_kn"],
        "shafts": v["shafts"],
        "power_hp": v["power_design_shp"], "power_kw": v["power_design_kw"],
        "friction_resistance": None, "wave_resistance": None,   # 明确不做（PLAN 7.3）
        "range_nm": v["range_nm"], "pct_coal": v["pct_coal"],
        "engine_weight_t": v["engine_weight_t"], "bunker_t": v["bunker_total_t"],
        "_not_implemented": ["friction_resistance", "wave_resistance", "displacement_factor"],
    }
