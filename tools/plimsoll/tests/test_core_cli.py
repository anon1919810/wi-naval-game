"""Subprocess acceptance for the calculation-core command line."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plimsoll import app, exports, project_store  # noqa: E402


def analysis_result(status="completed"):
    return {
        "schema": "plimsoll-analysis-1",
        "status": status,
        "project_id": "fixture",
        "condition_id": "normal",
        "project_fingerprint": "a" * 64,
        "input_fingerprint": "b" * 64,
        "request_fingerprint": "c" * 64,
        "diagnostics": [],
        "stages": {},
    }


PROJECT_FIXTURE = (
    TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
)
OFFSETS_FIXTURE = TOOLS / "plimsoll" / "cases" / "queen_mary_1913_offsets.json"


def import_geometry_args(project, geometry, *, output, provenance,
                         estimate="false", keel_offset_m="0.0",
                         fmt="legacy-offsets-5"):
    return [
        "import-geometry", str(project), str(geometry),
        "--format", fmt,
        "--keel-offset-m", keel_offset_m,
        "--provenance", provenance,
        "--estimate", estimate,
        "--output", str(output),
    ]


class CoreCliEntrypointTests(unittest.TestCase):
    def run_cli(self, arguments, cwd):
        env = dict(
            os.environ,
            PYTHONIOENCODING="utf-8",
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=str(TOOLS),
        )
        return subprocess.run(
            [sys.executable, "-B", "-m", "plimsoll", *map(str, arguments)],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_module_help_runs_from_unrelated_chinese_directory(self):
        with tempfile.TemporaryDirectory(prefix="核心命令-") as temp:
            before = set(Path(temp).iterdir())
            result = self.run_cli(["--help"], temp)
            after = set(Path(temp).iterdir())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("analyze", result.stdout)
        self.assertIn("batch", result.stdout)
        self.assertIn("sweep", result.stdout)
        self.assertIn("import-geometry", result.stdout)
        self.assertEqual(after, before)

    def test_analyze_computes_once_and_serializes_same_result_to_json_and_csv(self):
        with tempfile.TemporaryDirectory(prefix="单船计算-") as temp:
            root = Path(temp)
            project_path = root / "项目.json"
            options_path = root / "选项.json"
            output_path = root / "结果.json"
            csv_path = root / "结果.csv"
            project_path.write_text('{"schema":"plimsoll-project-1"}', encoding="utf-8")
            options_path.write_text('{"stages":["loading"]}', encoding="utf-8")
            result = analysis_result()
            stdout, stderr = StringIO(), StringIO()
            compute = mock.Mock(return_value=result)
            with (
                mock.patch.object(app, "project_store", types.SimpleNamespace(
                    load=mock.Mock(return_value={"id": "fixture"})), create=True),
                mock.patch.object(app, "analysis", types.SimpleNamespace(
                    compute_project=compute), create=True),
                mock.patch.object(app, "exports", exports, create=True),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                try:
                    exit_code = app.main([
                        "analyze", str(project_path), "--condition", "normal",
                        "--options", str(options_path), "--output", str(output_path),
                        "--csv", str(csv_path),
                    ])
                except NotImplementedError:
                    exit_code = -1
            self.assertEqual(exit_code, 0, stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            compute.assert_called_once_with(
                {"id": "fixture"}, "normal", {"stages": ["loading"]}
            )
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), result)
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn("request_fingerprint", csv_text)
            self.assertIn("c" * 64, csv_text)

    def test_invalid_options_json_is_one_structured_error(self):
        project_path = TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        with tempfile.TemporaryDirectory(prefix="错误输入-") as temp:
            options = Path(temp) / "重复键.json"
            options.write_text('{"stages":[],"stages":[]}', encoding="utf-8")
            result = self.run_cli([
                "analyze", project_path, "--condition", "loaded",
                "--options", options,
            ], temp)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["command"], "analyze")
        self.assertEqual(payload["code"], "cli.json_invalid")
        self.assertEqual(payload["input_path"], str(options))
        self.assertTrue(payload["diagnostics"][0]["blocking"])
        self.assertNotIn("Traceback", result.stderr)

    def test_result_output_cannot_alias_explicit_options_input(self):
        project_path = TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        with tempfile.TemporaryDirectory(prefix="路径保护-") as temp:
            options = Path(temp) / "选项.json"
            original = '{"stages":["loading"]}'
            options.write_text(original, encoding="utf-8")
            result = self.run_cli([
                "analyze", project_path, "--condition", "loaded",
                "--options", options, "--output", options,
            ], temp)
            preserved = options.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["code"], "cli.output_alias")
        self.assertEqual(preserved, original)

    def test_batch_continues_after_case_failures_and_uses_ordinal_filenames(self):
        source_project = (
            TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        )
        with tempfile.TemporaryDirectory(prefix="批量计算-") as temp:
            root = Path(temp)
            manifest_dir = root / "清单"
            projects = manifest_dir / "项目"
            cwd = root / "无关工作目录"
            out = root / "输出"
            projects.mkdir(parents=True)
            cwd.mkdir()
            (projects / "方箱.json").write_bytes(source_project.read_bytes())
            (projects / "坏项目.json").write_text("{", encoding="utf-8")
            manifest = {
                "schema": "plimsoll-batch-1",
                "cases": [
                    {"id": "first", "project": "项目/方箱.json",
                     "condition_id": "loaded", "options": {"stages": ["loading"]}},
                    {"id": "broken", "project": "项目/坏项目.json",
                     "condition_id": "loaded", "options": {"stages": ["loading"]}},
                    {"id": "missing-condition", "project": "项目/方箱.json",
                     "condition_id": "ghost", "options": {"stages": ["loading"]}},
                    {"id": "../unsafe!?", "project": "项目/方箱.json",
                     "condition_id": "loaded", "options": {"stages": ["loading"]}},
                    {"id": "later", "project": "项目/方箱.json",
                     "condition_id": "loaded", "options": {"stages": ["loading"]}},
                ],
            }
            manifest_path = manifest_dir / "批量.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            result = self.run_cli(["batch", manifest_path, "--out", out], cwd)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            summary = json.loads((out / "batch-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["schema"], "plimsoll-batch-result-1")
            self.assertEqual(summary["status"], "partial")
            self.assertEqual([case["id"] for case in summary["cases"]],
                             [case["id"] for case in manifest["cases"]])
            self.assertEqual([case["ordinal"] for case in summary["cases"]],
                             [1, 2, 3, 4, 5])
            self.assertEqual(summary["cases"][0]["result_path"], "0001.result.json")
            self.assertIsNone(summary["cases"][1]["result_path"])
            self.assertIsNone(summary["cases"][2]["result_path"])
            self.assertEqual(summary["cases"][3]["result_path"], "0004.result.json")
            self.assertEqual(summary["cases"][4]["result_path"], "0005.result.json")
            self.assertTrue(summary["cases"][1]["diagnostics"])
            self.assertTrue(summary["cases"][2]["diagnostics"])
            self.assertEqual(
                sorted(path.name for path in out.iterdir()),
                ["0001.result.json", "0004.result.json", "0005.result.json",
                 "batch-summary.json"],
            )
            self.assertFalse((root / "unsafe!?").exists())

    def test_sweep_rejects_invalid_axes_before_creating_outputs(self):
        project_path = TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        valid = {
            "schema": "plimsoll-sweep-1",
            "project": str(project_path),
            "condition_id": "loaded",
            "base_options": {"stages": ["resistance"], "resistance": {
                "scenario_id": "study", "speeds_kn": [10]}},
            "axes": [{
                "field": "resistance.speed_kn", "values": [10],
                "source": "declared grid", "estimate": False,
            }],
        }
        invalid_axes = {
            "duplicate": [valid["axes"][0], valid["axes"][0]],
            "unknown": [{**valid["axes"][0], "field": "hull.length_m"}],
            "boolean": [{**valid["axes"][0], "values": [True]}],
            "nonpositive": [{**valid["axes"][0], "values": [0]}],
            "too-many-speed": [{**valid["axes"][0], "values": list(range(1, 203))}],
            "too-many-qpc": [{**valid["axes"][0], "field": "resistance.qpc",
                                "values": [index / 100 for index in range(1, 23)]}],
            "product": [
                {**valid["axes"][0], "values": list(range(1, 202))},
                {**valid["axes"][0], "field": "resistance.qpc",
                 "values": [index / 100 for index in range(1, 7)]},
            ],
        }
        with tempfile.TemporaryDirectory(prefix="扫描边界-") as temp:
            root = Path(temp)
            for label, axes in invalid_axes.items():
                with self.subTest(case=label):
                    document = {**valid, "axes": axes}
                    source = root / f"{label}.json"
                    out = root / f"{label}-输出"
                    source.write_text(json.dumps(document), encoding="utf-8")
                    result = self.run_cli(["sweep", source, "--out", out], root)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(json.loads(result.stderr)["code"],
                                     "cli.schema_invalid")
                    self.assertFalse(out.exists())

    def test_import_geometry_happy_path_materializes_self_contained_offsets(self):
        project_path = (
            TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        )
        geometry_path = (
            TOOLS / "plimsoll" / "cases" / "queen_mary_1913_offsets.json"
        )
        with tempfile.TemporaryDirectory(prefix="导入几何-") as temp:
            output = Path(temp) / "导入结果.project.json"
            result = self.run_cli([
                "import-geometry", str(project_path), str(geometry_path),
                "--format", "legacy-offsets-5",
                "--keel-offset-m", "-1.0",
                "--provenance", json.dumps({"title": "Queen Mary 1913 型线"}),
                "--estimate", "true",
                "--output", str(output),
            ], temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            imported = project_store.load(output)
        geometry = imported["geometry"]
        self.assertEqual(geometry["kind"], "offsets")
        self.assertEqual(geometry["keel_offset_m"], -1.0)
        expected_sha = hashlib.sha256(geometry_path.read_bytes()).hexdigest()
        self.assertEqual(geometry["source"]["raw_content_sha256"], expected_sha)
        self.assertEqual(
            geometry["source"]["input_source"],
            {"title": "Queen Mary 1913 型线"},
        )

    def test_import_geometry_is_no_longer_unimplemented(self):
        project_path = (
            TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        )
        geometry_path = (
            TOOLS / "plimsoll" / "cases" / "queen_mary_1913_offsets.json"
        )
        with tempfile.TemporaryDirectory(prefix="回归保护-") as temp:
            output = Path(temp) / "回归结果.project.json"
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    exit_code = app.main([
                        "import-geometry", str(project_path), str(geometry_path),
                        "--format", "legacy-offsets-5",
                        "--keel-offset-m", "0.0",
                        "--provenance", json.dumps({"title": "fixture"}),
                        "--estimate", "false",
                        "--output", str(output),
                    ])
                except NotImplementedError:
                    self.fail("import-geometry still raises NotImplementedError")
        self.assertEqual(exit_code, 0, stderr.getvalue())

    def test_import_geometry_rejects_schema_mismatch_as_one_structured_error(self):
        project_path = (
            TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        )
        with tempfile.TemporaryDirectory(prefix="非法内容-") as temp:
            geometry = Path(temp) / "坏型线.json"
            geometry.write_text(
                json.dumps({"schema": "plimsoll-offsets-9", "stations": []}),
                encoding="utf-8",
            )
            output = Path(temp) / "结果.project.json"
            result = self.run_cli([
                "import-geometry", str(project_path), str(geometry),
                "--format", "legacy-offsets-5",
                "--keel-offset-m", "0.0",
                "--provenance", json.dumps({"title": "bad"}),
                "--estimate", "false",
                "--output", str(output),
            ], temp)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["code"], "cli.geometry_import")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())

    def test_import_geometry_output_cannot_alias_project_input(self):
        project_path = (
            TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        )
        geometry_path = (
            TOOLS / "plimsoll" / "cases" / "queen_mary_1913_offsets.json"
        )
        with tempfile.TemporaryDirectory(prefix="路径保护-") as temp:
            result = self.run_cli([
                "import-geometry", str(project_path), str(geometry_path),
                "--format", "legacy-offsets-5",
                "--keel-offset-m", "0.0",
                "--provenance", json.dumps({"title": "fixture"}),
                "--estimate", "false",
                "--output", str(project_path),
            ], temp)
            preserved = project_path.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["code"], "cli.output_alias")
        self.assertEqual(preserved,
                         project_path.read_text(encoding="utf-8"))

    def test_import_geometry_passes_estimate_flag_through(self):
        project_path = (
            TOOLS / "plimsoll" / "cases" / "projects" / "analytic_box.project.json"
        )
        geometry_path = (
            TOOLS / "plimsoll" / "cases" / "queen_mary_1913_offsets.json"
        )
        for estimate, expected in (("false", False), ("true", True)):
            with self.subTest(estimate=estimate), \
                    tempfile.TemporaryDirectory(prefix="估计标志-") as temp:
                output = Path(temp) / "结果.project.json"
                result = self.run_cli([
                    "import-geometry", str(project_path), str(geometry_path),
                    "--format", "legacy-offsets-5",
                    "--keel-offset-m", "0.0",
                    "--provenance", json.dumps({"title": "fixture"}),
                    "--estimate", estimate,
                    "--output", str(output),
                ], temp)
                self.assertEqual(result.returncode, 0, result.stderr)
                imported = project_store.load(output)
                self.assertIs(imported["geometry"]["estimate"], expected)

    def test_import_geometry_bare_string_provenance_is_kept_verbatim(self):
        with tempfile.TemporaryDirectory(prefix="裸串来源-") as temp:
            output = Path(temp) / "结果.project.json"
            result = self.run_cli(
                import_geometry_args(
                    PROJECT_FIXTURE, OFFSETS_FIXTURE, output=output,
                    provenance="survey 1913",
                ), temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            imported = project_store.load(output)
        self.assertEqual(imported["geometry"]["source"]["input_source"], "survey 1913")

    def test_import_geometry_json_string_literal_provenance_is_decoded(self):
        with tempfile.TemporaryDirectory(prefix="字面量来源-") as temp:
            output = Path(temp) / "结果.project.json"
            result = self.run_cli(
                import_geometry_args(
                    PROJECT_FIXTURE, OFFSETS_FIXTURE, output=output,
                    provenance='"survey 1913"',
                ), temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            imported = project_store.load(output)
        self.assertEqual(imported["geometry"]["source"]["input_source"], "survey 1913")

    def test_import_geometry_rejects_empty_provenance(self):
        with tempfile.TemporaryDirectory(prefix="空来源-") as temp:
            output = Path(temp) / "结果.project.json"
            result = self.run_cli(
                import_geometry_args(
                    PROJECT_FIXTURE, OFFSETS_FIXTURE, output=output,
                    provenance="",
                ), temp)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["code"], "cli.provenance_invalid")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())

    def test_import_geometry_rejects_duplicate_payload_keys(self):
        with tempfile.TemporaryDirectory(prefix="重复键-") as temp:
            geometry = Path(temp) / "重复键.json"
            geometry.write_bytes(
                b'{"schema": "plimsoll-offsets-1", "schema": "x", "stations": []}'
            )
            output = Path(temp) / "结果.project.json"
            result = self.run_cli(
                import_geometry_args(
                    PROJECT_FIXTURE, geometry, output=output,
                    provenance="survey 1913",
                ), temp)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["code"], "cli.geometry_import")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())

    def test_import_geometry_rejects_invalid_utf8_payload(self):
        with tempfile.TemporaryDirectory(prefix="非法UTF8-") as temp:
            geometry = Path(temp) / "坏字节.json"
            geometry.write_bytes(b'\xff\xff{"schema": "plimsoll-offsets-1"}')
            output = Path(temp) / "结果.project.json"
            result = self.run_cli(
                import_geometry_args(
                    PROJECT_FIXTURE, geometry, output=output,
                    provenance="survey 1913",
                ), temp)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["code"], "cli.geometry_import")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())

    def test_import_geometry_rejects_nonfinite_keel_offset(self):
        for keel in ("nan", "inf"):
            with self.subTest(keel=keel), \
                    tempfile.TemporaryDirectory(prefix="非有限龙骨-") as temp:
                output = Path(temp) / "结果.project.json"
                result = self.run_cli(
                    import_geometry_args(
                        PROJECT_FIXTURE, OFFSETS_FIXTURE, output=output,
                        provenance="survey 1913", keel_offset_m=keel,
                    ), temp)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                payload = json.loads(result.stderr)
                self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
                self.assertEqual(payload["code"], "cli.geometry_import")
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_import_geometry_rejects_missing_output_directory(self):
        with tempfile.TemporaryDirectory(prefix="缺失目录-") as temp:
            output = Path(temp) / "不存在" / "结果.project.json"
            result = self.run_cli(
                import_geometry_args(
                    PROJECT_FIXTURE, OFFSETS_FIXTURE, output=output,
                    provenance="survey 1913",
                ), temp)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "plimsoll-cli-error-1")
        self.assertEqual(payload["code"], "cli.output_write")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
