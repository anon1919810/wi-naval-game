# Task 7 implementation report

Date: 2026-09-22

Status: committed as `84271fe` (`feat: add resistance and systems models`) after
the coordinator's shared full-suite run. No remote push was made.

## Runtime and verification

The required executable path was used with `-B` and
`PYTHONIOENCODING=utf-8`:

```text
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe
actual sys.version: 3.13.14 (main, Jun 11 2026, 04:04:46) [MSC v.1944 64 bit (AMD64)]
SHA-256: ec8139feb5012b12a531196f257fddf53668f0109918d5d44ffa195cf352fdd6
shared HEAD at final targeted run: f9c5ee803cea4314297dfd9ded0d0b472a1e08f0
```

Final targeted command covered the Task 7 modules, canonical generation, and
the one selected legacy integration regression:

```text
python -B -m unittest \
  tools.plimsoll.tests.test_holtrop \
  tools.plimsoll.tests.test_friction \
  tools.plimsoll.tests.test_resistance \
  tools.plimsoll.tests.test_engines \
  tools.plimsoll.tests.test_systems_integration \
  tools.plimsoll.tests.test_project_cases \
  tools.plimsoll.tests.test_calculation_integrity.CalculationIntegrity.test_reynolds_warning_survives_curve_and_identifies_speed

Ran 115 tests in 2.711s — OK
```

`test_project_cases` generated every canonical case twice and compared bytes
with the committed fixtures. A fresh direct generation changed only
`queen_mary_1913.project.json`; `generic_steamer.project.json` and
`analytic_box.project.json` remained byte-identical. `git diff --check` passed.
Per coordinator instruction, this worker did not independently repeat the
shared full suite.

The coordinator's frozen Task 4/7 shared regression ran the complete suite from
the same recorded source hashes:

```text
Ran 482 tests in 137.817s — 0 failures/errors
process elapsed wall time: 138.307s
scope unchanged during run: true
evidence: task-4-7-regression.json and task-4-7-regression.log
```

Immediately before staging, all fourteen Task 7 file SHA-256 hashes matched the
`scope_sha256_after` values in that regression manifest. Only those fourteen
paths were staged and committed.

## RED and GREEN evidence

- The production Holtrop tests initially failed at import because
  `tools/plimsoll/holtrop.py` did not exist. The resistance/friction tests
  initially failed on the absent named friction APIs and absent strict
  source-axis interpolation mode. Systems tests likewise failed before
  `systems.summary` existed. The implementation was then built from the
  separately audited prototype mathematics rather than copying it as accepted
  production.
- Engine RED cases exposed the partial-bunker bug: one missing fuel was being
  converted to zero and reported as a complete total. Additional RED cases
  caught both-fuels-unknown subtotal handling and unchecked
  `range_at_speed_kn` when `range_nm` was absent. Their focused GREEN behavior
  is null complete total, separately named known subtotal, explicit-zero
  preservation, and finite numeric validation.
- Endurance hardening RED showed that a positive burn marked non-required and
  scenarios without source/estimate metadata were accepted. Positive burn now
  requires `required: true`, and provenance fields are mandatory.
- Systems hardening RED caught an empty systems object being reported complete;
  it now emits blocking `systems.none_declared`.
- Holtrop hardening RED required exceptions to carry structured blocking
  diagnostics; `HoltropInputError` and `HoltropNumericalError` now do.
- The selected shared regression reproduced exactly as 53 passing and one
  failure in a 54-test focused command: a 28.1 kn Reynolds-range warning still
  existed but no longer contained the historical `Schoenherr` identity. The
  warning now names the method honestly as the “Conn 1953 explicit Schoenherr
  approximation” while the curve retains `[28.1 kn]` context. The focused test
  then passed.
- Two new canonical physical-input tests first failed with two `KeyError:
  'armour'` errors. After the generator and summary changes, both passed, and
  the wider systems/project selection passed 22 tests.
- A strict Taylor curve diagnostic test first failed with `KeyError:
  'diagnostics'`. The curve now preserves the blocking table diagnostic with
  speed and input-path context at both row and curve level; the focused test
  passed.

## Holtrop--Mennen 1982

`holtrop.compute` implements the complete versioned
`holtrop_mennen_1982` resistance sum: friction with the 1982 form factor,
appendages, wave resistance, bulb resistance, immersed-transom resistance, and
correlation resistance, plus separately declared optional bow-thruster and
additional-roughness increments. It does not mix the 1984 form-factor or wave
regressions.

The frozen independent NTUA reproduction benchmark uses the paper's 205 m by
32 m hypothetical hull at 25 kn. Component targets and the predeclared source
tolerance are:

| Result | Target | Tolerance |
| --- | ---: | ---: |
| RF | 869.47 kN | 0.1% relative, 0.005 kN floor |
| RAPP | 8.83 kN | 0.1% relative, 0.005 kN floor |
| RW | 556.63 kN | 0.1% relative, 0.005 kN floor |
| RB | 0.049 kN | 0.1% relative, 0.0005 kN floor |
| RTR | 0 kN | exact zero |
| RA | 220.53 kN | 0.1% relative, 0.005 kN floor |
| total | 1791.54 kN | 0.1% relative, 0.005 kN floor |
| effective power | 23039 kW | 0.1% relative, 0.5 kW floor |

Independent algebraic tests verify component aggregation, `PE=RT*V`, exact
international-knot conversion, density scaling, explicit wetted area, and
weighted appendage force at `1e-10` relative tolerance. Tests cover both sides
and equality conventions for c12, c7, c15, c16, lambda, c4, and c6; explicit
zero bulb/transom/appendage branches; fore-draft-only terms; positive and zero
c5; the real negative-PB branch; the exact PB singularity; missing inputs;
bool/nonfinite/huge/tiny inputs; optional terms; high-Froude and project
low-Reynolds eligibility.

The audited primary paper's printed `CA`, `CF`, `RA`, and `RF` do not satisfy
`RA/RF=CA/CF`. The implementation follows the verified equations and coherent
NTUA component reproduction. It does not tune constants or tolerance to the
paper's inconsistent printed total.

## Friction and Taylor--Gertler

The legacy `schoenherr_cf` entry point remains the explicit Conn 1953
compatibility approximation and is now available under the exact method ID
`conn_1953_schoenherr_approx`. The source-conformance option
`schoenherr_implicit_ittc_0.242` solves the implicit equation. Tests cover the
official ITTC table anchors from `Re=1e5` through `1e10` at the printed
`5e-7` coefficient tolerance, inverse construction, and equation residual at
`1e-10`.

Taylor's source-oriented mode is
`taylor_gertler_source_axis_strict`. It interpolates on the printed
`L/volume^(1/3)` axis, rejects points outside the stored axes, and returns
unavailable when any positive-weight corner is missing. Exact nodes ignore
unrelated zero-weight holes. The midpoint test at source coordinate 7.5 proves
that this differs from reciprocal-cube interpolation. The tracked table adapter
associates exact headings `[10, 9, 8, 7, 6, 5.5]` without rewriting cells.

The existing endpoint-clipping and missing-corner-renormalizing behavior remains
available under `legacy_volume_ratio_clip_renormalize`. Friction, interpolation,
speed conversion, roughness, and QPC methods are recorded separately. Strict
table diagnostics survive a speed curve with speed context.

## Engines and endurance

Legacy rounded power and speed conversions remain the defaults under explicit
compatibility method IDs. New callers can select precise `units.convert`
mechanical horsepower and the exact international knot.

A bunker total exists only when coal and oil are both known. Explicit zero is
known. With one known fuel, only `bunker_known_subtotal_t` is available and
`engines.bunker_partial` explains why total and percentage are null. With both
unknown, subtotal is also null.

Computed endurance requires a declared
`steady_simultaneous_fuel_consumption` scenario. Each consumed fuel has its own
mass, reserve, and burn rate. The earliest required depletion limits duration;
range is `hours * speed_kn`. Zero burn is unused and never emits infinity.
Missing required values yield null endurance and a blocking structured
diagnostic. Positive burn requires `required: true`, and scenario source plus
estimate status are mandatory. Historical range stays a separate comparison
input.

## Systems and Queen Mary physical inputs

`systems.summary(project, state)` treats the selected effective loading ledger
as the sole mass authority. It flattens reviewed Task 3 system leaves, preserves
condition and fingerprints, links effective-item provenance, distinguishes
installed from broadside counts, detects missing/repeated/shared ownership, and
returns review-required proposals for physical formula discrepancies without
mutating the project or loading state.

The Queen Mary augmentation adds thirteen fixed-armour models using the legacy
rounded areas and nominal thicknesses with density 7,850 kg/m3:

```text
armour-belt-229mm                 627.0 m2  229 mm
armour-belt-taper-102mm-aft      154.0 m2  102 mm
armour-belt-taper-102mm-fwd      323.4 m2  102 mm
armour-bulkhead-aft              321.61 m2 102 mm
armour-bulkhead-fwd              373.24 m2 102 mm
armour-deck-25mm                 3995.88 m2 25 mm
armour-deck-64mm                 5314.13 m2 64 mm
armour-upper-belt-152mm          501.6 m2  152 mm
barbette-a / barbette-b / q      39.98 m2 each, 229 mm
barbette-x                       47.82 m2  229 mm
conning-tower                    201.03 m2 254 mm
```

The calculation is `area_m2 * thickness_m * density_kg_m3 / 1000`.
One-decimal areas declare 0.1 m2 display resolution and two-decimal areas 0.01
m2. The algebraic comparison uses the project-standard `1e-10` relative and
absolute-t tolerance, so the thirteen preserved rounding differences surface as
thirteen proposals. Differences range from `-0.007377 t` to `+0.007717 t`.
No area is fitted back from a ledger mass, and the accepted normal-loading total
remains exactly `27851.62934079477 t`.

Six armament models use the accepted generator precision:

```text
main guns:        8 installed * 76.10191346912 t
main mounts:      4 installed twin mounts * 609.62814528 t
main ammunition:  8 installed * 80 rounds *
                   (635.029318 + 134.71693389) kg
secondary guns:   16 installed * 2.13369850848 t
secondary mounts: 16 installed * 1.0 t
secondary ammo:   16 installed * 150 rounds *
                   (14.06136347 + 4.250656623554688) kg
```

All six reproduce their linked ledger masses within the declared algebraic
tolerance. The 16-gun secondary installation is distinct from its 8-gun
broadside. Broadside fields are rejected as mass multipliers. The main-mount
boundary retains complete revolving mounts, rotating gunhouse armour, and
hoists above the fixed trunk; the thirteen armour models remain fixed
protection and include the fixed barbettes.

## Files in Task 7 scope

Created:

- `tools/plimsoll/holtrop.py`
- `tools/plimsoll/systems.py`
- `tools/plimsoll/tests/test_holtrop.py`
- `tools/plimsoll/tests/test_friction.py`
- `tools/plimsoll/tests/test_systems_integration.py`
- `docs/plimsoll-1.0/systems-resistance-contract.md`

Modified:

- `tools/plimsoll/resistance.py`
- `tools/plimsoll/engines.py`
- `tools/plimsoll/tests/test_resistance.py`
- `tools/plimsoll/tests/test_engines.py`
- `tools/plimsoll/tools/gen_project_cases.py`
- `tools/plimsoll/cases/projects/queen_mary_1913.project.json`
- `tools/plimsoll/tests/test_project_cases.py`
- `docs/plimsoll-1.0/case-sources.md` (addendum only)

The legacy regression in `test_calculation_integrity.py` was exercised but did
not need modification. Geometry, stability, generic-case, analytic-case,
source-case, and unrelated files were not edited by Task 7.

## Residual limits and coordinator boundary

- `analysis.resistance_for_loading` remains Task 8. Task 7 documents the input
  contract and does not add a stub.
- The current canonical cases do not declare Holtrop stern, bulb, transom,
  appendage, bow-thruster, roughness, or QPC scenario choices. Offsets and
  scalar hull values alone do not establish them. Task 8 must return
  unavailable until it receives a named sourced or estimated scenario with
  explicit absences and QPC sensitivity.
- Holtrop conformance demonstrates equation reproduction for the hypothetical
  benchmark, not Queen Mary trial accuracy or broad hull-form validity.
- The primary Gertler DTMB-806 page definitions remain unavailable through the
  bounded source audit. The tracked subset and secondary source normalization
  are disclosed; strict mode does not extend the stored domain.
- The implicit Schoenherr equation's numerical solvability is separate from
  turbulent applicability.
- Armour proposals expose legacy geometric rounding and source limitations.
  They are not evidence that the reviewed Task 3 ledger should be replaced.
- Endurance is a steady simultaneous-consumption scenario, not an engine map,
  route model, sea-margin model, or energetic interchange between fuels.
