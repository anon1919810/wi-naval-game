"""One selected immutable loading through the public calculation coordinator."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis
import loading
import project_io
import project_store


def box_project():
    return dict(id="analysis-box", name="解析方箱", geometry=dict(kind="offsets",
        keel_offset_m=7, source="analytic box", estimate=False,
        offsets=dict(schema="plimsoll-section-polygons-1", stations=[
            [x, [[-3, 7], [3, 7], [3, 11], [-3, 11]]] for x in [-10, 0, 10]])),
        weight_groups=[dict(id="weights", items=[dict(id="hull.a[0]", mass_t=246,
            x_m=0, y_m=0, kg_m=1, source="analytic loading", estimate=False)])],
        loading_conditions=[dict(id="normal"), dict(id="deep", overrides={"hull.a[0]": {"mass_t": 307.5}})],
        opening_definition="supplied", openings=[])


class AnalysisTests(unittest.TestCase):
    def test_requested_reference_grids_retain_row_limits(self):
        result = analysis.compute_project(box_project(), "normal", dict(stages=["hydrostatic_curve", "bonjean"],
            hydrostatic_waterlines_above_keel_m=[1, 2], bonjean_waterlines_above_keel_m=[1, 5]))
        self.assertEqual(result["stages"]["hydrostatic_curve"]["status"], "completed")
        self.assertEqual(result["stages"]["bonjean"]["status"], "model_limit")
        hydro = result["stages"]["hydrostatic_curve"]["data"]
        self.assertAlmostEqual(hydro["rows"][0]["values"]["volume_m3"], 120, delta=1e-10)
        self.assertFalse(hydro["loading_equilibrium_claim"])
        self.assertIsNone(result["stages"]["bonjean"]["data"]["rows"][1]["sections"][0]["area_m2"])

    def test_effective_request_can_be_replayed_without_changing_identity(self):
        result = analysis.compute_project(box_project(), "normal", {"stages": ["loading"]})
        replay = analysis.compute_project(box_project(), "normal", result["request"]["options"])
        self.assertEqual(replay["request_fingerprint"], result["request_fingerprint"])

    def test_deck_uses_shifted_selected_plane_and_supplied_profile(self):
        project = box_project()
        project["deck"] = dict(source="deck drawing", estimate=False, reference_length_m={"value": 20},
            points=[dict(id="aft", x_m=-5, y_m=3, z_m=1), dict(id="fore", x_m=5, y_m=3, z_m=3)],
            segments=[dict(id="main", aft_point_id="aft", fore_point_id="fore")])
        result = analysis.compute_project(project, "normal", {"stages": ["deck"]})
        data = result["stages"]["deck"]["data"]
        self.assertEqual(result["status"], "completed")
        self.assertAlmostEqual(data["profile"]["covered_length_m"], 10, delta=1e-10)
        self.assertAlmostEqual(data["profile"]["coverage_fraction"], .5, delta=1e-10)
        self.assertAlmostEqual(data["profile"]["mean_normal_clearance_m"], 0, delta=1e-10)
        self.assertLess(data["points"][0]["normal_clearance_m"], 0)

    def test_selected_fuel_endurance_and_historical_conditions_remain_explicit(self):
        project = box_project()
        project["systems"] = {"propulsion": {"weight_item_ids": ["hull.a[0]"],
            "facts": {"shafts": {"value": 2, "source": "machinery", "estimate": False}},
            "fuel_bindings": {"coal": {"weight_item_ids": ["hull.a[0]"], "source": "test fuel", "estimate": True},
                              "oil": {"weight_item_ids": [], "absent": True, "source": "no oil", "estimate": False}}}}
        project["endurance_scenarios"] = [dict(id="cruise", method="steady_simultaneous_fuel_consumption",
            speed_kn=10, power_kw=1000, source="consumption study", estimate=True, fuels={
                "coal": dict(required=True, burn_t_per_day=10, reserve_t=6),
                "oil": dict(required=False, burn_t_per_day=0, reserve_t=0)})]
        project["historical_comparisons"] = [dict(id="range", quantity="range_nm", value=5700, unit="nm",
            condition_id="normal", speed_kn=10, source="independent comparison", estimate=True)]
        result = analysis.compute_project(project, "normal", {"stages": ["endurance", "historical"], "endurance_scenario_id": "cruise"})
        self.assertEqual(result["status"], "completed")
        endurance = result["stages"]["endurance"]["data"]
        self.assertEqual(endurance["values"]["range_nm"], 5760)
        self.assertEqual(result["stages"]["historical"]["data"]["rows"][0]["difference"], 60)
        deep = analysis.compute_project(project, "deep", {"stages": ["endurance", "historical"], "endurance_scenario_id": "cruise"})
        self.assertEqual(deep["stages"]["historical"]["data"]["rows"][0]["status"], "unavailable")
        self.assertGreater(deep["stages"]["endurance"]["data"]["values"]["range_nm"], 5760)

    def test_selected_box_identity_plane_and_input_immutability(self):
        project = box_project()
        original = copy.deepcopy(project)
        result = analysis.compute_project(project, "normal", {"stages": ["hydrostatics"]})
        state = result["stages"]["loading"]["data"]
        self.assertEqual(result["schema"], "plimsoll-analysis-1")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["input_fingerprint"], loading.resolve_loading(project, "normal")["input_fingerprint"])
        self.assertEqual(result["input_fingerprint"], state["input_fingerprint"])
        eq = result["stages"]["equilibrium"]["data"]
        self.assertAlmostEqual(eq["volume_m3"], 240, delta=1e-10)
        self.assertAlmostEqual(eq["waterline_d_m"], 9, delta=1e-10)
        measures = result["stages"]["hydrostatics"]["data"]
        self.assertEqual(measures["plane"], {"p": eq["p"], "q": eq["q"], "waterline_d_m": eq["waterline_d_m"]})
        self.assertFalse(result["stages"]["equilibrium"]["requested"])
        self.assertEqual(project, original)
        json.dumps(result, allow_nan=False).encode("utf-8")

    def test_loading_only_never_runs_expensive_kernels_and_request_identity_changes(self):
        with patch.object(analysis.stability, "solve_loaded_equilibrium", side_effect=AssertionError("unexpected solve")):
            first = analysis.compute_project(box_project(), "normal", {"stages": ["loading"]})
            second = analysis.compute_project(box_project(), "normal", {"stages": ["loading"], "equilibrium": {"rho_t_m3": 1}})
        self.assertEqual(first["stages"]["equilibrium"]["status"], "not_requested")
        self.assertNotEqual(first["request_fingerprint"], second["request_fingerprint"])
        self.assertEqual(first["input_fingerprint"], second["input_fingerprint"])

    def test_missing_geometry_preserves_loading_and_returns_partial(self):
        project = box_project()
        project["geometry"] = {"kind": "offsets_reference", "keel_offset_m": None,
            "reference": {"path": "不存在.json"}, "source": "declared", "estimate": True}
        result = analysis.compute_project(project, "normal", {"stages": ["loading", "hydrostatics"]})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stages"]["loading"]["status"], "completed")
        self.assertEqual(result["stages"]["geometry"]["status"], "unavailable")
        self.assertEqual(result["stages"]["hydrostatics"]["status"], "unavailable")
        self.assertIsNone(result["stages"]["hydrostatics"]["data"])

    def test_request_validation_rejects_unknown_nonfinite_bool_and_missing_grids(self):
        for options in ({"mystery": 1}, {"stages": ["unknown"]}, {"equilibrium": {"rho_t_m3": True}},
                        {"equilibrium": {"rho_t_m3": float("nan")}}, {"stages": ["gz"]},
                        {"stages": ["gz"], "gz_angles_deg": [0, 0]},
                        {"stages": ["gz"], "gz_angles_deg": [False]},
                        {"stages": ["gz"], "gz_angles_deg": list(range(202))}):
            with self.subTest(options=options), self.assertRaises(analysis.AnalysisInputError) as caught:
                analysis.compute_project(box_project(), "normal", options)
            self.assertTrue(caught.exception.diagnostics)

    def test_persistent_opening_knowledge_reaches_real_gz(self):
        for marker in ("unknown", "legacy_ambiguous", "supplied"):
            project = box_project()
            project["opening_definition"] = marker
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "开口定义.json"
                project_store.save(path, project)
                reopened = project_store.load(path)
            result = analysis.compute_project(reopened, "normal", {"stages": ["gz"], "gz_angles_deg": [0]})
            curve = result["stages"]["gz"]["data"]
            self.assertEqual(curve["input_fingerprint"], result["input_fingerprint"])
            self.assertEqual(curve["opening_definition"], marker)
            expected = True if marker == "supplied" else None
            self.assertIs(curve["rows"][0]["validity"]["intact_valid"], expected)


if __name__ == "__main__":
    unittest.main()
