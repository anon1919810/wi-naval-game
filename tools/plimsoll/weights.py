"""Plimsoll · L2 重量分组与重心合成（v0：合成引擎 + 装甲组实数据）

设计纪律（承 SPEC §2，不赘述）：纯函数 dict→dict；输出项带 formula/source/estimate；
**核心不做四舍五入**；同输入同输出。

坐标基准（本项目被咬过三次的地方，必须显式）
------------------------------------------------
本模块**只接受 `datum: "keel"`** —— 每项重量沿**自龙骨向上**的 `kg_m`。
这跟 KB（自龙骨）同基准，KM−KG 才是合法减法。模型坐标（龙骨 z=−9.9）的
数值必须先换算再进来，换算在生成器里做，不在这里猜。

v0 范围（诚实清单）
-------------------
- **合成引擎是实数**：质量矩加权、逐组小计、trace 全套。
- **装甲组是实数据**：厚度带 wiki 来源、面积由模型包围盒推（estimate），
  由 `tools/gen_weights_case.py` 生成，可复现。
- **武备/动力/船体舾装三组为空**：不是省略，是没有数据。合成结果里明确报
  「覆盖率」，**不许**把空组当 0 混进 KG 去算 GM —— 空组会让 KG 偏高、GM 偏小，
  那是「绿着错着」的新变种。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-weights-1"
VALID_DATUM = ("keel",)


def synthesize(case: dict) -> dict:
    """重量分组 → 总质量（t）与合成重心 KG（自龙骨，m）。

    输入：plimsoll-weights-1 案例（见 cases/queen_mary_1913_weights.json）。
    输出：values / trace / warnings / coverage。
    **只对非空组做加权**；空组不进 KG，但会出现在 warnings 与 coverage 里。
    """
    trace: list[dict] = []
    warnings: list[str] = []

    def T(key, value, formula, source, estimate=False):
        trace.append({"key": key, "value": value, "formula": formula,
                      "source": source, "estimate": estimate})

    if case.get("schema") != SCHEMA:
        raise ValueError("schema 必须是 %s，收到 %r" % (SCHEMA, case.get("schema")))
    datum = case.get("datum")
    if datum not in VALID_DATUM:
        raise ValueError("datum 必须是 %s（KG 自龙骨向上）；收到 %r。"
                         "模型坐标请先在生成器里换算。" % (VALID_DATUM, datum))

    groups = case.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("groups 必须是非空数组")

    seen_ids: set[str] = set()
    total_m = 0.0
    moment_m = 0.0
    n_items = 0
    group_rows: list[dict] = []

    for g in groups:
        gid = g.get("id")
        if not gid:
            raise ValueError("每个组都要有 id，收到 %r" % (g,))
        items = g.get("items") or []
        g_m = 0.0
        g_mom = 0.0
        for it in items:
            iid = it.get("id")
            if not iid:
                raise ValueError("组 %s 里某项没有 id" % gid)
            if iid in seen_ids:
                raise ValueError("重量项 id 重复：%r" % iid)
            seen_ids.add(iid)
            mass = it.get("mass_t")
            kg = it.get("kg_m")
            if not isinstance(mass, (int, float)) or isinstance(mass, bool) \
                    or not math.isfinite(mass) or mass <= 0:
                raise ValueError("%s.%s.mass_t 必须为正的有限值，收到 %r" % (gid, iid, mass))
            if not isinstance(kg, (int, float)) or isinstance(kg, bool) \
                    or not math.isfinite(kg) or kg < 0:
                raise ValueError("%s.%s.kg_m 必须为非负有限值（自龙骨向上），收到 %r" % (gid, iid, kg))
            est = bool(it.get("estimate", False))
            g_m += mass
            g_mom += mass * kg
            n_items += 1
            T("item.%s.%s" % (gid, iid), mass,
              "m = %s" % ("面积×厚×ρ" if it.get("_area_m2") else "输入"),
              it.get("source", "无来源"), est)
            T("item.%s.%s.kg_m" % (gid, iid), kg, "重心（自龙骨）",
              it.get("source", "无来源"), est)
        g_kg = (g_mom / g_m) if g_m > 0 else None
        group_rows.append({
            "id": gid, "label": g.get("label", gid), "items": len(items),
            "mass_t": g_m, "kg_m": g_kg,
            "note": g.get("_note") if not items else None,
        })
        if items:
            T("group.%s.mass_t" % gid, g_m, "Σ m（组内）", "组 %s 合成" % gid)
            T("group.%s.kg_m" % gid, g_kg, "Σ(m·kg)/Σm（组内）", "组 %s 合成", True)
        else:
            warnings.append("组 %s 为空：%s" % (gid, g.get("_note", "无数据，未计入合成")))

    total_m = sum(r["mass_t"] for r in group_rows)
    moment_m = sum((r["mass_t"] * r["kg_m"]) for r in group_rows if r["kg_m"] is not None)
    kg = (moment_m / total_m) if total_m > 0 else None

    T("total_mass_t", total_m, "Σ 各组质量", "全船合成")
    if kg is not None:
        T("kg_m", kg, "Σ(m·kg)/Σm（自龙骨）", "全船合成（仅非空组）", True)

    ref = case.get("reference") or {}
    disp = ref.get("displacement_normal_t")
    coverage = None
    if disp:
        coverage = 100.0 * total_m / float(disp)
        T("coverage_pct", coverage, "合成质量 / 参考排水量 ×100",
          "对照 %s" % ref.get("displacement_source", "参考排水量"), True)
        if coverage < 95.0:
            warnings.append("合成质量只覆盖参考排水量的 %.1f%% —— 缺组未计入，"
                            "此 KG 不能当全船 KG 用。" % coverage)
        elif coverage > 105.0:
            warnings.append("合成质量超参考排水量 %.1f%%，重量口径不一致。" % coverage)

    return {
        "values": {
            "total_mass_t": total_m,
            "kg_m": kg,
            "items": n_items,
            "coverage_pct": coverage,
        },
        "groups": group_rows,
        "trace": trace,
        "warnings": warnings,
        "datum": "keel",
    }


def gm_from_km(case: dict, km_m: float, free_surface_m: float = 0.0) -> dict:
    """KM（自龙骨）− KG_eff（自龙骨 + 自由液面修正）= GM。

    **合成质量没覆盖排水量时会拒绝给 GM** —— 用残缺的 KG 算出漂亮的 GM，
    是这个项目最该防的错误。硬要算就先补数据。
    """
    r = synthesize(case)
    kg = r["values"]["kg_m"]
    total = r["values"]["total_mass_t"]
    ref = (case.get("reference") or {}).get("displacement_normal_t")
    if kg is None:
        raise ValueError("没有任何重量项，无法合成 KG。")
    if ref and total < 0.95 * float(ref):
        raise ValueError("重量组只覆盖排水量的 %.1f%%，KG 不是全船重心，拒绝算 GM。"
                         "缺的组：%s" % (
                             r["values"]["coverage_pct"],
                             ", ".join(g["id"] for g in r["groups"] if g["items"] == 0)))
    kg_eff = kg + float(free_surface_m)
    gm = float(km_m) - kg_eff
    return {
        "values": {"km_m": float(km_m), "kg_m": kg, "free_surface_m": free_surface_m,
                   "kg_eff_m": kg_eff, "gm_m": gm},
        "trace": r["trace"] + [{"key": "gm_m", "value": gm,
                                "formula": "GM = KM − (KG + FSC)",
                                "source": "合成 KG（见上）", "estimate": True}],
        "warnings": list(r["warnings"]),
        "datum": "keel",
    }
