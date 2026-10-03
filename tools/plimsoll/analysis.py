"""Coordinate reviewed kernels against one immutable selected loading."""
import copy
import json
import math

try:
    from . import _analysis_request as request_api
    from . import loading, project_io, geometry_analysis, stability, systems, flooding
    from . import _analysis_proposals as proposals
    from . import _analysis_bindings as bindings
except ImportError:
    import _analysis_request as request_api
    import loading, project_io, geometry_analysis, stability, systems, flooding
    import _analysis_proposals as proposals
    import _analysis_bindings as bindings

AnalysisInputError = request_api.AnalysisInputError
METHOD_VERSION = request_api.VERSIONS["coordinator"]
DEPENDENCIES = {
    "loading": [], "systems": ["loading"], "l0": [], "geometry": [],
    "equilibrium": ["loading", "geometry"], "hydrostatics": ["equilibrium"],
    "gz": ["loading", "geometry"], "deck": ["equilibrium"],
    "hydrostatic_curve": ["geometry"], "bonjean": ["geometry"],
    "resistance": ["hydrostatics"], "propulsion": ["loading", "systems"],
    "endurance": ["propulsion"], "historical": ["loading"], "flooding": ["loading", "geometry"],
}


def _envelope(name, requested):
    return dict(status="not_requested", requested=requested, dependencies=list(DEPENDENCIES[name]),
        reason=None, validity=dict(complete=False, converged=None, model_applicable=None,
        historical_validated=None), method_versions={}, assumptions=[], diagnostics=[], data=None)


def _diagnostics(data, stage, prefix="$"):
    """Keep every native diagnostic/warning, including failed nested samples."""
    result = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "diagnostics" and isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        row = copy.deepcopy(item)
                        row.update(stage=stage, source_path=item.get("source_path", item.get("path", f"{prefix}.diagnostics[{i}]")))
                        row.setdefault("path", f"{prefix}.diagnostics[{i}]")
                        row.setdefault("blocking", row.get("severity") == "error")
                        result.append(row)
            elif key == "warnings" and isinstance(value, list):
                result.extend(dict(request_api.diagnostic("analysis.kernel_warning", str(text),
                    f"{prefix}.warnings[{i}]", False), stage=stage,
                    source_path=f"{prefix}.warnings[{i}]") for i, text in enumerate(value))
            else:
                result.extend(_diagnostics(value, stage, f"{prefix}.{key}"))
    elif isinstance(data, list):
        for i, value in enumerate(data):
            result.extend(_diagnostics(value, stage, f"{prefix}[{i}]"))
    return result


def _finish(envelope, stage, data, status="completed", complete=None, applicable=None):
    envelope["data"] = data
    envelope["status"] = status
    validity = data.get("validity", {})
    envelope["validity"] = dict(complete=(validity.get("complete", status == "completed") if complete is None else complete),
        converged=data.get("converged", validity.get("numerical_convergence")),
        model_applicable=validity.get("model_applicable", applicable), historical_validated=None)
    envelope["method_versions"] = {"coordinator": METHOD_VERSION}
    if "method_version" in data:
        envelope["method_versions"]["kernel"] = data["method_version"]
    if "methods" in data:
        envelope["method_versions"]["methods"] = copy.deepcopy(data["methods"])
    assumptions = data.get("assumptions", [])
    envelope["assumptions"] = copy.deepcopy(assumptions if isinstance(assumptions, list) else [assumptions])
    envelope["diagnostics"] = _diagnostics(data, stage)
    if not envelope["validity"]["complete"] and status == "completed":
        envelope["status"] = "unavailable"
    if envelope["status"] != "completed":
        envelope["reason"] = data.get("stop_reason", "requested output is incomplete or outside its model")


def _unavailable(envelope, stage, reason, code="analysis.unavailable", status="unavailable"):
    envelope.update(status=status, reason=reason)
    envelope["diagnostics"].append(dict(request_api.diagnostic(code, reason, f"$.stages.{stage}"),
                                        stage=stage, source_path=f"$.stages.{stage}"))


def compute_project(project, condition_id, options=None, *, cancel_check=None):
    """Return one selected-loading result; never read caller/project paths or save."""
    if cancel_check is not None and not callable(cancel_check):
        request_api.reject("cancel_check must be callable", "$.cancel_check")
    snapshot, request, fingerprint = request_api.normalize(project, condition_id, options)
    opts = request["options"]
    state = loading.resolve_loading(snapshot, condition_id)
    requested = set(opts["stages"])
    active = {"loading"}
    def require(name):
        if name in active:
            return
        active.add(name)
        for dependency in DEPENDENCIES[name]:
            require(dependency)
    for name in requested:
        require(name)
    stages = {name: _envelope(name, name in requested) for name in request_api.STAGES}
    geometry = snapshot.get("geometry")
    marker = snapshot["opening_definition"]
    openings = snapshot["openings"] if marker == "supplied" else None
    rho = opts["equilibrium"]["rho_t_m3"]
    for name in request_api.STAGES:
        if name not in active:
            continue
        envelope = stages[name]
        if cancel_check is not None and cancel_check():
            _unavailable(envelope, name, "calculation canceled before this stage", "analysis.canceled", "canceled")
            continue
        failed_dependencies = [d for d in DEPENDENCIES[name] if stages[d]["status"] != "completed"]
        if failed_dependencies:
            _unavailable(envelope, name, "unavailable dependencies: " + ", ".join(failed_dependencies))
            continue
        try:
            if name == "loading":
                _finish(envelope, name, state, complete=state["complete_mass"] and state["complete_cg"]
                        and not any(d["blocking"] for d in state["diagnostics"]))
            elif name == "systems":
                data = proposals.bind(systems.summary(snapshot, state), state, fingerprint)
                data = bindings.page_rows_for(snapshot, state, data)
                _finish(envelope, name, data, complete=data["complete"])
            elif name == "l0":
                data = geometry_analysis.parameterized_hydrostatics(snapshot["hull"])
                data["declared_hull"] = dict(metadata=copy.deepcopy(snapshot.get("metadata", {})),
                    design_facts=copy.deepcopy(snapshot["hull"].get("design_facts", {})),
                    display_preferences=copy.deepcopy(snapshot.get("display_preferences", {})),
                    boundary="optional design declarations; reference displacement is not selected ledger mass; deep Cb is not inferred geometry")
                data["hull_ratios"] = dict(
                    design_lwl_over_beam=snapshot["hull"]["lwl_m"] / snapshot["hull"]["beam_m"],
                    numerator="hull.lwl_m", denominator="hull.beam_m",
                    method="declared_design_dimensions_ratio_v1")
                _finish(envelope, name, data, data["status"])
            elif name == "geometry":
                if not isinstance(geometry, dict) or geometry.get("kind") != "offsets":
                    _unavailable(envelope, name, "materialized geometry required: explicitly import source bytes or materialize a reference project",
                                 "analysis.geometry_not_materialized")
                    continue
                data = stability.prepare_geometry(geometry)[3]
                _finish(envelope, name, data, applicable=True)
            elif name == "equilibrium":
                data = stability.solve_loaded_equilibrium(geometry, state, opts["equilibrium"])
                if data["converged"] and "target_trim_deg" in opts["equilibrium"]:
                    data["trim_target_study"] = stability.trim_target_study(
                        geometry, data, opts["equilibrium"]["target_trim_deg"])
                _finish(envelope, name, data, "completed" if data["converged"] else "failed")
            elif name == "hydrostatics":
                equilibrium = stages["equilibrium"]["data"]
                plane = {k: equilibrium[k] for k in ("p", "q", "waterline_d_m")}
                data = geometry_analysis.measures_at_plane(geometry, plane, rho_t_m3=rho)
                km = data["values"]["km_t_m"]
                data["values"]["gm_t_m"] = None if km is None else km - equilibrium["effective_loading"]["cg_keel_m"][2]
                selected_length = data["values"].get("waterline_length_body_x_m")
                selected_beam = data["values"].get("waterline_beam_body_y_m")
                data["selected_length_beam_ratio"] = dict(
                    value=selected_length / selected_beam if selected_length is not None
                        and selected_beam is not None and selected_beam > 0 else None,
                    numerator="selected_plane_waterline_length_body_x_m",
                    denominator="selected_plane_waterline_beam_body_y_m",
                    method="selected_plane_body_axis_dimensions_ratio_v1")
                data["gm_definition"] = "upright geometric KM minus effective KG; unavailable for inclined/contact states"
                coefficient = snapshot["hull"].get("roll_gyration_coeff")
                source = (snapshot["hull"].get("sources") or {}).get("roll_gyration_coeff")
                beam = data["values"].get("waterline_beam_body_y_m")
                gm = data["values"]["gm_t_m"]
                roll_available = (data["status"] == "completed" and
                    all(isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
                        for value in (coefficient, beam, gm)) and bool(source) and
                    abs(equilibrium.get("heel_deg", 0)) < 1e-8)
                data["loaded_roll"] = dict(
                    status="completed" if roll_available else "unavailable",
                    period_s=2*math.pi*coefficient*beam/math.sqrt(9.80665*gm) if roll_available else None,
                    selected_gm_m=gm, selected_beam_m=beam,
                    gyration_coeff=coefficient, source=source,
                    estimate=True, method="selected_loading_small_angle_roll_v1",
                    reason=None if roll_available else "positive selected GM and an explicitly sourced gyration coefficient are required")
                data["input_fingerprint"] = state["input_fingerprint"]
                _finish(envelope, name, data, data["status"])
            elif name == "gz":
                data = stability.stability_curve(geometry, state, opts["gz_angles_deg"], openings, opts["equilibrium"])
                data["opening_definition"] = marker
                _finish(envelope, name, data, "completed" if data["converged"] else
                        "model_limit" if data["endpoint"]["kind"] == "model_limit" else "failed")
            elif name == "hydrostatic_curve":
                data = geometry_analysis.hydrostatic_table(geometry, opts["hydrostatic_waterlines_above_keel_m"], rho_t_m3=rho)
                _finish(envelope, name, data, "completed" if all(r["status"] == "completed" for r in data["rows"]) else "model_limit")
            elif name == "bonjean":
                data = geometry_analysis.bonjean_table(geometry, opts["bonjean_waterlines_above_keel_m"])
                _finish(envelope, name, data, "completed" if all(r["status"] == "completed" for r in data["rows"]) else "model_limit")
            elif name == "flooding":
                selected = copy.deepcopy(opts["flooding"])
                # An explicit scenario opening declaration takes precedence. The
                # persistent marker governs only the inherited project definition.
                if "openings" not in selected["scenario"]:
                    selected["scenario"]["openings"] = copy.deepcopy(openings)
                if cancel_check is not None:
                    selected["options"]["cancel_check"] = lambda _state: cancel_check()
                data = flooding.simulate_flooding(snapshot, condition_id, selected["scenario"], selected["options"])
                data["project_opening_definition"] = marker
                data["coordinator_openings_origin"] = "scenario" if "openings" in opts["flooding"]["scenario"] else marker
                if data.get("loading") and data["loading"].get("input_fingerprint") != state["input_fingerprint"]:
                    raise ValueError("flooding returned a different selected loading fingerprint")
                mapped = {"invalid_input": "unavailable", "equilibrium_failure": "failed", "downflooding_event": "model_limit"}
                _finish(envelope, name, data, mapped.get(data["status"], data["status"]))
            else:
                data, status = bindings.run(name, snapshot, state, opts, stages)
                _finish(envelope, name, data, status)
        except (ValueError, TypeError, KeyError, OverflowError, ZeroDivisionError) as error:
            diagnostics = getattr(error, "diagnostics", [request_api.diagnostic("analysis.stage_input", str(error), f"$.stages.{name}")])
            _finish(envelope, name, {"diagnostics": diagnostics}, "unavailable", complete=False)
            envelope["reason"] = str(error)
    selected = [stages[name] for name in requested]
    complete = all(s["status"] == "completed" and s["validity"]["complete"] for s in selected)
    converged = [s["validity"]["converged"] for s in selected if s["validity"]["converged"] is not None]
    applicable = [s["validity"]["model_applicable"] for s in selected if s["validity"]["model_applicable"] is not None]
    result = dict(schema="plimsoll-analysis-1", status="canceled" if any(s["status"] == "canceled" for s in selected)
        else "completed" if complete else "partial", project_id=snapshot["id"], condition_id=condition_id,
        project_fingerprint=state["project_fingerprint"], input_fingerprint=state["input_fingerprint"],
        request_fingerprint=fingerprint, request=request, input_snapshot=snapshot,
        units=copy.deepcopy(snapshot["units"]), coordinates=copy.deepcopy(snapshot["coordinates"]),
        geometry_datum={"keel_offset_m": geometry.get("keel_offset_m"), "coordinate_origin": "explicit_geometry_datum"}
            if isinstance(geometry, dict) else None, method_versions=copy.deepcopy(request_api.VERSIONS),
        sources=copy.deepcopy(snapshot["sources"]), diagnostics=[d for s in stages.values() for d in s["diagnostics"]],
        validity=dict(complete=complete, converged=all(converged) if converged else None,
                      model_applicable=all(applicable) if applicable else None, historical_validated=None), stages=stages)
    json.dumps(result, allow_nan=False).encode("utf-8")
    return result


def materialize_reference_project(project, parameters, *, keel_offset_m, source, estimate,
                                  station_count=41, section_points=32):
    """Explicitly replace geometry in an owned project using the reviewed model."""
    normalized = project_io.normalize_project(project)
    normalized["geometry"] = geometry_analysis.materialize_reference_hull(parameters,
        keel_offset_m=keel_offset_m, source=source, estimate=estimate,
        n_stations=station_count, n_section=section_points)
    return project_io.normalize_project(normalized)


def apply_mass_proposal(project, condition_id, proposal, *, current_request, target="selected_condition"):
    """Recompute identity/model and apply only the selected condition's mass."""
    return proposals.apply(project, condition_id, proposal, current_request=current_request, target=target)
