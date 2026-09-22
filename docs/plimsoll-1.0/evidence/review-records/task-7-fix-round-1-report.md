# Task 7 fix round 1 report

Date: 2026-09-22

Status: `READY_FIX`. Production, tests, generated case, and documentation are
frozen for coordinated regression and review. No fix commit or remote push was
made. The review base was `df9e835`; the shared branch advanced through disjoint
task commits during implementation and was at
`c71ee1c6c88663f13822bcc4416c615803375825` when final hashes were recorded.

## Review findings and fixes

### Present systems cannot collapse missing ownership to zero

RED: the focused review regression failed because `status: present` with
`weight_item_ids: []` returned `complete=True`, `ledger_mass_t=0.0`, and no
diagnostic.

GREEN: a present row now requires at least one selected-ledger link. An empty
list emits blocking `systems.present_without_weight_items`, leaves the row mass
null, leaves the linked total null, and makes the summary incomplete. An actual
absence still uses `status: absent` plus a reason; a real zero-mass present item
can remain known zero by linking an explicit zero-mass ledger row. Ledger mass
authority and canonical totals are unchanged.

### Physical mass proposals require validated provenance

RED: two focused tests failed because models with missing/empty source,
missing/non-boolean estimate status, or incomplete estimated-input provenance
still calculated and could propose ledger replacements.

GREEN: every physical model now requires a non-empty string or structured
source and a boolean estimate flag before calculation. Estimated models require
an `input_provenance` entry for every formula input; every entry has a non-empty
source and boolean estimate status. Missing or malformed metadata raises a
validation error before any proposal is produced.

The Queen Mary generator and committed canonical case now add per-input
provenance to all six gun, mount, and ammunition models. This changes metadata
only: the accepted item masses, count boundaries, formula values, thirteen
rounded-armour proposals, and normal-loading total
`27851.62934079477 t` remain unchanged. Generator determinism tests pass.

### Strict Taylor uses explicit source headings and declared precision

RED: two focused tests proved that strict mode accepted a table without
`source_axes` by reconstructing headings and that a caller-supplied node mismatch
of `2e-10` passed the former `5e-10` adapter tolerance.

The first literal `1e-10` comparison against the tracked compatibility axis
also exposed an approved-contract precision conflict: its nine-decimal stored
nodes differ from exact reciprocal cubes by up to `4.072126e-10`. The
coordinator ruled that the raw compatibility axis must remain unchanged and
that strict source headings must not be reconstructed from it.

GREEN under that ruling:

- strict mode always requires explicit
  `source_axes.l_over_volume_cuberoot` and never reconstructs it;
- generic mappings without an audited rounding declaration validate each
  heading/reciprocal-cube association at the fixed `1e-10` algebraic tolerance;
- the audited tracked adapter declares exact headings by index and serializes
  `source_axis_mapping` with policy
  `rounded_reciprocal_cube_9_decimal_places`;
- the retained compatibility coordinates must equal
  `round(1 / heading**3, 9)` with only `1e-15` floating-representation
  tolerance;
- direct strict results and strict speed-curve rows retain the serialized
  mapping and source note;
- raw Taylor cells and the rounded compatibility axis are unchanged, and the
  named legacy interpolation remains unchanged.

The tracked positive mapping, a missing-source-axis case, a falsely associated
generic axis, and the `2e-10` tolerance mutation are all covered. The authorized
clarification in `taylor-benchmark-design.md` distinguishes the exact
reciprocal-cube `1e-10` identity from nine-decimal compatibility storage without
changing cell tolerances.

### Holtrop diagnostics identify input locations

RED: a non-finite `speed_kn` produced diagnostic path `$` instead of
`$.speed_kn`.

GREEN: top-level numeric validation defaults to `$.<field>`. Nested appendage
and bow-thruster numbers pass their explicit paths; the regression asserts
`$.speed_kn` and `$.appendages[0].area_m2`. Invalid appendage arrays and rows
also carry their container/index paths. Numerical-domain errors remain
structured and blocking.

## Targeted verification

The required interpreter was used with `-B` and
`PYTHONIOENCODING=utf-8`:

```text
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe
actual runtime: Python 3.13.14
```

Final targeted command covered Holtrop, both friction methods, Taylor,
engines/endurance, systems integration, canonical project generation, and the
selected legacy Reynolds-warning regression:

```text
Ran 121 tests in 2.781s — OK
```

The exact test modules were `test_holtrop`, `test_friction`,
`test_resistance`, `test_engines`, `test_systems_integration`,
`test_project_cases`, and
`CalculationIntegrity.test_reynolds_warning_survives_curve_and_identifies_speed`.
The scoped `git diff --check` passed.

The earlier 482-test evidence predates this review-fix working tree. It is
historical evidence for the original Task 7 commit and is not claimed as a
fresh pass for round 1. Per instruction, no full suite was run here.

## Frozen changed paths and SHA-256

```text
docs/plimsoll-1.0/case-sources.md c7a99bc144c852ebef92661841fa6fce65321b11e1419ee41a314ee3d780c04e
docs/plimsoll-1.0/systems-resistance-contract.md b0f8a61eafa48df6b8a145566c20b2c55061955ece89a123045a549f08b8888a
docs/plimsoll-1.0/taylor-benchmark-design.md 7a98103c1611edaea7d18edba91c3b2735813db131260b6b9257ee1c8a5ba1c4
tools/plimsoll/cases/projects/queen_mary_1913.project.json 49b1dec04ed2fedad1cca7115fda73f8b6deb48decd898ce647ba80509c65132
tools/plimsoll/holtrop.py a0aaaa61b8b47b6231bae314b488c8d88d44dc471f80d7df0322e2694acd66c3
tools/plimsoll/resistance.py 2831c57861123cd23b8eae8762b2ff40e4393d884fad4552aba90a64bfcb4cea
tools/plimsoll/systems.py 768ba04e89a1d7c111c99bb70bcee0dfdc03787be016695b7a3130b38a8b16f2
tools/plimsoll/tests/test_holtrop.py 5f7f443a582b1ffd4786c0b53f0a9606ecc5a000816b73419968489f9a8a06e7
tools/plimsoll/tests/test_project_cases.py 8f37ceca6b694aa4f523e2305a0487660ce38d3ae3e44bee2014acb6483be7ab
tools/plimsoll/tests/test_resistance.py c80414631ae7c3e89d49cb2386032bcecceee080c937dacd24432a8873674686
tools/plimsoll/tests/test_systems_integration.py 4e3baebf456875873d452dc550c8a535555065ab8a3c512ce6e28c9433e5a15a
tools/plimsoll/tools/gen_project_cases.py 2ccf3d08ca66b4fb27ed123bc95229bd590f0f1ef1631fc50c5485f049a4022e
```

No unresolved conflict with the approved specification remains after the Taylor
precision ruling. Task 8 coordinator/persistence and Task 6 flooding work remain
outside this fix scope.

## Exact targeted test invocation

The command ran from the repository worktree shown below. No external
`PYTHONPATH` was set: each listed test module performs its existing import-path
setup by inserting `tools/plimsoll` into `sys.path` before importing the modules
under test.

```powershell
Set-Location 'C:\Users\杨睿\Documents\Codex\2026-09-17\shi\work\plimsoll-1.0'
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B -m unittest tools.plimsoll.tests.test_holtrop tools.plimsoll.tests.test_friction tools.plimsoll.tests.test_resistance tools.plimsoll.tests.test_engines tools.plimsoll.tests.test_systems_integration tools.plimsoll.tests.test_project_cases tools.plimsoll.tests.test_calculation_integrity.CalculationIntegrity.test_reynolds_warning_survives_curve_and_identifies_speed
```
