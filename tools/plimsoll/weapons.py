"""Plimsoll · Weapons 页（v0：鱼雷/水雷/深弹 + Misc weight 五分区）

SPS Weapons 页（COVERAGE.md §2.4）：鱼雷（主/副：数量/直径/长/布置）、水雷、深弹、
**Misc weight 五分区**（Hull-Below / Hull-Above water / On deck / Above Deck / Void）。

Plimsoll 的做法（诚实记录）
---------------------------
- **鱼雷**：只算有源的部分 —— 管数、携带数、直径、战斗部总装药 = 携带数 × 单雷装药。
  **单雷全重未采集** → 置 None + 警告，不用装药冒充全重（两者差一个数量级）。
- **水雷 / 深弹**：本舰未装备 → 显式 0 并带来源（这是史实，不是"没填"）。
  若案例没给，则置 None + 警告（区分「确实为 0」与「没数据」）。
- **Misc weight 五分区**：SPS 里是纯输入，本模块做三件事：分区小计、占排水量比例、
  **与 L2 的接口警告** —— 分区重量没有 KG（重心高），不能直接喂给 `weights.py` 合成 KG，
  必须补 kg_m 才行（否则又是"绿着错着"）。
- 射程/航速（4,500 yd @ 45 kn 等）**来源冲突**（维基 vs MaritimeQuest），案例里并列记录。

设计纪律（承 SPEC §2，含 §2.7 通用性）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；**不出现任何具体船只的常量**。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-weapons-1"
MISC_ZONES = ("hull_below_water", "hull_above_water", "on_deck", "above_deck", "void")
ZONE_LABEL = {"hull_below_water": "Hull below water", "hull_above_water": "Hull above water",
              "on_deck": "On deck", "above_deck": "Above deck", "void": "Void"}


def _finite(v, what, positive=False, allow_zero=False):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ValueError("%s 必须是有限数值，收到 %r" % (what, v))
    if positive and v <= 0:
        raise ValueError("%s 必须为正，收到 %r" % (what, v))
    if v < 0:
        raise ValueError("%s 不能为负，收到 %r" % (what, v))
    return float(v)


def _int_nonneg(v, what):
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise ValueError("%s 必须为非负整数，收到 %r" % (what, v))
    return v


def _T(trace, key, value, formula, source, estimate=False):
    trace.append({"key": key, "value": value, "formula": formula,
                  "source": source, "estimate": estimate})


# ---------------------------------------------------------------- 鱼雷


def torpedoes(case: dict) -> dict:
    """鱼雷清单：管数/携带数/直径/装药总重；单雷全重缺则置 None。"""
    trace: list[dict] = []
    warnings: list[str] = []

    if case.get("schema") != SCHEMA:
        raise ValueError("schema 必须是 %s，收到 %r" % (SCHEMA, case.get("schema")))

    bats = case.get("torpedo_batteries")
    if not isinstance(bats, list) or not bats:
        raise ValueError("torpedo_batteries 必须是非空数组")

    rows = []
    total_tubes = 0
    total_carried = 0
    total_expl = 0.0
    have_expl = False

    for b in bats:
        bid = b.get("id")
        if not bid:
            raise ValueError("每个鱼雷组都要有 id，收到 %r" % (b,))
        tubes = _int_nonneg(b.get("tubes"), "%s.tubes" % bid)
        carried = _int_nonneg(b.get("carried"), "%s.carried" % bid)
        dia = b.get("diameter_mm")
        dia = _finite(dia, "%s.diameter_mm" % bid, positive=True) if dia is not None else None
        length = b.get("length_m")
        length = _finite(length, "%s.length_m" % bid, positive=True) if length is not None else None
        warhead = b.get("warhead_kg")
        warhead = _finite(warhead, "%s.warhead_kg" % bid) if warhead is not None else None
        unit_w = b.get("unit_weight_t")
        unit_w = _finite(unit_w, "%s.unit_weight_t" % bid, positive=True) if unit_w is not None else None

        src = b.get("source", "无来源")
        est = bool(b.get("estimate", False))
        expl_total = (carried * warhead / 1000.0) if warhead is not None else None
        if expl_total is not None:
            have_expl = True
            total_expl += expl_total
        if unit_w is None:
            warnings.append("鱼雷组 %s 未提供单雷全重：鱼雷总重置空（不能用装药重代替）。" % bid)
        if length is None:
            warnings.append("鱼雷组 %s 未提供雷长（SPS 字段）。" % bid)

        rows.append({
            "id": bid, "tubes": tubes, "carried": carried,
            "diameter_mm": dia, "length_m": length, "warhead_kg": warhead,
            "unit_weight_t": unit_w,
            "weight_total_t": (carried * unit_w) if unit_w is not None else None,
            "explosive_total_t": expl_total,
            "arrangement": b.get("arrangement"), "estimate": est, "source": src,
        })
        total_tubes += tubes
        total_carried += carried
        _T(trace, "%s.tubes" % bid, tubes, "输入", src, est)
        _T(trace, "%s.carried" % bid, carried, "输入", src, est)
        if expl_total is not None:
            _T(trace, "%s.explosive_total_t" % bid, expl_total,
               "W = 携带数 × 单雷装药", src, est)

    _T(trace, "tubes_total", total_tubes, "Σ 管数", "鱼雷组合计")
    _T(trace, "carried_total", total_carried, "Σ 携带数", "鱼雷组合计")
    if have_expl:
        _T(trace, "explosive_total_t", total_expl, "Σ 各组装药", "鱼雷组合计", True)

    return {
        "values": {"tubes_total": total_tubes, "carried_total": total_carried,
                   "explosive_total_t": total_expl if have_expl else None},
        "batteries": rows,
        "trace": trace,
        "warnings": warnings,
    }


# ---------------------------------------------------------------- 水雷 / 深弹


def ordnance(case: dict) -> dict:
    """水雷 / 深弹数量。没给就是**没数据**（None），给了 0 才是"确实不装备"。"""
    trace: list[dict] = []
    warnings: list[str] = []
    out = {}
    for key in ("mines", "depth_charges"):
        blk = case.get(key)
        if blk is None:
            warnings.append("%s 未给：置空（不是 0）。本舰若确实不装备，请显式给 0 并带来源。" % key)
            out[key] = None
            continue
        n = _int_nonneg(blk.get("count"), "%s.count" % key)
        src = blk.get("source", "无来源")
        out[key] = {"count": n, "source": src}
        _T(trace, "%s.count" % key, n, "输入", src, bool(blk.get("estimate", False)))
        if n == 0:
            warnings.append("%s = 0（按案例来源：不装备）。" % key)
    return {"values": out, "trace": trace, "warnings": warnings}


# ---------------------------------------------------------------- Misc weight


def misc_weight(case: dict) -> dict:
    """SPS Misc weight 五分区：小计、占排水量比例，以及与 L2 的接口警告。"""
    trace: list[dict] = []
    warnings: list[str] = []

    zones = case.get("misc_weight") or {}
    rows = []
    total = 0.0
    for z in MISC_ZONES:
        blk = zones.get(z)
        if blk is None:
            warnings.append("分区 %s 未给：置空（不计入小计）。" % z)
            rows.append({"zone": z, "label": ZONE_LABEL[z], "mass_t": None})
            continue
        m = _finite(blk.get("mass_t"), "misc_weight.%s.mass_t" % z)
        src = blk.get("source", "无来源")
        rows.append({"zone": z, "label": ZONE_LABEL[z], "mass_t": m,
                     "estimate": bool(blk.get("estimate", False)), "source": src})
        total += m
        _T(trace, "misc.%s" % z, m, "输入", src, bool(blk.get("estimate", False)))

    _T(trace, "misc_total_t", total, "Σ 五分区", "Misc weight 合计")

    disp = case.get("displacement_normal_t")
    pct = None
    if disp:
        pct = 100.0 * total / float(disp)
        _T(trace, "misc_pct_displacement", pct, "杂项重量 / 排水量 ×100", "占比检查", True)
        if pct > 25.0:
            warnings.append("Misc weight 占排水量 %.1f%% 偏高（>25%%）：检查分区口径是否重复计入"
                            "（如船体钢料既在 hull 组又在这里）。" % pct)

    warnings.append("Misc weight 分区只有重量、**没有重心高 kg_m**：不能直接喂给 weights.py "
                    "合成 KG（会算出偏低的 KG、偏大的 GM）。补 kg_m 后再接入 L2。")

    return {"values": {"misc_total_t": total, "misc_pct_displacement": pct},
            "zones": rows, "trace": trace, "warnings": warnings}


def sps_view(case: dict) -> dict:
    """整页视图：鱼雷表 + 水雷/深弹 + Misc weight 分区。"""
    t = torpedoes(case)
    o = ordnance(case)
    m = misc_weight(case)
    return {
        "torpedoes": t["batteries"], "tubes_total": t["values"]["tubes_total"],
        "carried_total": t["values"]["carried_total"],
        "explosive_total_t": t["values"]["explosive_total_t"],
        "mines": o["values"]["mines"], "depth_charges": o["values"]["depth_charges"],
        "misc_weight": m["zones"], "misc_total_t": m["values"]["misc_total_t"],
        "warnings": t["warnings"] + o["warnings"] + m["warnings"],
    }
