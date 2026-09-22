# Task 6 independent review — round 0

Review target: `df9e835..93218ff03bada4754b98435be94c3b559dfb87ab`

Scope: the five Task 6 paths in
`task-6-review-df9e835-93218ff.diff`. Task 8A changes, the later unified
coordinator, exports, CLI, UI, deployment, and packaging are outside this
review. The current core-only scope does not relax the flooding equations,
tolerances, provenance, state, or replay contracts.

## Verdicts

**Specification verdict: NEEDS CHANGES.** The implementation correctly follows
the added-mass convention, passes current liquid geometry into every accepted
equilibrium, uses the common unit normal and geometry datum, conserves each
internal transfer as one signed quantity, retains only accepted states, and
keeps optional remaining GZ on the current liquid loads. The producer's
analytic/refinement and shared-regression evidence is consistent with those
paths. Four released requirements remain unmet: equal-head zero flow is
overridden by a finite-aperture model limit, four shipped generic presets name
no shipped project, public validity omits numerical convergence, and null/empty
source metadata is accepted without an unknown-source diagnostic.

**Code-quality verdict: NEEDS CHANGES.** The split between the conservative
network kernel and the coupled driver is coherent, solver reuse is disciplined,
and the accepted/failed timeline ownership is clear. The state machine and
ledger code are readable. The findings below affect public behavior and replay,
not style alone. I found no Critical issue.

## Findings

### Important

1. **Equal heads are reported as an unsupported partial aperture instead of
   exact zero flow.**

   In `tools/plimsoll/_flooding_kernel.py:234-253`, the finite-aperture
   intersection check runs before the head difference is evaluated at lines
   253-260. An open, nonzero aperture intersected by two identical liquid
   surfaces therefore returns `model_limit`,
   `partial_aperture_unsupported`, and `flow_m3_s=null` even though the declared
   pressure difference is exactly zero.

   The binding design says both dry/equal-head sides have zero flow, and the
   integration decisions say a zero-flow edge remains zero-flow. No partial-flow
   model is needed to establish zero differential pressure. This can stop an
   otherwise equilibrated connected network instead of completing with
   `equal_heads_or_no_open_flow`. Evaluate the exact zero-head case before the
   partial-aperture applicability gate, while retaining the gate for a nonzero
   requested rate.

2. **The four generic shipped presets cannot be resolved to any shipped
   canonical project.**

   `tools/plimsoll/cases/projects/damage-presets.json:7,29,52,74` names
   `project_id="generic-box-fixture"` and `condition_id="normal"`. No canonical
   project with that ID exists under `tools/plimsoll/cases/projects`; the shipped
   generic IDs are `analytic-box-reference` and `generic-steamer-reference`.
   `tools/plimsoll/tests/test_flooding.py:457-483` only checks preset categories
   and replays a Queen Mary preset. Its generic numerical fixture is an in-memory
   `coupled-flooding-box` (`test_flooding.py:40-77`), so it does not establish a
   public preset replay.

   Consumers cannot load or deterministically run the advertised generic
   single, two-connected, asymmetric, or closed-valve cases. Point them at a
   compatible shipped project/condition or ship the exact referenced canonical
   fixture, then replay every preset through the same public resolution path.

3. **Public validity never reports mathematical/numerical convergence as a
   separate dimension.**

   The invalid envelope at `tools/plimsoll/flooding.py:459-471`, initial
   equilibrium-failure envelope at `tools/plimsoll/flooding.py:546-560`, and
   final envelope at `tools/plimsoll/flooding.py:707-714` contain `complete`,
   `model_applicable`, `historical_validated`, and `safe`, but omit
   `numerical_convergence`.

   The global contract explicitly separates completeness, mathematical
   convergence, applicability, and historical validation. Callers currently
   have to infer convergence from timeline internals and status, which is
   ambiguous for cancellation, capacity/model limits after converged accepted
   states, and equilibrium failure. Add the explicit field with documented
   semantics; do not equate requested-duration completeness with numerical
   convergence.

4. **Source metadata can be null or empty without an unknown-provenance
   diagnostic.**

   `tools/plimsoll/flooding.py:65-69` checks only that `source` is present.
   Scenario, sea, tanks, connections, and openings all use this helper at lines
   177, 199, 211, 238, and 290. Values such as `source=null`, `{}`, or an empty
   string are accepted and copied into an otherwise applicable result. The
   private kernel has the same presence-only behavior at
   `tools/plimsoll/_flooding_kernel.py:31-34`.

   The binding contract allows unknown as null only with a diagnostic and
   requires scenario geometry/orifice provenance to remain explicit. Current
   output silently presents unprovenanced geometry and Cd as a normal scenario.
   Either require a nonempty supported source value for this scenario schema or
   preserve null as unknown while adding a structured, non-silent provenance
   diagnostic and appropriate applicability/completeness semantics.

### Minor

1. **The public preset test checks inventory labels rather than generic preset
   usability.**

   `tools/plimsoll/tests/test_flooding.py:457-470` verifies categories, schema,
   and metadata, then lines 472-483 replay only Queen Mary. A project-ID typo or
   incompatible generic loading condition therefore passes. Add a table-driven
   load/condition/simulate check for every shipped preset; a duration-zero replay
   is sufficient to validate wiring without turning this into a long numerical
   regression.

2. **The initial kernel-validation failure discards an already established
   input fingerprint and scenario context.**

   After normalization, loading resolution, and fingerprinting at
   `tools/plimsoll/flooding.py:500-520`, a kernel error at lines 563-569 returns
   `_invalid_result`, whose fields at lines 459-470 set `input_fingerprint=null`
   and omit project/loading/scenario. Public validation should catch all scenario
   errors before equilibrium; if an invariant still fails at this boundary,
   retaining the computed identity and normalized context would make the failure
   reproducible. This does not affect the accepted numerical path.

## Focused probe

I did not rerun the producer's 10 focused tests, 100 compatibility tests, or the
controller's 545-test shared regression. Code reading exposed finding 1, so I
ran one direct probe with the specified interpreter:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='tools/plimsoll'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -c "import _flooding_kernel as k; tank=lambda i:{'id':i,'length_m':10.0,'beam_m':1.0,'height_m':5.0,'x_m':0.0,'y_m':0.0,'keel_to_bottom_m':0.0,'permeability':1.0,'free_surface':True,'fluid_density_t_m3':1.025,'source':{'kind':'probe'},'estimate':False}; edge={'id':'equal-partial','from_node_id':'a','to_node_id':'b','centre_m':[0.0,0.0,1.0],'area_m2':0.1,'discharge_coefficient':0.6,'fluid_density_t_m3':1.025,'open':True,'aperture_height_m':0.5,'source':{'kind':'probe'},'estimate':False}; r=k.evaluate_flows([tank('a'),tank('b')],{'a':10.0,'b':10.0},[edge],attitude={'heel_deg':0.0,'trim_deg':0.0,'geometry_keel_offset_m':0.0}); print(r['status'],r['edges'][0]['status'],r['edges'][0]['flow_m3_s'])"
```

Observed exit 0:

```text
model_limit partial_aperture_unsupported None
```

The probe was read-only with respect to production, tests, index, checkout, and
branch state.

## Confirmed behavior and quality notes

- `_attitude_and_sea` converts the geometry-datum intercept to unit-normal sea
  offset, while tank/aperture ordinates receive the geometry keel translation.
  The kernel uses the same normal for sea, tank planes, and connection centres.
- Every candidate volume set is passed as current Task 5 liquid loads to the
  Task 4 equilibrium solver. The accepted row takes moving centroids from that
  equilibrium. The implementation does not call the legacy upright damage path,
  subtract lost buoyancy, or add a second FSC correction.
- Transfers are signed once per edge and applied with equal/opposite internal
  deltas. Sea exchange alone changes onboard volume/mass, and conservation is
  reported independently of equilibrium residual and ODE truncation error.
- Aggregate outgoing/incoming rates bound the timestep before applying a
  candidate. Capacity, dry source, reversal, partial aperture, equilibrium
  failure, cancellation, step limit, downflooding, and scheduled completion have
  distinct stop paths.
- Timeline row zero is the accepted initial equilibrium. Failed candidate
  volumes/equilibrium stay in `failed_attempt`; they are not appended. The final
  accepted state is retained on later failure or cancellation.
- Remaining GZ receives the same density, equilibrium options, openings, and
  current liquid loads. Its safety and historical validation remain unset.
- The Queen Mary presets are plainly labeled engineering proxies. I found no
  ship-specific coefficient hidden in either numerical module.

## Unverified later integration boundaries

- The unified project coordinator has not yet routed flooding through the common
  calculation snapshot/result fingerprint. That later phase must preserve all
  Task 6 diagnostics and state distinctions; its absence is not a defect in
  these five paths.
- Canonical persistence currently normalizes absent openings to `[]`, so Task 6
  cannot recover unknown-versus-known-empty after save/reload from the normalized
  project alone. The controller assigned a persistent validated
  knowledge/origin marker and end-to-end null/empty migration tests to Task 8B.
  The scenario-level `openings=null` bridge works, but it is not a substitute for
  that project persistence fix.
- Core CLI/batch/sweep and JSON/CSV export must later resolve the repaired preset
  IDs, retain null/zero and diagnostics, and expose failed/canceled timelines.
  UI, deployment, and standalone packaging are deferred by
  `current-core-scope.md` and were not assessed.
- No historical flooding/subdivision validation is established. The Queen Mary
  tank and aperture layouts remain explicit estimated proxies, and the analytic
  anchors validate only the declared vented point-orifice model.
- The controller's shared `545 passed` in `171.404 s` and unchanged 93-path
  hashes are accepted integration evidence from `task-6-8a-regression.json/log`;
  they were not rerun or recharacterized as independent reviewer execution.

