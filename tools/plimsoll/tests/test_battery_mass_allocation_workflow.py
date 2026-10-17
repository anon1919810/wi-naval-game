# -*- coding: utf-8 -*-
"""Workflow contract checks for the whole-battery mount allocation adoption loop.

Written against the declared contract, not against a draft. Every assertion
states a property the returned project, reading or receipt must have, and these
tests run the real project normalization, the real analysis stages and the real
proposal/adoption workflow; nothing is mocked.

The section is optional. Absent or null it adds no family, no method and no
suppression; present, it selects explicit layouts, suppresses **only** the old
per-row mount models of those layouts, exposes a read-only allocation reading
and registers one zero-tolerance allocation model per bound mount target. The
adoption cohort is recomputed on the server and applied atomically or not at all.
"""

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from plimsoll import analysis, project_io  # noqa: E402
from plimsoll import battery_layout, battery_totals, battery_mass_allocation  # noqa: E402
from plimsoll import concept_estimates as kernels  # noqa: E402

LAYOUT_ARMOUR_ITEM = "weapons.main_layout_armour"
SECOND_BATTERY_ID = "main_g2"
UNSET = object()


def project():
    return project_io.normalize_project(
        json.loads((ROOT / "tools/plimsoll/cases/projects/concept_cruiser.project.json")
                   .read_text(encoding="utf-8-sig")))


def run(p):
    return analysis.compute_project(p, "normal", {"stages": ["systems", "design_balance"]})


def data(result):
    return result["stages"]["design_balance"]["data"]


def models(result):
    return {m["id"]: m for row in result["stages"]["systems"]["data"]["systems"].values()
            for m in row["mass_models"]}


def allocation_proposals(result):
    return [q for q in result["stages"]["systems"]["data"]["update_proposals"]
            if q["model"]["inputs"].get("method_version") == battery_mass_allocation.METHOD_VERSION]


def item(p, key):
    return next(i for g in p["weight_groups"] for i in g["items"] if i["id"] == key)


def second_battery():
    first = copy.deepcopy(project()["concept_design"]["batteries"][0])
    first["id"] = SECOND_BATTERY_ID
    first["mount_count"] = 1
    first["barrels_per_mount"] = 3
    first["guns_item_id"] = "weapons.guns2"
    first["mounts_item_id"] = "weapons.mounts2"
    first["ammunition_item_id"] = "weapons.ammunition2"
    return first


def layout_declaration(**overrides):
    declared = {
        "id": "main_layout",
        "source": "declared synthetic layout; no vessel corresponds to this design",
        "group1": {"battery_id": "main", "mount_selector": 4, "layout_index": 1,
                   "elevated_mounts": 1, "deck_mounts": 1, "depressed_mounts": 0},
        "group2": {"battery_id": SECOND_BATTERY_ID, "mount_selector": 7, "layout_index": 7,
                   "elevated_mounts": 0, "deck_mounts": 1, "depressed_mounts": 0},
        "group2_double_elevation": False,
        "group2_double_depression": False,
        "deck_profile": {"forecastle_fraction": 0.2, "forward_deck_fraction": 0.3,
                         "forward_fore_m": 2.2, "forward_aft_m": 1.6,
                         "aft_fore_m": 1.6, "aft_aft_m": 1.2},
        "armour": {"system_id": "weapons.main", "item_id": LAYOUT_ARMOUR_ITEM,
                   "face_mm": 150.0, "rear_roof_mm": 100.0, "barbette_mm": 75.0},
    }
    for key, value in overrides.items():
        if value is None and key in declared:
            declared.pop(key)
            continue
        if isinstance(value, dict) and isinstance(declared.get(key), dict):
            declared[key] = dict(declared[key], **value)
        else:
            declared[key] = value
    return declared


def base_with_layout(layout, battery_mass_allocation=UNSET, mix=False):
    """The cruiser with two battery rows, their items and one declared layout."""
    p = project()
    p["concept_design"]["batteries"][0]["mount_count"] = 2
    if mix:
        p["concept_design"]["batteries"][0]["shared_cradle"] = True
    p["weight_groups"][0]["items"].extend([
        {"id": "weapons.guns2", "mass_t": 60.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 12.0,
         "source": "synthetic declared placeholder", "estimate": True},
        {"id": "weapons.mounts2", "mass_t": 55.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 11.0,
         "source": "synthetic declared placeholder", "estimate": True},
        {"id": "weapons.ammunition2", "mass_t": 20.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 4.0,
         "source": "synthetic declared placeholder", "estimate": True},
        {"id": LAYOUT_ARMOUR_ITEM, "mass_t": 300.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 60.0,
         "source": "synthetic declared placeholder", "estimate": True},
    ])
    p["systems"]["weapons"]["main"]["weight_item_ids"].extend(
        ["weapons.guns2", "weapons.mounts2", "weapons.ammunition2", LAYOUT_ARMOUR_ITEM])
    p["concept_design"]["balance"]["roles"].update({
        "weapons.guns2": "guns", "weapons.mounts2": "mounts",
        "weapons.ammunition2": "ammunition", LAYOUT_ARMOUR_ITEM: "gun_mount_armour"})
    p["concept_design"]["batteries"].append(second_battery())
    p["concept_design"]["battery_layouts"] = [layout]
    if battery_mass_allocation is not UNSET:
        p["concept_design"]["battery_mass_allocation"] = battery_mass_allocation
    return p


def mixed_layout():
    """Two shared twins on ``main`` against one non-shared triple on the second row."""
    return layout_declaration(group1={"mount_selector": 3})


def mixed_project(allocation=UNSET):
    declared = ({"source": "declared", "layout_ids": ["main_layout"]}
                if allocation is UNSET else allocation)
    return base_with_layout(mixed_layout(), declared, mix=True)


# ------------------------------------------- independent expected values

def row_weight_t(battery):
    """The row's own mount estimate in tonnes, read without any ammunition input."""
    if battery["mount_count"] == 0:
        return 0.0
    calibre_in = kernels.millimetres_to_inches(battery["calibre_mm"])
    date_factor = kernels.gun_date_factor(battery["year"])
    count = battery["mount_count"] * battery["barrels_per_mount"]
    gun_lt = kernels.gun_mass_long_tons(calibre_in, battery["barrel_calibres"], date_factor,
                                        count)
    mounts_lt = kernels.mount_mass_long_tons(gun_lt, calibre_in, battery["gun_type"],
                                             battery["mount_type"],
                                             shared_cradle=battery["shared_cradle"])
    return mounts_lt * kernels.LONG_TON_KG / 1000.0


def expected_values(p, layout_id):
    """The source total and the two row weights, recomputed from the kernels."""
    layout = next(l for l in p["concept_design"]["battery_layouts"] if l["id"] == layout_id)
    batteries = p["concept_design"]["batteries"]
    reading = battery_layout.evaluate(layout, batteries)
    totals = battery_totals.evaluate(layout, batteries, reading)
    rows = []
    for name in ("group1", "group2"):
        group = layout.get(name)
        if not isinstance(group, dict) or group.get("battery_id") is None:
            continue
        battery = next(b for b in batteries if b["id"] == group["battery_id"])
        rows.append((battery["id"], battery["mounts_item_id"], row_weight_t(battery)))
    return totals["values"]["mounts_t"], rows


def _exact_tonnes(source_t, weight, legacy):
    """The tonne mass a row's allocation model calculates, exactly as ``systems`` does."""
    part = source_t * (weight / legacy)
    return part * 1000.0 / kernels.LONG_TON_KG * kernels.LONG_TON_KG / 1000.0


def _physical_alternative(mass_t):
    """An ordinary declared physical model on the first row's mount target."""
    return {
        "id": "physical.mounts.probe",
        "method": "volume_density_mass",
        "linked_weight_item_id": "weapons.mounts",
        "inputs": {"volume_m3": mass_t, "density_kg_m3": 1000.0},
        "source": "synthetic physical alternative; no source vessel corresponds",
        "estimate": True,
        "input_provenance": {key: {"source": "synthetic fixture", "estimate": True}
                             for key in ("volume_m3", "density_kg_m3")},
        "comparison_tolerance": {"relative": 0.0, "absolute_t": 0.0},
        "comparison_policy": "empirical_concept_screening_tolerance",
        "boundary": "synthetic physical alternative",
    }


# ------------------------------------------------------- compatibility

def test_a_project_without_the_section_adds_no_family_and_no_method():
    result = run(base_with_layout(layout_declaration()))
    assert "battery_mass_allocation" not in data(result)
    assert "battery_mass_allocation" not in data(result).get("methods", {})
    assert "concept.main.mounts" in models(result)


def test_a_null_section_adds_no_family():
    result = run(base_with_layout(layout_declaration(), battery_mass_allocation=None))
    assert "battery_mass_allocation" not in data(result)
    assert "concept.main.mounts" in models(result)


def test_an_empty_selection_names_the_method_and_suppresses_nothing():
    result = run(mixed_project({"source": "declared", "layout_ids": []}))
    payload = data(result)
    assert payload["methods"]["battery_mass_allocation"] == battery_mass_allocation.METHOD_VERSION
    assert payload["battery_mass_allocation"] == []
    assert "concept.main.mounts" in models(result)


# ----------------------------------------------------- suppression

def test_a_selected_layout_suppresses_only_its_own_old_row_mounts():
    result = run(mixed_project())
    registered = models(result)
    assert "concept.main.mounts" not in registered
    assert "concept.main_g2.mounts" not in registered
    # Guns, ammunition and the layout armour are untouched.
    assert "concept.main.guns" in registered
    assert "concept.main.ammunition" in registered
    assert "concept_layout.main_layout.armour" in registered


def test_turning_the_mode_off_returns_the_old_generation():
    assert "battery_mass_allocation" not in data(run(base_with_layout(mixed_layout(), mix=True)))
    assert "battery_mass_allocation" in data(run(mixed_project()))


# ------------------------------------------------------- the reading

def test_the_reading_reads_the_source_and_row_weights_from_the_kernels():
    p = mixed_project()
    source_t, rows = expected_values(p, "main_layout")
    result = run(p)
    record = data(result)["battery_mass_allocation"][0]
    assert record["id"] == "main_layout"
    assert record["method_version"] == battery_mass_allocation.METHOD_VERSION
    values = record["values"]
    assert values["source_mounts_t"] == pytest.approx(source_t)
    assert values["legacy_mounts_t"] == pytest.approx(sum(weight for _, _, weight in rows))
    assert values["allocated_total_t"] == pytest.approx(source_t)
    assert record["status"] == "available"
    # Every record carries its target, weight, share and allocated mass.
    assert [r["id"] for r in record["records"]] == [r[0] for r in rows]
    assert [r["target_id"] for r in record["records"]] == [r[1] for r in rows]
    assert [r["weight_t"] for r in record["records"]] == pytest.approx(
        [r[2] for r in rows])
    assert sum(r["allocated_mass_t"] for r in record["records"]) == pytest.approx(source_t)
    assert record["provenance"] == {
        "source_method_version": battery_mass_allocation.SOURCE_METHOD_VERSION,
        "allocation_policy": battery_mass_allocation.POLICY,
        "declared_source": "declared",
    }


def test_the_allocation_shares_are_proportional_to_the_row_weights():
    p = mixed_project()
    source_t, rows = expected_values(p, "main_layout")
    records = data(run(p))["battery_mass_allocation"][0]["records"]
    total_weight = sum(weight for _, _, weight in rows)
    for record, (_, _, weight) in zip(records, rows):
        assert record["share"] == pytest.approx(weight / total_weight)
        assert record["allocated_mass_t"] == pytest.approx(source_t * weight / total_weight)


def test_the_selected_mirror_reads_the_explicit_mount_targets():
    p = mixed_project()
    record = data(run(p))["battery_mass_allocation"][0]
    assert record["values"]["selected_mounts_t"] == pytest.approx(
        item(p, "weapons.mounts")["mass_t"] + item(p, "weapons.mounts2")["mass_t"])
    selected = {r["id"]: r["selected_mass_t"] for r in record["records"]}
    assert selected["main"] == pytest.approx(item(p, "weapons.mounts")["mass_t"])
    assert selected[SECOND_BATTERY_ID] == pytest.approx(item(p, "weapons.mounts2")["mass_t"])


# --------------------------------------------------- the generated models

def test_the_allocation_models_carry_the_cohort_metadata_and_zero_tolerance():
    p = mixed_project()
    source_t, rows = expected_values(p, "main_layout")
    result = run(p)
    batch = allocation_proposals(result)
    assert sorted(q["item_id"] for q in batch) == ["weapons.mounts", "weapons.mounts2"]
    for proposal in batch:
        model = proposal["model"]
        inputs = model["inputs"]
        assert inputs["method_version"] == battery_mass_allocation.METHOD_VERSION
        assert inputs["allocation_group_id"] == "battery-mounts:main_layout"
        assert inputs["allocation_policy"] == battery_mass_allocation.POLICY
        assert sorted(inputs["allocation_target_ids"]) == ["weapons.mounts", "weapons.mounts2"]
        assert inputs["source_method_version"] == battery_mass_allocation.SOURCE_METHOD_VERSION
        # Zero tolerance: any nonexact target yields a proposal and is never rewritten
        # silently inside the ordinary comparison window.
        assert model["comparison_tolerance_t"] == 0.0
    registered = models(result)
    registered_model = registered["concept_allocation.main_layout.main"]
    assert registered_model["linked_weight_item_id"] == "weapons.mounts"
    assert registered_model["calculated_mass_t"] == pytest.approx(
        next(r["allocated_mass_t"] for r in data(result)["battery_mass_allocation"][0]["records"]
             if r["id"] == "main"))


def test_the_stage_envelope_exposes_the_family_method():
    result = run(mixed_project())
    assert result["stages"]["design_balance"]["method_versions"]["methods"]["battery_mass_allocation"] \
        == battery_mass_allocation.METHOD_VERSION


# ---------------------------------------------------------- zero / unknown

def test_a_bound_zero_row_allocates_zero_and_can_propose_clearing_an_old_mass():
    p = mixed_project()
    p["concept_design"]["batteries"][1]["mount_count"] = 0
    p["concept_design"]["battery_layouts"][0]["group2"] = dict(
        p["concept_design"]["battery_layouts"][0]["group2"],
        elevated_mounts=0, deck_mounts=0, depressed_mounts=0)
    result = run(p)
    record = data(result)["battery_mass_allocation"][0]
    second = next(r for r in record["records"] if r["id"] == SECOND_BATTERY_ID)
    assert second["weight_t"] == 0.0
    assert second["share"] == 0.0
    assert second["allocated_mass_t"] == 0.0
    cleared = [q for q in allocation_proposals(result) if q["item_id"] == "weapons.mounts2"]
    assert len(cleared) == 1
    assert cleared[0]["proposed_mass_t"] == 0.0


def test_an_unknown_row_weight_leaves_the_split_unavailable_and_suppresses_the_old_model():
    p = mixed_project()
    p["concept_design"]["batteries"][1]["shared_cradle"] = None
    result = run(p)
    record = data(result)["battery_mass_allocation"][0]
    # A missing row weight blocks the split, but the bound mount targets' selected
    # ledger masses are independent of it, so the reading is partial, never a
    # silent copy of the ledger into the missing allocation.
    assert record["status"] == "partial"
    assert record["values"]["source_mounts_t"] is not None
    assert all(r["allocated_mass_t"] is None for r in record["records"])
    assert record["values"]["allocated_total_t"] is None
    assert allocation_proposals(result) == []
    registered = models(result)
    assert "concept.main.mounts" not in registered
    assert "concept.main_g2.mounts" not in registered


def test_an_unknown_source_with_known_selected_actuals_is_partial():
    p = mixed_project()
    p["concept_design"]["batteries"][0]["calibre_mm"] = None
    p["concept_design"]["batteries"][1]["calibre_mm"] = None
    record = data(run(p))["battery_mass_allocation"][0]
    assert record["status"] == "partial"
    assert record["values"]["allocated_total_t"] is None
    assert record["values"]["selected_mounts_t"] == pytest.approx(
        item(p, "weapons.mounts")["mass_t"] + item(p, "weapons.mounts2")["mass_t"])


# ------------------------------------------------- declaration rejections

def test_duplicate_or_unknown_selected_layout_ids_are_refused():
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(mixed_project(
            {"source": "declared", "layout_ids": ["main_layout", "main_layout"]}))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(mixed_project(
            {"source": "declared", "layout_ids": ["nope"]}))


# --------------------------------------------------------- atomic adoption

def test_a_single_member_of_a_pending_cohort_is_refused_before_any_write():
    p = mixed_project()
    result = run(p)
    batch = allocation_proposals(result)
    assert len(batch) == 2
    with pytest.raises(analysis.AnalysisInputError) as excinfo:
        analysis.apply_mass_proposals(p, "normal", [copy.deepcopy(batch[0])],
                                      current_request=result["request"])
    assert excinfo.value.diagnostics[0]["code"] == "analysis.proposal_cohort_incomplete"


def test_the_whole_cohort_applies_atomically_and_recomputes_exact():
    p = mixed_project()
    result = run(p)
    batch = allocation_proposals(result)
    applied = analysis.apply_mass_proposals(p, "normal", [copy.deepcopy(q) for q in batch],
                                            current_request=result["request"])
    assert applied["applied_count"] == 2
    updated = applied["project"]
    after = run(updated)
    assert allocation_proposals(after) == []
    # The receipt keeps the allocation cohort metadata in the standard inputs.
    override = updated["loading_conditions"][0]["override_provenance"]["weapons.mounts"]["mass_t"]
    acceptance = override["acceptance"]
    assert acceptance["inputs"]["allocation_group_id"] == "battery-mounts:main_layout"
    assert acceptance["inputs"]["method_version"] == battery_mass_allocation.METHOD_VERSION
    assert acceptance["inputs"]["allocation_policy"] == battery_mass_allocation.POLICY


def test_explicit_whole_mode_exposes_in_tolerance_armour_for_complete_alignment():
    p = mixed_project()
    p['concept_design']['mass_summary'] = {'source': 'controlled alignment', 'armour_scope_complete': False}
    source_armour = run(p)['stages']['design_balance']['data']['battery_totals'][0]['values']['armour_t']
    item(p, LAYOUT_ARMOUR_ITEM)['mass_t'] = source_armour * 1.03
    result = run(p)
    proposals = result['stages']['systems']['data']['update_proposals']
    assert any(q['item_id'] == LAYOUT_ARMOUR_ITEM for q in proposals)
    targets = {LAYOUT_ARMOUR_ITEM}
    for battery in p['concept_design']['batteries']:
        targets.update((battery['guns_item_id'], battery['mounts_item_id']))
    batch = [q for q in proposals if q['item_id'] in targets]
    updated = analysis.apply_mass_proposals(p, 'normal', batch, current_request=result['request'])['project']
    total = data(run(updated))['battery_totals'][0]
    assert total['selected_values']['total_t'] == pytest.approx(total['values']['total_t'], rel=1e-12)
    disabled = copy.deepcopy(p)
    disabled['concept_design'].pop('battery_mass_allocation')
    assert not any(q['item_id'] == LAYOUT_ARMOUR_ITEM for q in run(disabled)['stages']['systems']['data']['update_proposals'])


def test_a_forged_allocation_proposal_is_refused_and_nothing_is_written():
    p = mixed_project()
    result = run(p)
    batch = allocation_proposals(result)
    forged = copy.deepcopy(batch[0])
    forged["proposed_mass_t"] = 999.0
    with pytest.raises(analysis.AnalysisInputError) as excinfo:
        analysis.apply_mass_proposals(p, "normal", [forged, copy.deepcopy(batch[1])],
                                      current_request=result["request"])
    assert excinfo.value.diagnostics[0]["code"] == "analysis.proposal_forged"


def test_a_declared_unresolved_group_nulls_the_parent_subtotal_but_keeps_its_member():
    p = mixed_project()
    group2 = p["concept_design"]["battery_layouts"][0]["group2"]
    p["concept_design"]["battery_layouts"][0]["group2"] = dict(group2, battery_id=None)
    result = run(p)
    record = data(result)["battery_mass_allocation"][0]
    # The second group is declared but never resolved to a row, so the boundary of
    # the parent mount subtotal cannot be closed: it must be null, never the
    # subtotal of the one row that happened to survive.
    assert record["values"]["selected_mounts_t"] is None
    # The surviving row's own bound actual stays independently readable.
    main = next(r for r in record["records"] if r["id"] == "main")
    assert main["selected_mass_t"] == pytest.approx(item(p, "weapons.mounts")["mass_t"])
    assert record["status"] == "partial"
    # The blocked split names no partial allocation and registers no model.
    assert all(r["allocated_mass_t"] is None for r in record["records"])
    assert record["values"]["allocated_total_t"] is None
    assert allocation_proposals(result) == []
    assert "concept.main.mounts" not in models(result)


@pytest.mark.parametrize("cross_system_model_id_collision", [False, True])
def test_a_batch_that_adopts_a_cohort_may_not_rewrite_an_already_exact_member(cross_system_model_id_collision):
    p = mixed_project()
    source_t, rows = expected_values(p, "main_layout")
    total_weight = sum(weight for _, _, weight in rows)
    # Make the first row's ledger exactly its recomputed allocated share, so its
    # allocation model produces no pending proposal of its own. A batch that then
    # adopts the second row must not be able to lower the exact first row through
    # an ordinary physical model in the same batch.
    item(p, "weapons.mounts")["mass_t"] = _exact_tonnes(source_t, rows[0][2], total_weight)
    alternative = _physical_alternative(1.0)
    if cross_system_model_id_collision:
        # Model IDs are local to a system leaf. A valid physical model in A's
        # leaf may share B's allocation-model ID without being that allocation.
        second_items = ["weapons.guns2", "weapons.mounts2", "weapons.ammunition2"]
        p["systems"]["weapons"]["secondary"] = {
            "source": "synthetic second leaf", "estimate": True, "weight_item_ids": second_items}
        p["systems"]["weapons"]["main"]["weight_item_ids"] = [
            target for target in p["systems"]["weapons"]["main"]["weight_item_ids"]
            if target not in second_items]
        p["concept_design"]["batteries"][1]["system_id"] = "weapons.secondary"
        alternative["id"] = "concept_allocation.main_layout.main_g2"
    p["systems"]["weapons"]["main"]["mass_models"] = [alternative]
    result = run(p)
    by_item = {q["item_id"]: q for q in result["stages"]["systems"]["data"]["update_proposals"]}
    # The exact member has no allocation proposal; only the second row's allocation
    # is pending, and the first row's pending proposal is the physical alternative.
    assert [q["item_id"] for q in allocation_proposals(result)] == ["weapons.mounts2"]
    assert by_item["weapons.mounts"]["source_model_id"] == alternative["id"]
    assert by_item["weapons.mounts"]["proposed_mass_t"] == 1.0
    with pytest.raises(analysis.AnalysisInputError) as excinfo:
        analysis.apply_mass_proposals(
            p, "normal",
            [copy.deepcopy(by_item["weapons.mounts"]), copy.deepcopy(by_item["weapons.mounts2"])],
            current_request=result["request"])
    assert excinfo.value.diagnostics[0]["code"] == "analysis.proposal_cohort_conflict"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
