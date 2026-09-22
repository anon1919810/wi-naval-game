# -*- coding: utf-8 -*-
"""Canonical project fixtures are complete, standalone, and reproducible."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
CASES = PKG / "cases" / "projects"
GENERATOR = PKG / "tools" / "gen_project_cases.py"
sys.path.insert(0, os.fspath(PKG))

import geometry  # noqa: E402
import loading  # noqa: E402
import project_io  # noqa: E402


FILENAMES = (
    "queen_mary_1913.project.json",
    "generic_steamer.project.json",
    "analytic_box.project.json",
)
GROUP_IDS = {
    "hull",
    "armour",
    "armament",
    "machinery",
    "outfit",
    "ammunition",
    "fuel",
    "water",
    "other_loads",
}


def _load(name: str) -> dict:
    with (CASES / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def _stationed_hull(project: dict) -> geometry.StationedHull:
    stations = [
        (row[0], [tuple(point) for point in row[1]])
        for row in project["geometry"]["offsets"]["stations"]
    ]
    return geometry.StationedHull(stations, name=project["name"])


class ProjectCaseTests(unittest.TestCase):
    def test_all_committed_cases_normalize_and_resolve_every_loading(self):
        """Catches malformed fixtures and loading overrides that bypass the real pipeline."""
        for filename in FILENAMES:
            with self.subTest(filename=filename):
                project = project_io.normalize_project(_load(filename))
                self.assertEqual(set(group["id"] for group in project["weight_groups"]), GROUP_IDS)
                self.assertEqual(project["geometry"]["kind"], "offsets")
                self.assertEqual(
                    project["geometry"]["offsets"]["schema"],
                    "plimsoll-section-polygons-1",
                )
                self.assertNotIn("path", project["geometry"]["offsets"])
                for condition in project["loading_conditions"]:
                    state = loading.resolve_loading(project, condition["id"])
                    self.assertIsNotNone(state["values"]["total_mass_t"])
                    self.assertTrue(state["complete_mass"])
                    self.assertTrue(state["complete_cg"])

    def test_generator_is_byte_deterministic_and_matches_committed_cases(self):
        """Catches timestamps, platform-dependent ordering, and stale generated fixtures."""
        self.assertTrue(GENERATOR.is_file(), "canonical project generator is missing")
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            for output in (first, second):
                completed = subprocess.run(
                    [sys.executable, "-B", os.fspath(GENERATOR), "--output-dir", output],
                    cwd=PKG,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
            for filename in FILENAMES:
                expected = (CASES / filename).read_bytes()
                self.assertEqual((Path(first) / filename).read_bytes(), expected)
                self.assertEqual((Path(second) / filename).read_bytes(), expected)

    def test_queen_mary_ledger_uses_independent_formulas_without_residual_mass(self):
        """Catches displacement fitting and unit/broadside errors in the historical fixture."""
        project = project_io.normalize_project(_load(FILENAMES[0]))
        items = {
            item["id"]: item
            for group in project["weight_groups"]
            for item in group["items"]
        }
        long_ton = 1.0160469088
        lb_to_t = 0.45359237 / 1000.0
        expected_fixed = sum(
            (
                0.35 * 27_000 * long_ton,
                6820.701,
                8 * 167_776 * lb_to_t,
                4 * 600 * long_ton,
                16 * 42 * 112 * lb_to_t,
                16.0,
                50.0,
                75_000 / 15 * long_ton,
                0.03 * 27_000 * long_ton,
                8 * 80 * (1400 + 297) * lb_to_t,
                16 * 150 * (31 + 9 + (5 + 15 / 16) / 16) * lb_to_t,
                12.0,
            )
        )
        variable_ids = {
            "coal",
            "fuel-oil",
            "reserve-feed-water",
            "potable-water",
            "provisions-stores",
            "crew-effects",
        }
        actual_fixed = sum(item["mass_t"] for item in items.values() if item["id"] not in variable_ids)
        self.assertTrue(math.isclose(actual_fixed, expected_fixed, rel_tol=1e-10))
        normal = loading.resolve_loading(project, "normal-engineering")
        deep = loading.resolve_loading(project, "deep-engineering")
        self.assertTrue(math.isclose(normal["values"]["total_mass_t"], 27851.629342730772, rel_tol=1e-10))
        self.assertTrue(math.isclose(deep["values"]["total_mass_t"], 31926.26234273077, rel_tol=1e-10))
        self.assertIsNone(project["loading_conditions"][0]["reference_displacement_t"])
        self.assertIsNone(project["loading_conditions"][1]["reference_displacement_t"])
        self.assertNotIn("residual", " ".join(items).lower())

        armour = next(group for group in project["weight_groups"] if group["id"] == "armour")
        ownership = [token for item in armour["items"] for token in item["includes"]]
        self.assertEqual(len(ownership), len(set(ownership)))
        main_mounts = items["main-mounts"]
        self.assertIn("armour.main-turret.rotating", main_mounts["includes"])
        self.assertFalse(any("turret" in token for token in ownership))
        self.assertEqual(project["systems"]["weapons"]["secondary"]["broadside_guns"], 8)

    def test_every_inferred_queen_mary_item_discloses_bounds_and_dependencies(self):
        """Catches unsupported point estimates and model positions presented as measurements."""
        project = _load(FILENAMES[0])
        for group in project["weight_groups"]:
            self.assertGreater(len(group["items"]), 0, group["id"])
            for item in group["items"]:
                if item["estimate"]:
                    self.assertIsInstance(item["source"], dict, item["id"])
                    self.assertTrue(item["source"].get("formula"), item["id"])
                    self.assertTrue(item["source"].get("citation"), item["id"])
                    self.assertTrue(item["source"].get("dependencies"), item["id"])
                    self.assertEqual(
                        set(item["uncertainty"]),
                        {"mass_t", "x_m", "y_m", "kg_m"},
                        item["id"],
                    )
        self.assertFalse(project["sources"]["historical_validation"]["validated"])
        self.assertEqual(project["sources"]["comparisons"][0]["raw_value"], 26770)
        self.assertEqual(project["sources"]["comparisons"][0]["raw_unit"], "tons (unresolved)")

    def test_serialized_geometry_has_direct_analytic_volume_anchors(self):
        """Catches wrong station coordinates, datum shifts, and parameter materialization errors."""
        box = _load(FILENAMES[2])
        self.assertEqual(box["geometry"]["keel_offset_m"], 0.0)
        box_result = _stationed_hull(box).integrate(0.0, 4.0)
        self.assertTrue(math.isclose(box_result["volume"], 800.0, rel_tol=1e-10))
        self.assertTrue(math.isclose(box_result["xlcb"], 0.0, abs_tol=1e-10))
        self.assertTrue(math.isclose(box_result["yb"], 0.0, abs_tol=1e-10))

        steamer = _load(FILENAMES[1])
        target = 0.72 * 90.0 * 13.0 * 5.5
        steamer_result = _stationed_hull(steamer).integrate(0.0, 5.5)
        self.assertLess(abs(steamer_result["volume"] - target) / target, 0.01)
        self.assertEqual(steamer["geometry"]["source"]["method"], "parameter-derived reference geometry")

        queen_mary = _load(FILENAMES[0])
        self.assertEqual(queen_mary["geometry"]["keel_offset_m"], -9.9)
        self.assertGreaterEqual(len(queen_mary["geometry"]["offsets"]["stations"]), 121)

    def test_compartments_and_openings_are_explicit_engineering_fixtures(self):
        """Catches incomplete proxy geometry and surveyed-data claims for modeled subdivisions."""
        numeric = {
            "length_m",
            "beam_m",
            "height_m",
            "x_m",
            "y_m",
            "keel_to_bottom_m",
            "permeability",
        }
        for filename in FILENAMES:
            project = _load(filename)
            compartment_ids = {item["id"] for item in project["compartments"]}
            self.assertTrue(compartment_ids)
            for compartment in project["compartments"]:
                self.assertTrue(numeric <= compartment.keys())
                self.assertIn("free_surface", compartment)
                self.assertTrue(compartment["estimate"])
                self.assertIn("engineering fixture", compartment["source"].lower())
            for opening in project["openings"]:
                self.assertTrue({"id", "label", "kind", "x_m", "y_m", "z_m", "open", "source", "estimate"} <= opening.keys())
                self.assertTrue(opening["estimate"])
                if opening["kind"] == "connection":
                    self.assertNotEqual(opening["from"], opening["to"])
                    self.assertTrue({opening["from"], opening["to"]} <= compartment_ids | {"sea"})
                    self.assertIn("area_m2", opening)
                    self.assertIn("discharge_coefficient", opening)

    def test_intact_damage_presets_state_zero_initial_water(self):
        """Catches implicit dry-state assumptions or flood water encoded as solid weight."""
        for filename in FILENAMES:
            project = _load(filename)
            compartments = {item["id"] for item in project["compartments"]}
            self.assertTrue("damage_presets" in project, filename)
            preset = next(item for item in project["damage_presets"] if item["id"] == "intact")
            self.assertEqual(set(preset["initial_water_volumes_m3"]), compartments)
            self.assertTrue(all(volume == 0.0 for volume in preset["initial_water_volumes_m3"].values()))
            self.assertEqual(preset["opening_overrides"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
