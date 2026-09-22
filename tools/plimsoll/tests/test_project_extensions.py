"""Canonical optional inputs, persistent knowledge and effective field provenance."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loading
import project_io
import project_store


def project():
    return {"schema": "plimsoll-project-1", "id": "schema-study", "name": "型线与载荷", "weight_groups": [{
        "id": "hull", "items": [{"id": "plate.a[1]", "mass_t": 10, "x_m": 0,
        "y_m": 0, "kg_m": 2, "source": "base survey", "estimate": False,
        "uncertainty": {"mass_t": [9, 11], "kg_m": [1, 3]}}]}],
        "loading_conditions": [{"id": "normal"}, {"id": "custom", "overrides": {
            "plate.a[1]": {"mass_t": 12}}}]}


def fact(value, source="declared input", estimate=False):
    return {"value": value, "source": source, "estimate": estimate}


class OpeningKnowledgeTests(unittest.TestCase):
    def test_unknown_none_and_legacy_ambiguity_survive_chinese_roundtrip(self):
        fingerprints = []
        for extra, expected in (({}, "unknown"), ({"openings": []}, "legacy_ambiguous"),
                                ({"openings": [], "opening_definition": "supplied"}, "supplied")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                raw = {**project(), **extra}
                original = copy.deepcopy(raw)
                normalized = project_io.normalize_project(raw)
                self.assertEqual(normalized["opening_definition"], expected)
                path = Path(temp) / "中文项目.json"
                project_store.save(path, normalized)
                reopened = project_store.load(path)
                self.assertEqual(reopened, normalized)
                self.assertEqual(raw, original)
                fingerprints.append(loading.resolve_loading(reopened, "normal")["input_fingerprint"])
                codes = {d["code"] for d in project_io.validate_project(reopened)}
                if expected == "legacy_ambiguous":
                    self.assertIn("openings.legacy_ambiguous", codes)
        self.assertEqual(len(set(fingerprints)), 3)

    def test_new_and_migrated_projects_keep_unknown_opening_knowledge(self):
        self.assertEqual(project_io.new_project("Draft")["opening_definition"], "unknown")
        migrated = project_io.migrate_legacy({"schema": "plimsoll-ship-1", "name": "旧船", "hull": {}})
        self.assertEqual(migrated["opening_definition"], "unknown")

    def test_marker_consistency_and_nonempty_inference_are_validated(self):
        opening = {"id": "hatch", "x_m": 0, "y_m": 0, "z_m": 4, "open": True}
        self.assertEqual(project_io.normalize_project({**project(), "openings": [opening]})[
            "opening_definition"], "supplied")
        for marker in ("bad", None, True, "unknown", "legacy_ambiguous"):
            with self.subTest(marker=marker), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "openings": [opening], "opening_definition": marker})


class OverrideProvenanceTests(unittest.TestCase):
    def test_selected_mass_provenance_and_bounds_do_not_relabel_base_coordinates(self):
        raw = project()
        raw["loading_conditions"][1]["override_provenance"] = {"plate.a[1]": {"mass_t": {
            "source": "physical model", "estimate": True, "uncertainty": [11, 13]}}}
        original = copy.deepcopy(raw)
        state = loading.resolve_loading(raw, "custom")
        item = state["effective_items"][0]
        self.assertEqual(item["mass_t"], 12)
        self.assertEqual(item["uncertainty"], {"mass_t": [11, 13], "kg_m": [1, 3]})
        self.assertEqual(item["provenance"]["fields"]["mass_t"]["source"], "physical model")
        self.assertEqual(item["provenance"]["fields"]["kg_m"]["source"], "base survey")
        self.assertIs(item["provenance"]["fields"]["kg_m"]["estimate"], False)
        self.assertIs(item["estimate"], True)
        self.assertTrue(state["provenance"]["provenance_complete"])
        self.assertEqual(loading.resolve_loading(raw, "normal")["effective_items"][0]["mass_t"], 10)
        self.assertEqual(raw, original)

    def test_legacy_override_has_unknown_field_provenance_and_correct_diagnostic_path(self):
        result = loading.resolve_loading(project(), "custom")
        item = result["effective_items"][0]
        self.assertIsNone(item["provenance"]["fields"]["mass_t"]["source"])
        self.assertIsNone(item["estimate"])
        self.assertFalse(result["provenance"]["provenance_complete"])
        self.assertNotIn("mass_t", item["uncertainty"])
        diagnostic = next(d for d in result["diagnostics"] if d["code"] == "loading.uncertainty_override_cleared")
        self.assertEqual(diagnostic["path"], '$.loading_conditions[1].overrides["plate.a[1]"].mass_t')

    def test_override_metadata_cannot_be_orphaned_malformed_or_outside_nominal(self):
        for metadata in ([], {"ghost": {"mass_t": {}}}, {"plate.a[1]": {"kg_m": {}}},
                         {"plate.a[1]": {"mass_t": {"estimate": "yes"}}},
                         {"plate.a[1]": {"mass_t": {"source": [], "estimate": False}}},
                         {"plate.a[1]": {"mass_t": {"uncertainty": [1, 2]}}},
                         {"plate.a[1]": {"mass_t": {"uncertainty": [False, 12]}}}):
            raw = project()
            raw["loading_conditions"][1]["override_provenance"] = metadata
            with self.subTest(metadata=metadata), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(raw)

    def test_explicit_null_override_provenance_remains_unknown(self):
        raw = project()
        raw["loading_conditions"][1]["override_provenance"] = {"plate.a[1]": {
            "mass_t": {"source": None, "estimate": None}}}
        normalized = project_io.normalize_project(raw)
        self.assertEqual(normalized["loading_conditions"][1]["override_provenance"],
                         raw["loading_conditions"][1]["override_provenance"])
        self.assertIsNone(loading.resolve_loading(normalized, "custom")["effective_items"][0]["estimate"])

    def test_acceptance_record_is_bound_to_condition_value_and_valid_fingerprints(self):
        record = {"operation": "replace_weight_item_mass", "condition_id": "custom",
                  "source_system_id": "armour", "source_model_id": "plate-volume",
                  "formula": "mass=volume*density", "inputs": {"volume_m3": 1.5},
                  "input_provenance": {"volume_m3": {"source": "drawing", "estimate": True}},
                  "previous_mass_t": 10, "new_mass_t": 12,
                  "project_fingerprint": "a" * 64, "input_fingerprint": "b" * 64,
                  "request_fingerprint": "c" * 64}
        raw = project()
        raw["loading_conditions"][1]["override_provenance"] = {"plate.a[1]": {"mass_t": {
            "source": "physical model", "estimate": True, "acceptance": record}}}
        self.assertEqual(project_io.normalize_project(raw)["loading_conditions"][1][
            "override_provenance"]["plate.a[1]"]["mass_t"]["acceptance"], record)
        for patch in ({"new_mass_t": 11}, {"condition_id": "normal"}, {"request_fingerprint": "stale"},
                      {"new_mass_t": True}, {"inputs": {"volume_m3": True}}, {"input_provenance": {}},
                      {"previous_mass_t": None}, {"previous_mass_t": True},
                      {"previous_mass_t": -1}, {"previous_mass_t": float("inf")}):
            bad = copy.deepcopy(raw)
            bad["loading_conditions"][1]["override_provenance"]["plate.a[1]"]["mass_t"]["acceptance"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(bad)
        del record["previous_mass_t"]
        with self.assertRaises(project_io.ProjectValidationError):
            project_io.normalize_project(raw)
        record["previous_mass_t"] = 0
        self.assertEqual(project_io.normalize_project(raw)["loading_conditions"][1][
            "override_provenance"]["plate.a[1]"]["mass_t"]["acceptance"]["previous_mass_t"], 0)

    def test_mixed_estimated_and_unknown_fields_do_not_certify_provenance(self):
        raw = project()
        raw["weight_groups"][0]["items"][0]["estimate"] = True
        result = loading.resolve_loading(raw, "custom")
        self.assertIs(result["effective_items"][0]["estimate"], True)
        self.assertFalse(result["provenance"]["provenance_complete"])
        self.assertEqual(result["provenance"]["unverified_item_ids"], ["plate.a[1]"])

    def test_empty_override_source_cannot_certify_effective_provenance(self):
        raw = project()
        raw["loading_conditions"][1]["override_provenance"] = {"plate.a[1]": {
            "mass_t": {"source": "  ", "estimate": False}}}
        result = loading.resolve_loading(raw, "custom")
        self.assertFalse(result["provenance"]["provenance_complete"])
        self.assertIn("loading.override_provenance_unknown", [d["code"] for d in result["diagnostics"]])


class OptionalCoreFieldsTests(unittest.TestCase):
    def test_present_fuel_ownership_and_absence_require_provenance(self):
        for declaration in ({"weight_item_ids": ["plate.a[1]"]},
                            {"weight_item_ids": [], "absent": True}):
            for metadata in ({}, {"source": None, "estimate": None},
                             {"source": " ", "estimate": False},
                             {"source": {}, "estimate": True},
                             {"source": "ledger"}, {"source": "ledger", "estimate": 0}):
                raw = project()
                raw["systems"] = {"propulsion": {"status": "present", "fuel_bindings": {
                    "coal": {**declaration, **metadata}}}}
                with self.subTest(declaration=declaration, metadata=metadata):
                    errors = [d for d in project_io.validate_project(raw) if d["blocking"]]
                    self.assertTrue(any(d["path"].startswith(
                        "$.systems.propulsion.fuel_bindings.coal.") for d in errors))
                    with self.assertRaises(project_io.ProjectValidationError):
                        project_io.normalize_project(raw)
            for source, estimate in (("ledger", False), ({"document": "fuel plan"}, True)):
                raw["systems"]["propulsion"]["fuel_bindings"]["coal"] = {
                    **declaration, "source": source, "estimate": estimate}
                self.assertEqual(project_io.normalize_project(raw)["systems"], raw["systems"])
        raw = project()
        raw["systems"] = {"propulsion": {"status": "present"}}
        self.assertNotIn("fuel_bindings", project_io.normalize_project(raw)["systems"]["propulsion"])

    def test_system_leaf_cannot_hide_nested_systems_or_malformed_facts(self):
        for category, field in (("weapons", "calibre_m"), ("armour", "thickness_m"),
                                ("propulsion", "shafts")):
            for boundary in ({"status": "present"}, {"weight_item_ids": ["plate.a[1]"]},
                             {"mass_models": []}):
                for value in (True, 2, None):
                    raw = project()
                    raw["systems"] = {category: {**boundary, "group": {"main": {
                        "weight_item_ids": ["plate.a[1]"], "facts": {field: fact(value)}}}}}
                    with self.subTest(category=category, boundary=boundary, value=value):
                        errors = [d for d in project_io.validate_project(raw) if d["blocking"]]
                        self.assertTrue(any(d["path"] == f'$.systems.{category}["group"]["main"]'
                                            for d in errors))

    def test_fact_leaf_links_are_validated_without_reinterpreting_leaf_payloads(self):
        leaf = {"weight_item_ids": ["plate.a[1]"], "facts": {"calibre_m": fact(None, None, None)},
                "source": {"facts": "original survey metadata", "status": "archival"},
                "mass_models": []}
        raw = {**project(), "systems": {"weapons": {"main": leaf}}}
        self.assertEqual(project_io.normalize_project(raw)["systems"], raw["systems"])
        for ids in (None, "plate.a[1]", [True], ["ghost"], ["plate.a[1]", "plate.a[1]"]):
            bad = copy.deepcopy(raw)
            bad["systems"]["weapons"]["main"]["weight_item_ids"] = ids
            with self.subTest(ids=ids):
                errors = [d for d in project_io.validate_project(bad) if d["blocking"]]
                self.assertTrue(any(d["path"] == '$.systems.weapons["main"].weight_item_ids'
                                    for d in errors))

    def test_table_sha256_requires_lowercase_full_hex_identity(self):
        scenario = {"id": "taylor", "method": "taylor_gertler_source_axis_strict",
                    "attitude_policy": "strict_upright", "source": "source table", "estimate": True,
                    "table_id": "strict-source-table", "table_sha256": "abcdef0123456789" * 4}
        raw = {**project(), "resistance_scenarios": [scenario]}
        self.assertEqual(project_io.normalize_project(raw)["resistance_scenarios"], [scenario])
        for value in ("not-a-sha", "A" * 64, "g" * 64, "a" * 63, "a" * 65, "", None, True):
            with self.subTest(value=value), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "resistance_scenarios": [
                    {**scenario, "table_sha256": value}]})

    def test_optional_facts_keep_null_source_and_exact_selected_ledger_binding(self):
        raw = project()
        raw.update(metadata={"country": fact(None, None, None), "design_year": fact(1913)},
                   display_preferences={"length": "ft", "power": "shp"})
        raw["systems"] = {"propulsion": {"weight_item_ids": ["plate.a[1]"],
            "facts": {"shafts": fact(2), "design_power_kw": fact(None, None, None)},
            "fuel_bindings": {"coal": {"weight_item_ids": ["plate.a[1]"], "source": "fuel study", "estimate": True},
                              "oil": {"weight_item_ids": [], "absent": True, "source": "none declared", "estimate": False}}}}
        normalized = project_io.normalize_project(raw)
        self.assertEqual(normalized["metadata"], raw["metadata"])
        self.assertEqual(normalized["systems"], raw["systems"])
        self.assertEqual(normalized["units"]["length"], "m")
        self.assertTrue(any(d["code"] == "extension.provenance_unknown" for d in project_io.validate_project(raw)))
        self.assertEqual(loading.resolve_loading(raw, "custom")["values"]["total_mass_t"], 12)

    def test_optional_numeric_guards_unknown_fields_and_wrong_units_reject(self):
        for bad in ({"metadata": {"design_year": fact(True)}},
                    {"metadata": {"country": fact(3)}}, {"metadata": {"year": fact(1913)}},
                    {"display_preferences": {"length": "kg"}},
                    {"systems": {"propulsion": {"weight_item_ids": [], "facts": {"shafts": fact(1.5)}}}},
                    {"systems": {"weapons": {"main": {"weight_item_ids": [], "facts": {"calibre_m": fact(True)}}}}},
                    {"metadata": {"design_year": {"value": 1913, "source": [], "estimate": False}}}):
            with self.subTest(bad=bad), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), **bad})
        for value in (float("nan"), float("inf"), -1, True):
            raw = project()
            raw["systems"] = {"propulsion": {"weight_item_ids": [], "facts": {"design_power_kw": fact(value)}}}
            with self.subTest(value=value), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(raw)

    def test_fuel_binding_rejects_unknown_duplicate_and_undeclared_empty_ownership(self):
        for fuels in ({"coal": {"weight_item_ids": ["ghost"]}},
                      {"coal": {"weight_item_ids": []}},
                      {"coal": {"weight_item_ids": ["plate.a[1]", "plate.a[1]"]}},
                      {"coal": {"weight_item_ids": ["plate.a[1]"]}, "oil": {"weight_item_ids": ["plate.a[1]"]}},
                      {"coal": {"weight_item_ids": ["plate.a[1]"], "absent": True}}):
            for binding in fuels.values():
                binding.update(source="fuel allocation", estimate=True)
            raw = project()
            raw["systems"] = {"propulsion": {"weight_item_ids": [], "fuel_bindings": fuels}}
            with self.subTest(fuels=fuels), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(raw)

    def test_deck_segments_reference_points_and_validate_present_coordinates(self):
        deck = {"source": None, "estimate": None, "points": [
            {"id": "aft", "x_m": -5, "y_m": 2, "z_m": 4},
            {"id": "fore", "x_m": 5, "y_m": 2, "z_m": None}],
            "segments": [{"id": "main", "aft_point_id": "aft", "fore_point_id": "fore"}]}
        raw = {**project(), "deck": deck}
        self.assertEqual(project_io.normalize_project(raw)["deck"], deck)
        for bad in ({**deck, "segments": [{"id": "main", "aft_point_id": "ghost", "fore_point_id": "fore"}]},
                    {**deck, "points": [{"id": "point", "x_m": True, "y_m": 0, "z_m": 4}]},
                    {**deck, "estimate": "unknown"}):
            with self.subTest(bad=bad), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "deck": bad})

    def test_historical_comparison_requires_condition_speed_and_compatible_unit(self):
        row = {"id": "trial", "quantity": "shaft_power_kw", "value": 100,
               "unit": "shp", "condition_id": "normal", "speed_kn": 10,
               "source": "trial", "estimate": False}
        raw = {**project(), "historical_comparisons": [row]}
        self.assertEqual(project_io.normalize_project(raw)["historical_comparisons"], [row])
        for patch in ({"condition_id": "missing"}, {"speed_kn": True}, {"unit": "t"},
                      {"speed_kn": None}, {"quantity": "mystery"}, {"value": False}):
            with self.subTest(patch=patch), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "historical_comparisons": [{**row, **patch}]})

    def test_resistance_scenario_has_explicit_choices_and_no_shape_defaults(self):
        scenario = {"id": "study", "method": "holtrop_mennen_1982", "source": "declared approximation",
                    "estimate": True, "attitude_policy": "selected_plane_longitudinal_trim_proxy_v1",
                    "inputs": {"c_stern": 0, "bulb_area_m2": None},
                    "input_provenance": {"c_stern": {"source": "declared stern", "estimate": True}},
                    "qpc": fact(0.55, "declared efficiency", True)}
        raw = {**project(), "resistance_scenarios": [scenario]}
        saved = project_io.normalize_project(raw)["resistance_scenarios"][0]
        self.assertEqual(saved, scenario)
        self.assertNotIn("appendages", saved["inputs"])
        for patch in ({"method": "automatic"}, {"source": None}, {"estimate": None},
                      {"inputs": {"c_stern": True}}, {"qpc": fact(0)},
                      {"input_provenance": {}}, {"inputs": {"volume_m3": 5}}):
            with self.subTest(patch=patch), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "resistance_scenarios": [{**scenario, **patch}]})

    def test_endurance_scenario_preserves_unknown_burn_and_rejects_optional_positive_stream(self):
        row = {"id": "cruise", "method": "steady_simultaneous_fuel_consumption", "speed_kn": 10,
               "power_kw": 1000, "source": "study", "estimate": True, "fuels": {
                   "coal": {"required": True, "burn_t_per_day": None, "reserve_t": 0},
                   "oil": {"required": False, "burn_t_per_day": 0, "reserve_t": 0}}}
        self.assertEqual(project_io.normalize_project({**project(), "endurance_scenarios": [row]})[
            "endurance_scenarios"], [row])
        for patch in ({"required": False, "burn_t_per_day": 2, "reserve_t": 0},
                      {"required": True, "burn_t_per_day": True, "reserve_t": 0},
                      {"required": "yes", "burn_t_per_day": 0, "reserve_t": 0}):
            bad = copy.deepcopy(row)
            bad["fuels"]["coal"] = patch
            with self.subTest(patch=patch), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "endurance_scenarios": [bad]})

    def test_nested_shape_inputs_and_qpc_grid_validate_without_calculating(self):
        scenario = {"id": "bare", "method": "holtrop_mennen_1982", "attitude_policy": "strict_upright",
            "source": "engineering study", "estimate": True, "inputs": {
                "appendages": [], "bow_thruster": {"present": False}}, "input_provenance": {
                "appendages": {"source": "declared absent", "estimate": True},
                "bow_thruster": {"source": "declared absent", "estimate": True}},
            "qpc_sensitivity": {"values": [0.5, 0.6], "source": "sensitivity", "estimate": True}}
        self.assertEqual(project_io.normalize_project({**project(), "resistance_scenarios": [scenario]})[
            "resistance_scenarios"], [scenario])
        for key, value in (("appendages", [{"area_m2": True, "factor": 1.5}]),
                           ("appendages", [{"area_m2": 1, "factor": -1}]),
                           ("bow_thruster", {"present": False, "diameter_m": 1}),
                           ("bow_thruster", {"present": "no"})):
            bad = copy.deepcopy(scenario)
            bad["inputs"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "resistance_scenarios": [bad]})
        for values in ([0.6, 0.5], [0.5, 0.5], [True], [0], [float("inf")], list(range(1, 23))):
            bad = copy.deepcopy(scenario)
            bad["qpc_sensitivity"]["values"] = values
            with self.subTest(values=values), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project({**project(), "resistance_scenarios": [bad]})


if __name__ == "__main__":
    unittest.main()
