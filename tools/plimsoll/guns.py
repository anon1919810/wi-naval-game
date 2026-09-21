"""Plimsoll · Guns 页（SPS Weights 表对齐，v0）

SPS Guns 页的 Weights 表（COVERAGE.md §2.3，参考图证实）：
  行：Guns / Mounts / Armour / Total / Broadside lbs / Broadside kg / Magazine；
  列：Main / 2nd / 3rd / 4th / 5th / Total。

Plimsoll 的做法（诚实记录）
---------------------------
- Guns 行：门数 × 单炮重（NavWeaps/维基有源，非 estimate）。
- Mounts 行：座数 × 单座重。**Queen Mary 的 BII* 座 NavWeaps 未单列**
  （只给了 Mark II = 600 t，BII* 是 N/A）——沿用 600 t 并标 estimate。
- Armour 行：炮塔装甲重 —— **已知缺口**（turret_face 在模型 manifest 里无选面
  role 对象，Armour 页同此缺口），置 None + 警告，**不冒充 0**。
- Broadside：单舷可参战门数 × 弹重；lb→kg 用国际磅定义 0.45359237（精确）。
- Magazine：门数 × 每门储弹 × (弹重 + 装药)。副炮装药未采集 → 只算弹重并警告。

设计纪律（承 SPEC §2）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；同输入同输出。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-guns-1"
SPS_COLUMNS = ("main", "2nd", "3rd", "4th", "5th")
LB_TO_KG = 0.45359237  # 国际磅定义（精确常量，非估算）


def _finite_positive(v, what):
    if not isinstance(v, (int, float)) or isinstance(v, bool) \
            or not math.isfinite(v) or v <= 0:
        raise ValueError("%s 必须为正的有限值，收到 %r" % (what, v))


def _int_positive(v, what):
    if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
        raise ValueError("%s 必须为正整数，收到 %r" % (what, v))


def compute(case: dict) -> dict:
    """武备案例 → SPS Weights 表（Guns/Mounts/Armour/Total/Broadside/Magazine）。"""
    trace: list[dict] = []
    warnings: list[str] = []

    def T(key, value, formula, source, estimate=False):
        trace.append({"key": key, "value": value, "formula": formula,
                      "source": source, "estimate": estimate})

    if case.get("schema") != SCHEMA:
        raise ValueError("schema 必须是 %s，收到 %r" % (SCHEMA, case.get("schema")))

    batteries = case.get("batteries")
    if not isinstance(batteries, list) or not batteries:
        raise ValueError("batteries 必须是非空数组")

    seen_cols: set[str] = set()
    out: dict[str, dict] = {}

    for b in batteries:
        col = b.get("column")
        if col not in SPS_COLUMNS:
            raise ValueError("battery %r 的 column %r 不合法，必须是 %s"
                             % (b.get("id"), col, SPS_COLUMNS))
        if col in seen_cols:
            raise ValueError("column %r 重复" % col)
        seen_cols.add(col)
        bid = b.get("id", col)

        guns = b.get("guns")
        _int_positive(guns, "battery %s 的 guns" % bid)
        gun_w = b.get("gun_weight_t")
        _finite_positive(gun_w, "battery %s 的 gun_weight_t" % bid)

        est_mount = bool(b.get("mount_estimate", False))
        mounts = b.get("mounts")
        mount_w = b.get("mount_weight_t")
        if mounts is not None or mount_w is not None:
            _int_positive(mounts, "battery %s 的 mounts" % bid)
            _finite_positive(mount_w, "battery %s 的 mount_weight_t" % bid)

        shell_lb = b.get("shell_lb")
        _finite_positive(shell_lb, "battery %s 的 shell_lb" % bid)
        shell_kg = float(shell_lb) * LB_TO_KG

        broadside_guns = b.get("broadside_guns")
        _int_positive(broadside_guns, "battery %s 的 broadside_guns" % bid)
        if broadside_guns > guns:
            raise ValueError("battery %s 的 broadside_guns(%d) 不能超过 guns(%d)"
                             % (bid, broadside_guns, guns))

        guns_t = guns * float(gun_w)
        mounts_t = (mounts * float(mount_w)) if (mounts is not None and mount_w is not None) else None
        total_t = guns_t + (mounts_t or 0.0)
        broadside_lb = broadside_guns * float(shell_lb)
        broadside_kg = broadside_lb * LB_TO_KG

        rounds = b.get("rounds_per_gun")
        charge_lb = b.get("charge_lb")
        if rounds is not None:
            _int_positive(rounds, "battery %s 的 rounds_per_gun" % bid)
            per_round_kg = shell_kg + (float(charge_lb) * LB_TO_KG if charge_lb is not None else 0.0)
            magazine_t = guns * rounds * per_round_kg / 1000.0
            if charge_lb is None:
                warnings.append("battery %s 未提供装药重：Magazine 只算了弹重（偏低）。" % bid)
        else:
            magazine_t = None
            warnings.append("battery %s 未提供每门储弹数：Magazine 置空。" % bid)

        if mounts_t is None:
            warnings.append("battery %s 未提供炮座/炮塔重量：Mounts 置空，Total 偏低。" % bid)
        warnings.append("Armour 行（炮塔装甲重）暂缺：模型无炮塔装甲对象（与 Armour 页同缺口）。")

        T("%s.guns_t" % col, guns_t, "W = 门数 × 单炮重", b.get("gun_source", "无来源"),
          bool(b.get("gun_estimate", False)))
        if mounts_t is not None:
            T("%s.mounts_t" % col, mounts_t, "W = 座数 × 单座重",
              b.get("mount_source", "无来源"), est_mount)
        T("%s.total_t" % col, total_t, "Guns + Mounts（Armour 缺不计）",
          "battery %s" % bid, est_mount)
        T("%s.broadside_lb" % col, broadside_lb, "W = 单舷门数 × 弹重",
          b.get("shell_source", "无来源"), bool(b.get("shell_estimate", False)))
        T("%s.broadside_kg" % col, broadside_kg, "lb × 0.45359237（国际磅定义）",
          "精确换算", False)
        if magazine_t is not None:
            T("%s.magazine_t" % col, magazine_t,
              "W = 门数 × 每门储弹 × (弹重 + 装药)",
              b.get("ammo_source", "无来源"), bool(b.get("ammo_estimate", False)))

        out[col] = {
            "id": bid, "column": col,
            "guns": guns, "gun_weight_t": float(gun_w), "guns_t": guns_t,
            "mounts": mounts, "mount_weight_t": mount_w, "mounts_t": mounts_t,
            "armour_t": None,
            "total_t": total_t,
            "shell_lb": float(shell_lb), "broadside_guns": broadside_guns,
            "broadside_lb": broadside_lb, "broadside_kg": broadside_kg,
            "rounds_per_gun": rounds, "charge_lb": charge_lb,
            "magazine_t": magazine_t,
            "estimate": bool(b.get("mount_estimate", False)) or bool(b.get("gun_estimate", False)),
        }

    cols = [out[c] for c in SPS_COLUMNS if c in out]
    totals = {
        "guns_t": sum(r["guns_t"] for r in cols),
        "mounts_t": sum(r["mounts_t"] for r in cols if r["mounts_t"] is not None),
        "armour_t": None,  # 炮塔装甲重：已知缺口，不冒充 0
        "total_t": sum(r["total_t"] for r in cols),
        "broadside_lb": sum(r["broadside_lb"] for r in cols),
        "broadside_kg": sum(r["broadside_kg"] for r in cols),
        "magazine_t": sum(r["magazine_t"] for r in cols if r["magazine_t"] is not None),
    }
    T("total.guns_t", totals["guns_t"], "Σ 各列 Guns", "Weights 表合计")
    T("total.total_t", totals["total_t"], "Σ 各列 Total", "Weights 表合计")
    T("total.magazine_t", totals["magazine_t"], "Σ 各列 Magazine（缺项不计）", "Weights 表合计")

    return {
        "values": totals,
        "batteries": out,
        "columns": [c for c in SPS_COLUMNS if c in out],
        "trace": trace,
        "warnings": warnings,
    }


def sps_table(result: dict) -> dict:
    """compute() 结果 → SPS Weights 表视图：行 × 列（含 Total 列）。"""
    rows = ("guns_t", "mounts_t", "armour_t", "total_t",
            "broadside_lb", "broadside_kg", "magazine_t")
    labels = {"guns_t": "Guns", "mounts_t": "Mounts", "armour_t": "Armour",
              "total_t": "Total", "broadside_lb": "Broadside lbs",
              "broadside_kg": "Broadside kg", "magazine_t": "Magazine"}
    table = []
    for r in rows:
        row = {"row": labels[r]}
        for col in result["columns"]:
            row[col] = result["batteries"][col][r]
        row["total"] = result["values"][r]
        table.append(row)
    return table
