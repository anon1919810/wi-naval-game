"""Reproduce generic geometry anchors and isolated in-memory mutation checks."""

import io
import json
from pathlib import Path
import sys
import types
import unittest

root = Path(__file__).resolve().parents[3]
package = root / "tools" / "plimsoll"
sys.path.insert(0, str(package))
sys.path.insert(0, str(package / "tests"))
import geometry_analysis
import test_geometry_analysis as checks

source = (package / "geometry_analysis.py").read_text(encoding="utf-8")
mutations = [
    ("omit_station_trim", "intercept = d+p*x", "intercept = d",
     "test_selected_trim_and_heel_use_each_station_plane_and_true_plane_area"),
    ("omit_inclined_area_factor", "awp_m2=projected_area*s", "awp_m2=projected_area",
     "test_selected_trim_and_heel_use_each_station_plane_and_true_plane_area"),
    ("omit_keel_from_deck", "z+keel-p*x-q*y-d", "z-p*x-q*y-d",
     "test_deck_clearance_uses_signed_normal_distance_and_keel_datum"),
    ("omit_clearance_normalization", "/math.hypot(1, p, q)", "/1",
     "test_deck_clearance_uses_signed_normal_distance_and_keel_datum"),
    ("wrong_longitudinal_moment_power", "_linear_integral(xs, width, 2)",
     "_linear_integral(xs, width, 0)",
     "test_box_selected_waterline_has_exact_geometry_and_declared_girth_method"),
    ("discard_parameter_keel_shift", "[[y, z+keel] for y, z in poly]", "[[y, z] for y, z in poly]",
     "test_reference_materialization_is_explicit_estimated_and_datum_consistent"),
]
mutation_results = []
for name, before, after, test_name in mutations:
    assert source.count(before) == 1, name
    module = types.ModuleType("geometry_analysis_mutant")
    exec(compile(source.replace(before, after), str(package / "geometry_analysis.py"), "exec"),
         module.__dict__)
    checks.analysis = module
    result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([
        checks.GeometryAnalysisTests(test_name),
    ]))
    checks.analysis = geometry_analysis
    mutation_results.append(dict(name=name, detected=not result.wasSuccessful(),
                                 failures=len(result.failures), errors=len(result.errors)))
    print(f"{name}: {'DETECTED' if not result.wasSuccessful() else 'SURVIVED'}")
    if result.wasSuccessful():
        raise SystemExit(1)

refinement = []
for n, m in ((41, 48), (81, 96)):
    hull = geometry_analysis.materialize_reference_hull(checks.parameters(),
        keel_offset_m=0, source="independent reference study", estimate=True,
        n_stations=n, n_section=m)
    result = geometry_analysis.measures_at_plane(hull, checks.plane())
    refinement.append(dict(n_stations=n, n_section=m, values=result["values"],
                           content_sha256=hull["source"]["content_sha256"]))
deltas = {key: abs(refinement[1]["values"][key]-refinement[0]["values"][key])
              / abs(refinement[1]["values"][key])
          for key in ("volume_m3", "awp_m2", "it_m4", "kb_m")}
assert max(deltas.values()) < 0.01
box = geometry_analysis.measures_at_plane(checks.prism(), checks.plane())
triangle = geometry_analysis.measures_at_plane(checks.prism(triangle=True), checks.plane())
inclined = geometry_analysis.measures_at_plane(checks.prism(), checks.plane(p=0.05, q=0.2))
evidence = dict(method_version=geometry_analysis.METHOD_VERSION,
    tolerance=dict(exact_relative=1e-10, exact_absolute=1e-10, refinement_relative=0.01),
    box=box, triangle=triangle, inclined=inclined, refinement=refinement,
    refinement_relative_deltas=deltas, mutation_results=mutation_results)
target = Path(__file__).with_name("task-8-geometry-evidence.json")
target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
print("refinement_relative_deltas:", json.dumps(deltas))
print("6/6 focused mutations detected; production files untouched")
print("saved:", target)
