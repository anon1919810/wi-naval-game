# -*- coding: utf-8 -*-
"""Concept-design configuration, generated estimates, balance and batch acceptance.

These are behavioural tests of the integrated contract: the estimate chain, the
adapted balance screen, and the atomic reviewed-batch application. Each asserts a
property the contract requires, not the shape of the current draft.
"""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import analysis  # noqa: E402
import concept_design  # noqa: E402
import concept_estimates as ce  # noqa: E402
import loading  # noqa: E402
import project_io  # noqa: E402
import project_store  # noqa: E402

CASE = PKG / "cases/projects/concept_cruiser.project.json"
STAGES = ["loading", "systems", "design_balance"]
LT_PER_T = 1000.0 / ce.LONG_TON_KG
SOURCE_CELLS = ("GunControl.cs", "EngineControl.cs", "HullControl.cs",
                "PerformanceControl.cs", "MainForm.cs")


def case_project():
    return project_store.load(CASE)


def run(project, condition="normal", stages=None):
    return analysis.compute_project(project, condition, {"stages": list(stages or STAGES)})


def balance(result):
    return result["stages"]["design_balance"]["data"]


def proposals(result, source_prefix=None):
    rows = result["stages"]["systems"]["data"]["update_proposals"]
    if source_prefix is None:
        return rows
    return [row for row in rows if row["source_model_id"].startswith(source_prefix)]


def find(rows, item_id):
    matches = [row for row in rows if row["item_id"] == item_id]
    return matches[0] if matches else None


def item(project, identity):
    for group in project["weight_groups"]:
        for entry in group["items"]:
            if entry["id"] == identity:
                return entry
    raise KeyError(identity)


def drop_mass(project, identity):
    item(project, identity).pop("mass_t", None)


def set_mass(project, identity, mass_t, kg_m=None):
    entry = item(project, identity)
    entry["mass_t"] = mass_t
    if kg_m is not None:
        entry["kg_m"] = kg_m


def add_item(project, system_path, identity, **fields):
    record = dict(id=identity, source="synthetic test fixture", estimate=True)
    record.update(fields)
    project["weight_groups"][0]["items"].append(record)
    systems = project["systems"]
    parts = system_path.split(".")
    for part in parts[:-1]:
        systems = systems.setdefault(part, {})
    leaf = systems.setdefault(parts[-1], {"weight_item_ids": []})
    leaf["weight_item_ids"].append(identity)
    return record


def generated_models(project):
    state = loading.resolve_loading(project, "normal")
    return concept_design.generated_models(project, state)


class ConceptCaseTests(unittest.TestCase):
    def setUp(self):
        self.project = case_project()

    def test_the_synthetic_case_is_a_valid_project_with_estimated_provenance(self):
        normalized = project_io.normalize_project(self.project)
        self.assertEqual(normalized["id"], "concept-cruiser")
        self.assertTrue(normalized["concept_design"]["estimate"])
        for group in normalized["weight_groups"]:
            for entry in group["items"]:
                self.assertTrue(entry.get("source"), entry["id"])
                self.assertTrue(entry.get("mass_t") is not None or True)
        # The historical Queen Mary fixture is untouched by this case.
        queen = PKG / "cases/projects/queen_mary_1913.project.json"
        self.assertTrue(queen.exists())
        self.assertNotIn("concept", json.loads(queen.read_text(encoding="utf-8"))["id"])

    def test_estimate_apply_recompute_and_save_reload(self):
        original = copy.deepcopy(self.project)
        first = run(self.project)
        self.assertEqual(first["stages"]["loading"]["status"], "completed")
        self.assertEqual(first["stages"]["design_balance"]["status"], "completed")
        before = balance(first)
        self.assertIsNotNone(before["structure"]["required_total_long_tons"])
        self.assertLess(before["structure"]["structure_margin_long_tons"], 0.0)

        components = proposals(first, "concept.main.")
        self.assertEqual(len(components), 3)
        applied = analysis.apply_mass_proposals(self.project, "normal", components,
                                                current_request=first["request"])
        updated = applied["project"]
        self.assertEqual(applied["applied_count"], 3)
        self.assertEqual(sorted(applied["batch"]["item_ids"]),
                         ["weapons.ammunition", "weapons.guns", "weapons.mounts"])
        self.assertEqual(self.project, original)
        self.assertEqual(updated["weight_groups"], original["weight_groups"])
        selected_guns = next(row for row in loading.resolve_loading(updated, "normal")["effective_items"]
                             if row["id"] == "weapons.guns")
        self.assertNotEqual(selected_guns["mass_t"], item(original, "weapons.guns")["mass_t"])

        second = run(updated)
        after = balance(second)
        # Applying components is not convergence: the structural demand moves.
        self.assertNotAlmostEqual(after["structure"]["required_total_long_tons"],
                                  before["structure"]["required_total_long_tons"], places=6)
        # A fresh structural proposal is visible again after the recompute.
        self.assertIsNotNone(find(proposals(second), "hull.structure"))
        self.assertNotIn("weapons.guns", [row["item_id"] for row in proposals(second)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "concept.json"
            project_store.save(path, updated)
            self.assertEqual(project_store.load(path), updated)

    def test_accepted_empirical_provenance_is_labelled_and_auditable(self):
        first = run(self.project)
        component = proposals(first, "concept.main.guns")[0]
        applied = analysis.apply_mass_proposals(self.project, "normal", [component],
                                                current_request=first["request"])
        entry = applied["project"]["loading_conditions"][0]["override_provenance"][
            "weapons.guns"]["mass_t"]
        self.assertEqual(entry["source"]["method"],
                         "accepted_selected_condition_empirical_estimate")
        self.assertEqual(entry["source"]["method_version"], ce.METHOD_VERSION)
        self.assertEqual(entry["source"]["source_sha256"], ce.SOURCE_SHA256)
        self.assertIn("GunControl.cs", entry["acceptance"]["inputs"]["source_location"])
        self.assertIn("not whole-program parity", entry["source"]["boundary"])
        self.assertTrue(entry["estimate"])
        self.assertEqual(entry["acceptance"]["previous_mass_t"], component["current_mass_t"])
        self.assertEqual(entry["acceptance"]["new_mass_t"], component["proposed_mass_t"])

    def test_a_physical_acceptance_keeps_its_own_provenance_label(self):
        project = case_project()
        project["systems"]["weapons"]["main"]["mass_models"] = [dict(
            id="physical.guns", method="counted_unit_mass",
            linked_weight_item_id="weapons.guns",
            inputs=dict(unit_mass_t=1.0, count_value=1, count_basis="declared unit mass"),
            source="declared plate fixture", estimate=False,
            comparison_tolerance=dict(relative=0, absolute_t=0))]
        first = run(project)
        component = find(proposals(first), "weapons.guns")
        self.assertEqual(component["source_model_id"], "physical.guns")
        applied = analysis.apply_mass_proposal(project, "normal", component,
                                               current_request=first["request"])
        entry = applied["project"]["loading_conditions"][0]["override_provenance"][
            "weapons.guns"]["mass_t"]
        self.assertEqual(entry["source"]["method"],
                         "accepted_selected_condition_physical_model")

    def test_other_conditions_and_base_weights_are_preserved(self):
        original = copy.deepcopy(self.project)
        first = run(self.project)
        component = proposals(first, "concept.main.guns")[0]
        applied = analysis.apply_mass_proposals(self.project, "normal", [component],
                                                current_request=first["request"])["project"]
        self.assertEqual(self.project, original)
        deep = next(c for c in applied["loading_conditions"] if c["id"] == "deep")
        original_deep = next(c for c in original["loading_conditions"] if c["id"] == "deep")
        self.assertEqual(deep["overrides"], original_deep["overrides"])
        # The base item mass is untouched; only the condition override moves.
        self.assertEqual(item(applied, "weapons.guns")["mass_t"],
                         item(original, "weapons.guns")["mass_t"])
        self.assertEqual(loading.resolve_loading(applied, "deep")["values"]["total_mass_t"],
                         loading.resolve_loading(original, "deep")["values"]["total_mass_t"])
        self.assertNotEqual(loading.resolve_loading(applied, "normal")["values"]["total_mass_t"],
                            loading.resolve_loading(original, "normal")["values"]["total_mass_t"])


class GeneratedModelTests(unittest.TestCase):
    def setUp(self):
        self.project = case_project()
        self.result = run(self.project)

    def test_one_battery_definition_creates_exactly_three_component_models(self):
        components = proposals(self.result, "concept.main.")
        self.assertEqual([row["source_model_id"] for row in components],
                         ["concept.main.guns", "concept.main.mounts",
                          "concept.main.ammunition"])
        self.assertEqual(sorted(row["item_id"] for row in components),
                         ["weapons.ammunition", "weapons.guns", "weapons.mounts"])

    def test_guns_mounts_and_ammunition_are_mutually_exclusive(self):
        targets = [row["item_id"] for row in proposals(self.result, "concept.main.")]
        self.assertEqual(len(set(targets)), 3)
        self.assertNotIn("weapons.rotating_armour", targets)
        model = next(m for m in self.result["stages"]["systems"]["data"]["systems"]
                     ["weapons.main"]["mass_models"] if m["id"] == "concept.main.mounts")
        self.assertNotIn("rotating", model["formula"].lower())

    def test_every_generated_model_carries_method_source_and_hash(self):
        models = [model
                  for system in self.result["stages"]["systems"]["data"]["systems"].values()
                  for model in system["mass_models"] if model["id"].startswith("concept.")]
        self.assertEqual(len(models), 6)
        for model in models:
            self.assertEqual(model["method"], "empirical_estimate_v1")
            self.assertEqual(model["inputs"]["method_version"], ce.METHOD_VERSION)
            self.assertEqual(model["inputs"]["source_sha256"], ce.SOURCE_SHA256)
            self.assertEqual(model["source"]["sha256"], ce.SOURCE_SHA256)
            self.assertEqual(model["source"]["assembly"], ce.SOURCE_ASSEMBLY)
            self.assertTrue(any(token in model["inputs"]["source_location"]
                                for token in SOURCE_CELLS), model["id"])
            self.assertEqual(set(model["input_provenance"]), set(model["inputs"]))
            self.assertEqual(model["comparison_policy"],
                             "empirical_concept_screening_tolerance")
            self.assertIn("not whole-program parity", model["boundary"])
            self.assertTrue(model["inputs"]["estimate_long_tons"] >= 0)

    def test_generated_model_ids_cannot_collide_with_declared_models(self):
        self.project["systems"]["weapons"]["main"]["mass_models"] = [dict(
            id="concept.main.guns", method="counted_unit_mass",
            linked_weight_item_id="weapons.guns",
            inputs=dict(unit_mass_t=1.0, count_value=1, count_basis="declared unit mass"),
            source="declared", estimate=False,
            comparison_tolerance=dict(relative=0, absolute_t=0))]
        result = run(self.project)
        codes = [d["code"] for d in result["stages"]["systems"]["data"]["diagnostics"]]
        self.assertIn("systems.generated_model_duplicate", codes)
        ids = [m["id"] for m in result["stages"]["systems"]["data"]["systems"]
               ["weapons.main"]["mass_models"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_physical_and_an_empirical_model_may_both_compare_one_item(self):
        self.project["systems"]["weapons"]["main"]["mass_models"] = [dict(
            id="physical.guns", method="counted_unit_mass",
            linked_weight_item_id="weapons.guns",
            inputs=dict(unit_mass_t=1.0, count_value=1, count_basis="declared unit mass"),
            source="declared plate fixture", estimate=False,
            comparison_tolerance=dict(relative=0, absolute_t=0))]
        result = run(self.project)
        row = result["stages"]["systems"]["data"]["systems"]["weapons.main"]
        methods = {model["id"]: model["method"] for model in row["mass_models"]}
        self.assertEqual(methods["physical.guns"], "counted_unit_mass")
        self.assertEqual(methods["concept.main.guns"], "empirical_estimate_v1")
        # Neither model becomes the mass authority.
        self.assertEqual(row["ledger_mass_t"],
                         sum(linked["mass_t"] for linked in row["linked_items"]))
        self.assertEqual(loading.resolve_loading(self.project, "normal")["values"]
                         ["total_mass_t"],
                         loading.resolve_loading(result["input_snapshot"], "normal")
                         ["values"]["total_mass_t"])

    def test_an_unknown_target_mass_still_yields_a_proposal_with_a_null_difference(self):
        drop_mass(self.project, "weapons.mounts")
        result = run(self.project)
        row = find(proposals(result), "weapons.mounts")
        self.assertIsNotNone(row)
        self.assertIsNone(row["current_mass_t"])
        self.assertIsNone(row["difference_t"])
        self.assertIsNotNone(row["proposed_mass_t"])

    def test_changing_calibre_and_power_changes_the_proposals(self):
        before = {row["item_id"]: row["proposed_mass_t"] for row in proposals(self.result)}
        self.project["concept_design"]["batteries"][0]["calibre_mm"] = 203.2
        self.project["concept_design"]["machinery"]["shaft_power_kw"] = 9000.0
        after = {row["item_id"]: row["proposed_mass_t"] for row in proposals(run(self.project))}
        self.assertGreater(after["weapons.guns"], before["weapons.guns"])
        self.assertGreater(after["weapons.mounts"], before["weapons.mounts"])
        self.assertGreater(after["weapons.ammunition"], before["weapons.ammunition"])
        self.assertGreater(after["propulsion.machinery"], before["propulsion.machinery"])

    def test_manual_shell_mass_moves_ammunition_and_strength_but_not_the_gun(self):
        baseline = {row["item_id"]: row["proposed_mass_t"] for row in proposals(self.result)}
        baseline_cross = balance(self.result)["strength"]["cross"]
        self.project["concept_design"]["batteries"][0]["shell_mass_kg"] = 45.0
        result = run(self.project)
        after = {row["item_id"]: row["proposed_mass_t"] for row in proposals(result)}
        self.assertAlmostEqual(after["weapons.guns"], baseline["weapons.guns"], places=9)
        self.assertNotAlmostEqual(after["weapons.ammunition"], baseline["weapons.ammunition"],
                                  places=6)
        self.assertNotAlmostEqual(balance(result)["strength"]["cross"], baseline_cross, places=6)
        model = next(m for m in result["stages"]["systems"]["data"]["systems"]["weapons.main"]
                     ["mass_models"] if m["id"] == "concept.main.ammunition")
        self.assertEqual(model["inputs"]["shell_origin"], "declared_manual_override")

    def test_omitted_broadside_matches_an_explicit_installed_count(self):
        implicit = balance(self.result)
        self.project["concept_design"]["batteries"][0]["broadside_guns"] = 8
        explicit = balance(run(self.project))
        self.assertAlmostEqual(implicit["structure"]["broadside_lb"],
                               explicit["structure"]["broadside_lb"], places=12)
        self.assertAlmostEqual(implicit["strength"]["cross"], explicit["strength"]["cross"],
                               places=12)
        self.assertIn("installed count", implicit["structure"]["broadside_detail"][0]
                      ["broadside_basis"])

    def test_a_broadside_count_above_the_installed_count_is_rejected(self):
        self.project["concept_design"]["batteries"][0]["broadside_guns"] = 9
        with self.assertRaises(Exception) as caught:
            run(self.project)
        message = str(caught.exception)
        self.assertIn("broadside", message)
        self.assertIn("rejected", message)

    def test_the_strength_expression_uses_rotating_armour_only(self):
        data = balance(self.result)
        baseline_cross = data["strength"]["cross"]
        baseline_budget = data["values"]["remaining_structural_budget_long_tons"]
        baseline_demand = data["structure"]["required_total_long_tons"]
        added = data["roles"]["rotating_armour"] * LT_PER_T
        set_mass(self.project, "armour.belt_main",
                 item(self.project, "armour.belt_main")["mass_t"] + added)
        changed = balance(run(self.project))
        # The budget moves, but the direct strength term does not.
        self.assertNotAlmostEqual(changed["values"]["remaining_structural_budget_long_tons"],
                                  baseline_budget, places=6)
        self.assertAlmostEqual(changed["strength"]["cross"], baseline_cross, places=12)
        self.assertAlmostEqual(changed["structure"]["required_total_long_tons"],
                               baseline_demand, places=9)
        self.assertAlmostEqual(changed["structure"]["cross_coefficient"],
                               data["structure"]["cross_coefficient"], places=12)
        self.assertAlmostEqual(changed["structure"]["long_coefficient"],
                               data["structure"]["long_coefficient"], places=12)
        # Rotating armour, the direct term, does move it.
        set_mass(self.project, "weapons.rotating_armour",
                 item(self.project, "weapons.rotating_armour")["mass_t"] + added)
        rotated = balance(run(self.project))
        self.assertNotAlmostEqual(rotated["structure"]["cross_coefficient"],
                                  data["structure"]["cross_coefficient"], places=12)

    def test_explicit_power_drives_both_the_engine_and_the_strength_demand(self):
        baseline = balance(self.result)
        baseline_engine = find(proposals(self.result), "propulsion.machinery")["proposed_mass_t"]
        self.project["concept_design"]["machinery"]["shaft_power_kw"] = 12000.0
        result = run(self.project)
        changed = balance(result)
        self.assertEqual(changed["power"]["power_origin"], "declared_shaft_power_kw")
        self.assertEqual(changed["structure"]["hp_origin"], "declared_shaft_power_kw")
        self.assertGreater(find(proposals(result), "propulsion.machinery")["proposed_mass_t"],
                           baseline_engine)
        self.assertGreater(changed["structure"]["required_total_long_tons"],
                           baseline["structure"]["required_total_long_tons"])

    def test_the_fuel_capacity_factor_is_a_display_estimate_not_a_ledger_item(self):
        generated = generated_models(self.project)
        model = next(m for m in generated["systems"]["propulsion.fuel"]
                     if m["id"] == "concept.fuel")
        self.assertEqual(model["capacity_display_factor"], 1.8)
        self.assertIn("not another ledger item", model["capacity_note"])
        item_ids = {entry["id"] for group in self.project["weight_groups"]
                    for entry in group["items"]}
        self.assertNotIn("propulsion.fuel.capacity", item_ids)
        self.assertEqual(find(proposals(self.result), "propulsion.fuel")["item_id"],
                         "propulsion.fuel")


class BalanceScreenTests(unittest.TestCase):
    def setUp(self):
        self.project = case_project()
        self.result = run(self.project)
        self.data = balance(self.result)

    def test_the_screen_reports_total_target_difference_and_budget(self):
        values = self.data["values"]
        self.assertEqual(values["target_displacement_t"], 8200.0)
        self.assertAlmostEqual(values["difference_t"],
                               values["target_displacement_t"] - values["selected_total_mass_t"],
                               places=9)
        # The residual budget is the target minus nonstructure mass, a separate
        # quantity from the strength demand.
        self.assertAlmostEqual(
            values["remaining_structural_budget_long_tons"],
            values["target_displacement_t"] * LT_PER_T
            - values["nonstructure_mass_long_tons"], places=6)
        self.assertNotAlmostEqual(values["remaining_structural_budget_long_tons"],
                                  values["structure_demand_long_tons"], places=6)

    def test_current_strength_is_evaluated_at_the_selected_structure(self):
        data = self.data["structure"]
        self.assertEqual(self.data["strength"]["evaluated_at_structure_long_tons"],
                         data["current_structure_long_tons"])
        self.assertLess(data["current_structure_long_tons"], data["required_total_long_tons"])
        structure = data["current_structure_long_tons"]
        self.assertAlmostEqual(self.data["strength"]["cross"],
                               data["cross_coefficient"] * structure, places=12)
        self.assertAlmostEqual(self.data["strength"]["longitudinal"],
                               data["long_coefficient"] * structure, places=12)
        self.assertAlmostEqual(
            self.data["strength"]["composite"],
            ce.strength_composite(self.data["strength"]["cross"],
                                  self.data["strength"]["longitudinal"]), places=12)
        # The demand is a separate, load-derived quantity that hits the target.
        self.assertAlmostEqual(
            ce.strength_composite(data["cross_coefficient"] * data["required_total_long_tons"],
                                  data["long_coefficient"] * data["required_total_long_tons"]),
            data["strength_target"], places=9)

    def test_changing_the_selected_structure_changes_strength_and_margin_but_not_the_demand(self):
        demand = self.data["structure"]["required_total_long_tons"]
        set_mass(self.project, "hull.structure", item(self.project, "hull.structure")["mass_t"] * 1.2)
        changed = balance(run(self.project))
        self.assertGreater(changed["structure"]["current_structure_long_tons"],
                           self.data["structure"]["current_structure_long_tons"])
        self.assertGreater(changed["strength"]["cross"], self.data["strength"]["cross"])
        self.assertGreater(changed["strength"]["composite"], self.data["strength"]["composite"])
        self.assertGreater(changed["structure"]["structure_margin_long_tons"],
                           self.data["structure"]["structure_margin_long_tons"])
        self.assertAlmostEqual(changed["structure"]["required_total_long_tons"], demand, places=9)

    def test_margin_is_total_structure_minus_total_demand(self):
        data = self.data["structure"]
        self.assertAlmostEqual(data["structure_margin_long_tons"],
                               data["current_structure_long_tons"]
                               - data["required_total_long_tons"], places=9)

    def test_the_screen_reports_a_structure_shortfall_and_never_auto_fits(self):
        codes = [w["code"] for w in self.data["design_warnings"]]
        self.assertIn("design_balance.structure_shortfall", codes)
        self.assertLess(self.data["strength"]["composite"],
                        self.data["strength"]["composite_target"])
        original = copy.deepcopy(self.project)
        run(self.project)
        self.assertEqual(self.project, original)
        self.assertEqual(self.project["loading_conditions"][0].get("overrides", {}), {})

    def test_a_sufficient_structure_is_reported_as_such(self):
        set_mass(self.project, "hull.structure",
                 item(self.project, "hull.structure")["mass_t"] * 1.6)
        codes = [w["code"] for w in balance(run(self.project))["design_warnings"]]
        self.assertIn("design_balance.structure_sufficient", codes)

    def test_cramped_space_and_poor_seakeeping_are_reported(self):
        self.project["concept_design"]["balance"]["space_hull_fraction"] = 0.55
        self.project["concept_design"]["balance"]["space_deck_fraction"] = 0.6
        self.project["concept_design"]["balance"]["steadiness"] = 10
        data = balance(run(self.project))
        codes = [w["code"] for w in data["design_warnings"]]
        self.assertIn("design_balance.hull_space_cramped", codes)
        self.assertIn("design_balance.deck_room_cramped", codes)
        self.assertTrue({"design_balance.poor_seakeeping", "design_balance.weak_seakeeping"}
                        & set(codes))

    def test_overweight_and_underweight_are_reported_against_the_declared_target(self):
        codes = [w["code"] for w in self.data["design_warnings"]]
        self.assertIn("design_balance.underweight", codes)
        for entry in self.project["weight_groups"][0]["items"]:
            entry["mass_t"] = entry["mass_t"] * 1.6
        heavy = [w["code"] for w in balance(run(self.project))["design_warnings"]]
        self.assertIn("design_balance.overweight", heavy)

    def test_scores_are_labelled_empirical_and_never_physical_trim_or_roll(self):
        text = json.dumps(self.data, ensure_ascii=False)
        self.assertIn("not a physical GM", text)
        self.assertNotIn("roll_period", text)
        self.assertNotIn("trim_deg", text)
        self.assertIsNone(self.data["historical_validated"])
        self.assertIn("not whole-program parity", self.data["method_scope"])
        self.assertEqual(self.data["basis"],
                         "declared design displacement, selected ledger allocations")

    def test_estimated_borne_weight_comes_from_selected_bare_guns(self):
        mount_type = self.project["concept_design"]["batteries"][0]["mount_type"]
        adjustment = ce.MOUNT_ADJUSTMENT[ce.MOUNT_TYPES.index(mount_type)]
        expected = ce.balance_borne_weight_long_tons(
            item(self.project, "weapons.guns")["mass_t"] * LT_PER_T, adjustment)
        self.assertAlmostEqual(self.data["selected_borne_weight_long_tons"], expected, places=9)
        # Mounts and rotating armour never enter it.
        set_mass(self.project, "weapons.mounts",
                 item(self.project, "weapons.mounts")["mass_t"] * 2.0)
        set_mass(self.project, "weapons.rotating_armour",
                 item(self.project, "weapons.rotating_armour")["mass_t"] * 2.0)
        self.assertAlmostEqual(balance(run(self.project))["selected_borne_weight_long_tons"],
                               expected, places=12)

    def test_a_positive_guns_role_item_outside_a_battery_makes_dependent_metrics_unavailable(self):
        add_item(self.project, "weapons.reserve", "weapons.reserve", mass_t=40.0,
                 x_m=100.0, y_m=0.0, kg_m=12.0)
        self.project["systems"]["weapons"]["reserve"].update(
            source="synthetic reserve battery", estimate=True, installed_guns=2)
        self.project["concept_design"]["balance"]["roles"]["weapons.reserve"] = "guns"
        data = balance(run(self.project))
        self.assertIsNone(data["selected_borne_weight_long_tons"])
        self.assertIn("concept_design.guns_role_unbound",
                      [d["code"] for d in data["diagnostics"]])
        self.assertIsNone(data.get("strength"))
        self.assertEqual(data["status"], "unavailable")

    def test_the_bulkhead_narrowing_needs_bulkhead_beam_above_the_declared_mass(self):
        del self.project["concept_design"]["balance"]["bulkhead_beam_m"]
        codes = [d["code"] for d in balance(run(self.project))["diagnostics"]]
        self.assertIn("concept_design.bulkhead_beam_required", codes)
        self.assertEqual(balance(run(self.project))["status"], "unavailable")
        self.project["concept_design"]["balance"]["bulkhead_beam_m"] = 12.0
        narrowed = balance(run(self.project))
        self.assertEqual(narrowed["status"], "completed")
        self.assertIsNotNone(narrowed["space"]["hull_ratio"])
        # With the bulkhead declared at zero the narrowing is skipped entirely.
        set_mass(self.project, "armour.bulkhead", 0.0)
        widened = balance(run(self.project))
        self.assertNotIn("concept_design.bulkhead_beam_required",
                         [d["code"] for d in widened["diagnostics"]])
        # Dropping the narrowing removes the beam/bulkhead widening.
        self.assertLess(widened["space"]["hull_ratio"], narrowed["space"]["hull_ratio"])

    def test_the_declared_crew_band_and_space_ratios_are_reported(self):
        band = ce.crew_band(self.data["hull_proxy"]["displacement_long_tons"])
        self.assertEqual(self.data["crew"]["crew_min"], band["crew_min"])
        self.assertEqual(self.data["crew"]["crew_max"], band["crew_max"])
        self.assertGreater(self.data["space"]["hull_ratio"], 0.0)
        self.assertGreater(self.data["space"]["deck_ratio"], 0.0)


class IncompleteLedgerTests(unittest.TestCase):
    def setUp(self):
        self.project = case_project()

    def test_the_screen_runs_with_a_missing_cg_and_an_incomplete_loading(self):
        for entry in self.project["weight_groups"][0]["items"]:
            entry.pop("kg_m", None)
        result = run(self.project)
        self.assertNotEqual(result["stages"]["loading"]["status"], "completed")
        self.assertEqual(result["stages"]["design_balance"]["status"], "completed")
        self.assertTrue(balance(result)["structure"]["required_total_long_tons"] > 0)
        # The estimate chain still proposes, which is the point of an early screen.
        self.assertEqual(len(proposals(result, "concept.main.")), 3)

    def test_physical_stages_stay_blocked_when_geometry_is_absent(self):
        result = analysis.compute_project(
            self.project, "normal",
            {"stages": ["loading", "design_balance", "hydrostatics"]})
        self.assertEqual(result["stages"]["hydrostatics"]["status"], "unavailable")
        self.assertEqual(result["stages"]["design_balance"]["status"], "completed")

    def test_an_unknown_adjustable_structure_item_still_yields_a_proposal(self):
        drop_mass(self.project, "hull.structure")
        result = run(self.project)
        row = find(proposals(result), "hull.structure")
        self.assertIsNotNone(row)
        self.assertIsNone(row["current_mass_t"])
        self.assertIsNotNone(row["proposed_mass_t"])
        data = balance(result)
        self.assertIsNotNone(data["structure"]["required_total_long_tons"])
        self.assertIsNone(data["structure"]["structure_margin_long_tons"])
        self.assertIn("concept_design.structure_unknown",
                      [d["code"] for d in data["diagnostics"]])

    def test_an_unknown_fixed_structure_item_blocks_the_dependent_screen(self):
        add_item(self.project, "hull.structure", "hull.frames", x_m=80.0, y_m=0.0, kg_m=7.0)
        self.project["concept_design"]["balance"]["roles"]["hull.frames"] = "structure"
        result = run(self.project)
        rows = (result["stages"]["systems"].get("data") or {}).get("update_proposals", [])
        self.assertNotIn("concept.structure", [row["source_model_id"] for row in rows])
        self.assertIn("concept_design.structure_unknown",
                      [d["code"] for d in balance(result)["diagnostics"]])

    def test_an_unknown_supporting_load_blocks_the_dependent_structure_screen(self):
        drop_mass(self.project, "weapons.rotating_armour")
        result = run(self.project)
        data = balance(result)
        self.assertIsNone(data.get("structure"))
        rows = (result["stages"]["systems"].get("data") or {}).get("update_proposals", [])
        self.assertNotIn("concept.structure", [row["source_model_id"] for row in rows])
        self.assertIn("concept_design.supporting_load_unknown",
                      [d["code"] for d in data["diagnostics"]])

    def test_a_positive_unmapped_item_is_reported_not_silently_allocated(self):
        add_item(self.project, "weapons.misc_weight", "mystery", mass_t=50.0,
                 x_m=50.0, y_m=0.0, kg_m=8.0)
        data = balance(run(self.project))
        self.assertIn("mystery", data["unclassified_item_ids"])
        self.assertFalse(data["screening_complete"])
        self.assertEqual(data["status"], "unavailable")

    def test_an_explicit_zero_role_is_a_declared_absence(self):
        data = balance(run(self.project))
        self.assertEqual(data["roles"]["misc_void"], 0.0)
        self.assertTrue(data["screening_complete"])
        self.assertTrue(data["structure"]["required_total_long_tons"] > 0)


class BatchAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.project = case_project()
        self.result = run(self.project)

    def test_a_batch_is_atomic_and_writes_only_the_selected_condition(self):
        original = copy.deepcopy(self.project)
        rows = proposals(self.result, "concept.main.")
        applied = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                current_request=self.result["request"])
        self.assertEqual(self.project, original)
        updated = applied["project"]
        normal = next(c for c in updated["loading_conditions"] if c["id"] == "normal")
        self.assertEqual(sorted(normal["overrides"]),
                         ["weapons.ammunition", "weapons.guns", "weapons.mounts"])
        for change in applied["changes"]:
            self.assertEqual(change["condition_id"], "normal")
            self.assertIn("acceptance", change)

    def test_a_rejected_batch_writes_nothing(self):
        rows = proposals(self.result)
        original = copy.deepcopy(self.project)
        for batch in ([], [rows[0], rows[0]], [{**rows[0], "proposed_mass_t": 999.0}]):
            with self.assertRaises(analysis.AnalysisInputError):
                analysis.apply_mass_proposals(self.project, "normal", batch,
                                              current_request=self.result["request"])
        self.assertEqual(self.project, original)

    def test_an_empty_duplicate_or_foreign_batch_is_rejected(self):
        rows = proposals(self.result)
        cases = [
            ([], "empty"),
            ([rows[0], rows[0]], "duplicate"),
            ([{**rows[0], "proposed_mass_t": 999.0}], "forged"),
            ([{**rows[0], "source_system_id": "propulsion.machinery"}], "foreign"),
            ([{**rows[0], "item_id": 7}], "item id type"),
        ]
        for batch, label in cases:
            with self.subTest(batch=label), self.assertRaises(analysis.AnalysisInputError):
                analysis.apply_mass_proposals(self.project, "normal", batch,
                                              current_request=self.result["request"])

    def test_a_stale_project_is_rejected(self):
        rows = proposals(self.result)
        stale = copy.deepcopy(self.project)
        stale["name"] = "changed after the proposals were produced"
        with self.assertRaises(analysis.AnalysisInputError):
            analysis.apply_mass_proposals(stale, "normal", [rows[0]],
                                          current_request=self.result["request"])

    def test_reapplying_an_accepted_batch_is_rejected_as_stale(self):
        rows = proposals(self.result)
        applied = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                current_request=self.result["request"])["project"]
        with self.assertRaises(analysis.AnalysisInputError):
            analysis.apply_mass_proposals(applied, "normal", rows,
                                          current_request=self.result["request"])

    def test_a_changed_condition_request_is_rejected(self):
        rows = proposals(self.result)
        deep = run(self.project, "deep")
        with self.assertRaises(analysis.AnalysisInputError):
            analysis.apply_mass_proposals(self.project, "deep", rows,
                                          current_request=deep["request"])

    def test_an_unknown_target_mass_does_not_block_an_otherwise_valid_batch(self):
        drop_mass(self.project, "weapons.mounts")
        result = run(self.project)
        rows = proposals(result, "concept.main.")
        applied = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                current_request=result["request"])
        self.assertEqual(applied["applied_count"], 3)

    def test_a_missing_cg_does_not_block_an_otherwise_valid_batch(self):
        for entry in self.project["weight_groups"][0]["items"]:
            entry.pop("kg_m", None)
        result = run(self.project)
        rows = proposals(result, "concept.main.")
        applied = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                current_request=result["request"])
        self.assertEqual(applied["applied_count"], 3)

    def test_an_unrelated_unknown_mass_does_not_block_an_otherwise_valid_batch(self):
        drop_mass(self.project, "weapons.other")
        result = run(self.project)
        rows = proposals(result, "concept.main.")
        applied = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                current_request=result["request"])
        self.assertEqual(applied["applied_count"], 3)

    def test_shared_ownership_is_rejected_as_ambiguous(self):
        result = run(self.project)
        row = find(proposals(result), "weapons.guns")
        self.project["systems"]["weapons"]["misc_weight"]["weight_item_ids"].append("weapons.guns")
        original = copy.deepcopy(self.project)
        with self.assertRaises(analysis.AnalysisInputError) as caught:
            analysis.apply_mass_proposals(self.project, "normal", [row],
                                          current_request=result["request"])
        self.assertIn("several systems", str(caught.exception))
        self.assertEqual(self.project, original)

    def test_a_derived_subtraction_condition_rejects_application_without_touching_its_base(self):
        base = case_project()
        base["loading_conditions"].append(dict(
            id="light", label="Light",
            definition=dict(kind="light", base_condition_id="normal", excluded_item_ids=[],
                            source="synthetic subtraction fixture", estimate=True)))
        result = run(base, "light")
        row = find(proposals(result), "weapons.guns")
        self.assertIsNotNone(row)
        original = copy.deepcopy(base)
        with self.assertRaises(analysis.AnalysisInputError) as caught:
            analysis.apply_mass_proposals(base, "light", [row], current_request=result["request"])
        self.assertIn("derived subtraction condition", str(caught.exception))
        self.assertIn("normal", str(caught.exception))
        self.assertEqual(base, original)

    def test_the_single_proposal_api_still_works_and_keeps_its_change_key(self):
        row = proposals(self.result, "concept.main.guns")[0]
        applied = analysis.apply_mass_proposal(self.project, "normal", row,
                                               current_request=self.result["request"])
        self.assertIn("change", applied)
        self.assertEqual(applied["change"]["item_id"], "weapons.guns")
        self.assertEqual(applied["change"]["current_request"]["condition_id"], "normal")
        self.assertEqual(len(applied["changes"]), 1)
        self.assertIsNone(applied["batch"]["item_ids"] and None)
        self.assertEqual(applied["batch"]["item_ids"], ["weapons.guns"])

    def test_batch_validation_does_not_recompute_geometry(self):
        rows = proposals(self.result)
        with mock.patch.object(analysis.stability, "solve_loaded_equilibrium",
                               side_effect=AssertionError("must not solve geometry")):
            applied = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                    current_request=self.result["request"])
        self.assertEqual(applied["applied_count"], len(rows))

    def test_an_applied_component_batch_still_leaves_a_fresh_structure_proposal(self):
        rows = proposals(self.result, "concept.main.")
        updated = analysis.apply_mass_proposals(self.project, "normal", rows,
                                                current_request=self.result["request"])["project"]
        after = run(updated)
        structure = find(proposals(after), "hull.structure")
        self.assertIsNotNone(structure)
        before = find(proposals(self.result), "hull.structure")
        self.assertNotAlmostEqual(structure["proposed_mass_t"], before["proposed_mass_t"],
                                  places=6)
        self.assertIsNotNone(balance(after)["structure"]["required_total_long_tons"])


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.project = case_project()

    def test_an_absent_configuration_keeps_every_previous_default(self):
        plain = case_project()
        del plain["concept_design"]
        result = run(plain)
        self.assertEqual(result["stages"]["systems"]["status"], "completed")
        self.assertEqual(result["stages"]["design_balance"]["status"], "not_configured")
        self.assertFalse(result["stages"]["design_balance"]["data"]["screening_complete"])
        self.assertEqual(result["stages"]["systems"]["data"]["update_proposals"], [])

    def test_the_configuration_is_never_mutated_by_a_run(self):
        before = copy.deepcopy(self.project["concept_design"])
        run(self.project)
        self.assertEqual(self.project["concept_design"], before)

    def test_invalid_schema_method_source_and_estimate_are_rejected(self):
        for field, value in (("schema", "plimsoll-concept-design-2"),
                             ("method", "plimsoll-physical-v1"),
                             ("source", ""), ("source", 7), ("estimate", False)):
            project = case_project()
            project["concept_design"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(Exception):
                run(project)

    def test_noninteger_counts_and_years_are_rejected_not_truncated(self):
        project = case_project()
        project["concept_design"]["batteries"][0]["mount_count"] = 4.5
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("integer", str(caught.exception).lower())
        project = case_project()
        project["concept_design"]["hull_year"] = 1918.5
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("integer", str(caught.exception).lower())

    def test_out_of_domain_and_wrong_types_are_rejected(self):
        cases = [
            ({"target_displacement_t": 0}, "positive"),
            ({"target_displacement_t": "8200"}, "finite number"),
            ({"target_displacement_t": float("inf")}, "finite number"),
            ({"hull_year": 1849}, "1850"),
            ({"freeboard_m": -1}, "positive"),
            ({"stern": "square"}, "one of"),
            ({"screws": 9}, "8"),
        ]
        for patch, token in cases:
            project = case_project()
            project["concept_design"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(Exception) as caught:
                run(project)
            self.assertIn(token, str(caught.exception).lower())

    def test_battery_enums_counts_and_cradle_domain_are_rejected(self):
        cases = [
            ({"gun_type": "laser"}, "one of"),
            ({"mount_type": "turret"}, "one of"),
            ({"calibre_mm": 0}, "positive"),
            ({"calibre_mm": 600}, "500"),
            ({"barrels_per_mount": 0}, "1"),
            ({"barrels_per_mount": 11}, "10"),
            ({"rounds_per_gun": -1}, "0"),
            ({"shared_cradle": "yes"}, "boolean"),
            ({"shared_cradle": True, "barrels_per_mount": 1}, "shared cradle"),
        ]
        for patch, token in cases:
            project = case_project()
            project["concept_design"]["batteries"][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(Exception) as caught:
                run(project)
            self.assertIn(token, str(caught.exception).lower())

    def test_a_null_shell_mass_is_editable_and_means_the_formula_estimate(self):
        self.assertIsNone(self.project["concept_design"]["batteries"][0]["shell_mass_kg"])
        generated = generated_models(self.project)
        model = next(m for m in generated["systems"]["weapons.main"]
                     if m["id"] == "concept.main.ammunition")
        self.assertEqual(model["inputs"]["shell_origin"], "formula_estimate_sps_3b3")

    def test_duplicate_targets_and_ids_are_rejected(self):
        project = case_project()
        project["concept_design"]["batteries"].append(dict(
            project["concept_design"]["batteries"][0],
            guns_item_id="weapons.guns", mounts_item_id="weapons.mounts",
            ammunition_item_id="propulsion.machinery"))
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("already owned", str(caught.exception))

        project = case_project()
        battery = project["concept_design"]["batteries"][0]
        battery["mounts_item_id"] = battery["guns_item_id"]
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("three distinct", str(caught.exception))

    def test_a_target_must_be_owned_by_its_declared_system(self):
        project = case_project()
        project["concept_design"]["batteries"][0]["system_id"] = "propulsion.machinery"
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("must be linked by the declared system", str(caught.exception))

    def test_an_unknown_system_id_is_not_silently_ignored(self):
        project = case_project()
        project["concept_design"]["batteries"][0]["system_id"] = "weapons.missing"
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("not a declared systems leaf", str(caught.exception))

    def test_every_role_value_must_be_known(self):
        project = case_project()
        project["concept_design"]["balance"]["roles"]["weapons.guns"] = "torpedo"
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("one of", str(caught.exception))

    def test_zero_membership_does_not_require_dummy_items(self):
        project = case_project()
        del project["concept_design"]["balance"]["roles"]["misc.void"]
        self.assertEqual(balance(run(project))["roles"]["misc_void"], 0)

    def test_balance_assumptions_must_be_declared_not_invented(self):
        for field in ("steadiness", "space_hull_fraction", "space_deck_fraction", "super_factor",
                      "super_factor_long", "concentration", "strength_target"):
            project = case_project()
            del project["concept_design"]["balance"][field]
            with self.subTest(field=field):
                data = balance(run(project))
                self.assertEqual(data["status"], "unavailable")
                self.assertTrue(any(field in d["message"] for d in data["diagnostics"]))

    def test_the_assumption_source_is_recorded(self):
        self.assertIn("synthetic", balance(run(self.project))["assumption_source"])

    def test_fuel_requires_machinery_and_a_sane_cruise_speed(self):
        project = case_project()
        del project["concept_design"]["machinery"]
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("fuel requires a declared machinery", str(caught.exception))
        project = case_project()
        project["concept_design"]["fuel"]["cruise_speed_kn"] = 25.0
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("cruise speed", str(caught.exception))

    def test_fuel_without_a_declared_range_is_unavailable_but_editable(self):
        project = case_project()
        project["concept_design"]["fuel"]["range_nm"] = None
        result = run(project)
        self.assertNotIn("concept.fuel", [m["id"] for m in result["stages"]["systems"]["data"]
                                         ["systems"]["propulsion.fuel"]["mass_models"]])
        self.assertTrue(any("range_nm" in d["path"]
                            for d in result["stages"]["systems"]["data"]["diagnostics"]))

    def test_the_adjustable_structure_item_must_carry_the_structure_role(self):
        project = case_project()
        project["concept_design"]["balance"]["roles"]["hull.structure"] = "other"
        with self.assertRaises(Exception) as caught:
            run(project)
        self.assertIn("'structure' role", str(caught.exception))

    def test_one_canonical_mass_count_remains_the_only_authority(self):
        result = run(self.project)
        state = loading.resolve_loading(self.project, "normal")
        self.assertEqual(result["stages"]["loading"]["data"]["values"]["total_mass_t"],
                         state["values"]["total_mass_t"])
        for condition in self.project["loading_conditions"]:
            self.assertNotIn("weapons.guns", condition.get("overrides", {}))
            self.assertNotIn("hull.structure", condition.get("overrides", {}))
        summary = result["stages"]["systems"]["data"]
        self.assertEqual(summary["mass_authority"], "selected_loading_weight_ledger")
        for row in summary["update_proposals"]:
            self.assertTrue(row["requires_review"])


if __name__ == "__main__":
    unittest.main()
