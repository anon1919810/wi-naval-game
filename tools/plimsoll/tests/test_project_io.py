# -*- coding: utf-8 -*-
"""Canonical project, units, diagnostics, migration, and fingerprint tests."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))

import project_io  # noqa: E402
import project_store  # noqa: E402
import units  # noqa: E402


def populated_project() -> dict:
    """Return a small generic project with one item and one condition."""
    project = project_io.new_project("Analytic Test Ship", "analytic-test-ship")
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
                    "id": "structure",
                    "mass_t": 1000.0,
                    "x_m": 1.0,
                    "y_m": 0.0,
                    "kg_m": 5.0,
                    "source": "analytic fixture",
                    "estimate": False,
                }
            ],
        }
    ]
    project["loading_conditions"] = [
        {
            "id": "normal",
            "label": "Normal",
            "reference_displacement_t": 1000.0,
            "overrides": {},
        }
    ]
    return project


class TestUnits(unittest.TestCase):
    """Exercise exact definitions and dimension checking."""

    def test_exact_mass_definitions(self):
        self.assertEqual(units.convert(1, "long_ton", "t"), 1.0160469088)
        self.assertEqual(units.convert(1000, "kg", "t"), 1.0)

    def test_length_power_speed_and_angle_definitions(self):
        self.assertAlmostEqual(units.convert(1, "ft", "m"), 0.3048)
        self.assertAlmostEqual(units.convert(1, "shp", "kW"), 0.7456998715822702)
        self.assertAlmostEqual(units.convert(1, "kn", "m_s"), 1852 / 3600)
        self.assertAlmostEqual(units.convert(180, "deg", "rad"), math.pi)

    def test_round_trip_conversion(self):
        for value, first, second in (
            (123.4, "t", "kg"),
            (37.0, "m", "ft"),
            (21.0, "kn", "m_s"),
            (15000.0, "kW", "shp"),
            (47.0, "deg", "rad"),
        ):
            self.assertTrue(
                math.isclose(
                    units.convert(units.convert(value, first, second), second, first),
                    value,
                    rel_tol=1e-10,
                    abs_tol=1e-10,
                )
            )

    def test_rejects_cross_dimension_unknown_and_nonfinite_inputs(self):
        for args in (
            (1.0, "m", "t"),
            (1.0, "bogus", "m"),
            (True, "m", "ft"),
            (math.nan, "m", "ft"),
            (math.inf, "m", "ft"),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                units.convert(*args)


class TestProjectDefaultsAndValidation(unittest.TestCase):
    """Verify draft defaults and structured validation diagnostics."""

    def test_new_project_is_editable_draft_with_canonical_defaults(self):
        project = project_io.new_project("Test Ship", "test-ship")
        self.assertEqual(project["schema"], "plimsoll-project-1")
        self.assertEqual(project["id"], "test-ship")
        self.assertEqual(project["revision"], 0)
        self.assertEqual(
            project["units"],
            {"length": "m", "mass": "t", "speed": "kn", "power": "kW", "angle": "deg"},
        )
        self.assertEqual(
            project["coordinates"],
            {
                "x_positive": "forward",
                "x_origin": "midships",
                "y_positive": "starboard",
                "z_origin": "keel",
            },
        )
        self.assertIsNone(project["geometry"])
        diagnostics = project_io.validate_project(project)
        self.assertTrue(any(d["code"] == "draft.hull_incomplete" for d in diagnostics))
        self.assertFalse(any(d["severity"] == "error" for d in diagnostics))

    def test_zero_is_known_while_null_is_unknown(self):
        project = populated_project()
        item = project["weight_groups"][0]["items"][0]
        item.update({"mass_t": 0, "x_m": 0, "y_m": None, "kg_m": 0, "source": None})
        diagnostics = project_io.validate_project(project)
        unknown_paths = {d["path"] for d in diagnostics if d["code"] == "value.unknown"}
        self.assertEqual(unknown_paths, {"$.weight_groups[0].items[0].y_m"})
        self.assertTrue(any(d["code"] == "source.missing" for d in diagnostics))
        self.assertFalse(any(d["severity"] == "error" for d in diagnostics))

    def test_unknown_hull_and_loading_values_have_diagnostics(self):
        project = populated_project()
        project["hull"]["beam_m"] = None
        project["loading_conditions"][0]["reference_displacement_t"] = None
        unknown_paths = {
            d["path"] for d in project_io.validate_project(project) if d["code"] == "value.unknown"
        }
        self.assertIn("$.hull.beam_m", unknown_paths)
        self.assertIn("$.loading_conditions[0].reference_displacement_t", unknown_paths)

    def test_malformed_hull_key_returns_diagnostic_instead_of_crashing(self):
        project = populated_project()
        project["hull"] = {1: 2}
        diagnostics = project_io.validate_project(project)
        self.assertTrue(any(d["code"] == "json.key_invalid" for d in diagnostics))
        with self.assertRaises(project_io.ProjectValidationError) as caught:
            project_io.normalize_project(project)
        self.assertTrue(any(d["code"] == "json.key_invalid" for d in caught.exception.diagnostics))

    def test_missing_or_null_estimate_is_unknown_not_confirmed_false(self):
        missing = populated_project()
        del missing["weight_groups"][0]["items"][0]["estimate"]
        explicit_unknown = copy.deepcopy(missing)
        explicit_unknown["weight_groups"][0]["items"][0]["estimate"] = None
        confirmed = copy.deepcopy(missing)
        confirmed["weight_groups"][0]["items"][0]["estimate"] = False

        normalized = project_io.normalize_project(missing)
        self.assertIsNone(normalized["weight_groups"][0]["items"][0]["estimate"])
        self.assertTrue(
            any(d["code"] == "estimate.unknown" for d in project_io.validate_project(missing))
        )
        self.assertEqual(
            project_io.input_fingerprint(missing),
            project_io.input_fingerprint(explicit_unknown),
        )
        self.assertNotEqual(
            project_io.input_fingerprint(missing),
            project_io.input_fingerprint(confirmed),
        )

    def test_geometry_kinds_require_matching_nonempty_structural_payloads(self):
        invalid_geometry = (
            {
                "kind": "offsets_reference",
                "reference": {},
            },
            {
                "kind": "offsets_reference",
                "reference": {"path": ""},
            },
            {
                "kind": "parameters",
                "parameters": {},
            },
            {
                "kind": "offsets",
                "offsets": {"stations": []},
            },
            {
                "kind": "parameters",
                "reference": {"path": "ship.json"},
            },
            {
                "kind": "future_geometry",
                "parameters": {"block_coeff": 0.7},
            },
        )
        for geometry in invalid_geometry:
            project = populated_project()
            project["geometry"] = {
                "source": "test fixture",
                "estimate": False,
                "keel_offset_m": 0.0,
                **geometry,
            }
            with self.subTest(geometry=geometry):
                self.assertTrue(
                    any(
                        d["code"].startswith("geometry.") and d["severity"] == "error"
                        for d in project_io.validate_project(project)
                    )
                )

    def test_geometry_kinds_accept_minimum_valid_structural_payloads(self):
        valid_geometry = (
            {"kind": "offsets_reference", "reference": {"path": "ship.json"}},
            {"kind": "parameters", "parameters": {"block_coeff": 0.7}},
            {"kind": "offsets", "offsets": {"stations": [{"x_m": 0.0}]}},
        )
        for geometry in valid_geometry:
            project = populated_project()
            project["geometry"] = {
                "source": "test fixture",
                "estimate": False,
                "keel_offset_m": 0.0,
                **geometry,
            }
            with self.subTest(geometry=geometry):
                self.assertFalse(
                    any(d["severity"] == "error" for d in project_io.validate_project(project))
                )

    def test_duplicate_group_item_and_loading_ids_are_errors(self):
        cases = []
        duplicate_group = populated_project()
        duplicate_group["weight_groups"].append(copy.deepcopy(duplicate_group["weight_groups"][0]))
        cases.append(duplicate_group)
        duplicate_item = populated_project()
        duplicate_item["weight_groups"].append(
            {
                "id": "stores",
                "label": "Stores",
                "required": False,
                "items": [copy.deepcopy(duplicate_item["weight_groups"][0]["items"][0])],
            }
        )
        cases.append(duplicate_item)
        duplicate_loading = populated_project()
        duplicate_loading["loading_conditions"].append(
            copy.deepcopy(duplicate_loading["loading_conditions"][0])
        )
        cases.append(duplicate_loading)

        for project in cases:
            with self.subTest(project=project), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(project)

    def test_override_rejects_unknown_item_and_unknown_fields(self):
        project = populated_project()
        project["loading_conditions"][0]["overrides"] = {
            "missing": {"mass_t": 1.0},
            "structure": {"source": "not an override field"},
        }
        diagnostics = project_io.validate_project(project)
        self.assertEqual(
            {d["code"] for d in diagnostics if d["severity"] == "error"},
            {"override.item_unknown", "override.field_unknown"},
        )

    def test_numeric_fields_reject_booleans_negative_bounds_and_nonfinite_values(self):
        patches = (
            ("mass_t", True),
            ("mass_t", -1),
            ("x_m", math.nan),
            ("y_m", math.inf),
            ("kg_m", -0.1),
        )
        for field, value in patches:
            project = populated_project()
            project["weight_groups"][0]["items"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(
                project_io.ProjectValidationError
            ):
                project_io.normalize_project(project)

    def test_uncertainty_bounds_are_finite_dimensioned_and_contain_nominal(self):
        project = populated_project()
        project["weight_groups"][0]["items"][0]["uncertainty"] = {
            "mass_t": [900.0, 1100.0],
            "x_m": [-1.0, 2.0],
            "y_m": [-0.5, 0.5],
            "kg_m": [4.5, 5.5],
        }
        self.assertFalse(any(d["severity"] == "error" for d in project_io.validate_project(project)))

        bad = copy.deepcopy(project)
        bad["weight_groups"][0]["items"][0]["uncertainty"]["mass_t"] = [-1.0, 999.0]
        codes = {d["code"] for d in project_io.validate_project(bad) if d["severity"] == "error"}
        self.assertEqual(codes, {"uncertainty.dimension", "uncertainty.nominal_outside"})

    def test_includes_are_component_tokens_not_nested_mass(self):
        project = populated_project()
        item = project["weight_groups"][0]["items"][0]
        item["includes"] = ["hull.shell", "hull.framing"]
        self.assertFalse(any(d["severity"] == "error" for d in project_io.validate_project(project)))
        item["includes"] = ["hull.shell", {"mass_t": 2}]
        self.assertTrue(
            any(d["code"] == "includes.token_invalid" for d in project_io.validate_project(project))
        )

    def test_normalize_deep_copies_and_only_supplies_schema_defaults(self):
        payload = {
            "schema": "plimsoll-project-1",
            "id": "draft",
            "name": "Draft",
            "hull": {"beam_m": None},
        }
        original = copy.deepcopy(payload)
        normalized = project_io.normalize_project(payload)
        self.assertEqual(payload, original)
        self.assertEqual(normalized["hull"], {"beam_m": None})
        self.assertEqual(normalized["revision"], 0)
        self.assertEqual(normalized["weight_groups"], [])
        normalized["hull"]["beam_m"] = 20
        self.assertIsNone(payload["hull"]["beam_m"])

    def test_unsupported_schema_and_reserved_result_fields_are_rejected(self):
        for patch in (
            {"schema": "plimsoll-project-2"},
            {"result": {"stability": "cached"}},
            {"input_fingerprint": "self-referential"},
        ):
            project = populated_project()
            project.update(patch)
            with self.subTest(patch=patch), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(project)

    def test_missing_schema_is_rejected(self):
        project = populated_project()
        del project["schema"]
        diagnostics = project_io.validate_project(project)
        self.assertTrue(any(
            d["code"] == "schema.missing" and d["severity"] == "error"
            for d in diagnostics
        ))
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project(project)

    def test_missing_schema_rejected_end_to_end_on_load(self):
        project = populated_project()
        del project["schema"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no_schema.json"
            path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(project_io.ProjectValidationError):
                project_store.load(path)


class TestMigrationAndFingerprint(unittest.TestCase):
    """Verify lossless legacy retention and canonical hashing."""

    def test_migration_preserves_inputs_converts_known_units_and_marks_unknown_axes(self):
        ship = {
            "schema": "plimsoll-ship-1",
            "name": "Legacy Ship",
            "units": "SI",
            "hull": {
                "lwl_m": 150.0,
                "beam_m": 20.0,
                "displacement_normal_t": 10000.0,
                "displacement_deep_t": 12000.0,
                "displacement_unit": "long_ton",
                "offsets_path": "legacy_offsets.json",
                "sources": {"displacement_normal_t": "archive A"},
            },
        }
        weights = {
            "schema": "plimsoll-weights-1",
            "datum": "keel",
            "groups": [
                {
                    "id": "machinery",
                    "label": "Machinery",
                    "items": [
                        {
                            "id": "engines",
                            "mass_t": 500.0,
                            "kg_m": 4.0,
                            "source": "builder return",
                            "estimate": False,
                            "_legacy_note": "verbatim metadata",
                        }
                    ],
                }
            ],
        }

        project = project_io.migrate_legacy(ship, weights)

        self.assertEqual(project["legacy_inputs"], {"ship": ship, "weights": weights})
        self.assertEqual(project["hull"]["displacement_normal_t"], 10160.469088)
        conditions = {condition["id"]: condition for condition in project["loading_conditions"]}
        self.assertEqual(conditions["normal"]["reference_displacement_t"], 10160.469088)
        self.assertEqual(conditions["deep"]["reference_displacement_t"], 12192.5629056)
        item = project["weight_groups"][0]["items"][0]
        self.assertIsNone(item["x_m"])
        self.assertIsNone(item["y_m"])
        self.assertEqual(item["source"], "builder return")
        self.assertEqual(project["geometry"]["reference"], {"path": "legacy_offsets.json"})
        unknown_paths = {
            d["path"] for d in project_io.validate_project(project) if d["code"] == "value.unknown"
        }
        self.assertIn("$.weight_groups[0].items[0].x_m", unknown_paths)
        self.assertIn("$.weight_groups[0].items[0].y_m", unknown_paths)

    def test_unconfirmed_legacy_tonnes_are_estimated_without_fabricating_load_difference(self):
        ship = {
            "schema": "plimsoll-ship-1",
            "name": "Unconfirmed Ship",
            "hull": {"displacement_normal_t": 9000.0},
        }
        project = project_io.migrate_legacy(ship)
        conditions = {condition["id"]: condition for condition in project["loading_conditions"]}
        self.assertEqual(conditions["normal"]["reference_displacement_t"], 9000.0)
        self.assertIsNone(conditions["deep"]["reference_displacement_t"])
        self.assertTrue(project["sources"]["migration"]["mass_unit_estimated"])
        self.assertEqual(project["weight_groups"], [])

    def test_fingerprint_is_order_independent_but_input_sensitive(self):
        project = populated_project()
        reordered = {key: project[key] for key in reversed(project)}
        reordered["units"] = {key: project["units"][key] for key in reversed(project["units"])}
        self.assertEqual(
            project_io.input_fingerprint(project), project_io.input_fingerprint(reordered)
        )

        changed = copy.deepcopy(project)
        changed["weight_groups"][0]["items"][0]["x_m"] = 1.0001
        self.assertNotEqual(
            project_io.input_fingerprint(project), project_io.input_fingerprint(changed)
        )


if __name__ == "__main__":
    unittest.main()
