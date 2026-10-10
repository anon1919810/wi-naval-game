import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "tools/plimsoll/cases/damage_lab"


class DamageLabCliTests(unittest.TestCase):
    def invoke(self, experiment, output, *extra):
        return subprocess.run([sys.executable, "-m", "tools.plimsoll.damage_lab", "--project",
            str(CASES / "synthetic-rig.project.json"), "--condition", "normal", "--experiment",
            str(experiment), "--output", str(output), *extra], cwd=ROOT, capture_output=True, text=True)

    def test_json_csv_round_trip_uses_frozen_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            output, table = Path(folder) / "report.json", Path(folder) / "report.csv"
            run = self.invoke(CASES / "machinery-hit.experiment.json", output, "--csv", str(table))
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            rows = list(csv.DictReader(io.StringIO(table.read_text(encoding="utf-8"))))
            values = {row["path"]: json.loads(row["value_json"]) for row in rows}
            self.assertEqual(values["/request_fingerprint"], result["request_fingerprint"])
            self.assertEqual(values["/final_state/modules/0/effective_availability"],
                             result["final_state"]["modules"][0]["effective_availability"])
            from tools.plimsoll.damage_lab import run_experiment
            replay = run_experiment(result["input_snapshot"], result["condition_id"], result["request"]["experiment"])
            self.assertEqual(replay["request_fingerprint"], result["request_fingerprint"])
            self.assertEqual(replay["final_state"], result["final_state"])

    def test_duplicate_keys_reject_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            input_path, output = Path(folder) / "input.json", Path(folder) / "out.json"
            input_path.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
            run = self.invoke(input_path, output)
            self.assertEqual(run.returncode, 1)
            self.assertIn("duplicate JSON key", run.stderr)
            self.assertFalse(output.exists())

    def test_input_output_alias_is_rejected(self):
        input_path = CASES / "intact.experiment.json"
        original = input_path.read_bytes()
        run = self.invoke(input_path, input_path)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(input_path.read_bytes(), original)
