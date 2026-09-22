# Task 6 connected-flooding implementation report

Status: **READY_FOR_INTEGRATION**

Date: 2026-09-22

The initial scratch-only flow-kernel preparation is preserved below. After the
controller approved Task 4 and Task 5, the same design was promoted into the
owned Task 6 production paths and integrated with repeated Task 4 equilibrium
and Task 5 liquid geometry. No Task 4, Task 5, Task 7 or Task 8 file was edited.
The shared full suite and commit remain reserved for controller integration.

## Phase 1 scratch artifacts

- `task-6-prototype/flooding_kernel.py`
- `task-6-prototype/test_flooding_kernel.py`
- this report

All are ignored by `.superpowers/sdd/.gitignore`.

## Prepared design

The prototype exposes three deliberately non-production functions:

- `evaluate_flows(...)`: validates unique tank/edge IDs, explicit density,
  `Cd`, area, valve state, source/estimate metadata and non-dangling node IDs;
  resolves Task 5 `liquid_state` for each tank; and evaluates signed rates.
- `step_fixed_attitude(...)`: applies one conservative explicit-Euler network
  step. It aggregates all outgoing and incoming rates by tank before choosing
  an admissible duration. Every internal transfer is one signed quantity
  applied with equal and opposite tank deltas; there is no per-node clamp.
  Candidate states are recomputed and the step is halved before head reversal,
  unsupported partial-aperture state, or unresolved liquid geometry.
- `simulate_fixed_attitude(...)`: retains the `t=0` state, strictly increasing
  accepted times, actual step sizes, individual edge flows/transfers,
  cumulative sea exchange, and total volume/mass conservation residuals.

Heads use the shared unit normal
`(-tan(trim),-tan(heel),1)/sqrt(1+p^2+q^2)`. Tank and aperture coordinates are
keel-relative; `geometry_keel_offset_m` translates both into the sea plane's
geometry datum before the dot products. Partial tank planes come only from the
reviewed Task 5 `liquid_state`; no clipping or centroid solver was copied.

The sea is a distinct explicit node. Every connected tank, sea node and edge
must declare exactly the same positive `fluid_density_kg_m3`. Density does not
enter the incompressible volume-flow law, but it is retained and used for the
independent mass ledger. Missing `Cd`, density, source or estimate is invalid;
booleans and non-finite numerics are rejected by the kernel or Task 5 geometry.

The full-tank head convention is the upper support plane of the rectangular
tank along the common normal. This permits physically directed outflow from a
full vented tank. Any continued inflow into a full tank stops with
`status=model_limit, stop_reason=receiver_capacity`; no pressure, overflow or
discard is invented. An empty tank has zero head. Zero permeability therefore
has zero capacity and stops attempted inflow visibly.

Finite aperture height is optional applicability information. If a liquid
surface intersects an open, nonzero aperture, rate is `null` and the evaluator
returns `model_limit/partial_aperture_unsupported`. A closed or zero-flow edge
remains zero-flow and does not disable the tank free surface. Pressure fields
are explicitly rejected as outside this vented model.

## RED to GREEN evidence

Interpreter command prefix:

```text
PYTHONIOENCODING=utf-8
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B
```

The executable reports Python `3.13.14` despite its directory name.

Observed RED runs:

1. Initial focused run failed with `ModuleNotFoundError: flooding_kernel`.
2. The first implementation run exposed the wrong project-root resolution,
   then two behavior failures: the mirror edge direction in the test fixture
   and an aggregate-budget fixture that equalized before dry-out. The fixtures
   were corrected to the independently intended physical cases.
3. The mass-ledger test failed with missing
   `initial_total_mass_kg`/`cumulative_sea_exchange_kg` fields before those
   fields were implemented.
4. The closed finite-aperture test failed because the evaluator returned
   `model_limit`; valve/zero-flow precedence was then corrected.

Final focused command:

```text
python.exe -B -m unittest -v test_flooding_kernel.py
```

Result: `Ran 12 tests ... OK`.

The independent oracle command was also run directly and emitted:

- paired-tank exact transfer at 5 s: `1.24034731541798 m3`;
- fixed-sea exact inflow at 5 s: `1.8348043474001763 m3`;
- combined `p=.1, q=.2` heads: port `1.3174650984805198 m`,
  starboard `1.122285083890813 m`;
- combined inclined rate: `0.11739355624798266 m3/s`.

Prototype refinement evidence, using the predeclared `0.5, 0.25, 0.125 s`
sequence:

| Case | dt (s) | transfer (m3) | absolute error (m3) | volume residual (m3) | mass residual (kg) |
|---|---:|---:|---:|---:|---:|
| paired tanks | 0.5 | 1.2486178781133503 | 0.008270562695370298 | -7.105427357601002e-15 | -7.275957614183426e-12 |
| paired tanks | 0.25 | 1.24446787514945 | 0.004120559731469964 | 0 | 0 |
| paired tanks | 0.125 | 1.2424039292659739 | 0.0020566138479938267 | 0 | -3.637978807091713e-12 |
| fixed sea | 0.5 | 1.8391224090727167 | 0.004318061672540452 | 1.3322676295501878e-15 | 2.2737367544323206e-13 |
| fixed sea | 0.25 | 1.8369607816351206 | 0.002156434234944271 | -8.881784197001252e-16 | -1.3642420526593924e-12 |
| fixed sea | 0.125 | 1.8358819161731788 | 0.0010775687730024686 | 5.10702591327572e-15 | 5.229594535194337e-12 |

Errors decrease at every halving. Finest relative errors are
`0.1658095133862386%` (paired tanks) and `0.05872935577732461%` (fixed sea),
both below the predeclared 1% bound. Every volume residual satisfies
`1e-10*max(1,total volume,absolute sea exchange)` independently of the ODE
error; mass residuals satisfy the analogous scale.

The focused tests also cover the exact inclined head/rate anchor at `1e-10`,
datum translation, port/starboard mirroring, closed/zero/equal/reversed flow,
dry and full bounds, zero permeability, no apertures, closed-valve active free
surface, sea inflow/outflow balance, shared-source aggregate budgeting,
large-step reversal avoidance, partial-aperture model limits, unsupported
pressure fields, density mismatch, ordered time history and scheduled stop.

## Deliberate limits before promotion

- This is fixed-attitude validation only. It does not call Task 4 equilibrium,
  expose `simulate_flooding`, compute GZ snapshots, or claim ship survival.
- Repeated floating equilibrium, equilibrium-failure retention, downflooding
  events, cancellation and deterministic scenario presets remain integration
  work after the Task 4 API is accepted.
- The integrator is bounded first-order explicit Euler. Refinement is verified
  for the declared anchors; no higher-order accuracy is claimed.
- The model is one incompressible vented fluid with a static sea plane and a
  fully submerged point-orifice approximation. Compressed air, pressure
  networks, partially wetted finite openings, waves, sloshing and unmodeled
  overflow stop or remain outside the model.
- Tank geometry is the reviewed rectangular Task 5 domain. Its unsupported
  partial-volume/angle/numerical states propagate visibly; the kernel does not
  substitute another liquid solver.
- The prototype has not been exercised against the in-progress Task 4/7 shared
  full suite, by explicit phase instruction.

## Production integration

Owned production artifacts:

- `tools/plimsoll/_flooding_kernel.py`: private, reusable conservative
  pressure-head/orifice network and fixed-attitude validation driver;
- `tools/plimsoll/flooding.py`: public `simulate_flooding(...)` driver with
  repeated full equilibrium, bounded retries, ordered accepted states,
  cancellation, failure retention, downflooding and optional remaining GZ;
- `tools/plimsoll/tests/test_flooding.py`: independent fixed and coupled
  validation plus public-contract and replay coverage;
- `tools/plimsoll/cases/projects/damage-presets.json`: deterministic generic
  single/two-connected/asymmetric/closed-valve cases and explicit Queen Mary
  engineering proxies;
- `docs/plimsoll-1.0/flooding-api.md`: public schema, semantics, limits and
  legacy migration contract.

The private kernel was created because pressure-head evaluation, aggregate
network budgeting and the independently testable fixed-attitude integrator are
one cohesive numerical component. The public module owns project/loading
resolution and quasi-static equilibrium feedback. This ownership decision was
recorded before the private module was written.

The public result uses schema `plimsoll-flooding-result-1` and method
`connected-quasi-static-flooding-1`. Scenario water is additional mass.
Every accepted candidate is passed to `solve_loaded_equilibrium` with its
current Task 5 liquid loads; the converged waterline intercept is converted to
the common unit-normal sea-plane offset before flows are reevaluated. Failed
candidates never enter the timeline. The last accepted state remains available
on bounded equilibrium, timestep, capacity, aperture or callback stops.

### Production RED to GREEN evidence

The production tests initially failed because the two production modules did
not exist. Subsequent focused RED cases exposed and fixed these contract gaps:

1. over-capacity initial water first reached equilibrium and was reported as
   an equilibrium failure; scenario validation now calls Task 5 before any
   equilibrium solve and returns `invalid_input`;
2. an unknown option could reach scheduled completion; all options are now
   validated before simulation;
3. private `from_node_id`/`to_node_id` keys leaked through the public flow
   record; public records now use `from`/`to` while retaining signed flow;
4. unordered remaining-GZ angles raised from Task 4 after the flooding
   simulation; the public boundary now rejects them as structured invalid
   input before producing a timeline.

The focused production suite covers the fixed paired-reservoir and sea ODE
refinements, sea inflow and outflow, no edges, equal/reversed/closed/zero flow,
dry/full/capacity limits, aggregate shared-node budgets, zero permeability,
finite partial apertures, combined heel/trim head, datum translation, mirror
symmetry, coupled heave feedback, immutable deterministic replay, cancellation,
initial equilibrium failure, downflooding, invalid metadata/finite/boolean
inputs, missing openings, active free surface behind a closed valve, current
liquid loads in remaining GZ, and generic/Queen Mary preset replay.

Explicit `scenario.openings=null` is the sanctioned persistence bridge for
unknown opening knowledge. It overrides a normalized project empty array,
survives in the returned scenario and fingerprint, and remains distinct from
the known-empty `[]` case. Whole-product save/reopen preservation is owned and
tested by Task 8; Task 6 requires no additional bridge.

### Coupled heave refinement

The independent continuous oracle gives final influx
`1.2756512554179793 m3` and draft `2.00637825627709 m` at 5 seconds. Production
`simulate_flooding` produced:

| dt (s) | accepted steps | influx (m3) | influx abs. error (m3) | draft (m) | draft abs. error (m) | volume residual (m3) | mass residual (t) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | 10 | 1.2807510745723398 | 0.00509981915436053 | 2.006403755372867 | 2.549909577709286e-05 | 0 | 4.440892098500626e-16 |
| 0.25 | 20 | 1.278195871139907 | 0.0025446157219277676 | 2.006390979355695 | 1.2723078604892635e-05 | -2.886579864025407e-15 | -3.3306690738754696e-15 |
| 0.125 | 40 | 1.27692224271631 | 0.0012709872983307502 | 2.0063846112135852 | 6.354936495256425e-06 | 4.440892098500626e-16 | 1.1102230246251565e-15 |

Both influx and draft-change errors decrease on every halving. At `dt=.125 s`,
both relative errors are about `0.0996%`, below the predeclared 1% thresholds.
Every accepted equilibrium is symmetric within `1e-6 deg`, its scaled
force/moment residuals are at most `1e-6`, and conservation remains far inside
the separate `1e-10` scaled bounds.

A selected runtime mutation replaced every current liquid-load list with an
empty list, modeling the concrete omission of floodwater added mass. At
`dt=.125 s` it held draft at `1.96 m` and predicted `1.2479218011525806 m3`
influx, a `2.1737488320279923%` error. It fails the predeclared coupled-heave
criterion while the production code passes. The mutation was applied only at
runtime by the ignored `task-6-prototype/production_evidence.py`; no production
source was changed for the mutation run.

### Verification evidence

Interpreter:

```text
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B
```

The executable reports Python `3.13.14`.

Focused Task 6 command, run from `tools/plimsoll/tests`:

```text
python.exe -B -m unittest -v test_flooding.py
```

Result: `Ran 10 tests in 10.248s ... OK`.

Scoped compatibility command, run from `tools/plimsoll/tests`:

```text
python.exe -B -m unittest -v test_damage_loop.py test_flood_combination.py test_calculation_integrity.py test_tank_geometry.py test_stability_loading.py
```

Result: `Ran 100 tests in 107.291s ... OK`. This includes relevant legacy
damage behavior plus the reviewed Task 4/5 contracts and is deliberately not
the shared full suite.

The production modules compile with `py_compile`, and the preset parses with
`json.tool`. An actual `queen-mary-single-proxy` initialization against
`queen_mary_1913.project.json` and `normal-engineering`, with duration changed
only to zero for a bounded replay check, returned `completed`,
`scheduled_completion`, one accepted state and a converged equilibrium with no
diagnostics.

### Production limits and integration state

- The time method remains bounded first-order explicit Euler. The declared
  refinement is validated; higher-order accuracy is not claimed.
- The model is one incompressible vented same-density liquid network with
  static connectivity and constant point-orifice coefficients. Compressed air,
  pressure networks, waves, sloshing, partial finite apertures, overflow,
  structural failure and changing damage geometry are outside this version and
  stop or remain explicitly unknown.
- Downflooding is detected at accepted states and is not interpolated as an
  exact crossing. Missing openings remain unknown. Completion, convergence,
  applicability, historical validation and safety are separate.
- Queen Mary cases are deterministic engineering-layout proxies, not surveyed
  subdivision, historical damage or empirical validation.
- No Task 4/5/7/8 interface concern was found. No shared module was edited.
- Per controller instruction, no shared full-suite run or commit was made while
  other task writers were active. Controller integration, shared regression
  and independent review are the remaining steps.

### Frozen production hashes

SHA-256 at freeze:

```text
f4257d967d7823fcb7ac0f79b62c3a18cfb5d7d030e6b9576b20e5955a064dbf  tools/plimsoll/_flooding_kernel.py
53af072c626b8c20f1f44e920a78a7c190e2968805981dfae204a5ae542be29c  tools/plimsoll/flooding.py
bb934e48694a43469584127e0cf6e06c3c01a599106df154671a6df71fe335fa  tools/plimsoll/tests/test_flooding.py
e09fe511fd1c70843b940df203dace59aa9184f5891db9f6dc013eca1d6f5688  tools/plimsoll/cases/projects/damage-presets.json
140e7d649f77bebf97b6cf960ee66558fab3d3b7823e302ef5ade1ac7fdb987d  docs/plimsoll-1.0/flooding-api.md
```

## Review fix round 1 — READY_FIX

Independent review round 0 reported four Important and two Minor findings.
All six are addressed in the Task 6 owned paths, with one newly authorized
canonical fixture:

1. The kernel classifies exact equal heads as `equal_heads` with zero flow
   before applying the finite-height aperture gate. A nonzero-head surface
   intersection remains the visible `partial_aperture_unsupported` model
   limit.
2. `generic_flooding_box.project.json` now supplies the exact rectangular
   project and `normal` loading condition named by all four generic presets.
   It explicitly declares `opening_definition: supplied` and `openings: []`.
   The table-driven public test resolves and initializes all six generic and
   Queen Mary presets through `simulate_flooding`.
3. Every public result envelope now includes
   `validity.numerical_convergence`. It is `null` before any equilibrium solve,
   `false` when the required initial or final attempted equilibrium cannot
   converge, and `true` when every accepted reported state has a converged
   equilibrium. This dimension is independent of requested-duration
   completion and model applicability, so a canceled, downflooding, capacity,
   or partial-aperture result can retain a converged last accepted state.
4. Scenario, sea, tank, connection and supplied-opening source fields now
   require a nonblank string or nonempty object. Public failures use blocking
   `flooding.source_invalid` diagnostics with the exact field path; the private
   kernel rejects the same unsupported values.
5. Preset testing now checks actual project and condition resolution and calls
   the public simulator for every shipped preset at duration zero.
6. A kernel invariant rejected after project normalization, loading
   resolution, fingerprinting and initial equilibrium retains the input and
   project fingerprints, resolved loading, normalized scenario, opening
   origin, and the established convergence state.

The Task 8B opening-knowledge transition required no Task 6 schema workaround.
The new fixture uses its explicit canonical marker; Task 8B owns the project
normalization and persistence implementation.

### Fix-round RED to GREEN evidence

- The equal-head finite-aperture regression first returned `model_limit` and
  `partial_aperture_unsupported`; after reordering the exact-zero decision, its
  focused test passed (`Ran 1 test ... OK`). The existing nonzero partial-
  aperture fixture was corrected to place unequal surfaces through the
  aperture, preserving its intended model-limit coverage.
- Seven source cases initially failed: private tank `null`, private connection
  `{}`, and public scenario `null`, sea `{}`, tank blank string, connection
  `null`, and opening `{}`. The two focused source tests then passed
  (`Ran 2 tests ... OK`).
- Convergence assertions initially raised missing-key errors and the injected
  late kernel failure returned a null fingerprint. The corrected four-test
  convergence/context run passed (`Ran 4 tests in 4.564s ... OK`).
- The all-preset replay test initially produced four subtest failures because
  `generic-box-fixture` was unresolved. After adding the canonical fixture,
  the same public replay test passed (`Ran 1 test in 3.937s ... OK`).

### Fix-round verification

Interpreter path:

```text
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B
```

The executable reports Python `3.13.14`; `PYTHONIOENCODING=utf-8` was set for
the test commands.

Focused Task 6 suite from repository root:

```text
python.exe -B -m unittest tools.plimsoll.tests.test_flooding
```

Result: `Ran 14 tests in 12.812s ... OK`.

Targeted adjacent regression command:

```text
python.exe -B -m unittest tools.plimsoll.tests.test_flooding tools.plimsoll.tests.test_damage_loop tools.plimsoll.tests.test_project_cases tools.plimsoll.tests.test_tank_geometry tools.plimsoll.tests.test_stability_loading
```

Result: `Ran 97 tests in 115.889s ... OK`. This covers the repaired public
surface, legacy damage behavior, shipped cases, Task 5 liquid geometry, and the
Task 4 loaded-equilibrium interface. It is deliberately not the shared full
suite.

An explicit canonical validation/loading probe returned:

```text
generic-box-fixture supplied 0 normal ['axis_complete', 'complete_cg', 'complete_mass', 'condition_id', 'coordinates', 'coverage', 'diagnostics', 'effective_items', 'groups', 'input_fingerprint', 'project_fingerprint', 'project_id', 'provenance', 'schema', 'uncertainty', 'units', 'values']
```

The zero is the number of project-validation errors. `git diff --check` passed
for all Task 6 owned paths. No full suite or commit was run in this fix round,
as instructed. The shared HEAD at freeze was
`68f27c415905933730f5bab7232250a199ac738c`; no Task 8B owned file was edited.

### Fix-round production hashes

```text
c267107b1a1a947f0ee07d067a647e7f6b49d985824ca7cfb89ea3793f9cf33d  tools/plimsoll/_flooding_kernel.py
982ac09c5186060c0c8f4acbe77af0b1e58d4dd28fa2376f8322c5befaf0d9dc  tools/plimsoll/flooding.py
d5390e0e7a4e9d8d52fa73d760e6978b755955c944384c3d81de87a121622eff  tools/plimsoll/tests/test_flooding.py
e09fe511fd1c70843b940df203dace59aa9184f5891db9f6dc013eca1d6f5688  tools/plimsoll/cases/projects/damage-presets.json
8a81771114e641e2667e35deabeb395edefe96a865b86570e12f64eb8435d6fe  tools/plimsoll/cases/projects/generic_flooding_box.project.json
2eb2c56bf41495ba8034c16627a98b25f8d83f0b8d0109038ae9485e9a5121eb  docs/plimsoll-1.0/flooding-api.md
```

The repaired production paths are frozen for controller integration and
independent review.
