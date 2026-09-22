# Task 4 implementation report — DONE_WITH_CONCERNS

Date: 2026-09-22. The controller's shared full regression passed and the five
frozen Task 4 paths were committed as
`6f20e06dd8493cb88d42d76d5377237dc7d15e32` (`feat: solve loaded equilibrium and stability`).
Independent review remains a controller-owned gate; documented applicability
and numerical/model limitations below remain concerns, not hidden guarantees.

## Shared integration and scoped commit update

Read `.superpowers/sdd/2026-09-22-plimsoll-1.0/task-4-7-regression.json` and
`.log`: `python.exe -B tools/plimsoll/run_all_tests.py` ran **482 tests, zero
failures/errors, 137.817 s test time, 138.3065151 s checkpoint wall time**.
Source scope hashes were identical before/after that run. The earlier single
Task 7 warning failure is retained below as interim evidence; it is superseded
by this successful shared integration run. This agent did not rerun the suite.

Immediately before staging, all five hashes matched the frozen record and the
shared regression manifest; `git diff --check` and staged diff-check were clear.
The staged set and final commit each contained exactly these five authorized
paths. No controller evidence files or Task 7 files were staged; no push occurred.
Post-commit index was empty and the five paths had no working-tree difference
from HEAD. A command-local safe.directory setting for this exact worktree was
needed under the elevated Windows user to access external worktree Git metadata;
no global Git configuration or primary-checkout source files were changed.

## Scope / environment

Worktree: `C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`.
Base supplied by controller: `bf98a7b15515fd7c82506cf9807ad5ea533986da`.
Only these five deliverable paths were edited/created:

- `tools/plimsoll/stability.py`
- `tools/plimsoll/tests/test_stability_loading.py`
- `tools/plimsoll/geometry.py`
- `tools/plimsoll/geometric.py`
- `docs/plimsoll-1.0/stability-api.md`

Scratch reports/evidence are under `.superpowers/sdd/2026-09-22-plimsoll-1.0/`.
No Task 3 cases, Task 5 tank geometry, Task 7 production/tests, primary Desktop
checkout, Unity assets, original independent oracle scripts or project validator
were changed. `git diff` confirms both independent oracle scripts unchanged.

Executable (used with `-B` and `PYTHONIOENCODING=utf-8`):
`C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe`.
Actual captured `sys.version`:
`3.13.14 (main, Jun 11 2026, 04:04:46) [MSC v.1944 64 bit (AMD64)]`.
The directory label is not the runtime version.

## Implemented

Strict copied readiness adapter for canonical materialized polygons and legacy
five-number offsets, and explicit-datum stationed objects independent of import
class identity. Unknown keel/source remain explicit; polygon self-intersections,
nonfinite/bool coordinates, duplicate/unsorted stations, malformed sections,
zero extent/capacity and unresolved references fail. Point/line end sections and
flat closed ends are preserved. Per controller ruling, `parameters` remains
explicitly unsupported here; Task 8 retains L0 results and may separately
materialize a named, estimated reference hull with complete inputs and datum.

Free solve enforces displacement plus both projected horizontal moments.
Prescribed heel enforces the correct u-axis longitudinal condition, including
the p*q coupling term, and reports v-axis GZ. One slope-aware draft bracket
seeds simultaneous scaled d/p/q Newton iteration; bounded line search, central
Jacobian, contact-stencil refinement and explicit singular/failure handling do
not relax residual thresholds. An explicitly poor initial attitude can retry
neutral once, recording the failure; the solve is local, not a proof of global
branch uniqueness. No failed iterate is published as success.

Additional unique-ID liquids call reviewed Task 5 geometry at every attitude,
using requested volume for conserved mass and the same slopes. Base, added and
total mass/moments and liquid snapshots are reported separately. No additional
FSC. Existing base ledger IDs cannot also be additional liquid IDs; callers
still own physical deduplication under different aliases.

The controller approved optional fifth `options=None` on `stability_curve`.
It propagates density/datum/bounds/liquids through samples, ±0.01° initial
constrained derivative, bracketed zeros and opening immersion. Every row has
its own equilibrium/validity. Maxima/endpoints are sampled labels; model cutoffs,
failed samples and bracketed zeros stay distinct. Missing openings and actual
deck edges are unknown, roots after observed downflooding are not valid intact
AVS, and safety is always unknown. Geometry source/estimate and complete loading
provenance/uncertainty/identities remain visible. The later coordinator must
hash effective options as well as the returned base-loading fingerprint.

Shared kernel chord measure now sums occupied intervals, including exact
boundary edges, fixing U-section overcount and exact deck-contact omission.
`awp` is geometric intersection area, explicitly not a one-sided derivative at
contact. Legacy API return types/signatures remain; old trim is explicitly
labelled LCB-only. Unverified SpringSharp/physical-truth claims in both module
docstrings were replaced with method/assumption descriptions.

## RED → GREEN record

Focused command (all runs use the same cwd/executable above):

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_stability_loading.py
```

- Initial RED: 16 failures, 0.007 s. Fourteen missing-new-API assertions; actual
  kernel failures were U-section `awp=60` vs independently expected 40 and deck
  contact `awp=0` vs expected 20.
- Initial implementation: 14/16 passed. One 321-station continuous-box p error
  was `2.01418e-7` against predeclared `2e-7`; raised fixture resolution to 641,
  did not loosen tolerance. A steep shallow-hull initial seed followed a
  different moment branch; recorded neutral retry resolved the lower branch.
- 16/16 GREEN, 4.221 s.
- Expanded 26-test run: two API errors exposed missing fifth curve options and
  unstructured unsupported-geometry curve failure. After implementation,
  26/26 GREEN, 8.544 s.
- Expanded 29-test RED caught two real assertions: legitimate collinear end
  sections rejected, and initial 180° wrapped through tangent to a valid slope.
  Fixed readiness and validated initial angles before tangent conversion.
- Added genuinely high-trim shallow-prism analytical anchor: residual reduction
  stalled near section contact with the 1e-5 numerical Jacobian stencil. A
  smaller stencil resolved the kink while retaining the 1e-10 internal target
  and 1e-6 published maximum; no tolerance relaxation.
- Latest focused GREEN after all production changes: **31 tests, 9.506 s**.
  All raw physical arms are independently reconstructed in the test helper from
  returned B/G/p/q, rather than trusting serialized residual claims alone.
- `git diff --check` returned no output. No full-suite pass is claimed.

## Selected compatibility regression (interim shared-work snapshot)

Exact command body executed through a PowerShell here-string piped to the
bundled `python.exe -B -`, with UTF-8 environment:

```python
import sys,unittest,time
sys.path.insert(0,'tools/plimsoll/tests')
names=['test_stability_loading','test_geometric','test_trim_equilibrium',
       'test_offsets_import','test_hull','test_freesurface','test_damage_loop',
       'test_calculation_integrity','test_loading','test_project_io']
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
start=time.perf_counter()
result=unittest.TextTestRunner(verbosity=1).run(suite)
print('SELECTED_REGRESSION_SECONDS',time.perf_counter()-start)
sys.exit(not result.wasSuccessful())
```

**203 tests / 147.402 s: 202 passed, 1 failed.** The exact failure was
`test_calculation_integrity.CalculationIntegrity.test_reynolds_warning_survives_curve_and_identifies_speed`,
line 57, missing a warning containing both `Schoenherr` and `28.1` in
`out['warnings']`. Root was notified and routed this shared active-resistance
issue to Task 7. The controller explicitly requested no repeated 147-second
selected suite for the unrelated Task 7 change; one shared full suite follows
both freezes. This is not presented as a passing regression or completion gate.

## Independent numerical evidence

Unchanged oracle files: `docs/plimsoll-1.0/evidence/coupled_box_oracles.py` and
`coupled_ellipsoid_oracles.py`. Raw machine-readable fixture outputs, actual
runtime and solver residuals are in scratch `task-4-numerical-evidence.json`.
Production integrations were never used to generate continuous expected values.

Ellipsoid simultaneous refinement:

| Stations × points | Mode | p | q | d m | GZ m | Max scaled residual | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 41 × 32 | free | .0100082075653 | .100006348369 | 4.02153265007 | -2.06e-14 | 3.45e-13 | .0606 |
| 81 × 64 | free | .0100021375615 | .0999982922299 | 4.00540263050 | -6.47e-15 | 4.37e-14 | .1944 |
| 161 × 128 | free | .0100005461628 | .0999997194257 | 4.00134846005 | -3.75e-15 | 4.51e-14 | .8550 |
| 41 × 32 | prescribed | .0100082044800 | .1 | 4.02153326406 | .149987419258 | 8.45e-17 | .0505 |
| 81 × 64 | prescribed | .0100021400808 | .1 | 4.00540246204 | .150003402373 | 3.08e-16 | .1794 |
| 161 × 128 | prescribed | .0100005466523 | .1 | 4.00134843226 | .150000558461 | 3.08e-16 | .8145 |

Final adjacent relative changes (predeclared scales p=.01,q=.1,d=4,V=oracle V;
near-zero GZ and small B coordinates use 1 m): free p .015914%, q .001427%,
d .101354%, B components .003427%, .035014%, .136313%. Prescribed p .015934%,
d .101351%, GZ .0002844%, B components .003424%, .034670%, .136326%.
All <1%. Final continuous d error .033711%; p error .005467%; prescribed GZ
absolute error 5.5846e-7 m. Own-equilibrium residuals are listed separately.

Separated refinement also compares (81,128)→(161,128) and
(161,64)→(161,128), independently asserted <1% for p/d/GZ. Raw free and
prescribed outputs for these resolutions are retained in the JSON.

High-trim shallow-prism direct continuous integrals:
`h(x)=clamp(p*(x-40)+.5,0,1)`, target volume 100 m³, p=tan(20°),
`Bx=45-1/(240*p²)`, `Bz=.5-1/(120*p)`, KG=.5. At 1601 stations the solver
returned p=.3635741576781193, d=-14.042966307124802 m, V=99.99999999999915 m³;
scaled residuals V=-8.669e-15 and longitudinal=2.118e-14. Support was
[-18.178707883935143,19.178707883935143] m, demonstrating a reachable solution
far outside old upright-z brackets. Five iterations, 56 residual evaluations,
final difference stencil 1e-6, observed 0.5405 s. The p error remains <1%.

## Selected mutation evidence

`task-4-mutation-evidence.json` contains exact failure output for four isolated
in-memory module mutations; production files were never changed for mutation.
All four were caught by assertions, zero test errors:

1. u-axis arm replaced by legacy `delta_x` → free coupled box/mirror failed.
2. u-axis arm replaced by `(delta_x+p*delta_z)/sqrt(1+p²)` → prescribed coupled
   box failed, proving the omitted p*q coupling is observable.
3. `base_cg[2] += keel` replaced by `+=0` → coupled translated-datum test failed.
4. Both liquid attitude arguments frozen at zero → moving-liquid initial slope
   test failed, detecting removal of actual liquid movement.

The first keel mutation probe survived the original upright-volume-only test:
upright centered equilibrium is independent of KG. This exposed a real coverage
gap. Added explicit effective CG checks and the inclined translated-datum
regression; the same mutation then failed. This is reported rather than hiding
the survived initial probe. The final unmutated suite passed afterward.

Exact reproducible numerical/mutation command (the saved script contains the
full fixture, timing and mutation commands and creates separate reproduced JSON):

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B .superpowers/sdd/2026-09-22-plimsoll-1.0/task-4-reproduce-evidence.py
```

## Limits / review focus

- The sampled polygon/trapezoidal representation is a finite sealed envelope,
  not verified ship geometry or arbitrary mesh physics.
- Local bounded Newton does not enumerate equilibrium branches or certify
  global stability. Singular, near-saturated (capacity margin 1e-12), unsupported
  and exhausted cases explicitly fail. Accepted result residual remains ≤1e-6.
- General waterplane area is a geometric intersection, not a contact derivative.
  Deck edges cannot be inferred from arbitrary source polygons and remain unknown.
- Initial stiffness is the actual constrained dGZ/dheel at zero, with moving
  liquids if specified; for off-center loading it is not automatically GM.
- Sparse angle samples may miss intermediate zeros/opening dips. Only observed
  sign brackets are refined; maxima and endpoints remain explicitly sampled.
- Missing opening information means unknown intact AVS. Even positive stiffness
  never changes `safe=null` or `historical_validated=null`.
- Additional options/liquids must participate in later analysis/cache hashes;
  this API preserves the original loading fingerprint exactly.
- Shared full regression passed as recorded above. Independent spec/quality
  review remains a controller-owned gate; the commit does not substitute for it.
