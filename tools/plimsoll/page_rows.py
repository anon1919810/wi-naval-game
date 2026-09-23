"""Plimsoll · 声明式页面行投影（v0：Armour）

**为什么需要这一层**：SPS 七页的「行」与账本条目之间**没有对应关系**。
以装甲为例——SPS 页声明 8 行（main / upper / ends / armour_deck×2 /
torpedo_bulkhead / barbette / conning_tower），而账本有 13 个装甲条目
（`armour-belt-229mm`、`armour-belt-taper-102mm-fwd/aft`、`barbette-a/b/q/x`…），
两边的 id 与粒度都不同。此前没有机制能回答：
「SPS 的 main 行到底由账本哪些条目构成、合计是否等于账本装甲组质量」。

本模块提供该机制，并沿用仓库已有的绑定模式（`systems.*.weight_item_ids`）：

  页面行 ——(声明 weight_item_ids)--> 账本条目 ——(唯一质量权威)--> 质量

投影层只做四件事：**按声明聚合、校验不变量、回显几何输入、如实报告未知**。
它不产生任何新的质量数值，也不发明缺失的几何。

硬不变量（违反即诊断，不静默）
------------------------------
1. 同一条目被两行引用 → `page_rows.item_duplicate`（blocking）
2. 声明引用了账本里不存在的条目 → `page_rows.item_unknown`（blocking）
3. 账本里的装甲条目未被任何行覆盖 → `page_rows.item_uncovered`（非阻塞，列出 id）
4. 行合计 ≠ 账本该系统组质量 → `page_rows.mass_mismatch`（非阻塞但显式报告）
5. 未声明跨度 → `length_m = None` + `segment_status = "unknown_no_declared_extent"`
   （**不按形心反推长度**，也不拿面积冒充跨度）

设计纪律（承 SPEC §2 与通用性契约）：纯函数 dict→dict；核心零船只常量；
船只专属的分组声明进**项目数据**（本模块只消费它）；输出带 formula/source/estimate。
"""

from __future__ import annotations

import math

SCHEMA = "plimsoll-page-rows-1"
SCHEMA_FREEBOARD = "plimsoll-page-rows-freeboard-1"
MASS_TOLERANCE_T = 1e-9


def _diagnostic(code, message, path, blocking=False):
    return {"code": code, "severity": "error" if blocking else "warning",
            "path": path, "message": str(message), "blocking": bool(blocking)}


def _item_index(state):
    items = state.get("effective_items")
    if not isinstance(items, list):
        raise ValueError("state.effective_items must be an array (plimsoll-loading-1)")
    return {item["id"]: item for item in items}


def _plate_models(systems):
    """Return linked plate mass models of one system leaf, keyed by ledger item id."""
    index = {}
    for leaf in (systems or {}).values():
        if not isinstance(leaf, dict):
            continue
        for model in leaf.get("mass_models") or []:
            linked = model.get("linked_weight_item_id")
            if linked and model.get("method") == "plate_area_thickness_density_mass":
                index[linked] = {
                    "model_id": model.get("id"),
                    "area_m2": (model.get("inputs") or {}).get("area_m2"),
                    "thickness_mm": (
                        (model.get("inputs") or {}).get("thickness_m") * 1000.0
                        if isinstance((model.get("inputs") or {}).get("thickness_m"),
                                      (int, float)) else None),
                    "estimate": model.get("estimate"),
                    "source": model.get("source"),
                }
    return index


def project_declared_rows(state, systems_result, system, leaf, declaration):
    """Project declared page rows onto the selected loading ledger.

    Args:
        state: ``plimsoll-loading-1`` result (the only mass authority).
        systems_result: ``systems.summary`` result (bound ledger masses).
        system, leaf: e.g. ``"armour"`` / ``"fixed"`` — locates the bound system.
        declaration: list of rows, each
            ``{"row": str, "weight_item_ids": [str], "thickness_mm": float|None,
               "extents_m": {"aft_m": float, "fore_m": float}|None, "source": str,
               "estimate": bool}``.

    Returns:
        dict with per-row ledger masses, invariant diagnostics and honest unknowns.
    """
    if not isinstance(declaration, list) or not declaration:
        raise ValueError("declaration must be a nonempty array")
    ledger = _item_index(state)
    systems = (systems_result or {}).get("systems") or {}
    if not isinstance(systems, dict):
        raise ValueError("systems_result.systems must be an object")
    # systems.summary keys leaves as dotted identifiers: "armour.fixed", "weapons.main", ...
    leaf_key = "%s.%s" % (system, leaf)
    leaf_payload = systems.get(leaf_key)
    if not isinstance(leaf_payload, dict):
        raise ValueError("systems.%s is missing from the systems result" % leaf_key)
    bound_ids = leaf_payload.get("linked_items")
    if isinstance(bound_ids, list) and bound_ids and isinstance(bound_ids[0], dict):
        bound_ids = [entry.get("id") for entry in bound_ids]
    if not isinstance(bound_ids, list) or (not bound_ids and leaf_payload.get("status") != "absent"):
        raise ValueError("systems.%s.linked_items must be a nonempty array for a present leaf" % leaf_key)
    models = _plate_models({leaf_key: leaf_payload})

    diagnostics: list[dict] = []
    trace: list[dict] = []
    rows_out: list[dict] = []
    used: dict[str, str] = {}

    for index, entry in enumerate(declaration):
        path = "$.page_rows[%d]" % index
        row_name = entry.get("row")
        if not isinstance(row_name, str) or not row_name.strip():
            raise ValueError("%s.row must be a nonempty string" % path)
        ids = entry.get("weight_item_ids")
        if ids is None:
            ids = []
        if not isinstance(ids, list):
            raise ValueError("%s.weight_item_ids must be an array" % path)

        mass = 0.0
        mass_complete = True
        areas, thicknesses, estimates, sources, boundaries = [], [], [], [], []
        for item_id in ids:
            if item_id in used:
                diagnostics.append(_diagnostic(
                    "page_rows.item_duplicate",
                    "item %r is already declared by row %r" % (item_id, used[item_id]),
                    path + ".weight_item_ids", blocking=True))
                continue
            used[item_id] = row_name
            item = ledger.get(item_id)
            if item is None:
                diagnostics.append(_diagnostic(
                    "page_rows.item_unknown",
                    "item %r is not present in the selected loading ledger" % item_id,
                    path + ".weight_item_ids", blocking=True))
                continue
            value = item.get("mass_t")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                mass += float(value)
            else:
                mass_complete = False
                diagnostics.append(_diagnostic(
                    "page_rows.item_mass_unknown",
                    "item %r has no known mass; row total is incomplete" % item_id,
                    path + ".weight_item_ids"))
            estimates.append(bool(item.get("estimate", False)))
            model = models.get(item_id)
            if model:
                if isinstance(model["area_m2"], (int, float)):
                    areas.append(float(model["area_m2"]))
                if isinstance(model["thickness_mm"], (int, float)):
                    thicknesses.append(float(model["thickness_mm"]))
            provenance = item.get("provenance") or {}
            source = provenance.get("source", item.get("source"))
            if source is not None:
                sources.append(source)
            for model in leaf_payload.get("mass_models", []):
                if model.get("linked_weight_item_id") == item_id and model.get("boundary"):
                    boundaries.append(model["boundary"])

        declared_thickness = entry.get("thickness_mm")
        thickness_mm = float(declared_thickness) if isinstance(
            declared_thickness, (int, float)) and not isinstance(declared_thickness, bool) else (
            max(thicknesses) if thicknesses else None)

        # Typed inputs (diameter/counts/arrangement/...) are declared, never inferred.
        typed = entry.get("typed")
        typed = dict(typed) if isinstance(typed, dict) else None
        typed_unknown = sorted(key for key, value in (typed or {}).items() if value is None)
        if typed_unknown:
            diagnostics.append(_diagnostic(
                "page_rows.typed_field_unknown",
                "typed fields are unknown and must not be substituted: %r" % (typed_unknown,),
                path + ".typed"))
        if typed:
            typed_status = "declared" if not typed_unknown else "partial_unknown"
        else:
            typed_status = "unknown_no_typed_declaration"
        extents = entry.get("extents_m")
        declared_extent = (isinstance(extents, dict)
                           and isinstance(extents.get("aft_m"), (int, float))
                           and isinstance(extents.get("fore_m"), (int, float)))
        if extents is not None and not declared_extent:
            diagnostics.append(_diagnostic(
                "page_rows.extent_invalid",
                "extents_m must declare finite aft_m and fore_m", path + ".extents_m"))
        length_m = (float(extents["fore_m"]) - float(extents["aft_m"])
                    if declared_extent else None)

        rows_out.append({
            "row": row_name,
            "group": entry.get("group"),
            "label": entry.get("label"),
            # A row that binds no ledger item has no mass: unknown, never zero.
            "weight_t": mass if ids and mass_complete else None,
            "mass_status": ("ledger_bound" if mass_complete else "ledger_mass_unknown")
                if ids else "no_ledger_binding",
            "item_ids": list(ids),
            "item_count": len(ids),
            "thickness_mm": thickness_mm if ids else entry.get("thickness_mm"),
            "area_m2": sum(areas) if areas else None,
            "length_m": length_m,
            "extents_m": dict(extents) if declared_extent else None,
            "segment_status": ("declared_extents" if declared_extent
                               else "unknown_no_declared_extent"),
            "typed": typed,
            "typed_unknown_fields": typed_unknown,
            "typed_status": typed_status,
            "estimate": all(estimates) if estimates else None,
            "sources": sources,
            "declaration_source": entry.get("source"),
            "declaration_estimate": entry.get("estimate"),
            "model_boundaries": boundaries,
        })
        trace.append({
            "key": "page_row.%s.weight_t" % row_name,
            # A row with no ledger binding has unknown mass; the trace must not say 0.
            "value": mass if ids and mass_complete else None,
            "formula": ("Σ 声明条目的账本 mass_t（不重算）" if ids
                        else "no ledger binding → mass unknown"),
            "source": "selected loading weight ledger; declared binding by weight_item_ids",
            "estimate": all(estimates) if estimates else None,
        })

    uncovered = sorted(set(bound_ids) - set(used))
    if uncovered:
        diagnostics.append(_diagnostic(
            "page_rows.item_uncovered",
            "armour ledger items are not declared by any page row: %r" % (uncovered,),
            "$.page_rows"))

    total = (sum(row["weight_t"] for row in rows_out if row["weight_t"] is not None)
             if all(row["weight_t"] is not None for row in rows_out if row["item_ids"])
             else None)
    bound = leaf_payload.get("ledger_mass_t")
    matches = (total is not None and isinstance(bound, (int, float)) and not isinstance(bound, bool)
               and math.isclose(total, float(bound), rel_tol=MASS_TOLERANCE_T,
                                abs_tol=MASS_TOLERANCE_T))
    if not matches and not uncovered and bound is not None and total is not None:
        diagnostics.append(_diagnostic(
            "page_rows.mass_mismatch",
            "declared rows total %.9f t but %s.%s ledger mass is %r"
            % (total, system, leaf, bound), "$.page_rows"))
    trace.append({
        "key": "declared_rows_total_t",
        "value": total,
        "formula": "Σ 页面行（均为账本条目之和）",
        "source": "declared page rows over the selected ledger",
        "estimate": None,
    })

    result = {
        "schema": SCHEMA,
        "system": system,
        "leaf": leaf,
        "rows": rows_out,
        "values": {
            "declared_rows": len(rows_out),
            "declared_item_count": len(used),
            "ledger_item_count": len(bound_ids),
            "uncovered_item_ids": uncovered,
            "declared_rows_total_t": total,
            "ledger_leaf_mass_t": float(bound) if isinstance(bound, (int, float))
            and not isinstance(bound, bool) else None,
            "matches_ledger_mass": bool(matches) if bound is not None and total is not None else None,
        },
        "trace": trace,
        "diagnostics": diagnostics,
    }
    grouped = {}
    for row in rows_out:
        group_id = row["group"] or "unclassified"
        grouped.setdefault(group_id, []).append(row)
    result["groups"] = {group_id: dict(
        row_ids=[row["row"] for row in members],
        weight_t=sum(row["weight_t"] for row in members)
            if all(row["weight_t"] is not None for row in members) else None,
        status="ledger_bound" if all(row["weight_t"] is not None for row in members)
            else "unavailable",
        method="declared_nonoverlapping_page_row_sum_v1")
        for group_id, members in grouped.items()}
    if system == "weapons" and leaf_payload.get("broadside_count") is not None:
        models = [m for m in leaf_payload.get("mass_models", [])
                  if m.get("method") == "counted_ammunition_mass"]
        if len(models) == 1:
            model = models[0]
            projectile = model.get("inputs", {}).get("projectile_mass_kg")
            provenance = (model.get("input_provenance") or {}).get("projectile_mass_kg")
        else:
            projectile, provenance = None, None
        count = leaf_payload["broadside_count"]
        valid = (isinstance(projectile, (int, float)) and not isinstance(projectile, bool)
                 and math.isfinite(projectile) and projectile >= 0 and provenance)
        mass = count * projectile if valid else None
        result["broadside"] = {
            "count": count, "projectile_mass_kg": projectile if valid else None,
            "mass_kg": mass, "mass_lb": mass / 0.45359237 if mass is not None else None,
            "source": provenance if valid else None,
            "estimate": provenance.get("estimate") if valid else None,
            "status": "completed" if valid else "unavailable",
            "formula": "broadside_count × projectile_mass_kg; excludes charge and ammunition outfit",
        }
        if not valid:
            result["diagnostics"].append(_diagnostic(
                "page_rows.broadside_unknown",
                "a single sourced projectile mass model is required for broadside mass",
                "$.page_rows", False))
    return result


def armour_rows(state, systems_result, declaration):
    """Armour page rows (SPS Belts & Bulkheads / deck / towers) from the ledger."""
    return project_declared_rows(state, systems_result, "armour", "fixed", declaration)


def rotating_armour_component(state, declaration, battery=None):
    """Report a sourced subcomponent of one selected mounting item without adding mass."""
    result = dict(status="unavailable", method="declared_nonadditive_mount_component_v1",
                  mount_weight_item_id=None, mount_mass_t=None, declared_rotating_armour_mass_t=None,
                  rotating_armour_mass_t=None, other_mount_mass_t=None,
                  source=None, estimate=None, model_applicable=False, historical_validated=None,
                  mass_accounting="informational split of one selected mounting item; never added to ship or fixed-armour mass",
                  diagnostics=[],
                  reason="no independent rotating-armour component declared")
    if declaration is None:
        return result
    input_path = "$.systems.weapons.%s.rotating_armour_component" % (battery or "<battery>")
    item_id = declaration["mount_weight_item_id"]
    item = _item_index(state).get(item_id)
    parent_mass = item.get("mass_t") if item else None
    component_mass = declaration.get("mass_t")
    result.update(mount_weight_item_id=item_id, mount_mass_t=parent_mass,
                  declared_rotating_armour_mass_t=component_mass,
                  source=declaration.get("source"), estimate=declaration.get("estimate"))
    if component_mass is None or parent_mass is None:
        result["reason"] = "declared component or selected mounting mass is unknown"
        result["diagnostics"].append(_diagnostic(
            "page_rows.rotating_armour_unknown", result["reason"],
            input_path))
        return result
    if component_mass > parent_mass:
        result["reason"] = "declared rotating armour exceeds selected mounting mass"
        result["diagnostics"].append(_diagnostic(
            "page_rows.rotating_armour_exceeds_mount", result["reason"],
            input_path + ".mass_t"))
        return result
    result.update(status="completed", rotating_armour_mass_t=component_mass,
                  other_mount_mass_t=max(0.0, parent_mass - component_mass),
                  model_applicable=True, reason=None)
    return result


def deck_coverage(declaration):
    """Calculate declared protected plan area over its declared deck reference."""
    result = dict(status="unavailable", method="declared_protected_plan_area_ratio_v1",
                  formula="100 * covered_plan_area_m2 / reference_plan_area_m2",
                  coverage_pct=None, covered_plan_area_m2=None, reference_plan_area_m2=None,
                  source=None, estimate=None, model_applicable=False,
                  reason="no deck coverage study declared")
    if declaration is None:
        return result
    covered_fact = declaration.get("covered_plan_area_m2") or {}
    reference_fact = declaration.get("reference_plan_area_m2") or {}
    covered, reference = covered_fact.get("value"), reference_fact.get("value")
    result.update(covered_plan_area_m2=covered, reference_plan_area_m2=reference,
                  source={"covered_plan_area_m2": covered_fact.get("source"),
                          "reference_plan_area_m2": reference_fact.get("source")},
                  estimate=(covered_fact.get("estimate") or reference_fact.get("estimate"))
                      if covered is not None and reference is not None else None)
    missing = [key for key, value in (("covered_plan_area_m2", covered),
                                      ("reference_plan_area_m2", reference)) if value is None]
    if missing:
        result["reason"] = "missing " + ", ".join(missing)
        return result
    if (not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) for value in (covered, reference))
            or covered < 0 or reference <= 0 or covered > reference):
        result["reason"] = "declared plan areas are invalid or inconsistent"
        return result
    result.update(status="completed", coverage_pct=100.0 * covered / reference,
                  model_applicable=True, reason=None)
    return result


def minimum_main_belt(project, declaration):
    """Estimate the continuous length covering explicitly named vital compartments."""
    result = dict(status="unavailable", method="declared_compartment_extent_envelope_v1",
                  length_m=None, declared_span_m=None, protected_compartments=[],
                  source=None, estimate=True, model_applicable=False,
                  reason="no protected-compartment study declared")
    if declaration is None:
        return result
    compartments = {row["id"]: row for row in project["compartments"]}
    listed = [compartments[item_id] for item_id in declaration["protected_compartment_ids"]]
    extents = [dict(id=row["id"], aft_m=row["x_m"] - row["length_m"] / 2,
                    fore_m=row["x_m"] + row["length_m"] / 2,
                    source=row.get("source"), estimate=row.get("estimate")) for row in listed]
    aft = min(row["aft_m"] for row in extents)
    fore = max(row["fore_m"] for row in extents)
    result.update(declared_span_m=fore - aft, protected_compartments=extents,
                  source=declaration["source"],
                  estimate=declaration["estimate"] or any(row.get("estimate") for row in listed),
                  aft_margin_m=declaration["aft_margin_m"], fore_margin_m=declaration["fore_margin_m"])
    if not declaration["inventory_complete"]:
        result["reason"] = "declared protected compartments are not a complete inventory"
        return result
    result.update(status="completed", reason=None, model_applicable=True,
                  length_m=fore - aft + declaration["aft_margin_m"] + declaration["fore_margin_m"])
    return result


def _point_freeboard(point):
    """Return (value, source, estimate) of a deck point's declared freeboard fact.

    ``value`` is ``None`` when the fact is absent, null, non-finite, or negative:
    an invalid value is treated as unknown rather than fabricated. The deck
    validator already reports invalid numeric values separately, so this
    projection only ever consumes a finite non-negative declared value. It never
    reads ``z_m`` — the sealed-envelope top is not a freeboard source.
    """
    if not isinstance(point, dict):
        return None, None, None
    fb = point.get("freeboard_m")
    if not isinstance(fb, dict):
        return None, None, None
    raw = fb.get("value")
    if (isinstance(raw, (int, float)) and not isinstance(raw, bool)
            and math.isfinite(raw) and raw >= 0):
        value = float(raw)
    else:
        value = None
    source = fb.get("source")
    estimate = fb.get("estimate")
    estimate = bool(estimate) if isinstance(estimate, bool) else None
    return value, source, estimate


def _point_x(point):
    raw = point.get("x_m") if isinstance(point, dict) else None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(raw):
        return float(raw)
    return None


def freeboard_rows(deck):
    """Project declared deck-segment freeboards (design-input view, not the ledger).

    This is the SPS-style freeboard page input: each deck point MAY carry a
    declared ``freeboard_m`` fact (``{"value", "source", "estimate"}``). The
    projection reports, per segment, the endpoints' declared freeboards and a
    length-weighted mean over only the segments whose both endpoints declare a
    freeboard.

    **This is a declared-input projection. It never reads ``z_m``**, never uses
    the sealed-envelope top, never infers freeboard from a centroid or area, and
    never treats an unknown freeboard as zero. Unknowns stay unknown.

    Length-weighted mean (declared segments only):

        segment_mean = (fb_aft + fb_fore) / 2            # only when both declared
        length       = |x_fore - x_aft|
        weighted_mean = Σ(length × segment_mean) / Σ(length)   # over declared segments

    Coverage:

        coverage_fraction = Σ(length over declared) / Σ(length over all segments)

    A segment missing a freeboard contributes to neither the numerator nor the
    denominator of the weighted mean; an unknown reference length makes every
    ``length_percent`` null.
    """
    diagnostics = []
    if not isinstance(deck, dict):
        diagnostics.append(_diagnostic("page_rows.deck_invalid",
            "freeboard_rows requires a deck object", "$.deck"))
        return {"schema": SCHEMA_FREEBOARD, "segments": [], "values": {},
                "diagnostics": diagnostics}

    points = {p["id"]: p for p in (deck.get("points") or [])
              if isinstance(p, dict) and isinstance(p.get("id"), str)}

    ref_fact = deck.get("reference_length_m")
    ref_value = ref_fact.get("value") if isinstance(ref_fact, dict) else None
    ref_source = ref_fact.get("source") if isinstance(ref_fact, dict) else None
    ref_known = (isinstance(ref_value, (int, float)) and not isinstance(ref_value, bool)
                 and math.isfinite(ref_value) and ref_value > 0)
    if not ref_known:
        diagnostics.append(_diagnostic("page_rows.reference_length_unknown",
            "reference_length_m is unknown; every segment length_percent is null",
            "$.deck.reference_length_m"))

    segments_out = []
    unknown_segments = []
    known_ids = []
    unknown_ids = []
    weighted_num = 0.0
    weighted_den = 0.0
    total_length = 0.0
    declared_length = 0.0
    wm_estimates = []
    wm_sources = []

    for seg in (deck.get("segments") or []):
        if not isinstance(seg, dict):
            continue
        seg_id = seg.get("id")
        aft_id = seg.get("aft_point_id")
        fore_id = seg.get("fore_point_id")
        aft = points.get(aft_id)
        fore = points.get(fore_id)

        if aft is None or fore is None:
            diagnostics.append(_diagnostic("page_rows.segment_points_unknown",
                "segment %r references a non-existent point id (aft=%r fore=%r)"
                % (seg_id, aft_id, fore_id), "$.deck.segments"))
            segments_out.append({
                "id": seg_id, "aft_point_id": aft_id, "fore_point_id": fore_id,
                "length_m": None, "length_percent": None,
                "freeboard_aft_m": None, "freeboard_fore_m": None,
                "segment_mean_freeboard_m": None, "source": None, "estimate": None,
                "status": "unknown_missing_endpoint"})
            unknown_ids.append(seg_id)
            unknown_segments.append(seg_id)
            continue

        aft_val, aft_src, aft_est = _point_freeboard(aft)
        fore_val, fore_src, fore_est = _point_freeboard(fore)

        x_aft = _point_x(aft)
        x_fore = _point_x(fore)
        length = (abs(x_fore - x_aft)
                  if x_aft is not None and x_fore is not None else None)
        length_percent = (100.0 * length / float(ref_value)
                          if length is not None and ref_known else None)
        if length is not None:
            total_length += length

        if aft_val is None or fore_val is None:
            segments_out.append({
                "id": seg_id, "aft_point_id": aft_id, "fore_point_id": fore_id,
                "length_m": length, "length_percent": length_percent,
                "freeboard_aft_m": aft_val, "freeboard_fore_m": fore_val,
                "segment_mean_freeboard_m": None,
                "source": [s for s in (aft_src, fore_src) if s is not None] or None,
                "estimate": None, "status": "unknown_missing_freeboard"})
            unknown_ids.append(seg_id)
            unknown_segments.append(seg_id)
            continue

        seg_mean = 0.5 * (aft_val + fore_val)
        seg_estimate = (bool(aft_est and fore_est)
                        if aft_est is not None and fore_est is not None else None)
        seg_sources = [s for s in (aft_src, fore_src) if s is not None] or None
        segments_out.append({
            "id": seg_id, "aft_point_id": aft_id, "fore_point_id": fore_id,
            "length_m": length, "length_percent": length_percent,
            "freeboard_aft_m": aft_val, "freeboard_fore_m": fore_val,
            "segment_mean_freeboard_m": seg_mean,
            "source": seg_sources, "estimate": seg_estimate,
            "status": "declared"})
        known_ids.append(seg_id)
        if length is not None:
            weighted_num += length * seg_mean
            weighted_den += length
            declared_length += length
        wm_estimates.append(seg_estimate)
        wm_sources.append(seg_sources)

    if unknown_segments:
        diagnostics.append(_diagnostic("page_rows.freeboard_unknown",
            "segments with at least one endpoint freeboard unknown: %r"
            % (unknown_segments,), "$.deck.segments"))

    if weighted_den > 0:
        weighted_mean = weighted_num / weighted_den
        wm_estimate = (all(e for e in wm_estimates if e is not None)
                       if all(e is not None for e in wm_estimates) else None)
        wm_source_set = set()
        for grp in wm_sources:
            if isinstance(grp, list):
                wm_source_set.update(s for s in grp if isinstance(s, str))
        wm_source = sorted(wm_source_set) or None
    else:
        weighted_mean = None
        wm_estimate = None
        wm_source = None

    values = {
        "weighted_mean_freeboard_m": weighted_mean,
        "weighted_mean_estimate": wm_estimate,
        "weighted_mean_source": wm_source,
        "coverage_fraction": (declared_length / total_length) if total_length > 0 else None,
        "known_segment_ids": known_ids,
        "unknown_segment_ids": unknown_ids,
        "reference_length_m": ref_value if ref_known else None,
        "reference_source": ref_source,
        "total_length_m": total_length if total_length > 0 else None,
        "declared_length_m": declared_length if declared_length > 0 else None,
    }

    return {
        "schema": SCHEMA_FREEBOARD,
        "method": "declared_deck_segment_freeboard_v1",
        "formula": ("weighted_mean_freeboard_m = Σ(length × (fb_aft + fb_fore)/2) "
                    "/ Σ(length) over segments whose both endpoints declare a freeboard; "
                    "unknown freeboards are excluded from numerator and denominator"),
        "segments": segments_out,
        "values": values,
        "diagnostics": diagnostics,
    }
