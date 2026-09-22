"""Synthetic systems-to-ledger integration tests independent of source cases."""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG)

import systems  # noqa: E402
import loading  # noqa: E402
import project_io  # noqa: E402


def fixture() -> tuple[dict, dict]:
    project = {
        "id": "systems-fixture",
        "systems": {
            "propulsion": {
                "status": "present",
                "weight_item_ids": ["engine"],
                "source": "analytic propulsion fixture",
                "estimate": False,
                "mass_models": [
                    {
                        "id": "engine-volume-check",
                        "method": "volume_density_mass",
                        "linked_weight_item_id": "engine",
                        "inputs": {"volume_m3": 12.5, "density_kg_m3": 8000.0},
                        "comparison_tolerance": {"relative": 0.01, "absolute_t": 0.01},
                        "source": "analytic identity",
                        "estimate": False,
                    }
                ],
            },
            "armament": {
                "status": "present",
                "weight_item_ids": ["ammo", "armour"],
                "installed_count": 10,
                "broadside_count": 5,
                "source": "analytic armament fixture",
                "estimate": True,
                "mass_models": [
                    {
                        "id": "ammunition-count-check",
                        "method": "counted_unit_mass",
                        "linked_weight_item_id": "ammo",
                        "inputs": {"unit_mass_t": 4.0, "count_field": "installed_count"},
                        "comparison_tolerance": {"relative": 0.0, "absolute_t": 1e-10},
                        "source": "analytic identity",
                        "estimate": False,
                    },
                    {
                        "id": "armour-plate-check",
                        "method": "plate_area_thickness_density_mass",
                        "linked_weight_item_id": "armour",
                        "inputs": {"area_m2": 100.0, "thickness_m": 0.05,
                                   "density_kg_m3": 7850.0},
                        "comparison_tolerance": {"relative": 0.01, "absolute_t": 0.01},
                        "source": "analytic plate check",
                        "estimate": True,
                    },
                ],
            },
            "aviation": {
                "status": "absent",
                "reason": "fixture declares no aviation system",
                "source": "fixture declaration",
                "estimate": False,
            },
        },
    }
    state = {
        "schema": "plimsoll-loading-1",
        "project_id": "systems-fixture",
        "condition_id": "normal",
        "project_fingerprint": "project-fingerprint",
        "input_fingerprint": "loading-fingerprint",
        "complete_mass": True,
        "diagnostics": [],
        "effective_items": [
            {"id": "engine", "mass_t": 100.0, "source": "ledger engine", "estimate": False,
             "includes": ["machinery.main-engines"], "provenance": {"source": "ledger engine", "estimate": False}},
            {"id": "ammo", "mass_t": 40.0, "source": "ledger ammunition", "estimate": False,
             "includes": ["armament.ammunition"], "provenance": {"source": "ledger ammunition", "estimate": False}},
            {"id": "armour", "mass_t": 60.0, "source": "ledger armour", "estimate": True,
             "includes": ["armament.mount-armour"], "provenance": {"source": "ledger armour", "estimate": True}},
        ],
    }
    return project, state


class SystemsLedgerTests(unittest.TestCase):
    def test_ledger_masses_are_authoritative_and_formulas_do_not_add_mass(self):
        """Catch summing a physical check on top of linked ledger masses."""
        project, state = fixture()
        before = copy.deepcopy(project), copy.deepcopy(state)
        result = systems.summary(project, state)
        self.assertEqual((project, state), before)
        self.assertEqual(result["values"]["linked_known_mass_t"], 200.0)
        self.assertEqual(result["values"]["linked_total_mass_t"], 200.0)
        self.assertEqual(result["systems"]["armament"]["ledger_mass_t"], 100.0)
        self.assertEqual(result["systems"]["armament"]["mass_models"][1]["calculated_mass_t"], 39.25)
        self.assertEqual(result["mass_authority"], "selected_loading_weight_ledger")

    def test_mismatch_emits_reviewable_proposal_without_mutating_mass(self):
        """Catch silent overwrite of a manually reviewed canonical mass."""
        project, state = fixture()
        result = systems.summary(project, state)
        self.assertEqual(len(result["update_proposals"]), 1)
        proposal = result["update_proposals"][0]
        self.assertEqual(proposal["item_id"], "armour")
        self.assertEqual(proposal["current_mass_t"], 60.0)
        self.assertEqual(proposal["proposed_mass_t"], 39.25)
        self.assertTrue(proposal["requires_review"])
        self.assertEqual(result["systems"]["armament"]["ledger_mass_t"], 100.0)
        self.assertTrue(any(d["code"] == "systems.mass_mismatch" for d in result["diagnostics"]))

    def test_installed_count_drives_mass_while_broadside_remains_output(self):
        """Catch using broadside count for installation or ammunition mass."""
        project, state = fixture()
        row = systems.summary(project, state)["systems"]["armament"]
        self.assertEqual(row["installed_count"], 10)
        self.assertEqual(row["broadside_count"], 5)
        count_model = next(model for model in row["mass_models"] if model["id"] == "ammunition-count-check")
        self.assertEqual(count_model["calculated_mass_t"], 40.0)
        self.assertEqual(count_model["difference_t"], 0.0)

    def test_broadside_count_is_rejected_as_a_mass_multiplier(self):
        """Catch weapon-side presentation counts entering the weight ledger."""
        project, state = fixture()
        model = project["systems"]["armament"]["mass_models"][0]
        model["inputs"]["count_field"] = "broadside_count"
        with self.assertRaisesRegex(ValueError, "never a broadside count"):
            systems.summary(project, state)

    def test_absent_system_is_not_invented_zero_performance(self):
        """Catch converting an explicit system absence into fake numeric capability."""
        project, state = fixture()
        row = systems.summary(project, state)["systems"]["aviation"]
        self.assertEqual(row["status"], "absent")
        self.assertEqual(row["reason"], "fixture declares no aviation system")
        self.assertIsNone(row["ledger_mass_t"])

    def test_duplicate_or_unknown_weight_item_links_block_completeness(self):
        """Catch shared ownership and misspelled ledger IDs."""
        project, state = fixture()
        project["systems"]["auxiliary"] = {
            "status": "present", "weight_item_ids": ["engine", "missing"],
            "source": "bad fixture", "estimate": True,
        }
        result = systems.summary(project, state)
        self.assertFalse(result["complete"])
        codes = {diagnostic["code"] for diagnostic in result["diagnostics"] if diagnostic["blocking"]}
        self.assertIn("systems.weight_item_shared", codes)
        self.assertIn("systems.weight_item_unknown", codes)
        self.assertIsNone(result["values"]["linked_total_mass_t"])

    def test_unknown_linked_mass_remains_unknown(self):
        """Catch replacing a missing effective mass with zero."""
        project, state = fixture()
        next(item for item in state["effective_items"] if item["id"] == "engine")["mass_t"] = None
        result = systems.summary(project, state)
        self.assertIsNone(result["systems"]["propulsion"]["ledger_mass_t"])
        self.assertIsNone(result["values"]["linked_total_mass_t"])
        self.assertTrue(any(d["code"] == "systems.weight_mass_unknown" for d in result["diagnostics"]))

    def test_loading_identity_and_item_provenance_survive(self):
        """Catch disconnecting a system result from its selected loading state."""
        project, state = fixture()
        result = systems.summary(project, state)
        self.assertEqual(result["condition_id"], "normal")
        self.assertEqual(result["project_fingerprint"], "project-fingerprint")
        self.assertEqual(result["input_fingerprint"], "loading-fingerprint")
        linked = result["systems"]["propulsion"]["linked_items"][0]
        self.assertEqual(linked["provenance"], {"source": "ledger engine", "estimate": False})
        self.assertEqual(result["systems"]["propulsion"]["source"], "analytic propulsion fixture")

    def test_loading_ownership_failure_remains_blocking(self):
        """Catch presenting systems as complete over an invalid loading ledger."""
        project, state = fixture()
        state["complete_mass"] = False
        state["diagnostics"] = [{
            "code": "loading.ownership_overlap", "severity": "error", "path": "$.weight_groups",
            "message": "shared mount armour", "blocking": True,
        }]
        result = systems.summary(project, state)
        self.assertFalse(result["complete"])
        self.assertEqual(result["loading_diagnostics"], state["diagnostics"])
        self.assertTrue(any(d["code"] == "systems.loading_incomplete" for d in result["diagnostics"]))

    def test_invalid_formula_inputs_reject_bool_and_nonfinite(self):
        """Catch malformed physical inputs producing plausible-looking proposals."""
        project, state = fixture()
        model = project["systems"]["propulsion"]["mass_models"][0]
        for value in (True, float("inf")):
            model["inputs"]["volume_m3"] = value
            with self.assertRaises(ValueError, msg=value):
                systems.summary(project, state)

    def test_empty_systems_is_unknown_not_complete_absence(self):
        """Catch presenting an undeclared systems inventory as complete."""
        project, state = fixture()
        project["systems"] = {}
        result = systems.summary(project, state)
        self.assertFalse(result["complete"])
        self.assertTrue(any(d["code"] == "systems.none_declared" for d in result["diagnostics"]))


class CanonicalCaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(PKG, "cases", "projects", "queen_mary_1913.project.json")
        with open(path, encoding="utf-8") as handle:
            cls.project = project_io.normalize_project(json.load(handle))
        cls.state = loading.resolve_loading(cls.project, "normal-engineering")
        cls.result = systems.summary(cls.project, cls.state)

    def test_stable_task3_ids_link_to_selected_normal_loading(self):
        """Catch adapters that expect a different systems schema or stale IDs."""
        self.assertTrue(self.result["complete"])
        self.assertEqual(self.result["input_fingerprint"], self.state["input_fingerprint"])
        self.assertEqual(
            [item["id"] for item in self.result["systems"]["weapons.main"]["linked_items"]],
            ["main-guns", "main-mounts", "main-ammunition"],
        )
        self.assertEqual(
            [item["id"] for item in self.result["systems"]["propulsion"]["linked_items"]],
            ["boilers-uptakes", "turbines-shafting"],
        )

    def test_installed_and_broadside_counts_stay_distinct(self):
        """Catch using the eight-gun broadside as the sixteen-gun installation."""
        secondary = self.result["systems"]["weapons.secondary"]
        self.assertEqual(secondary["installed_count"], 16)
        self.assertEqual(secondary["broadside_count"], 8)
        ammunition = next(item for item in secondary["linked_items"] if item["id"] == "secondary-ammunition")
        self.assertEqual(ammunition["mass_t"], 43.948848224531254)

    def test_mount_armour_and_ammunition_are_counted_once(self):
        """Catch adding rotating armour or ammunition outside their ledger rows."""
        main = self.result["systems"]["weapons.main"]
        mount = next(item for item in main["linked_items"] if item["id"] == "main-mounts")
        self.assertIn("armour.main-turret.rotating", mount["includes"])
        linked_ids = [
            item["id"]
            for row in self.result["systems"].values()
            for item in row["linked_items"]
        ]
        self.assertEqual(linked_ids.count("main-mounts"), 1)
        self.assertEqual(linked_ids.count("main-ammunition"), 1)

    def test_canonical_physical_input_change_proposes_without_rewriting_loading(self):
        """Catch interactive armour edits silently replacing the selected ledger mass."""
        project = copy.deepcopy(self.project)
        state = copy.deepcopy(self.state)
        before = copy.deepcopy(state)
        armour = project["systems"]["armour"]["fixed"]
        model = armour["mass_models"][0]
        linked_id = model["linked_weight_item_id"]
        original_mass = next(
            item["mass_t"] for item in state["effective_items"] if item["id"] == linked_id
        )
        model["inputs"]["area_m2"] *= 2.0

        result = systems.summary(project, state)

        proposal = next(
            item for item in result["update_proposals"]
            if item["source_model_id"] == model["id"]
        )
        self.assertEqual(proposal["current_mass_t"], original_mass)
        self.assertNotEqual(proposal["proposed_mass_t"], original_mass)
        self.assertTrue(proposal["requires_review"])
        self.assertEqual(state, before)
        linked = next(
            item for item in result["systems"]["armour.fixed"]["linked_items"]
            if item["id"] == linked_id
        )
        self.assertEqual(linked["mass_t"], original_mass)
        self.assertTrue(any(
            diagnostic["code"] == "systems.mass_mismatch"
            and model["id"] in diagnostic["message"]
            for diagnostic in result["diagnostics"]
        ))

    def test_canonical_weapon_formulas_reproduce_ledger_and_armour_rounding_is_disclosed(self):
        """Catch rounded weapon inputs or hidden legacy armour discrepancies."""
        weapon_rows = (
            self.result["systems"]["weapons.main"],
            self.result["systems"]["weapons.secondary"],
        )
        weapon_models = [model for row in weapon_rows for model in row["mass_models"]]
        self.assertEqual(len(weapon_models), 6)
        for model in weapon_models:
            self.assertLessEqual(abs(model["difference_t"]), model["comparison_tolerance_t"])

        armour = self.result["systems"]["armour.fixed"]
        self.assertEqual(len(armour["mass_models"]), 13)
        proposals = [
            proposal for proposal in self.result["update_proposals"]
            if proposal["source_system_id"] == "armour.fixed"
        ]
        self.assertEqual(len(proposals), 13)
        self.assertTrue(all(proposal["requires_review"] for proposal in proposals))
        self.assertEqual(
            self.state["values"]["total_mass_t"],
            27851.62934079477,
        )


if __name__ == "__main__":
    unittest.main()
