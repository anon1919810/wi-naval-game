"""Independent behavioural checks for the new game aftermath/core bridge."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
META = {"source": "explicit synthetic gameplay fixture", "estimate": True}


def inputs():
    project = json.loads((ROOT / "cases/projects/generic_flooding_box.project.json").read_text(encoding="utf-8"))
    project["compartments"] = [{"id": "engine-room", "label": "Engine room", "length_m": 4,
        "beam_m": 3, "height_m": 2.5, "x_m": 0, "y_m": 2.5, "keel_to_bottom_m": 0,
        "permeability": .8, "free_surface": True, **META}]
    box = {"center_m": [0, 2.5, 1.25], "size_m": [1, 1, 1]}
    experiment = {"schema": "plimsoll-damage-lab-experiment-1", **META,
        "duration_s": 0, "time_step_s": .5, "initial_water_m3": {"engine-room": 0},
        "modules": [{"id": "engine", "label": "Engine", "role": "engine", "compartment_id": "engine-room",
            "box": box, "weight_item_ids": [], "required_staff": 6, "initial_integrity": 1,
            "nominal_shaft_power_kw": 500, **META}],
        "crew_groups": [{"id": "watch", "label": "Engine watch", "compartment_id": "engine-room",
            "module_id": "engine", "station_box": copy.deepcopy(box), "personnel": 10, **META}],
        "impact": {"position_m": [0, 2.5, 1.25], "severity": 1, "radius_m": 2, **META},
        "breaches": [], "remaining_gz_angles_deg": [0, 10],
        "rules": {"casualty_fraction": .4, "fatal_fraction": .25,
            "module_flood_threshold": .5, "evacuate_fill_fraction": .3, **META}}
    return project, experiment


class DamageLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.available = importlib.util.find_spec("tools.plimsoll.damage_lab") is not None

    def setUp(self):
        self.assertTrue(self.available, "new damage_lab API has not been implemented")
        self.lab = importlib.import_module("tools.plimsoll.damage_lab")
        self.project, self.experiment = inputs()

    def run_case(self, **kwargs):
        return self.lab.run_experiment(self.project, "normal", self.experiment, **kwargs)

    def test_known_casualty_counts_and_no_double_count(self):
        result = self.run_case()
        crew = result["final_state"]["crew_groups"][0]
        self.assertEqual([crew[k] for k in ("available", "incapacitated", "dead", "evacuated")], [6, 3, 1, 0])
        self.assertEqual(result["final_state"]["modules"][0]["effective_availability"], 0)
        self.assertEqual(result["status"], "completed")

    def test_zero_impact_keeps_mass_and_dry_state(self):
        self.experiment["impact"]["severity"] = 0
        result = self.run_case()
        self.assertEqual(result["final_state"]["modules"][0]["effective_availability"], 1)
        self.assertEqual(result["final_state"]["crew_groups"][0]["available"], 10)
        native = result["core_analysis"]["stages"]["flooding"]["data"]
        self.assertEqual(native["final_state"]["total_onboard_water_mass_t"], 0)
        self.assertEqual(result["input_snapshot"]["weight_groups"], self.project["weight_groups"])

    def test_availability_product_and_unknown_staff(self):
        self.experiment["impact"]["severity"] = 0
        self.experiment["modules"][0]["initial_integrity"] = .5
        self.experiment["crew_groups"][0]["personnel"] = 3
        self.assertEqual(self.run_case()["final_state"]["modules"][0]["effective_availability"], .25)
        self.experiment["crew_groups"][0]["personnel"] = None
        state = self.run_case()["final_state"]
        self.assertIsNone(state["modules"][0]["effective_availability"])
        self.assertIsNone(state["crew_groups"][0]["dead"])
        self.assertIsNone(state["capabilities"]["shaft_power_kw"])

    def test_real_breach_uses_native_water_and_accepted_times(self):
        self.experiment.update(duration_s=2)
        self.experiment["breaches"] = [{"id": "hole", "from_id": "sea", "to_id": "engine-room",
            "position_m": [0, 4, .2], "area_m2": .1, "discharge_coefficient": .6, **META}]
        result = self.run_case()
        native = result["core_analysis"]["stages"]["flooding"]["data"]
        self.assertGreater(native["final_state"]["total_onboard_water_mass_t"], 0)
        projected = result["final_state"]["ship"]
        self.assertEqual(projected["total_onboard_water_mass_t"], native["final_state"]["total_onboard_water_mass_t"])
        self.assertEqual(projected["equilibrium"], native["final_state"]["equilibrium"])
        times = [row["time_s"] for row in native["timeline"]]
        self.assertTrue(all(b > a for a, b in zip(times, times[1:])))
        self.assertLess(abs(native["final_state"]["mass_conservation_error_t"]), 1e-8)

    def test_identity_and_inputs_are_frozen(self):
        before = copy.deepcopy((self.project, self.experiment))
        first = self.run_case()
        _, _, fingerprint = self.lab.normalize_request(self.project, "normal", self.experiment)
        self.assertEqual(first["request_fingerprint"], fingerprint)
        self.assertEqual((self.project, self.experiment), before)
        replay = self.lab.run_experiment(first["input_snapshot"], "normal", first["request"]["experiment"])
        self.assertEqual(first["request_fingerprint"], replay["request_fingerprint"])
        self.assertEqual(first["final_state"], replay["final_state"])
        self.experiment["impact"]["severity"] = .5
        self.assertNotEqual(self.lab.normalize_request(self.project, "normal", self.experiment)[2], fingerprint)

    def test_simultaneous_events_have_distinct_indices(self):
        result = self.run_case()
        self.assertGreater(len(result["events"]), 1)
        indices = [row["index"] for row in result["events"]]
        self.assertEqual(indices, list(range(len(indices))))
        self.assertEqual(result["snapshots"][0]["event_index"], -1)
        self.assertEqual(result["snapshots"][0]["crew_groups"][0]["available"], 10)
        self.assertEqual(result["snapshots"][-1]["event_index"], indices[-1])

    def test_invalid_contracts_fail_before_calculation(self):
        mutations = [
            lambda e: e["impact"].update(severity=True),
            lambda e: e["impact"].update(radius_m=-1),
            lambda e: e["impact"].update(severity=float("nan")),
            lambda e: e["crew_groups"][0].update(personnel=-1),
            lambda e: e["crew_groups"][0].update(module_id=["engine", "other"]),
            lambda e: e["modules"][0]["box"].update(size_m=[-1, 1, 1]),
            lambda e: e["modules"].append(copy.deepcopy(e["modules"][0])),
            lambda e: e["modules"][0].update(compartment_id="foreign"),
            lambda e: e["modules"][0].update(source=""),
            lambda e: e.update(unrecognised=True),
            lambda e: e.update(duration_s=61),
            lambda e: e.update(duration_s=60, time_step_s=.0001),
            lambda e: e["crew_groups"][0]["station_box"].update(center_m=[0, -4, 1]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(self.experiment)
                mutation(candidate)
                with self.assertRaises(ValueError) as caught:
                    self.lab.normalize_request(self.project, "normal", candidate)
                self.assertTrue(caught.exception.diagnostics)

    def test_off_face_breach_is_rejected(self):
        self.experiment["breaches"] = [{"id": "bad-hole", "from_id": "sea", "to_id": "engine-room",
            "position_m": [0, 2.5, 1], "area_m2": .1, "discharge_coefficient": .6, **META}]
        with self.assertRaises(ValueError):
            self.lab.normalize_request(self.project, "normal", self.experiment)

    def test_cancel_is_not_success(self):
        self.assertEqual(self.run_case(cancel_check=lambda: True)["status"], "canceled")

    def test_internal_breach_requires_opposing_shared_faces(self):
        room = copy.deepcopy(self.project["compartments"][0])
        room["id"] = "overlapping-room"
        self.project["compartments"].append(room)
        self.experiment["initial_water_m3"][room["id"]] = 0
        self.experiment["breaches"] = [{"id": "bulkhead-hole", "from_id": "engine-room",
            "to_id": room["id"], "position_m": [0, 4, 1], "area_m2": .1,
            "discharge_coefficient": .6, **META}]
        with self.assertRaises(ValueError):
            self.lab.normalize_request(self.project, "normal", self.experiment)

    def test_flood_evacuation_conserves_injured_crew_and_staffing(self):
        self.experiment["impact"]["severity"] = .5
        self.experiment["initial_water_m3"]["engine-room"] = 10
        self.experiment["rules"].update(evacuate_fill_fraction=.3, module_flood_threshold=.9)
        result = self.run_case()
        crew = result["final_state"]["crew_groups"][0]
        self.assertEqual([crew[k] for k in ("available", "incapacitated", "dead", "evacuated")], [0, 2, 0, 8])
        self.assertEqual(crew["evacuated_location"], "abstract-assembly")
        self.assertEqual(crew["casualty_location"], "engine-room")
        self.assertEqual(result["final_state"]["modules"][0]["effective_availability"], 0)

    def test_partial_retains_last_accepted_state_and_stop(self):
        native = self.run_case()["core_analysis"]
        native["status"] = "partial"
        native["stages"]["flooding"]["status"] = "model_limit"
        native["stages"]["flooding"]["reason"] = "synthetic early-stop boundary"
        self.experiment["duration_s"] = 60
        with patch.object(importlib.import_module("tools.plimsoll.damage_lab.coordinator").analysis,
                          "compute_project", return_value=native):
            result = self.run_case()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["simulated_duration_s"], 0)
        self.assertEqual(result["core_analysis"]["stages"]["flooding"]["reason"], "synthetic early-stop boundary")

    def test_omitted_nullable_inputs_are_unknown_and_can_execute(self):
        self.experiment["impact"]["severity"] = 0
        for collection, key in (("modules", "nominal_shaft_power_kw"),
                                ("crew_groups", "personnel"), ("crew_groups", "module_id")):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.experiment)
                del candidate[collection][0][key]
                _, request, _ = self.lab.normalize_request(self.project, "normal", candidate)
                self.assertIsNone(request["experiment"][collection][0][key])
                result = self.lab.run_experiment(self.project, "normal", candidate)
                self.assertEqual(result["status"], "completed")
                if key == "personnel":
                    self.assertIsNone(result["final_state"]["crew_groups"][0]["dead"])
                if key == "nominal_shaft_power_kw":
                    self.assertIsNone(result["final_state"]["capabilities"]["shaft_power_kw"])
                self.assertNotIn(key, candidate[collection][0])

    def test_incomplete_canonical_rooms_have_admission_diagnostics(self):
        for key in ("length_m", "beam_m", "height_m", "x_m", "y_m", "keel_to_bottom_m",
                    "permeability", "source", "estimate"):
            with self.subTest(key=key):
                project = copy.deepcopy(self.project)
                del project["compartments"][0][key]
                for admission in (lambda: self.lab.default_experiment(project),
                                  lambda: self.lab.normalize_request(project, "normal", self.experiment)):
                    with self.assertRaises(self.lab.LabInputError) as caught:
                        admission()
                    self.assertTrue(caught.exception.diagnostics[0]["path"].endswith("." + key))

    def test_invalid_room_geometry_and_metadata_are_rejected(self):
        for key, value in (("length_m", 0), ("height_m", -1), ("beam_m", True),
                           ("x_m", "0"), ("permeability", 1.1), ("permeability", True),
                           ("source", ""), ("estimate", "yes"), ("label", [])):
            with self.subTest(key=key, value=value):
                project = copy.deepcopy(self.project)
                project["compartments"][0][key] = value
                with self.assertRaises(self.lab.LabInputError) as caught:
                    self.lab.normalize_request(project, "normal", self.experiment)
                self.assertTrue(caught.exception.diagnostics[0]["path"].endswith("." + key))

    def test_full_native_tank_has_no_internal_free_surface(self):
        self.experiment["impact"]["severity"] = 0
        self.experiment["initial_water_m3"]["engine-room"] = 24
        result = self.run_case()
        tank = result["final_state"]["ship"]["tanks"][0]
        self.assertEqual(tank["fill_fraction"], 1)
        self.assertIsNone(tank["plane_offset_m"])
        self.assertGreater(tank["volume_m3"], 0)


if __name__ == "__main__":
    unittest.main()
