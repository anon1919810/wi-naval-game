"""Declared page-row projection: ledger authority, invariants, honest unknowns.

These tests are ship-agnostic (synthetic ledger) except the single Queen Mary
integration check at the end.
"""

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
TOOLS = PKG.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import analysis, loading, page_rows, project_store, systems  # noqa: E402


def item(item_id, mass, **extra):
    payload = {"id": item_id, "mass_t": mass, "estimate": extra.pop("estimate", True),
               "source": extra.pop("source", "declared fixture")}
    payload.update(extra)
    return payload


def state(items):
    return {"schema": "plimsoll-loading-1", "condition_id": "normal",
            "project_fingerprint": "p" * 8, "input_fingerprint": "i" * 8,
            "effective_items": items}


def systems_result(bound_ids, leaf_mass, models=(), leaf="armour.fixed"):
    return {"schema": "plimsoll-systems-1",
            "systems": {leaf: {
                "ledger_mass_t": leaf_mass, "linked_items": list(bound_ids),
                "mass_models": list(models), "status": "complete"}}}


def declaration(rows):
    return [dict(row) for row in rows]


class ProjectionTests(unittest.TestCase):
    def test_rows_take_mass_from_the_ledger_not_from_declaration(self):
        ledger = state([item("belt", 100.0), item("deck", 40.0)])
        result = page_rows.armour_rows(
            ledger, systems_result(["belt", "deck"], 140.0),
            declaration([
                {"row": "main", "weight_item_ids": ["belt"]},
                {"row": "armour_deck", "weight_item_ids": ["deck"]},
            ]))
        self.assertEqual([row["weight_t"] for row in result["rows"]], [100.0, 40.0])
        self.assertTrue(result["values"]["matches_ledger_mass"])
        self.assertEqual(result["values"]["uncovered_item_ids"], [])
        self.assertEqual([diag for diag in result["diagnostics"] if diag["blocking"]], [])

    def test_duplicate_item_across_rows_is_blocking(self):
        ledger = state([item("belt", 100.0)])
        result = page_rows.armour_rows(
            ledger, systems_result(["belt"], 100.0),
            declaration([
                {"row": "main", "weight_item_ids": ["belt"]},
                {"row": "upper", "weight_item_ids": ["belt"]},
            ]))
        codes = {diag["code"]: diag["blocking"] for diag in result["diagnostics"]}
        self.assertTrue(codes.get("page_rows.item_duplicate"))

    def test_unknown_item_is_blocking(self):
        ledger = state([item("belt", 100.0)])
        result = page_rows.armour_rows(
            ledger, systems_result(["belt"], 100.0),
            declaration([{"row": "main", "weight_item_ids": ["belt", "ghost"]}]))
        codes = {diag["code"]: diag["blocking"] for diag in result["diagnostics"]}
        self.assertTrue(codes.get("page_rows.item_unknown"))

    def test_uncovered_ledger_item_is_reported_not_dropped(self):
        ledger = state([item("belt", 100.0), item("deck", 40.0)])
        result = page_rows.armour_rows(
            ledger, systems_result(["belt", "deck"], 140.0),
            declaration([{"row": "main", "weight_item_ids": ["belt"]}]))
        self.assertEqual(result["values"]["uncovered_item_ids"], ["deck"])
        self.assertIn("page_rows.item_uncovered",
                      {diag["code"] for diag in result["diagnostics"]})

    def test_mass_mismatch_is_reported(self):
        ledger = state([item("belt", 100.0)])
        result = page_rows.armour_rows(
            ledger, systems_result(["belt"], 111.0),
            declaration([{"row": "main", "weight_item_ids": ["belt"]}]))
        self.assertFalse(result["values"]["matches_ledger_mass"])
        self.assertIn("page_rows.mass_mismatch",
                      {diag["code"] for diag in result["diagnostics"]})

    def test_unknown_mass_keeps_row_total_incomplete(self):
        ledger = state([item("belt", None)])
        ledger["effective_items"][0].pop("mass_t")
        result = page_rows.armour_rows(
            ledger, systems_result(["belt"], 0.0),
            declaration([{"row": "main", "weight_item_ids": ["belt"]}]))
        self.assertIn("page_rows.item_mass_unknown",
                      {diag["code"] for diag in result["diagnostics"]})

    def test_extents_are_declared_or_unknown_never_invented(self):
        ledger = state([item("belt", 100.0)])
        unknown = page_rows.armour_rows(
            ledger, systems_result(["belt"], 100.0),
            declaration([{"row": "main", "weight_item_ids": ["belt"]}]))["rows"][0]
        self.assertIsNone(unknown["length_m"])
        self.assertEqual(unknown["segment_status"], "unknown_no_declared_extent")

        declared = page_rows.armour_rows(
            ledger, systems_result(["belt"], 100.0),
            declaration([{"row": "main", "weight_item_ids": ["belt"],
                          "extents_m": {"aft_m": -60.0, "fore_m": 116.0}}]))["rows"][0]
        self.assertAlmostEqual(declared["length_m"], 176.0, places=9)
        self.assertEqual(declared["segment_status"], "declared_extents")

    def test_invalid_extents_are_reported_and_length_stays_unknown(self):
        ledger = state([item("belt", 100.0)])
        result = page_rows.armour_rows(
            ledger, systems_result(["belt"], 100.0),
            declaration([{"row": "main", "weight_item_ids": ["belt"],
                          "extents_m": {"aft_m": -60.0}}]))
        self.assertIsNone(result["rows"][0]["length_m"])
        self.assertIn("page_rows.extent_invalid",
                      {diag["code"] for diag in result["diagnostics"]})

    def test_thickness_echoed_from_plate_model_when_not_declared(self):
        ledger = state([item("belt", 100.0)])
        models = [{"id": "belt-model", "method": "plate_area_thickness_density_mass",
                   "linked_weight_item_id": "belt",
                   "inputs": {"area_m2": 627.0, "thickness_m": 0.229,
                              "density_kg_m3": 7850.0}, "estimate": True}]
        row = page_rows.armour_rows(
            ledger, systems_result(["belt"], 100.0, models),
            declaration([{"row": "main", "weight_item_ids": ["belt"]}]))["rows"][0]
        self.assertAlmostEqual(row["thickness_mm"], 229.0, places=9)
        self.assertAlmostEqual(row["area_m2"], 627.0, places=9)


class QueenMaryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        case = (PKG / "cases" / "projects" / "queen_mary_1913.project.json")
        cls.project = project_store.load(case)
        cls.state = loading.resolve_loading(cls.project, "normal-engineering")
        cls.summary = systems.summary(cls.project, cls.state)
        cls.declaration = cls.project["systems"]["armour"]["fixed"]["page_rows"]

    def test_declared_rows_cover_the_ledger_exactly(self):
        result = page_rows.armour_rows(self.state, self.summary, self.declaration)
        values = result["values"]
        self.assertEqual(values["declared_rows"], 7)
        self.assertEqual(values["declared_item_count"], 13)
        self.assertEqual(values["ledger_item_count"], 13)
        self.assertEqual(values["uncovered_item_ids"], [])

    def test_declared_rows_total_equals_the_ledger_armour_mass(self):
        result = page_rows.armour_rows(self.state, self.summary, self.declaration)
        self.assertTrue(result["values"]["matches_ledger_mass"])
        self.assertAlmostEqual(result["values"]["declared_rows_total_t"], 6820.701, places=3)
        self.assertAlmostEqual(result["values"]["ledger_leaf_mass_t"], 6820.701, places=3)

    def test_every_row_reports_unknown_segments_rather_than_a_guess(self):
        result = page_rows.armour_rows(self.state, self.summary, self.declaration)
        for row in result["rows"]:
            self.assertEqual(row["segment_status"], "unknown_no_declared_extent")
            self.assertIsNone(row["length_m"])

    def test_coordinator_attaches_the_projection_to_the_systems_stage(self):
        result = analysis.compute_project(
            self.project, "normal-engineering", {"stages": ["loading", "systems"]})
        stage = result["stages"]["systems"]
        self.assertEqual(stage["status"], "completed")
        projection = stage["data"]["page_rows"]["armour.fixed"]
        self.assertTrue(projection["values"]["matches_ledger_mass"])

    def test_a_project_without_a_declaration_gains_no_invented_rows(self):
        stripped = json.loads(json.dumps(self.project))
        stripped["systems"]["armour"]["fixed"].pop("page_rows")
        for leaf in stripped["systems"]["weapons"].values():
            leaf.pop("page_rows", None)
        result = analysis.compute_project(
            stripped, "normal-engineering", {"stages": ["loading", "systems"]})
        self.assertNotIn("page_rows", result["stages"]["systems"]["data"])


    def test_typed_fields_are_echoed_and_unknowns_reported(self):
        ledger = state([item("torpedoes", 62.0)])
        known = page_rows.project_declared_rows(
            ledger, systems_result(["torpedoes"], 62.0, leaf="weapons.torpedo"),
            "weapons", "torpedo",
            [{"row": "torpedo_main", "weight_item_ids": ["torpedoes"],
              "typed": {"tubes": 2, "carried": 14, "diameter_mm": 533.0}}])["rows"][0]
        self.assertEqual(known["typed_status"], "declared")
        self.assertEqual(known["typed_unknown_fields"], [])

        partial = page_rows.project_declared_rows(
            ledger, systems_result(["torpedoes"], 62.0, leaf="weapons.torpedo"),
            "weapons", "torpedo",
            [{"row": "torpedo_main", "weight_item_ids": ["torpedoes"],
              "typed": {"tubes": 2, "length_m": None}}])
        self.assertEqual(partial["rows"][0]["typed_status"], "partial_unknown")
        self.assertEqual(partial["rows"][0]["typed_unknown_fields"], ["length_m"])
        self.assertIn("page_rows.typed_field_unknown",
                      {diag["code"] for diag in partial["diagnostics"]})
        self.assertFalse(any(diag["blocking"] for diag in partial["diagnostics"]))

    def test_row_without_a_ledger_binding_has_unknown_mass_not_zero(self):
        ledger = state([item("torpedoes", 62.0)])
        result = page_rows.project_declared_rows(
            ledger, systems_result(["torpedoes"], 62.0, leaf="weapons.torpedo"),
            "weapons", "torpedo",
            [{"row": "torpedo_main", "weight_item_ids": ["torpedoes"]},
             {"row": "mines", "weight_item_ids": [], "typed": {"count": None}}])
        mines = result["rows"][1]
        self.assertIsNone(mines["weight_t"])
        self.assertEqual(mines["mass_status"], "no_ledger_binding")
        # unknown mass must not be counted as zero in the total
        self.assertAlmostEqual(result["values"]["declared_rows_total_t"], 62.0, places=9)
        self.assertTrue(result["values"]["matches_ledger_mass"])

    def test_undeclared_typed_row_is_reported_as_unknown(self):
        ledger = state([item("torpedoes", 62.0)])
        row = page_rows.project_declared_rows(
            ledger, systems_result(["torpedoes"], 62.0, leaf="weapons.torpedo"),
            "weapons", "torpedo", [{"row": "mines"}])["rows"][0]
        self.assertEqual(row["typed_status"], "unknown_no_typed_declaration")
        self.assertIsNone(row["typed"])


class QueenMaryWeaponsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        case = (PKG / "cases" / "projects" / "queen_mary_1913.project.json")
        cls.project = project_store.load(case)
        cls.state = loading.resolve_loading(cls.project, "normal-engineering")
        cls.summary = systems.summary(cls.project, cls.state)
        cls.declaration = cls.project["systems"]["weapons"]["torpedo"]["page_rows"]

    def test_torpedo_row_matches_the_ledger_and_flags_missing_length(self):
        result = page_rows.project_declared_rows(self.state, self.summary, "weapons",
                                                 "torpedo", self.declaration)
        values = result["values"]
        self.assertEqual(values["declared_rows"], 4)
        self.assertEqual(values["declared_item_count"], 2)
        self.assertEqual(values["ledger_item_count"], 2)
        self.assertTrue(values["matches_ledger_mass"])
        main = result["rows"][0]
        self.assertAlmostEqual(main["weight_t"], 62.0, places=9)
        self.assertEqual(main["typed"]["diameter_mm"], 533.0)
        self.assertEqual(main["typed_unknown_fields"], ["length_m"])

    def test_count_only_rows_stay_unknown(self):
        result = page_rows.project_declared_rows(self.state, self.summary, "weapons",
                                                 "torpedo", self.declaration)
        for row in result["rows"][1:]:
            self.assertIsNone(row["weight_t"])
            self.assertEqual(row["mass_status"], "no_ledger_binding")
            self.assertTrue(row["typed_unknown_fields"])

    def test_coordinator_attaches_armour_and_weapons_projections(self):
        result = analysis.compute_project(
            self.project, "normal-engineering", {"stages": ["loading", "systems"]})
        views = result["stages"]["systems"]["data"]["page_rows"]
        self.assertEqual(sorted(views), ["armour.fixed", "weapons.main",
                                         "weapons.misc_weight", "weapons.secondary",
                                         "weapons.torpedo"])
        self.assertTrue(views["armour.fixed"]["values"]["matches_ledger_mass"])
        self.assertTrue(views["weapons.torpedo"]["values"]["matches_ledger_mass"])


if __name__ == "__main__":
    unittest.main()
