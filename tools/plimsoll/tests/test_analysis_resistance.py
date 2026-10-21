"""Selected-plane empirical adapters retain loading and approximation boundaries."""
import copy
from pathlib import Path
import sys
import unittest
import unittest.mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis
import geometry_analysis
import resistance
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


class ResistanceCoverageTests(unittest.TestCase):
    def test_a_speed_the_kernel_cannot_cover_is_a_named_gap(self):
        """The kernel may drop a speed; the stage must still name it."""
        project = selected_project()
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12, 40]))
        real = resistance.speed_power_curve

        def only_first_speed(*args, **kwargs):
            curve = real(*args, **kwargs)
            curve["rows"] = [row for row in curve["rows"] if row["speed_kn"] == 12]
            return curve

        with unittest.mock.patch.object(resistance, "speed_power_curve", only_first_speed):
            result = analysis.compute_project(project, "normal", options)
        rows = result["stages"]["resistance"]["data"]["rows"]
        self.assertEqual([row["speed_kn"] for row in rows], [12, 40])
        gap = rows[1]
        self.assertFalse(gap["complete"])
        self.assertIsNone(gap["total_resistance_kn"])
        self.assertIsNone(gap["kernel_row"])
        self.assertEqual([d["code"] for d in gap["diagnostics"]], ["taylor.speed_unavailable"])


class RecordedCalibrationTests(unittest.TestCase):
    def scenario_project(self, ship_type):
        project = selected_project()
        project.setdefault("hull", {})["block_coeff"] = 0.50
        scenario = project["resistance_scenarios"][0]
        scenario["calibration"] = dict(method="taylor_gertler_source_axis_strict", ship_type=ship_type)
        return project

    def test_a_recorded_factor_scales_the_power_and_attaches_its_provenance(self):
        project = self.scenario_project("battleship")
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        plain = analysis.compute_project(self.scenario_project_copy(), "normal", options)
        calibrated = analysis.compute_project(project, "normal", options)
        before = plain["stages"]["resistance"]["data"]["rows"][0]["effective_power_kw"]
        row = calibrated["stages"]["resistance"]["data"]["rows"][0]
        self.assertAlmostEqual(row["effective_power_kw"], before * 0.923, places=6)
        self.assertEqual(row["calibration"]["factor"], 0.923)
        self.assertEqual(row["calibration"]["sample"], 146)
        self.assertIn("resistance-benchmark", row["calibration"]["source"])

    def scenario_project_copy(self):
        project = selected_project()
        project.setdefault("hull", {})["block_coeff"] = 0.50
        return project

    def test_an_unfitted_ship_type_is_refused_and_leaves_the_power_uncalibrated(self):
        project = self.scenario_project("submarine")
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(project, "normal", options)
        data = result["stages"]["resistance"]["data"]
        codes = [d["code"] for d in data["diagnostics"]]
        self.assertIn("calibration.refused", codes)
        self.assertIsNone(data["rows"][0].get("calibration"))


class BlendedResistanceTests(unittest.TestCase):
    def blended_project(self, with_inputs=True):
        project = selected_project()
        scenario = project["resistance_scenarios"][0]
        scenario["method"] = "blended_taylor_holtrop_v1"
        project.setdefault("hull", {})["block_coeff"] = 0.50
        if with_inputs:
            scenario["holtrop_inputs"] = dict(
                c_stern=0, bulb_area_m2=0, transom_area_m2=0, appendages=[],
                bow_thruster={"present": False}, additional_roughness_delta_ca=0,
                density_kg_m3=1025, gravity_m_s2=9.81, kinematic_viscosity_m2_s=1.19e-6,
                x_aft_perpendicular_m=-50, x_fore_perpendicular_m=50)
        return project

    def test_a_blended_row_carries_both_families_and_one_blend(self):
        project = self.blended_project()
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(project, "normal", options)
        row = result["stages"]["resistance"]["data"]["rows"][0]
        blend = row["blend"]
        self.assertAlmostEqual(blend["holtrop_share"], 0.5)
        self.assertTrue(blend["blended"])
        self.assertIsNotNone(blend["taylor_resistance_kn"])
        self.assertIsNotNone(blend["holtrop_resistance_kn"])
        low, high = sorted((blend["taylor_resistance_kn"], blend["holtrop_resistance_kn"]))
        self.assertGreaterEqual(row["total_resistance_kn"], low - 1e-9)
        self.assertLessEqual(row["total_resistance_kn"], high + 1e-9)

    def test_a_blended_scenario_without_holtrop_inputs_is_named(self):
        project = self.blended_project(with_inputs=False)
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(project, "normal", options)
        codes = [d["code"] for d in result["stages"]["resistance"]["data"]["diagnostics"]]
        self.assertIn("blend.missing_inputs", codes)


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


class BlendRuleTests(unittest.TestCase):
    def project(self, rule, design_speed=28.5):
        project = selected_project()
        scenario = project["resistance_scenarios"][0]
        scenario["method"] = "blended_taylor_holtrop_v1"
        scenario["holtrop_inputs"] = dict(
            c_stern=0, bulb_area_m2=0, transom_area_m2=0, appendages=[],
            bow_thruster={"present": False}, additional_roughness_delta_ca=0,
            density_kg_m3=1025, gravity_m_s2=9.81, kinematic_viscosity_m2_s=1.19e-6,
            x_aft_perpendicular_m=-50, x_fore_perpendicular_m=50)
        if rule:
            scenario["blend_rule"] = rule
        if design_speed is not None:
            scenario["design_speed_kn"] = design_speed
        return project

    def test_the_cluster_rule_gives_one_weight_computed_from_the_design_point(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[10, 12, 14]))
        result = analysis.compute_project(self.project("cluster"), "normal", options)
        rows = result["stages"]["resistance"]["data"]["rows"]
        shares = {round(row["blend"]["holtrop_share"], 9) for row in rows if row.get("blend")}
        # one weight for the whole curve: the rule reads the hull, never the speed
        self.assertEqual(len(shares), 1, shares)
        self.assertTrue(any("blend_rule=cluster" in note
                            for note in result["stages"]["resistance"]["data"]["assumptions"]))

    def test_the_cluster_rule_without_a_design_speed_is_refused(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(self.project("cluster", design_speed=None), "normal", options)
        codes = [d["code"] for d in result["stages"]["resistance"]["data"]["diagnostics"]]
        self.assertIn("blend.missing_design_speed", codes)

    def test_without_a_rule_the_block_coefficient_rule_still_applies(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(self.project(None), "normal", options)
        row = result["stages"]["resistance"]["data"]["rows"][0]
        self.assertNotIn("blend_rule=cluster", str(result["stages"]["resistance"]["data"]["assumptions"]))
        self.assertIsNotNone(row["blend"])


class ClusterCorrectionTests(unittest.TestCase):
    def project(self, design_speed=28.5, declared_cb=0.55):
        project = selected_project()
        project.setdefault("hull", {})["block_coeff"] = declared_cb
        scenario = project["resistance_scenarios"][0]
        scenario["calibration"] = dict(mode="cluster")
        if design_speed is not None:
            scenario["calibration"]["design_speed_kn"] = design_speed
        return project

    def test_the_correction_is_one_factor_for_the_whole_curve(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[10, 12, 14]))
        result = analysis.compute_project(self.project(), "normal", options)
        rows = result["stages"]["resistance"]["data"]["rows"]
        factors = {round(row["calibration"]["factor"], 9) for row in rows if row.get("calibration")}
        self.assertEqual(len(factors), 1, factors)
        self.assertLess(list(factors)[0], 1.0)
        self.assertTrue(any("cluster correction applied" in note
                            for note in result["stages"]["resistance"]["data"]["assumptions"]))

    def test_a_hull_outside_the_cluster_is_left_alone(self):
        project = self.project(design_speed=21.0, declared_cb=0.40)
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(project, "normal", options)
        row = result["stages"]["resistance"]["data"]["rows"][0]
        self.assertAlmostEqual(row["calibration"]["factor"], 1.0, delta=0.02)

    def test_the_correction_without_a_design_speed_is_refused(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(self.project(design_speed=None), "normal", options)
        codes = [d["code"] for d in result["stages"]["resistance"]["data"]["diagnostics"]]
        self.assertIn("calibration.missing_design_speed", codes)

    def test_without_a_declared_block_coefficient_it_is_refused(self):
        project = self.project()
        project["hull"].pop("block_coeff", None)
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(project, "normal", options)
        codes = [d["code"] for d in result["stages"]["resistance"]["data"]["diagnostics"]]
        self.assertIn("calibration.missing_form", codes)


class TargetModeTests(unittest.TestCase):
    def project(self, calibration, target_mode=None):
        project = selected_project()
        project.setdefault("hull", {})["block_coeff"] = 0.55
        scenario = project["resistance_scenarios"][0]
        scenario["calibration"] = calibration
        if target_mode:
            scenario["target_mode"] = target_mode
        return project

    def run_speeds(self, project, speeds=(12,)):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=list(speeds)))
        return analysis.compute_project(project, "normal", options)["stages"]["resistance"]["data"]

    def test_design_mode_applies_one_flat_factor(self):
        data = self.run_speeds(self.project(dict(mode="design"), "design"), [10, 12, 14])
        factors = {round(row["calibration"]["factor"], 6) for row in data["rows"] if row.get("calibration")}
        self.assertEqual(len(factors), 1, factors)
        self.assertAlmostEqual(list(factors)[0], 0.8079, places=4)
        self.assertTrue(any("design-mode factor" in note for note in data["assumptions"]))

    def test_a_trial_fitted_correction_is_refused_on_a_rated_target(self):
        data = self.run_speeds(self.project(dict(mode="cluster", design_speed_kn=28.5), "design"))
        codes = [d["code"] for d in data["diagnostics"]]
        self.assertIn("calibration.mode_conflict", codes)
        self.assertIsNone(data["rows"][0].get("calibration"))

    def test_without_a_target_mode_the_old_behaviour_holds(self):
        data = self.run_speeds(self.project(dict(mode="cluster", design_speed_kn=28.5)))
        self.assertIsNotNone(data["rows"][0].get("calibration"))
        self.assertNotIn("calibration.mode_conflict", [d["code"] for d in data["diagnostics"]])


class ComparisonTargetTests(unittest.TestCase):
    def project(self, kind="design", shp=20000.0, speed=12.0, source="builder contract"):
        project = selected_project()
        scenario = project["resistance_scenarios"][0]
        scenario["target"] = dict(kind=kind, shp=shp, speed_kn=speed, source=source)
        return project

    def test_the_deviation_is_reported_and_named(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(self.project(), "normal", options)
        row = result["stages"]["resistance"]["data"]["rows"][0]
        comparison = row["comparison"]
        self.assertEqual(comparison["kind"], "design")
        self.assertEqual(comparison["target_shp"], 20000.0)
        self.assertAlmostEqual(comparison["deviation_pct"],
                               100 * (comparison["modelled_shaft_hp"] - 20000.0) / 20000.0, places=1)
        self.assertTrue(any("design target" in note
                            for note in result["stages"]["resistance"]["data"]["assumptions"]))

    def test_a_target_at_another_speed_is_not_silently_compared(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[10]))
        result = analysis.compute_project(self.project(speed=12.0), "normal", options)
        self.assertNotIn("comparison", result["stages"]["resistance"]["data"]["rows"][0])

    def test_a_scenario_without_a_target_produces_no_comparison(self):
        options = dict(stages=["resistance"], resistance=dict(scenario_id="trial", speeds_kn=[12]))
        result = analysis.compute_project(selected_project(), "normal", options)
        self.assertNotIn("comparison", result["stages"]["resistance"]["data"]["rows"][0])


if __name__ == "__main__":
    unittest.main()
