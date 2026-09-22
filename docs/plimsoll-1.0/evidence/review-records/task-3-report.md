# Task 3 implementation report

Date: 2026-09-22

Status: review-fix round 1 committed from `FIX_BASE`
`80fb8d88e63ec1c64831087a85ff263d273ee461` as
`bf98a7b15515fd7c82506cf9807ad5ea533986da`; frozen for independent review.

## Delivered files

- `tools/plimsoll/tools/gen_project_cases.py`
- `tools/plimsoll/cases/projects/queen_mary_1913.project.json`
- `tools/plimsoll/cases/projects/generic_steamer.project.json`
- `tools/plimsoll/cases/projects/analytic_box.project.json`
- `tools/plimsoll/tests/test_project_cases.py`
- `docs/plimsoll-1.0/case-sources.md`

This report is the only additional Task 3 coordination file. No legacy case,
core calculator, controller document, or Task 5 file was edited.

## Implementation

The generator creates three deterministic, self-contained
`plimsoll-project-1` payloads. It reads tracked legacy Queen Mary source cases
and the tracked object manifest only while generating that project. Saved
projects contain materialized `plimsoll-section-polygons-1` stations and need
no repository path, Blender, network, timestamp or Queen Mary-specific core
constant for consumption.

The Queen Mary fixture has all nine required weight groups and 31 positive-mass
items. Its fixed/base ledger is 26,021.630342730772 t. The normal and deep
engineering scenarios resolve to 27,851.62934079477 t and
31,926.26200617077 t. The raw 26,770 and 31,650 comparison values retain their
unresolved "tons" unit and are not canonical reference masses. There is no
residual or margin item.

All Queen Mary inferred items carry a formula, citation, dependency list,
boundary statement, four-axis uncertainty, and `estimate: true`. The four
revolving mounts own rotating turret armour; the thirteen fixed armour proxies
own unique tokens and contain no rotating-turret token. The main and secondary
broadside counts are both eight, while installed secondary guns remain sixteen.
Systems reference the existing weight-item IDs and add no calculated mass.

Normal consumables are base item values. The deep scenario overrides mass and
all coordinates with scenario provenance; its metadata states that the loading
contract clears base uncertainty and that scenario-specific bounds are not yet
supported. Predicted scenario totals are allowed to differ from source
comparisons.

The generic steamer materializes parameter-derived reference geometry. The
analytic box uses three explicit rectangular stations and integrates to exactly
800 m3 at 4 m draught. Optional unarmed/inapplicable categories are empty with
an explicit absence reason rather than a fake zero item.

All projects include flat compartment and opening fixtures with complete
coordinates, permeability and provenance. Each intact damage preset explicitly
sets initial compartment water volumes to known zero. Queen Mary proxies state
that they are not surveyed subdivision or opening data.

## RED/GREEN evidence

Initial RED:

```text
python -B -m unittest tools.plimsoll.tests.test_project_cases -v
Ran 6 tests
FAILED (failures=1, errors=7)
```

The expected missing-feature evidence was the absent generator and three absent
project files. A second RED cycle added explicit intact damage presets; the
focused test failed because `damage_presets` was absent, then passed after the
generator added explicit zero initial volumes.

Fresh targeted GREEN command:

```text
$env:PYTHONIOENCODING='utf-8'
python -B -m unittest tools.plimsoll.tests.test_project_cases tools.plimsoll.tests.test_project_io tools.plimsoll.tests.test_loading -v
Ran 43 tests in 2.059s
OK
```

The project-case tests execute the real normalization/loading pipeline for
every condition, regenerate into two temporary directories and compare bytes
with each other and the committed fixtures, verify independent unit/formula
anchors, integrate serialized geometry directly, and check fixture
compartment/opening contracts.

Controller-run shared full-suite evidence after Tasks 3 and 5 were frozen,
before review-fix round 1:

```text
Ran 394 tests in 116.530s
OK
PLIMSOLL_REGRESSION run=394 fail=0
exit 0
```

## Direct checks and self-review

- Queen Mary materialized geometry at its model waterline integrates to
  30,943.880252213905 m3 and declares `keel_offset_m = -9.9`.
- Generic steamer volume at 5.5 m is 4,592.398041540149 m3 versus the analytic
  4,633.2 m3 target, a 0.881% discretization difference within the declared
  <1% fixture criterion.
- Analytic box volume is exactly 800.0 m3 with zero transverse and longitudinal
  buoyancy-centre coordinates.
- Every generated loading is complete in mass and all three CG axes, with no
  blocking diagnostics or ownership overlap.
- Proposed mutation/sensitivity coverage (reasoned, not executed as a mutation
  harness): changing secondary `broadside_guns` from 8 to 16 maps to the
  independent ledger assertion; duplicating an armour ownership token maps to
  loading completeness; changing a box section width maps to the 800 m3
  analytic anchor; omitting estimated-item source/bounds maps to the provenance
  test; timestamps or key-order drift maps to the two-directory byte
  comparison. No performed mutation result is claimed.
- `git status --short` was reviewed. Concurrent Task 5 files and controller
  documents remain outside Task 3 ownership and were not staged.

## Remaining limits

The Queen Mary case is suitable as an auditable engineering fixture, not as a
historically validated weight statement. The unresolved primary evidence and
boundary questions are enumerated in `docs/plimsoll-1.0/case-sources.md`. The
generic reference hull is a parameter-derived construction and is not an
independent validation source. Full loaded-equilibrium behavior belongs to
Task 4; flooding calculation belongs to later tasks.

Initial Task 3 commit: `ccabee097bd25a5465bc0758dc101ec102cca7d9`

## Review-fix round 1: exact reserve feed water

Independent review found that the normal and deep reserve-feed-water literals
had been rounded independently from their declared formulas, violating the
binding `rel_tol=1e-10` for exact algebraic/unit anchors. No coefficient or
historical displacement input changed.

The focused RED added direct assertions for both formulas and replaced literal
aggregate expectations with sums of independently calculated components:

```text
python -B -m unittest tools.plimsoll.tests.test_project_cases.ProjectCaseTests.test_queen_mary_ledger_uses_independent_formulas_without_residual_mass -v
Ran 1 test in 0.550s
FAILED (failures=1)
```

The failure occurred at the new normal `0.015 * 27000 * 1.0160469088`
assertion. The generator now derives normal and deep masses directly as
411.498998064 t and 685.83166344 t. The focused GREEN result was:

```text
Ran 1 test in 0.561s
OK
```

Fresh focused plus relevant contract verification:

```text
python -B -m unittest tools.plimsoll.tests.test_project_cases tools.plimsoll.tests.test_project_io tools.plimsoll.tests.test_loading -v
Ran 43 tests in 2.042s
OK
```

The corrected scenario totals are 27,851.62934079477 t normal and
31,926.26200617077 t deep. Regeneration changed only the Queen Mary project
among the three generated fixture files. Its hashes changed as follows:

| Identity | Before | After |
| --- | --- | --- |
| File SHA-256 | `53f6d82ca8d2f3a3b606f4fb8c20cc374c1a074464a5e72000c53fa689f1cdfe` | `c32994d9cca5e5303db5a204b7bf7b8b28fb7b73804f2cd0aae623e6ba14622c` |
| Canonical input fingerprint | `5625703ae8767171a59dafc3bcbc5e0a89eddf8bf11e94c95fbb1045f62c2e31` | `558d8b18b566bc9afc41684f0b1f5f20459071027ebfa1b2662e1b5a1f4dfdaf` |

Review-fix commit: `bf98a7b15515fd7c82506cf9807ad5ea533986da`
