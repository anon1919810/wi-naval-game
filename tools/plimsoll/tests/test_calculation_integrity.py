"""Regression cases for physical centroids, incomplete resistance and provenance."""
import os
import sys
import unittest
import json
import math
from pathlib import Path
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import damage
import hydrostatics
import resistance
import engines
import freesurface


def table(cell=0.001):
    return {"axes": {"cp": [0.5, 0.7], "bt": [2., 4.],
                     "volumetric": [0.002, 0.004], "fn": [0.16, 0.58]},
            "cr": [[[[cell for _ in range(2)] for _ in range(2)]
                    for _ in range(2)] for _ in range(2)], "source": "test grid"}


class CalculationIntegrity(unittest.TestCase):
    hp = {"lwl_m": 200., "s_m2": 6000., "cp": 0.6, "bt": 3., "volumetric": 0.003}

    def test_flood_centroid_is_midpoint_of_occupied_height(self):
        for fraction, expected in [(0.25, 3.), (0.5, 4.), (1., 6.)]:
            with self.subTest(fraction=fraction):
                row = damage.flood_tank_state({"length_m": 10, "beam_m": 4,
                    "height_m": 8, "keel_to_bottom_m": 2, "flood_fraction": fraction})
                self.assertAlmostEqual(row["kg_flood_m"], expected)

    def test_impermeable_tank_does_not_change_stability(self):
        out = damage.flood_combination({"displacement_t": 1000., "kg_m": 5., "km_m": 8.},
            [{"length_m": 10, "beam_m": 8, "height_m": 4,
              "permeability": 0., "flood_fraction": 0.7}])
        self.assertEqual(out["fsc_m"], 0.)
        self.assertEqual(out["kg_effective_m"], 5.)
        self.assertEqual(out["gm_m"], 3.)
        self.assertFalse(out["tanks"][0]["free_surface_active"])

    def test_gz_free_surface_adapter_respects_disabled_or_impermeable_tanks(self):
        for flags in ({"permeability": 0.}, {"free_surface": False}, {}):
            with self.subTest(flags=flags):
                tanks = [{"length_m": 10., "beam_m": 8., "height_m": 4.,
                          "flood_fraction": .5, **flags}]
                combo = damage.flood_combination({"displacement_t": 1000., "kg_m": 4.}, tanks)
                fs = freesurface.free_surface_correction(damage.flood_tanks_to_fs_tanks(tanks),
                                                        combo["displacement_after_t"])
                self.assertAlmostEqual(fs["fsc_m"], combo["fsc_m"])

    def test_reynolds_warning_survives_curve_and_identifies_speed(self):
        out = resistance.speed_power_curve(self.hp, [28.1], table())
        self.assertTrue(any("Schoenherr" in w and "28.1" in w for w in out["warnings"]))
        self.assertTrue(any("Schoenherr" in w for w in out["rows"][0]["warnings"]))
        self.assertTrue(any(t["key"] == "cf" for t in out["rows"][0]["trace"]))

    def test_missing_residual_never_becomes_total_power(self):
        for grid in (None, table(None)):
            with self.subTest(grid=bool(grid)):
                out = resistance.speed_power_curve(self.hp, [28.1], grid)
                row = out["rows"][0]
                self.assertGreater(row["rf_kN"], 0)
                for key in ("rt_kN", "pe_kw", "shp_required"):
                    self.assertIsNone(row[key])
                self.assertFalse(row["complete"])
                self.assertIsNone(out["values"]["shp_max"])

    def test_sparse_and_axis_warnings_survive(self):
        grid = table()
        grid["cr"][0][0][0][0] = None
        out = resistance.speed_power_curve(self.hp, [28.1], grid)
        self.assertTrue(any("缺格" in w for w in out["warnings"]))
        out = resistance.speed_power_curve(dict(self.hp, cp=0.9), [28.1], table())
        self.assertTrue(any("截断" in w for w in out["warnings"]))

    def test_exact_table_endpoint_has_no_false_clipping_warning(self):
        out = resistance.residual_from_table(table(), 0.5, 2., 0.002, 0.16)
        self.assertFalse(out["warnings"])

    def test_nonfinite_speed_rejected(self):
        for v in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                resistance.speed_power_curve(self.hp, [v], table())

    def test_cwp_estimate_propagates_to_stability(self):
        result = hydrostatics.compute({"lwl_m": 100, "beam_m": 20, "draught_m": 6,
            "block_coeff": .6, "waterplane_coeff": .8, "waterplane_coeff_is_estimate": True,
            "kg_m": 3., "kg_is_estimate": False})
        trace = {t["key"]: t for t in result["trace"]}
        for key in ("awp_m2", "bm_t_m", "bm_l_m", "mct1cm_t_m_per_cm", "km_m", "gm_m"):
            with self.subTest(key=key):
                self.assertTrue(trace[key]["estimate"])

    def test_engines_partial_snapshot_preserves_diagnostics_and_missing_fields(self):
        fields = ("max_speed_kn", "cruise_speed_kn", "shafts", "power_design_shp",
                  "power_design_kw", "range_nm", "pct_coal", "engine_weight_t", "bunker_total_t")
        view = engines.sps_view({"values": dict.fromkeys(fields), "warnings": ["engine input"]},
            {"speed_kn": 28.1, "friction_kN": 1200., "residual_kN": None,
             "warnings": ["missing residual"], "estimate": True})
        self.assertIn("wave_resistance", view["_not_implemented"])
        self.assertIn("displacement_factor", view["_not_implemented"])
        self.assertIn("missing residual", view["warnings"])
        self.assertIn("engine input", view["warnings"])

    def test_normal_resistance_basis_uses_one_loading_for_all_geometry(self):
        from tools.qm_resistance_inputs import build_normal_basis
        # A box with 1000 m³ displacement: Cb=1, Cp=1/1, S=100*(1.7*2+5).
        hull = {"lwl_m": 100., "beam_m": 5., "draught_normal_m": 2.,
                "draught_deep_m": 9., "displacement_normal_t": 1025.,
                "block_coeff": .2}  # stale rounded Cb must not override consistent displacement
        hp = build_normal_basis(hull, {"cm": 1.})
        self.assertAlmostEqual(hp["s_m2"], 840.)
        self.assertAlmostEqual(hp["cp"], 1.)
        self.assertAlmostEqual(hp["volumetric"], .001)
        self.assertAlmostEqual(hp["bt"], 2.5)
        self.assertEqual(hp["loading_condition"], "normal")
        self.assertTrue(hp["estimate"])

    def test_report_marks_missing_values_and_breaks_curves_at_gaps(self):
        from tools.gen_speed_power_case import build_rows, build_svg
        curve = resistance.speed_power_curve(self.hp, [20., 22., 24.], table())
        rows = curve["rows"]
        for key in ("rt_kN", "pe_kw", "shp_required", "cr"):
            rows[1][key] = None
        curves = {q: curve for q in (.5, .55, .6)}
        output = build_rows(rows, curves)
        self.assertIn("—", output)
        svg = build_svg(rows, curves, 4000., 200000.)
        self.assertEqual(svg["RT"].count("M"), 2)

    def test_generated_point_and_curve_share_normal_loading(self):
        cases = Path(__file__).resolve().parents[1] / "cases"
        point = json.loads((cases / "queen_mary_1913_resistance.json").read_text(encoding="utf-8"))
        curve = json.loads((cases / "queen_mary_1913_speed_power.json").read_text(encoding="utf-8"))
        hp = curve["hull_params_normal_estimate"]
        self.assertEqual(hp, point["inputs"]["normal_estimate"])
        speed = curve["trial_reference"]["speed_kn"]
        row = next(r for r in curve["curves"]["qpc=0.55"]["rows"] if r["speed_kn"] == speed)
        self.assertEqual(row, point["normal_prediction"])
        self.assertAlmostEqual(row["fr"], speed * resistance.KNOT_MPS / math.sqrt(9.81 * hp["lwl_m"]))
        self.assertAlmostEqual(hp["volume_m3"], hp["cb"] * hp["lwl_m"] * hp["beam_m"] * hp["draught_m"])
        self.assertEqual(curve["trial_reference"]["loading_condition"], "unknown")
        self.assertFalse(curve["trial_comparison"]["validated"])

    def test_generated_geometry_keeps_estimate_on_all_traces(self):
        cases = Path(__file__).resolve().parents[1] / "cases"
        fc = json.loads((cases / "queen_mary_1913_formcoeff.json").read_text(encoding="utf-8"))
        self.assertTrue(fc["estimate"])
        self.assertTrue(all(t["estimate"] for t in fc["trace"]))
        self.assertTrue(any(t["key"] == "wetted_surface_m2" for t in fc["trace"]))

    def test_cli_gz_serializes_distinct_loading_and_deck_warning(self):
        pkg = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            run = subprocess.run([sys.executable, "-B", str(pkg / "cli.py"),
                str(pkg / "cases/queen_mary_1913.json"), "--gz", "-o", str(output)],
                capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=45)
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", errors="replace"))
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["loading_condition"], "normal")
        self.assertEqual(data["gz_curve"]["loading_condition"], "offsets_design_waterline")
        self.assertTrue(any("甲板浸没角" in w for w in data["gz_curve"]["warnings"]))
        self.assertTrue(all(w in data["warnings"] for w in data["gz_curve"]["warnings"]))


if __name__ == "__main__":
    unittest.main()
