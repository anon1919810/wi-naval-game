"""Read-only numerical probe: legacy LCB target versus full moment balance."""
from pathlib import Path
import json
import math
import sys

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'tools/plimsoll'))
from geometry import StationedHull

length, beam, draft, kg = 40.0, 10.0, 4.0, 3.0
poly = [(-beam/2, 0.0), (beam/2, 0.0), (beam/2, 10.0), (-beam/2, 10.0)]
hull = StationedHull([(-length/2 + length*i/160, poly) for i in range(161)])
volume = length * beam * draft
legacy = hull.solve_trim_equilibrium(volume, 1.0)
p = math.tan(legacy['trim_rad'])
full_moment_arm = (legacy['xlcb_m'] - 1.0) + p * (legacy['hydrostatics']['zb'] - kg)
evidence = {
    'probe': 'legacy_lcb_constraint_is_not_finite_trim_moment_equilibrium',
    'inputs': {'length_m': length, 'beam_m': beam, 'depth_m': 10.0,
               'target_volume_m3': volume, 'lcg_m': 1.0, 'kg_m': kg,
               'stations': 161, 'coordinates': 'keel z=0, x forward, y starboard'},
    'legacy_result': legacy,
    'full_longitudinal_moment_arm_m': full_moment_arm,
    'scaled_moment_residual': full_moment_arm / length,
    'predeclared_new_solver_tolerance': 1e-6,
    'status': 'legacy target passes, full moment condition fails; correction pending Task 4',
}
assert abs(legacy['lcb_residual_m']) < 1e-6
assert abs(full_moment_arm / length) > 1e-6
dest = root / 'docs/plimsoll-1.0/evidence/legacy-trim-moment-probe.json'
dest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'evidence': str(dest), 'full_moment_arm_m': full_moment_arm,
                  'scaled_residual': full_moment_arm / length}, ensure_ascii=False))

