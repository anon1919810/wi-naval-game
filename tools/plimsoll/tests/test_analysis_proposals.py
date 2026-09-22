"""Physical mass acceptance recomputes identity, model and selected scope."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis
import loading
import project_store
from test_analysis import box_project


def proposed_project():
    project = box_project()
    project["weight_groups"][0]["items"][0]["uncertainty"] = {"mass_t": [240, 250], "kg_m": [.8, 1.2]}
    project["systems"] = {"armour": {"weight_item_ids": ["hull.a[0]"], "mass_models": [dict(
        id="volume", method="volume_density_mass", linked_weight_item_id="hull.a[0]",
        inputs=dict(volume_m3=30, density_kg_m3=8000), source="explicit plate geometry", estimate=True,
        input_provenance={key: dict(source="analytic fixture", estimate=True) for key in ("volume_m3", "density_kg_m3")},
        comparison_tolerance=dict(relative=0, absolute_t=1e-10))]}}
    return project


class ProposalTests(unittest.TestCase):
    def test_apply_changes_only_selected_mass_and_audited_field_provenance(self):
        project = proposed_project()
        original = copy.deepcopy(project)
        result = analysis.compute_project(project, "normal", {"stages": ["systems"]})
        proposal = result["stages"]["systems"]["data"]["update_proposals"][0]
        with patch.object(analysis.stability, "solve_loaded_equilibrium", side_effect=AssertionError("freshness must not solve")):
            applied = analysis.apply_mass_proposal(project, "normal", proposal, current_request=result["request"])
        updated = applied["project"]
        state = loading.resolve_loading(updated, "normal")
        self.assertEqual(state["values"]["total_mass_t"], 240)
        self.assertEqual(loading.resolve_loading(updated, "deep")["values"]["total_mass_t"], 307.5)
        item = state["effective_items"][0]
        self.assertNotIn("mass_t", item["uncertainty"])
        self.assertEqual(item["uncertainty"]["kg_m"], [.8, 1.2])
        self.assertEqual(item["provenance"]["fields"]["kg_m"]["source"], "analytic loading")
        acceptance = updated["loading_conditions"][0]["override_provenance"]["hull.a[0]"]["mass_t"]["acceptance"]
        self.assertEqual(acceptance["previous_mass_t"], 246)
        self.assertEqual(acceptance["new_mass_t"], 240)
        self.assertEqual(acceptance["request_fingerprint"], result["request_fingerprint"])
        self.assertEqual(project, original)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "采用质量修订.json"
            project_store.save(path, updated)
            self.assertEqual(project_store.load(path), updated)

    def test_rejects_forged_value_stale_project_and_current_options_change(self):
        project = proposed_project()
        result = analysis.compute_project(project, "normal", {"stages": ["systems"]})
        proposal = result["stages"]["systems"]["data"]["update_proposals"][0]
        forged = {**proposal, "proposed_mass_t": 999}
        for current, submitted, request in ((project, forged, result["request"]),
            ({**project, "name": "changed source identity"}, proposal, result["request"]),
            (project, proposal, {**result["request"], "options": {**result["request"]["options"],
             "equilibrium": {**result["request"]["options"]["equilibrium"], "rho_t_m3": 1}}})):
            with self.subTest(forged=submitted is forged), self.assertRaises(analysis.AnalysisInputError):
                analysis.apply_mass_proposal(current, "normal", submitted, current_request=request)


if __name__ == "__main__":
    unittest.main()
