# -*- coding: utf-8 -*-
"""Three-axis canonical loading synthesis tests."""

from __future__ import annotations

import copy
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))

import loading  # noqa: E402
import project_io  # noqa: E402


def analytic_project() -> dict:
    """Return the independent two-item loading fixture from the Task 2 contract."""
    project = project_io.new_project("Analytic Loading Ship", "analytic-loading-ship")
    project["hull"] = {"lwl_m": 100.0, "beam_m": 15.0, "draught_m": 6.0}
    project["geometry"] = {
        "kind": "parameters",
        "source": "analytic fixture",
        "estimate": False,
        "keel_offset_m": 0.0,
        "parameters": {"block_coeff": 0.7},
    }
    project["weight_groups"] = [
        {
            "id": "lightship",
            "label": "Lightship",
            "required": True,
            "items": [
                {
                    "id": "first",
                    "mass_t": 100.0,
                    "x_m": -10.0,
                    "y_m": -2.0,
                    "kg_m": 4.0,
                    "source": "analytic fixture A",
                    "estimate": False,
                },
                {
                    "id": "second",
                    "mass_t": 300.0,
                    "x_m": 10.0,
                    "y_m": 2.0,
                    "kg_m": 8.0,
                    "source": "analytic fixture B",
                    "estimate": False,
                },
            ],
        }
    ]
    project["loading_conditions"] = [
        {
            "id": "normal",
            "label": "Normal",
            "reference_displacement_t": 400.0,
            "overrides": {},
        },
        {
            "id": "light",
            "label": "Light",
            "reference_displacement_t": 200.0,
            "overrides": {"second": {"mass_t": 100.0}},
        },
    ]
    return project


class TestAnalyticSynthesis(unittest.TestCase):
    """Verify exact mass, moments, CG, overrides, and result identity."""

    def test_three_axis_mass_moments_and_cg_match_independent_anchor(self):
        result = loading.resolve_loading(analytic_project(), "normal")

        self.assertEqual(result["schema"], "plimsoll-loading-1")
        self.assertEqual(result["values"]["known_mass_t"], 400.0)
        self.assertEqual(result["values"]["total_mass_t"], 400.0)
        self.assertEqual(
            result["values"]["known_moments_t_m"],
            {"x": 2000.0, "y": 400.0, "z": 2800.0},
        )
        self.assertEqual(
            result["values"]["moments_t_m"],
            {"x": 2000.0, "y": 400.0, "z": 2800.0},
        )
        self.assertTrue(
            math.isclose(result["values"]["lcg_m"], 5.0, rel_tol=1e-10)
        )
        self.assertTrue(
            math.isclose(result["values"]["tcg_m"], 1.0, rel_tol=1e-10)
        )
        self.assertTrue(
            math.isclose(result["values"]["kg_m"], 7.0, rel_tol=1e-10)
        )
        self.assertTrue(result["complete_mass"])
        self.assertTrue(result["complete_cg"])
        self.assertEqual(result["axis_complete"], {"x": True, "y": True, "z": True})

    def test_override_changes_only_present_field_without_mutating_project(self):
        project = analytic_project()
        before = copy.deepcopy(project)

        normal = loading.resolve_loading(project, "normal")
        light = loading.resolve_loading(project, "light")

        self.assertEqual(project, before)
        self.assertEqual(light["values"]["total_mass_t"], 200.0)
        self.assertEqual(
            light["values"]["moments_t_m"], {"x": 0.0, "y": 0.0, "z": 1200.0}
        )
        self.assertEqual(
            (light["values"]["lcg_m"], light["values"]["tcg_m"], light["values"]["kg_m"]),
            (0.0, 0.0, 6.0),
        )
        second = next(item for item in light["effective_items"] if item["id"] == "second")
        self.assertEqual(second["mass_t"], 100.0)
        self.assertEqual(second["x_m"], 10.0)
        self.assertEqual(second["overridden_fields"], ["mass_t"])
        self.assertEqual(normal["project_fingerprint"], light["project_fingerprint"])
        self.assertNotEqual(normal["input_fingerprint"], light["input_fingerprint"])


class TestCompletenessAndOwnership(unittest.TestCase):
    """Catch unknown-as-zero, partial-CG, missing-group, and double-counting errors."""

    def test_unknown_mass_blocks_total_while_explicit_zero_is_consumable(self):
        unknown_project = analytic_project()
        unknown_project["weight_groups"][0]["items"][1]["mass_t"] = None
        unknown = loading.resolve_loading(unknown_project, "normal")
        self.assertEqual(unknown["values"]["known_mass_t"], 100.0)
        self.assertIsNone(unknown["values"]["total_mass_t"])
        self.assertEqual(
            unknown["values"]["known_moments_t_m"],
            {"x": -1000.0, "y": -200.0, "z": 400.0},
        )
        self.assertEqual(unknown["values"]["moments_t_m"], {"x": None, "y": None, "z": None})
        self.assertFalse(unknown["complete_mass"])
        self.assertFalse(unknown["complete_cg"])

        zero_project = analytic_project()
        zero_item = zero_project["weight_groups"][0]["items"][1]
        zero_item.update({"mass_t": 0.0, "x_m": None, "y_m": None, "kg_m": None})
        zero = loading.resolve_loading(zero_project, "normal")
        self.assertEqual(zero["values"]["total_mass_t"], 100.0)
        self.assertEqual(zero["values"]["moments_t_m"], {"x": -1000.0, "y": -200.0, "z": 400.0})
        self.assertEqual(
            (zero["values"]["lcg_m"], zero["values"]["tcg_m"], zero["values"]["kg_m"]),
            (-10.0, -2.0, 4.0),
        )
        self.assertTrue(zero["complete_cg"])

    def test_literal_null_and_zero_overrides_do_not_inherit_base_values(self):
        project = analytic_project()
        project["loading_conditions"].extend(
            [
                {
                    "id": "unknown-second",
                    "label": "Unknown second",
                    "reference_displacement_t": None,
                    "overrides": {"second": {"mass_t": None}},
                },
                {
                    "id": "zero-second",
                    "label": "Zero second",
                    "reference_displacement_t": 100.0,
                    "overrides": {"second": {"mass_t": 0.0}},
                },
            ]
        )
        self.assertIsNone(
            loading.resolve_loading(project, "unknown-second")["values"]["total_mass_t"]
        )
        zero = loading.resolve_loading(project, "zero-second")
        self.assertEqual(zero["values"]["total_mass_t"], 100.0)
        self.assertEqual(zero["values"]["kg_m"], 4.0)

    def test_missing_one_axis_exposes_only_supported_axis_cgs(self):
        project = analytic_project()
        project["weight_groups"][0]["items"][0]["x_m"] = None
        result = loading.resolve_loading(project, "normal")
        self.assertEqual(result["values"]["total_mass_t"], 400.0)
        self.assertEqual(result["axis_complete"], {"x": False, "y": True, "z": True})
        self.assertEqual(result["values"]["known_moments_t_m"]["x"], 3000.0)
        self.assertIsNone(result["values"]["moments_t_m"]["x"])
        self.assertIsNone(result["values"]["lcg_m"])
        self.assertEqual(result["values"]["tcg_m"], 1.0)
        self.assertEqual(result["values"]["kg_m"], 7.0)
        self.assertTrue(result["complete_mass"])
        self.assertFalse(result["complete_cg"])

    def test_empty_required_group_refuses_total_even_at_99_percent_reference(self):
        project = analytic_project()
        project["weight_groups"].append(
            {"id": "machinery", "label": "Machinery", "required": True, "items": []}
        )
        project["loading_conditions"][0]["reference_displacement_t"] = 400.0 / 0.99
        result = loading.resolve_loading(project, "normal")
        self.assertEqual(result["values"]["known_mass_t"], 400.0)
        self.assertIsNone(result["values"]["total_mass_t"])
        self.assertFalse(result["complete_mass"])
        self.assertFalse(result["complete_cg"])
        self.assertIsNone(result["coverage"]["ratio"])
        self.assertTrue(
            any(d["code"] == "loading.required_group_empty" and d["blocking"] for d in result["diagnostics"])
        )

    def test_required_group_with_explicit_zero_item_is_not_missing(self):
        project = analytic_project()
        project["weight_groups"].append(
            {
                "id": "stores",
                "label": "Stores",
                "required": True,
                "items": [
                    {
                        "id": "empty-tank",
                        "mass_t": 0.0,
                        "x_m": None,
                        "y_m": None,
                        "kg_m": None,
                        "source": "declared empty",
                        "estimate": False,
                    }
                ],
            }
        )
        result = loading.resolve_loading(project, "normal")
        self.assertTrue(result["complete_mass"])
        self.assertTrue(result["complete_cg"])

    def test_active_inclusion_overlap_blocks_cg_and_zero_override_removes_it(self):
        project = analytic_project()
        first, second = project["weight_groups"][0]["items"]
        first["id"] = "turretA"
        first["includes"] = ["gunA"]
        second["id"] = "gunA"
        project["loading_conditions"][1]["overrides"] = {"gunA": {"mass_t": 0.0}}

        overlapping = loading.resolve_loading(project, "normal")
        collision = next(
            diagnostic
            for diagnostic in overlapping["diagnostics"]
            if diagnostic["code"] == "loading.ownership_overlap"
        )
        self.assertTrue(collision["blocking"])
        self.assertEqual(collision["severity"], "error")
        self.assertFalse(overlapping["complete_mass"])
        self.assertFalse(overlapping["complete_cg"])
        self.assertIsNone(overlapping["values"]["lcg_m"])

        resolved = loading.resolve_loading(project, "light")
        self.assertTrue(resolved["complete_mass"])
        self.assertTrue(resolved["complete_cg"])
        self.assertEqual(resolved["values"]["total_mass_t"], 100.0)


class TestCoverageAndValidation(unittest.TestCase):
    """Verify reference coverage remains diagnostic and malformed input fails upstream."""

    def test_reference_coverage_reports_under_over_and_absent_without_mass_plug(self):
        under_project = analytic_project()
        under_project["loading_conditions"][0]["reference_displacement_t"] = 1000.0
        under = loading.resolve_loading(under_project, "normal")
        self.assertEqual(under["coverage"]["ratio"], 0.4)
        self.assertEqual(under["coverage"]["unallocated_mass_t"], 600.0)
        self.assertTrue(any(d["code"] == "loading.coverage_low" for d in under["diagnostics"]))
        self.assertEqual(under["values"]["total_mass_t"], 400.0)

        over_project = analytic_project()
        over_project["loading_conditions"][0]["reference_displacement_t"] = 100.0
        over = loading.resolve_loading(over_project, "normal")
        self.assertEqual(over["coverage"]["ratio"], 4.0)
        self.assertEqual(over["coverage"]["unallocated_mass_t"], -300.0)
        self.assertTrue(any(d["code"] == "loading.coverage_high" for d in over["diagnostics"]))

        absent_project = analytic_project()
        absent_project["loading_conditions"][0]["reference_displacement_t"] = None
        absent = loading.resolve_loading(absent_project, "normal")
        self.assertEqual(
            absent["coverage"],
            {"reference_displacement_t": None, "ratio": None, "percent": None, "unallocated_mass_t": None},
        )

    def test_missing_condition_and_malformed_projects_fail_explicitly(self):
        with self.assertRaises(loading.LoadingConditionError):
            loading.resolve_loading(analytic_project(), "missing")

        invalid_projects = []
        duplicate = analytic_project()
        duplicate["weight_groups"][0]["items"][1]["id"] = "first"
        invalid_projects.append(duplicate)
        malformed_interval = analytic_project()
        malformed_interval["weight_groups"][0]["items"][0]["uncertainty"] = {
            "mass_t": [110.0, 90.0]
        }
        invalid_projects.append(malformed_interval)
        unknown_target = analytic_project()
        unknown_target["loading_conditions"][0]["overrides"] = {
            "absent": {"mass_t": 1.0}
        }
        invalid_projects.append(unknown_target)

        for project in invalid_projects:
            with self.subTest(project=project), self.assertRaises(project_io.ProjectValidationError):
                loading.resolve_loading(project, "normal")


class TestUncertaintyAndProvenance(unittest.TestCase):
    """Verify conservative intervals and tri-state provenance survive synthesis."""

    def test_signed_interval_arithmetic_matches_independent_anchor(self):
        project = analytic_project()
        first, second = project["weight_groups"][0]["items"]
        first.update(
            {
                "mass_t": 100.0,
                "x_m": -1.5,
                "uncertainty": {"mass_t": [90.0, 110.0], "x_m": [-2.0, -1.0]},
            }
        )
        second.update({"mass_t": 100.0, "x_m": 2.0})
        result = loading.resolve_loading(project, "normal")

        uncertainty = result["uncertainty"]
        self.assertEqual(uncertainty["kind"], "conservative_engineering_interval")
        self.assertFalse(uncertainty["is_confidence_interval"])
        self.assertEqual(uncertainty["total_mass_t"], [190.0, 210.0])
        self.assertEqual(uncertainty["moments_t_m"]["x"], [-20.0, 110.0])
        expected = [-20.0 / 190.0, 110.0 / 190.0]
        for actual, wanted in zip(uncertainty["cg_m"]["x"], expected):
            self.assertTrue(math.isclose(actual, wanted, rel_tol=1e-10, abs_tol=1e-10))
        self.assertTrue(uncertainty["certified"])

    def test_override_clears_inherited_interval_and_discloses_update_needed(self):
        project = analytic_project()
        project["weight_groups"][0]["items"][1]["uncertainty"] = {
            "mass_t": [250.0, 350.0]
        }
        result = loading.resolve_loading(project, "light")
        second = next(item for item in result["effective_items"] if item["id"] == "second")
        self.assertNotIn("mass_t", second.get("uncertainty", {}))
        self.assertTrue(
            any(
                d["code"] == "loading.uncertainty_override_cleared"
                and d["path"] == '$.loading_conditions[1].overrides["second"].mass_t'
                for d in result["diagnostics"]
            )
        )
        self.assertIn(
            "$.weight_groups[0].items[1].mass_t",
            result["uncertainty"]["conditional_on_nominal_fields"],
        )

    def test_estimated_item_without_bounds_is_diagnostic(self):
        project = analytic_project()
        project["weight_groups"][0]["items"][0]["estimate"] = True
        result = loading.resolve_loading(project, "normal")
        self.assertEqual(
            result["uncertainty"]["missing_estimate_bounds"],
            [{"item_id": "first", "fields": ["kg_m", "mass_t", "x_m", "y_m"]}],
        )
        self.assertTrue(
            any(d["code"] == "loading.estimated_without_uncertainty" for d in result["diagnostics"])
        )

    def test_unknown_mass_prevents_full_uncertainty_certification(self):
        project = analytic_project()
        project["weight_groups"][0]["items"][0]["mass_t"] = None
        result = loading.resolve_loading(project, "normal")
        self.assertIsNone(result["uncertainty"]["total_mass_t"])
        self.assertEqual(result["uncertainty"]["cg_m"], {"x": None, "y": None, "z": None})
        self.assertFalse(result["uncertainty"]["certified"])

    def test_provenance_summary_keeps_unknown_distinct_from_false(self):
        project = analytic_project()
        first, second = project["weight_groups"][0]["items"]
        first["estimate"] = False
        second["estimate"] = None
        second["source"] = None
        result = loading.resolve_loading(project, "normal")

        self.assertEqual(
            result["provenance"]["estimate_counts"],
            {"estimated": 0, "confirmed_non_estimated": 1, "unknown": 1},
        )
        self.assertEqual(result["provenance"]["source_missing_item_ids"], ["second"])
        self.assertEqual(result["provenance"]["unverified_item_ids"], ["second"])
        self.assertFalse(result["provenance"]["provenance_complete"])
        effective_second = next(
            item for item in result["effective_items"] if item["id"] == "second"
        )
        self.assertIsNone(effective_second["provenance"]["estimate"])


if __name__ == "__main__":
    unittest.main()
