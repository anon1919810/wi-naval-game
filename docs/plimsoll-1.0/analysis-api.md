# Selected-loading analysis API

Integration contract for the implemented coordinator, serializers and CLI.
Acceptance and remaining method limits are recorded separately.

`analysis.compute_project(project, condition_id, options=None, *, cancel_check=None)`
returns one JSON-compatible `plimsoll-analysis-1` result. It performs no caller
or project path I/O or discovery. Taylor requests may read the fixed bundled
`cases/taylor_gertler_cr_table.json` resource and must verify its raw-byte SHA-256
`e9dc5141235ad9a0ddc1c1de70ab33d28f7aac86f75953663c969ad3fd124d93`.
Qualified package use resolves that declared resource through `importlib.resources`;
direct-module use resolves the fixed path relative to its own module. Missing or
mismatched resources yield diagnostics, never a substituted table.
The optional runtime callback is excluded from serialized request identity.
`AnalysisInputError(ValueError)` exposes canonical structured `diagnostics` for
invalid project/request input. Missing calculable data returns stage envelopes.

## Request

`options` is an object with only these keys:

- `stages`: unique stage-name array. Omission requests loading, systems, l0,
  geometry, equilibrium, hydrostatics, deck and propulsion. Dependencies may run
  with `requested=false`; every stage is present in the result.
- `equilibrium`: validated solver options. Effective defaults are echoed.
  Optional `target_trim_deg` requests a **separate** longitudinal-moment study
  at that trim; it does not move ballast or replace the freely solved attitude.
- `gz_angles_deg`: 1..201 finite strictly increasing values, when GZ is requested.
- `hydrostatic_waterlines_above_keel_m`, `bonjean_waterlines_above_keel_m`:
  explicit 1..201 strictly increasing waterline grids for the respective stages.
- `resistance`: object with exactly one of `scenario_id` or `scenario`, and
  required positive increasing `speeds_kn` (1..201). Optional `qpc_override` is
  `{value,source,estimate}` with positive value, meaningful source and boolean
  estimate. Otherwise use the scenario QPC/sensitivity. This is the exact sweep
  override path; no project mutation is needed. Speed × QPC count is <=1000.
  `mode="predict_power"` is the default. `mode="fixed_power"` requires
  `fixed_shaft_power_kw`, a sourced single `qpc_override`, and at least two
  speeds bracketing the requested power. It never extrapolates beyond the
  submitted speed grid, and preserves nonprimary applicability on trim proxies.
- `endurance_scenario_id`: existing project scenario ID for endurance.
- `flooding`: `{scenario, options}` using the reviewed native scenario and
  bounded serializable native options. Runtime cancel_check belongs to the
  compute keyword, never this JSON object.

Unknown keys, bool/nonfinite numbers and conflicting density/datum options are
errors. Expensive stage requests require their explicit grids/scenarios; grids
do not silently request an otherwise unrequested stage. CLI sweep points replace
`options.resistance.speeds_kn` with a one-element speed array and/or
`options.resistance.qpc_override` with an explicitly sourced estimate fact.

## Exact result layout

All results contain these top-level keys:

```text
schema = "plimsoll-analysis-1"
status = completed | partial | canceled
project_id, condition_id
project_fingerprint, input_fingerprint, request_fingerprint
request = {schema:"plimsoll-analysis-request-1", condition_id, options}
input_snapshot = normalized canonical project
units, coordinates, geometry_datum
method_versions, sources, diagnostics, validity, stages
```

`input_fingerprint` is exactly the selected loading fingerprint. Request identity
binds the normalized snapshot, condition, effective options and method versions.
The 2026-10-09 audit repairs use coordinator `selected-loading-analysis-2`.
This changes request identities so cached pre-repair results cannot be reused
as repaired results; stored input snapshots and historical results are not
rewritten. Numerical method names, Taylor source bytes and the ITTC equation
remain unchanged.
Every stage is located **only under `result.stages`**, with these stable keys:

```text
loading, systems, l0, geometry, equilibrium, hydrostatics, gz, deck,
hydrostatic_curve, bonjean, resistance, propulsion, endurance, historical, flooding
```

Every stage has the same envelope:

```json
{
  "status": "not_requested",
  "requested": false,
  "dependencies": [],
  "reason": null,
  "validity": {"complete": false, "converged": null,
               "model_applicable": null, "historical_validated": null},
  "method_versions": {}, "assumptions": [], "diagnostics": [], "data": null
}
```

Stage statuses are completed, not_requested, unavailable, failed, canceled or
model_limit. `data` retains native kernel results; adapter-owned supplemental
fields are explicitly named. Top-level status is canceled if a requested stage
cancels, otherwise completed only if all requested stages have completed and
validity.complete=true, otherwise partial. Completion never certifies empirical
applicability or historical validity. Top-level validity has the same four axes.
Diagnostic records retain code/severity/path/message/blocking, add stage and
source_path, and are never coalesced by message. Stage diagnostics and the
top-level flattened list carry the same records.

The systems stage may contain selected-ledger `page_rows` for guns, weapons and
armour, including a separately declared minimum-belt engineering estimate.
It also contains `deck_coverage` with `coverage_pct = 100 × covered plan area /
reference plan area` only when both sourced areas are known. Missing data yields
`status="unavailable"` and `coverage_pct=null`; this study does not alter loading.
For a weapons battery with a `mounts` page row, an optional
`rotating_armour_component` reports sourced armour mass within one selected
mounting item and the non-armour remainder. Missing or oversized subcomponent
mass is unavailable; no subcomponent mass is added to the ship or armour ledger.
The deck stage reports endpoint normal freeboards and reference-length shares.
The propulsion stage contains `engine_page` with the explicitly classified
selected variable load. Hydrostatics exposes a small-angle roll study only when
selected GM and a sourced gyration coefficient are available. Missing inputs
produce unavailable/null study results, not substituted design facts.

Serializers serialize this already-computed result without calculator calls.
JSON preserves nulls. CSV generically flattens every stage/data path and must
carry stage status, units, identities, provenance and all diagnostic rows; no
fixed numeric row assumptions are needed.
Exit-success requires top-level completed; partial/canceled are unsuccessful
calculation outcomes even when useful loading outputs exist.

The exporter/CLI fixture can use a loading-only request with all fifteen stage
envelopes present: loading requested/completed and all others not_requested.
Actual native loading data is supplied by the public coordinator, not fabricated
by a formatter. Input validation failures use the exception diagnostics, not a
synthetic completed analysis result.

## Explicit geometry and proposal operations

`materialize_reference_project(project, parameters, *, keel_offset_m, source,
estimate, station_count=41, section_points=32)` is an explicit in-memory action
returning a new canonical project using the reviewed reference-hull helper.
Source-content import remains `geometry_import.import_geometry_content`.
Compute never reads an offsets_reference or implicitly generates geometry.

`apply_mass_proposal(project, condition_id, proposal, *, current_request,
target="selected_condition")` recomputes normalized request identity and the
actual systems proposal. `current_request` is the full request object shown
above, containing current options. Echoed client hashes alone are insufficient.
It returns `{project, change}`; the project is a new normalized canonical input,
and change contains old/new selected mass, condition/item/model identity,
provenance and original fingerprints. Other conditions and base ledger remain
unchanged. Compute's systems data exposes bound proposals for this action.
