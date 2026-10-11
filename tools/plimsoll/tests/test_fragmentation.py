"""Focused checks for the deterministic game-fragment/core bridge."""
import copy
import unittest
from unittest.mock import patch

from tools.plimsoll.damage_lab import LabInputError, normalize_request, run_experiment
from tools.plimsoll.tests.test_damage_lab import META, inputs


def fixture():
    project, experiment = inputs()
    other = copy.deepcopy(project["compartments"][0])
    other.update(id="other-room", x_m=4)
    project["compartments"].append(other)
    module = copy.deepcopy(experiment["modules"][0])
    module.update(id="other-engine", compartment_id="other-room", required_staff=0)
    module["box"]["center_m"][0] = 3
    experiment["modules"].append(module)
    experiment["initial_water_m3"]["other-room"] = 0
    experiment["impact"]["radius_m"] = 8
    experiment["detonation"] = dict(position_m=[0, 2.5, 1.25], fragment_count=128, seed=42,
        boundaries=[], **META)
    return project, experiment


def boundary(to_id="other-room", transmission=0):
    return dict(id="wall", from_id="engine-room", to_id=to_id,
        position_m=[2, 2.5, 1.25] if to_id != "sea" else [0, 4, 1.25],
        transmission=transmission, breach_threshold=1, max_breach_area_m2=0,
        discharge_coefficient=.6, **META)


class FragmentationTests(unittest.TestCase):
    def trace(self, project, experiment):
        from tools.plimsoll.damage_lab.fragmentation import trace_fragments
        project, request, _ = normalize_request(project, "normal", experiment)
        return trace_fragments(project, request["experiment"])

    def test_closed_wall_shields_and_transmission_reduces_target_exposure(self):
        project, experiment = fixture()
        closed = self.trace(project, experiment)
        self.assertEqual(closed["module_exposure"]["other-engine"], 0)
        experiment["detonation"]["boundaries"] = [boundary(transmission=1)]
        opened = self.trace(project, experiment)
        experiment["detonation"]["boundaries"][0]["transmission"] = .25
        reduced = self.trace(project, experiment)
        self.assertGreater(opened["module_exposure"]["other-engine"], 0)
        self.assertAlmostEqual(reduced["module_exposure"]["other-engine"],
                               opened["module_exposure"]["other-engine"] * .25)
        self.assertTrue(any(t["termination"] == "sealed_boundary" for t in closed["traces"]))

    def test_seed_reproduces_and_zero_budget_has_no_effect(self):
        project, experiment = fixture()
        first = self.trace(project, experiment)
        self.assertEqual(first, self.trace(project, experiment))
        experiment["detonation"]["seed"] = 43
        self.assertNotEqual(first["traces"], self.trace(project, experiment)["traces"])
        for field in ("severity", "radius_m"):
            candidate = copy.deepcopy(experiment)
            candidate["impact"][field] = 0
            report = self.trace(project, candidate)
            self.assertFalse(report["generated_breaches"])
            self.assertTrue(all(v == 0 for v in report["module_exposure"].values()))

    def test_bad_origins_geometry_and_duplicate_water_links_are_rejected(self):
        project, experiment = fixture()
        for key, value in (("position_m", [2, 2.5, 1.25]), ("fragment_count", True), ("seed", -1)):
            candidate = copy.deepcopy(experiment)
            candidate["detonation"][key] = value
            with self.subTest(key=key), self.assertRaises(LabInputError):
                normalize_request(project, "normal", candidate)
        overlap = copy.deepcopy(project)
        overlap["compartments"][1]["x_m"] = 1
        with self.assertRaises(LabInputError):
            normalize_request(overlap, "normal", experiment)
        wall = boundary("sea")
        wall.update(breach_threshold=0, max_breach_area_m2=.4)
        experiment["detonation"]["boundaries"] = [wall]
        experiment["breaches"] = [dict(id="manual", from_id="sea", to_id="engine-room",
            position_m=wall["position_m"], area_m2=.2, discharge_coefficient=.6, **META)]
        with self.assertRaises(LabInputError):
            normalize_request(project, "normal", experiment)

    def test_generated_breach_enters_native_core_once_and_input_is_frozen(self):
        project, experiment = fixture()
        experiment["duration_s"] = 2
        wall = boundary("sea")
        wall.update(breach_threshold=0, max_breach_area_m2=.4)
        experiment["detonation"]["boundaries"] = [wall]
        original = copy.deepcopy(experiment)
        from tools.plimsoll import analysis
        with patch('tools.plimsoll.damage_lab.coordinator.analysis.compute_project', wraps=analysis.compute_project) as calculate:
            result = run_experiment(project, "normal", experiment)
        native_links = calculate.call_args.args[2]['flooding']['scenario']['connections']
        self.assertEqual(len(native_links), 1)
        generated = result["fragmentation"]["generated_breaches"]
        self.assertEqual(len(generated), 1)
        self.assertEqual(native_links[0]['id'], generated[0]['id'])
        self.assertGreater(generated[0]["area_m2"], 0)
        self.assertEqual(result["applied_breaches"], generated)
        self.assertEqual(experiment, original)
        self.assertEqual(result["events"][0]["kind"], "detonation")
        self.assertGreater(result["final_state"]["ship"]["total_onboard_water_volume_m3"], 0)
        self.assertEqual(result["final_state"]["modules"][1]["mechanical_integrity"], 1)

    def test_canceled_trace_does_not_apply_partial_damage_or_holes(self):
        project, experiment = fixture()
        result = run_experiment(project, "normal", experiment, cancel_check=lambda: True)
        self.assertEqual(result["status"], "canceled")
        self.assertTrue(result["fragmentation"]["canceled"])
        self.assertEqual(result["final_state"]["modules"][0]["mechanical_integrity"], 1)
        self.assertFalse(result["fragmentation"]["generated_breaches"])
        self.assertFalse(result["events"])


if __name__ == "__main__":
    unittest.main()
