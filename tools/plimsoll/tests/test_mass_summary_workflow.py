# -*- coding: utf-8 -*-
"""Contract checks for the optional mass summary in the analysis workflow.

Written against the contract, not against a draft: every assertion states a
property the declared document and the returned result must have. These tests run
the real project normalization, the real analysis stages and the real
proposal/adoption workflow; nothing is mocked.

The two readings this section turns on are read-only:

* ``design_balance.battery_totals[]`` — one whole-battery source estimate per
  declared layout, each beside the current condition's ``selected_values``;
* ``design_balance.armour_totals`` — the declared estimate and the selected
  actual, kept apart.

Absent or null, the section adds no key, no family and no method anywhere.
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
from plimsoll import armour_totals, battery_totals  # noqa: E402

LAYOUT_ARMOUR_ITEM = "weapons.main_layout_armour"
SECOND_BATTERY_ID = "main_g2"
BATTERY_ARMOUR_ITEM = "weapons.main_battery_armour"
UNCLASSIFIED_ITEM = "misc.unclassified"
UNSET = object()


def project():
    return project_io.normalize_project(
        json.loads((ROOT / "tools/plimsoll/cases/projects/concept_cruiser.project.json")
                   .read_text(encoding="utf-8-sig")))


def run(p):
    return analysis.compute_project(p, "normal", {"stages": ["systems", "design_balance"]})


def data(result):
    return result["stages"]["design_balance"]["data"]


def stage(result):
    return result["stages"]["design_balance"]


def proposals(result, item_id=None):
    batch = result["stages"]["systems"]["data"]["update_proposals"]
    return [q for q in batch if item_id is None or q["item_id"] == item_id]


def models(result):
    return {m["id"]: m for row in result["stages"]["systems"]["data"]["systems"].values()
            for m in row["mass_models"]}


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


def add_ledger_item(p, identity, mass_t, system="weapons.main", role=None):
    p["weight_groups"][0]["items"].append({
        "id": identity, "mass_t": mass_t, "x_m": 100.0, "y_m": 0.0, "kg_m": 12.0,
        "source": "synthetic declared placeholder", "estimate": True})
    head, leaf = system.split(".")
    p["systems"][head][leaf]["weight_item_ids"].append(identity)
    if role is not None:
        p["concept_design"]["balance"]["roles"][identity] = role


def with_layouts(*layouts, mass_summary=UNSET, **overrides):
    """A project with two battery rows, their items and one declared layout."""
    p = project()
    p["concept_design"]["batteries"][0]["mount_count"] = 2
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
    p["concept_design"]["battery_layouts"] = list(layouts) or [layout_declaration()]
    if mass_summary is not UNSET:
        p["concept_design"]["mass_summary"] = mass_summary
    for key, value in overrides.items():
        if value is None and key in p["concept_design"]:
            p["concept_design"].pop(key)
        else:
            p["concept_design"][key] = value
    return p


def belt_region(rid="main_belt", kind="belt_main", item_id="armour.belt_main", **fields):
    declared = {"id": rid, "kind": kind, "system_id": "armour.fixed", "item_id": item_id,
                "source": "synthetic declared fixed armour; no vessel corresponds to it"}
    declared.update(fields)
    return declared


# --------------------------------------------------------- compatibility

def test_a_project_without_the_section_adds_no_key_and_no_family():
    result = run(with_layouts())
    assert "battery_totals" not in data(result)
    assert "armour_totals" not in data(result)
    assert "battery_totals" not in data(result).get("methods", {})
    assert "armour_totals" not in data(result).get("methods", {})


def test_a_null_section_adds_no_key_and_no_family():
    result = run(with_layouts(mass_summary=None))
    assert "battery_totals" not in data(result)
    assert "armour_totals" not in data(result)


def test_a_declared_section_turns_on_both_readings_and_their_methods():
    result = run(with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True}))
    payload = data(result)
    assert payload["methods"]["battery_totals"] == battery_totals.METHOD_VERSION
    assert payload["methods"]["armour_totals"] == armour_totals.METHOD_VERSION
    totals = payload["battery_totals"]
    assert [row["id"] for row in totals] == ["main_layout"]
    assert totals[0]["method_version"] == battery_totals.METHOD_VERSION
    # The four canonical keys are present; ``values`` additionally carries the
    # shared source facts and the long-ton figures beside them.
    assert {"guns_t", "mounts_t", "armour_t", "total_t"} <= set(totals[0]["values"])
    assert set(totals[0]["selected_values"]) == {"guns_t", "mounts_t", "armour_t", "total_t"}
    armour = payload["armour_totals"]
    assert armour["id"] == "ship_armour"
    assert armour["method_version"] == armour_totals.METHOD_VERSION
    assert set(armour["values"]) == set(armour_totals.VALUE_KEYS)


def test_the_declared_family_methods_reach_the_stage_envelope():
    result = run(with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True}))
    assert stage(result)["method_versions"]["methods"] == data(result)["methods"]


# ------------------------------------------------------ the source reading

def test_the_source_estimate_partitions_into_guns_mounts_and_layout_armour():
    result = run(with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True}))
    record = data(result)["battery_totals"][0]
    values = record["values"]
    assert record["status"] == "available"
    assert values["guns_t"] is not None and values["mounts_t"] is not None
    assert values["armour_t"] is not None and values["total_t"] is not None
    assert values["total_t"] == pytest.approx(values["guns_t"] + values["mounts_t"]
                                              + values["armour_t"])
    # The declared ammunition target carries a positive mass and never enters the
    # whole-battery sum: the source total is guns + mounts + layout armour only.
    ammunition = item(project(), "weapons.ammunition")["mass_t"]
    assert ammunition > 0


# ------------------------------------------------------ the selected mirror

def test_selected_values_come_from_the_current_ledger_by_target_id():
    result = run(with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True}))
    selected = data(result)["battery_totals"][0]["selected_values"]
    assert selected["guns_t"] == pytest.approx(60.9628 + 60.0)
    assert selected["mounts_t"] == pytest.approx(152.407 + 55.0)
    # The layout's own complete armour target, once, at its declared ledger mass.
    assert selected["armour_t"] == pytest.approx(300.0)
    assert selected["total_t"] == pytest.approx(60.9628 + 60.0 + 152.407 + 55.0 + 300.0)
    # The two ammunition targets (45.7221 t and 20.0 t) are excluded.
    assert selected["total_t"] != pytest.approx(
        selected["total_t"] + item(project(), "weapons.ammunition")["mass_t"] + 20.0)


def test_a_changed_ledger_moves_the_selected_mirror_and_not_the_estimate():
    baseline = run(with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True}))
    before = data(baseline)["battery_totals"][0]
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    item(p, LAYOUT_ARMOUR_ITEM)["mass_t"] = 123.0
    after = data(run(p))["battery_totals"][0]
    assert after["selected_values"]["armour_t"] == pytest.approx(123.0)
    assert after["values"]["armour_t"] == pytest.approx(before["values"]["armour_t"])
    assert after["selected_values"] != after["values"]


def test_a_missing_selected_target_leaves_that_figure_unknown_not_the_estimate():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    item(p, LAYOUT_ARMOUR_ITEM)["mass_t"] = None
    record = data(run(p))["battery_totals"][0]
    assert record["selected_values"]["armour_t"] is None
    assert record["selected_values"]["total_t"] is None
    assert record["values"]["armour_t"] is not None


# ------------------------------------------------------------ the armour totals

def test_the_armour_family_counts_the_layout_armour_once():
    result = run(with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True}))
    armour = data(result)["armour_totals"]
    assert armour["provenance"]["inputs"]["component_count"] == 1
    assert armour["provenance"]["inputs"]["belt_component_ids"] == []
    assert armour["status"] == "available"
    assert armour["values"]["estimated_total_t"] is not None
    assert armour["values"]["selected_total_t"] is not None
    # The selected actual is the nine-role sum, so it includes the rotating armour
    # that no component kernel derives and the other declared armour roles.
    assert armour["values"]["selected_total_t"] > armour["values"]["estimated_total_t"]


def test_fixed_regions_and_layouts_stay_distinct_namespaced_components():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    p["concept_design"]["fixed_armour"] = [
        belt_region("main_belt", "belt_main", "armour.belt_main",
                    thickness_mm=152.4, length_m=91.44, height_m=6.096)]
    result = run(p)
    armour = data(result)["armour_totals"]
    assert armour["provenance"]["inputs"]["component_count"] == 2
    assert armour["provenance"]["inputs"]["belt_component_ids"] == ["fixed:main_belt"]


def test_the_complete_scope_flag_gates_the_complete_declared_figures():
    for flag in (True, False, None):
        p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": flag})
        armour = data(run(p))["armour_totals"]
        if flag is True:
            assert armour["values"]["estimated_total_t"] is not None
            assert armour["values"]["estimated_belts_t"] == 0.0
        else:
            assert armour["values"]["estimated_total_t"] is None
            assert armour["values"]["estimated_belts_t"] is None
            # The known subtotal stays readable and is never called a total.
            assert armour["values"]["known_estimate_subtotal_t"] is not None


def test_an_unknown_component_leaves_the_complete_figures_unknown_and_lists_it():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    p["concept_design"]["fixed_armour"] = [
        belt_region("main_belt", "belt_main", "armour.belt_main", thickness_mm=None,
                    length_m=91.44, height_m=6.096)]
    armour = data(run(p))["armour_totals"]
    assert armour["values"]["estimated_total_t"] is None
    assert armour["values"]["estimated_belts_t"] is None
    assert armour["coverage"]["uncovered_component_ids"] == ["fixed:main_belt"]
    assert armour["values"]["known_estimate_subtotal_t"] is not None


def test_an_unclassified_selected_mass_leaves_the_selected_total_unknown():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    add_ledger_item(p, UNCLASSIFIED_ITEM, 10.0)
    result = run(p)
    armour = data(result)["armour_totals"]
    assert armour["values"]["selected_total_t"] is None
    assert armour["values"]["selected_belts_t"] is not None
    assert UNCLASSIFIED_ITEM in data(result)["unclassified_item_ids"]


def test_an_unknown_selected_role_leaves_the_selected_belts_unknown():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    item(p, "armour.belt_upper")["mass_t"] = None
    armour = data(run(p))["armour_totals"]
    assert armour["values"]["selected_belts_t"] is None
    assert armour["values"]["selected_total_t"] is None
    # The declared estimate is untouched by an unknown selected role.
    assert armour["values"]["estimated_total_t"] is not None


# -------------------------------------------------------- v1/v2 and tolerance

def test_a_layout_armour_and_the_referenced_rows_own_v1_armour_cannot_both_apply():
    p = with_layouts()
    add_ledger_item(p, BATTERY_ARMOUR_ITEM, 200.0, role="gun_mount_armour")
    p["concept_design"]["batteries"][0]["armour"] = {
        "system_id": "weapons.main", "item_id": BATTERY_ARMOUR_ITEM,
        "face_mm": 100.0, "rear_roof_mm": 50.0, "barbette_mm": 25.0,
        "freeboard_m": 5.0, "super_factor": 1.0}
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_a_battery_v1_armour_without_a_layout_is_one_declared_component():
    p = project()
    add_ledger_item(p, BATTERY_ARMOUR_ITEM, 200.0, role="gun_mount_armour")
    p["concept_design"]["batteries"][0]["armour"] = {
        "system_id": "weapons.main", "item_id": BATTERY_ARMOUR_ITEM,
        "face_mm": 100.0, "rear_roof_mm": 50.0, "barbette_mm": 25.0,
        "freeboard_m": 5.0, "super_factor": 1.0}
    p["concept_design"]["mass_summary"] = {"source": "declared", "armour_scope_complete": True}
    result = run(p)
    assert "battery_totals" not in data(result)
    armour = data(result)["armour_totals"]
    assert armour["provenance"]["inputs"]["component_count"] == 1
    assert armour["values"]["estimated_total_t"] is not None


def test_an_estimate_inside_the_proposal_tolerance_is_still_a_declared_component():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    calculated = models(run(p))["concept_layout.main_layout.armour"]["calculated_mass_t"]
    # Move the ledger target onto the estimate so the comparison is inside tolerance
    # and no mass-mismatch proposal is emitted for that item.
    p2 = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    item(p2, LAYOUT_ARMOUR_ITEM)["mass_t"] = calculated
    second = run(p2)
    assert proposals(second, LAYOUT_ARMOUR_ITEM) == []
    armour = data(second)["armour_totals"]
    assert armour["provenance"]["inputs"]["component_count"] == 1
    assert armour["values"]["estimated_total_t"] == pytest.approx(calculated)


def test_removing_the_declaration_keeps_the_selected_ledger_unchanged():
    with_section = run(with_layouts(
        mass_summary={"source": "declared", "armour_scope_complete": True}))
    without = run(with_layouts())
    assert data(with_section)["values"]["selected_total_mass_t"] == \
        data(without)["values"]["selected_total_mass_t"]
    assert "armour_totals" in data(with_section)
    assert "armour_totals" not in data(without)


# ---------------------------------------------------------- differing barrels

def test_differing_barrel_calibres_only_change_the_new_reading():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    p["concept_design"]["batteries"][1]["barrel_calibres"] = 50
    result = run(p)
    payload = data(result)
    record = payload["battery_totals"][0]
    # The whole-battery gun and mount total is unavailable; the layout armour is
    # still read and the project is not refused.
    assert record["values"]["guns_t"] is None
    assert record["values"]["mounts_t"] is None
    assert record["values"]["armour_t"] is not None
    assert record["values"]["total_t"] is None
    assert record["status"] == "partial"
    assert any(d["code"] == "battery_totals.contradiction" for d in record["diagnostics"])
    # The old layout reading itself is untouched, and the armour family still has
    # its own complete declared armour.
    assert payload["battery_layouts"][0]["status"] in ("available", "partial")
    assert payload["armour_totals"]["values"]["estimated_total_t"] is not None


# ----------------------------------------------------- open source boundaries

def test_an_unresolved_declared_group_leaves_its_guns_and_mounts_unknown():
    layout = layout_declaration()
    layout["group2"] = dict(layout["group2"], battery_id=None)
    p = with_layouts(layout,
                     mass_summary={"source": "declared", "armour_scope_complete": True})
    record = data(run(p))["battery_totals"][0]
    # The source boundary is already open; the selected mirror must be open too and
    # must never report the first group alone as the whole battery.
    assert record["values"]["guns_t"] is None
    assert record["values"]["mounts_t"] is None
    assert record["selected_values"]["guns_t"] is None
    assert record["selected_values"]["mounts_t"] is None
    assert record["selected_values"]["total_t"] is None
    # The layout's own bound armour is independent of an open group membership.
    assert record["selected_values"]["armour_t"] == pytest.approx(300.0)


def test_an_absent_second_group_is_not_read_as_an_open_membership():
    layout = layout_declaration()
    layout.pop("group2")
    p = with_layouts(layout,
                     mass_summary={"source": "declared", "armour_scope_complete": True})
    record = data(run(p))["battery_totals"][0]
    # group2 was never declared, so the first group's own figures stay known.
    assert record["selected_values"]["guns_t"] == pytest.approx(60.9628)
    assert record["selected_values"]["mounts_t"] == pytest.approx(152.407)
    assert record["selected_values"]["armour_t"] == pytest.approx(300.0)


def test_an_unbound_declared_armour_target_leaves_the_selected_armour_unknown():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    # The layout declares no armour of its own; both referenced rows carry a
    # single-group v1 armour and one of the two bindings is unfinished.
    p["concept_design"]["battery_layouts"][0].pop("armour")
    add_ledger_item(p, BATTERY_ARMOUR_ITEM, 200.0, role="gun_mount_armour")
    p["concept_design"]["batteries"][0]["armour"] = {
        "system_id": "weapons.main", "item_id": BATTERY_ARMOUR_ITEM,
        "face_mm": 100.0, "rear_roof_mm": 50.0, "barbette_mm": 25.0,
        "freeboard_m": 5.0, "super_factor": 1.0}
    p["concept_design"]["batteries"][1]["armour"] = {
        "system_id": "weapons.main", "item_id": None,
        "face_mm": 100.0, "rear_roof_mm": 50.0, "barbette_mm": 25.0,
        "freeboard_m": 5.0, "super_factor": 1.0}
    record = data(run(p))["battery_totals"][0]
    assert record["selected_values"]["guns_t"] is not None
    assert record["selected_values"]["mounts_t"] is not None
    # One declared armour target is unbound, so its category is unknown: the bound
    # one is never dropped and reported as the whole battery's armour.
    assert record["selected_values"]["armour_t"] is None
    assert record["selected_values"]["total_t"] is None


def test_a_referenced_zero_count_row_still_contributes_its_ledger_targets():
    layout = layout_declaration()
    layout["group2"] = dict(layout["group2"], elevated_mounts=0, deck_mounts=0,
                            depressed_mounts=0)
    p = with_layouts(layout,
                     mass_summary={"source": "declared", "armour_scope_complete": True})
    p["concept_design"]["batteries"][1]["mount_count"] = 0
    record = data(run(p))["battery_totals"][0]
    # A zero-count group is still a declared, resolved membership: its referenced
    # row's existing ledger mass is counted, never turned into a zero.
    assert record["selected_values"]["guns_t"] == pytest.approx(60.9628 + 60.0)
    assert record["selected_values"]["mounts_t"] == pytest.approx(152.407 + 55.0)


def test_a_bulge_fixed_component_keeps_its_balance_role_not_its_kind():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    p["concept_design"]["fixed_armour"] = [
        belt_region("main_bulge", "bulge", "armour.bulge", thickness_mm=25.4,
                    length_m=100.0, height_m=3.0)]
    armour = data(run(p))["armour_totals"]
    # The fixed kind 'bulge' is the balance role 'armour_bulge'; passing the raw
    # kind through would refuse the whole armour reading.
    assert armour is not None
    assert armour["coverage"]["declared_components"] == 2
    assert armour["provenance"]["inputs"]["belt_component_ids"] == []


def test_an_unavailable_source_with_known_selected_actuals_is_partial():
    p = with_layouts(mass_summary={"source": "declared", "armour_scope_complete": True})
    # Both referenced rows are valid drafts whose calibre is not yet chosen, so the
    # source estimate cannot be closed. The selected ledger actuals are independent.
    p["concept_design"]["batteries"][0]["calibre_mm"] = None
    p["concept_design"]["batteries"][1]["calibre_mm"] = None
    record = data(run(p))["battery_totals"][0]
    # Every source value stays unknown -- the ledger is never written into it.
    assert record["values"]["guns_t"] is None
    assert record["values"]["total_t"] is None
    # The selected actuals are known and the record is partial, not refused.
    assert record["status"] == "partial"
    assert record["selected_values"]["guns_t"] == pytest.approx(60.9628 + 60.0)
    assert record["selected_values"]["mounts_t"] == pytest.approx(152.407 + 55.0)
    assert record["selected_values"]["armour_t"] == pytest.approx(300.0)
    assert record["selected_values"]["total_t"] == pytest.approx(
        60.9628 + 60.0 + 152.407 + 55.0 + 300.0)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
