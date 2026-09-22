"""Lossless deterministic JSON/CSV serialization and atomic report writes."""
from __future__ import annotations

import copy
import csv
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

import exports


STAGES = (
    "loading", "systems", "l0", "geometry", "equilibrium",
    "hydrostatics", "gz", "deck", "hydrostatic_curve", "bonjean",
    "resistance", "propulsion", "endurance", "historical", "flooding",
)


def envelope(status="not_requested", *, requested=False, data=None,
             diagnostics=None, reason=None):
    return {
        "status": status,
        "requested": requested,
        "dependencies": [],
        "reason": reason,
        "validity": {
            "complete": status == "completed",
            "converged": True if status == "completed" else None,
            "model_applicable": None,
            "historical_validated": None,
        },
        "method_versions": {},
        "assumptions": [],
        "diagnostics": [] if diagnostics is None else diagnostics,
        "data": data,
    }


def analysis_result():
    stages = {name: envelope() for name in STAGES}
    stages["loading"] = envelope(status="completed", requested=True, data={
        "schema": "plimsoll-loading-1",
        "values": {
            "zero": 0,
            "false": False,
            "empty_string": "",
            "explicit_null": None,
            "empty_object": {},
            "empty_array": [],
            "native_mass": {"value": 12.345678901234567, "unit": "t"},
        },
        "provenance": {
            "source": "图纸, \"A\"\n第二行",
            "estimate": False,
            "uncertainty": {"mass_t": [11.0, 14.0]},
        },
    })
    same_message = "输入缺失，保留原始状态"
    stages["equilibrium"] = envelope(
        status="failed", requested=True, reason="input unavailable",
        diagnostics=[{
            "code": "analysis.same", "severity": "error",
            "path": "$.stages.equilibrium.data", "message": same_message,
            "blocking": True, "stage": "equilibrium",
            "source_path": "$.native.equilibrium",
        }])
    stages["flooding"] = envelope(
        status="canceled", requested=True, reason="canceled",
        diagnostics=[{
            "code": "analysis.same", "severity": "warning",
            "path": "$.stages.flooding.data", "message": same_message,
            "blocking": False, "stage": "flooding",
            "source_path": "$.native.flooding",
        }])
    diagnostics = copy.deepcopy(
        stages["equilibrium"]["diagnostics"] + stages["flooding"]["diagnostics"])
    return {
        "schema": "plimsoll-analysis-1",
        "status": "canceled",
        "project_id": "试验船",
        "condition_id": "港内,工况",
        "project_fingerprint": "project-hash",
        "input_fingerprint": "loading-hash",
        "request_fingerprint": "request-hash",
        "request": {
            "schema": "plimsoll-analysis-request-1",
            "condition_id": "港内,工况",
            "options": {"stages": ["loading", "equilibrium", "flooding"]},
        },
        "input_snapshot": {
            "schema": "plimsoll-project-1",
            "id": "试验船",
            "facts": {"explicit_null": None, "known_zero": 0,
                      "empty": "", "empty_object": {}, "empty_array": [],
                      "quoted\"key\nline": "值, \"甲\"\n乙"},
        },
        "units": {"length": "m", "mass": "t", "angle": "deg"},
        "coordinates": {"x_positive": "forward", "y_positive": "starboard"},
        "geometry_datum": {"z_origin": "keel", "keel_offset_m": 0},
        "method_versions": {"analysis": "selected-loading-analysis-1"},
        "sources": {"operator": "张三, \"值班\"\n夜班"},
        "diagnostics": diagnostics,
        "validity": {
            "complete": False,
            "converged": None,
            "model_applicable": None,
            "historical_validated": False,
        },
        "stages": stages,
    }


class ExportTests(unittest.TestCase):
    def test_json_is_deterministic_complete_and_does_not_mutate_result(self):
        result = analysis_result()
        before = copy.deepcopy(result)
        first = exports.serialize_report(result, format="json")
        second = exports.serialize_report(result, format="json")
        self.assertIsInstance(first, str)
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertEqual(json.loads(first), result)
        self.assertEqual(result, before)
        self.assertIn("张三", first)
        self.assertLess(first.index('"condition_id"'), first.index('"coordinates"'))
        self.assertIn("12.345678901234567", first)

    def test_csv_long_form_preserves_types_context_and_literal_text(self):
        result = analysis_result()
        before = copy.deepcopy(result)
        first = exports.serialize_report(result, format="csv")
        second = exports.serialize_report(result, format="csv")
        self.assertEqual(first, second)
        self.assertEqual(result, before)

        rows = list(csv.DictReader(StringIO(first, newline="")))
        by_path = {row["path"]: row for row in rows}
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["explicit_null"]']["value_type"], "null")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["known_zero"]']["value"], "0")
        self.assertEqual(by_path['$["stages"]["loading"]["data"]["values"]["false"]']["value"], "false")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["empty"]']["value_type"], "string")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["empty"]']["value"], "")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["empty_object"]']["value_type"], "object")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["empty_object"]']["container_size"], "0")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["empty_array"]']["value_type"], "array")
        self.assertEqual(by_path['$["input_snapshot"]["facts"]["empty_array"]']["container_size"], "0")
        self.assertNotIn('$["input_snapshot"]["facts"]["absent"]', by_path)

        special_key = 'quoted"key\nline'
        special_path = '$["input_snapshot"]["facts"][' + json.dumps(special_key, ensure_ascii=False) + ']'
        self.assertEqual(by_path[special_path]["key"], special_key)
        self.assertEqual(by_path[special_path]["value"], '值, "甲"\n乙')

        loading_source = '$["stages"]["loading"]["data"]["provenance"]["source"]'
        loading_estimate = '$["stages"]["loading"]["data"]["provenance"]["estimate"]'
        self.assertEqual(by_path[loading_source]["value"], '图纸, "A"\n第二行')
        self.assertEqual(by_path[loading_estimate]["value_type"], "boolean")
        self.assertEqual(by_path[loading_estimate]["value"], "false")
        self.assertEqual(by_path[loading_source]["stage"], "loading")
        self.assertEqual(by_path[loading_source]["stage_status"], "completed")
        self.assertEqual(by_path[loading_source]["analysis_status"], "canceled")
        self.assertEqual(by_path[loading_source]["project_id"], "试验船")
        self.assertEqual(by_path[loading_source]["condition_id"], "港内,工况")
        self.assertEqual(by_path[loading_source]["project_fingerprint"], "project-hash")
        self.assertEqual(by_path[loading_source]["input_fingerprint"], "loading-hash")
        self.assertEqual(by_path[loading_source]["request_fingerprint"], "request-hash")
        uncertainty = '$["stages"]["loading"]["data"]["provenance"]["uncertainty"]["mass_t"]'
        self.assertEqual(by_path[uncertainty]["value_type"], "array")
        self.assertEqual(by_path[uncertainty]["container_size"], "2")
        self.assertEqual(by_path[uncertainty + "[0]"]["record_path"], uncertainty + "[0]")

        for stage in STAGES:
            row = by_path['$["stages"][' + json.dumps(stage) + ']']
            self.assertEqual(row["stage"], stage)
            self.assertEqual(row["stage_status"], result["stages"][stage]["status"])
        diagnostic_rows = [row for row in rows if row["path"].endswith('["message"]')]
        same = [row for row in diagnostic_rows if row["value"] == "输入缺失，保留原始状态"]
        self.assertEqual(len(same), 4)
        self.assertEqual(len({row["path"] for row in same}), 4)
        self.assertEqual({row["stage"] for row in same}, {"equilibrium", "flooding"})
        expected_diagnostics = (
            (0, "equilibrium", "$.stages.equilibrium.data", "$.native.equilibrium", "true"),
            (1, "flooding", "$.stages.flooding.data", "$.native.flooding", "false"),
        )
        for index, stage, path, source_path, blocking in expected_diagnostics:
            base = f'$["diagnostics"][{index}]'
            self.assertEqual(by_path[base + '["stage"]']["value"], stage)
            self.assertEqual(by_path[base + '["path"]']["value"], path)
            self.assertEqual(by_path[base + '["source_path"]']["value"], source_path)
            self.assertEqual(by_path[base + '["blocking"]']["value"], blocking)
        self.assertEqual(by_path['$["units"]["length"]']["value"], "m")
        self.assertEqual(by_path['$["geometry_datum"]["z_origin"]']["value"], "keel")

    def test_serializer_rejects_invalid_inputs_and_never_imports_calculator(self):
        with self.assertRaisesRegex(ValueError, "plimsoll-analysis-1"):
            exports.serialize_report({"schema": "plimsoll-project-1"})
        with self.assertRaisesRegex(ValueError, "unsupported report format"):
            exports.serialize_report(analysis_result(), format="xml")

        nonfinite = analysis_result()
        nonfinite["input_snapshot"]["facts"]["bad"] = float("nan")
        for report_format in ("json", "csv"):
            with self.subTest(format=report_format):
                with self.assertRaisesRegex(ValueError, "Out of range float values"):
                    exports.serialize_report(nonfinite, format=report_format)

        invalid_text = analysis_result()
        invalid_text["sources"]["operator"] = "unpaired \ud800"
        for report_format in ("json", "csv"):
            with self.subTest(format=report_format):
                with self.assertRaises(UnicodeEncodeError):
                    exports.serialize_report(invalid_text, format=report_format)

        original_import = __import__

        def reject_analysis(name, *args, **kwargs):
            if name == "analysis" or name.endswith(".analysis"):
                raise AssertionError("serializer attempted to import the calculator")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=reject_analysis):
            self.assertTrue(exports.serialize_report(analysis_result(), "json"))
            self.assertTrue(exports.serialize_report(analysis_result(), "csv"))

    def test_generic_document_api_has_no_analysis_schema_assumption(self):
        document = {
            "schema": "plimsoll-batch-result-1",
            "status": "partial",
            "records": [
                {"id": "船,一", "value": None},
                {"id": "船\n二", "value": 0},
            ],
            "empty": {},
        }
        json_text = exports.serialize_document(document, format="json")
        self.assertIsInstance(json_text, str)
        self.assertEqual(json.loads(json_text), document)
        csv_text = exports.serialize_document(document, format="csv")
        rows = {row["path"]: row for row in csv.DictReader(StringIO(csv_text, newline=""))}
        self.assertEqual(rows['$["records"][0]["value"]']["value_type"], "null")
        self.assertEqual(rows['$["records"][1]["value"]']["value"], "0")
        self.assertEqual(rows['$["empty"]']["container_size"], "0")
        with self.assertRaisesRegex(ValueError, "plimsoll-analysis-1"):
            exports.serialize_report(document)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "批量.csv"
            exports.write_document(document, destination, format="csv")
            self.assertEqual(destination.read_text(encoding="utf-8"), csv_text)

    def test_generic_document_requires_an_actual_json_object_tree(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            exports.serialize_document([])
        with self.assertRaisesRegex(TypeError, "keys must be strings"):
            exports.serialize_document({1: "not a JSON object member"})
        with self.assertRaisesRegex(TypeError, "unsupported JSON value type"):
            exports.serialize_document({"tuple": (1, 2)})

    def test_write_report_atomically_replaces_with_exact_serialized_bytes(self):
        result = analysis_result()
        before = copy.deepcopy(result)
        with tempfile.TemporaryDirectory(prefix="报告-目录-") as directory:
            root = Path(directory)
            for report_format in ("json", "csv"):
                with self.subTest(format=report_format):
                    destination = root / f"分析-{report_format}.txt"
                    destination.write_bytes(b"previous bytes")
                    returned = exports.write_report(result, destination, format=report_format)
                    self.assertIsNone(returned)
                    self.assertEqual(
                        destination.read_bytes(),
                        exports.serialize_report(result, format=report_format).encode("utf-8"),
                    )
            self.assertEqual(result, before)
            self.assertFalse(any(path.name.startswith(".plimsoll-report-") for path in root.iterdir()))

            missing_parent = root / "missing" / "report.json"
            with self.assertRaises(FileNotFoundError):
                exports.write_report(result, missing_parent)
            self.assertFalse(missing_parent.parent.exists())

    def test_serialization_failure_happens_before_destination_is_touched(self):
        result = analysis_result()
        result["input_snapshot"]["facts"]["bad"] = float("inf")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "report.json"
            destination.write_bytes(b"irreplaceable prior bytes")
            with mock.patch.object(
                exports.tempfile, "NamedTemporaryFile",
                side_effect=AssertionError("temporary file opened before validation"),
            ):
                with self.assertRaisesRegex(ValueError, "Out of range float values"):
                    exports.write_report(result, destination)
            self.assertEqual(destination.read_bytes(), b"irreplaceable prior bytes")
            self.assertEqual(list(root.iterdir()), [destination])

    def test_write_fsync_and_replace_failures_preserve_prior_and_unrelated_files(self):
        operations = ("write", "fsync", "replace")
        for operation in operations:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                destination = root / "report.json"
                destination.write_bytes(b"prior bytes")
                unrelated = root / ".plimsoll-report-unrelated.tmp"
                unrelated.write_bytes(b"do not remove")

                patches = []
                if operation == "write":
                    real_factory = tempfile.NamedTemporaryFile

                    def fail_write(*args, **kwargs):
                        stream = real_factory(*args, **kwargs)
                        stream.write = mock.Mock(side_effect=OSError("injected write failure"))
                        return stream

                    patches.append(mock.patch.object(
                        exports.tempfile, "NamedTemporaryFile", side_effect=fail_write))
                elif operation == "fsync":
                    patches.append(mock.patch.object(
                        exports.os, "fsync", side_effect=OSError("injected fsync failure")))
                else:
                    patches.append(mock.patch.object(
                        exports.os, "replace", side_effect=PermissionError("injected replace failure")))

                with patches[0]:
                    with self.assertRaises(OSError) as caught:
                        exports.write_report(analysis_result(), destination)
                self.assertIn(f"injected {operation} failure", str(caught.exception))
                self.assertEqual(destination.read_bytes(), b"prior bytes")
                self.assertEqual(unrelated.read_bytes(), b"do not remove")
                self.assertEqual(set(root.iterdir()), {destination, unrelated})

    def test_cleanup_failure_keeps_primary_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "report.json"
            destination.write_bytes(b"prior bytes")
            unrelated = root / "unrelated.tmp"
            unrelated.write_bytes(b"unrelated")
            try:
                with mock.patch.object(
                    exports.os, "replace",
                    side_effect=PermissionError("primary replacement failure"),
                ), mock.patch.object(
                    exports.Path, "unlink",
                    side_effect=OSError("secondary cleanup failure"),
                ):
                    with self.assertRaises(PermissionError) as caught:
                        exports.write_report(analysis_result(), destination)
                self.assertIn("primary replacement failure", str(caught.exception))
                self.assertTrue(any(
                    "secondary cleanup failure" in note
                    for note in getattr(caught.exception, "__notes__", [])
                ))
                self.assertEqual(destination.read_bytes(), b"prior bytes")
                self.assertEqual(unrelated.read_bytes(), b"unrelated")
            finally:
                for path in root.iterdir():
                    if path not in {destination, unrelated}:
                        path.unlink()


if __name__ == "__main__":
    unittest.main()
