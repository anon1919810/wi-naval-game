"""Package import identity and direct legacy-script compatibility."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PKG = Path(__file__).resolve().parents[1]
TOOLS = PKG.parent


class PackageSubprocessTests(unittest.TestCase):
    def run_python(self, script, *args, cwd):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH=str(TOOLS))
        return subprocess.run(
            [sys.executable, "-B", "-c", textwrap.dedent(script), *map(str, args)],
            cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def test_package_import_is_qualified_and_has_no_global_side_effects(self):
        script = """
            import importlib
            import json
            import sys
            import types

            before = list(sys.path)
            sentinel = types.ModuleType("geometry")
            sentinel.marker = object()
            sys.modules["geometry"] = sentinel
            import plimsoll
            qualified = importlib.import_module("plimsoll.geometry")
            offsets = importlib.import_module("plimsoll.offsets")
            leaked = sorted(name for name in (
                "damage", "freesurface", "geometric", "hydrostatics", "offsets"
            ) if name in sys.modules)
            forbidden_runtime_modules = sorted(name for name in (
                "tkinter", "requests", "httpx", "socket"
            ) if name in sys.modules)
            print(json.dumps({
                "path_unchanged": before == sys.path,
                "geometry_identity": plimsoll.geometry is qualified,
                "class_identity": offsets.StationedHull is qualified.StationedHull,
                "sentinel_untouched": sys.modules["geometry"] is sentinel,
                "leaked": leaked,
                "forbidden_runtime_modules": forbidden_runtime_modules,
            }))
        """
        with tempfile.TemporaryDirectory(prefix="包导入-") as temp:
            before = set(Path(temp).iterdir())
            result = self.run_python(script, cwd=temp)
            after = set(Path(temp).iterdir())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(after, before)
        self.assertEqual(json.loads(result.stdout), {
            "path_unchanged": True,
            "geometry_identity": True,
            "class_identity": True,
            "sentinel_untouched": True,
            "leaked": [],
            "forbidden_runtime_modules": [],
        })

    def test_submodule_first_and_package_first_share_module_identity(self):
        scripts = (
            """
                import importlib, json
                geometry = importlib.import_module("plimsoll.geometry")
                import plimsoll
                print(json.dumps({"same": geometry is plimsoll.geometry}))
            """,
            """
                import importlib, json, plimsoll
                geometry = importlib.import_module("plimsoll.geometry")
                print(json.dumps({"same": geometry is plimsoll.geometry}))
            """,
        )
        with tempfile.TemporaryDirectory(prefix="导入顺序-") as temp:
            for index, script in enumerate(scripts):
                with self.subTest(index=index):
                    result = self.run_python(script, cwd=temp)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {"same": True})

    def test_existing_core_submodules_import_from_clean_process(self):
        modules = [
            "armour", "cli", "damage", "engines", "flooding", "freeboard",
            "freesurface", "geometric", "geometry", "geometry_analysis", "guns",
            "holtrop", "hull", "hydrostatics", "loading", "offsets",
            "project_extensions", "project_io", "project_store", "resistance",
            "run_damage_scenarios", "stability", "systems", "tank_geometry", "units",
            "weapons", "weights",
        ]
        script = """
            import importlib
            import json
            import sys

            before = list(sys.path)
            names = json.loads(sys.argv[1])
            loaded = [importlib.import_module("plimsoll." + name).__name__ for name in names]
            geometry = importlib.import_module("plimsoll.geometry")
            offsets = importlib.import_module("plimsoll.offsets")
            loading = importlib.import_module("plimsoll.loading")
            project_io = importlib.import_module("plimsoll.project_io")
            stability = importlib.import_module("plimsoll.stability")
            leaked = sorted(name for name in names if name in sys.modules)
            print(json.dumps({"loaded": loaded, "leaked": leaked,
                              "path_unchanged": before == sys.path,
                              "class_identity": offsets.StationedHull is geometry.StationedHull,
                              "exception_identity": (loading.project_io.ProjectValidationError
                                                     is project_io.ProjectValidationError),
                              "transitive_geometry_identity": stability.geometry is geometry}))
        """
        with tempfile.TemporaryDirectory(prefix="全部子模块-") as temp:
            result = self.run_python(script, json.dumps(modules), cwd=temp)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["loaded"], ["plimsoll." + name for name in modules])
        self.assertEqual(payload["leaked"], [])
        self.assertTrue(payload["path_unchanged"])
        self.assertTrue(payload["class_identity"])
        self.assertTrue(payload["exception_identity"])
        self.assertTrue(payload["transitive_geometry_identity"])

    def test_qualified_geometry_modules_run_a_real_hydrostatic_calculation(self):
        script = """
            import json
            from plimsoll import geometric, geometry

            hull = geometry.make_reference_hull(
                L=100.0, B=20.0, T=5.0, Cb=0.65, Cwp=0.80,
                deck=8.0, n_stations=41, n_section=32,
            )
            result = geometric.hydrostatics_upright(hull, 5.0)
            print(json.dumps({
                "geometry_module": hull.__class__.__module__,
                "volume_positive": result["volume_m3"] > 0.0,
                "draught_m": result["draught_m"],
            }))
        """
        with tempfile.TemporaryDirectory(prefix="几何计算-") as temp:
            result = self.run_python(script, cwd=temp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "geometry_module": "plimsoll.geometry",
            "volume_positive": True,
            "draught_m": 5.0,
        })


class LegacyScriptTests(unittest.TestCase):
    def test_direct_top_level_modules_retain_legacy_import_identity(self):
        script = """
            import json
            import damage
            import engines
            import geometry
            import hull
            import offsets

            print(json.dumps({
                "class_identity": offsets.StationedHull is geometry.StationedHull,
                "modules": [damage.__name__, engines.__name__, geometry.__name__,
                            hull.__name__, offsets.__name__],
            }))
        """
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                   PYTHONPATH=str(PKG))
        with tempfile.TemporaryDirectory(prefix="旧式导入-") as temp:
            result = subprocess.run(
                [sys.executable, "-B", "-c", textwrap.dedent(script)],
                cwd=temp, env=env, capture_output=True, text=True,
                encoding="utf-8", check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "class_identity": True,
            "modules": ["damage", "engines", "geometry", "hull", "offsets"],
        })

    def test_direct_cli_selftest_and_help_remain_available(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        for argument, expected in (("--selftest", "核心自检通过"), ("--help", "--selftest")):
            with self.subTest(argument=argument):
                result = subprocess.run(
                    [sys.executable, "-B", str(PKG / "cli.py"), argument],
                    cwd=PKG.parent, env=env, capture_output=True, text=True,
                    encoding="utf-8", check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
