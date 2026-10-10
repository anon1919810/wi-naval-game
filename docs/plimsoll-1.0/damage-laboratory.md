# Damage laboratory

The laboratory explains one **known hit**: which declared equipment was affected,
how its compartment duty groups were affected, and what accepted flooding states
do to the ship. React owns configuration and replay; Three.js is an inspection
surface; Python owns results. Inspection meshes never feed back into the solver.

## Run locally

The existing web API and bounded calculation worker must both be running. Open
`#/damage-lab/demo`, or the **Damage laboratory** entry in the project library.
Creating the synthetic vessel explicitly imports a new owned project. An existing
saved project can enter through the workbench's **More** menu. Save edits first.

The default synthetic vessel is 36 m long, 8 m wide and 5.5 m deep, with 37
canonical polygon sections defining its tapered bow, transom, keel, bilges and
deck. Its three declared gameplay compartments contain two separately owned
10 t machinery items and duty groups of 10 / 10 / 4 people. Total dry mass is
340 t. All geometry and loading values are explicit synthetic estimates; this
is not a historical vessel. Other projects use their own
canonical compartments and offsets; missing layouts remain unavailable. Default
equipment/stations are labelled estimated placeholders, with unknown crew counts
and power, until the user supplies them.

Rectangular compartments require finite positive dimensions, explicit position,
permeability within [0,1], and source/estimate metadata. An incomplete imported
layout returns an unavailable-layout diagnostic rather than a server error.
Omitted nullable `personnel`, `module_id` and `nominal_shaft_power_kw` fields
normalize to null; missing knowledge is not converted into zero or invented
personnel.

The page offers position, normalized severity, influence radius, duration,
nominal timestep and explicit sea-link controls. It also imports, edits and
downloads the full experiment JSON, using server admission before applying it.
The quick breach checkbox replaces the breach list; the full JSON supports
multiple sea links and actual opposing shared-face bulkhead links. A compartment
boundary sea link is a gameplay proxy, not a surveyed hull-skin intersection.

## CLI and reports for AI

From the repository root, in PowerShell:

```powershell
python -m tools.plimsoll.damage_lab --project tools/plimsoll/cases/damage_lab/synthetic-vessel.project.json --condition normal --experiment tools/plimsoll/cases/damage_lab/synthetic-vessel.experiment.json --output lab-report.json --csv lab-report.csv
```

The original `synthetic-rig.project.json` remains an analytic rectangular fixture
for numerical checks, with its unchanged `intact.experiment.json`,
`machinery-hit.experiment.json` and `submerged-breach.experiment.json` scenarios.
Python imports can instead call:

```python
from tools.plimsoll.damage_lab import normalize_request, run_experiment
snapshot, request, fingerprint = normalize_request(project, condition_id, experiment)
result = run_experiment(snapshot, condition_id, request['experiment'])
```

Every result contains `input_snapshot`, `request`, method versions, fingerprints,
native `core_analysis`, indexed `events`, immutable `snapshots`, and `final_state`.
An AI should inspect the **status, validity, diagnostics and stop reason first**,
then distinguish game estimates from native calculated values. To rerun, use the
frozen `input_snapshot` and `request.experiment`; do not substitute the current
project draft. CLI JSON rejects duplicate keys and nonfinite numbers, and output
paths cannot alias either input. Exit 0 means completed; 2 means partial; 3 means
canceled; 1 means invalid input or I/O failure. `elapsed_wall_seconds` is runtime,
not simulated time. Requested duration need not equal the accepted endpoint.

CSV is a complete flat JSON-Pointer representation: each row gives the frozen
request identity, terminal status, accepted endpoint, `path`, and a JSON value in
`value_json`. Arrays use integer path segments; escaped object keys use `~0` for
`~` and `~1` for `/`; nulls and empty containers are retained. This avoids a huge
single report cell. Prefer JSON for structured automated interpretation.

## Meaning and limits

- Equipment exposure is `severity * max(0, 1 - distance_to_AABB / radius)`;
  radius zero affects only containing boxes. Integrity loses this exposure;
  damaged equipment stays in the weight ledger.
- For known N, affected people are `floor(N * exposure * casualty_fraction)`;
  dead are `floor(affected * fatal_fraction)`; other affected people are
  incapacitated. Available + incapacitated + dead + evacuated always equals N.
  Unknown N stays unknown. These deterministic rules are **game estimates**,
  not blast-pressure, medical or historical casualty predictions.
- One duty group may staff at most one module. Effective availability is the
  product of mechanical, flooding and staffing factors. A known zero dominates
  unknown factors; otherwise an unknown factor propagates. Power remains unknown
  if a contributing nominal value or nonzero availability is unknown; a labelled
  known subtotal is retained. No maximum-speed inference is made.
- Flood thresholds operate on the real accepted water volume divided by
  permeability-scaled capacity. Available staff evacuate to an abstract assembly
  point; incapacitated/dead personnel remain associated with the original room.
  Evacuation and flood disable are irreversible in this single experiment.
- The existing `analysis.compute_project` flooding stage supplies connected
  vented orifice flow, coupled heave/heel/trim, water-conservation residuals and
  final remaining GZ. Added water belongs exclusively to the lab tanks. **The
  user's base loading must exclude that same added water.** Explicit lab-water
  ownership tokens in the base ledger are rejected; semantic ownership under
  unrelated names cannot be inferred. Existing opening knowledge is preserved.
- The model has fixed rectangular compartments, one incompressible liquid,
  static sea, a maximum 60 s duration and 120 nominal steps (240 accepted-step
  work limit), with the existing worker's timeout/cancellation/result-size bounds.
  Solver/model stops retain the last accepted state. Completed does not mean
  historically validated, safe, survived or sank.
- No new penetration, fuse, fragmentation, blast, fire, structural breakup,
  medical, damage-control pathfinding or repeated-hit solver is supplied. No
  real-time combat performance claim is made.

Replay uses event indices, including distinct t=0 events. It steps accepted
states without inventing intermediate physics. The final GZ panel is explicitly
labelled as a final-state report. Draft/condition/revision changes hide a mismatched
result; the stored run remains available for restoration or export. Owner checks,
CSRF, origin policy, immutable revisions, per-account active limits, lease/CAS
identity and bounded-process cleanup are shared with the existing queue. Analysis
URLs cannot read a lab run as an analysis report.

The scene uses `(x,y,z) → (x,z,-y)` and subtracts the raw hull geometry's keel
datum only for raw offsets. The neutral opaque hull preserves every canonical
section corner, interpolates only along its original edges, and lofts between
stations. Deck anchors stay aligned as beam changes. This sampled visual loft
does not replace the core's station quadrature or claim identical enclosed volume
between samples. Local cutaway removes the starboard shell and half deck while
retaining the port exterior; the open center plane has no opaque fill. Cuts clip
the original triangles, so nonplanar panels retain the same physical surface.
Hull triangles batch into two material groups rather than one draw per face. Interior
rooms and native water volumes remain whole. Retained hull faces occlude module
picking, and orbit drags do not select modules. Camera framing uses actual bounds
and survives replay and cutaway toggles. Extremely complex inputs exceeding
250,000 aligned station points, and degenerate point-only end sections, use the
explicit unavailable-view fallback. Their text reports remain available.
Ship rotation uses the core's orthonormal slope axes;
water meshes clip to the native liquid plane. Orbit/zoom, pick, hull section,
water visibility and reset are visual inspection controls. HTML selection and
reports remain usable without WebGL. The viewer is lazy loaded, respects reduced
motion for orbit damping, and disposes its graphics resources on exit.

Full accepted tanks render the whole compartment even though the native solver
correctly supplies no internal free-surface plane. Partial tanks with unavailable
planes are not given an invented fill. Negative GZ angles remain inside the chart,
and missing samples break the plotted curve. Late history/configuration-file reads
cannot replace a newer edit.
