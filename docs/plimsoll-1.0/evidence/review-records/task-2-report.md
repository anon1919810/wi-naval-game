# Task 2 report: three-axis weight and loading synthesis

Status: implemented and verified on `feature/plimsoll-1.0` from reviewed Task 1
HEAD `08151f1` (`5e06a01` plus review fix `b9c0a22`).

## Delivered files

- `tools/plimsoll/loading.py`: canonical `resolve_loading(project,
  condition_id)` implementation.
- `tools/plimsoll/tests/test_loading.py`: 15 independent loading tests.
- `docs/plimsoll-1.0/loading-contract.md`: output, ownership, coverage,
  provenance, identity, and interval semantics.
- `weights.py` was intentionally unchanged; the legacy API remains compatible.

## Public output

`resolve_loading` returns `schema`, project and condition IDs, canonical units
and coordinates, `project_fingerprint`, condition-sensitive
`input_fingerprint`, effective items, group rows, aggregate `values`, coverage,
provenance, uncertainty, axis completeness, mass/CG completeness, and structured
diagnostics.

`values` distinguishes known partials from complete results:

- `known_mass_t` and nullable `total_mass_t`;
- `known_moments_t_m` and independently nullable x/y/z `moments_t_m`;
- independently available `lcg_m`, `tcg_m`, and `kg_m`.

Effective items preserve source and tri-state estimate provenance, identify the
owning group and overridden fields, and retain explicit zero/null semantics.
Required empty groups, unknown masses, incomplete positive-mass coordinates,
zero-total designs, and exact ownership-token collisions receive structured
loading diagnostics. Reference displacement only reports ratio, percent, and
signed unallocated mass; it is never used as a residual-mass plug.

Uncertainty uses conservative independent interval arithmetic with signed
position endpoint products and a strictly positive total-mass denominator.
Nominal fallback fields are disclosed. Estimated items without bounds are
listed and diagnosed. An override clears the inherited interval for that field
and requests updated uncertainty metadata.

## TDD evidence

Interpreter for every test command:
`C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B`, with
`PYTHONIOENCODING=utf-8`.

1. Initial RED:
   `python -B -m unittest tools/plimsoll/tests/test_loading.py -v`
   failed at import with `ModuleNotFoundError: No module named 'loading'`.
   The first tests fixed the 400 t / (5,1,7) and override 200 t / (0,0,6)
   anchors, all three moments, immutability, and condition-derived identity.
2. First GREEN: the same command ran 2 tests, `OK`.
3. Completeness/ownership RED: the expanded 10-test command reported
   `FAILED (failures=1, errors=6)` for missing null/axis/required-group,
   ownership, and coverage behavior.
4. Completeness/ownership GREEN: the same 10 tests ran `OK`.
5. Interval/provenance RED: the expanded 15-test command reported
   `FAILED (failures=1, errors=4)` for missing uncertainty/provenance output and
   inherited override bounds.
6. Final focused GREEN:
   `python -B -m unittest tools/plimsoll/tests/test_loading.py -v`
   ran 15 tests in 0.014 s, `OK`.
7. Legacy compatibility:
   `python -B -m unittest tools/plimsoll/tests/test_weights.py -v`
   ran 15 tests in 0.002 s, `OK`.
8. Full regression:
   `python -B tools/plimsoll/run_all_tests.py`
   reported `Ran 361 tests in 114.970s`, `OK`,
   `PLIMSOLL_REGRESSION run=361 fail=0`, exit 0. The command was re-invoked
   once because the first tool session returned only progress dots after its
   30-second capture window and did not return the final count or exit status.
9. `git diff --check -- tools/plimsoll/loading.py
   tools/plimsoll/tests/test_loading.py docs/plimsoll-1.0/loading-contract.md`
   exited 0 with no output.

## Commit and concerns

Commit: `99d58b5e0053472963263ec7e8afe996fd65c8b6`
(`feat: resolve three-axis loading states`). The ignored coordination report is
not part of that commit.

Engineering intervals intentionally discard correlation and may overbound;
their nominal fallback dependencies are explicit. Ownership checks match exact
IDs/tokens only, so synonyms and untagged conceptual overlaps remain a data
governance responsibility. No Queen Mary constants, GUI/network dependency,
or residual-mass calibration was added.
