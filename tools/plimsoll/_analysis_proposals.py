"""Bind and apply reviewed systems proposals without rerunning geometry kernels.

A batch is recomputed against **one** original immutable snapshot, matched in
full, and written atomically to the selected condition's overrides. A rejection
never leaves a partial write behind, and the caller's project is never mutated.
"""
import copy

try:
    from . import _analysis_request as requests
    from . import loading, project_io, systems
except ImportError:
    import _analysis_request as requests
    import loading, project_io, systems

EMPIRICAL_METHODS = {"empirical_estimate_v1"}


def bind(summary, state, request_fingerprint):
    for proposal in summary["update_proposals"]:
        row = summary["systems"][proposal["source_system_id"]]
        model = next(m for m in row["mass_models"] if m["id"] == proposal["source_model_id"])
        proposal.update(condition_id=state["condition_id"], target="selected_condition",
            project_fingerprint=state["project_fingerprint"], input_fingerprint=state["input_fingerprint"],
            request_fingerprint=request_fingerprint, model=copy.deepcopy(model))
    return summary


AMBIGUITY_CODES = frozenset({
    "systems.weight_item_duplicate", "systems.weight_item_unknown",
    "systems.weight_item_shared", "systems.present_without_weight_items",
    "systems.generated_model_duplicate",
})


def _owners(summary, item_id):
    return [system_id for system_id, row in summary.get("systems", {}).items()
            if item_id in {linked["id"] for linked in row.get("linked_items", [])}]


def _ambiguity(summary, proposal):
    """Only genuine ambiguity blocks a proposal.

    An unknown target mass, an unrelated unknown mass, a missing CG and an
    incomplete ledger are all legitimate: the estimate is still independent and
    fully owned. What is rejected is an item owned by more than one system, an
    item the source system does not own, or a duplicate model identity.
    """
    item_id = proposal.get("item_id")
    if not isinstance(item_id, str) or not item_id:
        return dict(code="analysis.proposal_ownership", message="item_id must be a non-empty string")
    owners = _owners(summary, item_id)
    if len(owners) > 1:
        return dict(code="analysis.proposal_ownership",
                    message="item %r is owned by multiple systems %r" % (item_id, owners))
    if owners != [proposal.get("source_system_id")]:
        return dict(code="analysis.proposal_ownership",
                    message="item %r is owned by %r, not by the proposal's source system %r"
                            % (item_id, owners, proposal.get("source_system_id")))
    for diagnostic in summary.get("diagnostics", []):
        if diagnostic.get("blocking") and diagnostic.get("code") in AMBIGUITY_CODES:
            path = str(diagnostic.get("path", ""))
            if item_id in str(diagnostic.get("message", "")) or path == "$.systems":
                return dict(code="analysis.proposal_ownership",
                            message="ownership is ambiguous: %s" % (diagnostic.get("message"),))
    return None


def _acceptance(verified, model, state, fingerprint, condition_id):
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
        input_provenance=provenance, previous_mass_t=verified["current_mass_t"],
        new_mass_t=verified["proposed_mass_t"], project_fingerprint=state["project_fingerprint"],
        input_fingerprint=state["input_fingerprint"], request_fingerprint=fingerprint)
    empirical = model["method"] in EMPIRICAL_METHODS
    source = dict(
        method=("accepted_selected_condition_empirical_estimate" if empirical
                else "accepted_selected_condition_physical_model"),
        model_source=copy.deepcopy(model["source"]),
        source_system_id=verified["source_system_id"], source_model_id=verified["source_model_id"],
        formula=model["formula"], input_provenance_origin=provenance_origin)
    if empirical:
        source["comparison_policy"] = copy.deepcopy(model.get("comparison_policy"))
        source["method_version"] = model["inputs"].get("method_version")
        source["kernel"] = model["inputs"].get("kernel")
        source["source_sha256"] = model["inputs"].get("source_sha256")
        source["assembly"] = kernels_source(model)
        source["boundary"] = copy.deepcopy(model.get("boundary"))
    return acceptance, source


def kernels_source(model):
    """The assembly identity recorded with the accepted estimate, when present."""
    declared = model.get("source")
    if isinstance(declared, dict):
        return copy.deepcopy(declared.get("assembly"))
    return None


def apply_many(project, condition_id, proposals, *, current_request, target="selected_condition"):
    """Apply a reviewed batch of mass proposals to one selected condition."""
    if target != "selected_condition":
        requests.reject("only selected_condition mass application is supported", "$.target",
                        "analysis.proposal_scope")
    requests.obj(current_request, {"schema", "condition_id", "options"}, "$.current_request")
    if current_request.get("schema") != "plimsoll-analysis-request-1" or current_request.get("condition_id") != condition_id:
        requests.reject("current request must identify this selected condition", "$.current_request",
                        "analysis.proposal_stale")
    if "options" not in current_request:
        requests.reject("current normalized options are required; an echoed hash is insufficient",
                        "$.current_request")
    if not isinstance(proposals, list):
        requests.reject("proposals must be an array", "$.proposals")
    if not proposals:
        requests.reject("select at least one proposal; an empty batch is not an application",
                        "$.proposals", "analysis.proposal_empty")
    snapshot, request, fingerprint = requests.normalize(project, condition_id, current_request["options"])
    condition = next((c for c in snapshot["loading_conditions"] if c["id"] == condition_id), None)
    if condition is None:
        requests.reject("condition_id must identify an existing loading condition", "$.condition_id")
    if condition.get("definition"):
        # A subtraction condition is derived from a base condition and must not
        # carry overrides of its own; the base is never modified implicitly.
        requests.reject(
            "condition %r is a derived subtraction condition; apply the reviewed masses to its "
            "base condition %r or declare an explicit override condition instead"
            % (condition_id, condition["definition"].get("base_condition_id")),
            "$.condition_id", "analysis.proposal_derived_condition")
    submitted = [requests.json_copy(proposal, "$.proposals[%d]" % index)
                 for index, proposal in enumerate(proposals)]
    for entry in submitted:
        if not isinstance(entry, dict):
            requests.reject("each proposal must be an object", "$.proposals")
        for key in ("item_id", "source_system_id", "source_model_id"):
            if not isinstance(entry.get(key), str) or not entry.get(key):
                requests.reject("each proposal needs a non-empty string %s" % (key,), "$.proposals")
    state = loading.resolve_loading(snapshot, condition_id)
    for key, current in (("project_fingerprint", state["project_fingerprint"]),
                         ("input_fingerprint", state["input_fingerprint"]),
                         ("request_fingerprint", fingerprint)):
        for index, entry in enumerate(submitted):
            if entry.get(key) != current:
                requests.reject("proposal identity no longer matches the current project/loading/request",
                                "$.proposals[%d].%s" % (index, key), "analysis.proposal_stale")
    targets = [entry["item_id"] for entry in submitted]
    duplicates = sorted({item for item in targets if targets.count(item) > 1})
    if duplicates:
        requests.reject("a batch may carry at most one proposal per item; repeated: %r" % (duplicates,),
                        "$.proposals", "analysis.proposal_duplicate")
    try:
        actual = bind(systems.summary(snapshot, state), state, fingerprint)
    except (ValueError, TypeError, KeyError) as error:
        requests.reject(str(error), "$.systems", "analysis.proposal_unavailable")

    verified = []
    changes = []
    updates = {}
    for index, entry in enumerate(submitted):
        matches = [p for p in actual["update_proposals"] if p["item_id"] == entry.get("item_id")
                   and p["source_system_id"] == entry.get("source_system_id")
                   and p["source_model_id"] == entry.get("source_model_id")]
        if len(matches) != 1 or entry != matches[0]:
            requests.reject("submitted proposal differs from the recomputed model and provenance",
                            "$.proposals[%d]" % index, "analysis.proposal_forged")
        candidate = matches[0]
        ambiguity = _ambiguity(actual, candidate)
        if ambiguity is not None:
            requests.reject("proposal %d is not uniquely owned: %s" % (index, ambiguity["message"]),
                            "$.proposals[%d]" % index, ambiguity["code"])
        model = candidate["model"]
        acceptance, source = _acceptance(candidate, model, state, fingerprint, condition_id)
        updates.setdefault(candidate["item_id"], {})["mass_t"] = candidate["proposed_mass_t"]
        condition.setdefault("override_provenance", {}).setdefault(candidate["item_id"], {})["mass_t"] = \
            dict(source=source, estimate=model["estimate"], acceptance=acceptance)
        verified.append(candidate)
        changes.append(dict(target=target, condition_id=condition_id,
            item_id=candidate["item_id"], old_mass_t=candidate["current_mass_t"],
            new_mass_t=candidate["proposed_mass_t"], source=source,
            estimate=model["estimate"], acceptance=acceptance, current_request=request))
    for item_id, fields in updates.items():
        condition["overrides"].setdefault(item_id, {})["mass_t"] = fields["mass_t"]
    updated = project_io.normalize_project(snapshot)
    return dict(project=updated,
                changes=changes,
                # The single-proposal contract keeps its original singular key.
                change=changes[0] if len(changes) == 1 else None,
                applied_count=len(verified),
                batch=dict(target=target, condition_id=condition_id, item_ids=sorted(updates),
                           source="one recomputed immutable snapshot; atomic selected-condition write"),
                current_request=request)

def apply(project, condition_id, proposal, *, current_request, target):
    """Apply one proposal. Delegates to the same batch logic it shares."""
    return apply_many(project, condition_id, [proposal], current_request=current_request,
                      target=target)
