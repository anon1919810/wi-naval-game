# -*- coding: utf-8 -*-
"""Workflow contract for the optional rectangular armour-panel geometry.

Written against the contract, not against a draft: every assertion states a
property the declared document and the returned result must have. These tests
run the real project normalization, the real analysis stages and the real
proposal/adoption workflow; nothing is mocked. The pure kernel's own numbers are
covered by ``test_armour_geometry.py``; here we check the integration, the
adoption path and the physical recomputation.
"""

import copy
import json
import tempfile
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from plimsoll import analysis, concept_design, project_io, project_store  # noqa: E402
from plimsoll import armour_geometry, fixed_armour  # noqa: E402


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


def proposals(result, item_id=None):
    batch = result["stages"]["systems"]["data"]["update_proposals"]
    return [q for q in batch if item_id is None or q["item_id"] == item_id]


def data(result):
    return result["stages"]["design_balance"]["data"]


def item(p, key):
    return next(i for g in p["weight_groups"] for i in g["items"] if i["id"] == key)


def region(rid, kind, system_id, item_id, **fields):
    declared = {"id": rid, "kind": kind, "system_id": system_id, "item_id": item_id,
                "source": "synthetic declared fixed armour; no vessel corresponds to it"}
    declared.update(fields)
    return declared


MAIN_BELT = region("main_belt", "belt_main", "armour.fixed", "armour.belt_main",
                   thickness_mm=152.4, length_m=91.44, height_m=6.096)
UPPER_BELT = region("upper_belt", "belt_upper", "armour.fixed", "armour.belt_upper",
                    thickness_mm=127.0, length_m=91.44, height_m=4.572)
END_BELT = region("end_belt", "belt_ends", "armour.fixed", "armour.belt_ends",
                  thickness_mm=101.6, length_m=30.48, height_m=6.096)
BULKHEAD = region("tk_bulkhead", "bulkhead", "armour.fixed", "armour.bulkhead",
                  thickness_mm=76.2, length_m=24.384, height_m=7.62)
DECK = region("arm_deck", "deck", "armour.fixed", "armour.deck", thickness_mm=63.5,
              coverage_index=4, forecastle_fraction=0.26, quarterdeck_fraction=0.20,
              forecastle_mm=50.8, quarterdeck_mm=25.4)


def with_fixed(*regions):
    p = project()
    p["concept_design"]["fixed_armour"] = list(regions)
    return p


def plate(pid="p1", **fields):
    declared = {"id": pid, "source": "synthetic plate source",
                "density_source": "synthetic density source",
                "length_m": 10.0, "width_m": 2.0, "thickness_mm": 100.0,
                "density_kg_m3": 7850.0, "count": 2, "width_basis": "developed",
                "inclination_deg": None}
    declared.update(fields)
    return declared


def geo_region(fid="main_belt", source="synthetic panel region source", plates=None):
    return {"fixed_armour_id": fid, "source": source,
            "plates": [plate()] if plates is None else plates}


def with_geometry(*regions, fixed=(MAIN_BELT,), source="synthetic panel source"):
    p = with_fixed(*fixed)
    p["concept_design"]["armour_geometry"] = {"source": source, "regions": list(regions)}
    return p


# ------------------------------------------------------------ compatibility --

def test_an_absent_geometry_section_changes_nothing():
    plain = run(project())
    assert "armour_geometry" not in data(plain)
    assert "armour_geometry" not in (data(plain).get("methods") or {})
    assert not [m for m in models(plain) if m.startswith("concept_geometry.")]


def test_a_null_geometry_section_stays_disabled():
    p = with_fixed(MAIN_BELT)
    p["concept_design"]["armour_geometry"] = None
    result = run(project_io.normalize_project(p))
    assert "armour_geometry" not in data(result)
    assert "concept_fixed_armour.main_belt" in models(result)


def test_an_empty_region_list_opts_in_no_region():
    p = with_geometry(fixed=(MAIN_BELT,))
    result = run(p)
    assert data(result)["armour_geometry"] == []
    assert "concept_fixed_armour.main_belt" in models(result)


# ------------------------------------------------------------- the model ----

def test_one_physical_model_per_bound_opted_region():
    result = run(with_geometry(geo_region()))
    found = models(result)
    assert "concept_geometry.main_belt" in found
    assert "concept_fixed_armour.main_belt" not in found
    model = found["concept_geometry.main_belt"]
    assert model["method"] == "armour_panels_mass_v1"
    assert model["concept_component"] == "fixed_armour"
    assert model["linked_weight_item_id"] == "armour.belt_main"
    assert model["source"]["method_version"] == armour_geometry.METHOD_VERSION
    assert "assembly" not in model["source"]
    assert "sha256" not in model["source"]
    # The four pinned physical inputs, and nothing opaque beside them.
    assert set(model["inputs"]) == {"method_version", "region_kind", "geometry_source", "region"}
    assert model["inputs"]["method_version"] == armour_geometry.METHOD_VERSION
    assert model["inputs"]["region_kind"] == "belt_main"
    assert model["inputs"]["geometry_source"] == "synthetic panel source"
    assert model["inputs"]["region"]["fixed_armour_id"] == "main_belt"
    assert model["inputs"]["region"]["plates"][0]["length_m"] == 10.0
    assert model["calculated_mass_t"] == pytest.approx(31.4)
    assert model["comparison_tolerance_t"] == 0.0


def test_the_design_balance_reading_is_exposed_independently():
    result = run(with_geometry(geo_region()))
    entry = data(result)["armour_geometry"][0]
    assert entry["id"] == "main_belt"
    assert entry["method_version"] == armour_geometry.METHOD_VERSION
    assert entry["status"] == "available"
    assert entry["adoptable"] is True
    assert entry["values"]["area_m2"] == pytest.approx(40.0)
    assert entry["values"]["mass_t"] == pytest.approx(31.4)
    assert [r["id"] for r in entry["records"]] == ["p1"]
    assert data(result)["methods"]["armour_geometry"] == armour_geometry.METHOD_VERSION


def test_the_old_sps_reading_keeps_its_own_numbers_and_method():
    result = run(with_geometry(geo_region()))
    fixed = data(result)["fixed_armour"][0]
    assert fixed["active_mass_model"] == "geometry"
    assert fixed["geometry_selected"] is True
    assert fixed["adoption_notice"]
    assert fixed["method_version"] == fixed_armour.METHOD_VERSION
    assert fixed["values"]["total_long_tons"] > 0
    # The old empirical model itself is gone; the reading is comparison only.
    assert "concept_fixed_armour.main_belt" not in models(result)


# ------------------------------------------------- opted-in but unfinished --

def test_an_opted_incomplete_region_never_falls_back_to_the_old_model():
    p = with_geometry(geo_region(plates=[plate(length_m=None, width_m=None)]))
    result = run(project_io.normalize_project(p))
    found = models(result)
    assert "concept_fixed_armour.main_belt" not in found
    assert "concept_geometry.main_belt" not in found
    entry = data(result)["armour_geometry"][0]
    assert entry["status"] == "unavailable"
    assert entry["values"]["mass_t"] is None
    assert entry["adoptable"] is False


def test_an_opted_empty_plate_list_is_incomplete_not_zero():
    p = with_geometry(geo_region(plates=[]))
    result = run(project_io.normalize_project(p))
    assert "concept_geometry.main_belt" not in models(result)
    entry = data(result)["armour_geometry"][0]
    assert entry["status"] == "unavailable"
    assert entry["values"]["mass_t"] is None
    assert entry["records"] == []


def test_armour_totals_select_the_geometry_once_and_unknown_blocks():
    p = with_geometry(geo_region())
    p["concept_design"]["mass_summary"] = {"source": "synthetic summary",
                                           "armour_scope_complete": None}
    totals = data(run(project_io.normalize_project(p)))["armour_totals"]
    assert totals["values"]["known_estimate_subtotal_t"] == pytest.approx(31.4)

    incomplete = with_geometry(geo_region(plates=[plate(length_m=None, width_m=None)]))
    incomplete["concept_design"]["mass_summary"] = {"source": "synthetic summary",
                                                    "armour_scope_complete": None}
    broken = data(run(project_io.normalize_project(incomplete)))["armour_totals"]
    # The opted geometry is unknown and must not fall back to the known SPS mass.
    assert broken["values"]["known_estimate_subtotal_t"] is None


def test_a_determined_zero_mass_is_adoptable_even_when_area_is_unknown():
    # A known zero count is a determined zero area/volume/mass.
    count_zero = with_geometry(geo_region(plates=[
        plate(count=0, length_m=None, width_m=None, thickness_mm=None,
              density_kg_m3=None, width_basis=None, inclination_deg=None,
              source=None, density_source=None)]))
    entry = data(run(project_io.normalize_project(count_zero)))["armour_geometry"][0]
    assert entry["status"] == "available"
    assert entry["values"]["mass_t"] == 0.0
    assert entry["values"]["area_m2"] == 0.0
    assert entry["adoptable"] is True

    # A known zero thickness determines a zero mass while the area stays unknown.
    thickness_zero = with_geometry(geo_region(plates=[
        plate(thickness_mm=0.0, density_kg_m3=None, length_m=None, width_m=None,
              width_basis="developed", source=None, density_source=None)]))
    result = run(project_io.normalize_project(thickness_zero))
    entry = data(result)["armour_geometry"][0]
    assert entry["status"] == "partial"
    assert entry["values"]["mass_t"] == 0.0
    assert entry["values"]["area_m2"] is None
    assert entry["adoptable"] is True
    assert "concept_geometry.main_belt" in models(result)


# --------------------------------------------------------- all five kinds ---

def test_all_five_eligible_kinds_generate_geometry_models():
    regions = [geo_region("main_belt"), geo_region("upper_belt"), geo_region("end_belt"),
               geo_region("tk_bulkhead"), geo_region("arm_deck")]
    p = with_geometry(*regions, fixed=(MAIN_BELT, UPPER_BELT, END_BELT, BULKHEAD, DECK))
    result = run(project_io.normalize_project(p))
    found = models(result)
    ids = ["main_belt", "upper_belt", "end_belt", "tk_bulkhead", "arm_deck"]
    for fid in ids:
        assert "concept_geometry.%s" % fid in found, fid
        assert "concept_fixed_armour.%s" % fid not in found, fid
    assert [entry["id"] for entry in data(result)["armour_geometry"]] == ids


# ---------------------------------------------------------- independence ----

def test_the_geometry_reading_survives_a_missing_design_hull():
    p = with_geometry(geo_region())
    for key in ("lwl_m", "beam_m", "draught_normal_m", "block_coeff"):
        p["hull"].pop(key, None)
    result = run(p)
    assert data(result)["armour_geometry"][0]["values"]["mass_t"] == pytest.approx(31.4)
    assert data(result)["status"] != "completed"


def test_switching_geometry_off_restores_the_old_model_without_editing_the_ledger():
    p = with_geometry(geo_region())
    on = models(run(p))
    assert "concept_geometry.main_belt" in on
    assert "concept_fixed_armour.main_belt" not in on
    off_project = copy.deepcopy(p)
    off_project["concept_design"]["armour_geometry"] = None
    off = models(run(off_project))
    assert "concept_fixed_armour.main_belt" in off
    assert "concept_geometry.main_belt" not in off
    assert item(off_project, "armour.belt_main")["mass_t"] == \
        item(p, "armour.belt_main")["mass_t"]


# ------------------------------------------------------------- adoption -----

def test_the_physical_proposal_recomputes_and_is_adopted_with_its_method():
    p = with_geometry(geo_region())
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    assert len(batch) == 1
    assert batch[0]["proposed_mass_t"] == pytest.approx(31.4)
    assert batch[0]["source_model_id"] == "concept_geometry.main_belt"
    accepted = analysis.apply_mass_proposals(p, "normal", batch,
                                             current_request=result["request"])
    assert accepted["applied_count"] == 1
    updated = accepted["project"]
    override = updated["loading_conditions"][0]["override_provenance"]["armour.belt_main"]["mass_t"]
    assert override["acceptance"]["method"] == "armour_panels_mass_v1"
    assert override["source"]["method"] == "accepted_selected_condition_physical_model"
    assert override["source"]["model_source"]["method_version"] == armour_geometry.METHOD_VERSION
    assert "assembly" not in override["source"]["model_source"]
    assert "sha256" not in override["source"]["model_source"]
    assert set(override["acceptance"]["inputs"]) == {
        "method_version", "region_kind", "geometry_source", "region"}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "geometry.json"
        project_store.save(path, updated)
        assert project_store.load(path) == updated


def test_a_forged_opaque_geometry_receipt_is_refused():
    p = with_geometry(geo_region())
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    updated = analysis.apply_mass_proposals(p, "normal", batch,
                                            current_request=result["request"])["project"]
    # The honest stored receipt round-trips through the real validator.
    project_io.normalize_project(updated)
    # A precomputed mass smuggled in beside the declaration is refused.
    forged = copy.deepcopy(updated)
    acceptance = forged["loading_conditions"][0]["override_provenance"]["armour.belt_main"]["mass_t"]["acceptance"]
    acceptance["inputs"]["mass_t"] = 999.0
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(forged)
    # A region that is not a valid declaration is refused too.
    forged2 = copy.deepcopy(updated)
    acceptance2 = forged2["loading_conditions"][0]["override_provenance"]["armour.belt_main"]["mass_t"]["acceptance"]
    acceptance2["inputs"]["region"] = {"fixed_armour_id": "main_belt", "plates": "not-a-list"}
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(forged2)


def test_a_stale_geometry_proposal_is_refused():
    p = with_geometry(geo_region())
    result = run(p)
    batch = proposals(result, "armour.belt_main")
    thicker = with_geometry(geo_region(plates=[plate(thickness_mm=300.0)]))
    with pytest.raises(Exception):
        analysis.apply_mass_proposals(thicker, "normal", batch,
                                      current_request=result["request"])
