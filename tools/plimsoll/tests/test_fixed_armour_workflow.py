# -*- coding: utf-8 -*-
"""Contract checks for the optional fixed armour and empirical cost in the workflow.

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
from plimsoll import concept_cost, fixed_armour  # noqa: E402
from plimsoll import _analysis_request as request_api  # noqa: E402

NEW_ITEM = "armour.fixed.bulge_extra"
NEW_SYSTEM = "armour.fixed_extra"


def project():
    return project_io.normalize_project(
        json.loads((ROOT / "tools/plimsoll/cases/projects/concept_cruiser.project.json")
                   .read_text(encoding="utf-8-sig")))


def run(p, condition="normal"):
    return analysis.compute_project(p, condition, {"stages": ["systems", "design_balance"]})


def models(result):
    data = result["stages"]["systems"]["data"]
    assert data is not None, result["stages"]["systems"]
    return {m["id"]: m for row in data["systems"].values() for m in row["mass_models"]}


def model_owner(result, model_id):
    for system_id, row in result["stages"]["systems"]["data"]["systems"].items():
        if any(m["id"] == model_id for m in row["mass_models"]):
            return system_id
    return None


def proposals(result, item_id=None):
    batch = result["stages"]["systems"]["data"]["update_proposals"]
    return [q for q in batch if item_id is None or q["item_id"] == item_id]


def diagnostics(result):
    return (result["stages"]["systems"].get("diagnostics", [])
            + result["stages"]["design_balance"].get("diagnostics", []))


def item(p, key):
    return next(i for g in p["weight_groups"] for i in g["items"] if i["id"] == key)


def region(rid, kind, system_id, item_id, **fields):
    declared = {"id": rid, "kind": kind, "system_id": system_id, "item_id": item_id,
                "source": "synthetic declared fixed armour; no vessel corresponds to it"}
    declared.update(fields)
    return declared


def with_regions(*regions, cost=None, **overrides):
    """A project with the declared fixed regions on the synthetic case's own items."""
    p = project()
    if regions:
        p["concept_design"]["fixed_armour"] = list(regions)
    if cost is not None:
        p["concept_design"]["cost"] = cost
    for key, value in overrides.items():
        if value is None and key in p["concept_design"]:
            p["concept_design"].pop(key)
        else:
            p["concept_design"][key] = value
    return p


MAIN_BELT = region("main_belt", "belt_main", "armour.fixed", "armour.belt_main",
                   thickness_mm=152.4, length_m=91.44, height_m=6.096)
BULGE = region("bulge", "bulge", "armour.fixed", "armour.bulge",
               thickness_mm=76.2, length_m=30.48, height_m=3.658)
TOWER = region("tower", "conning", "armour.fixed", "armour.conning",
               thickness_mm=203.2, aft_mm=101.6)
BOX_DECK = region("box_deck", "deck", "armour.fixed", "armour.deck",
                  thickness_mm=50.8, coverage_index=4, forecastle_fraction=0.26,
                  quarterdeck_fraction=0.20, forecastle_mm=50.8, quarterdeck_mm=25.4)


def with_new_target(p, rid="extra_bulge"):
    """Add one more independent unknown-mass target under its own systems leaf."""
    p["weight_groups"][0]["items"].append({
        "id": NEW_ITEM, "mass_t": 42.0, "x_m": 76.0, "y_m": 7.9, "kg_m": 3.2,
        "source": "synthetic declared placeholder for the extra fixed armour target",
        "estimate": True})
    p["systems"]["armour"]["fixed_extra"] = {
        "source": "synthetic declared placeholder for the extra fixed armour target",
        "estimate": True, "weight_item_ids": [NEW_ITEM]}
    p["concept_design"]["balance"]["roles"][NEW_ITEM] = "armour_bulge"
    p["concept_design"]["fixed_armour"].append(
        region(rid, "bulge", NEW_SYSTEM, NEW_ITEM, thickness_mm=101.6, length_m=24.384,
               height_m=4.572))
    return p


# ------------------------------------------------------------ compatibility --

def test_a_project_without_fixed_armour_or_cost_is_completely_unchanged():
    plain = run(project())
    data = plain["stages"]["design_balance"]["data"]
    assert "fixed_armour" not in data
    assert "cost" not in data
    assert not [m for m in models(plain) if m.startswith("concept_fixed_armour.")]
    assert plain["stages"]["design_balance"]["status"] == "completed"


def test_an_empty_fixed_armour_list_changes_nothing_either():
    p = project()
    p["concept_design"]["fixed_armour"] = []
    result = run(project_io.normalize_project(p))
    assert "fixed_armour" not in result["stages"]["design_balance"]["data"]
    assert not [m for m in models(result) if m.startswith("concept_fixed_armour.")]


def test_a_null_fixed_armour_and_a_null_cost_stay_disabled():
    p = with_regions(cost=None)
    p["concept_design"]["fixed_armour"] = None
    p["concept_design"]["cost"] = None
    result = run(project_io.normalize_project(p))
    data = result["stages"]["design_balance"]["data"]
    assert "fixed_armour" not in data
    assert "cost" not in data


def test_the_keys_are_refused_when_they_are_not_in_their_documented_shape():
    p = with_regions(MAIN_BELT)
    p["concept_design"]["fixed_armour"] = {"id": "x"}
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)
    p = with_regions(cost=["not", "an", "object"])
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_an_unknown_field_inside_a_region_or_the_cost_is_refused_not_ignored():
    p = with_regions(region("x", "bulge", "armour.fixed", "armour.bulge", pitch_deg=5.0))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)
    p = with_regions(cost={"source": "x", "exchange_rate": 4.0})
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_a_stale_or_renamed_section_key_is_refused_rather_than_ignored():
    for key, value in (("fixed_armours", []), ("costs", {}), ("fixed_armour_records", [])):
        p = project()
        p["concept_design"][key] = value
        with pytest.raises(project_io.ProjectValidationError):
            project_io.normalize_project(p)


# ---------------------------------------------------------------- the model --

def test_a_bound_available_region_registers_its_own_independent_model():
    result = run(with_regions(MAIN_BELT, BULGE, TOWER, BOX_DECK))
    found = models(result)
    assert "concept_fixed_armour.main_belt" in found
    model = found["concept_fixed_armour.main_belt"]
    assert model["method"] == "empirical_estimate_v1"
    assert model["linked_weight_item_id"] == "armour.belt_main"
    assert model_owner(result, "concept_fixed_armour.main_belt") == "armour.fixed"
    assert model["concept_component"] == "fixed_armour"
    assert model["source"]["method_version"] == fixed_armour.METHOD_VERSION
    assert model["inputs"]["method_version"] == fixed_armour.METHOD_VERSION
    assert model["source"]["sha256"] == fixed_armour.SOURCE_SHA256
    assert model["boundary"] == fixed_armour.SOURCE_SCOPE
    # The enclosing adapted method is untouched by an independent kernel.
    assert concept_design.METHOD == "sps-3b3-adapted-v1"


def test_the_model_uses_the_standard_five_percent_comparison_policy():
    result = run(with_regions(MAIN_BELT))
    model = models(result)["concept_fixed_armour.main_belt"]
    assert model["comparison_policy"] == concept_design.COMPARISON_POLICY
    ledger = item(with_regions(MAIN_BELT), "armour.belt_main")["mass_t"]
    assert model["comparison_tolerance_t"] == pytest.approx(
        max(concept_design.COMPARISON_TOLERANCE["absolute_t"],
            concept_design.COMPARISON_TOLERANCE["relative"] * abs(ledger)))
    assert len(proposals(result, "armour.belt_main")) == 1


def test_the_model_inputs_stay_flat_and_carry_the_whole_declaration_as_origin_text():
    model = models(run(with_regions(BOX_DECK)))["concept_fixed_armour.box_deck"]
    for key, value in model["inputs"].items():
        assert isinstance(value, (int, float, str)), key
        assert not isinstance(value, bool), key
    payload = json.loads(model["inputs"]["origin"])
    assert payload["record"]["id"] == "box_deck"
    assert payload["record"]["coverage_index"] == 4
    assert payload["provenance"]["source_sha256"] == fixed_armour.SOURCE_SHA256
    assert payload["context"]["displacement_t"]["value"] == 8200.0


def test_the_model_carries_the_recovered_per_term_breakdown():
    deck = models(run(with_regions(BOX_DECK)))["concept_fixed_armour.box_deck"]
    breakdown = deck["component_breakdown"]
    assert sorted(breakdown) == ["central_long_tons", "fore_long_tons", "quarter_long_tons"]
    assert breakdown["fore_long_tons"] > 0.0
    assert breakdown["quarter_long_tons"] > 0.0
    assert sum(breakdown.values()) == pytest.approx(
        deck["inputs"]["estimate_long_tons"])
    tower = models(run(with_regions(TOWER)))["concept_fixed_armour.tower"]
    assert sorted(tower["component_breakdown"]) == ["aft_long_tons", "fore_long_tons"]


def test_a_box_region_without_its_deck_fractions_generates_nothing_and_says_why():
    # The recovered method adds the forecastle and quarter-deck terms after the
    # coverage switch for every selector, so a box deck with no declared fractions
    # is an unfinished declaration, not a box with no upper plates.
    incomplete = region("box_deck", "deck", "armour.fixed", "armour.deck",
                        thickness_mm=50.8, coverage_index=4)
    result = run(with_regions(incomplete))
    assert "concept_fixed_armour.box_deck" not in models(result)
    reading = result["stages"]["design_balance"]["data"]["fixed_armour"][0]
    assert reading["status"] == "unavailable"
    assert reading["values"]["central_area_sqft"] is None
    assert any(d["field"] in ("forecastle_fraction", "quarterdeck_fraction")
               for d in reading["diagnostics"])


def test_a_missing_forecastle_plate_never_reads_as_a_zero_plate():
    incomplete = region("box_deck", "deck", "armour.fixed", "armour.deck",
                        thickness_mm=50.8, coverage_index=4, forecastle_fraction=0.26,
                        quarterdeck_fraction=0.20, quarterdeck_mm=25.4)
    result = run(with_regions(incomplete))
    assert "concept_fixed_armour.box_deck" not in models(result)
    reading = result["stages"]["design_balance"]["data"]["fixed_armour"][0]
    assert reading["status"] == "unavailable"
    assert any(d["field"] == "forecastle_mm" for d in reading["diagnostics"])


def test_the_regions_are_generated_before_the_design_hull_proxy():
    p = with_regions(MAIN_BELT, BULGE, TOWER)
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        p["hull"].pop(key, None)
    result = run(p)
    found = models(result)
    assert "concept.machinery" not in found
    assert "concept_fixed_armour.main_belt" not in found
    assert "concept_fixed_armour.bulge" in found
    assert "concept_fixed_armour.tower" in found


def test_an_unavailable_region_generates_no_model_but_still_reports_its_reading():
    p = with_regions(region("unknown_belt", "belt_main", "armour.fixed", "armour.belt_main",
                            length_m=91.44, height_m=6.096))
    result = run(p)
    assert "concept_fixed_armour.unknown_belt" not in models(result)
    reading = result["stages"]["design_balance"]["data"]["fixed_armour"][0]
    assert reading["status"] == "unavailable"
    assert reading["values"]["total_long_tons"] is None
    assert reading["diagnostics"]


def test_an_unbound_region_keeps_the_project_valid_and_generates_nothing():
    p = with_regions(region("draft", "bulge", None, None, thickness_mm=76.2, length_m=30.48,
                            height_m=3.658))
    result = run(project_io.normalize_project(p))
    assert "concept_fixed_armour.draft" not in models(result)
    assert result["stages"]["systems"]["status"] != "failed"
    assert result["stages"]["design_balance"]["data"]["fixed_armour"][0]["status"] == "available"


def test_a_freshly_added_empty_record_is_saveable_and_unfilled():
    # The exact shape a normal editor writes when a reader adds a region: a chosen
    # kind, no bindings, a blank note and every declared value an explicit unknown.
    p = with_regions({"id": "fixed_armour_1", "kind": "belt_main", "system_id": None,
                      "item_id": None, "source": "", "thickness_mm": None, "length_m": None,
                      "height_m": None})
    result = run(project_io.normalize_project(p))
    assert "concept_fixed_armour.fixed_armour_1" not in models(result)
    reading = result["stages"]["design_balance"]["data"]["fixed_armour"][0]
    assert reading["status"] == "unavailable"
    assert reading["values"]["total_long_tons"] is None
    assert result["stages"]["design_balance"]["status"] == "completed"


# ------------------------------------------------------------ design balance --

def test_the_balance_screen_returns_the_fixed_armour_readings():
    data = run(with_regions(MAIN_BELT, BULGE, TOWER))["stages"]["design_balance"]["data"]
    readings = data["fixed_armour"]
    assert [entry["id"] for entry in readings] == ["main_belt", "bulge", "tower"]
    entry = readings[0]
    assert entry["kind"] == "belt_main"
    assert entry["method_version"] == fixed_armour.METHOD_VERSION
    assert entry["status"] == "available"
    assert entry["values"]["total_long_tons"] > 0
    assert entry["values"]["mass_t"] > 0
    assert entry["provenance"]["source_sha256"] == fixed_armour.SOURCE_SHA256


def test_the_fixed_armour_readings_survive_a_missing_balance_section():
    p = with_regions(MAIN_BELT, BULGE)
    p["concept_design"].pop("balance")
    data = run(p)["stages"]["design_balance"]["data"]
    assert data["fixed_armour"][0]["values"]["total_long_tons"] > 0
    assert data["status"] != "completed"


def test_the_fixed_armour_readings_survive_a_missing_hull_proxy():
    p = with_regions(MAIN_BELT, BULGE)
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        p["hull"].pop(key, None)
    readings = run(p)["stages"]["design_balance"]["data"]["fixed_armour"]
    # The simple planar plate reads no hull context at all; the tapered belt does,
    # so it reports why instead of disappearing.
    assert readings[1]["status"] == "available"
    assert readings[1]["values"]["total_long_tons"] > 0
    assert readings[0]["status"] == "unavailable"
    assert readings[0]["values"]["total_long_tons"] is None
    assert readings[0]["diagnostics"]


def test_an_unavailable_region_never_takes_the_whole_screen_down():
    p = with_regions(region("bad", "deck", "armour.fixed", "armour.deck", thickness_mm=50.8))
    data = run(p)["stages"]["design_balance"]["data"]
    assert data["fixed_armour"][0]["status"] == "unavailable"
    assert data["status"] == "completed"
    assert data["values"]["structure_demand_long_tons"] is not None


# ------------------------------------------------------------- ownership --

def test_a_region_may_not_use_another_components_target():
    p = with_regions(region("steal", "bulge", "armour.fixed", "weapons.mounts",
                            thickness_mm=76.2, length_m=30.48, height_m=3.658))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_two_regions_may_not_weigh_the_same_item_twice():
    p = with_regions(BULGE, region("second_bulge", "bulge", "armour.fixed", "armour.bulge",
                                   thickness_mm=101.6, length_m=24.384, height_m=4.572))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_a_region_may_not_take_the_adjustable_structure_target():
    p = with_regions(region("steal", "bulge", "armour.fixed", "hull.structure",
                            thickness_mm=76.2, length_m=30.48, height_m=3.658))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_owning_system_must_actually_link_the_region_target():
    p = with_regions(region("wrong_leaf", "bulge", "propulsion.machinery", "armour.bulge",
                            thickness_mm=76.2, length_m=30.48, height_m=3.658))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_a_new_independent_target_is_allowed_and_keeps_its_own_role():
    p = with_new_target(with_regions(BULGE))
    result = run(project_io.normalize_project(p))
    found = models(result)
    assert "concept_fixed_armour.extra_bulge" in found
    model = found["concept_fixed_armour.extra_bulge"]
    assert model["linked_weight_item_id"] == NEW_ITEM
    assert model_owner(result, "concept_fixed_armour.extra_bulge") == NEW_SYSTEM
    assert concept_design.validate_config(
        project_io.normalize_project(p), {i["id"] for g in p["weight_groups"]
                                          for i in g["items"]})["fixed_armour"][1]["item_id"] \
        == NEW_ITEM


def test_the_region_target_must_carry_the_role_of_its_own_kind():
    for kind, item_id, wrong in (("bulge", "armour.bulge", "belt_main"),
                                 ("conning", "armour.conning", "rotating_armour"),
                                 ("deck", "armour.deck", "conning")):
        p = with_regions(region("x", kind, "armour.fixed", item_id, thickness_mm=76.2,
                                length_m=30.48, height_m=3.658, aft_mm=50.0))
        p["concept_design"]["balance"]["roles"][item_id] = wrong
        with pytest.raises(project_io.ProjectValidationError):
            project_io.normalize_project(p)


def test_removing_a_declaration_removes_only_the_declaration():
    p = with_regions(MAIN_BELT, BULGE)
    normalized = project_io.normalize_project(p)
    p["concept_design"]["fixed_armour"] = [BULGE]
    again = project_io.normalize_project(p)
    assert not [m for m in models(analysis.compute_project(
        again, "normal", {"stages": ["systems", "design_balance"]}))
        if m.startswith("concept_fixed_armour.main_belt")]
    # The target item and its declared mass are untouched by the removal.
    assert item(again, "armour.belt_main")["mass_t"] == item(normalized, "armour.belt_main")["mass_t"]
    assert again["systems"]["armour"]["fixed"]["weight_item_ids"] == \
        normalized["systems"]["armour"]["fixed"]["weight_item_ids"]


# ----------------------------------------------------------------- adoption --

def test_the_fixed_armour_proposal_is_reviewed_before_any_adoption():
    original = item(with_regions(MAIN_BELT), "armour.belt_main")["mass_t"]
    p = with_regions(MAIN_BELT)
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    assert len(batch) == 1
    proposal = batch[0]
    assert proposal["proposed_mass_t"] > 0
    assert proposal["current_mass_t"] == original
    assert proposal["requires_review"] is True
    assert proposal["source_model_id"] == "concept_fixed_armour.main_belt"
    # The declared ledger is untouched until the proposal is explicitly adopted.
    assert item(p, "armour.belt_main")["mass_t"] == original


def test_reviewed_adoption_records_its_own_method_and_leaves_every_other_condition():
    p = with_regions(MAIN_BELT)
    original = copy.deepcopy(p)
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    accepted = analysis.apply_mass_proposals(p, "normal", batch,
                                             current_request=result["request"])
    updated = accepted["project"]
    assert accepted["applied_count"] == 1
    assert updated["weight_groups"] == original["weight_groups"]
    assert p == original
    others = {c["id"]: c for c in updated["loading_conditions"] if c["id"] != "normal"}
    assert others == {c["id"]: c for c in original["loading_conditions"]
                      if c["id"] != "normal"}
    override = updated["loading_conditions"][0]["override_provenance"]["armour.belt_main"]
    assert override["mass_t"]["source"]["method_version"] == fixed_armour.METHOD_VERSION
    assert override["mass_t"]["acceptance"]["previous_mass_t"] == batch[0]["current_mass_t"]
    assert override["mass_t"]["acceptance"]["source_model_id"] == \
        "concept_fixed_armour.main_belt"
    origin = override["mass_t"]["acceptance"]["inputs"]["origin"]
    assert json.loads(origin)["record"]["id"] == "main_belt"


def test_an_old_mass_persists_until_the_region_is_edited_and_reviewed_again():
    p = with_regions(MAIN_BELT)
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    adopted = analysis.apply_mass_proposals(p, "normal", batch,
                                            current_request=result["request"])["project"]
    override = adopted["loading_conditions"][0]["overrides"]["armour.belt_main"]["mass_t"]
    assert override == pytest.approx(batch[0]["proposed_mass_t"])
    # Editing the declaration alone changes nothing in the adopted condition.
    thicker = copy.deepcopy(adopted)
    thicker["concept_design"]["fixed_armour"][0]["thickness_mm"] = 304.8
    assert thicker["loading_conditions"][0]["overrides"]["armour.belt_main"]["mass_t"] \
        == pytest.approx(batch[0]["proposed_mass_t"])
    # It only changes after a fresh run is reviewed and adopted again.
    rerun = run(project_io.normalize_project(thicker))
    new_batch = proposals(rerun, "armour.belt_main")
    assert new_batch[0]["current_mass_t"] == pytest.approx(override)
    assert new_batch[0]["proposed_mass_t"] > batch[0]["proposed_mass_t"]


def test_a_stale_fixed_armour_proposal_is_refused():
    p = with_regions(MAIN_BELT)
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    thicker = with_regions(region("main_belt", "belt_main", "armour.fixed", "armour.belt_main",
                                 thickness_mm=304.8, length_m=91.44, height_m=6.096))
    with pytest.raises(Exception):
        analysis.apply_mass_proposals(thicker, "normal", batch,
                                      current_request=result["request"])


def test_an_adopted_fixed_armour_survives_a_save_and_reopen():
    import tempfile
    p = with_regions(MAIN_BELT)
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    updated = analysis.apply_mass_proposals(p, "normal", batch,
                                            current_request=result["request"])["project"]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "fixed_armour.json"
        project_store.save(path, updated)
        assert project_store.load(path) == updated


def test_an_existing_layout_and_a_fixed_region_may_use_distinct_items():
    p = with_regions(MAIN_BELT)
    p["weight_groups"][0]["items"].append({
        "id": "weapons.layout_armour", "mass_t": 300.0, "x_m": 100.0, "y_m": 0.0,
        "kg_m": 60.0, "source": "synthetic declared layout armour target", "estimate": True})
    p["systems"]["weapons"]["main"]["weight_item_ids"].append("weapons.layout_armour")
    p["concept_design"]["balance"]["roles"]["weapons.layout_armour"] = "gun_mount_armour"
    p["concept_design"]["battery_layouts"] = [{
        "id": "main_layout", "source": "synthetic declared layout",
        "group1": {"battery_id": "main", "mount_selector": 4, "layout_index": 1,
                   "elevated_mounts": 2, "deck_mounts": 2, "depressed_mounts": 0},
        "group2": None, "group2_double_elevation": False, "group2_double_depression": False,
        "deck_profile": {"forecastle_fraction": 0.2, "forward_deck_fraction": 0.3,
                         "forward_fore_m": 2.2, "forward_aft_m": 1.6,
                         "aft_fore_m": 1.6, "aft_aft_m": 1.2},
        "armour": {"system_id": "weapons.main", "item_id": "weapons.layout_armour",
                   "face_mm": 150.0, "rear_roof_mm": 100.0, "barbette_mm": 75.0}}]
    result = run(project_io.normalize_project(p))
    found = models(result)
    assert "concept_layout.main_layout.armour" in found
    assert "concept_fixed_armour.main_belt" in found
    assert found["concept_layout.main_layout.armour"]["linked_weight_item_id"] == \
        "weapons.layout_armour"
    assert found["concept_fixed_armour.main_belt"]["linked_weight_item_id"] == \
        "armour.belt_main"
    assert {q["item_id"] for q in proposals(result)} >= {"weapons.layout_armour",
                                                         "armour.belt_main"}


def test_a_fixed_region_does_not_change_any_existing_estimate():
    baseline = run(project())
    armed = run(with_regions(MAIN_BELT, BULGE, TOWER, BOX_DECK))
    plain = models(baseline)
    with_regions_models = models(armed)
    for model_id, model in plain.items():
        assert with_regions_models[model_id]["inputs"]["estimate_long_tons"] == \
            model["inputs"]["estimate_long_tons"], model_id
    assert armed["stages"]["design_balance"]["data"]["roles"] == \
        baseline["stages"]["design_balance"]["data"]["roles"]


def test_a_declared_fixed_region_and_cost_declare_their_own_method_versions():
    # A saved report and a saved comparison gate on the method version each
    # component family actually ran under, so a changed or mismatched component
    # method is never compared as a delta.
    only_armour = run(with_regions(MAIN_BELT))["stages"]["design_balance"]["data"]
    assert only_armour["methods"] == {"fixed_armour": fixed_armour.METHOD_VERSION}
    only_cost = run(with_regions(cost={"source": None}))["stages"]["design_balance"]["data"]
    assert only_cost["methods"] == {"cost": concept_cost.METHOD_VERSION}
    both = run(with_regions(MAIN_BELT, cost={"source": None}))["stages"]["design_balance"]["data"]
    assert both["methods"] == {"fixed_armour": fixed_armour.METHOD_VERSION,
                               "cost": concept_cost.METHOD_VERSION}
    assert list(both["methods"]) == ["fixed_armour", "cost"]


def test_the_declared_methods_are_absent_when_neither_new_section_is_declared():
    # An absent optional feature adds no empty report section and no empty method
    # map, so an older saved report keeps exactly the shape it was saved with.
    plain = run(project())["stages"]["design_balance"]
    assert "methods" not in plain["data"]
    assert "methods" not in plain["method_versions"]
    assert plain["method_versions"]["kernel"] == concept_design.METHOD
    assert plain["method_versions"]["coordinator"] == "selected-loading-analysis-2"
    layouts_only = with_regions()
    layouts_only["concept_design"]["battery_layouts"] = None
    layouts_only["concept_design"]["batteries"] = []
    empty = run(project_io.normalize_project(layouts_only))["stages"]["design_balance"]
    assert "methods" not in empty["data"]


def test_the_coordinator_copies_the_declared_methods_onto_the_envelope():
    # The existing coordinator copies data.methods into the stage's
    # method_versions; this work adds no global request identity.
    result = run(with_regions(MAIN_BELT, cost={"source": None}))
    stage = result["stages"]["design_balance"]
    assert stage["method_versions"]["methods"] == stage["data"]["methods"]
    assert stage["method_versions"]["methods"] == {
        "fixed_armour": "sps-3b3-fixed-armour-v1", "cost": "sps-3b3-cost-v1"}
    assert stage["method_versions"]["kernel"] == "sps-3b3-adapted-v1"
    assert result["method_versions"] == request_api.VERSIONS
    assert "fixed_armour" not in result["method_versions"]
    assert "cost" not in result["method_versions"]
    json.dumps(result["stages"]["design_balance"], allow_nan=False)


def test_a_declared_layout_joins_the_method_map_when_a_new_section_is_present():
    p = with_regions(MAIN_BELT, cost={"source": None})
    p["weight_groups"][0]["items"].append({
        "id": "weapons.layout_armour", "mass_t": 300.0, "x_m": 100.0, "y_m": 0.0,
        "kg_m": 60.0, "source": "synthetic declared layout armour target", "estimate": True})
    p["systems"]["weapons"]["main"]["weight_item_ids"].append("weapons.layout_armour")
    p["concept_design"]["balance"]["roles"]["weapons.layout_armour"] = "gun_mount_armour"
    p["concept_design"]["batteries"][0]["mount_count"] = 2
    p["concept_design"]["battery_layouts"] = [{
        "id": "main_layout", "source": "synthetic declared layout",
        "group1": {"battery_id": "main", "mount_selector": 4, "layout_index": 1,
                   "elevated_mounts": 1, "deck_mounts": 1, "depressed_mounts": 0},
        "group2": None, "group2_double_elevation": False, "group2_double_depression": False,
        "deck_profile": {"forecastle_fraction": 0.2, "forward_deck_fraction": 0.3,
                         "forward_fore_m": 2.2, "forward_aft_m": 1.6,
                         "aft_fore_m": 1.6, "aft_aft_m": 1.2},
        "armour": {"system_id": "weapons.main", "item_id": "weapons.layout_armour",
                   "face_mm": 150.0, "rear_roof_mm": 100.0, "barbette_mm": 75.0}}]
    data = run(project_io.normalize_project(p))["stages"]["design_balance"]["data"]
    assert data["methods"] == {"fixed_armour": fixed_armour.METHOD_VERSION,
                               "layout": "sps-3b3-battery-layout-v1",
                               "cost": concept_cost.METHOD_VERSION}


# ------------------------------------------------------------------- cost --

def test_a_declared_cost_section_returns_its_own_reading():
    data = run(with_regions(cost={"source": "synthetic declared cost source"}))[
        "stages"]["design_balance"]["data"]
    cost = data["cost"]
    assert cost["method_version"] == concept_cost.METHOD_VERSION
    assert cost["method_scope"] == concept_cost.SOURCE_SCOPE
    assert cost["status"] == "available"
    assert cost["source"] == "synthetic declared cost source"
    for key in ("usd_million", "gbp_million", "load_long_tons", "light_basis_long_tons",
                "year_factor", "light_usd_million", "machinery_usd_million",
                "borne_usd_million"):
        assert key in cost["values"], key
    assert cost["values"]["gbp_million"] == pytest.approx(cost["values"]["usd_million"] / 4.0)
    assert "4:1" in cost["currency_convention"]


def test_the_cost_reading_needs_no_fixed_armour_and_no_design_hull():
    p = with_regions(cost={"source": None})
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        p["hull"].pop(key, None)
    p["concept_design"].pop("balance")
    data = run(p)["stages"]["design_balance"]["data"]
    assert data["status"] != "completed"
    assert data["cost"]["status"] == "unavailable"


def test_a_cost_section_without_a_balance_section_is_unavailable_not_zero():
    p = with_regions(cost={"source": None})
    p["concept_design"].pop("balance")
    data = run(p)["stages"]["design_balance"]["data"]
    assert data["cost"]["status"] == "unavailable"
    assert data["cost"]["values"]["usd_million"] is None
    assert any(d["code"] == "concept_design.cost_unavailable"
               for d in diagnostics(run(p)))


def test_the_cost_reads_the_selected_condition_and_never_a_proposed_mass():
    p = with_regions(cost={"source": None})
    result = run(p)
    cost = result["stages"]["design_balance"]["data"]["cost"]
    assert cost["inputs"]["fuel_mass_t"] == pytest.approx(711.2328)
    assert cost["inputs"]["machinery_mass_t"] == pytest.approx(1168.4539)
    # Adopting the fuel estimate changes the next run's cost, and only then.
    batch = proposals(result, "propulsion.fuel")
    adopted = analysis.apply_mass_proposals(p, "normal", batch,
                                            current_request=result["request"])["project"]
    assert run(adopted)["stages"]["design_balance"]["data"]["cost"]["values"]["usd_million"] \
        != cost["values"]["usd_million"]
    assert run(adopted)["stages"]["design_balance"]["data"]["cost"]["inputs"]["fuel_mass_t"] \
        == pytest.approx(batch[0]["proposed_mass_t"])


def test_each_condition_reports_its_own_selected_cost():
    p = with_regions(cost={"source": None})
    normal = run(p, "normal")["stages"]["design_balance"]["data"]["cost"]
    deep = run(p, "deep")["stages"]["design_balance"]["data"]["cost"]
    assert normal["inputs"]["fuel_mass_t"] == pytest.approx(711.2328)
    assert deep["inputs"]["fuel_mass_t"] == pytest.approx(1480.7278)
    assert deep["values"]["usd_million"] != normal["values"]["usd_million"]
    assert normal["values"]["year_factor"] == pytest.approx(2.0)


def test_the_cost_reads_the_declared_hull_year_not_the_engine_year():
    p = with_regions(cost={"source": None})
    data = run(p)["stages"]["design_balance"]["data"]
    assert data["cost"]["values"]["year_factor"] == pytest.approx(
        1.0 + (1918 + 1.5 - 1914) / 5.5)
    assert data["cost"]["inputs"]["hull_year"] == 1918
    assert p["concept_design"]["machinery"]["year"] == 1905


def test_the_cost_creates_no_target_no_model_and_no_proposal():
    baseline = project()
    armed = with_regions(cost={"source": None})
    assert {i["id"] for g in armed["weight_groups"] for i in g["items"]} == \
        {i["id"] for g in baseline["weight_groups"] for i in g["items"]}
    assert {i["id"]: i.get("mass_t") for g in armed["weight_groups"] for i in g["items"]} == \
        {i["id"]: i.get("mass_t") for g in baseline["weight_groups"] for i in g["items"]}
    assert sorted(models(run(armed))) == sorted(models(run(baseline)))
    assert {q["item_id"] for q in proposals(run(armed))} == \
        {q["item_id"] for q in proposals(run(baseline))}


def test_an_unclassified_selected_mass_leaves_the_cost_unavailable():
    p = with_regions(cost={"source": None})
    p["concept_design"]["balance"]["roles"].pop("misc.hull")
    p["weight_groups"][0]["items"].append({
        "id": "extra.unclassified", "mass_t": 12.0, "x_m": 10.0, "y_m": 0.0, "kg_m": 1.0,
        "source": "synthetic unclassified placeholder", "estimate": True})
    p["systems"]["weapons"]["misc_weight"]["weight_item_ids"].append("extra.unclassified")
    result = run(project_io.normalize_project(p))
    cost = result["stages"]["design_balance"]["data"]["cost"]
    assert cost["status"] == "unavailable"
    assert cost["values"]["usd_million"] is None
    assert any("extra.unclassified" in json.dumps(d) for d in diagnostics(result))


def test_a_guns_role_item_that_is_not_bound_to_a_battery_leaves_the_cost_unavailable():
    p = with_regions(cost={"source": None})
    p["concept_design"]["batteries"] = []
    result = run(project_io.normalize_project(p))
    cost = result["stages"]["design_balance"]["data"]["cost"]
    assert cost["status"] == "unavailable"
    assert any(d["code"] == "concept_design.cost_borne_unavailable"
               for d in diagnostics(result))
