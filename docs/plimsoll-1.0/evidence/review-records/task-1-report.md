# Task 1 report: canonical project, units, diagnostics and migration

Status: DONE

Commit: `5e06a01` (`feat(plimsoll): add canonical project contract`)

## Implementation

- Added `units.convert(value, from_unit, to_unit)` for the required mass,
  length, speed, power and angle units. It uses the binding precise constants,
  rejects booleans/nonfinite values/unknown units and rejects cross-dimension
  conversions.
- Added canonical `plimsoll-project-1` project creation, validation and
  normalization. Defaults use the required units and coordinate system.
  Validation returns structured `{code, severity, path, message, blocking}`
  diagnostics; malformed input raises `ProjectValidationError` from
  normalization with the full list retained.
- Preserved the distinction between `null` and explicit zero. Item, hull,
  geometry and loading-reference unknowns are diagnosed without values being
  invented. Missing item/geometry provenance is diagnosed.
- Enforced nonnegative mass/KG, signed x/y, finite reals, global item-ID
  uniqueness, group/loading-ID uniqueness and known-item-only loading
  overrides. Only the four weight/CG fields may be overridden.
- Defined and validated optional uncertainty ranges
  `{mass_t:[lo,hi], x_m:[lo,hi], y_m:[lo,hi], kg_m:[lo,hi]}`. Bounds are
  finite, ordered, dimension-valid and inclusive of a known nominal.
- Defined and validated `includes` as unique string ownership tokens. They add
  no mass; duplicate active ownership remains a loading-resolution check.
- Added deterministic legacy migration for `plimsoll-ship-1` plus optional
  `plimsoll-weights-1`: exact legacy payload retention, hull copying, explicit
  declared mass-unit conversion, estimated status for unconfirmed tonnes,
  normal/deep references without a residual plug, source-preserving weight
  mapping with missing x/y left null, and unresolved typed offsets references.
- Added stable SHA-256 fingerprints from sorted canonical JSON. Result/cache
  fields and a stored fingerprint are rejected as non-input fields.
- Documented the full canonical schema, unit definitions, geometry, weights,
  uncertainty, ownership tags, loading overrides, diagnostics, migration and
  fingerprint semantics.

## Owned files

- `docs/plimsoll-1.0/data-contract.md`
- `tools/plimsoll/project_io.py`
- `tools/plimsoll/tests/test_project_io.py`
- `tools/plimsoll/units.py`

Controller-owned concurrent documentation and evidence changes were not staged
or committed.

## RED / GREEN evidence

Interpreter for every Python command:
`C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe`, with
`-B` and `PYTHONIOENCODING=utf-8`.

Initial RED:

```text
python -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
ImportError: Failed to import test module: test_project_io
ModuleNotFoundError: No module named 'project_io'
Ran 1 test
FAILED (errors=1)
```

During GREEN, the first implementation run passed 15/16. The only failure was
the test's decimal-place assertion rejecting a `1.8189894035458565e-12`
round-trip difference at 15000, tighter than the binding `rel_tol=1e-10` /
`abs_tol=1e-10`. The test was corrected to the declared tolerance.

Self-review RED for two uncovered contract behaviors:

```text
python -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
FAIL: test_explicit_geometry_requires_payload_or_reference_parameters
FAIL: test_unknown_hull_and_loading_values_have_diagnostics
Ran 18 tests
FAILED (failures=2)
```

Focused GREEN after the minimal production changes:

```text
python -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
..................
Ran 18 tests in 0.004s
OK
```

Real repository migration probe:

```text
plimsoll-project-1 4 13
errors= 0 warnings= 30
3745a4edd6bc6d346954d8f105b8f792c85d5f9e7d4298625cb4368e5c9f72bd
```

This used `queen_mary_1913.json` and `queen_mary_1913_weights.json`; warnings
retain the missing x/y, unknown keel offset and incomplete-group facts.

Full regression:

```text
python -B tools/plimsoll/run_all_tests.py
Ran 343 tests in 120.323s
OK
PLIMSOLL_REGRESSION run=343 fail=0
```

Whitespace and staged-scope check:

```text
git -c core.whitespace=cr-at-eol diff --cached --check
<no output; exit 0>

git diff --cached --name-only
docs/plimsoll-1.0/data-contract.md
tools/plimsoll/project_io.py
tools/plimsoll/tests/test_project_io.py
tools/plimsoll/units.py
```

## Self-review and concerns

The implementation contains no ship-specific constants, GUI/network imports,
repository scanning, hidden calibration or residual-mass inference. Public
inputs remain JSON-native and legacy calculator modules were not changed.

No blocking concern or unresolved contract ambiguity remains. Loading-time
duplicate ownership checks are deliberately deferred to Task 2, as specified;
Task 1 validates only the `includes` token shape.

## Review round 1 fixes

Status: DONE

Fix base: `e5f2ee0`

Fix commit: `b9c0a22` (`fix(plimsoll): tighten project validation`)

Implemented all three Important findings and controller rulings:

- Non-string hull keys now remain structured `json.key_invalid` diagnostics;
  hull-specific validation skips the already-reported malformed key instead of
  calling string methods and raising `AttributeError`.
- A missing canonical weight-item `estimate` now normalizes to `null`, produces
  `estimate.unknown`, and fingerprints identically to explicit `null` but
  differently from explicitly confirmed `false`. Declared booleans and the
  conservative legacy-migration default remain unchanged.
- Geometry validation now supports only `offsets_reference`, `parameters` and
  `offsets`, requires the matching non-empty structural payload, rejects wrong
  payload types, empty payloads, mismatched payload fields and unsupported
  kinds, and performs no filesystem scan or hull-physics validation.
- Updated the public data contract with the nullable estimate semantics and
  kind-specific geometry payload shapes.

Review-fix RED:

```text
python -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
ERROR: test_malformed_hull_key_returns_diagnostic_instead_of_crashing
AttributeError: 'int' object has no attribute 'endswith'
FAIL: test_missing_or_null_estimate_is_unknown_not_confirmed_false
AssertionError: False is not None
FAIL: test_geometry_kinds_require_matching_nonempty_structural_payloads
  six failing subtests: empty reference, empty path, empty parameters, empty
  stations, mismatched payload and unsupported kind
Ran 21 tests in 0.014s
FAILED (failures=7, errors=1)
```

Review-fix GREEN, repeated after documentation alignment:

```text
python -B -m unittest discover -s tools/plimsoll/tests -p test_project_io.py
.....................
Ran 21 tests in 0.006s
OK
```

Scoped verification:

```text
git -c core.whitespace=cr-at-eol diff --cached --check
<no output; exit 0>

git diff --cached --name-only
docs/plimsoll-1.0/data-contract.md
tools/plimsoll/project_io.py
tools/plimsoll/tests/test_project_io.py
```

No broader regression was repeated because the fix changed only the new
standalone Task 1 module, its focused tests and its contract documentation, as
directed by the controller. No new shared-code concern was discovered.
