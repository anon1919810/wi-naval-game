"""The canonical knowledge marker survives into real damage and remaining GZ."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis
import project_store

CASES = Path(__file__).resolve().parents[1] / "cases" / "projects"


def inputs():
    project = json.loads((CASES / "generic_flooding_box.project.json").read_text(encoding="utf-8"))
    scenario = json.loads((CASES / "damage-presets.json").read_text(encoding="utf-8"))["presets"][0]["scenario"]
    scenario.pop("openings")
    scenario["duration_s"] = 0
    return project, scenario


class FloodingCoordinatorTests(unittest.TestCase):
    def test_unknown_and_declared_none_survive_store_into_remaining_gz(self):
        fingerprints = []
        for marker in ("unknown", "legacy_ambiguous", "supplied"):
            project, scenario = inputs()
            project["opening_definition"] = marker
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "进水开口.json"
                project_store.save(path, project)
                reopened = project_store.load(path)
            options = dict(stages=["flooding"], flooding=dict(scenario=scenario,
                options=dict(remaining_gz_angles_deg=[0])))
            result = analysis.compute_project(reopened, "normal", options)
            self.assertEqual(result["stages"]["flooding"]["status"], "completed")
            native = result["stages"]["flooding"]["data"]
            self.assertEqual(native["loading"]["input_fingerprint"], result["input_fingerprint"])
            self.assertNotEqual(native["input_fingerprint"], result["input_fingerprint"])
            self.assertEqual(native["coordinator_openings_origin"], marker)
            self.assertIs(native["remaining_gz"]["rows"][0]["validity"]["intact_valid"], True if marker == "supplied" else None)
            replay = analysis.compute_project(reopened, "normal", result["request"]["options"])
            self.assertEqual(replay["request_fingerprint"], result["request_fingerprint"])
            fingerprints.append(result["request_fingerprint"])
        self.assertEqual(len(set(fingerprints)), 3)

    def test_canceled_native_timeline_keeps_convergence_and_stop_reason(self):
        project, scenario = inputs()
        scenario["duration_s"] = .5
        count = [0]
        def cancel():
            count[0] += 1
            return count[0] > 3
        result = analysis.compute_project(project, "normal", dict(stages=["flooding"],
            flooding=dict(scenario=scenario)), cancel_check=cancel)
        stage = result["stages"]["flooding"]
        self.assertEqual(result["status"], "canceled")
        self.assertEqual(stage["status"], "canceled")
        self.assertEqual(stage["data"]["stop_reason"], "canceled")
        self.assertIs(stage["validity"]["converged"], True)
        self.assertFalse(stage["validity"]["complete"])


if __name__ == "__main__":
    unittest.main()
