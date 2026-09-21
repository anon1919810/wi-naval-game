"""Plimsoll · Armour 页（SPS Belts & Bulkheads 表对齐，v0）

SPS Armour 页的结构（COVERAGE.md §2.5，28 项）：
  Belts & Bulkheads 表 —— 行：Main / Ends / Upper / Bulge / Torpedo bulkhead；
    列：Max Thickness / Length ft / Height ft / Weight tons。
    **Length/Height 在 SPS 里是用户输入，Weight 是输出**（参考图证实）。
  另有 Armour deck（Forecastle / Fore & aft / Quarter deck）、Conning towers、Total armour。

Plimsoll 的做法（与 SPS 的差异，诚实记录）
------------------------------------------
- 厚度：来自 armour_zones.json，逐区带 wiki 来源。
- 面积：SPS 用 Length×Height 算重量；我们优先用模型包围盒按 role 选面累加的
  area_m2（逐对象保真 + 曲率系数 1.10），Length/Height 只作展示口径。
  行里只给 length_m/height_m 时，退化为 SPS 的 L×H 口径（兼容外部输入）。
- 重量：W = area × t × ρ；ρ = 7850 kg/m³（造船学教科书常量，案例里带出处）。
- 全部几何项都是 estimate：包围盒无朝向信息；炮管不计入装甲（生成器已排除）。
- SPS 的 Bulge 行：Queen Mary 1913 无防雷凸舱，该行无数据 → 置 None + 警告，
  **不冒充 0**（「绿着错着」防则）。
- Armour deck 的 SPS 三行（Forecastle/Fore & aft/Quarter deck）需要按位置分段，
  现有分区只按厚度层（64mm/25mm）—— 本 v0 按层出两行，位置分段列为已知缺口。

设计纪律（承 SPEC §2）：纯函数 dict→dict；输出带 formula/source/estimate；
核心不做四舍五入；同输入同输出。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-armour-1"
DEFAULT_RHO_KG_M3 = 7850.0

# SPS Belts & Bulkheads 表的五行（顺序即 SPS 图上的顺序）
BELT_ROWS = ("main", "ends", "upper", "bulge", "torpedo_bulkhead")
# 全部合法分组：五行 + 甲板 + 炮座/炮塔/司令塔 + 其他
VALID_GROUPS = BELT_ROWS + ("armour_deck", "barbette", "turret", "conning_tower", "other")


def _finite_positive(v, what):
    if not isinstance(v, (int, float)) or isinstance(v, bool) \
            or not math.isfinite(v) or v <= 0:
        raise ValueError("%s 必须为正的有限值，收到 %r" % (what, v))


def compute(case: dict) -> dict:
    """装甲案例 → 逐区重量 + 分组合计 + SPS 表视图。

    输入：plimsoll-armour-1 案例（见 cases/queen_mary_1913_armour.json）。
    每行：{id, group, thickness_mm, area_m2 | (length_m + height_m), source, estimate}。
    """
    trace: list[dict] = []
    warnings: list[str] = []

    def T(key, value, formula, source, estimate=False):
        trace.append({"key": key, "value": value, "formula": formula,
                      "source": source, "estimate": estimate})

    if case.get("schema") != SCHEMA:
        raise ValueError("schema 必须是 %s，收到 %r" % (SCHEMA, case.get("schema")))

    rho = case.get("rho_kg_m3", DEFAULT_RHO_KG_M3)
    _finite_positive(rho, "rho_kg_m3")
    rho_src = case.get("rho_source", "未注明出处")

    rows_in = case.get("rows")
    if not isinstance(rows_in, list) or not rows_in:
        raise ValueError("rows 必须是非空数组")

    seen_ids: set[str] = set()
    out_rows: list[dict] = []
    group_totals: dict[str, float] = {}

    for r in rows_in:
        rid = r.get("id")
        if not rid:
            raise ValueError("每行都要有 id，收到 %r" % (r,))
        if rid in seen_ids:
            raise ValueError("装甲行 id 重复：%r" % rid)
        seen_ids.add(rid)

        group = r.get("group")
        if group not in VALID_GROUPS:
            raise ValueError("行 %s 的 group %r 不合法，必须是 %s"
                             % (rid, group, VALID_GROUPS))

        t_mm = r.get("thickness_mm")
        _finite_positive(t_mm, "行 %s 的 thickness_mm" % rid)
        t_m = float(t_mm) / 1000.0

        area = r.get("area_m2")
        if area is not None:
            _finite_positive(area, "行 %s 的 area_m2" % rid)
            area = float(area)
            geo = "area_m2"
        else:
            length = r.get("length_m")
            height = r.get("height_m")
            _finite_positive(length, "行 %s 的 length_m" % rid)
            _finite_positive(height, "行 %s 的 height_m" % rid)
            area = float(length) * float(height)
            geo = "length_m × height_m"

        est = bool(r.get("estimate", False))
        src = r.get("source", "无来源")
        weight = area * t_m * float(rho) / 1000.0

        out_rows.append({
            "id": rid, "group": group,
            "thickness_mm": float(t_mm),
            "length_m": r.get("length_m"), "height_m": r.get("height_m"),
            "area_m2": area, "weight_t": weight,
            "estimate": est, "source": src,
        })
        group_totals[group] = group_totals.get(group, 0.0) + weight
        T("row.%s.weight_t" % rid, weight,
          "W = %s × t × ρ（t=%.3f m, ρ=%.0f kg/m³）" % (geo, t_m, float(rho)),
          src, est)

    total = sum(out_rows[i]["weight_t"] for i in range(len(out_rows)))
    for g in sorted(group_totals):
        T("group.%s.weight_t" % g, group_totals[g], "Σ（组内）", "Armour 分组 %s" % g)
    T("total_armour_t", total, "Σ 全部装甲行", "Armour 合计")

    n_est = sum(1 for r in out_rows if r["estimate"])
    if n_est == len(out_rows):
        warnings.append("全部 %d 行都是 estimate（几何来自包围盒，厚度有 wiki 来源）——"
                        "总计不能当精确重量引用。" % len(out_rows))

    # SPS 五行里没出现的行 → 警告，不冒充 0
    present = {r["group"] for r in out_rows}
    for b in BELT_ROWS:
        if b not in present:
            warnings.append("SPS 行 %s 无对应分区（重量置空，不计入合计）。" % b)

    return {
        "values": {
            "total_armour_t": total,
            "rows": len(out_rows),
            "rho_kg_m3": float(rho),
            "n_estimate_rows": n_est,
        },
        "rows": out_rows,
        "groups": group_totals,
        "trace": trace,
        "warnings": warnings,
    }


def sps_table(result: dict) -> dict:
    """compute() 结果 → SPS Armour 页的表视图（Belts & Bulkheads + 甲板/塔座/其他 + Total）。"""
    by_group: dict[str, list[dict]] = {}
    for r in result["rows"]:
        by_group.setdefault(r["group"], []).append(r)

    def belt_view(g):
        rs = by_group.get(g, [])
        if not rs:
            return {"row": g, "thickness_mm": None, "length_m": None,
                    "height_m": None, "weight_t": None}
        return {
            "row": g,
            "thickness_mm": max(r["thickness_mm"] for r in rs),
            "length_m": max((r["length_m"] for r in rs if r["length_m"] is not None), default=None),
            "height_m": max((r["height_m"] for r in rs if r["height_m"] is not None), default=None),
            "weight_t": sum(r["weight_t"] for r in rs),
        }

    def rows_view(g):
        return [{"id": r["id"], "thickness_mm": r["thickness_mm"],
                 "weight_t": r["weight_t"], "estimate": r["estimate"]}
                for r in by_group.get(g, [])]

    return {
        "belts": [belt_view(g) for g in BELT_ROWS],
        "armour_deck": rows_view("armour_deck"),
        "barbettes_turrets": rows_view("barbette") + rows_view("turret"),
        "conning_tower": rows_view("conning_tower"),
        "other": rows_view("other"),
        "total_armour_t": result["values"]["total_armour_t"],
    }
