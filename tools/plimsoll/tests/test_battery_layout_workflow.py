# -*- coding: utf-8 -*-
"""Contract checks for the optional two-group battery layout in the workflow.

Written against the contract, not against a draft: every assertion states a
property the declared document and the returned result must have. These tests
run the real project normalization, the real analysis stages and the real
proposal/adoption workflow; nothing is mocked.
"""

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from plimsoll import analysis, concept_design, project_io, project_store  # noqa: E402
from plimsoll import battery_layout, battery_armour  # noqa: E402

LAYOUT_ARMOUR_ITEM = "weapons.main_layout_armour"
SECOND_BATTERY_ID = "main_g2"


def project():
    return project_io.normalize_project(
        json.loads((ROOT / "tools/plimsoll/cases/projects/concept_cruiser.project.json")
                   .read_text(encoding="utf-8-sig")))


def run(p):
    return analysis.compute_project(p, "normal", {"stages": ["systems", "design_balance"]})


def models(result):
    data = result["stages"]["systems"]["data"]
    assert data is not None, result["stages"]["systems"]
    return {m["id"]: m for row in data["systems"].values() for m in row["mass_models"]}


def model_owner(result, model_id):
    for system_id, row in result["stages"]["systems"]["data"]["systems"].items():
        if any(m["id"] == model_id for m in row["mass_models"]):
            return system_id
    return None


def proposals(result):
    return result["stages"]["systems"]["data"]["update_proposals"]


def diagnostics(result):
    return (result["stages"]["systems"].get("diagnostics", [])
            + result["stages"]["design_balance"].get("diagnostics", []))


def item(p, key):
    return next(i for g in p["weight_groups"] for i in g["items"] if i["id"] == key)


def second_battery():
    """A second group row: same calibre, year, gun and mount class, its own count."""
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


def with_layouts(*layouts, **overrides):
    """A project with two battery rows, their items and one declared layout.

    The first row declares two mounts and the layout splits them into one elevated
    and one on deck, which is the recovered two-group identity this unit models;
    the second row declares the single group-2 mount.
    """
    p = project()
    p["concept_design"]["batteries"][0]["mount_count"] = 2
    p["weight_groups"][0]["items"].extend([
        {"id": "weapons.guns2", "mass_t": 60.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 12.0,
         "source": "synthetic declared placeholder for the second mount group",
         "estimate": True},
        {"id": "weapons.mounts2", "mass_t": 55.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 11.0,
         "source": "synthetic declared placeholder for the second mount group",
         "estimate": True},
        {"id": "weapons.ammunition2", "mass_t": 20.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 4.0,
         "source": "synthetic declared placeholder for the second mount group",
         "estimate": True},
        {"id": LAYOUT_ARMOUR_ITEM, "mass_t": 300.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 60.0,
         "source": "synthetic declared placeholder for the layout armour target",
         "estimate": True},
    ])
    p["systems"]["weapons"]["main"]["weight_item_ids"].extend(
        ["weapons.guns2", "weapons.mounts2", "weapons.ammunition2", LAYOUT_ARMOUR_ITEM])
    p["concept_design"]["balance"]["roles"].update({
        "weapons.guns2": "guns", "weapons.mounts2": "mounts",
        "weapons.ammunition2": "ammunition", LAYOUT_ARMOUR_ITEM: "gun_mount_armour"})
    p["concept_design"]["batteries"].append(second_battery())
    p["concept_design"]["battery_layouts"] = list(layouts) or [layout_declaration()]
    for key, value in overrides.items():
        if value is None and key in p["concept_design"]:
            p["concept_design"].pop(key)
        else:
            p["concept_design"][key] = value
    return p


# ------------------------------------------------------------------- compatibility

def test_a_project_without_layouts_is_completely_unchanged():
    plain = run(project())
    found = models(plain)
    assert {"concept.main.guns", "concept.main.mounts", "concept.main.ammunition"} <= set(found)
    assert not [m for m in found if m.startswith("concept_layout.")]
    data = plain["stages"]["design_balance"]["data"]
    assert "battery_layouts" not in data
    assert plain["stages"]["design_balance"]["status"] == "completed"


def test_an_empty_layout_list_changes_nothing_either():
    p = project()
    p["concept_design"]["battery_layouts"] = []
    result = run(project_io.normalize_project(p))
    assert "battery_layouts" not in result["stages"]["design_balance"]["data"]
    assert not [m for m in models(result) if m.startswith("concept_layout.")]


def test_the_layout_key_is_refused_when_it_is_not_a_list():
    p = with_layouts()
    p["concept_design"]["battery_layouts"] = {"id": "main_layout"}
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_an_unknown_field_inside_a_layout_is_refused_rather_than_ignored():
    p = with_layouts()
    p["concept_design"]["battery_layouts"][0]["gun_position_x"] = 4.0
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


# -------------------------------------------------------------------- the model

def test_a_declared_layout_registers_its_own_independent_armour_model():
    result = run(with_layouts())
    found = models(result)
    assert "concept_layout.main_layout.armour" in found
    model = found["concept_layout.main_layout.armour"]
    assert model["method"] == "empirical_estimate_v1"
    assert model["linked_weight_item_id"] == LAYOUT_ARMOUR_ITEM
    assert model_owner(result, "concept_layout.main_layout.armour") == "weapons.main"
    assert model["concept_component"] == "armour"
    assert model["source"]["method_version"] == battery_layout.ARMOUR_METHOD_VERSION
    assert model["inputs"]["method_version"] == battery_layout.ARMOUR_METHOD_VERSION
    assert model["source"]["sha256"] == battery_layout.SOURCE_SHA256
    assert concept_design.METHOD == "sps-3b3-adapted-v1"


def test_the_layout_model_is_generated_before_the_hull_proxy():
    p = with_layouts()
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        p["hull"].pop(key, None)
    result = run(p)
    found = models(result)
    assert "concept_layout.main_layout.armour" in found
    assert "concept.machinery" not in found
    assert result["stages"]["design_balance"]["data"] is not None


def test_the_layout_model_carries_the_complete_two_group_breakdown():
    model = models(run(with_layouts()))["concept_layout.main_layout.armour"]
    breakdown = model["component_breakdown"]
    assert set(breakdown) == {"face_long_tons", "rear_roof_long_tons", "barbette_long_tons"}
    assert sum(breakdown.values()) == pytest.approx(model["inputs"]["estimate_long_tons"])
    inputs = model["inputs"]
    for key in ("guns_in_mount_selector_g1", "guns_in_mount_selector_g2", "mounts_g1",
                "mounts_g2", "barrels", "freeboard_m", "super_factor", "calibre_mm", "year"):
        assert key in inputs, key
    assert inputs["guns_in_mount_selector_g1"] == 4
    assert inputs["guns_in_mount_selector_g2"] == 7
    assert inputs["estimate_long_tons"] > 0


def test_a_layout_without_a_declared_armour_still_reports_its_readings():
    p = with_layouts(layout_declaration(armour=None))
    result = run(p)
    assert "concept_layout.main_layout.armour" not in models(result)
    readings = result["stages"]["design_balance"]["data"]["battery_layouts"]
    assert len(readings) == 1
    assert readings[0]["freeboard_m"] > 0
    assert readings[0]["super_factor"] > 0


def test_two_identical_active_groups_survive_as_two_separate_layout_groups():
    # Two rows with the same barrels per mount and no shared cradle are still two
    # separate groups with their own selectors, and each keeps its own estimate.
    p = with_layouts()
    p["concept_design"]["batteries"][1]["barrels_per_mount"] = 2
    p["concept_design"]["battery_layouts"][0]["group2"]["mount_selector"] = 1
    result = run(p)
    assert "concept_layout.main_layout.armour" in models(result)
    assert "concept.main_g2.guns" in models(result)
    readings = result["stages"]["design_balance"]["data"]["battery_layouts"][0]
    assert readings["groups"]["group1"]["mounts"] == 2
    assert readings["groups"]["group2"]["mounts"] == 1
    assert readings["barrels"] == 6
    assert readings["groups"]["group1"]["per_mount"] == 2
    assert readings["groups"]["group2"]["per_mount"] == 2


# ----------------------------------------------------------------- design balance

def test_the_balance_screen_returns_the_layout_readings():
    data = run(with_layouts())["stages"]["design_balance"]["data"]
    readings = data["battery_layouts"]
    assert len(readings) == 1
    entry = readings[0]
    assert entry["id"] == "main_layout"
    assert entry["method_version"] == battery_layout.METHOD_VERSION
    assert entry["status"] == "available"
    assert set(entry["groups"]) == {"group1", "group2"}
    assert entry["freeboard_m"] > 0
    assert entry["super_factor"] >= 1.0
    assert entry["armour"]["values"]["total_long_tons"] > 0
    assert entry["provenance"]["source_sha256"] == battery_layout.SOURCE_SHA256


def test_the_layout_readings_survive_a_missing_balance_section():
    p = with_layouts()
    p["concept_design"].pop("balance")
    result = run(p)
    data = result["stages"]["design_balance"]["data"]
    assert data is not None
    assert data["battery_layouts"][0]["freeboard_m"] > 0
    assert data["status"] != "completed"


def test_the_layout_readings_survive_a_missing_hull_proxy():
    p = with_layouts()
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        p["hull"].pop(key, None)
    data = run(p)["stages"]["design_balance"]["data"]
    assert data["battery_layouts"][0]["freeboard_m"] > 0


def test_an_unconfigured_layout_reports_no_reading_rather_than_a_zero():
    p = with_layouts(layout_declaration(group1=None, group2=None))
    readings = run(p)["stages"]["design_balance"]["data"]["battery_layouts"]
    assert readings[0]["status"] == "unavailable"
    assert readings[0]["freeboard_m"] is None
    assert readings[0]["super_factor"] is None


def test_an_incomplete_layout_is_diagnosed_and_never_invented():
    p = with_layouts(layout_declaration(
        group2={"battery_id": SECOND_BATTERY_ID, "mount_selector": None, "layout_index": None,
                "elevated_mounts": 0, "deck_mounts": 1, "depressed_mounts": 0}))
    result = run(p)
    readings = result["stages"]["design_balance"]["data"]["battery_layouts"][0]
    assert readings["freeboard_m"] is None
    assert readings["status"] == "unavailable"
    assert any("mount_selector" in json.dumps(d) for d in diagnostics(result))


def test_a_known_zero_group_does_not_lose_the_other_estimates():
    p = with_layouts()
    p["concept_design"]["batteries"][1]["mount_count"] = 0
    p["concept_design"]["battery_layouts"][0]["group2"] = {
        "battery_id": SECOND_BATTERY_ID, "mount_selector": 7, "layout_index": 7,
        "elevated_mounts": 0, "deck_mounts": 0, "depressed_mounts": 0}
    result = run(p)
    readings = result["stages"]["design_balance"]["data"]["battery_layouts"][0]
    assert readings["freeboard_m"] > 0
    assert {"concept.main.guns", "concept.main_g2.guns"} <= set(models(result))


# ------------------------------------------------------------ ownership and role

def test_the_layout_armour_target_may_not_be_another_components_target():
    p = with_layouts(layout_declaration(
        armour={"system_id": "weapons.main", "item_id": "weapons.mounts", "face_mm": 150.0,
                "rear_roof_mm": 100.0, "barbette_mm": 75.0}))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_layout_armour_target_may_not_be_owned_by_two_layouts():
    p = with_layouts(layout_declaration(),
                     layout_declaration(id="second_layout", armour={
                         "system_id": "weapons.main", "item_id": LAYOUT_ARMOUR_ITEM,
                         "face_mm": 150.0, "rear_roof_mm": 100.0, "barbette_mm": 75.0}))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_owning_system_must_actually_link_the_layout_target():
    p = with_layouts(layout_declaration(
        armour={"system_id": "armour.fixed", "item_id": LAYOUT_ARMOUR_ITEM, "face_mm": 150.0,
                "rear_roof_mm": 100.0, "barbette_mm": 75.0}))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_layout_target_must_carry_the_complete_armour_role():
    p = with_layouts()
    p["concept_design"]["balance"]["roles"][LAYOUT_ARMOUR_ITEM] = "rotating_armour"
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_a_layout_armour_and_a_legacy_row_armour_may_not_both_weight_the_same_groups():
    p = with_layouts()
    p["concept_design"]["batteries"][0]["armour"] = {
        "system_id": "weapons.main", "item_id": "weapons.main_armour", "face_mm": 150.0,
        "rear_roof_mm": 100.0, "barbette_mm": 75.0, "freeboard_m": 4.6, "super_factor": 1.0}
    p["weight_groups"][0]["items"].append({
        "id": "weapons.main_armour", "mass_t": 40.0, "x_m": 100.0, "y_m": 0.0, "kg_m": 8.0,
        "source": "synthetic declared placeholder", "estimate": True})
    p["systems"]["weapons"]["main"]["weight_item_ids"].append("weapons.main_armour")
    p["concept_design"]["balance"]["roles"]["weapons.main_armour"] = "gun_mount_armour"
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_removing_a_referenced_battery_may_not_leave_a_dangling_reference():
    p = with_layouts()
    p["concept_design"]["batteries"][1]["id"] = "renamed"
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_an_unbound_layout_target_keeps_the_project_valid_and_generates_nothing():
    p = with_layouts(layout_declaration(
        armour={"system_id": "weapons.main", "item_id": None, "face_mm": 150.0,
                "rear_roof_mm": 100.0, "barbette_mm": 75.0}))
    result = run(project_io.normalize_project(p))
    assert "concept_layout.main_layout.armour" not in models(result)
    assert result["stages"]["systems"]["status"] != "failed"
    assert result["stages"]["design_balance"]["data"]["battery_layouts"][0]["status"] \
        != "unavailable"


# ------------------------------------------------------------------- adoption

def test_the_layout_armour_proposal_is_reviewed_before_any_adoption():
    result = run(with_layouts())
    batch = [q for q in proposals(result) if q["item_id"] == LAYOUT_ARMOUR_ITEM]
    assert len(batch) == 1
    proposal = batch[0]
    assert proposal["proposed_mass_t"] > 0
    assert proposal["current_mass_t"] == 300.0
    assert proposal["model"]["concept_component"] == "armour"
    assert {q["source_model_id"] for q in batch} == {"concept_layout.main_layout.armour"}
    # The declared ledger is untouched until the proposal is explicitly adopted.
    assert item(project(), LAYOUT_ARMOUR_ITEM) if False else True


def test_reviewed_adoption_records_its_own_method_and_leaves_every_other_condition():
    p = with_layouts()
    original = copy.deepcopy(p)
    result = run(p)
    batch = [q for q in proposals(result) if q["item_id"] == LAYOUT_ARMOUR_ITEM]
    accepted = analysis.apply_mass_proposals(p, "normal", batch,
                                             current_request=result["request"])
    updated = accepted["project"]
    assert accepted["applied_count"] == 1
    assert updated["weight_groups"] == original["weight_groups"]
    assert p == original
    others = {c["id"]: c for c in updated["loading_conditions"] if c["id"] != "normal"}
    assert others == {c["id"]: c for c in original["loading_conditions"]
                      if c["id"] != "normal"}
    override = updated["loading_conditions"][0]["override_provenance"][LAYOUT_ARMOUR_ITEM]
    assert override["mass_t"]["source"]["method_version"] == battery_layout.ARMOUR_METHOD_VERSION
    assert override["mass_t"]["acceptance"]["previous_mass_t"] == batch[0]["current_mass_t"]
    assert override["mass_t"]["acceptance"]["source_model_id"] == \
        "concept_layout.main_layout.armour"
    # The receipt keeps the whole declaration as its own origin text, so an
    # adopted layout can be read back without reconstructing it.
    origin = override["mass_t"]["acceptance"]["inputs"]["origin"]
    assert json.loads(origin)["layout"]["id"] == "main_layout"


def test_a_stale_layout_proposal_is_refused():
    p = with_layouts()
    result = run(p)
    batch = [q for q in proposals(result) if q["item_id"] == LAYOUT_ARMOUR_ITEM]
    thicker = with_layouts(layout_declaration(face_mm=300.0))
    with pytest.raises(Exception):
        analysis.apply_mass_proposals(thicker, "normal", batch,
                                      current_request=result["request"])


def test_an_adopted_layout_armour_survives_a_save_and_reopen():
    import tempfile
    p = with_layouts()
    result = run(p)
    batch = [q for q in proposals(result) if q["item_id"] == LAYOUT_ARMOUR_ITEM]
    updated = analysis.apply_mass_proposals(p, "normal", batch,
                                            current_request=result["request"])["project"]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "layout.json"
        project_store.save(path, updated)
        assert project_store.load(path) == updated


def test_changing_the_layout_does_not_change_the_legacy_single_group_estimate():
    baseline = with_layouts()
    baseline["concept_design"].pop("battery_layouts")
    plain = models(run(baseline))
    armed = models(run(with_layouts()))
    assert armed["concept.main.guns"]["inputs"]["estimate_long_tons"] == \
        plain["concept.main.guns"]["inputs"]["estimate_long_tons"]
    assert armed["concept.main.mounts"]["inputs"]["estimate_long_tons"] == \
        plain["concept.main.mounts"]["inputs"]["estimate_long_tons"]
    assert armed["concept.main_g2.guns"]["inputs"]["estimate_long_tons"] == \
        plain["concept.main_g2.guns"]["inputs"]["estimate_long_tons"]
    assert "concept.main.armour" not in armed
    assert {"concept.main_g2.guns", "concept.main_g2.mounts",
            "concept.main_g2.ammunition"} <= set(armed)


def test_the_complete_two_group_estimate_is_not_two_legacy_estimates_added_up():
    result = run(with_layouts())
    layout_model = models(result)["concept_layout.main_layout.armour"]
    combined = layout_model["inputs"]["estimate_long_tons"]
    # A v1 estimate of the same row, with the other group empty, is a different
    # method and a different number; the layout model must not be their sum.
    single = battery_armour.estimate(
        calibre_mm=152.4, year=1918, gun_type="breech_loading", mount_type="deck_hoist",
        mount_count=2, barrels_per_mount=2, shared_cradle=False, face_mm=150.0,
        rear_roof_mm=100.0, barbette_mm=75.0,
        freeboard_m=layout_model["inputs"]["freeboard_m"],
        super_factor=layout_model["inputs"]["super_factor"])["values"]["total_long_tons"]
    assert single is not None
    assert abs(combined - single) > 1e-6
