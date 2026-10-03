"""Explicit Standard/Light subtraction rules, not automatic cargo deductions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plimsoll import analysis, loading, project_io, project_store


def fixture():
    p = project_io.new_project("Declared loading study", "loading-form")
    p["hull"] = dict(lwl_m=20, loa_m=20, beam_m=10, draught_normal_m=4,
                     block_coeff=1, waterplane_coeff=1)
    p["weight_groups"] = [dict(id="outfit", label="Outfit", items=[
        dict(id="structure", mass_t=700, x_m=0, y_m=0, kg_m=3, source="fixture", estimate=False),
        dict(id="fuel", mass_t=120, x_m=5, y_m=0, kg_m=1, source="fixture", estimate=False)])]
    p["loading_conditions"] = [dict(id="normal", label="Normal", overrides={"fuel": {"mass_t": 100}}),
        dict(id="standard", label="Standard study", overrides={}, definition=dict(
            kind="standard", base_condition_id="normal", excluded_item_ids=["fuel"],
            source="User-defined removal of fuel", estimate=True))]
    return p


class LoadingDefinitionTests(unittest.TestCase):
    def test_explicit_removal_uses_base_loading_once_and_preserves_project(self):
        p = fixture(); original = copy.deepcopy(p)
        result = loading.resolve_loading(p, "standard")
        self.assertEqual(result["values"]["total_mass_t"], 700)
        self.assertEqual(result["values"]["kg_m"], 3)
        self.assertEqual(result["definition"]["excluded_item_ids"], ["fuel"])
        fuel = next(i for i in result["effective_items"] if i["id"] == "fuel")
        self.assertEqual(fuel["provenance"]["fields"]["mass_t"]["source"], "User-defined removal of fuel")
        self.assertEqual(p, original)

    def test_empty_explicit_removal_inherits_base_override_not_base_item(self):
        p = fixture(); p["loading_conditions"][1]["definition"]["excluded_item_ids"] = []
        self.assertEqual(loading.resolve_loading(p, "standard")["values"]["total_mass_t"], 800)

    def test_invalid_rules_are_blocked_instead_of_guessed(self):
        for patch in ({"base_condition_id": "missing"}, {"base_condition_id": "standard"},
                      {"excluded_item_ids": ["missing"]}, {"excluded_item_ids": ["fuel", "fuel"]},
                      {"kind": "maximum"}, {"source": None}, {"estimate": None}):
            with self.subTest(patch=patch):
                p = fixture(); p["loading_conditions"][1]["definition"].update(patch)
                self.assertTrue(any(d["blocking"] for d in project_io.validate_project(p)))

    def test_chaining_and_mixed_overrides_are_rejected(self):
        p = fixture(); derived = copy.deepcopy(p["loading_conditions"][1])
        derived.update(id="light", label="Light")
        derived["definition"].update(kind="light", base_condition_id="standard")
        p["loading_conditions"].append(derived)
        self.assertTrue(any(d["blocking"] for d in project_io.validate_project(p)))
        p = fixture(); p["loading_conditions"][1]["overrides"] = {"fuel": {"mass_t": 10}}
        self.assertTrue(any(d["blocking"] for d in project_io.validate_project(p)))

    def test_definition_roundtrip_and_request_identity(self):
        p = fixture()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "study.json"
            project_store.save(path, p); reopened = project_store.load(path)
            result = analysis.compute_project(reopened, "standard", {"stages": ["loading"]})
            self.assertEqual(result["stages"]["loading"]["data"]["values"]["total_mass_t"], 700)
            changed = copy.deepcopy(reopened)
            changed["loading_conditions"][1]["definition"]["excluded_item_ids"] = []
            other = analysis.compute_project(changed, "standard", {"stages": ["loading"]})
            self.assertNotEqual(result["request_fingerprint"], other["request_fingerprint"])

    def test_optional_hull_fact_validation_and_projection(self):
        p = fixture(); p["hull"]["design_facts"] = {"block_coeff_deep": dict(value=-1, source="fixture", estimate=True)}
        self.assertTrue(any(d["blocking"] for d in project_io.validate_project(p)))
        p["hull"]["design_facts"]["block_coeff_deep"]["value"] = None
        p["metadata"] = {"country": dict(value="UK", source="fixture", estimate=False)}
        result = analysis.compute_project(p, "normal", {"stages": ["l0"]})
        declared = result["stages"]["l0"]["data"]["declared_hull"]
        self.assertIsNone(declared["design_facts"]["block_coeff_deep"]["value"])
        self.assertEqual(declared["metadata"]["country"]["value"], "UK")


if __name__ == "__main__":
    unittest.main()
