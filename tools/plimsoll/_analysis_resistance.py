"""Explicit empirical adaptation of the actual selected waterplane."""
import copy
import hashlib
from importlib import resources
import json
import math
from pathlib import Path

try:
    from . import resistance, holtrop, units
    from ._analysis_request import diagnostic
except ImportError:
    import resistance, holtrop, units
    from _analysis_request import diagnostic

TABLE_ID = "taylor-gertler-molland-a3"
TABLE_SHA256 = "e9dc5141235ad9a0ddc1c1de70ab33d28f7aac86f75953663c969ad3fd124d93"


def _source_table(scenario):
    if scenario.get("table_id") != TABLE_ID or scenario.get("table_sha256") != TABLE_SHA256:
        raise ValueError("explicit registered Taylor table ID and exact raw SHA-256 are required")
    try:
        raw = (resources.files(__package__).joinpath("cases", "taylor_gertler_cr_table.json").read_bytes()
               if __package__ else Path(__file__).with_name("cases").joinpath("taylor_gertler_cr_table.json").read_bytes())
    except (OSError, ModuleNotFoundError) as error:
        raise ValueError("declared bundled Taylor source resource is unavailable") from error
    if hashlib.sha256(raw).hexdigest() != TABLE_SHA256:
        raise ValueError("bundled Taylor source resource raw SHA-256 mismatch")
    table = resistance.taylor_gertler_source_table(json.loads(raw.decode("utf-8")))
    return table, dict(id=TABLE_ID, raw_sha256=TABLE_SHA256, source=table["source"],
        resource="cases/taylor_gertler_cr_table.json", lookup="fixed_declared_package_resource", source_axis_mapping=table["source_axis_mapping"])


def _unavailable(data, reason, path="$.options.resistance"):
    data["diagnostics"].append(diagnostic("analysis.resistance_unavailable", reason, path))
    data["validity"] = dict(complete=False, numerical_convergence=None, model_applicable=False, historical_validated=None)
    data["reason"] = reason
    return data, "unavailable"


def _fixed_power_study(data, project, state, options, stages):
    """Bracket and bisect a declared shaft power on one selected QPC curve."""
    request = options["resistance"]
    target = request["fixed_shaft_power_kw"]
    study = dict(status="unavailable", requested_shaft_power_kw=target,
                 speed_kn=None, model_applicable=False, primary_result=False,
                 method="bracketed_selected_plane_shaft_power_v1",
                 reason="no complete monotone power bracket inside the supplied speed grid")
    rows = data["power_rows"]
    if len(rows) < 2 or any(row["shaft_power_kw"] is None for row in rows):
        return study
    if any(right["shaft_power_kw"] <= left["shaft_power_kw"]
           for left, right in zip(rows, rows[1:])):
        return study
    pair = next(((left, right) for left, right in zip(rows, rows[1:])
                 if left["shaft_power_kw"] <= target <= right["shaft_power_kw"]), None)
    if pair is None:
        return study
    low, high = pair[0]["speed_kn"], pair[1]["speed_kn"]
    applicable = pair[0]["primary_result"] and pair[1]["primary_result"]
    for _ in range(16):
        mid = (low + high) / 2
        trial_options = copy.deepcopy(options)
        trial_request = trial_options["resistance"]
        trial_request["mode"] = "predict_power"
        trial_request.pop("fixed_shaft_power_kw", None)
        trial_request["speeds_kn"] = [mid]
        trial, _ = compute(project, state, trial_options, stages)
        trial_row = trial["power_rows"][0]
        if trial_row["shaft_power_kw"] is None:
            study["reason"] = "resistance method became unavailable inside the bracket"
            return study
        applicable = applicable and trial_row["primary_result"]
        if trial_row["shaft_power_kw"] < target:
            low = mid
        else:
            high = mid
    study.update(status="completed" if applicable else "estimated_nonprimary",
                 speed_kn=(low+high)/2, bracket_speeds_kn=[pair[0]["speed_kn"], pair[1]["speed_kn"]],
                 model_applicable=bool(applicable), primary_result=bool(applicable),
                 estimate=True, reason=None if applicable else "resistance rows do not satisfy the project applicability policy")
    return study


def compute(project, state, options, stages):
    request = options["resistance"]
    scenario = copy.deepcopy(request.get("scenario") or next(s for s in project["resistance_scenarios"] if s["id"] == request["scenario_id"]))
    equilibrium, measured = stages["equilibrium"]["data"], stages["hydrostatics"]["data"]
    plane = {key: equilibrium[key] for key in ("p", "q", "waterline_d_m")}
    data = dict(method=scenario["method"], method_version="selected-plane-resistance-adapter-2",
        scenario=scenario, selected_plane=plane, selected_volume_m3=measured["values"]["volume_m3"],
        input_fingerprint=state["input_fingerprint"], geometry_source=copy.deepcopy(project["geometry"].get("source")),
        estimate=True, primary_result=False, rows=[], power_rows=[], effective_inputs={}, diagnostics=[], assumptions=[],
        wetted_surface=copy.deepcopy(measured["wetted_surface"]), source_table=None)
    policy = scenario["attitude_policy"]
    proxy = policy == "selected_plane_longitudinal_trim_proxy_v1"
    if options["equilibrium"]["liquid_loads"] or abs(plane["q"]) > 1e-10:
        return _unavailable(data, "empirical adapter excludes additional liquid/damage and physical heel states")
    if not proxy and not measured["upright_empirical_eligible"]:
        return _unavailable(data, "strict upright empirical geometry is unavailable at the actual selected attitude")
    if proxy:
        data["assumptions"].append(dict(method=policy, estimate=True, primary_result=False,
            model_applicable=False, actual_p=plane["p"], actual_q=plane["q"],
            q_roundoff_recognition_tolerance=1e-10, plane_changed=False,
            statement="body-axis ratios at the actual selected plane; q tolerance recognizes numerical roundoff only, not a physical heel cutoff; no trim validation range asserted"))
        data["diagnostics"].append(diagnostic("analysis.trim_proxy_estimated",
            "explicit longitudinal-trim proxy is estimated and non-primary; empirical applicability is false",
            "$.options.resistance", False))
    values = measured["values"]
    length, beam, draft, volume = (values[key] for key in ("waterline_length_body_x_m", "waterline_beam_body_y_m",
                                                       "reference_draft_midships_m", "volume_m3"))
    coefficients = measured["form_coefficients"]["values"]
    if any(v is None or v <= 0 for v in (length, beam, draft, volume, coefficients["cp"], coefficients["cm"])):
        return _unavailable(data, "selected-plane coefficient references are incomplete")
    inputs = copy.deepcopy(scenario.get("inputs", {}))
    if "qpc_override" in request:
        qpcs = [copy.deepcopy(request["qpc_override"])]
    elif "qpc_sensitivity" in scenario:
        sensitivity = scenario["qpc_sensitivity"]
        qpcs = [dict(value=value, source=copy.deepcopy(sensitivity["source"]), estimate=sensitivity["estimate"])
                for value in sensitivity["values"]]
    elif "qpc" in scenario:
        qpcs = [copy.deepcopy(scenario["qpc"])]
    else:
        return _unavailable(data, "explicit sourced QPC or QPC sensitivity is required for the resistance/power request")
    data["qpc_inputs"] = qpcs
    data["input_provenance"] = copy.deepcopy(scenario.get("input_provenance", {}))
    data["derived_input_provenance"] = dict(source_path="$.stages.hydrostatics.data", estimate=True,
        input_fingerprint=state["input_fingerprint"], geometry_source=copy.deepcopy(project["geometry"].get("source")))
    taylor = scenario["method"] == "taylor_gertler_source_axis_strict"
    required = ({"delta_cf", "density_kg_m3", "kinematic_viscosity_m2_s"} if taylor else
        {"c_stern", "bulb_area_m2", "transom_area_m2", "appendages", "bow_thruster", "additional_roughness_delta_ca",
         "density_kg_m3", "gravity_m_s2", "kinematic_viscosity_m2_s", "x_aft_perpendicular_m", "x_fore_perpendicular_m"})
    allowed = required if taylor else required | {"bulb_height_m"}
    missing = [key for key in sorted(required) if inputs.get(key) is None]
    if missing:
        return _unavailable(data, "missing explicit scenario choices: " + ", ".join(missing))
    if inputs.keys() - allowed:
        return _unavailable(data, "scenario inputs not consumed by selected method: " + repr(sorted(inputs.keys() - allowed)))
    if taylor:
        choices = dict(friction_method="schoenherr_implicit_ittc_0.242", interpolation_method="taylor_gertler_source_axis_strict",
                       speed_conversion_method="international_knot_exact")
        if any(scenario.get(key) != value for key, value in choices.items()):
            return _unavailable(data, "Taylor requires explicit strict source-axis, implicit Schoenherr and exact-knot method choices")
        table, data["source_table"] = _source_table(scenario)
        effective = dict(lwl_m=length, s_m2=measured["wetted_surface"]["area_m2"], cp=coefficients["cp"],
            bt=beam/draft, volumetric=volume/length**3, estimate=True, loading_condition=state["condition_id"],
            sources=data["derived_input_provenance"])
        data["effective_inputs"] = effective
        native = resistance.speed_power_curve(effective, request["speeds_kn"], table, qpc=qpcs[0]["value"],
            rho=inputs["density_kg_m3"], nu=inputs["kinematic_viscosity_m2_s"], delta_cf=inputs["delta_cf"], **choices)
        data["kernel"] = native
        data["assumptions"].append("kernel legacy horsepower and unsourced-QPC warning retained verbatim; canonical shaft kW uses PE/QPC and precise units.convert separately")
        for row in native["rows"]:
            row_diagnostics = copy.deepcopy(row.get("diagnostics", []))
            for entry in row_diagnostics:
                entry['kernel_path'] = entry['path']
                entry['path'] = '$.options.resistance' + entry['path'][1:]
            data['diagnostics'].extend(row_diagnostics)
            data["rows"].append(dict(speed_kn=row["speed_kn"], total_resistance_kn=row["rt_kN"],
                effective_power_kw=row["pe_kw"], complete=row["complete"],
                primary_result=row["primary_result"] and not proxy, model_applicable=row["model_applicable"] and not proxy,
                estimate=True, kernel_row=row, diagnostics=row_diagnostics,
                components=dict(friction_kn=row.get("rf_kN"), wave_kn=row.get("rr_kN"),
                    wave_fraction_pct=100*row["rr_kN"]/row["rt_kN"]
                        if row.get("rr_kN") is not None and row.get("rt_kN") else None,
                    wave_definition="Taylor residual resistance; includes non-friction residual effects")))
    else:
        aft, fore = inputs.pop("x_aft_perpendicular_m"), inputs.pop("x_fore_perpendicular_m")
        if not math.isclose(fore-aft, length, rel_tol=1e-10, abs_tol=1e-10):
            return _unavailable(data, "declared perpendicular length does not match selected station-support length")
        tf, ta = plane["waterline_d_m"]+plane["p"]*fore-project["geometry"]["keel_offset_m"], plane["waterline_d_m"]+plane["p"]*aft-project["geometry"]["keel_offset_m"]
        mean_draft = (tf+ta)/2
        if min(tf, ta) <= 0:
            return _unavailable(data, "selected fore/aft drafts must be positive")
        area_mid = coefficients["cm"] * beam * draft
        effective = dict(inputs, lwl_m=length, beam_m=beam, draft_fore_m=tf, draft_aft_m=ta,
            displacement_volume_m3=volume, midship_coeff=area_mid/(beam*mean_draft),
            waterplane_coeff=values["awp_projected_xy_m2"]/(length*beam),
            lcb_percent_lwl=100*(values["lcb_m"]-(aft+fore)/2)/length,
            wetted_surface_m2=measured["wetted_surface"]["area_m2"], input_provenance=data["input_provenance"])
        data["effective_inputs"] = effective
        data["perpendiculars"] = dict(aft_x_m=aft, fore_x_m=fore, source=scenario["input_provenance"])
        data["not_applied_scenario_fields"] = [key for key in ("table_id", "table_sha256", "friction_method", "interpolation_method", "speed_conversion_method") if key in scenario]
        for speed in request["speeds_kn"]:
            try:
                native = holtrop.compute({**effective, "speed_kn": speed})
                primary = native["applicability"]["primary_result"] and not proxy
                data["rows"].append(dict(speed_kn=speed, total_resistance_kn=native["values"]["total_resistance_kn"],
                    effective_power_kw=native["values"]["effective_power_kw"], complete=native["scenario"]["complete"],
                    primary_result=primary, model_applicable=primary, estimate=True, kernel=native,
                    components=dict(friction_kn=native["values"]["rf_kn"], wave_kn=native["values"]["rw_kn"],
                        wave_fraction_pct=100*native["values"]["rw_kn"]/native["values"]["total_resistance_kn"]
                            if native["values"]["total_resistance_kn"] else None,
                        wave_definition="Holtrop RW term only; other resistance terms excluded")))
            except holtrop.HoltropError as error:
                data["rows"].append(dict(speed_kn=speed, total_resistance_kn=None, effective_power_kw=None,
                    complete=False, primary_result=False, model_applicable=False, estimate=True, diagnostics=error.diagnostics))
    for row in data["rows"]:
        for qpc in qpcs:
            shaft = row["effective_power_kw"]/qpc["value"] if row["effective_power_kw"] is not None else None
            data["power_rows"].append(dict(speed_kn=row["speed_kn"], qpc=copy.deepcopy(qpc),
                effective_power_kw=row["effective_power_kw"], shaft_power_kw=shaft,
                shaft_power_shp=units.convert(shaft, "kW", "shp") if shaft is not None else None,
                complete=row["complete"], estimate=True, primary_result=row["primary_result"],
                formula="shaft_power_kw=effective_power_kw/qpc; shaft_power_shp=units.convert(kW,shp)"))
    complete = all(row["complete"] for row in data["rows"])
    data["primary_result"] = all(row["primary_result"] for row in data["rows"])
    if request["mode"] == "fixed_power":
        data["fixed_power_study"] = _fixed_power_study(data, project, state, options, stages)
        if data["fixed_power_study"]["speed_kn"] is None:
            data["diagnostics"].append(diagnostic("analysis.fixed_power_no_bracket",
                data["fixed_power_study"]["reason"], "$.options.resistance", False))
            complete = False
    data["validity"] = dict(complete=complete, numerical_convergence=None,
        model_applicable=data["primary_result"], historical_validated=None)
    return data, "completed" if complete else "model_limit"
