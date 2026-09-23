"""Exercise real UTF-8 project persistence and atomic failure boundaries."""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

import project_io
import project_store


def sample_project():
    """Return a project with deliberately distinct unknown, zero and provenance."""
    project = project_io.new_project("试验船", "generic-persistence")
    project["hull"] = {"lwl_m": 12, "beam_m": None}
    project["weight_groups"] = [{
        "id": "structure", "items": [
            {"id": "plate", "mass_t": 0, "x_m": None, "y_m": 0,
             "kg_m": 1, "source": {"id": "drawing", "page": "第六页"},
             "estimate": True, "includes": ["hull.plate"],
             "uncertainty": {"kg_m": [0.5, 1.5]}},
            {"id": "unknown", "mass_t": None, "estimate": None},
            {"id": "known", "mass_t": 3, "x_m": 0, "y_m": 0,
             "kg_m": 2, "source": "称重", "estimate": False},
        ],
    }]
    project["loading_conditions"] = [{
        "id": "custom", "overrides": {"plate": {"mass_t": None}},
    }]
    project["sources"] = {"drawing": {"title": "船体图纸", "estimate": True}}
    project["study_notes"] = {"unknown": None, "known_zero": 0, "text": "备注"}
    return project


class TestProjectStore(unittest.TestCase):
    """Catch discarded input, implicit lookup and destructive failed saves."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "中文项目"
        self.directory.mkdir()
        self.path = self.directory / "试验船.json"

    def test_chinese_roundtrip_preserves_identity_unknown_zero_and_sources(self):
        project = sample_project()
        original = copy.deepcopy(project)
        project_store.save(self.path, project)
        loaded = project_store.load(self.path)
        self.assertEqual(project, original)
        self.assertEqual(project_io.input_fingerprint(loaded),
                         project_io.input_fingerprint(project))
        self.assertEqual(loaded["study_notes"],
                         {"unknown": None, "known_zero": 0, "text": "备注"})
        items = loaded["weight_groups"][0]["items"]
        self.assertEqual([item["estimate"] for item in items], [True, None, False])
        self.assertIsNone(items[0]["x_m"])
        self.assertEqual(items[0]["mass_t"], 0)
        self.assertEqual(items[0]["source"], {"id": "drawing", "page": "第六页"})
        self.assertEqual(items[0]["uncertainty"], {"kg_m": [0.5, 1.5]})
        self.assertEqual(loaded["loading_conditions"][0]["overrides"],
                         {"plate": {"mass_t": None}})
        self.assertIn("试验船", self.path.read_text(encoding="utf-8"))
        self.assertEqual(project_io.validate_project(loaded),
                         project_io.validate_project(project))
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_legacy_load_then_save_reopens_canonical_without_inventing_weights(self):
        ship = {"schema": "plimsoll-ship-1", "name": "旧船", "hull": {
            "displacement_normal_t": 10, "displacement_unit": "long_ton",
            "offsets_path": "型线/船体.json"}, "note": "原始来源"}
        self.path.write_text(json.dumps(ship, ensure_ascii=False), encoding="utf-8")
        loaded = project_store.load(self.path)
        self.assertEqual(loaded["schema"], "plimsoll-project-1")
        self.assertEqual(loaded["legacy_inputs"], {"ship": ship, "weights": None})
        self.assertEqual(loaded["weight_groups"], [])
        self.assertAlmostEqual(loaded["hull"]["displacement_normal_t"], 10.160469088)
        self.assertIsNone(loaded["loading_conditions"][1]["reference_displacement_t"])
        self.assertEqual(loaded["geometry"]["reference"]["path"], "型线/船体.json")
        project_store.save(self.path, loaded)
        self.assertEqual(project_store.load(self.path), loaded)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["schema"],
                         "plimsoll-project-1")

    def test_save_legacy_payload_migrates_and_retains_original(self):
        ship = {"schema": "plimsoll-ship-1", "name": "旧船", "hull": {}}
        project_store.save(self.path, ship)
        loaded = project_store.load(self.path)
        self.assertEqual(loaded["legacy_inputs"]["ship"], ship)
        self.assertEqual(loaded["schema"], "plimsoll-project-1")

    def test_reference_resolution_uses_project_directory_without_reading_or_mutating(self):
        project = sample_project()
        project["geometry"] = {
            "kind": "offsets_reference", "source": "selected survey", "estimate": True,
            "keel_offset_m": None, "reference": {"path": "型线/船体.json"},
        }
        original = copy.deepcopy(project)
        project_store.save(self.path, project)
        loaded = project_store.load(self.path)
        resolved = project_store.resolve_geometry_reference(self.path, loaded)
        self.assertEqual(resolved, self.directory / "型线" / "船体.json")
        self.assertFalse(resolved.exists())
        self.assertEqual(project, original)
        self.assertEqual(loaded["geometry"], original["geometry"])
        self.assertEqual(project_io.input_fingerprint(loaded),
                         project_io.input_fingerprint(original))
        # Save-as retains the declared input; it does not silently rewrite references.
        relocated = self.directory / "另一个项目" / "copy.json"
        relocated.parent.mkdir()
        project_store.save(relocated, loaded)
        copy_project = project_store.load(relocated)
        self.assertEqual(copy_project, loaded)
        self.assertEqual(project_store.resolve_geometry_reference(relocated, copy_project),
                         relocated.parent / "型线" / "船体.json")

    def test_explicit_absolute_reference_is_preserved(self):
        project = sample_project()
        target = self.directory / "chosen.json"
        project["geometry"] = {
            "kind": "offsets_reference", "source": "selected", "estimate": False,
            "keel_offset_m": 0, "reference": {"path": str(target)},
        }
        self.assertEqual(project_store.resolve_geometry_reference(self.path, project), target)
        self.assertFalse(target.exists())

    def test_reference_resolver_rejects_absent_or_materialized_geometry(self):
        for geometry in (None, {
            "kind": "parameters", "source": "draft", "estimate": True,
            "keel_offset_m": 0, "parameters": {"beam_m": 3},
        }):
            with self.subTest(geometry=geometry):
                project = sample_project()
                project["geometry"] = geometry
                with self.assertRaises(ValueError):
                    project_store.resolve_geometry_reference(self.path, project)

    def test_legacy_load_does_not_discover_sibling_weights(self):
        (self.directory / "weights.json").write_text("{broken", encoding="utf-8")
        self.path.write_text(json.dumps({
            "schema": "plimsoll-ship-1", "name": "Legacy", "hull": {},
        }), encoding="utf-8")
        loaded = project_store.load(self.path)
        self.assertEqual(loaded["weight_groups"], [])
        self.assertIsNone(loaded["legacy_inputs"]["weights"])

    def test_explicit_legacy_weights_migration_roundtrip_preserves_payload_and_provenance(self):
        ship = {"schema": "plimsoll-ship-1", "name": "旧船", "hull": {}}
        weights = {"schema": "plimsoll-weights-1", "groups": [{
            "id": "hull", "items": [{
                "id": "plate", "mass_t": 0, "kg_m": None,
                "source": {"title": "原始重量表"}, "estimate": False,
            }],
        }]}
        migrated = project_io.migrate_legacy(ship, weights)
        project_store.save(self.path, migrated)
        loaded = project_store.load(self.path)
        self.assertEqual(loaded["legacy_inputs"], {"ship": ship, "weights": weights})
        item = loaded["weight_groups"][0]["items"][0]
        self.assertEqual(item["mass_t"], 0)
        self.assertIsNone(item["kg_m"])
        self.assertIsNone(item["x_m"])
        self.assertEqual(item["source"], {"title": "原始重量表"})
        self.assertIs(item["estimate"], False)

    def test_validation_failure_preserves_existing_bytes_and_all_diagnostics(self):
        self.path.write_bytes(b"prior exact bytes")
        project = sample_project()
        project["hull"]["lwl_m"] = True
        project["revision"] = -1
        expected = project_io.validate_project(project)
        with self.assertRaises(project_io.ProjectValidationError) as error:
            project_store.save(self.path, project)
        self.assertEqual(error.exception.diagnostics, expected)
        self.assertEqual(self.path.read_bytes(), b"prior exact bytes")
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_nonfinite_values_cannot_replace_existing_file(self):
        self.path.write_bytes(b"prior")
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                project = sample_project()
                project["study_notes"]["number"] = value
                with self.assertRaises(ValueError):
                    project_store.save(self.path, project)
                self.assertEqual(self.path.read_bytes(), b"prior")
                self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_serialization_failure_happens_before_creating_temporary_file(self):
        self.path.write_bytes(b"prior")
        # Lone surrogates cannot be encoded as UTF-8 even though JSON accepts them.
        project = sample_project()
        project["study_notes"]["text"] = "\ud800"
        with self.assertRaises(UnicodeEncodeError):
            project_store.save(self.path, project)
        self.assertEqual(self.path.read_bytes(), b"prior")
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_replace_failure_preserves_previous_file_and_cleans_only_owned_temp(self):
        self.path.write_bytes(b"prior")
        unrelated = self.directory / ".someone-elses.tmp"
        unrelated.write_bytes(b"keep")
        temporary_paths = []

        def failed_replace(source, destination):
            temporary = Path(source)
            temporary_paths.append(temporary)
            self.assertEqual(temporary.parent, self.path.parent)
            self.assertNotEqual(temporary, self.path)
            self.assertEqual(Path(destination), self.path)
            self.assertEqual(json.loads(temporary.read_text(encoding="utf-8"))["name"],
                             "试验船")
            raise PermissionError("injected replace failure")

        with mock.patch.object(project_store.os, "replace", side_effect=failed_replace):
            with self.assertRaisesRegex(PermissionError, "injected replace failure"):
                project_store.save(self.path, sample_project())
        self.assertTrue(temporary_paths)
        self.assertTrue(all(not path.exists() for path in temporary_paths))
        self.assertEqual(self.path.read_bytes(), b"prior")
        self.assertEqual(unrelated.read_bytes(), b"keep")
        self.assertEqual(set(self.directory.iterdir()), {self.path, unrelated})

    def test_flush_failure_preserves_previous_file_and_cleans_owned_temp(self):
        self.path.write_bytes(b"prior")
        with mock.patch.object(project_store.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                project_store.save(self.path, sample_project())
        self.assertEqual(self.path.read_bytes(), b"prior")
        self.assertEqual(list(self.directory.iterdir()), [self.path])

    def test_cleanup_failure_keeps_primary_save_error_and_identifies_owned_temp(self):
        self.path.write_bytes(b"prior")
        unrelated = self.directory / ".unrelated.tmp"
        unrelated.write_bytes(b"keep")
        for operation in ("fsync", "replace"):
            primary = OSError(f"primary {operation} failure")
            with self.subTest(operation=operation):
                with mock.patch.object(project_store.os, operation, side_effect=primary), \
                     mock.patch.object(Path, "unlink", side_effect=PermissionError("cleanup denied")):
                    with self.assertRaises(OSError) as caught:
                        project_store.save(self.path, sample_project())
                self.assertIs(caught.exception, primary)
                leftovers = [p for p in self.directory.iterdir() if p not in (self.path, unrelated)]
                self.assertEqual(len(leftovers), 1)
                note = "\n".join(getattr(caught.exception, "__notes__", []))
                self.assertIn("cleanup denied", note)
                self.assertIn(str(leftovers[0]), note)
                self.assertEqual(self.path.read_bytes(), b"prior")
                self.assertEqual(unrelated.read_bytes(), b"keep")
                leftovers[0].unlink()

    def test_load_rejects_invalid_json_and_does_not_return_previous_project(self):
        project_store.save(self.path, sample_project())
        project_store.load(self.path)
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            project_store.load(self.path)

    def test_load_rejects_unsupported_schema_and_nonfinite_json(self):
        for payload in ({"schema": "plimsoll-project-999", "id": "x", "name": "x"},
                        {"id": "x", "name": "x", "extra": float("nan")}, []):
            with self.subTest(payload=payload):
                self.path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ValueError):
                    project_store.load(self.path)

    def test_load_missing_file_raises_without_creating_file(self):
        with self.assertRaises(FileNotFoundError):
            project_store.load(self.path)
        self.assertFalse(self.path.exists())

    def test_fresh_process_supports_direct_and_package_import_from_other_cwd(self):
        for search_path, module in ((PKG, "project_store"), (PKG.parent, "plimsoll.project_store")):
            with self.subTest(module=module):
                script = (
                    "import importlib, json, pathlib, sys; "
                    "sys.path.insert(0, sys.argv[1]); "
                    "store = importlib.import_module(sys.argv[2]); "
                    "store.save(sys.argv[3], {'schema':'plimsoll-project-1','id':'child','name':'子进程'}); "
                    "print(json.dumps(store.load(sys.argv[3]), ensure_ascii=False))"
                )
                completed = subprocess.run(
                    [sys.executable, "-B", "-c", script, str(search_path), module, str(self.path)],
                    cwd=self.directory, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                    capture_output=True, text=True, encoding="utf-8", check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["name"], "子进程")


if __name__ == "__main__":
    unittest.main()
