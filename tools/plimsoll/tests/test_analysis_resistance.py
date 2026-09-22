"""Selected-plane empirical adapters retain loading and approximation boundaries."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis
import geometry_analysis
from test_analysis import box_project

TABLE_SHA = "e9dc5141235ad9a0ddc1c1de70ab33d28f7aac86f75953663c969ad3fd124d93"


def selected_project(method="taylor_gertler_source_axis_strict"):
    project = box_project()
    project["geometry"] = geometry_analysis.materialize_reference_hull(
        dict(lwl_m=100, beam_m=15, draught_m=5, block_coeff=.6, waterplane_coeff=.8, depth_m=9),
        keel_offset_m=2, source="explicit numerical reference", estimate=True, n_stations=17, n_section=12)
    item = project["weight_groups"][0]["items"][0]
    item.update(mass_t=4000, x_m=1, kg_m=3)
    project["loading_conditions"][1]["overrides"]["hull.a[0]"]["mass_t"] = 4400
    inputs = dict(delta_cf=.0004, density_kg_m3=1025, kinematic_viscosity_m2_s=1.19e-6)
    if method == "holtrop_mennen_1982":
        inputs = dict(c_stern=0, bulb_area_m2=0, transom_area_m2=0, appendages=[],
            bow_thruster={"present": False}, additional_roughness_delta_ca=0, density_kg_m3=1025,
            gravity_m_s2=9.81, kinematic_viscosity_m2_s=1.19e-6,
            x_aft_perpendicular_m=-50, x_fore_perpendicular_m=50)
    project["resistance_scenarios"] = [dict(id="trial", method=method, source="explicit estimated study",
        estimate=True, attitude_policy="selected_plane_longitudinal_trim_proxy_v1", inputs=inputs,
        input_provenance={key: dict(source="declared scenario", estimate=True) for key in inputs},
        qpc_sensitivity=dict(values=[.5, .6], source="efficiency sensitivity", estimate=True),
        table_id="taylor-gertler-molland-a3", table_sha256=TABLE_SHA,
        friction_method="schoenherr_implicit_ittc_0.242", interpolation_method="taylor_gertler_source_axis_strict",
        speed_conversion_method="international_knot_exact")]
    return project


class SelectedResistanceTests(unittest.TestCase):
    def test_taylor_proxy_keeps_actual_trim_volume_and_exact_power_conversion(self):
        project = selected_project()
        original = copy.deepcopy(project)
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(project, "normal", options)
        data = result["stages"]["resistance"]["data"]
        eq = result["stages"]["equilibrium"]["data"]
        self.assertGreater(abs(eq["trim_deg"]), .01)
        self.assertEqual(data["selected_plane"], {key: eq[key] for key in ("p", "q", "waterline_d_m")})
        self.assertAlmostEqual(data["selected_volume_m3"], 4000/1.025, delta=1e-6)
        self.assertFalse(data["validity"]["model_applicable"])
        self.assertFalse(data["primary_result"])
        self.assertEqual(data["source_table"]["raw_sha256"], TABLE_SHA)
        rows = data["power_rows"]
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0]["shaft_power_kw"])
        self.assertAlmostEqual(rows[0]["shaft_power_kw"]*.5, rows[1]["shaft_power_kw"]*.6, delta=1e-10)
        self.assertAlmostEqual(rows[0]["shaft_power_kw"], rows[0]["shaft_power_shp"]*.7456998715822702, delta=1e-10)
        self.assertEqual(project, original)

    def test_strict_trim_and_missing_shape_choices_are_unavailable(self):
        project = selected_project()
        project["resistance_scenarios"][0]["attitude_policy"] = "strict_upright"
        result = analysis.compute_project(project, "normal", dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12])))
        self.assertEqual(result["stages"]["resistance"]["status"], "unavailable")
        project = selected_project("holtrop_mennen_1982")
        del project["resistance_scenarios"][0]["inputs"]["bow_thruster"]
        del project["resistance_scenarios"][0]["input_provenance"]["bow_thruster"]
        result = analysis.compute_project(project, "normal", dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12])))
        self.assertEqual(result["stages"]["resistance"]["status"], "unavailable")

    def test_holtrop_uses_selected_drafts_and_retains_kernel_algebra(self):
        project = selected_project("holtrop_mennen_1982")
        result = analysis.compute_project(project, "normal", dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12])))
        data = result["stages"]["resistance"]["data"]
        eq = result["stages"]["equilibrium"]["data"]
        inputs = data["effective_inputs"]
        self.assertAlmostEqual(inputs["draft_fore_m"], eq["waterline_d_m"]+50*eq["p"]-2, delta=1e-10)
        self.assertAlmostEqual(inputs["draft_aft_m"], eq["waterline_d_m"]-50*eq["p"]-2, delta=1e-10)
        row = data["rows"][0]
        self.assertAlmostEqual(row["effective_power_kw"], row["total_resistance_kn"]*12*1852/3600, delta=1e-10)
        self.assertFalse(row["primary_result"])


if __name__ == "__main__":
    unittest.main()
