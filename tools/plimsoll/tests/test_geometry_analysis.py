"""Independent C1/C4 box, triangle, datum, provenance and event anchors."""

import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stability
import geometry

try:
    import geometry_analysis as analysis
except ModuleNotFoundError:
    analysis = None


def prism(triangle=False, shift=0, n=3):
    poly = [[-3, 5], [3, 5], [0, 0]] if triangle else [[-3, 0], [3, 0], [3, 5], [-3, 5]]
    return {
        "kind": "offsets", "keel_offset_m": shift,
        "source": "independent analytic prism", "estimate": False,
        "offsets": {"schema": "plimsoll-section-polygons-1", "stations": [
            [-10 + 20*i/(n-1), [[y, z+shift] for y, z in poly]] for i in range(n)
        ]},
    }


def plane(d=2, p=0, q=0):
    return {"waterline_d_m": d, "p": p, "q": q}


def parameters():
    return {"lwl_m": 20, "beam_m": 6, "draught_m": 2,
            "block_coeff": 0.6, "waterplane_coeff": 0.8, "depth_m": 5}


class SharedGeometryAPITests(unittest.TestCase):
    def test_public_adapter_matches_solver_preparation_and_owns_its_copy(self):
        self.assertTrue(hasattr(stability, "prepare_geometry"), "public adapter is absent")
        hull = prism(shift=7)
        old = stability._prepare(hull, {})
        new = stability.prepare_geometry(hull)
        self.assertEqual(old[0].stations, new[0].stations)
        self.assertEqual(old[1:], new[1:])
        new[0].stations[0][1][0] = (900, 900)
        new[3]["source"] = "changed"
        self.assertEqual(hull, prism(shift=7))

    def test_public_adapter_rejects_malformed_options(self):
        self.assertTrue(hasattr(stability, "prepare_geometry"), "public adapter is absent")
        for bad in ([], False, 1, "options"):
            with self.subTest(options=bad), self.assertRaises(ValueError):
                stability.prepare_geometry(prism(), bad)

    def test_shared_waterline_intervals_preserve_contact_and_concavity(self):
        self.assertTrue(hasattr(geometry, "waterline_intervals"), "public intervals are absent")
        poly = [[-3, 0], [3, 0], [3, 4], [1, 4], [1, 1], [-1, 1], [-1, 4], [-3, 4]]
        for height, intervals, halfwidth in ((2, [(-3, -1), (1, 3)], 2),
                                            (0, [(-3, 3)], 3), (5, [], None)):
            self.assertEqual(geometry.waterline_intervals(poly, 0, height), intervals)
            self.assertEqual(geometry._line_chord_halfwidth(poly, 0, height), halfwidth)


class GeometryAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analysis, "geometry-analysis API is not implemented")

    def exact(self, actual, expected):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10),
                        (actual, expected))

    def test_box_selected_waterline_has_exact_geometry_and_declared_girth_method(self):
        result = analysis.measures_at_plane(prism(), plane())
        self.assertEqual(result["status"], "completed")
        v = result["values"]
        for key, expected in {
            "volume_m3": 240, "displacement_t": 246, "kb_m": 1,
            "lcb_m": 0, "tcb_m": 0, "awp_m2": 120, "it_m4": 360,
            "il_m4": 4000, "bm_t_m": 1.5, "bm_l_m": 50/3,
            "km_t_m": 2.5, "tpc_t_per_cm": 1.23,
            "waterline_length_body_x_m": 20, "waterline_beam_body_y_m": 6,
        }.items():
            self.exact(v[key], expected)
        for key in ("cb", "cm", "cp", "cwp"):
            self.exact(result["form_coefficients"]["values"][key], 1)
        wet = result["wetted_surface"]
        self.exact(wet["area_m2"], 200)
        self.assertNotEqual(wet["area_m2"], 224)
        self.assertEqual(wet["method"], "longitudinal_station_girth_integral")
        self.assertEqual(wet["end_faces"], "excluded")
        self.assertTrue(wet["estimate"])
        self.assertIsNone(result["validity"]["numerical_convergence"])
        self.assertIsNone(result["validity"]["historical_validated"])

    def test_triangle_is_quadratic_in_depth_not_a_box_assumption(self):
        result = analysis.measures_at_plane(prism(triangle=True), plane())
        for key, expected in {"volume_m3": 48, "kb_m": 4/3,
                              "awp_m2": 48, "it_m4": 23.04}.items():
            self.exact(result["values"][key], expected)
        table = analysis.bonjean_table(prism(triangle=True), [1, 2, 4])
        for row, area in zip(table["rows"], [0.6, 2.4, 9.6]):
            for section in row["sections"]:
                self.exact(section["area_m2"], area)

    def test_requested_bonjean_keeps_station_positions_units_and_datum(self):
        table = analysis.bonjean_table(prism(shift=7), [1, 2, 4])
        self.assertEqual(table["waterline_datum"], "above_declared_keel")
        self.assertEqual(table["units"]["section_area"], "m2")
        for row, height in zip(table["rows"], [1, 2, 4]):
            self.exact(row["waterline_above_keel_m"], height)
            self.exact(row["waterline_z_m"], height+7)
            self.assertEqual([s["x_m"] for s in row["sections"]], [-10, 0, 10])
            for section in row["sections"]:
                self.exact(section["area_m2"], 6*height)

    def test_upright_reference_grid_retains_out_of_envelope_rows(self):
        table = analysis.hydrostatic_table(prism(), [-1, 0, 1, 2, 4, 5, 6], rho_t_m3=1.025)
        self.assertEqual(table["scenario"], "constrained_upright_reference_waterlines")
        self.assertFalse(table["loading_equilibrium_claim"])
        self.assertEqual(len(table["rows"]), 7)
        for index in (0, 1, 5, 6):
            row = table["rows"][index]
            self.assertEqual(row["status"], "model_limit")
            self.assertIsNone(row["values"]["bm_t_m"])
            self.assertTrue(row["diagnostics"])
        for index, mass in ((2, 123), (3, 246), (4, 492)):
            self.exact(table["rows"][index]["values"]["displacement_t"], mass)

    def test_geometry_and_declared_keel_translation_preserve_physical_quantities(self):
        a = analysis.measures_at_plane(prism(), plane(d=2, p=0.05, q=0.2))
        b = analysis.measures_at_plane(prism(shift=7), plane(d=9, p=0.05, q=0.2))
        for key, value in a["values"].items():
            if value is not None:
                self.exact(value, b["values"][key])
        self.exact(a["wetted_surface"]["area_m2"], b["wetted_surface"]["area_m2"])
        self.assertEqual(a["plane"]["waterline_d_m"]+7, b["plane"]["waterline_d_m"])
        for key, value in a["form_coefficients"]["values"].items():
            self.exact(value, b["form_coefficients"]["values"][key])
        self.assertEqual(a["form_coefficients"]["applicability"], b["form_coefficients"]["applicability"])

    def test_selected_trim_and_heel_use_each_station_plane_and_true_plane_area(self):
        result = analysis.measures_at_plane(prism(), plane(d=2, p=0.05, q=0.2))
        self.exact(result["values"]["volume_m3"], 240)
        self.exact(result["values"]["awp_m2"], 120*math.sqrt(1.0425))
        self.exact(result["values"]["tcb_m"], 0.3)
        for section, expected in zip(result["sections"], [9, 12, 15]):
            self.exact(section["area_m2"], expected)
        self.assertEqual([s["intercept_m"] for s in result["sections"]], [1.5, 2, 2.5])
        self.assertIsNone(result["values"]["bm_t_m"])
        self.assertIsNone(result["values"]["tpc_t_per_cm"])
        self.assertEqual(result["form_coefficients"]["applicability"],
                         "inclined_body_axis_ratios_not_upright_empirical_inputs")
        self.assertFalse(result["upright_empirical_eligible"])

    def test_concave_waterplane_moments_sum_intervals_without_filling_gap(self):
        hull = prism()
        poly = [[-3, 0], [3, 0], [3, 4], [1, 4], [1, 1], [-1, 1], [-1, 4], [-3, 4]]
        hull["offsets"]["stations"] = [[x, poly] for x in (-10, 0, 10)]
        result = analysis.measures_at_plane(hull, plane())
        self.exact(result["values"]["awp_m2"], 80)
        self.exact(result["values"]["it_m4"], 1040/3)
        self.exact(result["values"]["volume_m3"], 200)

    def test_asymmetric_waterplane_inertia_is_about_its_centroid(self):
        hull = prism()
        for _, poly in hull["offsets"]["stations"]:
            for point in poly:
                point[0] += 4
        result = analysis.measures_at_plane(hull, plane())
        self.exact(result["values"]["it_m4"], 360)
        self.exact(result["values"]["waterplane_centroid_y_m"], 4)

    def test_boundary_edge_contact_does_not_claim_one_sided_derivative(self):
        hull = prism()
        poly = [[-3, 0], [3, 0], [3, 4], [1, 4], [1, 1], [-1, 1], [-1, 4], [-3, 4]]
        hull["offsets"]["stations"] = [[x, poly] for x in (-10, 0, 10)]
        result = analysis.measures_at_plane(hull, plane(d=1))
        self.exact(result["values"]["awp_m2"], 120)
        self.assertIsNone(result["values"]["tpc_t_per_cm"])
        self.assertIsNone(result["values"]["bm_t_m"])
        self.assertTrue(any(d["code"] == "geometry.waterplane_contact" for d in result["diagnostics"]))
        self.assertFalse(result["upright_empirical_eligible"])

    def test_real_loaded_trim_is_retained_and_never_replaced_by_upright_geometry(self):
        hull = prism(n=81)
        state = {"complete_mass": True, "complete_cg": True, "diagnostics": [],
                 "input_fingerprint": "inclined-test", "values": {
                     "total_mass_t": 246, "lcg_m": 0.2, "tcg_m": 0.1, "kg_m": 1}}
        solved = stability.solve_loaded_equilibrium(hull, state)
        self.assertTrue(solved["converged"], solved)
        selected = analysis.measures_at_plane(hull, solved)
        self.exact(selected["plane"]["p"], solved["p"])
        self.exact(selected["plane"]["q"], solved["q"])
        self.exact(selected["values"]["volume_m3"], solved["volume_m3"])
        self.assertNotEqual(solved["p"], 0)
        self.assertFalse(selected["upright_empirical_eligible"])

    def test_grids_are_explicit_bounded_and_reject_boolean_nonfinite_values(self):
        for bad in ([], [1, 1], [2, 1], [True], [float("nan")], list(range(202)), "1,2"):
            for function in (analysis.bonjean_table, analysis.hydrostatic_table):
                with self.subTest(bad=bad, function=function.__name__), self.assertRaises(ValueError):
                    function(prism(), bad)
        for bad in (True, float("inf"), -1, 0):
            with self.subTest(density=bad), self.assertRaises(ValueError):
                analysis.measures_at_plane(prism(), plane(), rho_t_m3=bad)

    def test_invalid_geometry_is_rejected_by_shared_validated_adapter(self):
        for hull in ({"kind": "parameters"}, {"kind": "offsets_reference"}, prism()):
            if hull.get("kind") == "offsets":
                hull["offsets"]["stations"][1][1] = [[-3, 0], [3, 5], [3, 0], [-3, 5]]
            with self.subTest(hull=hull), self.assertRaises(ValueError):
                analysis.measures_at_plane(hull, plane())

    def test_reference_materialization_is_explicit_estimated_and_datum_consistent(self):
        original = parameters()
        hull = analysis.materialize_reference_hull(
            original, keel_offset_m=7, source={"title": "chosen parameter study"}, estimate=False,
            n_stations=41, n_section=48,
        )
        self.assertEqual(original, parameters())
        self.assertEqual(hull["kind"], "offsets")
        self.assertTrue(hull["estimate"])
        self.assertEqual(hull["source"]["input_source"], {"title": "chosen parameter study"})
        self.assertIs(hull["source"]["input_estimate"], False)
        self.assertEqual(hull["keel_offset_m"], 7)
        self.assertEqual(hull["source"]["parameters"]["depth_m"], 5)
        self.assertEqual(len(hull["source"]["content_sha256"]), 64)
        result = analysis.measures_at_plane(hull, plane(d=9))
        self.assertLess(abs(result["values"]["volume_m3"]-144)/144, 0.01)
        self.assertEqual(max(z for _, poly in hull["offsets"]["stations"] for _, z in poly), 12)
        self.assertEqual(json.loads(json.dumps(hull, allow_nan=False)), hull)

    def test_materialization_requires_complete_shape_depth_datum_and_provenance(self):
        for key in parameters():
            bad = parameters()
            bad.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                analysis.materialize_reference_hull(bad, keel_offset_m=0, source="study", estimate=True)
        for fields in ({"block_coeff": 0.9}, {"block_coeff": 0.8},
                       {"waterplane_coeff": 0.2}, {"depth_m": 1}, {"beam_m": True}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                analysis.materialize_reference_hull({**parameters(), **fields},
                                                    keel_offset_m=0, source="study", estimate=True)
        for kwargs in ({"keel_offset_m": None}, {"source": None}, {"estimate": "yes"},
                       {"n_stations": 2}, {"n_section": 10000}):
            args = {"keel_offset_m": 0, "source": "study", "estimate": True, **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analysis.materialize_reference_hull(parameters(), **args)

    def test_materialized_geometry_runs_real_loaded_solver_and_refines_below_one_percent(self):
        results = []
        for n, m in ((41, 48), (81, 96)):
            hull = analysis.materialize_reference_hull(parameters(), keel_offset_m=0,
                source="reference refinement", estimate=True, n_stations=n, n_section=m)
            results.append(analysis.measures_at_plane(hull, plane())["values"])
        for key in ("volume_m3", "awp_m2", "it_m4", "kb_m"):
            self.assertLess(abs(results[1][key]-results[0][key])/abs(results[1][key]), 0.01)
        state = {"complete_mass": True, "complete_cg": True, "diagnostics": [],
                 "input_fingerprint": "reference-test", "values": {
                     "total_mass_t": 147.6, "lcg_m": 0, "tcg_m": 0, "kg_m": 1}}
        solved = stability.solve_loaded_equilibrium(hull, state)
        self.assertTrue(solved["converged"], solved)
        self.assertLess(max(abs(v) for v in solved["residuals"]["scaled"].values()), 1e-6)

    def test_l0_box_retains_zero_and_null_and_traces_defaults(self):
        hull = {"lwl_m": 20, "beam_m": 6, "draught_m": 2, "block_coeff": 1,
                "waterplane_coeff": 1, "kg_m": 0, "displacement_normal_t": 0}
        result = analysis.parameterized_hydrostatics(hull)
        self.exact(result["values"]["displacement_volume_m3"], 240)
        self.exact(result["values"]["kb_m"], 1)
        self.exact(result["values"]["gm_m"], 2.5)
        self.assertEqual(result["reference_displacement"]["mass_t"], 0)
        self.assertIsNone(result["reference_displacement"]["deviation_pct"])
        self.assertTrue(any(d["code"] == "l0.zero_reference_mass" for d in result["diagnostics"]))
        self.assertTrue(any(a["field"] == "roll_gyration_coeff" and a["value"] == 0.38
                            and a["estimate"] is True for a in result["assumptions"]))
        hull["kg_m"] = None
        unknown = analysis.parameterized_hydrostatics(hull)
        self.assertIsNone(unknown["values"]["gm_m"])
        self.assertIsNone(unknown["inputs"]["kg_m"])
        self.assertIsNone(unknown["validity"]["historical_validated"])

    def test_l0_missing_input_and_infeasible_shape_have_explicit_status(self):
        self.assertEqual(analysis.parameterized_hydrostatics({})["status"], "unavailable")
        bad = {**parameters(), "block_coeff": 0.9}
        result = analysis.parameterized_hydrostatics(bad)
        self.assertEqual(result["status"], "model_limit")
        self.assertTrue(result["diagnostics"])
        self.assertIsNone(result["values"])
        for key in ("lwl_m", "kg_m", "waterplane_coeff", "roll_gyration_coeff"):
            for value in (True, float("nan"), float("inf")):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    analysis.parameterized_hydrostatics({**parameters(), key: value})

    def test_l0_optional_defaults_have_provenance_and_do_not_modify_input(self):
        hull = {"lwl_m": 20, "beam_m": 6, "draught_m": 2, "block_coeff": 0.6,
                "kg_m": 0, "waterplane_coeff": None, "waterplane_coeff_is_estimate": None}
        original = copy.deepcopy(hull)
        result = analysis.parameterized_hydrostatics(hull)
        self.assertEqual(hull, original)
        self.assertIsNone(result["inputs"]["waterplane_coeff"])
        self.assertTrue(any(a["field"] == "waterplane_coeff" and a["value"] == 0.8
                            and a["estimate"] is True for a in result["assumptions"]))
        self.assertTrue(result["trace"])
        self.assertTrue(result["diagnostics"])
        self.assertEqual(result["scenario"], "parameterized_design_waterline_not_loaded_equilibrium")

    def test_l0_null_sources_remain_unknown_without_blocking_geometry(self):
        result = analysis.parameterized_hydrostatics({**parameters(), "sources": None})
        self.assertEqual(result["status"], "completed")
        self.assertIsNone(result["inputs"]["sources"])
        self.assertTrue(any(d["code"] == "l0.sources_unknown" for d in result["diagnostics"]))

    def test_l0_rejects_present_malformed_fields_before_any_early_return(self):
        for base in ({}, {**parameters(), "block_coeff": 0.9}, parameters()):
            for bad in ({"sources": []}, {"kg_is_estimate": "invalid"},
                        {"block_coeff_is_estimate": 0}, {"waterplane_coeff_is_estimate": []},
                        {"displacement_unit_is_estimate": "false"},
                        {"draught_normal_m": 2, "draught_m": True}):
                with self.subTest(base=base, bad=bad), self.assertRaises(ValueError):
                    analysis.parameterized_hydrostatics({**base, **bad})

    def test_l0_diagnoses_empty_and_missing_direct_input_sources(self):
        hull = {**parameters(), "kg_m": 0, "displacement_normal_t": 0, "sources": {}}
        result = analysis.parameterized_hydrostatics(hull)
        self.assertEqual(result["inputs"]["sources"], {})
        self.assertIsNone(result["reference_displacement"]["source"])
        self.assertTrue(any(d["code"] == "l0.sources_unknown" for d in result["diagnostics"]))
        missing_paths = {d["path"] for d in result["diagnostics"] if d["code"] == "l0.input_source_unknown"}
        self.assertEqual(missing_paths, {
            "$.hull.sources.lwl_m", "$.hull.sources.beam_m", "$.hull.sources.draught_m",
            "$.hull.sources.block_coeff", "$.hull.sources.waterplane_coeff",
            "$.hull.sources.depth_m", "$.hull.sources.kg_m", "$.hull.sources.displacement_normal_t"})
        hull["sources"] = {"lwl_m": "survey", "kg_m": "", "beam_m": None}
        partial = analysis.parameterized_hydrostatics(hull)
        paths = {d["path"] for d in partial["diagnostics"] if d["code"] == "l0.input_source_unknown"}
        self.assertNotIn("$.hull.sources.lwl_m", paths)
        self.assertIn("$.hull.sources.kg_m", paths)
        self.assertIn("$.hull.sources.beam_m", paths)
        self.assertEqual(partial["inputs"], hull)

    def test_l0_shape_limit_diagnostic_points_to_hull(self):
        result = analysis.parameterized_hydrostatics({**parameters(), "block_coeff": 0.9})
        self.assertEqual(next(d for d in result["diagnostics"] if d["code"] == "l0.shape_limit")["path"],
                         "$.hull")

    def test_l0_default_estimate_flags_are_explicit_assumptions_and_diagnostics(self):
        hull = {**parameters(), "kg_m": 0, "kg_is_estimate": None,
                "block_coeff_is_estimate": False}
        result = analysis.parameterized_hydrostatics(hull)
        assumptions = {a["field"]: a for a in result["assumptions"]}
        for flag in ("waterplane_coeff_is_estimate", "kg_is_estimate", "displacement_unit_is_estimate"):
            self.assertIn(flag, assumptions)
            self.assertIs(assumptions[flag]["value"], True)
            self.assertIsNone(assumptions[flag]["original_value"])
            self.assertTrue(assumptions[flag]["source"])
            self.assertTrue(any(d["code"] == "l0.default_assumption" and d["path"] == f"$.hull.{flag}"
                                for d in result["diagnostics"]))
        self.assertNotIn("block_coeff_is_estimate", assumptions)
        self.assertIsNone(result["inputs"]["kg_is_estimate"])
        self.assertIs(next(t for t in result["trace"] if t["key"] == "kg_m")["estimate"], None)

    def test_deck_event_inputs_are_validated_even_when_all_samples_failed(self):
        deck = {"source": "deck plan", "estimate": False,
                "points": [{"id": "edge", "x_m": 0, "y_m": 3, "z_m": 4}]}
        samples = [{"angle_deg": 0, "equilibrium": {"converged": False}}]
        for bad in ([], {**deck, "source": None}, {**deck, "source": " "},
                    {**deck, "estimate": "invalid"}, {**deck, "points": []},
                    {**deck, "points": [{"id": "edge", "x_m": 0, "y_m": 3, "z_m": math.nan}]}):
            with self.subTest(deck=bad), self.assertRaises(ValueError):
                analysis.deck_immersion_events(bad, samples, keel_offset_m=0)
        for keel in (math.nan, math.inf, True, None):
            with self.subTest(keel=keel), self.assertRaises(ValueError):
                analysis.deck_immersion_events(deck, samples, keel_offset_m=keel)
        unknown = analysis.deck_immersion_events(None, samples, keel_offset_m=0)
        self.assertEqual(unknown["rows"][0]["status"], "unavailable")

    def test_l0_preserves_positive_reference_discrepancy_warning(self):
        result = analysis.parameterized_hydrostatics({**parameters(), "displacement_normal_t": 1000,
                                                      "displacement_unit_is_estimate": False})
        self.exact(result["reference_displacement"]["mass_t"], 1000)
        self.exact(result["reference_displacement"]["deviation_pct"], -85.24)
        self.assertTrue(any(d["code"] == "l0.legacy_warning" and "相差" in d["message"]
                            for d in result["diagnostics"]))
        reference_trace = next(item for item in result["trace"] if item["key"] == "displacement_input_t")
        self.assertIs(reference_trace["estimate"], False)

    def test_deck_clearance_uses_signed_normal_distance_and_keel_datum(self):
        deck = {"source": "deck plan", "estimate": False, "points": [
            {"id": "edge", "x_m": 4, "y_m": 2, "z_m": 3}]}
        for shift in (0, 7):
            result = analysis.deck_clearance(deck, plane(d=2+shift, p=0.1, q=0.2),
                                              keel_offset_m=shift)
            self.exact(result["minimum_clearance_m"], 0.2/math.sqrt(1.05))
            self.assertEqual(result["event_type"], "deck_geometry_only_not_downflooding")
        unknown = analysis.deck_clearance(None, plane(), keel_offset_m=0)
        self.assertEqual(unknown["status"], "unavailable")
        self.assertIsNone(unknown["minimum_clearance_m"])

    def test_deck_events_distinguish_contact_bracket_unknown_and_failed_sample(self):
        deck = {"source": "estimated deck", "estimate": True, "points": [
            {"id": "edge", "x_m": 0, "y_m": 3, "z_m": 3}]}
        def sample(angle, q, converged=True):
            return {"angle_deg": angle, "equilibrium": {**plane(q=q), "converged": converged}}
        result = analysis.deck_immersion_events(deck, [sample(0, 0), sample(30, 0.6)], keel_offset_m=0)
        self.assertEqual(result["events"][0]["kind"], "sampled_sign_bracket")
        self.assertEqual(result["events"][0]["bracket_deg"], [0, 30])
        self.assertIsNone(result["events"][0]["angle_deg"])
        contact = analysis.deck_immersion_events(deck, [sample(0, 0), sample(20, 1/3)], keel_offset_m=0)
        self.assertEqual(contact["events"][0]["kind"], "sampled_contact")
        unknown = analysis.deck_immersion_events(deck, [sample(0, 0), sample(10, 0.1)], keel_offset_m=0)
        self.assertEqual(unknown["endpoint"]["kind"], "dry_at_last_sample_event_unknown")
        failed = analysis.deck_immersion_events(deck,
            [sample(0, 0), sample(10, 0.1, False), sample(30, 0.6)], keel_offset_m=0)
        self.assertFalse(any(e["kind"] == "sampled_sign_bracket" for e in failed["events"]))
        self.assertEqual(failed["rows"][1]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
