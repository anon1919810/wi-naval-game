"""Explicit, source-preserving geometry content import contracts."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG))

import geometry_import
import project_io
import project_store
import stability


def project() -> dict:
    value = project_io.new_project("几何导入试验", "geometry-import-test")
    value["hull"] = {"lwl_m": 99.0, "beam_m": 12.0, "depth_m": 88.0}
    value["sources"] = {"design": {"title": "保留的设计资料"}}
    value["study_notes"] = {"selected_loading": "harbour", "known_zero": 0}
    return value


def polygon_payload(*, whitespace: bool = False) -> bytes:
    payload = {
        "schema": "plimsoll-section-polygons-1",
        "source": {"title": "独立解析型线", "page": 6},
        "estimate": False,
        "stations": [
            [-10.0, [[-3.0, 7.0], [3.0, 7.0], [3.0, 11.0], [-3.0, 11.0]]],
            [0.0, [[-3.0, 7.0], [3.0, 7.0], [3.0, 11.0], [-3.0, 11.0]]],
            [10.0, [[-3.0, 7.0], [3.0, 7.0], [3.0, 11.0], [-3.0, 11.0]]],
        ],
    }
    separators = None if whitespace else (",", ":")
    return json.dumps(payload, ensure_ascii=False, separators=separators).encode("utf-8")


def legacy_payload() -> bytes:
    return json.dumps({
        "schema": "plimsoll-offsets-1",
        "deck_z_m": 4.0,
        "source": {"title": "五列型值表", "method": "declared table"},
        "stations": [
            [-10.0, 0.0, 0.0, -2.0, 0.0],
            [-5.0, 2.0, 2.0, -2.0, 1.0],
            [0.0, 3.0, 3.0, -2.0, 1.0],
            [5.0, 2.0, 2.0, -2.0, 1.0],
            [10.0, 0.0, 0.0, -2.0, 0.0],
        ],
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class GeometryImportTests(unittest.TestCase):
    def exact(self, actual, expected):
        self.assertTrue(
            math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10),
            (actual, expected),
        )

    def test_polygon_import_is_self_contained_datum_exact_and_immutable(self):
        original = project()
        raw = polygon_payload()
        project_before = copy.deepcopy(original)
        bytes_before = bytes(raw)

        imported = geometry_import.import_geometry_content(
            original,
            raw,
            format="plimsoll-section-polygons-1",
            keel_offset_m=7.0,
            source={"title": "用户选择", "path": "型线/船体.json"},
            estimate=False,
        )

        self.assertEqual(original, project_before)
        self.assertEqual(raw, bytes_before)
        self.assertIsNot(imported, original)
        self.assertEqual(imported["hull"], original["hull"])
        self.assertEqual(imported["sources"], original["sources"])
        self.assertEqual(imported["study_notes"], original["study_notes"])
        imported_geometry = imported["geometry"]
        self.assertEqual(imported_geometry["kind"], "offsets")
        self.assertEqual(imported_geometry["keel_offset_m"], 7.0)
        self.assertIs(imported_geometry["estimate"], False)
        self.assertEqual(imported_geometry["offsets"], json.loads(raw))
        trace = imported_geometry["source"]
        self.assertEqual(trace["method"], "geometry_content_import")
        self.assertEqual(trace["format"], "plimsoll-section-polygons-1")
        self.assertEqual(trace["raw_content_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(trace["input_source"],
                         {"title": "用户选择", "path": "型线/船体.json"})
        self.assertIs(trace["input_estimate"], False)
        self.assertEqual(trace["keel_offset_m"], 7.0)
        self.assertEqual(trace["payload_provenance"], {
            "source": {"title": "独立解析型线", "page": 6},
            "estimate": False,
        })
        prepared = stability.prepare_geometry(imported_geometry)
        self.assertEqual(prepared[3]["bounds_m"], [[-10.0, 10.0], [-3.0, 3.0],
                                                    [7.0, 11.0]])
        self.exact(prepared[3]["sealed_envelope_capacity_m3"], 480.0)

    def test_public_arguments_fail_with_structured_import_diagnostics(self):
        cases = [
            ("unhashable format", {"format": []}, "$.format",
             "geometry_import.format_unsupported"),
            ("oversized datum", {"keel_offset_m": 10**400}, "$.keel_offset_m",
             "geometry_import.number_invalid"),
            ("boolean datum", {"keel_offset_m": True}, "$.keel_offset_m",
             "geometry_import.number_invalid"),
            ("null source", {"source": None}, "$.source",
             "geometry_import.source_invalid"),
            ("empty source", {"source": {}}, "$.source",
             "geometry_import.source_invalid"),
            ("blank source", {"source": "  "}, "$.source",
             "geometry_import.source_invalid"),
            ("nonboolean estimate", {"estimate": 1}, "$.estimate",
             "geometry_import.estimate_invalid"),
        ]
        defaults = {
            "format": "plimsoll-section-polygons-1",
            "keel_offset_m": 7.0,
            "source": "selected content",
            "estimate": False,
        }
        for label, overrides, path, code in cases:
            with self.subTest(case=label):
                with self.assertRaises(geometry_import.GeometryImportError) as caught:
                    geometry_import.import_geometry_content(
                        project(), polygon_payload(), **{**defaults, **overrides})
                diagnostic = caught.exception.diagnostics[0]
                self.assertEqual(diagnostic["path"], path)
                self.assertEqual(diagnostic["code"], code)
                self.assertTrue(diagnostic["blocking"])

    def test_caller_source_rejects_surrogates_and_preserves_chinese_text(self):
        invalid_sources = [
            ("string", "\ud800", "$.source"),
            ("object value", {"title": "\ud800"}, "$.source.title"),
            ("nested value", {"details": {"page": "\ud800"}},
             "$.source.details.page"),
            ("nested key", {"details": {"\ud800": "value"}},
             "$.source.details"),
        ]
        for label, declared_source, expected_path in invalid_sources:
            with self.subTest(case=label):
                with self.assertRaises(geometry_import.GeometryImportError) as caught:
                    geometry_import.import_geometry_content(
                        project(), polygon_payload(),
                        format="plimsoll-section-polygons-1", keel_offset_m=7,
                        source=declared_source, estimate=False)
                diagnostic = caught.exception.diagnostics[0]
                self.assertEqual(diagnostic["code"],
                                 "geometry_import.unicode_scalar_invalid")
                self.assertEqual(diagnostic["path"], expected_path)

        chinese = {"标题": "用户选择的型线", "细节": {"页": "第六页"}}
        imported = geometry_import.import_geometry_content(
            project(), polygon_payload(), format="plimsoll-section-polygons-1",
            keel_offset_m=7, source=chinese, estimate=False)
        self.assertEqual(imported["geometry"]["source"]["input_source"], chinese)
        encoded = json.dumps(imported, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.assertIn("用户选择的型线".encode("utf-8"), encoded)

    def test_escaped_lone_surrogate_is_not_returned_as_unsavable_text(self):
        raw = polygon_payload().replace(
            b'"estimate":false', b'"note":"\\ud800","estimate":false')
        with self.assertRaises(geometry_import.GeometryImportError) as caught:
            geometry_import.import_geometry_content(
                project(), raw, format="plimsoll-section-polygons-1",
                keel_offset_m=7, source="selected", estimate=False)
        self.assertEqual(caught.exception.diagnostics[0]["code"],
                         "geometry_import.unicode_scalar_invalid")
        self.assertEqual(caught.exception.diagnostics[0]["path"], "$.content.note")

    def test_legacy_rows_method_and_prior_reference_are_preserved_without_lookup(self):
        original = project()
        original["geometry"] = {
            "kind": "offsets_reference",
            "keel_offset_m": None,
            "source": {"title": "旧的外部引用"},
            "estimate": True,
            "reference": {"path": "不存在/未读取.json"},
        }
        prior = copy.deepcopy(original["geometry"])
        raw = legacy_payload()
        imported = geometry_import.import_geometry_content(
            original, raw, format="legacy-offsets-5", keel_offset_m=-2,
            source="explicit caller bytes", estimate=True)

        self.assertEqual(original["geometry"], prior)
        geometry = imported["geometry"]
        self.assertEqual(geometry["offsets"], json.loads(raw))
        self.assertEqual(len(geometry["offsets"]["stations"]), 5)
        self.assertEqual(geometry["offsets"]["deck_z_m"], 4.0)
        self.assertEqual(geometry["source"]["representation"],
                         "legacy_offsets_5_section_generator")
        self.assertEqual(geometry["source"]["prior_offsets_reference"], prior)
        self.assertEqual(geometry["source"]["payload_provenance"], {
            "source": {"title": "五列型值表", "method": "declared table"},
        })
        prepared = stability.prepare_geometry(geometry)
        self.assertEqual(prepared[3]["schema"], "plimsoll-offsets-1")
        self.assertEqual(prepared[3]["keel_offset_m"], -2.0)
        self.assertEqual(prepared[3]["bounds_m"][2], [-2.0, 4.0])
        self.assertNotEqual(geometry["offsets"]["deck_z_m"], 5.1)

    def test_raw_hash_changes_with_whitespace_without_changing_geometry(self):
        compact = polygon_payload()
        spaced = polygon_payload(whitespace=True)
        kwargs = dict(format="plimsoll-section-polygons-1", keel_offset_m=7,
                      source={"title": "same selection"}, estimate=True)
        first = geometry_import.import_geometry_content(project(), compact, **kwargs)
        second = geometry_import.import_geometry_content(project(), spaced, **kwargs)
        self.assertEqual(first["geometry"]["offsets"], second["geometry"]["offsets"])
        self.assertNotEqual(first["geometry"]["source"]["raw_content_sha256"],
                            second["geometry"]["source"]["raw_content_sha256"])
        self.assertIs(first["geometry"]["estimate"], True)
        self.assertIs(first["geometry"]["source"]["input_estimate"], True)
        self.assertNotIn("historical_validated", first["geometry"]["source"])

    def test_self_contained_geometry_survives_chinese_path_save_and_move(self):
        imported = geometry_import.import_geometry_content(
            project(), polygon_payload(), format="plimsoll-section-polygons-1",
            keel_offset_m=7, source="selected bytes", estimate=False)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "中文目录" / "原项目.json"
            second = root / "另一个目录" / "移动后.json"
            first.parent.mkdir()
            second.parent.mkdir()
            project_store.save(first, imported)
            first.replace(second)
            reopened = project_store.load(second)
        self.assertEqual(reopened["geometry"], imported["geometry"])
        prepared = stability.prepare_geometry(reopened["geometry"])
        self.exact(prepared[3]["sealed_envelope_capacity_m3"], 480.0)
        self.assertNotIn("reference", reopened["geometry"])

    def test_strict_parser_rejects_ambiguous_or_nonportable_json(self):
        huge = b'{"schema":"plimsoll-section-polygons-1","value":' + (
            b"9"*5000) + b',"stations":[]}'
        cases = [
            ("invalid utf8", b"\xff", "geometry_import.utf8_invalid"),
            ("malformed", b"{", "geometry_import.json_invalid"),
            ("duplicate", b'{"schema":"plimsoll-section-polygons-1",'
             b'"schema":"plimsoll-section-polygons-1","stations":[]}',
             "geometry_import.duplicate_key"),
            ("nan", b'{"schema":"plimsoll-section-polygons-1",'
             b'"value":NaN,"stations":[]}', "geometry_import.number_nonfinite"),
            ("overflow float", b'{"schema":"plimsoll-section-polygons-1",'
             b'"value":1e9999,"stations":[]}', "geometry_import.number_nonfinite"),
            ("oversized integer", huge, "geometry_import.number_out_of_range"),
            ("root array", b"[]", "geometry_import.object_required"),
        ]
        for label, raw, code in cases:
            with self.subTest(case=label):
                with self.assertRaises(geometry_import.GeometryImportError) as caught:
                    geometry_import.import_geometry_content(
                        project(), raw, format="plimsoll-section-polygons-1",
                        keel_offset_m=0, source="selected", estimate=False)
                self.assertEqual(caught.exception.diagnostics[0]["code"], code)
                self.assertEqual(caught.exception.diagnostics[0]["path"], "$.content")

    def test_format_schema_and_content_type_are_explicit(self):
        cases = [
            ("unknown", polygon_payload(), "unknown-format", "$.format",
             "geometry_import.format_unsupported"),
            ("polygon as legacy", polygon_payload(), "legacy-offsets-5",
             "$.content.schema", "geometry_import.schema_mismatch"),
            ("legacy as polygon", legacy_payload(), "plimsoll-section-polygons-1",
             "$.content.schema", "geometry_import.schema_mismatch"),
            ("text not bytes", polygon_payload().decode("utf-8"),
             "plimsoll-section-polygons-1", "$.content",
             "geometry_import.content_type"),
        ]
        for label, raw, selected_format, path, code in cases:
            with self.subTest(case=label):
                with self.assertRaises(geometry_import.GeometryImportError) as caught:
                    geometry_import.import_geometry_content(
                        project(), raw, format=selected_format, keel_offset_m=0,
                        source="selected", estimate=False)
                self.assertEqual(caught.exception.diagnostics[0]["path"], path)
                self.assertEqual(caught.exception.diagnostics[0]["code"], code)

    def test_shared_geometry_adapter_rejects_unrepaired_content(self):
        base = json.loads(polygon_payload())
        cases = []
        bad = copy.deepcopy(base)
        bad["stations"][0][1][0][0] = True
        cases.append(("boolean coordinate", bad, "plimsoll-section-polygons-1"))
        bad = copy.deepcopy(base)
        bad["stations"][1][0] = -10.0
        cases.append(("duplicate station", bad, "plimsoll-section-polygons-1"))
        bad = copy.deepcopy(base)
        bad["stations"][1][0] = -11.0
        cases.append(("unordered station", bad, "plimsoll-section-polygons-1"))
        bad = copy.deepcopy(base)
        bad["stations"] = bad["stations"][:2]
        cases.append(("too few stations", bad, "plimsoll-section-polygons-1"))
        bad = copy.deepcopy(base)
        bad["stations"][1][1] = [[-3, 7], [3, 11], [3, 7], [-3, 11]]
        cases.append(("touching section", bad, "plimsoll-section-polygons-1"))
        legacy = json.loads(legacy_payload())
        legacy.pop("deck_z_m")
        cases.append(("missing legacy deck", legacy, "legacy-offsets-5"))
        legacy = json.loads(legacy_payload())
        legacy["deck_z_m"] = True
        cases.append(("boolean legacy deck", legacy, "legacy-offsets-5"))

        for label, payload, selected_format in cases:
            with self.subTest(case=label):
                raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                with self.assertRaises(geometry_import.GeometryImportError) as caught:
                    geometry_import.import_geometry_content(
                        project(), raw, format=selected_format, keel_offset_m=0,
                        source="selected", estimate=False)
                diagnostic = caught.exception.diagnostics[0]
                self.assertEqual(diagnostic["code"], "geometry_import.geometry_invalid")
                self.assertEqual(diagnostic["path"], "$.content")
                self.assertIn("geometry validation failed", diagnostic["message"])

    def test_failed_import_preserves_project_and_existing_saved_bytes(self):
        original = project()
        before = copy.deepcopy(original)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "已保存.json"
            project_store.save(path, original)
            saved = path.read_bytes()
            with self.assertRaises(geometry_import.GeometryImportError):
                geometry_import.import_geometry_content(
                    original, b"{broken", format="plimsoll-section-polygons-1",
                    keel_offset_m=0, source="selected", estimate=False)
            self.assertEqual(path.read_bytes(), saved)
        self.assertEqual(original, before)

    def test_invalid_project_diagnostics_are_preserved_in_import_error(self):
        invalid = project()
        invalid["revision"] = -1
        invalid["hull"]["beam_m"] = True
        expected = project_io.validate_project(invalid)
        with self.assertRaises(geometry_import.GeometryImportError) as caught:
            geometry_import.import_geometry_content(
                invalid, polygon_payload(), format="plimsoll-section-polygons-1",
                keel_offset_m=7, source="selected", estimate=False)
        self.assertEqual(caught.exception.diagnostics, expected)


if __name__ == "__main__":
    unittest.main()
