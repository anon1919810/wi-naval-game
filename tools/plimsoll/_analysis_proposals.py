"""Bind and apply reviewed systems proposals without rerunning geometry kernels.

A batch is recomputed against **one** original immutable snapshot, matched in
full, and written atomically to the selected condition's overrides. A rejection
never leaves a partial write behind, and the caller's project is never mutated.
"""
import copy

try:
    from . import _analysis_request as requests
    from . import battery_mass_allocation, loading, project_io, systems
except ImportError:
    import _analysis_request as requests
    import battery_mass_allocation, loading, project_io, systems

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


def _allocation_cohort(proposal):
    """The whole-battery allocation cohort a proposal belongs to, or ``None``.

    The identity is read from the **recomputed** model's own inputs, never from
    anything the client supplied: a caller cannot widen, split or rename a cohort
    by editing the metadata it sends back.
    """
    model = proposal.get("model")
    inputs = model.get("inputs") if isinstance(model, dict) else None
    if not isinstance(inputs, dict):
        return None
    if inputs.get("method_version") != battery_mass_allocation.METHOD_VERSION:
        return None
    if inputs.get("allocation_policy") != battery_mass_allocation.POLICY:
        return None
    group = inputs.get("allocation_group_id")
    if not isinstance(group, str) or not group:
        return None
    return group


def _allocation_models_by_group(summary):
    """Every recomputed allocation model, grouped by its cohort id.

    The complete cohort is read from this snapshot's ``mass_models`` -- not from
    ``update_proposals`` -- because an already-exact member produces no pending
    proposal yet still belongs to the cohort and its target must not be rewritten
    away from the recomputed allocation.
    """
    by_group = {}
    for row in summary.get("systems", {}).values():
        for model in row.get("mass_models", []):
            inputs = model.get("inputs") if isinstance(model, dict) else None
            if not isinstance(inputs, dict):
                continue
            if inputs.get("method_version") != battery_mass_allocation.METHOD_VERSION:
                continue
            if inputs.get("allocation_policy") != battery_mass_allocation.POLICY:
                continue
            group = inputs.get("allocation_group_id")
            if not isinstance(group, str) or not group:
                continue
            by_group.setdefault(group, []).append(model)
    return by_group


def _reject_conflicting_cohort_alternatives(group, cohort_models, matched):
    """Refuse a cohort target rewritten through another model in the same batch.

    An already-exact member of a selected cohort carries no pending proposal, so a
    pending-only check would let a caller submit an *alternative* proposal (an
    ordinary physical model on the same target) alongside the still-pending
    members and change the exact member away from the recomputed allocation --
    which breaks the whole-battery conservation the cohort exists to preserve.
    The complete recomputed cohort, its target set and its allocated masses are
    read from the snapshot; an alternative for a cohort target is refused unless
    it already names the recomputed allocation value.
    """
    if not cohort_models:
        return
    expected = {}
    for model in cohort_models:
        target = model.get("linked_weight_item_id")
        if isinstance(target, str):
            expected.setdefault(target, model.get("calculated_mass_t"))
    for proposal in matched:
        item_id = proposal.get("item_id")
        if item_id not in expected or _allocation_cohort(proposal) == group:
            continue
        want = expected[item_id]
        if want is None or proposal.get("proposed_mass_t") != want:
            requests.reject(
                "target %r belongs to allocation group %r, whose recomputed allocation is %r; "
                "a batch that adopts this cohort may not rewrite the target to %r through "
                "another model" % (item_id, group, want, proposal.get("proposed_mass_t")),
                "$.proposals", "analysis.proposal_cohort_conflict")


def _require_complete_allocation_cohorts(summary, matched):
    """A submitted allocation member requires every still-pending member.

    The cohort is recomputed here from the immutable snapshot. A batch that
    carries one member of a still-pending allocation group is refused **before
    any write**, so a proportional split can never be half-adopted and leave the
    ledger summing to something the recovered source never said. A batch that
    selects a cohort may also never rewrite one of its targets through another
    model, even an already-exact target that has no pending proposal of its own.
    """
    submitted_groups = {}
    for proposal in matched:
        group = _allocation_cohort(proposal)
        if group is not None:
            submitted_groups.setdefault(group, set()).add(proposal["item_id"])
    if not submitted_groups:
        return
    pending_groups = {}
    for proposal in summary.get("update_proposals", []):
        group = _allocation_cohort(proposal)
        if group is not None:
            pending_groups.setdefault(group, set()).add(proposal["item_id"])
    complete = _allocation_models_by_group(summary)
    for group, items in sorted(submitted_groups.items()):
        missing = sorted(pending_groups.get(group, set()) - items)
        if missing:
            requests.reject(
                "allocation group %r must be adopted as one cohort; the still-pending members "
                "%r are missing from this batch" % (group, missing),
                "$.proposals", "analysis.proposal_cohort_incomplete")
        _reject_conflicting_cohort_alternatives(group, complete.get(group, []), matched)


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
    # Match every submitted proposal against the recomputed snapshot first, then
    # require the whole pending allocation cohort, and only then write. Nothing is
    # mutated before the cohort is complete.
    matched = []
    for index, entry in enumerate(submitted):
        matches = [p for p in actual["update_proposals"] if p["item_id"] == entry.get("item_id")
                   and p["source_system_id"] == entry.get("source_system_id")
                   and p["source_model_id"] == entry.get("source_model_id")]
        if len(matches) != 1 or entry != matches[0]:
            requests.reject("submitted proposal differs from the recomputed model and provenance",
                            "$.proposals[%d]" % index, "analysis.proposal_forged")
        matched.append(matches[0])
    _require_complete_allocation_cohorts(actual, matched)
    for index, entry in enumerate(submitted):
        candidate = matched[index]
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
