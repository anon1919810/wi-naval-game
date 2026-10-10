# Offline numerical convergence study: findings and limitations

Date 2026-10-10. This records a reproducible, offline study of the implemented
Plimsoll numerics against independent analytic answers. It measures numeric
convergence only. It does **not** establish physical accuracy, statutory
stability compliance, historical ship accuracy or SPS superiority, and it makes
no claim about any real vessel.

## Reproducible command

From the repository root, using the project virtual environment:

```powershell
& web/backend/.venv/Scripts/python.exe tools/plimsoll/tools/convergence_study.py --output-dir C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/numerical-convergence-2026-10-10/codex
```

The runner uses only the Python standard library plus the repository's own
modules. It makes no network call, writes no production state, and its result
does not depend on the current working directory; an absolute `--output-dir`
works from anywhere. It writes `convergence-study.json`,
`convergence-study.csv` and `convergence-study.md`, and exits `0` when every
declared check passes and `1` when any fails. `--help` runs no study and
writes nothing.

Every number quoted below is taken from the retained
`convergence-study.json` produced by that command. The observed status was
**pass, 98 of 98 declared checks**. Sources and supplied fixtures were hashed
before and after the run and were unchanged.

The independently accepted JSON is retained in
[the evidence snapshot](evidence/numerical-convergence-2026-10-10.json), including
all measurements, declared limits, 13 full source hashes and method versions.
This is an offline study added after the public runtime release `a863b0e`;
the numerical kernels are byte-identical to that frozen release.

## Source identity

The report hashes every actual kernel, fixture builder, oracle and study file
before and after the run, and never hashes its own output:

| file | role |
| --- | --- |
| `tools/plimsoll/stability.py` | runtime loaded equilibrium and GZ curve |
| `tools/plimsoll/geometry.py` | runtime polygon-section hydrostatics |
| `tools/plimsoll/flooding.py`, `_flooding_kernel.py` | runtime flooding driver and flow kernel |
| `tools/plimsoll/loading.py`, `project_io.py`, `tank_geometry.py`, `offsets.py` | runtime supporting kernels |
| `tools/plimsoll/tools/convergence_fixtures.py` | study fixture builder |
| `tools/plimsoll/tools/convergence_study.py` | study runner and writers |
| `docs/plimsoll-1.0/evidence/coupled_ellipsoid_oracles.py` | existing independent ellipsoid oracle (unmodified) |
| `docs/plimsoll-1.0/evidence/flooding_oracles.py` | existing independent coupled-heave oracle (unmodified) |
| `docs/plimsoll-1.0/evidence/wall_sided_box_oracle.py` | new independent wall-sided GZ oracle |

Method versions reported: `loaded-projected-equilibrium-2`,
`connected-quasi-static-flooding-3`, kernel `vented-orifice-network-2`, solver
residual tolerance `1e-6`.

## 1. Geometry: hull discretization

Fixture: ellipsoid semi-axes 20/5/5 m centred at z = 5 m, waterplane
`p = 0.01`, `q = 0.1`, `d = 4 m`, rho = 1.025 t/m³, KG = 3 m, prescribed
GZ = 0.15 m. The reference answers come from the pre-existing independent
sliced-ellipsoid oracle, which is continuous and is never fitted to a sampled
hull. Each mesh is built by analytic ellipse sampling at cosine-spaced
longitudinal stations.

Three evaluations are run per mesh: direct integration of the specified
waterplane plane, the public free-equilibrium solver, and the public solver
with the analytic heel prescribed.

Refinement ratios use the number of **intervals** for station meshes and the
number of **nodes** for section vertices. A 41/81/161 station mesh has
40/80/160 intervals and therefore halves exactly; the reported ratios are 2.0
and 2.0. Observed orders of the direct-plane volume error against the
continuous oracle:

| sequence | refinement | volume abs error (m³) | ratio | observed order |
| --- | --- | --- | --- | --- |
| stations | 41 stations, 128 vertices | 1.1178e+00 | — | — |
| stations | 81 stations, 128 vertices | 5.4681e-01 | 2.0 | 1.032 |
| stations | 161 stations, 128 vertices | 4.0447e-01 | 2.0 | 0.435 |
| vertices | 161 stations, 32 vertices | 5.7193e+00 | — | — |
| vertices | 161 stations, 64 vertices | 1.4774e+00 | 2.0 | 1.953 |
| vertices | 161 stations, 128 vertices | 4.0447e-01 | 2.0 | 1.869 |

### Fixed-axis effects and the finite finest-mesh comparison

Each sequence holds the other axis fixed, so refining one axis does not remove
the other axis's discretization error. The raw longitudinal order of 0.435
describes these measured meshes; it does not isolate the asymptotic order of
longitudinal integration or establish how much of the error comes from each
axis. The report publishes a separate `finest_mesh_comparison` block that subtracts the
**finite finest mesh error** of the same sequence. This is explicitly a
comparison between measured meshes, **not** a measured or analytic floor for
the fixed axis, and it is flagged `used_for_acceptance: false`; it never
contributes to pass or fail. The raw observed orders remain the reported
evidence.

Both order series require adjacent valid levels. A failed intermediate level
is retained as a gap: recovery cannot reuse an earlier error with the adjacent
refinement ratio, and the comparison series cannot compress that gap away.

The `order_interpretation` metadata identifies solved volume and free-GZ as
equilibrium constraints, with their actual residual scales. It leaves other
solved-state errors unclassified: comparing an error with a solver tolerance
cannot identify it as round-off or separate solver and mesh contributions.

Accuracy at the shared finest mesh (161 stations × 128 vertices), worst case
across evaluations, against the predeclared limits:

| quantity | observed | declared limit | ratio |
| --- | --- | --- | --- |
| volume relative error | 5.473e-04 | 1e-3 | 0.547 |
| buoyancy centre x error | 9.412e-05 m | 0.01 m | 0.009 |
| buoyancy centre y error | 1.166e-04 m | 0.01 m | 0.012 |
| buoyancy centre z error | 1.165e-03 m | 0.01 m | 0.117 |
| waterline d error | 1.348e-03 m | 0.01 m | 0.135 |
| trim slope p error | 5.467e-07 | 1e-4 | 0.005 |
| heel slope q error | 2.806e-07 | 1e-4 | 0.003 |
| prescribed GZ error | 5.585e-07 m | 0.001 m | 0.0006 |

Worst scaled equilibrium residual over every declared solved state was
6.985e-14, against the declared 1e-6.

## 2. GZ sampling: solver accuracy and curve quadrature are different metrics

Fixture: sealed empty rectangular prism 40 × 10 × 10 m, draft 4 m, KG 3 m,
rho 1.025 t/m³, mass 1640 t, 21 stations, no openings and no liquids. The new
independent oracle derives from the submerged column `h(y) = T + y*tan(phi)`
that `BM = B²/(12T)`, `GM = T/2 + BM - KG`, and
`GZ = (GM + BM*tan(phi)²/2)*sin(phi)`. The closed-form area under the lever in
radians is `GM*(1-cos P) + BM/2*(1/cos P + cos P - 2)`, using
`∫ sin³φ/cos²φ dφ = 1/cos φ + cos φ`. For this fixture
`BM = 2.083333… m`, `GM = 1.083333… m`, `GZ(30°) = 0.7152777778 m`, and the
exact area to 30° is 0.16672866898736885 m·rad, confirmed to 12 decimal
places by an independent Simpson integration of the same lever
(0.16672866898736924 m·rad).

The oracle is bounded: `abs(tan(phi))*B/2 < min(T, depth-T)` gives an
exclusive wedge of ±38.659808°. `bounds_ok` rejects that boundary and
everything beyond, `gz_m` refuses to return a value outside the wedge rather
than extrapolating a lever the derivation never defined, and `require_valid_angle_deg`
raises with the offending value. The wedge boundary is a geometry limit: the
oracle reports `first_zero_gz_deg` as `null` with an explicit reason, because
it is neither a zero of the righting lever nor an angle of vanishing
stability, and this study makes no AVS claim in this range.

The two metrics are reported separately and never merged:

| step (deg) | samples | fixed-angle max error (m) | common-angle max error (m) | curve area relative error | area order |
| --- | --- | --- | --- | --- | --- |
| 5 | 7 | 8.882e-16 | 8.882e-16 | 3.6370e-03 | — |
| 2.5 | 13 | 2.109e-15 | 8.882e-16 | 9.1062e-04 | 1.998 |
| 1.25 | 25 | 2.887e-15 | 8.882e-16 | 2.2774e-04 | 1.999 |
| 0.625 | 49 | 2.887e-15 | 8.882e-16 | 5.6940e-05 | 2.000 |

Fixed-angle agreement is already at double-precision round-off at every
sampling level, well inside the declared 1e-6 m, and it does **not** improve
with a smaller step. The curve-area error is roughly four times smaller per
halving, an observed order near 2.0 consistent with composite trapezoidal
quadrature, and the finest relative error 5.694e-05 is inside the declared
1e-4. A curve can therefore be sampled to machine precision and still
integrate inaccurately; the curve-area metric measures that sampling error.

Convergence and model applicability are tracked separately. A sample must
explicitly report `model_applicable` as boolean `true`; absent, null, false,
string, numeric and non-finite claims are unusable. Such a sample, or one whose
endpoint kind is `model_limit`, is
retained as a failed sample and fails acceptance even when its lever number
looks acceptable. Missing, `null`, boolean, string, NaN and infinity levers are
rejected as failed samples *before* any quadrature is attempted, so a missing
lever can never raise a `TypeError` or enter a sum.

## 3. Flooding: time integration

Fixture: centred 20 × 10 × 6 m hull, base mass 401.8 t at KG 1 m, one 4 × 2 × 4
m vented tank initially holding 8 m³, sea rho 1.025 t/m³, Cd 0.6, area
0.1 m², point aperture at z = 0.1 m, duration 5 s, against the existing
independent coupled-heave ODE oracle.

| dt (s) | status | steps | inflow relative error | draft-change relative error | observed order | max scaled residual | volume cons (m³) | mass cons (t) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5 | completed / scheduled_completion | 10 | 3.9978e-03 | 3.9978e-03 | — | 1.050e-14 | 0.0 | 4.441e-16 |
| 0.25 | completed / scheduled_completion | 20 | 1.9948e-03 | 1.9948e-03 | 1.003 | 9.352e-15 | -2.887e-15 | -3.331e-15 |
| 0.125 | completed / scheduled_completion | 40 | 9.9634e-04 | 9.9634e-04 | 1.001 | 1.094e-14 | 4.441e-16 | 1.110e-15 |
| 0.0625 | completed / scheduled_completion | 80 | 4.9791e-04 | 4.9791e-04 | 1.001 | 1.105e-14 | -3.997e-15 | -3.331e-15 |
| 0.03125 | completed / scheduled_completion | 160 | 2.4889e-04 | 2.4889e-04 | 1.000 | 1.093e-14 | -4.663e-15 | -4.219e-15 |

Both normalized errors decrease monotonically, the finest is 2.489e-04 against
the declared 1%, conservation is at round-off against the declared 1e-9 m³
and 4.1e-8 t, and every accepted state satisfies the scaled residual limit.

The observed time order is close to 1.0. This is reported as **evidence about
the implemented integration**, not as an automatic claim of a higher-order
scheme. It is consistent with the explicit Euler update in the runtime. This
fixture accepted the requested steps; adaptive rejection and halving remain
available in the implementation. The study does not prove an order for every
scenario or adaptive step sequence.

### Accepted-state integrity

Every accepted timeline state and the final state are checked independently
for boolean convergence and for finite values of the required scaled residual
components `volume`, `longitudinal` and `transverse`, the heel and trim
angles, the waterline draft, the tank volumes, and the presence of the
expected tank ID. A state that is missing any of these is recorded as broken
and makes the whole level's maxima unavailable rather than being dropped in
favour of its healthy neighbours.

The all-state residual and attitude extrema include the separate final-state
object. A finite final residual above `1e-6` fails the same magnitude limit
even if every timeline row reports zero; an incomplete or unconverged final
object makes those all-state extrema unavailable.

Time consistency is verified without assuming the public result object's
internal aliasing: accepted times must start at zero and never decrease, and
both the last timeline time and the separate final-state time must equal the
declared duration and each other. Conservation limits apply to the
**magnitude** of the signed error; the signed value is retained in every
evidence format as the observation, so a large negative conservation error
fails exactly as a large positive one does.

## Honest evidence on failure

A failed, model-limited or non-finite sample is never dropped and never
converted into a passing zero error. Missing is reported as *unavailable*,
distinct from zero. Concretely, the study fails acceptance and exits 1 when a
coarse geometry level raises while the finest would pass; when a required
scaled residual component is missing or non-finite; when convergence is not
the boolean `true`; when any required metric is absent; when a GZ lever is
missing or not a finite number; when a GZ row or endpoint reports the model
does not apply; when an accepted flooding state or the final state is
incomplete or unconverged; when the timeline and final-state times disagree;
and when a hook raises anywhere. On every one of those paths the study still
writes JSON, CSV and Markdown and exits 1, and the failing angle, status,
reason and diagnostics appear in all three formats.

Raw flags are validated before the assembled report is copied into strict
JSON form. Non-finite metadata becomes null in place while the rejected
status and its reason survive, so a NaN/Inf convergence or applicability
claim cannot either pass or prevent the failure report from being written.

These behaviours are locked by regression tests in
`tools/plimsoll/tests/test_convergence_study.py`, including positive controls
built on independently derived analytic answers, so that a rejection of valid
input would itself be a visible failure.

## Verification performed

- Codex independently ran the whole core suite with `PYTHONPATH` set to the
  repository's `tools` directory and
  `web/backend/.venv/Scripts/python.exe -u -m pytest tools/plimsoll/tests -q`
  → **895 passed, 594 subtests passed**, 402.11 s, exit 0.
- That pytest count includes the existing `test_generic_ship.py::testbed_weights`
  helper, which pytest collects as a function test and reports with one
  `PytestReturnNotNoneWarning` because it returns a dictionary. Subtests are
  counted separately above; the runtime identities are verified below.
- The study command above → **exit 0, 98/98 checks passed**, with all source and fixture hashes unchanged.
- Independent analytic recalculation verified the ellipsoid volume/centres,
  wall-sided levers/area and coupled-heave inflow/draft, as well as the reported
  errors. A separate water-column and Simpson cross-check agreed to approximately
  1e-10 m and 1e-16 m·rad on the box fixture.
- Codex's separate adversarial harness → **21/21 passed**: three valid controls
  and eighteen failure cases. Every failure returns a failing report, writes
  JSON/CSV/Markdown and produces exit 1. Raising hooks, missing/NaN residuals,
  missing levers, absent/non-boolean/non-finite applicability, tank volumes,
  final-state convergence and residual bounds, time mismatch and negative
  conservation errors are covered. Additional regression subcases ensure that
  failed refinement levels remain gaps in both observed-order series.
- Independently checked all **100 frozen runtime files** against the public
  release manifest; none changed. The final local evidence, including failed
  review snapshots, is in the task output directory
  `outputs/numerical-convergence-2026-10-10/`.
- Fixture identity is part of each suite's result and the overall acceptance.
  A mutation fails even if a later GZ call restores the global payload; each
  call's before/after hash is checked separately.
- `git diff --cached --check` → clean.

## Remaining limitations

- External experimental and model-basin validation is **pending**. Nothing in
  this report substitutes for it, and no result here is evidence about a real
  ship's hydrostatics, stability or flooding behaviour.
- The oracles are continuous integrals of idealised bodies: an ellipsoid, a
  closed wall-sided prism, and a symmetric box with a point orifice. They test
  the chosen model and its numerics, not a vessel.
- The flooding anchor fixes one constant-Cd orifice law, a single fluid
  density, no trapped air, no waves, no sloshing and no structural failure.
  Agreement here is agreement with that chosen ODE.
- The geometry sequences each hold one axis fixed, so neither sequence isolates
  a single error source, and the finite-finest-mesh comparison is a
  mesh-to-mesh difference rather than an analytic decomposition.
- Observed orders are empirical trends over three to five levels on these
  meshes. They are not proofs of asymptotic order and they do not extrapolate
  beyond the refinements actually run.
- No AVS, downflooding angle or statutory stability criterion is computed,
  claimed or implied anywhere in this study.
