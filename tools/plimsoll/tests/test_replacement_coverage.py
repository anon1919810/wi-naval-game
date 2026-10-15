# -*- coding: utf-8 -*-
"""Coverage-baseline regression: the seven-page map must not overstate replacement.

The 2026-10-15 comparison found two wrong bindings (Set Trim, Steadiness), an
unknown method that is now known (natural speed) and one editor the original
capture never saw (the gun editor). These tests pin the repaired baseline so
the same false completion cannot come back silently.
"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
RECONCILER_PATH = ROOT / "tools/plimsoll/tools/reconcile_seven_pages.py"
PROPOSAL = ROOT / "docs/plimsoll-1.0/evidence/seven-page-binding-proposal.json"
SUPPLEMENT = ROOT / "docs/plimsoll-1.0/evidence/gun-editor-source-supplement.json"
INVENTORY_FILES = (
    ROOT / ".superpowers/sdd/2026-09-22-plimsoll-1.0/seven-page-fields.json",
    ROOT / "docs/plimsoll-1.0/evidence/seven-page-inventory.json",
)
FROZEN_INVENTORY_SHA256 = "b4b979b73b48a8e8b9f668375f4be0616ee3af5f882b72ede05b46b32f007d07"
RECORD_COUNT = 191
CONTROL_COUNT = 35
METHOD_COUNT = 12

# Paths that must never again be offered as the SpringSharp answer for these records.
WITHDRAWN = {
    "performance.set_trim": {
        "$.stages.equilibrium.data.trim_deg",
        "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_t_m",
        "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_kNm",
    },
    "performance.steadiness": {
        "$.hull.roll_gyration_coeff",
        "$.stages.hydrostatics.data.values.gm_t_m",
        "$.stages.hydrostatics.data.loaded_roll.period_s",
    },
}


def load_reconciler():
    spec = importlib.util.spec_from_file_location("reconcile_seven_pages", RECONCILER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_generator(destination: Path) -> None:
    """Run the checked-in generator against a sandbox copy of the artifact."""
    (destination / "tools/plimsoll/tools").mkdir(parents=True, exist_ok=True)
    (destination / "docs/plimsoll-1.0/evidence").mkdir(parents=True, exist_ok=True)
    shutil.copytree(RECONCILER_PATH.parent, destination / "tools/plimsoll/tools",
                    dirs_exist_ok=True)
    shutil.copy2(PROPOSAL, destination / "docs/plimsoll-1.0/evidence"
                  / PROPOSAL.name)
    completed = subprocess.run(
        [sys.executable, "-B", str(destination / "tools/plimsoll/tools"
                                   / RECONCILER_PATH.name)],
        capture_output=True, cwd=str(destination))
    if completed.returncode != 0:
        raise AssertionError("reconciler failed: %s" % completed.stderr.decode("utf-8", "replace"))


class FrozenInventoryTests(unittest.TestCase):
    def test_original_inventory_is_untouched(self):
        for path in INVENTORY_FILES:
            self.assertTrue(path.exists(), "%s is missing" % path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, FROZEN_INVENTORY_SHA256,
                             "%s no longer matches the frozen observation inventory" % path)

    def test_proposal_records_the_frozen_inventory_digest(self):
        data = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        self.assertEqual(data["inventory"]["sha256"], FROZEN_INVENTORY_SHA256)
        self.assertEqual(data["inventory"]["record_count"], RECORD_COUNT)


class FrozenIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.records = cls.data["records"]
        cls.by_id = {record["id"]: record for record in cls.records}

    def test_the_191_frozen_ids_are_unchanged(self):
        self.assertEqual(len(self.records), RECORD_COUNT)
        self.assertEqual(len(self.by_id), RECORD_COUNT)
        inventory = json.loads(INVENTORY_FILES[0].read_text(encoding="utf-8"))
        observed = [field["id"] for field in inventory["common_controls"]]
        observed += [field["id"] for page in inventory["pages"]
                     for group in page["groups"] for field in group["fields"]]
        self.assertEqual(len(observed), RECORD_COUNT)
        self.assertEqual(sorted(observed), sorted(self.by_id))

    def test_frozen_page_and_label_fields_are_untouched(self):
        inventory = json.loads(INVENTORY_FILES[0].read_text(encoding="utf-8"))
        frozen = dict((field["id"], field)
                      for field in inventory["common_controls"]
                      + [f for page in inventory["pages"]
                         for group in page["groups"] for f in group["fields"]])
        for record in self.records:
            source = frozen[record["id"]]
            self.assertEqual(record["label"], source["label"], record["id"])
            self.assertEqual(record["io"], source["io"], record["id"])
            self.assertEqual(record["seen"], source["seen"], record["id"])

    def test_every_record_declares_a_disposition_and_a_semantic_relation(self):
        vocabulary = set(self.data["semantic_relation_vocabulary"])
        for record in self.records:
            self.assertTrue(record["current_disposition"], record["id"])
            self.assertIn(record["current_disposition"],
                          set(self.data["disposition_counts"]), record["id"])
            self.assertIn(record["semantic_relation"], vocabulary, record["id"])
            self.assertEqual(record["core_review"]["status"], record["current_disposition"],
                             record["id"])

    def test_every_record_declares_a_verification_state(self):
        states = set(self.data["verification_state_counts"])
        for record in self.records:
            verification = record["verification"]
            self.assertIn(verification["state"], states, record["id"])
            self.assertTrue(verification["basis"], record["id"])
            self.assertTrue(verification["note"], record["id"])

    def test_earlier_scope_decisions_survive_as_history(self):
        for record in self.records:
            phases = [entry["phase"] for entry in record["disposition_history"]]
            self.assertEqual(phases[:2], ["original_proposal",
                                          "core_binding_reconciliation_2026_09"],
                             record["id"])
            self.assertEqual(phases[-1], self.data["phase"], record["id"])
            self.assertTrue(record["pre_reconciliation_disposition"], record["id"])


class SemanticDisputeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.by_id = {record["id"]: record for record in cls.data["records"]}

    def test_set_trim_is_an_empirical_steadiness_adjustment_not_target_trim(self):
        record = self.by_id["performance.set_trim"]
        self.assertEqual(record["current_disposition"], "unavailable_semantic_mismatch")
        self.assertEqual(record["semantic_relation"], "different_semantics_unimplemented")
        active = {entry.get("path") for entry in record["result_bindings"]}
        active |= {entry.get("path") for entry in record["canonical_inputs"]}
        self.assertEqual(active & WITHDRAWN["performance.set_trim"], set())
        self.assertEqual(record["historical_rejected_bindings"][0]["withdrawn_phase"],
                         self.data["phase"])
        self.assertEqual({entry["path"] for entry in record["historical_rejected_bindings"]},
                         WITHDRAWN["performance.set_trim"])
        self.assertIn("0..100", record["source_evidence"]["sps_units"])
        self.assertIn("steadiness", record["source_evidence"]["sps_meaning"])
        self.assertNotIn("target_trim_deg", record["core_review"]["limitation"])
        self.assertIn("empirical steadiness adjustment",
                      record["core_review"]["limitation"])

    def test_steadiness_is_a_score_not_a_roll_period(self):
        record = self.by_id["performance.steadiness"]
        self.assertEqual(record["current_disposition"], "unavailable_semantic_mismatch")
        active = {entry.get("path") for entry in record["result_bindings"]}
        active |= {entry.get("path") for entry in record["canonical_inputs"]}
        self.assertEqual(active & WITHDRAWN["performance.steadiness"], set())
        self.assertEqual({entry["path"] for entry in record["historical_rejected_bindings"]},
                         WITHDRAWN["performance.steadiness"])
        self.assertIn("Math.Min(steadiness * seaboat, 100)",
                      record["source_evidence"]["sps_method"])
        self.assertIn("seconds", record["source_evidence"]["sps_units"])

    def test_withdrawn_bindings_are_never_reintroduced_by_a_later_phase(self):
        for identity, paths in WITHDRAWN.items():
            record = self.by_id[identity]
            active = {entry.get("path") for entry in record["result_bindings"]}
            active |= {entry.get("path") for entry in record["canonical_inputs"]}
            self.assertEqual(active & paths, set(), identity)

    def test_disputed_records_carry_no_active_stage_or_provenance_requirement(self):
        for identity in WITHDRAWN:
            record = self.by_id[identity]
            self.assertEqual(record["required_stages"], [], identity)
            self.assertEqual(record["provenance_bindings"], [], identity)
            self.assertEqual(record["canonical_inputs"], [], identity)
            self.assertIsNone(record["required_condition"], identity)
            self.assertEqual(record["result_bindings"], [], identity)

    def test_active_limitation_states_the_recovered_semantics(self):
        trim = self.by_id["performance.set_trim"]["limitation"]
        self.assertIn("0..100", trim)
        self.assertIn("steadiness adjustment", trim)
        self.assertNotIn("Solved trim is available", trim)
        steady = self.by_id["performance.steadiness"]["limitation"]
        self.assertIn("min(steadiness x seaboat, 100)", steady)
        self.assertIn("seconds", steady)
        self.assertNotIn("roll_period_s exists", steady)

    def test_superseded_active_metadata_is_preserved_as_history(self):
        for identity, stages in (("performance.set_trim", "equilibrium"),
                                 ("performance.steadiness", "hydrostatics")):
            history = self.by_id[identity]["historical_metadata"]
            self.assertEqual(len(history), 1, identity)
            entry = history[0]
            self.assertEqual(entry["phase"], "original_proposal", identity)
            self.assertEqual(entry["required_stages"], [stages], identity)
            self.assertTrue(entry["provenance_bindings"], identity)
            self.assertTrue(entry["limitation"], identity)
        self.assertEqual(self.by_id["performance.steadiness"]["historical_metadata"][0]
                         ["canonical_inputs"], [{"path": "$.hull.roll_gyration_coeff"}])
        self.assertEqual(self.by_id["hull.derived.natural_speed"]["historical_metadata"][0]
                         ["canonical_inputs"], [{"path": "$.hull.lwl_m"}])

    def test_natural_speed_claims_no_active_stage_or_binding(self):
        record = self.by_id["hull.derived.natural_speed"]
        self.assertEqual(record["required_stages"], [])
        self.assertEqual(record["provenance_bindings"], [])
        self.assertEqual(record["canonical_inputs"], [])
        self.assertIn("no versioned parity method", record["limitation"])

    def test_no_record_keeps_active_metadata_for_a_withdrawn_claim(self):
        for identity, paths in WITHDRAWN.items():
            record = self.by_id[identity]
            for key in ("required_stages", "provenance_bindings", "canonical_inputs"):
                self.assertEqual({entry.get("path") for entry in record[key]} & paths, set(),
                                 "%s.%s" % (identity, key))

    def test_related_studies_are_kept_apart_from_the_withdrawn_binding(self):
        """Withdrawing a claim must not delete a live path; it relabels it instead."""
        for identity in WITHDRAWN:
            related = self.by_id[identity]["related_plimsoll_studies"]
            self.assertTrue(related, identity)
            paths = {entry["plimsoll_path"] for entry in related}
            self.assertTrue(paths <= WITHDRAWN[identity], identity)
            for entry in related:
                self.assertIn("not_sps", entry["relation"], identity)
                self.assertTrue(entry["what_it_is"], identity)


class NaturalSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = next(record for record in
                          json.loads(PROPOSAL.read_text(encoding="utf-8"))["records"]
                          if record["id"] == "hull.derived.natural_speed")

    def test_source_is_now_known_but_parity_is_claimed(self):
        self.assertEqual(self.record["current_disposition"],
                         "method_known_parity_not_implemented")
        self.assertEqual(self.record["semantic_relation"], "method_known_not_implemented")
        self.assertIn("sqrt(lengthEffect)", self.record["source_evidence"]["sps_method"])
        self.assertIn("coSharp", self.record["source_evidence"]["sps_method"])
        self.assertFalse(self.record["current_disposition"].startswith("implemented"))

    def test_no_plimsoll_result_binding_is_offered_for_natural_speed(self):
        self.assertEqual(self.record["result_bindings"], [])

    def test_legacy_helper_no_longer_claims_to_be_the_sps_convention(self):
        source = (ROOT / "tools/plimsoll/hull.py").read_text(encoding="utf-8")
        self.assertNotIn("SPS 惯例", source)
        self.assertIn("SLR_LEGACY", source)
        self.assertIn("√lengthEffect", source)

    def test_the_old_constant_name_survives_only_as_a_deprecated_alias(self):
        sys.path.insert(0, str(ROOT / "tools/plimsoll"))
        try:
            import hull
        finally:
            sys.path.pop(0)
        self.assertEqual(hull.SLR_SPS, hull.SLR_LEGACY)
        # The alias must not change any number: the numerical API is untouched.
        self.assertEqual(hull.natural_speed({"lwl_m": 90.0}, slr=hull.SLR_SPS)["values"]
                         ["natural_speed_kn"],
                         hull.natural_speed({"lwl_m": 90.0}, slr=hull.SLR_LEGACY)["values"]
                         ["natural_speed_kn"])


class NoInflatedEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.records = cls.data["records"]

    def test_no_record_claims_verified_sps_equivalence(self):
        for record in self.records:
            self.assertFalse(record["verification"]["sps_equivalence_claim"], record["id"])
            self.assertIsNone(record["verification"]["sps_equivalence_evidence"], record["id"])
            self.assertFalse(record["verification"]["executable_equivalence_run"], record["id"])
        self.assertEqual(self.data["sps_equivalence_claims"]["verified_records"], 0)
        self.assertFalse(self.data["completion_claim"])

    def test_approved_exclusions_are_not_counted_as_coverage(self):
        excluded = [record for record in self.records
                    if record["current_disposition"] == "excluded_by_approved_scope"]
        self.assertEqual(len(excluded), 26)
        for record in excluded:
            self.assertEqual(record["semantic_relation"], "scope_excluded_not_a_replacement")
            self.assertEqual(record["verification"]["state"], "scope_excluded_not_verified")
            self.assertFalse(record["current_disposition"].startswith("implemented"))

    def test_an_existing_binding_is_not_evidence_of_equivalence(self):
        bound = [record for record in self.records
                 if record["current_disposition"] == "existing_binding_conditioned"]
        self.assertTrue(bound)
        for record in bound:
            self.assertIn(record["verification"]["state"],
                          {"not_re_audited_in_this_review",
                           "re_audited_against_recovered_source_2026_10_15"}, record["id"])

    def test_records_not_re_audited_say_so_instead_of_claiming_verification(self):
        for record in self.records:
            if record["id"] in ("performance.set_trim", "performance.steadiness",
                                "hull.derived.natural_speed",
                                "guns.battery_selection.editor_fields_unknown"):
                continue
            if record["verification"]["state"] == "not_re_audited_in_this_review":
                self.assertIn("not re-verified", record["verification"]["note"], record["id"])

    def test_deferred_presentation_is_history_not_todays_ui(self):
        deferred = [record for record in self.records
                    if record["current_disposition"] == "presentation_deferred_historical_phase"]
        self.assertEqual(len(deferred), 16)
        for record in deferred:
            self.assertEqual(record["semantic_relation"],
                             "presentation_phase_historical_not_retested")
            self.assertIn("not re-tested", record["core_review"]["limitation"], record["id"])


class GunEditorSupplementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supplement = json.loads(SUPPLEMENT.read_text(encoding="utf-8"))
        cls.controls = cls.supplement["controls"]
        cls.methods = cls.supplement["methods"]

    def test_supplement_is_versioned_and_names_its_source(self):
        self.assertEqual(self.supplement["schema"], "plimsoll-gun-editor-source-supplement-1")
        self.assertTrue(self.supplement["version"])
        self.assertEqual(self.supplement["placeholder_record"],
                         "guns.battery_selection.editor_fields_unknown")
        source = self.supplement["source"]
        self.assertEqual(source["executable_sha256"],
                         "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc")
        self.assertEqual(source["assembly_version"], "3.0.3032.29945")

    def test_control_and_method_counts_are_stable_and_unique(self):
        self.assertEqual(len(self.controls), CONTROL_COUNT)
        self.assertEqual(len(self.methods), METHOD_COUNT)
        self.assertEqual(len({control["id"] for control in self.controls}), CONTROL_COUNT)
        self.assertEqual(len({method["id"] for method in self.methods}), METHOD_COUNT)

    def test_every_control_carries_evidence_units_interface_and_coverage(self):
        for control in self.controls:
            for field in ("id", "sps_label", "sps_control", "direction", "sps_units",
                          "sps_default", "sps_handler", "plimsoll_interface",
                          "plimsoll_support", "semantic_relation", "coverage",
                          "plimsoll_audit_state", "coverage_note"):
                self.assertIn(field, control, control["id"])
                self.assertTrue(control[field] not in (None, ""), "%s.%s" % (control["id"], field))

    def test_absent_plimsoll_support_is_scoped_to_the_enumerated_contract(self):
        """A gap may only be asserted where the declared contract makes it verifiable."""
        enumerated = ("tools/plimsoll/project_extensions.py",
                       "PAGE_ROW_TYPED_FIELDS", "WEAPON_FIELDS")
        for control in self.controls:
            if not control["coverage"].startswith("no_field_in_enumerated"):
                continue
            support = control["plimsoll_support"]
            self.assertTrue(any(token in support for token in enumerated),
                            "%s claims an absent field without contract evidence" % control["id"])
            self.assertEqual(control["plimsoll_audit_state"],
                             "verified_against_current_source_2026_10_15", control["id"])

    def test_audit_state_is_declared_for_every_entry(self):
        allowed = {"verified_against_current_source_2026_10_15", "not_reaudited"}
        for control in self.controls:
            self.assertIn(control["plimsoll_audit_state"], allowed, control["id"])
        self.assertNotIn("not_reaudited", {c["plimsoll_audit_state"] for c in self.controls},
                         "every gun-editor entry was re-read against the current source")

    def test_barrel_count_maps_to_the_live_declared_installed_count(self):
        control = next(item for item in self.controls if item["id"] == "gun.barrels")
        self.assertIn("$.systems.weapons.<battery_id>.installed_guns", control["plimsoll_interface"])
        self.assertIn("page_rows[weapons.<battery_id>].installed_guns",
                      control["plimsoll_interface"])
        for evidence in ("systems.py", "_declared_count", "page_rows.py", "GunsEditor.tsx"):
            self.assertIn(evidence, control["plimsoll_support"], evidence)
        self.assertEqual(control["coverage"], "declared_input_no_estimation")
        self.assertNotIn("implemented", control["semantic_relation"])
        self.assertIn("not to be equated with the mount count", control["coverage_note"])

    def test_declared_installed_inputs_are_recorded_with_their_evidence(self):
        declared = {entry["path"]: entry for entry in self.supplement["plimsoll_declared_inputs"]}
        self.assertIn("$.systems.weapons.<battery_id>.installed_guns", declared)
        self.assertIn("$.systems.weapons.<battery_id>.rounds_per_gun", declared)
        self.assertIn("$.systems.weapons.<battery_id>.facts.projectile_mass_kg", declared)
        for path, entry in declared.items():
            self.assertTrue(entry["role"], path)
            self.assertTrue(entry["evidence"], path)
        self.assertIn("_declared_count",
                      declared["$.systems.weapons.<battery_id>.installed_guns"]["evidence"])

    def test_rounds_per_barrel_maps_to_the_live_declared_rounds_input(self):
        control = next(item for item in self.controls if item["id"] == "gun.rounds_per_barrel")
        self.assertIn("rounds_per_gun", control["plimsoll_interface"])
        self.assertIn("per_gun_shell_kg", control["plimsoll_interface"])
        self.assertIn("systems.py", control["plimsoll_support"])
        self.assertEqual(control["coverage"], "declared_input_no_estimation")

    def test_every_method_carries_evidence_units_and_coverage(self):
        for method in self.methods:
            for field in ("id", "name", "location", "formula", "units", "coverage", "note"):
                self.assertIn(field, method, method["id"])
                self.assertTrue(method[field] not in (None, ""), "%s.%s" % (method["id"], field))

    def test_the_required_gun_controls_are_present(self):
        ids = {control["id"] for control in self.controls}
        for required in ("gun.calibre", "gun.barrel_length", "gun.year", "gun.gun_type",
                         "gun.mount_type", "gun.mounts_total",
                         "gun.guns_in_mount.g1", "gun.guns_in_mount.g2",
                         "gun.layout.g1", "gun.layout.g2",
                         "gun.mounts.raised.g1", "gun.mounts.raised.g2",
                         "gun.mounts.deck.g2", "gun.mounts.below_deck.g1",
                         "gun.mounts.below_deck.g2",
                         "gun.superfiring.raised_two_up", "gun.superfiring.below_deck_lower",
                         "gun.armour.face", "gun.armour.side_rear", "gun.armour.barbette",
                         "gun.armour.weight", "gun.shell_weight_lb", "gun.shell_weight_kg",
                         "gun.shell_weight_lock", "gun.rounds_per_barrel"):
            self.assertIn(required, ids)

    def test_the_required_gun_methods_are_present(self):
        ids = {method["id"] for method in self.methods}
        for required in ("shell_weight_estimate", "gun_mass", "mount_mass",
                         "mount_weight_adjustment", "group_split", "superfiring_ratio",
                         "free_gun_rating", "layout_text_and_position", "mount_armour_mass",
                         "ammunition_mass", "description_text", "validation_warnings"):
            self.assertIn(required, ids)

    def test_no_estimating_control_is_claimed_as_implemented(self):
        estimating = [control for control in self.controls
                      if control["coverage"] in ("declared_input_no_estimation",
                                                 "no_field_in_enumerated_weapon_contract")]
        self.assertTrue(estimating)
        for control in estimating:
            self.assertNotIn("implemented", control["semantic_relation"])
        self.assertEqual(self.supplement["coverage_counts"]["declared_input_no_estimation"],
                         len([c for c in self.controls
                              if c["coverage"] == "declared_input_no_estimation"]))

    def test_supplement_declares_its_inputs_before_claiming_gaps(self):
        self.assertIn("declared", self.supplement["coverage_note"])
        self.assertIn("estimating chain", self.supplement["coverage_note"])
        self.assertTrue(any("does not execute" in line
                            for line in self.supplement["evidence_boundary"]))
        self.assertTrue(any("marked not_reaudited" in line
                            for line in self.supplement["evidence_boundary"]))

    def test_the_placeholder_record_points_at_the_supplement(self):
        record = next(record for record in
                      json.loads(PROPOSAL.read_text(encoding="utf-8"))["records"]
                      if record["id"] == "guns.battery_selection.editor_fields_unknown")
        self.assertEqual(record["current_disposition"], "source_expanded_not_implemented")
        self.assertEqual(record["source_evidence"]["supplement_path"],
                         "docs/plimsoll-1.0/evidence/gun-editor-source-supplement.json")


class GeneratorDeterminismTests(unittest.TestCase):
    def test_two_runs_produce_byte_identical_output(self):
        with TemporaryDirectory() as folder:
            destination = Path(folder)
            run_generator(destination)
            first = (destination / "docs/plimsoll-1.0/evidence" / PROPOSAL.name).read_bytes()
            run_generator(destination)
            second = (destination / "docs/plimsoll-1.0/evidence" / PROPOSAL.name).read_bytes()
            self.assertEqual(first, second)
            self.assertEqual((destination / "docs/plimsoll-1.0/evidence"
                              / SUPPLEMENT.name).read_bytes(), SUPPLEMENT.read_bytes())

    def test_the_checked_in_artifact_is_a_fixed_point_of_the_generator(self):
        with TemporaryDirectory() as folder:
            destination = Path(folder)
            run_generator(destination)
            self.assertEqual((destination / "docs/plimsoll-1.0/evidence" / PROPOSAL.name)
                             .read_bytes(), PROPOSAL.read_bytes())

    def test_regeneration_preserves_the_record_identity(self):
        with TemporaryDirectory() as folder:
            destination = Path(folder)
            run_generator(destination)
            before = json.loads(PROPOSAL.read_text(encoding="utf-8"))
            after = json.loads((destination / "docs/plimsoll-1.0/evidence"
                                / PROPOSAL.name).read_text(encoding="utf-8"))
        self.assertEqual([record["id"] for record in before["records"]],
                         [record["id"] for record in after["records"]])
        self.assertEqual(before["records"], after["records"])


class ReconcilerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_reconciler()
        cls.data = json.loads(PROPOSAL.read_text(encoding="utf-8"))

    def test_review_does_not_return_a_disputed_binding(self):
        record = copy.deepcopy(next(item for item in self.data["records"]
                                    if item["id"] == "performance.set_trim"))
        status, path, _ = self.module.review(record)
        self.assertEqual(status, "unavailable_semantic_mismatch")
        self.assertIsNone(path)
        status, path, _ = self.module.review(next(item for item in self.data["records"]
                                                   if item["id"] == "performance.steadiness"))
        self.assertEqual(status, "unavailable_semantic_mismatch")
        self.assertIsNone(path)

    def test_review_never_reports_natural_speed_as_implemented(self):
        record = next(item for item in self.data["records"]
                      if item["id"] == "hull.derived.natural_speed")
        status, path, _ = self.module.review(copy.deepcopy(record))
        self.assertEqual(status, "method_known_parity_not_implemented")
        self.assertIsNone(path)

    def test_exclusion_never_reports_implemented(self):
        record = next(item for item in self.data["records"]
                      if item["id"] == "performance.strength.cross_sectional")
        status, _, _ = self.module.review(copy.deepcopy(record))
        self.assertEqual(status, "excluded_by_approved_scope")
        self.assertFalse(status.startswith("implemented"))


if __name__ == "__main__":
    unittest.main()