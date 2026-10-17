"""Coordinate reviewed kernels against one immutable selected loading."""
import copy
import json
import math

try:
    from . import _analysis_request as request_api
    from . import loading, project_io, geometry_analysis, stability, systems, flooding
    from . import concept_design
    from . import small_angle_stability
    from . import _analysis_proposals as proposals
    from . import _analysis_bindings as bindings
except ImportError:
    import _analysis_request as request_api
    import loading, project_io, geometry_analysis, stability, systems, flooding
    import concept_design
    import small_angle_stability
    import _analysis_proposals as proposals
    import _analysis_bindings as bindings

AnalysisInputError = request_api.AnalysisInputError
METHOD_VERSION = request_api.VERSIONS["coordinator"]
# The batch argument of apply_mass_proposals shadows this name, so keep a stable
# module alias next to it.
proposal_api = proposals
DEPENDENCIES = {
    "loading": [], "systems": ["loading"], "l0": [], "geometry": [],
    "equilibrium": ["loading", "geometry"], "hydrostatics": ["equilibrium"],
    "gz": ["loading", "geometry"], "deck": ["equilibrium"],
    "hydrostatic_curve": ["geometry"], "bonjean": ["geometry"],
    "resistance": ["hydrostatics"], "propulsion": ["loading", "systems"],
    "endurance": ["propulsion"], "historical": ["loading"], "flooding": ["loading", "geometry"],
    "design_balance": ["loading", "systems"],
    # The compatibility design is self-contained: it reads the optional
    # sps_3b3_design declaration and nothing from the physical ledger, hull lines
    # or centre of gravity, so it must never be gated by them.
    "sps_compat": [],
    # The native ship design stage is likewise self-contained: it reads the
    # authoritative declaration and the managed mass ledger, never hull lines or a
    # centre of gravity, so a fresh empty design is never gated by physical
    # geometry it has not been given.
    "ship_design": [],
}
# The adapted concept screen and the systems summary read selected masses, not a
# physical result, so they still run when the loading ledger is incomplete or a CG
# is missing. The loading stage keeps its truthful incomplete status, and geometry
# and the physical stages stay blocked exactly as before.
SOFT_DEPENDENCIES = {
    "systems": {"loading"},
    "design_balance": {"loading", "systems"},
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
                for i,item in enumerate(value):
                    path=f'{prefix}.warnings[{i}]'
                    if isinstance(item,dict):
                        row=copy.deepcopy(item)
                        row.setdefault('code','analysis.kernel_warning');row.setdefault('message','')
                        row.setdefault('path',row.get('field',path));row.setdefault('severity','warning');row.setdefault('blocking',False)
                    else:row=request_api.diagnostic('analysis.kernel_warning',str(item),path,False)
                    row.update(stage=stage,source_path=row.get('source_path',path));result.append(row)
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


#: Compatibility stage status -> the coordinator's own stage vocabulary.
_SPS_STAGE_STATUS = {"available": "completed", "completed": "completed", "ok": "completed",
                     "partial": "partial", "unavailable": "unavailable"}


def _sps_compat_result(snapshot):
    """Run the SpringSharp 3b3 compatibility stage over the saved declaration.

    The compatibility design is an entry point of its own. It reads only the
    optional ``sps_3b3_design`` section — never the physical ledger, hull lines or
    centre of gravity — so a design the original program completes is reported on
    its own terms. A missing kernel or declaration is an honest structured
    unavailability, not a failed project, and source warnings alone never demote a
    complete design.
    """
    design = snapshot.get("sps_3b3_design")
    if not isinstance(design, dict):
        return {"status": "unavailable", "diagnostics": [request_api.diagnostic(
            "analysis.sps_design_missing",
            "the sps_compat stage requires an sps_3b3_design section",
            "$.sps_3b3_design")]}
    module = request_api.kernel_module("sps_compat")
    if module is None:
        return {"status": "unavailable", "diagnostics": [request_api.diagnostic(
            "analysis.sps_module_unavailable",
            "the SpringSharp 3b3 compatibility kernel is not available in this installation",
            "$.sps_3b3_design")]}
    try:
        data = dict(module.compute(design))
    except Exception as error:
        return {"status": "unavailable", "diagnostics": [request_api.diagnostic(
            "analysis.sps_kernel_error",
            "the compatibility kernel failed: %s" % (error,),
            "$.sps_3b3_design")]}
    # The underlying method is an empirical source-compatibility calculation; the
    # stage must not be read as a physical hydrostatics or CG claim.
    data.setdefault("kind", "sps_3b3_empirical_compatibility")
    report_module = request_api.kernel_module("sps_report")
    if report_module is not None and hasattr(report_module, "build"):
        try:
            report = report_module.build(data)
        except Exception as error:
            data.setdefault("diagnostics", []).append(request_api.diagnostic(
                "analysis.sps_report_error",
                "the compatibility report could not be built: %s" % (error,),
                "$.sps_3b3_design", False))
        else:
            if isinstance(report, dict):
                data["report"] = report
    return data


def _sps_stage_status(data):
    return _SPS_STAGE_STATUS.get(str(data.get("status")), "unavailable")


#: Native stage status -> the coordinator's own stage vocabulary. The native
#: kernel speaks the same words the compatibility stage does, so one map serves
#: both; an unknown word is an honest unavailability rather than a silent pass.
def _ship_design_stage_status(data):
    return _SPS_STAGE_STATUS.get(str(data.get("status")), "unavailable")


def _ship_design_result(snapshot, condition_id):
    """Run the native ship design stage over the saved declaration.

    The native declaration is the product's own entry point. It reads only the
    ``ship_design`` section and the managed mass ledger — never hull lines or a
    centre of gravity — so a fresh empty design is reported on its own terms: an
    empirical screen plus the owner-condition ledger and balance, all computed by
    the pure native kernel. The result carries the kernel's own structured
    diagnostics and source identity unchanged; this function only records which
    condition was *requested* here and which condition the declaration itself
    *bases* its ledger on, so a caller can never mistake one for the other.
    """
    design = snapshot.get("ship_design")
    if not isinstance(design, dict):
        return {"status": "unavailable", "diagnostics": [request_api.diagnostic(
            "analysis.ship_design_missing",
            "the ship_design stage requires a ship_design declaration",
            "$.ship_design")]}
    module = request_api.kernel_module("ship_design")
    if module is None:
        return {"status": "unavailable", "diagnostics": [request_api.diagnostic(
            "analysis.ship_design_module_unavailable",
            "the native ship design kernel is not available in this installation",
            "$.ship_design")]}
    try:
        computed = module.compute(snapshot, condition_id)
    except Exception as error:
        diagnostics = getattr(error, "diagnostics", None)
        if isinstance(diagnostics, list) and diagnostics:
            return {"status": "unavailable", "diagnostics": list(diagnostics)}
        return {"status": "unavailable", "diagnostics": [request_api.diagnostic(
            "analysis.ship_design_kernel_error",
            "the native ship design kernel failed: %s" % (error,),
            "$.ship_design")]}
    data = dict(computed)
    # The underlying method is an empirical native screen over the declared
    # design; the stage must never be read as a physical hydrostatics or CG claim.
    data.setdefault("kind", "native_ship_design")
    data["requested_condition_id"] = condition_id
    declared_basis = design.get("condition_id")
    data["basis_condition_id"] = declared_basis if isinstance(declared_basis, str) else None
    return data


ROLL_ASSUMPTIONS = ["small-angle static estimate about the selected loading",
                    "no added inertia, no added damping, no coupled roll/heave/pitch dynamics",
                    "not a natural period of the coupled system and not a safety criterion"]
UPROLL_REASON = ("nonzero trim: the sourced roll gyration coefficient is a body-x inertia axis and "
                 "cannot be reused about the inclined longitudinal axis u0; a new inertia tensor "
                 "about u0 is outside this method")
MISSING_INPUTS_REASON = ("positive selected GM and an explicitly sourced gyration coefficient are "
                         "required")


def _scalar_roll(geometry, declared_hull, state, equilibrium, measures, small_angle,
                 equilibrium_options):
    """Return the honest scalar-roll study for the selected loading.

    Three gates apply to every path: an explicitly sourced gyration coefficient,
    an effective transverse scale, and a proved reflection symmetry about y = 0
    without which heave and trim couple to a first-order roll response. The
    original upright, no-moving-liquid formula keeps its own method identity; a
    moving liquid uses the new equilibrium restoring height, computed by the
    small-angle kernel with the free-surface effect counted once, and reports the
    new method identity.
    """
    values = measures["values"]
    hull = declared_hull if isinstance(declared_hull, dict) else {}
    coefficient = hull.get("roll_gyration_coeff")
    source = (hull.get("sources") or {}).get("roll_gyration_coeff")
    beam = values.get("waterline_beam_body_y_m")
    legacy_gm = values.get("gm_t_m")
    trim_deg = abs(equilibrium.get("trim_deg", 0.0))
    heel_deg = abs(equilibrium.get("heel_deg", 0.0))
    moving = bool(equilibrium.get("liquids"))
    upright = heel_deg < 1e-8 and trim_deg < 1e-8
    study = dict(status="unavailable", period_s=None, selected_gm_m=None, selected_beam_m=beam,
                 gyration_coeff=coefficient, source=copy.deepcopy(source), estimate=True,
                 method="selected_loading_small_angle_roll_v1",
                 assumptions=list(ROLL_ASSUMPTIONS), restoring_gm_m=None,
                 restoring_source=None, restoring_method=None, symmetry=None,
                 reason=MISSING_INPUTS_REASON)
    if not isinstance(coefficient, (int, float)) or isinstance(coefficient, bool) \
            or coefficient <= 0 or not source or not isinstance(beam, (int, float)) \
            or isinstance(beam, bool) or beam <= 0:
        return study
    symmetry = small_angle_stability.scalar_roll_eligibility(
        geometry, state, equilibrium_options, equilibrium=equilibrium)
    study["symmetry"] = symmetry
    if symmetry.get("baseline_applicable") is not True:
        study["reason"] = ("selected equilibrium baseline is not eligible for scalar roll: "
                           + str(symmetry.get("baseline_plane", {}).get("reason")
                                 or "baseline applicability is unknown"))
        return study
    if not symmetry["symmetry_proved"]:
        study["reason"] = ("reflection symmetry about y = 0 is not proved, so heave and trim do "
                           "not decouple from a first-order roll response: "
                           + "; ".join(symmetry["reasons"]))
        return study
    if not upright:
        study["reason"] = UPROLL_REASON if trim_deg >= 1e-8 else MISSING_INPUTS_REASON
        if heel_deg >= 1e-8:
            study["reason"] = "nonzero equilibrium heel: the selected loading does not float upright"
        return study
    if not moving:
        if not isinstance(legacy_gm, (int, float)) or isinstance(legacy_gm, bool) or legacy_gm <= 0:
            return study
        study.update(status="completed", reason=None, selected_gm_m=legacy_gm,
                     restoring_gm_m=legacy_gm,
                     restoring_source="upright geometric KM minus selected KG",
                     restoring_method="upright_hydrostatic_km_minus_kg",
                     period_s=2 * math.pi * coefficient * beam / math.sqrt(9.80665 * legacy_gm))
        return study
    # Moving liquids: only a resolved positive equilibrium restoring height,
    # with the free-surface effect already inside it, may carry a period.
    stiffness = small_angle.get("equilibrium_gm_m")
    resolved = (small_angle.get("status") == "completed"
                and small_angle.get("restoring_sign") == "positive"
                and isinstance(stiffness, (int, float)) and not isinstance(stiffness, bool)
                and stiffness > 0)
    study.update(method="selected_loading_equilibrium_roll_v2",
                 restoring_gm_m=stiffness if isinstance(stiffness, (int, float)) else None,
                 restoring_source=small_angle.get("definition"),
                 restoring_method=small_angle.get("method_version"))
    if not resolved:
        study["method"] = "selected_loading_small_angle_roll_v1"
        study["reason"] = ("a resolved positive free-trim restoring height is required for a moving "
                           "liquid: " + str(small_angle.get("reason") or "restoring sign unresolved"))
        return study
    study.update(status="completed", reason=None, selected_gm_m=stiffness,
                 period_s=2 * math.pi * coefficient * beam / math.sqrt(9.80665 * stiffness))
    return study


def compute_project(project, condition_id, options=None, *, cancel_check=None):
    """Return one selected-loading result; never read caller/project paths or save."""
    if cancel_check is not None and not callable(cancel_check):
        request_api.reject("cancel_check must be callable", "$.cancel_check")
    snapshot, request, fingerprint = request_api.normalize(project, condition_id, options)
    opts = request["options"]
    requested = set(opts["stages"])
    active = set() if requested and requested <= {"sps_compat", "ship_design"} else {"loading"}
    def require(name):
        if name in active:
            return
        active.add(name)
        for dependency in DEPENDENCIES[name]:
            require(dependency)
    for name in requested:
        require(name)
    if 'loading' in active:
        try:
            state = loading.resolve_loading(snapshot, condition_id)
        except loading.LoadingRangeError as error:
            request_api.reject(str(error), '$.weight_groups', 'loading.derived_out_of_range')
    else:
        project_fingerprint=project_io.input_fingerprint(snapshot)
        state={'project_fingerprint':project_fingerprint,
               'input_fingerprint':loading._result_fingerprint(project_fingerprint,condition_id)}
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
        if name in SOFT_DEPENDENCIES:
            # Data presence is enough; a truthful incomplete loading stage must not
            # block an empirical mass screen that never reads a CG.
            failed_dependencies = [d for d in failed_dependencies
                                   if stages[d].get("data") is None
                                   or stages[d]["status"] in ("canceled", "failed")]
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
                small_angle = small_angle_stability.analyze(geometry, state, opts["equilibrium"])
                data["small_angle_stability"] = small_angle
                data["values"]["equilibrium_gm_t_m"] = small_angle.get("equilibrium_gm_m")
                data["equilibrium_gm_definition"] = small_angle.get("definition")
                data["methods"] = {"small_angle_stability": small_angle_stability.METHOD_VERSION}
                data["input_fingerprint"] = state["input_fingerprint"]
                data["loaded_roll"] = _scalar_roll(geometry, snapshot["hull"], state, equilibrium, data,
                                                  small_angle, opts["equilibrium"])
                _finish(envelope, name, data, data["status"])
                # Stage metadata names the kernel that produced the nested
                # result, so a stale small-angle result cannot pass as current.
                envelope["method_versions"]["small_angle_stability"] = (
                    small_angle_stability.METHOD_VERSION)
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
            elif name == "design_balance":
                if isinstance(snapshot.get("ship_design"), dict):
                    # The native declaration owns the shared ledger, its estimated
                    # masses and their adoption. Running the legacy concept screen
                    # here would produce a second estimate and adoption authority
                    # for the same targets, which the unified design forbids even
                    # when a caller explicitly asks for this stage.
                    _unavailable(envelope, name,
                                 "the native ship design owns the ledger balance and estimated "
                                 "masses; the legacy concept screen would be a second adoption "
                                 "authority for the same targets and is not produced",
                                 "analysis.design_balance_native_owned")
                    continue
                data = concept_design.evaluate(
                    snapshot, state, stages["systems"].get("data"))
                _finish(envelope, name, data, data.get("status", "completed"),
                        applicable=data.get("status") != "not_configured")
            elif name == "sps_compat":
                data = _sps_compat_result(snapshot)
                mapped = _sps_stage_status(data)
                _finish(envelope, name, data, mapped, complete=(mapped == "completed"),
                        applicable=(mapped != "unavailable"))
            elif name == "ship_design":
                data = _ship_design_result(snapshot, condition_id)
                mapped = _ship_design_stage_status(data)
                _finish(envelope, name, data, mapped, complete=(mapped == "completed"),
                        applicable=(mapped != "unavailable"))
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


def apply_mass_proposals(project, condition_id, proposals, *, current_request,
                         target="selected_condition"):
    """Apply a reviewed batch atomically against one recomputed snapshot.

    Every proposal is revalidated together; a rejection writes nothing. The
    caller's project is never mutated and other conditions and base weights are
    preserved.
    """
    return proposal_api.apply_many(project, condition_id, proposals,
                                   current_request=current_request, target=target)
