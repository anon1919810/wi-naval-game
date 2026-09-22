"""Run from the Plimsoll worktree root; isolate mutations in memory only."""
import io
import json
from pathlib import Path
import sys
import time
import types
import unittest

sys.path.insert(0, 'tools/plimsoll/tests')
import test_stability_loading as tests

directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('work/stability-verification')
directory.mkdir(parents=True, exist_ok=True)
production = tests.stability
oracle = tests.oracle('coupled_ellipsoid_oracles.py')
rows = []
for n, m in ((41,32),(81,64),(161,128),(81,128),(161,64)):
    for mode in ('free','prescribed'):
        cg_key = 'free_equilibrium_cg_m' if mode=='free' else 'constrained_heel_cg_m'
        options = {} if mode=='free' else {'heel_deg':oracle['waterplane']['heel_deg']}
        start = time.perf_counter()
        result = production.solve_loaded_equilibrium(tests.ellipsoid(n,m),
            tests.load(oracle['mass_t'],oracle[cg_key]),options)
        elapsed = time.perf_counter()-start
        assert result['converged'], result
        rows.append(dict(stations=n,vertices=m,mode=mode,converged=result['converged'],
            seconds=elapsed,p=result['p'],q=result['q'],d=result['waterline_d_m'],
            gz=result['gz_m'],b=result['buoyancy_centre_m'],volume=result['volume_m3'],
            residuals=result['residuals'],solver=result['solver']))
report = {'runtime':sys.version,'oracle':oracle,'ellipsoid':rows}
(directory/'task-4-numerical-evidence-reproduced.json').write_text(
    json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print('Ellipsoid evidence: 10 converged states; max scaled residual',
      max(abs(v) for row in rows for v in row['residuals']['scaled'].values()))

source = Path('tools/plimsoll/stability.py').read_text(encoding='utf-8')
mutations = [
    ('legacy_lcb_only','_dot(delta,u)','delta[0]','test_free_coupled_box_and_mirror'),
    ('omit_constrained_coupling','_dot(delta,u)',
     '(delta[0]+p*delta[2])/math.sqrt(1+p*p)',
     'test_prescribed_heel_uses_projected_longitudinal_axis'),
    ('omit_keel_conversion','base_cg[2] += keel','base_cg[2] += 0',
     'test_inclined_explicit_keel_translation_preserves_physical_attitude'),
    ('freeze_moving_liquid',
     'heel_deg=math.degrees(math.atan(q)),trim_deg=math.degrees(math.atan(p)))',
     'heel_deg=0,trim_deg=0)',
     'test_moving_liquid_conserves_mass_and_its_stiffness_has_no_second_fsc'),
]
results = []
for name,old,new,test in mutations:
    assert old in source
    module = types.ModuleType('stability_mutant')
    exec(compile(source.replace(old,new),'stability_mutant.py','exec'),module.__dict__)
    tests.stability = module
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream).run(
        unittest.TestSuite([tests.LoadedStability(test)]))
    results.append(dict(name=name,test=test,caught=not result.wasSuccessful(),
        failures=len(result.failures),errors=len(result.errors),output=stream.getvalue()))
    print(name, 'CAUGHT' if not result.wasSuccessful() else 'SURVIVED')
tests.stability = production
(directory/'task-4-mutation-evidence-reproduced.json').write_text(
    json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(row['caught'] and row['failures']==1 and row['errors']==0 for row in results)
