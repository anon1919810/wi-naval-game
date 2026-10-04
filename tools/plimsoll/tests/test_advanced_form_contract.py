"""Optional `flooding_scenarios` storage contract for the advanced input forms.

Phase 1 of the advanced-workflow plan adds one optional project field: saved
flooding scenario drafts. These focused tests pin the storage contract only —
structure, references and numeric domains — and prove that saving a draft runs no
numerical solve, keeps unknown values unknown, does not create a second mass
authority, and leaves older projects without the field readable.
"""

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flooding
import loading
import project_io


def project():
    return {
        "schema": "plimsoll-project-1", "id": "advanced-forms", "name": "Advanced forms fixture",
        "hull": {"lwl_m": 88.0, "beam_m": 12.0, "depth_m": 8.0},
        "weight_groups": [{"id": "structure", "items": [
            {"id": "hull-plate", "mass_t": 120.0, "x_m": 0.0, "y_m": 0.0, "kg_m": 4.0,
             "source": "declared survey", "estimate": False}]}],
        "loading_conditions": [{"id": "normal", "overrides": {}}],
        "systems": {}, "compartments": [], "opening_definition": "supplied", "openings": [],
    }


def sea(density=1.025):
    return {"id": "sea", "fluid_density_t_m3": density, "source": "declared sea", "estimate": False}


def tank(**overrides):
    row = {"id": "room", "length_m": 10.0, "beam_m": 6.0, "height_m": 3.0, "x_m": 1.0, "y_m": 0.0,
           "keel_to_bottom_m": 0.5, "permeability": 0.9, "free_surface": True,
           "fluid_density_t_m3": 1.025, "initial_volume_m3": 0.0,
           "source": "declared compartment", "estimate": False}
    row.update(overrides)
    return row


def connection(**overrides):
    row = {"id": "sea-hole", "from": "sea", "to": "room", "x_m": 0.0, "y_m": 0.0, "z_m": 0.2,
           "area_m2": 0.05, "discharge_coefficient": 0.6, "fluid_density_t_m3": 1.025,
           "open": True, "source": "declared aperture", "estimate": False}
    row.update(overrides)
    return row


def scenario(**overrides):
    row = {"schema": "plimsoll-flooding-scenario-1", "id": "flooding_1", "label": "Single hole",
           "duration_s": 60.0, "time_step_s": 0.5, "source": "declared damage case", "estimate": False,
           "sea": sea(), "tanks": [tank()], "connections": [connection()]}
    row.update(overrides)
    return row


def with_scenarios(*scenarios):
    base = project()
    base["flooding_scenarios"] = list(scenarios)
    return base


def blocking(diagnostics):
    return [(item["path"], item["message"]) for item in diagnostics
            if item.get("severity") == "error"]


class SavedScenarioStorageTests(unittest.TestCase):
    def test_project_compartment_identity_is_unique_and_nonempty(self):
        for identities in (("room", "room"), ("",), (None,)):
            with self.subTest(identities=identities):
                base = project()
                base["compartments"] = [{"id": identity} for identity in identities]
                self.assertTrue(blocking(project_io.validate_project(base)))

    def test_a_complete_draft_saves_and_reopens_unchanged(self):
        raw = with_scenarios(scenario())
        before = copy.deepcopy(raw)
        normalized = project_io.normalize_project(raw)
        self.assertEqual(normalized["flooding_scenarios"][0]["id"], "flooding_1")
        self.assertEqual(normalized["flooding_scenarios"][0]["connections"][0]["discharge_coefficient"], 0.6)
        # Normalization never rewrites the caller's payload.
        self.assertEqual(raw, before)

    def test_unknown_values_stay_unknown_and_save_as_an_incomplete_draft(self):
        raw = with_scenarios(scenario(duration_s=60.0, time_step_s=None,
                                      tanks=[tank(initial_volume_m3=None, source=None, estimate=None)],
                                      connections=[connection(area_m2=None)]))
        normalized = project_io.normalize_project(raw)
        draft = normalized["flooding_scenarios"][0]
        self.assertIsNone(draft["time_step_s"])
        self.assertIsNone(draft["tanks"][0]["initial_volume_m3"])
        self.assertIsNone(draft["tanks"][0]["source"])
        self.assertIsNone(draft["connections"][0]["area_m2"])
        warnings = {item["code"] for item in project_io.validate_project(normalized)}
        self.assertIn("extension.value_unknown", warnings)
        # An incomplete draft stays out of the run: the kernel still refuses it.
        result = flooding.simulate_flooding(normalized, "normal", draft)
        self.assertEqual(result["status"], "invalid_input")
        self.assertEqual(result["timeline"], [])

    def test_saving_a_draft_performs_no_numerical_solve(self):
        base = project()
        without = loading.resolve_loading(project_io.normalize_project(base), "normal")
        raw = with_scenarios(scenario())
        normalized = project_io.normalize_project(raw)
        after = loading.resolve_loading(normalized, "normal")
        # No solver ran and no mass moved: the ledger stays the only mass authority.
        # The identity changes because the project input genuinely changed, but no
        # mass, centre of gravity or completeness flag may follow from a draft.
        self.assertNotEqual(after["input_fingerprint"], without["input_fingerprint"])
        self.assertEqual(after["complete_mass"], without["complete_mass"])
        self.assertEqual(after["values"], without["values"])
        self.assertEqual(after["groups"], without["groups"])
        self.assertEqual([(item["id"], item["mass_t"], item["x_m"], item["kg_m"])
                          for item in after["effective_items"]],
                         [(item["id"], item["mass_t"], item["x_m"], item["kg_m"])
                          for item in without["effective_items"]])

    def test_tank_ids_may_not_collide_with_ledger_items_or_the_sea_node(self):
        for label, tank_id in (("ledger", "hull-plate"), ("sea", "sea")):
            with self.subTest(label), self.assertRaises(project_io.ProjectValidationError) as raised:
                project_io.normalize_project(with_scenarios(scenario(tanks=[tank(id=tank_id)])))
            paths = {item["path"] for item in raised.exception.diagnostics}
            self.assertIn("$.flooding_scenarios[0].tanks[0].id", paths)

    def test_dangling_and_self_referencing_edges_are_refused(self):
        for label, edge in (("dangling", connection(to="ghost")), ("self", connection(to="sea"))):
            with self.subTest(label), self.assertRaises(project_io.ProjectValidationError) as raised:
                project_io.normalize_project(with_scenarios(scenario(connections=[edge])))
            paths = {item["path"] for item in raised.exception.diagnostics}
            self.assertTrue(paths & {"$.flooding_scenarios[0].connections[0].to",
                                     "$.flooding_scenarios[0].connections[0]"})

    def test_duplicate_scenario_tank_and_connection_ids_are_refused(self):
        cases = {
            "$.flooding_scenarios[1].id": with_scenarios(scenario(), copy.deepcopy(scenario())),
            "$.flooding_scenarios[0].tanks[1].id": with_scenarios(
                scenario(tanks=[tank(), tank(id="room")])),
            "$.flooding_scenarios[0].connections[1].id": with_scenarios(
                scenario(connections=[connection(), connection()])),
        }
        for expected, raw in cases.items():
            with self.subTest(expected), self.assertRaises(project_io.ProjectValidationError) as raised:
                project_io.normalize_project(raw)
            self.assertIn(expected, {item["path"] for item in raised.exception.diagnostics})

    def test_numeric_domains_and_optional_shapes_are_checked(self):
        cases = [
            scenario(time_step_s=0.0),
            scenario(duration_s=-1.0),
            scenario(tanks=[tank(permeability=1.5)]),
            scenario(tanks=[tank(height_m=0.0)]),
            scenario(tanks=[tank(permeability=True)]),
            scenario(connections=[connection(area_m2=-0.1)]),
            scenario(connections=[connection(discharge_coefficient=1.2)]),
            scenario(connections=[connection(open="yes")]),
            scenario(connections=[connection(free_surface=True)]),
            scenario(connections=[connection(aperture_height_m=0.0)]),
            scenario(schema="plimsoll-project-1"),
            scenario(pressures=[1]),
        ]
        for raw in cases:
            with self.subTest(schema=raw.get("schema")), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(with_scenarios(raw))

    def test_supported_optional_shapes_are_accepted(self):
        for openings in (None, [], [{"id": "vent", "open": True, "x_m": 0.0, "y_m": 0.0, "z_m": 5.0,
                                     "source": "ventilation plan", "estimate": True}]):
            with self.subTest(openings=openings):
                normalized = project_io.normalize_project(with_scenarios(scenario(openings=openings)))
                self.assertEqual(normalized["flooding_scenarios"][0]["openings"], openings)
        # A finite aperture check is optional and only needs a positive height.
        normalized = project_io.normalize_project(
            with_scenarios(scenario(connections=[connection(aperture_height_m=0.9)])))
        self.assertEqual(normalized["flooding_scenarios"][0]["connections"][0]["aperture_height_m"], 0.9)

    def test_provenance_is_preserved_and_pressure_fields_are_unsupported(self):
        structured = scenario()
        structured["sea"]["source"] = {"kind": "declared_density", "note": "textbook"}
        normalized = project_io.normalize_project(with_scenarios(structured))
        self.assertEqual(normalized["flooding_scenarios"][0]["sea"]["source"]["note"], "textbook")
        for field in ("pressure_pa", "from_pressure_pa", "air_pressure_pa"):
            with self.subTest(field), self.assertRaises(project_io.ProjectValidationError) as raised:
                project_io.normalize_project(
                    with_scenarios(scenario(connections=[connection(**{field: 1.0})])))
            self.assertIn(f'$.flooding_scenarios[0].connections[0]["{field}"]',
                          {item["path"] for item in raised.exception.diagnostics})

    def test_projects_without_the_field_are_unchanged(self):
        normalized = project_io.normalize_project(project())
        self.assertNotIn("flooding_scenarios", normalized)
        # The field is a list of drafts; a non-list is refused rather than ignored.
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project({**project(), "flooding_scenarios": {}})


if __name__ == "__main__":
    unittest.main()
