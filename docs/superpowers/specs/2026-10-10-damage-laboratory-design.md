# Plimsoll damage laboratory — first complete aftermath loop

Date: 2026-10-10. Status: implementation brief for the new laboratory.

## Intent and decisions

The laboratory answers the user's question: which modules were damaged by this
hit, and what does that do to the ship and its crew? It must connect to Plimsoll's
actual calculation core. Crew are represented by compartment and duty group,
not individually. This is a new implementation; the legacy DamageRange remains
an untouched comparison artifact.

The user has requested development and proposed Three.js. Codex recommends
React + Three.js inside the current Plimsoll web workspace, with Python owning
the aftermath calculation. This replaces the earlier provisional Unity viewer
choice. Codex plans/reviews/accepts; OpenCode implements. Local acceptance only;
no staging, commits, pushes, public deployment or writes to the Unity project.

## First deliverable and explicit boundaries

Produce a working local experiment page, a pure Python experiment API and CLI,
and owner-scoped asynchronous web runs using the existing bounded worker.
A visitor selects a saved project/loading, declares an impact location and
gameplay severity/radius, and optionally declares a breach into a compartment.
They run one experiment, inspect modules/crew/ship consequences, scrub the
timeline and export the full input/result. The first version starts at the
already-known hit location: it is an aftermath laboratory, not a newly certified
penetration, fuse, fragmentation or explosive-pressure solver. Do not route
through the audited legacy DamageRange solver or legacy damage.py.

Single hit; fixed hydraulic topology after that hit. No automatic hull break-up,
fire propagation, medical injury prediction, real-time combat, pumping,
pathfinding, rescue, repeated hits, topology edits during a run or extrapolated
damaged-hull speed. All game damage/crew rules are versioned estimates. Valid
partial core results remain inspectable with their stop reasons.

## Ownership and calculation chain

1. Freeze the canonical project, selected condition, experiment and methods.
   Project mass/CG comes only from the existing selected loading ledger.
2. A declared localized gameplay impact generates deterministic module and crew
   events. Event sequence numbers order simultaneous events without inventing
   different physical times.
3. Explicit breach inputs generate `plimsoll-flooding-scenario-1` connections;
   call the current `analysis.compute_project` flooding stage and retain its
   complete native result. The wrapper does not implement another flood,
   equilibrium, water centroid, free-surface or GZ formula.
4. Accepted core timeline rows drive estimated module flooding availability and
   crew evacuation. Apply only actual accepted times; never invent the requested
   final state when the core stops early.
5. Result projection provides replay snapshots, explanatory events and game
   capability estimates alongside authoritative core quantities and validity.

Use metres/tonnes/seconds/kW/degrees at boundaries, x forward, y starboard,
z above keel. Render Three.js coordinates as (x,z,-y), preserving handedness.
Ship inclination/water visualisation must use the core geometry datum and
equilibrium plane, not a separate waterline assumption. Damage disables
equipment without deleting its mass. Added floodwater is represented once by
the flooding scenario, not by editing the project ledger as well.

## Input and output contract

Create `tools/plimsoll/damage_lab/` as an independent package. Public functions:

```
normalize_request(project, condition_id, experiment)
    -> (normalized_snapshot, normalized_request, request_fingerprint)
run_experiment(project, condition_id, experiment, *, cancel_check=None) -> dict
```

The builder chooses focused internal files. Normalize/compute must not mutate
the caller's project or experiment, perform caller-path I/O, or read arbitrary
project file references. Reject invalid/unknown input keys, bool/nonfinite
numeric values, duplicate IDs, missing references, invalid boxes, invalid crew
counts, insufficient metadata and excessive grids before starting the worker.
Errors carry structured code/path/message/blocking diagnostics.

Request schema: `plimsoll-damage-lab-request-1`. Experiment schema:
`plimsoll-damage-lab-experiment-1`. Result schema:
`plimsoll-damage-lab-result-1`. Each physical/game parameter carries nonempty
source and boolean estimate metadata at its containing record. Gameplay rules
have a distinct method version; modifying them changes request identity.

The experiment declares:

- `duration_s` in [0,60], positive `time_step_s`, at most 120 nominal flood steps;
- explicit rectangular compartments referencing the canonical project's
  compartment IDs, with known initial added water (default explicit zero in the
  supplied fixtures); hydraulic tank IDs are distinct from weight-item IDs;
- equipment modules: ID, label, role, compartment ID, axis-aligned box in core
  coordinates, selected-ledger weight links if known, required staff count,
  initial integrity and optional sourced nominal shaft-power contribution;
- crew groups: ID, label, compartment ID, duty/module links, station box,
  personnel count, source and estimate. Personnel can be null (unknown), which
  must not be rendered or calculated as zero;
- one impact: position, severity in [0,1], influence radius >=0, source/estimate;
- explicit breaches: ID, from/to compartment or sea, point, positive or zero
  area, Cd, source/estimate. Breach location and affected compartment must be
  resolved. A known absence is `breaches: []`;
- sourced rules: casualty fraction, fatal fraction, equipment flood-disable
  threshold and crew evacuation threshold, all in [0,1];
- a bounded GZ angle grid for final remaining GZ, with explicit core options.

Reuse canonical compartment geometry, including metadata, rather than silently
inventing subdivision for a ship with none. An explicit synthetic fixture may
provide its own canonical compartments. No personnel numbers are imported from
unrelated historical claims. UI defaults are clearly labelled game estimates.

Result retains normalized snapshot/request, all input/method fingerprints,
project/condition IDs, sources, diagnostics, validity, complete native core
analysis, events, replay snapshots, final modules/crew/capabilities, and elapsed
wall-clock calculation seconds separately from simulated duration seconds.
Use completed/partial/canceled status compatible with the calculation queue;
unknown quantities remain null. No success or safety assertion from positive GM.

### Builder-check decisions (Codex implementation choices)

The first page supports layout authoring through full experiment JSON import/edit,
with ordinary controls for the selected module/group's personnel and impact.
An explicit defaults helper may create clearly labelled estimated equipment and
station placeholders inside already supplied canonical compartments. It must not
invent compartments, personnel or nominal power: personnel/power start unknown.
An explicit separate synthetic demo supplies a complete usable known-count layout.
Users can add/edit declared modules through the JSON editor; bad or unsupported
saved ship layouts produce a readable unavailable state.

One crew group may staff only one module in this first version; enforce exactly
one duty-module reference (or zero for an explicitly non-operating group). Multiple
distinct groups may staff the same module. Each group's personnel belong to it
once. Modules and station boxes must be inside their declared compartment.

A sea breach point must lie on the boundary of its target compartment AABB.
This is an explicitly declared compartment-to-sea proxy; it does not certify
that the face is surveyed hull plating. An internal breach must lie on a shared
face of its two compartment AABBs. First version excludes arbitrary remote pipe
connections. Use explicit 1e-6 m geometric comparison tolerance. Reject an
unrelated point/endpoints rather than moving the point or fabricating a wall.

Effective availability uses the versioned product rule:
`mechanical_integrity * flooding_availability * staffing_availability`.
A known zero factor makes the result known zero; otherwise any unknown factor
makes it null. A total shaft-power estimate is null if any contributing nominal
power or nonzero availability is unknown; retain a labelled known subtotal.
These are gameplay choices, not fitted empirical equipment/crew data.

## Localized gameplay rule

This first iteration deliberately uses a transparent game rule, not simulated
medical or explosive physics. Distance is from impact point to each declared
module/station AABB. For positive radius, exposure is
`severity * max(0, 1-distance/radius)`. At radius zero, only containing boxes
receive the severity. Module integrity becomes
`max(0, initial_integrity-exposure)`; each module is processed once.

For a known crew count N, affected personnel are
`floor(N * exposure * casualty_fraction)`; dead are
`floor(affected * fatal_fraction)`; incapacitated are `affected-dead`.
The remaining personnel are available. Null N makes all count-derived results
unknown, including staffing-dependent capability. This sampling policy is
deterministic and its source/estimate is visible, not historical validation.

At accepted flooding snapshots, compare actual volume with permeability-scaled
capacity. When the sourced module threshold is reached, operational flooding
availability becomes zero without erasing mechanical integrity. When the sourced
crew evacuation threshold is reached, available personnel move to an abstract
assembly location and become evacuated. Incapacitated/dead do not silently
evacuate. No automatic return/recovery during this single experiment.
Available + incapacitated + dead + evacuated equals the group's initial N.

Module staffing availability is min(1, available assigned personnel / required
staff), or one for explicitly unstaffed equipment, or null if required staffing
is unknown. Effective module availability combines mechanical, flood and staff
availability. Show each cause separately. A known shaft-power contribution is
scaled by availability; absent/unknown performance inputs stay unavailable.
Do not derive arbitrary maximum-speed factors from damaged-module counts.
Dependencies beyond explicitly supplied module links remain future work.

## Core bridge and stop semantics

The native core's new flooding API is the only hydraulic path. It starts with
the supplied added-water state at t=0, and the impact/activation events are also
t=0. It owns all later accepted times and initial equilibrium. Preserve project
opening knowledge: unknown stays unknown; declared absence stays an empty list.
Do not convert downflooding openings into hydraulic connections.
Retain force/moment residuals, water conservation errors, model limits, numerical
convergence and remaining GZ. Display model limits as model limits, never sink,
survive or victory conclusions. No scenario spill/pressure invention at capacity.

## Web and asynchronous work

Add workspace hash route `#/damage-lab/<project-id>` and a discoverable project
entry. Reuse authentication, CSRF, allowed origins, immutable revisions and the
existing CalculationRun owner/lease/cancellation/result-size protections.
Add dedicated enqueue/read/export routes with the damage-lab request schema as
the kind discriminator, without a database schema migration. Existing analysis
routes, run lists, report views and exports must keep their existing behaviour;
lab requests/results must not accidentally be interpreted as analysis reports.
Dispatch the pure package from the existing bounded worker. Result identity must
match the enqueued normalized identity, including after method upgrades.

The page shows real read/queued/running/partial/failed/canceled states and never
retains the previous successful report under a changed experiment. The local
draft has its own identity; editing retires playback and makes the old result
visibly historical or clears it. Poll only the selected run, cancel on user
request, and ignore late replies after input/project/unmount changes.

## Display direction

Apply the existing Swiss visual language: Space Grotesk titles, Inter text,
paper background, left-aligned grid, blue focus/selection, restrained red damage
accent, visible fine rules. Three.js scene is the dominant inspection surface,
not a tiny preview. Equipment boxes and compartment boundaries are distinct.
Use uncluttered hull/section outlines from the canonical geometry; analytical
fixtures and estimated Queen Mary layouts are labelled.

Orbit/zoom, compartment/module selection, reset view, water visibility and a
section/transparent inspection view. Selection is mirrored in accessible HTML
lists and results. A WebGL failure leaves usable HTML results and an explicit
rendering error. Initial pause, play/pause, speed and event-by-event stepping;
event index rather than time-only stepping handles equal-time events. Damage
colours and counts derive from the selected snapshot, never final-result fades.
Pause/reduced-motion produces a stable scene. Keep diagrams and text legible.

Use Three.js directly with React-owned HTML controls; no additional scene
framework. Lazy-load the scene/page and dispose renderer, controls, geometry,
materials, observers and animation frames on unmount. No new audio this round.
No external 3D asset, medical model or CDN dependency is necessary.

## Acceptance

Batch checks by core/bridge and web/scene clusters. Tests must use independent
expected outcomes and at least one real core flooding computation, not only
mocks. Cover zero impact, localized damage, null personnel, personnel
conservation, impact severity changes, no-breach dry state, submerged breach,
accepted-time ordering, simultaneous stepping, stale draft/result protection,
native early-stop propagation, source/ID/box/unit validation and input immutability.
CLI JSON round trip must contain sufficient inputs to rerun the experiment.
Backend owner isolation, revision conflict, queue dispatch/identity/cancellation
and analysis regression tests pass. Frontend tests/build pass. Inspect actual
local browser at desktop viewport, exercise a complete experiment, selection,
playback and export; retain screenshots and a concrete acceptance report.

Compare the protected baseline hashes before delivery. Existing dirty verifier
work, legacy Unity files and calculation kernels remain preserved. Acceptance
does not claim historical injury calibration, real-time game performance or
public deployment.
