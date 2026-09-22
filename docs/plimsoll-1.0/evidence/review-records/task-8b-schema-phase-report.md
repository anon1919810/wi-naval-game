# Task 8 report — persistence phase only

Status: **PERSISTENCE_READY — frozen for controller review.**

This completes only the expressly released independent persistence phase. Task 8
as a whole remains incomplete. Numerical integration was not released or started.
No commits, pushes, full-suite run, package initializer edits, schema edits,
calculator stubs or changes to other owners' production files were made.

## Implemented

- `project_store.load(path) -> dict`: UTF-8 JSON read, canonical normalization,
  or explicit `plimsoll-ship-1` migration through reviewed `project_io`.
- `project_store.save(path, project) -> None`: normalize a copy, validate,
  serialize with `allow_nan=False`, encode UTF-8 before creating a temporary
  file, write/flush/fsync a unique same-directory owned file, close it, then
  `os.replace`. Finally clean only that owned temporary path.
- Preserve literal typed geometry references, unknown/zero distinctions,
  source/estimate status, legacy inputs, uncertainty, loading overrides and
  canonical input identity. Do not discover sibling weights or regenerate hulls.
- `resolve_geometry_reference(project_path, project) -> Path`: explicitly
  resolve declared offsets references against the project file directory without
  reading their content or inserting machine paths into canonical input.
- Ordinary relative import for package use, explicit direct-module import
  branch otherwise; no `sys.modules` rewriting or path injection in this module.
- Document contracts, portability boundary, error propagation and atomic-save
  limitations in `docs/plimsoll-1.0/project-store.md`.

Controller confirmed the reference and legacy-weight interface before its
implementation: preserve references during load/save, use the explicit resolver,
and require explicit `migrate_legacy(ship, weights)` for additional weights.

## TDD and verification evidence

All commands ran from:
`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`.

Interpreter command prefix (PowerShell):

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B
```

Actual interpreter verified with `-c 'import sys; print(sys.version)'`:
`3.13.14 (main, Jun 11 2026, 04:04:46) [MSC v.1944 64 bit (AMD64)]`.

### RED

Before `project_store.py` existed, wrote the initial persistence tests and ran:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_store.py -v
```

Exit 1: `ModuleNotFoundError: No module named 'project_store'`;
`FAILED (errors=1)`. This was a missing-production-module collection failure,
not a claimed assertion-level failure. After controller approved reference
semantics, added reference tests and reran the same command before implementing;
the absent module produced the same expected failure.

### GREEN

After implementing persistence, the same targeted command exited 0:
`Ran 16 tests in 0.523s`, `OK`.

Added a regression test for an explicitly migrated legacy weights payload
(existing migration + save/load behavior; no additional production behavior).
Then ran the related project tests:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p 'test_project*.py' -v
```

Exit 0: `Ran 46 tests in 2.812s`, `OK`. This pattern included 17 persistence
tests, 21 existing project-I/O/unit tests, and 8 existing project-case tests.
It did not run the full suite. No test failures or warnings were reported.

Persistence tests exercise real files and independent literal expectations:
Chinese UTF-8 filenames/content; canonical fingerprint stability; source and
estimate identity; legacy reopening; explicit legacy weights; reference base and
save-as behavior; absolute references; no sibling discovery; all validation
diagnostics; boolean and nonfinite rejection; UTF-8 encoding failure; fsync and
replace failures; owned-temp-only cleanup; malformed edits after successful
loads; missing files; unsupported schema; direct/package imports in fresh
subprocesses from a different current directory. Failure injection is confined
to OS durability/replacement boundaries; normalization, serialization and actual
temporary-file content remain real.

### Focused mutation checks

The scratch helper applies mutations only to in-memory module instances:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B .superpowers/sdd/2026-09-22-plimsoll-1.0/task-8-persistence-mutations.py
```

Exit 0:

```text
omit_atomic_replace: DETECTED
omit_owned_cleanup: DETECTED
resolve_against_cwd: DETECTED
unknown_to_zero: DETECTED
4/4 focused mutations detected; production files untouched
```

### Diff checks and self-review

`git diff --check` exited 0. Because the three new files are untracked, also
checked each using `git diff --no-index --check -- /dev/null <file>` and confirmed
no output (no whitespace errors). The first wrapper mistakenly treated the
normal no-index difference exit 1 as a check failure; the corrected wrapper
accepts 0/1 and rejects any emitted check text or status greater than 1:

```powershell
$taskFiles = @('tools/plimsoll/project_store.py', 'tools/plimsoll/tests/test_project_store.py', 'docs/plimsoll-1.0/project-store.md')
foreach ($taskFile in $taskFiles) {
    $taskCheck = git diff --no-index --check -- /dev/null $taskFile 2>&1
    if ($taskCheck) { $taskCheck; exit 1 }
    if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
    Write-Output ('clean: ' + $taskFile)
}
Get-FileHash -Algorithm SHA256 -LiteralPath $taskFiles | Format-List Path,Hash
```

All three new files reported clean. Self-review confirmed that file replacement
occurs after serialization and fsync, temporary cleanup has no directory scan,
load never resolves reference content, and canonical project input is unchanged
by the explicit resolver. The final production edit after GREEN was docstring
wording only, clarifying that `Path.resolve` reads no referenced content, while
it may inspect filesystem symlinks. No behavioral production edit followed GREEN.

At final status inspection, other owners had modifications to `systems.py`,
`tests/test_systems_integration.py`, and a new `runtime-release-candidate.md`.
Those files were not edited by this phase.

## Frozen deliverables and SHA-256

| File | SHA-256 |
| --- | --- |
| `tools/plimsoll/project_store.py` | `038166D2BE8271CE191294237A823DCB64F4962CBF6AEC2BC5AD9DF7B49824E6` |
| `tools/plimsoll/tests/test_project_store.py` | `B4B9E8DEAE73B43561C27F875E801E8D68B779F8CDF193BFCE7BF7F7758593FF` |
| `docs/plimsoll-1.0/project-store.md` | `AA9390B4657341C6E605CC94CD39F10CA6BCC020693EA757CCF40B93F2D65F59` |

Scratch artifacts: this report and `task-8-persistence-mutations.py`.

## Limitations and next released scope

- Saving a reference project into another directory preserves the literal path;
  it does not package external geometry. Missing references remain valid editable
  inputs. The resolver does not check existence or validate geometry contents.
- Parent directories must already exist. Persistence exposes ordinary file and
  JSON errors directly; callers must surface them. No locking, concurrent-edit
  conflict detection, directory fsync, backup history or power-loss guarantee is
  claimed. An ungraceful process exit may leave an owned temporary file.
- Existing package initializer path injection remains untouched under ownership
  restrictions; package smoke checks do not claim that known integration debt
  is solved. `project_io` and `loading` remained read-only.
- After Task 4/6/7 reviews and explicit controller release: build the immutable
  calculation coordinator and separate request identity; integrate reviewed
  numerical APIs and typed stage validity; add explicitly requested geometry
  materialization/import with validation, provenance and content hashes; deliver
  the remaining C1/C4 geometry analysis/curves/deck boundaries; fix coordinated
  loading diagnostic routing and package imports; then exports, real batch/sweep
  CLI, game contract example and all Task 8 decision/field-map requirements.
  Browser import must consume user-selected content, not arbitrary local reads.
- Full integration testing, commits and independent review remain controller
  coordinated. No whole-Task-8 completion claim is made.

---

# Geometry-analysis phase — appended 2026-09-22

Status: **GEOMETRY_READY — frozen for controller review.**

Released base: `3f18bcb`. This is the next independent Task 8 building-block
phase, not completion of the coordinator/exports/CLI/UI work. The three
persistence files retained their exact previously recorded hashes.

## Scope and implementation

New files:

- `tools/plimsoll/geometry_analysis.py`
- `tools/plimsoll/tests/test_geometry_analysis.py`
- `docs/plimsoll-1.0/geometry-analysis-api.md`

Controller expressly extended ownership for two small shared-API changes:

- `stability.py`: add public `prepare_geometry(hull, options=None)` with options
  type validation, calling `_prepare` unchanged. Return tuple and ownership/datum
  are documented. No solver code changed.
- `geometry.py`: expose `waterline_intervals` by extracting the existing
  contact/concavity interval logic. `_line_chord_halfwidth` retains its signature
  and sums those same intervals. No alternate clipping kernel was introduced.

Implemented public helpers:

1. `parameterized_hydrostatics`: validates numeric types before legacy coercion;
   traces actual L0 formulas/default assumptions, preserves null/zero/source and
   estimate provenance, retains positive-reference discrepancy warnings, and
   reports missing/infeasible inputs explicitly. It is labeled a parameterized
   design-waterline study, not loaded equilibrium.
2. `materialize_reference_hull`: requires all dimensions/Cb/Cwp, explicit flat
   deck depth above keel, datum and source/estimate. Uses the existing generator
   with explicit depth/deck, records parameter/source identity and content hash,
   marks generated polygons estimated, and validates through the shared adapter.
3. `measures_at_plane`: reuses the selected p/q/d, section clipping and submerged
   integration. Provides centroidal in-plane waterplane moments, explicit
   body-axis reference coefficients, and a declared estimated station-girth
   wetted area excluding end faces and longitudinal shell slopes. Inclined planes
   do not acquire upright BM/TPC or empirical eligibility. Contact edges suppress
   derivative-based quantities while retaining geometric intersection measures.
4. `bonjean_table` and `hydrostatic_table`: explicit bounded requested levels with
   both datums and density. Preserve contact/out-of-envelope rows and distinguish
   constrained upright reference studies from selected loading equilibrium.
5. `deck_clearance` and `deck_immersion_events`: supplied sourced deck points,
   exact signed normal distance, sampled contacts/sign brackets/unknown endpoint
   states, failure gaps and no fabricated refined root or safe-angle claim.

Inventory correction: the earlier controller note that no Bonjean function
existed was stale/incomplete. `StationedHull.bonjean_curve` is present and this
phase reuses it. No replacement Bonjean clipping implementation was invented.

## RED/GREEN evidence

The command prefix, worktree and actual Python version remain as documented in
the persistence phase. The geometry test command was:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_geometry_analysis.py -v
```

Initial RED: 18 assertion failures, `geometry-analysis API is not implemented`.
After the shared API scope extension, RED was 21 assertion failures, including
`public adapter is absent` and `public intervals are absent`. Tests existed
before the module, public wrapper and interval extraction.

First implementation run: 19/21 passed. The two failures were inappropriate
exact Python equality for 1.0000000000000002 versus 1 and 9.000000000000002
versus 9. Those assertions were corrected to the **already predeclared** relative
and absolute 1e-10 tolerance, not a relaxed scientific threshold. Then 21/21
passed in 1.389 s.

Self-review added explicit regressions before fixes:

- Concave boundary-edge contact incorrectly exposed TPC/BM as a one-sided
  derivative: observed `1.2299999999999998 is not None`; fixed by checking original
  boundary-edge coincidence and suppressing derivative quantities.
- Null source container blocked otherwise computable L0 geometry with
  `ValueError: hull.sources must be an object`; fixed with an explicitly
  unprovenanced empty effective source map, preserved original null, and diagnostic.
- Removing all legacy reference masses had suppressed a positive-reference
  discrepancy warning: observed failed warning assertion; only zero is now
  handled outside the legacy truthiness branch, preserving positive warnings.
- Direct reference-mass estimate=False was overwritten by the derived-model
  estimate marker: observed `True is not False` using the focused command below;
  direct input provenance now remains distinct from derived model estimates.
- Boundary contact still indicated upright empirical eligibility: observed
  failed false assertion; eligibility now follows the non-contact derivative gate.

Focused commands for the last two RED checks appended respectively
`-k positive_reference` and `-k boundary_edge` to the geometry unittest discovery
command (without `-v`). Both exited 1 before their fixes.

Final geometry GREEN after the final behavior edit:
`Ran 25 tests in 1.440s`, `OK`, exit 0. No warnings or failing tests.

Targeted shared-kernel/L0 regressions:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_stability_loading.py -v
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_hydrostatics.py -v
```

Stability: 36/36 passed in 11.392 s, exit 0, including old contact/concavity,
coupled equilibrium, geometry readiness, datum, refinement and liquid tests.
L0: 28/28 passed in 0.004 s, exit 0. These historical regression tests are
compatibility evidence, not independent historical validation claims.
The final combined targeted coverage is 25 + 36 + 28 = 89 tests. This was not a
full-suite run. No commits or pushes were created.

## Scientific and mutation evidence

Predeclared box/triangle/keel-shift algebraic checks retain rel/abs tolerance
1e-10. Tests exercise box V=240 m³, displacement=246 t, KB=1 m, Awp=120 m²,
IT=360 m⁴, IL=4000 m⁴, BM_T=1.5 m, KM_T=2.5 m, TPC=1.23 t/cm and unit form
coefficients at draft 2 m. Girth wetted area is explicitly 200 m² rather than
the complete-shell 224 m². Triangle V=48 m³, KB=4/3 m, Awp=48 m² and IT=23.04
m⁴ provide an independent nonlinear section-area anchor. Concave occupied
intervals and asymmetrically translated sections test true centroidal moments.

The real loaded solver is exercised both with explicit generated reference
geometry and with a listed/trimmed generic box. Selected p/q/d and volume are
retained; no z=0 or forced-upright result is substituted.

Reproduction command:

```powershell
$env:PYTHONIOENCODING='utf-8'; & 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B .superpowers/sdd/2026-09-22-plimsoll-1.0/task-8-geometry-evidence.py
```

Exit 0. Six in-memory mutations were detected: omitted local station trim,
omitted inclined area factor, omitted deck keel shift, omitted signed-distance
normalization, wrong longitudinal moment integration power, and discarded
materialization keel shift. Production files were never mutated by this helper.

Actual 41-station/48-subdivision to 81/96 reference refinement relative deltas:

| Quantity | Relative delta |
| --- | --- |
| volume | 0.0020396634269995665 |
| waterplane area | 0.0007730633719727651 |
| transverse waterplane inertia | 0.0007709402651835369 |
| KB | 0.0012179775550215045 |

All are below the predeclared 0.01 (1%) limit; maximum is approximately 0.204%.
Independent expected reference displacement volume is 144 m³. The materialized
geometry's real equilibrium also satisfies scaled residual <=1e-6.

Raw box/triangle/inclined results, resolutions/content hashes, refinement and
mutation outcomes are in `task-8-geometry-evidence.json`, reproduced by the
adjacent Python helper. These generic anchors are not historical validation.

## Final checks, hashes and remaining scope

Self-review read the small shared-file diff: `geometry.py` +16/-4 lines and
`stability.py` +12/-0. No solver, package import, schema, loading, case,
resistance, exports, CLI or UI edits were made by this phase.

`git diff --check -- tools/plimsoll/geometry.py tools/plimsoll/stability.py`
was clean. Each new file also passed the same no-index whitespace check wrapper
documented earlier. Final SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `tools/plimsoll/geometry_analysis.py` | `0C78C553FB7FBD624984D98B4BE018E86C4273F2623548CFF38D527814C76876` |
| `tools/plimsoll/tests/test_geometry_analysis.py` | `D5248D18723B52DC461800CFCAFDAC451E94D03B954F81103299E93986EE5680` |
| `docs/plimsoll-1.0/geometry-analysis-api.md` | `088CB162D24325DE301CBFA4C4880680E7D5B5624C62F8A78664910E718382DD` |
| `tools/plimsoll/geometry.py` | `1C6E6E038C31DBC1D812A9D95EC2DE4670FEBBC4E0E17B1EC438D7C659323482` |
| `tools/plimsoll/stability.py` | `54AA735ED039167165866DEF7039783D72AC183FD3340BBAF5FC24C823541321` |

All three persistence hashes were rechecked and exactly match the earlier phase.

Limitations are intentional and documented: station quadrature remains an
approximation; reference dimensions use station support rather than refined
waterline endpoints; wetted area is girth-based and excludes end faces; inclined
ratios are not upright empirical resistance inputs; deck events are sampled and
unrefined; helper results do not contain a coordinator request identity or new
project schema fields. An explicit L0 default can replace an unknown optional
parameter only as a serialized estimated assumption while retaining original
null input. No new scientific calibration or ship-specific constants were used.

Next scope still requires an explicit controller release: immutable coordinator
integration, external content import/materialization with provenance/hash,
coordinated canonical optional fields and loading diagnostic routing, ordinary
package imports, exports, real batch/sweep CLI, game contract and the complete
Task 8 decisions/field-map gates. Slight loaded trim adaptation for empirical
resistance must be separately declared and validated; these helpers deliberately
do not silently make that approximation. Full Task 8 remains incomplete.

# Task 8A fix round 1 — READY_FIX, frozen

2026-09-22. Controller released BASE `93218ff`; shared HEAD was `cafc5ca`
at final inspection (no commit made by this agent). Read all five findings in
`task-8a-review-round-0.md` verbatim and verified them against the implementation.
Also read the user-authorized `current-core-scope.md`: current acceptance is
class-SPS Python/CLI calculation core plus project/calculation JSON/CSV and
actual field bindings. UI/service/deployment/Windows packaging/HTML display and
game-specific export are deferred; earlier report references are historical.

## Changes against the five findings

- Important 1: L0 validates every supplied numeric field (both draft spellings),
  all four estimate flags and source-map type before either early return.
  Deck point validation is shared and is performed before processing event
  samples; malformed deck/source/estimate/ordinates or keel reject even if all
  equilibria failed. Null deck remains unknown. No numerical solver changed.
- Important 2: absent/null/empty L0 source maps diagnose unknown provenance.
  Every supplied direct numeric input lacking its source dependency has an
  individual `l0.input_source_unknown` diagnostic, including KG=0 and reference
  displacement=0. Partial maps preserve sourced facts and diagnose remaining
  dependencies; literal input source maps are unchanged.
- Minor 1: shape-limit path is now exactly `$.hull`.
- Minor 2: absent/null estimate flags used as conservative effective defaults
  each have source/value/original-null assumptions and matching diagnostics.
  Original input and direct-input trace unknowns are not converted to measured
  provenance; explicit false is not defaulted.
- Minor 3: save catches the primary failure, attempts cleanup only for its
  owned temporary path, and re-raises the same exception. An OS cleanup failure
  adds a note with path/error rather than masking the original exception.
  Successful replace already consumes the path and performs no second unlink.
  Actual prior-file bytes and unrelated-temp preservation are covered.

Only six of the eight released paths changed: geometry_analysis/project_store,
their tests and their two API docs. geometry.py/stability.py remain unchanged.
Scratch preparation was also updated with accepted 8B rulings, current scope
and the requirement to recompute request identity from current normalized
options rather than compare echoed client hashes. No 8B production work began.

## RED and targeted GREEN evidence

Each command below ran from the worktree with
`$env:PYTHONIOENCODING='utf-8'` and interpreter
`C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B`
(actual Python 3.13.14). The exact command pattern was:

```powershell
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_geometry_analysis.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_store.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_hydrostatics.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
```

| Run | Outcome |
| --- | --- |
| Geometry RED, before implementation | 30 tests, 26 expected failing subtests/assertions, 1.498s, exit 1. Failures were missing upfront validation, missing source/default assumptions and wrong shape diagnostic path. |
| Persistence RED, before implementation | 18 tests, 2 expected failing subtests, 0.468s, exit 1. Cleanup PermissionError replaced both injected fsync and replace primary exceptions. |
| Geometry GREEN | 30 tests passed, 1.453s, exit 0. |
| Persistence GREEN | 18 tests passed, 0.445s, exit 0. |
| Legacy hydrostatics regression | 28 tests passed, 0.003s, exit 0. |
| Project-I/O regression | 21 tests passed, 0.005s, exit 0. |

Six new test methods cover the five findings; subtests distinguish missing,
infeasible and completed L0 inputs and failed-only deck samples. OS failure
injection is confined to fsync/replace/unlink while writing real temp files.
97 targeted tests passed. `git diff --check` passed. No full suite, new mutation
run or commit; the controller's earlier 545-test full pass predates these fixes
and is not represented as verification of this round.

## Frozen SHA-256

| File | SHA-256 |
| --- | --- |
| `tools/plimsoll/geometry_analysis.py` | `B6DC22ACDD9001FDD8A8A383C23B8228FF3C50DC9FF7AB8742DBD4D0B6248291` |
| `tools/plimsoll/project_store.py` | `2C83B4DBEC976F897E3C502709C570F2B63D2A2326B3530E9A0A2067306307B7` |
| `tools/plimsoll/tests/test_geometry_analysis.py` | `35C8D2670F4519F02CA916201A80BB1E98F4E89D48A1BB426568E3712610B5DC` |
| `tools/plimsoll/tests/test_project_store.py` | `A14A3B2B1A649B73A0B42AA7CFD0341CBCB54BE44A7A382064B190DCDA77113B` |
| `docs/plimsoll-1.0/geometry-analysis-api.md` | `B486203F3DEC2DD48FA6D75B0ABE0B079420C5924A880FB1919F0B3FB5A02F0F` |
| `docs/plimsoll-1.0/project-store.md` | `4255FBF35B9AF85D99DC23C8A0A66D454EEEC29576F6B34AA68792E52BE2D72F` |
| `tools/plimsoll/geometry.py` (unchanged) | `1C6E6E038C31DBC1D812A9D95EC2DE4670FEBBC4E0E17B1EC438D7C659323482` |
| `tools/plimsoll/stability.py` (unchanged) | `54AA735ED039167165866DEF7039783D72AC183FD3340BBAF5FC24C823541321` |

Limitations remain as documented in 8A: source diagnostics do not establish
historical validity; cleanup may leave the explicitly identified temp if the
filesystem rejects unlink; openings knowledge persistence and coordinator
integration remain mandatory 8B work after controller release. Awaiting
independent fix review. This is READY_FIX, not whole-core completion.

# Task 8B schema/loading phase — SCHEMA_READY, frozen

2026-09-22. Released at BASE `ed26f7e`; shared HEAD at final checks was
`dcefdd0`. This agent made no commit. Read accepted 8B preparation/rulings,
current core-only scope and the CLI preparation. The 8A helpers/store remain
frozen. Task6 concurrent files and its generic_flooding_box fixture were not
edited. No source importer, coordinator, package initialization, numerical
equation, CLI, export, UI or service implementation began in this phase.

## Exact owned changes

1. `tools/plimsoll/project_io.py`: persistent opening_definition defaulting and
   consistency validation; validated per-field override_provenance/acceptance;
   optional extension validation; actual array/index and quoted override paths.
2. `tools/plimsoll/loading.py`: individual effective-field provenance and origins,
   unknown legacy override provenance, conservative aggregate estimates, bounds
   replacement per field, per-field provenance/uncertainty assessment, correct
   diagnostic path for clearing inherited uncertainty. No mass/moment equations
   changed and no input/base/other-condition mutation.
3. New `tools/plimsoll/project_extensions.py`: validates optional metadata,
   display preferences, deck/profile references, typed propulsion/weapon/armour
   facts, explicit fuel ledger ownership, resistance/endurance scenarios,
   same-condition historical comparison inputs and stored acceptance records.
   This module imports no numerical kernel and makes no calculations/default
   scenarios. Existing installed/broadside counts and mass_models are untouched.
4. New `tools/plimsoll/tests/test_project_extensions.py`: 18 focused methods,
   including actual Chinese-path save/reopen and selected loading resolution.
5. `tools/plimsoll/tests/test_loading.py`: replace the old diagnostic suffix
   expectation with the correct array index and JSON-quoted item-key path.
6. `docs/plimsoll-1.0/data-contract.md`: opening and effective provenance rules.
7. New `docs/plimsoll-1.0/project-extensions.md`: exact optional field paths,
   types, units, source/estimate semantics and remaining execution boundaries.

No generator or case changes were needed. The generator serializes its own raw
payloads and the three existing cases declare nonempty openings; normalization
infers supplied without rewriting those committed fixtures. The byte-determinism
regression passed. The new Task6 generic_flooding_box fixture was not included
in owned changes or regeneration.

## Implemented semantics and remaining boundaries

Absent raw opening definitions become unknown before default []; marker-free
legacy [] becomes legacy_ambiguous; explicit none requires supplied+[]. The
states persist, diagnose ambiguity and produce distinct project/loading hashes.
New drafts/legacy migration start unknown. Supplied points require supplied
knowledge: when adding points to a newly created draft, edit the marker too.
The later coordinator/Task6 bridge still must convert unknown/ambiguous to None
and supplied to the actual array; this phase does not claim that bridge exists.

Override metadata never inhabits numeric overrides. Metadata must match an
actual item/field override; bounds must contain its nominal. Missing override
source/estimate stays unknown instead of inheriting a base mass source.
Unchanged coordinates retain base attribution. Field-level uncertainty flags
avoid relabeling every coordinate as estimated merely because mass is estimated.
Aggregate estimate true does not hide another field's unknown source/estimate.
Stored acceptance validates condition, value and identity format, but does not
prove freshness or authorize application. The future proposal API must recompute
current normalized-request identity and the actual systems proposal/value/source.

Optional facts are validated input bindings, not decorated computed results.
The exact documented paths must be consumed or explicitly marked unavailable/
excluded by the forthcoming coordinator and seven-page output registry. Shape
scenario unknowns stay unknown and no bare-hull/QPC assumptions are inserted.
Legacy raw system keys retain their reviewed contracts. The 8A review's minor
unused KG/reference estimate-default assumption note remains carried to the next
authorized geometry/coordinator pass; frozen geometry files were not changed.

## RED → GREEN and focused regressions

All commands ran from the worktree with PYTHONIOENCODING=utf-8 and
`C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B`
(actual Python 3.13.14). Exact test command form:

```powershell
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_extensions.py
```

The same command was run with each pattern below. RED evidence, before each
relevant implementation:

- Initial 7 opening/provenance methods: 10 assertion/subtest failures and 5
  missing-result-key errors because opening_definition/provenance.fields did not
  exist; exit 1, 0.030s. GREEN 7 passed, 0.038s.
- Optional facts/scenarios: 14 methods, 34 expected failing assertions/subtests
  because malformed optional data was accepted; exit 1, 0.058s. GREEN 14 passed,
  0.034s.
- Stored acceptance integrity: 16 methods, 6 expected failing subtests for
  stale-format/wrong-condition/value/provenance records; exit 1, 0.040s.
  GREEN 16 passed, 0.039s.
- Whitespace-only override source: 18 methods, 1 expected false-completeness
  failure; exit 1, 0.043s. GREEN 18 passed, 0.040s.
- The first legacy loading regression exposed one old assertion depending on
  the malformed path suffix. Updated that assertion to the explicitly approved
  correct path; no numerical test anchor or tolerance changed.

Final fresh targeted evidence after all implementation changes:

| Pattern | Tests | Elapsed | Result |
| --- | ---: | ---: | --- |
| `test_project_extensions.py` | 18 | 0.043s | exit 0, passed |
| `test_loading.py` | 15 | 0.015s | exit 0, passed |
| `test_project_io.py` | 21 | 0.007s | exit 0, passed |
| `test_project_store.py` | 18 | 0.485s | exit 0, passed |
| `test_project_cases.py` | 8 | 2.047s | exit 0, passed |
| `test_systems_integration.py` | 19 | 0.346s | exit 0, passed |

99 targeted tests passed. An initial mistaken `test_systems.py` pattern matched
zero tests (exit 1, NO TESTS RAN); corrected to test_systems_integration.py above.
No full suite was run. No quantitative numerical acceptance tolerance changed.

In-memory mutations:

```powershell
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B .superpowers/sdd/2026-09-22-plimsoll-1.0/task-8b-schema-mutations.py
```

All 3 caught through assertion failures, no harness errors: unknown openings →
supplied (2 failures); inherit base source for unsourced override (1 failure);
remove bool-as-number guard (3 failures). Source files were never rewritten.
Evidence is task-8b-schema-mutations.json; script is alongside it.
`git diff --check` passed. Explicit UTF-8/final-newline/no-trailing-whitespace
checks passed on all three new files. Frozen 8A geometry/store/kernel hashes
were rechecked and matched the prior fix report.

## SHA-256 freeze

| File | SHA-256 |
| --- | --- |
| `tools/plimsoll/project_io.py` | `AA87146C94B74ACF670F9EF69F69ECCDBEB8D18C4D4386FDC4896F8239D2460E` |
| `tools/plimsoll/loading.py` | `2416BFEA526F432F7C174DE9A2F958FE16230BCE35263A619A623BCB6AEE3CBE` |
| `tools/plimsoll/project_extensions.py` | `6B6C433603A18BD09A07F7F14D7F69E67663CF1A3C463A03B7F36EB931501EC0` |
| `tools/plimsoll/tests/test_loading.py` | `F937097B3D6E74B88A134866DC1C6D5F99B7DC206B937517A1AAE33950408051` |
| `tools/plimsoll/tests/test_project_extensions.py` | `902356B1DFF52729D1E969DE1F4AA4BC83534C398244D027441BFC125004243F` |
| `docs/plimsoll-1.0/data-contract.md` | `18287EBE6880FE4BDA6B35CBAA55887BCA342E4106158AD609A0A412518D2944` |
| `docs/plimsoll-1.0/project-extensions.md` | `76350764D5D7079A29720B1EB99D3B0C8E809107FD238104990574736C41AA4C` |

SCHEMA_READY is an independent phase gate only. Await controller release before
coordinator/import/package/proposal-application edits; no whole-core completion
claim is made by these schema and loading checks.

## Schema fix round 1 — READY_FIX (2026-09-22)

Authorized base: `9655584`. Read all four findings in
`task-8b-schema-review-round-0.md` before changes. Only three of the seven
authorized schema paths changed: `project_extensions.py`,
`tests/test_project_extensions.py`, and `project-extensions.md`. The other four
remain byte-identical to the schema freeze. No loading equations, cases,
generators, persistence, numerical kernels, importer, package imports or
coordinator code changed. Other owners' working-tree changes were left alone.

### Finding resolutions

- Important 1: every present coal/oil ownership or explicit-absence declaration
  now requires nonempty string/object source and boolean estimate. An omitted
  binding remains omitted/unknown. Tests cover both ownership and absence with
  missing, null, blank, empty-object and invalid estimate provenance, plus
  positive string/object source and true/false estimate cases. Existing fuel
  ownership negative tests now supply valid provenance so they still detect
  ownership defects independently of the new provenance gate.
- Important 2: declared system leaves cannot contain nested recognized system
  declarations, even through intermediate containers. Their local and nested
  typed facts are still validated; a parent boundary cannot suppress a malformed
  child. Facts, mass_models, source and fuel_bindings are leaf payloads and are
  excluded from system descent; source metadata remains opaque. Tests exercise
  all three leaf-boundary keys across propulsion/weapons/armour, with malformed,
  valid and nullable child facts. A fact leaf's declared weight_item_ids now
  require an array of unique existing IDs. Empty/status-only draft declarations
  remain allowed; systems.summary retains present/absent, shared ownership and
  accounting authority. No reviewed installed-count or mass-model keys changed.
- Important 3: stored replacement acceptance requires finite nonnegative
  previous_mass_t, including an explicit zero when that was the prior mass.
  Missing/null/bool/negative/nonfinite cases reject. Recomputing that prior value
  against the real current selected condition remains the later application
  API's responsibility; this is a stored-audit validation gate.
- Minor 1: a present table_sha256 must be exactly 64 lowercase hexadecimal
  characters. Null, wrong length, uppercase and nonhex identities reject. The
  small shared SHA validator preserves acceptance-fingerprint validation.

Nullable descriptive facts and literal null provenance continue to survive
normalization. No complete coordinator/proposal/endurance behavior is claimed.

### RED and focused GREEN evidence

Working directory for every command:
`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`.
All Python commands used the declared interpreter and UTF-8 environment:

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_extensions.py
```

Before production edits: 22 tests, 50 assertion failures, no test errors,
0.068s, exit 1. Failures specifically exposed absent provenance errors,
unreached nested facts/link diagnostics, missing/null previous mass and invalid
table identities. After production edits: 22 tests, 0.046s, exit 0.

After the final test and documentation edits, the following exact commands all
passed (independent focused suites; no full suite):

```powershell
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_extensions.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_loading.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_store.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_project_cases.py
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_systems_integration.py
```

| Suite | Passed | Seconds |
| --- | ---: | ---: |
| project_extensions | 22 | 0.046 |
| loading | 15 | 0.011 |
| project_io | 21 | 0.006 |
| project_store | 18 | 0.514 |
| project_cases | 8 | 2.116 |
| systems_integration | 19 | 0.372 |

Total: 103 targeted tests passed, including Chinese-path roundtrip, prior-file
preservation, selected loading, reviewed systems and generator determinism.
No full-suite run, commit, index operation or new mutation probe was performed.
An exploratory Windows `rg` read with a shell wildcard path failed before search;
this was not a validation command or test result.

```powershell
git diff --check -- tools/plimsoll/project_io.py tools/plimsoll/loading.py tools/plimsoll/project_extensions.py tools/plimsoll/tests/test_loading.py tools/plimsoll/tests/test_project_extensions.py docs/plimsoll-1.0/data-contract.md docs/plimsoll-1.0/project-extensions.md
Get-FileHash -Algorithm SHA256 tools/plimsoll/project_io.py,tools/plimsoll/loading.py,tools/plimsoll/project_extensions.py,tools/plimsoll/tests/test_loading.py,tools/plimsoll/tests/test_project_extensions.py,docs/plimsoll-1.0/data-contract.md,docs/plimsoll-1.0/project-extensions.md
```

Scoped diff check passed. Final seven-path SHA-256 freeze:

| File | SHA-256 |
| --- | --- |
| `tools/plimsoll/project_io.py` | `AA87146C94B74ACF670F9EF69F69ECCDBEB8D18C4D4386FDC4896F8239D2460E` |
| `tools/plimsoll/loading.py` | `2416BFEA526F432F7C174DE9A2F958FE16230BCE35263A619A623BCB6AEE3CBE` |
| `tools/plimsoll/project_extensions.py` | `91040FC54849B387EB736CBBAA102C896F0450D7541B3CF5C31D124D60B2B14D` |
| `tools/plimsoll/tests/test_loading.py` | `F937097B3D6E74B88A134866DC1C6D5F99B7DC206B937517A1AAE33950408051` |
| `tools/plimsoll/tests/test_project_extensions.py` | `F76B721C3AB4E5996A209D3F918AE4A9601432CC88AD901832723A7558049476` |
| `docs/plimsoll-1.0/data-contract.md` | `18287EBE6880FE4BDA6B35CBAA55887BCA342E4106158AD609A0A412518D2944` |
| `docs/plimsoll-1.0/project-extensions.md` | `03D5E4288251C2F23D3AC5E692302F09E70392C8A8219CBBF6872578FF06DB4D` |

READY_FIX: all seven schema paths are frozen pending independent re-review.
Coordinator/proposal implementation remains gated; importer and package-import
work belong to their separate authorized owners.
