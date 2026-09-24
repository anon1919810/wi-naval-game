"""Selected deck, propulsion, endurance and historical adapters; no new kernels."""
import copy

try:
    from . import engines, geometry_analysis, page_rows, units
    from ._analysis_request import diagnostic
except ImportError:
    import engines, geometry_analysis, page_rows, units
    from _analysis_request import diagnostic


def page_rows_for(project, state, summary):
    """Attach declared SPS page rows (ledger projections) to a systems summary.

    A leaf that declares ``page_rows`` gets its rows projected from the selected
    loading ledger; leaves without a declaration are left untouched (no invention).
    Diagnostics travel inside each projection and are collected by the coordinator.
    """
    declared = {}
    for system, sections in (project.get("systems") or {}).items():
        if not isinstance(sections, dict):
            continue
        for leaf, payload in sections.items():
            if isinstance(payload, dict) and isinstance(payload.get("page_rows"), list):
                declared["%s.%s" % (system, leaf)] = payload
    views = {}
    for key, payload in declared.items():
        system, leaf = key.split(".", 1)
        views[key] = page_rows.project_declared_rows(state, summary, system, leaf, payload["page_rows"])
        if system == "weapons":
            views[key]["guns"] = page_rows.guns_rows(state, summary, system, leaf, payload)
        if system == "weapons" and any(row.get("row") == "mounts" for row in payload["page_rows"]):
            views[key]["rotating_armour_component"] = page_rows.rotating_armour_component(
                state, payload.get("rotating_armour_component"), battery=leaf)
        if key == "armour.fixed":
            views[key]["minimum_main_belt"] = page_rows.minimum_main_belt(
                project, (project["systems"]["armour"]["fixed"] or {}).get("minimum_main_belt"))
    result = copy.deepcopy(summary)
    if views:
        result["page_rows"] = views
    fixed = ((project.get("systems") or {}).get("armour") or {}).get("fixed") or {}
    result["deck_coverage"] = page_rows.deck_coverage(fixed.get("deck_coverage"))
    return result


def _deck(project, stages):
    geometry = project["geometry"]
    plane = stages["equilibrium"]["data"]
    deck = project.get("deck")
    data = geometry_analysis.deck_clearance(deck, plane, keel_offset_m=geometry["keel_offset_m"])
    # Declared-input freeboard projection (design view). This is a DISTINCT adapter
    # from the flotation/measured normal_clearance computed above: it never depends
    # on the equilibrium plane and is kept under its own key so the two calibrations
    # (declared design freeboard vs measured current-flotation clearance) stay
    # unmistakably separable. Absent deck -> key omitted, never null.
    if deck is not None:
        data["declared_freeboard"] = page_rows.freeboard_rows(deck)
    if data["status"] != "completed":
        return data, data["status"]
    points = {point["id"]: point for point in deck["points"]}
    clearances = {point["id"]: point["normal_clearance_m"] for point in data["points"]}
    intervals, rows = [], []
    for segment in deck.get("segments", []):
        aft, fore = segment["aft_point_id"], segment["fore_point_id"]
        left, right = points[aft]["x_m"], points[fore]["x_m"]
        intervals.append((left, right))
        reference = deck.get("reference_length_m", {}).get("value")
        rows.append(dict(id=segment["id"], length_m=right-left,
            aft_point_id=aft, fore_point_id=fore,
            aft_clearance_m=clearances[aft], fore_clearance_m=clearances[fore],
            length_pct=100*(right-left)/reference if reference else None,
            mean_normal_clearance_m=(clearances[aft]+clearances[fore])/2,
            source=segment.get("source", deck.get("source")), estimate=segment.get("estimate", deck.get("estimate"))))
    intervals.sort()
    overlap = any(b[0] < a[1] for a, b in zip(intervals, intervals[1:]))
    known_length = sum(r["length_m"] for r in rows)
    reference = deck.get("reference_length_m", {}).get("value")
    profile = dict(segments=rows, covered_length_m=known_length if not overlap else None,
        reference_length_m=reference, coverage_fraction=known_length/reference if reference and not overlap else None,
        mean_normal_clearance_m=sum(r["length_m"]*r["mean_normal_clearance_m"] for r in rows)/known_length
            if known_length and not overlap else None, coverage="overlapping" if overlap else "supplied_segments_only",
        method="length_weighted_linear_endpoint_clearance_over_supplied_nonoverlapping_segments")
    data["profile"] = profile
    if overlap or not rows:
        data["diagnostics"].append(diagnostic("analysis.deck_profile_incomplete",
            "overlapping or absent segments do not define a whole-ship mean freeboard", "$.deck.segments", False))
    curve = stages["gz"]["data"]
    if curve is None:
        data["diagnostics"].append(diagnostic(
            "analysis.deck_events_require_gz",
            "sampled deck immersion events require the gz stage; it was neither requested nor available in this request",
            "$.stages.deck.data.sampled_events", False))
        data["sampled_events"] = None
    else:
        data["sampled_events"] = geometry_analysis.deck_immersion_events(
            deck, curve["rows"], keel_offset_m=geometry["keel_offset_m"])
    return data, "completed"


def _fuel(propulsion, state):
    ledger = {i["id"]: i for i in state["effective_items"]}
    values, trace = {}, {}
    for name in ("coal", "oil"):
        binding = propulsion.get("fuel_bindings", {}).get(name)
        masses = [ledger[i]["mass_t"] for i in binding["weight_item_ids"]] if binding is not None else [None]
        values[name + "_t"] = sum(masses) if all(v is not None for v in masses) else None
        trace[name] = dict(binding=copy.deepcopy(binding), selected_items=[copy.deepcopy(ledger[i])
            for i in binding["weight_item_ids"]] if binding else [], value_t=values[name + "_t"],
            input_path=f"$.systems.propulsion.fuel_bindings.{name}",
            output_path=f"$.stages.propulsion.data.values.{name}_t")
    return values, trace


def _propulsion(project, state, stages):
    prop = project["systems"].get("propulsion", {})
    facts = copy.deepcopy(prop.get("facts", {}))
    values, fuels = _fuel(prop, state)
    case = dict(schema=engines.SCHEMA, **values, displacement_normal_t=state["values"]["total_mass_t"],
        power_conversion_method="international_mechanical_hp_precise", speed_conversion_method="international_knot_exact",
        fuel_source=fuels)
    for field in ("shafts", "max_speed_kn", "cruise_speed_kn"):
        fact = facts.get(field, {})
        case[field] = fact.get("value")
        case[field.replace("_kn", "") + "_source"] = fact.get("source")
    for canonical, legacy in (("design_power_kw", "power_design"), ("trial_power_kw", "power_trial")):
        fact = facts.get(canonical, {})
        case[legacy + "_shp"] = units.convert(fact["value"], "kW", "shp") if fact.get("value") is not None else None
        case[legacy + "_source"] = fact.get("source")
    system = (stages["systems"]["data"] or {}).get("systems", {}).get("propulsion", {})
    mass = system.get("ledger_mass_t")
    variable_binding = prop.get("variable_load_groups")
    group_rows = {row["id"]: row for row in state["groups"]}
    selected_groups = ([copy.deepcopy(group_rows[identity]) for identity in variable_binding["group_ids"]]
                       if variable_binding is not None else [])
    group_masses = [row["total_mass_t"] for row in selected_groups]
    engine_page = dict(boilers_count=facts.get("boilers", {}).get("value"),
        energy_source=facts.get("energy_source", {}).get("value"),
        transmission=facts.get("transmission", {}).get("value"),
        machinery_mass_t=mass, variable_group_ids=copy.deepcopy(variable_binding["group_ids"])
            if variable_binding else [],
        variable_load_t=sum(group_masses) if variable_binding is not None
            and all(value is not None for value in group_masses) else None,
        selected_variable_groups=selected_groups, variable_load_binding=copy.deepcopy(variable_binding),
        status="completed" if variable_binding is not None and all(value is not None for value in group_masses)
            else "unavailable", method="selected_loading_ledger_group_sum_v1",
        boundary="machinery mass is a separate installed system ledger projection; variable groups are not added again to displacement")
    coal, oil = values.get("coal_t"), values.get("oil_t")
    engine_page["coal_share_of_declared_fuel_pct"] = (
        100 * coal / (coal + oil) if coal is not None and oil is not None and coal + oil > 0
        else None)
    engine_page["coal_share_definition"] = "selected coal mass / (selected coal + selected oil mass); unknown when fuel inventory is incomplete or empty"
    if mass is not None and mass > 0:
        case["engine_weight_t"] = mass
        case["engine_weight_source"] = "selected linked propulsion ledger; not an independent mass estimate"
    # No design L is substituted for an unavailable selected waterline.
    hydro = stages["hydrostatics"]["data"]
    if hydro is not None:
        case["lwl_m"] = hydro["values"]["waterline_length_body_x_m"]
    known_facts = dict(facts=facts, fuel_bindings=fuels, effective_case=case, engine_page=engine_page,
        assumptions=["legacy displacement_normal_t adapter key contains the selected total mass",
                     "precise international horsepower and knot conversion"], input_fingerprint=state["input_fingerprint"])
    if case["shafts"] is None:
        return dict(**known_facts, values=values, diagnostics=[diagnostic("analysis.shafts_unknown",
            "engine kernel requires explicit shaft count; supplied facts and fuel masses are retained",
            "$.systems.propulsion.facts.shafts")]), "unavailable"
    native = engines.compute(case)
    return dict(**native, **known_facts), "completed"


def _endurance(project, opts, stages):
    propulsion = stages["propulsion"]["data"]
    scenario = next(s for s in project["endurance_scenarios"] if s["id"] == opts["endurance_scenario_id"])
    case = copy.deepcopy(propulsion["effective_case"])
    case["endurance_scenario"] = copy.deepcopy(scenario)
    if scenario["speed_kn"] is None or scenario["power_kw"] is None:
        return dict(values=None, scenario=copy.deepcopy(scenario), diagnostics=[diagnostic("analysis.endurance_operating_point_unknown",
            "explicit operating speed and power are required", "$.endurance_scenarios")]), "unavailable"
    native = engines.compute(case)
    values = native["values"]["steady_endurance"]
    return dict(values=values, kernel=native, scenario=copy.deepcopy(scenario),
        fuel_bindings=copy.deepcopy(propulsion["fuel_bindings"]), input_fingerprint=propulsion["input_fingerprint"]), "completed" if values is not None else "unavailable"


def _historical(project, state, stages):
    rows = []
    for supplied in project.get("historical_comparisons", []):
        row = dict(comparison=copy.deepcopy(supplied), status="unavailable", calculated=None,
            difference=None, relative_difference=None, unit=supplied["unit"], result_path=None,
            historical_validated=None, reason="no calculated result at exactly this condition and speed")
        quantity, current, path, unit = supplied["quantity"], None, None, None
        if supplied["condition_id"] == state["condition_id"]:
            if quantity == "displacement_t":
                current, unit, path = state["values"]["total_mass_t"], "t", "$.stages.loading.data.values.total_mass_t"
            elif quantity == "draught_m" and stages["equilibrium"]["data"] is not None:
                current, unit, path = stages["equilibrium"]["data"].get("waterline_above_keel_m"), "m", "$.stages.equilibrium.data.waterline_above_keel_m"
            elif quantity == "range_nm" and stages["endurance"]["data"] is not None:
                value = stages["endurance"]["data"].get("values")
                if value and supplied.get("speed_kn") == value["speed_kn"]:
                    current, unit, path = value["range_nm"], "nm", "$.stages.endurance.data.values.range_nm"
            elif quantity == "shaft_power_kw" and stages["resistance"]["data"] is not None:
                matches = [r for r in stages["resistance"]["data"].get("power_rows", []) if r["speed_kn"] == supplied.get("speed_kn")]
                if len(matches) == 1:
                    current, unit, path = matches[0]["shaft_power_kw"], "kW", "$.stages.resistance.data.power_rows"
            elif quantity == "speed_kn":
                row["reason"] = "no independent speed prediction is implemented; supplied speed is not a calculation"
        if current is not None and supplied["value"] is not None:
            calculated = current if unit == supplied["unit"] else units.convert(current, unit, supplied["unit"])
            difference = calculated - supplied["value"]
            row.update(status="completed", calculated=calculated, difference=difference,
                       relative_difference=difference/supplied["value"] if supplied["value"] else None,
                       result_path=path, reason=None)
        rows.append(row)
    return dict(rows=rows, diagnostics=[] if rows else [diagnostic("analysis.historical_unknown",
        "no historical comparison rows supplied", "$.historical_comparisons", False)]), "completed"


def run(name, project, state, options, stages):
    if name == "deck":
        return _deck(project, stages)
    if name == "propulsion":
        return _propulsion(project, state, stages)
    if name == "endurance":
        return _endurance(project, options, stages)
    if name == "historical":
        return _historical(project, state, stages)
    if name == "resistance":
        try:
            from . import _analysis_resistance
        except ImportError:
            import _analysis_resistance
        return _analysis_resistance.compute(project, state, options, stages)
    raise ValueError(f"unsupported adapter {name}")
