"""Bind and apply reviewed systems proposals without rerunning geometry kernels."""
import copy

try:
    from . import _analysis_request as requests
    from . import loading, project_io, systems
except ImportError:
    import _analysis_request as requests
    import loading, project_io, systems


def bind(summary, state, request_fingerprint):
    for proposal in summary["update_proposals"]:
        row = summary["systems"][proposal["source_system_id"]]
        model = next(m for m in row["mass_models"] if m["id"] == proposal["source_model_id"])
        proposal.update(condition_id=state["condition_id"], target="selected_condition",
            project_fingerprint=state["project_fingerprint"], input_fingerprint=state["input_fingerprint"],
            request_fingerprint=request_fingerprint, model=copy.deepcopy(model))
    return summary


def apply(project, condition_id, proposal, *, current_request, target):
    if target != "selected_condition":
        requests.reject("only selected_condition mass application is supported", "$.target", "analysis.proposal_scope")
    requests.obj(current_request, {"schema", "condition_id", "options"}, "$.current_request")
    if current_request.get("schema") != "plimsoll-analysis-request-1" or current_request.get("condition_id") != condition_id:
        requests.reject("current request must identify this selected condition", "$.current_request", "analysis.proposal_stale")
    if "options" not in current_request:
        requests.reject("current normalized options are required; an echoed hash is insufficient", "$.current_request")
    snapshot, request, fingerprint = requests.normalize(project, condition_id, current_request["options"])
    state = loading.resolve_loading(snapshot, condition_id)
    submitted = requests.json_copy(proposal, "$.proposal")
    if not isinstance(submitted, dict):
        requests.reject("proposal must be an object", "$.proposal")
    for key, current in (("project_fingerprint", state["project_fingerprint"]),
                         ("input_fingerprint", state["input_fingerprint"]), ("request_fingerprint", fingerprint)):
        if submitted.get(key) != current:
            requests.reject("proposal identity no longer matches the current project/loading/request",
                            "$.proposal." + key, "analysis.proposal_stale")
    try:
        actual = bind(systems.summary(snapshot, state), state, fingerprint)
    except ValueError as error:
        requests.reject(str(error), "$.systems", "analysis.proposal_unavailable")
    if not actual["complete"]:
        requests.reject("systems ownership/loading is incomplete", "$.systems", "analysis.proposal_unavailable")
    matches = [p for p in actual["update_proposals"] if p["item_id"] == submitted.get("item_id")
               and p["source_system_id"] == submitted.get("source_system_id")
               and p["source_model_id"] == submitted.get("source_model_id")]
    if len(matches) != 1 or submitted != matches[0]:
        requests.reject("submitted proposal differs from the recomputed physical model and provenance",
                        "$.proposal", "analysis.proposal_forged")
    verified = matches[0]
    model = verified["model"]
    provenance = copy.deepcopy(model.get("input_provenance"))
    provenance_origin = "per_input_model_metadata"
    if not provenance and model["estimate"] is False:
        # The reviewed systems contract permits a non-estimated model-level
        # source. Preserve that origin explicitly rather than invent a survey.
        provenance = {key: dict(source=copy.deepcopy(model["source"]), estimate=False) for key in model["inputs"]}
        provenance_origin = "declared_nonestimated_model_source"
    acceptance = dict(operation="replace_weight_item_mass", condition_id=condition_id,
        source_system_id=verified["source_system_id"], source_model_id=verified["source_model_id"],
        method=model["method"], formula=model["formula"], inputs=copy.deepcopy(model["inputs"]),
        input_provenance=provenance, previous_mass_t=verified["current_mass_t"], new_mass_t=verified["proposed_mass_t"],
        project_fingerprint=state["project_fingerprint"], input_fingerprint=state["input_fingerprint"], request_fingerprint=fingerprint)
    source = dict(method="accepted_selected_condition_physical_model", model_source=copy.deepcopy(model["source"]),
                  source_system_id=verified["source_system_id"], source_model_id=verified["source_model_id"],
                  formula=model["formula"], input_provenance_origin=provenance_origin)
    condition = next(c for c in snapshot["loading_conditions"] if c["id"] == condition_id)
    item_id = verified["item_id"]
    condition["overrides"].setdefault(item_id, {})["mass_t"] = verified["proposed_mass_t"]
    condition.setdefault("override_provenance", {}).setdefault(item_id, {})["mass_t"] = dict(
        source=source, estimate=model["estimate"], acceptance=acceptance)
    updated = project_io.normalize_project(snapshot)
    return dict(project=updated, change=dict(target=target, condition_id=condition_id, item_id=item_id,
        old_mass_t=verified["current_mass_t"], new_mass_t=verified["proposed_mass_t"], source=source,
        estimate=model["estimate"], acceptance=acceptance, current_request=request))
