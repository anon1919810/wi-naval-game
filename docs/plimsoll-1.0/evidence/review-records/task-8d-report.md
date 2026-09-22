# Task 8D — explicit source geometry content import report

Implementation started from released BASE
`96555848fd8640d3e1700a2aed1c6f00a6d32af0`. Only the three authorized
production/test/documentation paths were created:

- `tools/plimsoll/geometry_import.py`
- `tools/plimsoll/tests/test_geometry_import.py`
- `docs/plimsoll-1.0/geometry-import-api.md`

The module exposes
`import_geometry_content(project, content_bytes, *, format, keel_offset_m,
source, estimate)` and `GeometryImportError`. It performs no file I/O. It
strictly decodes and parses caller-supplied bytes, assembles canonical
self-contained offsets geometry, validates it through the stable public
`stability.prepare_geometry` adapter, replaces geometry only in a normalized
deep copy, and normalizes the final project.

## Design choices

The provenance trace uses a wrapper rather than merging namespaces. It records
method and version, selected format, exact raw-byte SHA-256,
`keel_offset_m`, caller `input_source`, caller `input_estimate`, payload
`source`/`sources`/`estimate`, and an explicit representation label. A prior
typed `offsets_reference` geometry is retained verbatim as
`prior_offsets_reference`; its path is never resolved or read. Geometry
`estimate` is exactly the caller's boolean.

`legacy-offsets-5` preserves the supplied `plimsoll-offsets-1` object and all
five-number rows. Preparation may generate its analysis polygons through the
existing legacy method, but the stored geometry remains labeled
`legacy_offsets_5_section_generator`. The importer supplies no deck, hull
dimension, unit conversion, origin shift, station sort, or Queen Mary value.

Strict parsing rejects duplicate keys, invalid UTF-8, malformed JSON,
non-object roots, `NaN`/`Infinity`, overflowing floats, oversized integers, and
unpaired Unicode surrogates. Public arguments reject booleans as numbers,
nonfinite or oversized datum values, empty provenance, and nonboolean estimate
state. Content and declaration failures raise `GeometryImportError(ValueError)`
with structured code/severity/path/message/blocking diagnostics. Project
validation diagnostics are preserved inside the same exception type; parser
and shared-adapter causes remain chained and shared-adapter messages are
retained.

## RED to GREEN evidence

The first dedicated run failed because `geometry_import` did not exist:

```text
python.exe -B -m unittest tools.plimsoll.tests.test_geometry_import
ModuleNotFoundError: No module named 'geometry_import'
Ran 1 test ... FAILED (errors=1)
```

After the first implementation slice, the independent polygon import passed
with exact nonzero datum, bounds, 480 m3 analytic capacity, raw-byte hash,
payload/caller provenance and input immutability:

```text
Ran 1 test in 0.001s ... OK
```

The next public-argument RED exposed two raw implementation exceptions:

```text
TypeError: unhashable type: 'list'
OverflowError: int too large to convert to float
Ran 1 test ... FAILED (errors=2)
```

Explicit format type validation and overflow-safe datum validation made the
same test green:

```text
Ran 1 test in 0.001s ... OK
```

A third RED showed that an escaped lone surrogate could enter a returned
project and later fail UTF-8 persistence:

```text
AssertionError: GeometryImportError not raised
Ran 1 test ... FAILED (failures=1)
```

Recursive Unicode-scalar validation made the same test green:

```text
Ran 1 test ... OK
```

The completed dedicated suite covers analytic polygons, legacy tables, exact
raw hashes, whitespace-only hash changes, caller and payload provenance, prior
reference retention without lookup, Chinese-path save/move/reopen, strict
parser failures, schema mismatches, explicit argument failures, shared-adapter
geometry failures, project-diagnostic preservation, immutability and existing
saved-byte preservation.

## Verification

Interpreter:

```text
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B
```

The executable reports Python `3.13.14`; commands set
`PYTHONIOENCODING=utf-8`.

Dedicated suite:

```text
python.exe -B -m unittest -v tools.plimsoll.tests.test_geometry_import
```

Result: `Ran 11 tests in 1.545s ... OK`.

Final targeted compatibility command:

```text
python.exe -B -m unittest -v tools.plimsoll.tests.test_geometry_import tools.plimsoll.tests.test_project_store tools.plimsoll.tests.test_stability_loading tools.plimsoll.tests.test_geometry_analysis
```

Result: `Ran 95 tests in 13.333s ... OK`. This is the dedicated importer plus
the directly used project-store and public geometry/stability contracts. It is
not the shared full suite.

Package import probe:

```text
python.exe -B -c "import tools.plimsoll.geometry_import as module; print(module.METHOD_VERSION)"
geometry-content-import-1
```

Direct-module imports are exercised by the dedicated tests. Package-relative
imports are exercised by the probe. Trailing-whitespace inspection was clean.
No full suite, staging or commit was performed.

The shared HEAD advanced during this independent phase from the released BASE
to `92019a7f45d8403f6c154932709d9e466a810c67`; Task 8D did not edit shared
dependencies or the unrelated untracked
`docs/plimsoll-1.0/evidence/primary-preservation-check.json` and
`tools/plimsoll/tests/test_package_imports.py`. Concurrent package-import work
also left modifications in `__init__.py`, `engines.py`, `geometric.py`, and
`offsets.py`; Task 8D did not edit them. After those changes appeared, the
dedicated importer suite was rerun read-only and passed all 11 tests in
`1.167s`.

## Frozen hashes

```text
84e2f84607c4ad10468b3e95091f47e04bff6dec88701346048a8f28a3d694e8  tools/plimsoll/geometry_import.py
9bd38fae41f8e677a9640f6ebb6a9fee010868d259ba3a2ca924d8d5344e3db3  tools/plimsoll/tests/test_geometry_import.py
93cfcd45b12145021f91881fc708d84a169c35058bebd15bb0a61c69bac2ba05  docs/plimsoll-1.0/geometry-import-api.md
```

The three Task 8D paths are frozen at `READY_FOR_INTEGRATION`.

## Independent review fix round 1 — READY_FIX

Independent review round 0 reported one Important and one Minor boundary
defect. Both are fixed in the original three owned paths at BASE
`3dd85fbcc6e3f77336aa748151b4e3aee21bca5d`.

Caller-supplied source provenance now passes through the same Unicode-scalar
validator as parsed payload content. A string source reports `$.source`; nested
object values report their full source-rooted paths; an invalid nested key
reports the containing source-object path. No replacement or normalization of
valid text occurs. The focused positive case preserves nested Chinese keys and
values exactly and serializes the returned project with strict UTF-8.

`_integer` now wraps both Python integer-conversion `ValueError` and numeric
`OverflowError` in the existing `_StrictJSONError` range path. A 5,000-digit
token therefore returns blocking `geometry_import.number_out_of_range` at
`$.content`; the importer does not query, raise or disable the interpreter's
integer conversion limit.

### Fix-round RED to GREEN evidence

Focused RED command:

```text
python.exe -B -m unittest tools.plimsoll.tests.test_geometry_import.GeometryImportTests.test_caller_source_rejects_surrogates_and_preserves_chinese_text tools.plimsoll.tests.test_geometry_import.GeometryImportTests.test_strict_parser_rejects_ambiguous_or_nonportable_json
```

Observed result: four caller-source cases failed because
`GeometryImportError` was not raised, and the 5,000-digit token escaped as raw
`ValueError` without diagnostics: `Ran 2 tests ... FAILED (failures=4,
errors=1)`.

After the two localized validation changes, the identical command returned:

```text
Ran 2 tests in 0.003s ... OK
```

Final dedicated command:

```text
python.exe -B -m unittest -v tools.plimsoll.tests.test_geometry_import
```

Result: `Ran 12 tests in 1.267s ... OK`. Per controller instruction, the
previously accepted 95-test adjacent batch and shared full suite were not
repeated because Task 8D changed no shared dependency in this fix round.

Trailing-whitespace inspection and `git diff --check` were clean for all three
owned paths. No staging, commit, full suite, interpreter-limit change, shared
module edit or unrelated-file edit was performed.

### Fix-round frozen hashes

```text
cc90c9021a7d4fea9658727fb31c97c915b001c7ff50f48ee05ae30ab6ad39ff  tools/plimsoll/geometry_import.py
b9f6f42dbf8f8aec792f9b6a807c8ba1b72eebaa10368e9fb5e7285e758be967  tools/plimsoll/tests/test_geometry_import.py
22ea512b097937a53a8ac1bb6523ec43e5f245159d3425a9b16e3898c12f81bc  docs/plimsoll-1.0/geometry-import-api.md
```

The three Task 8D paths are frozen at `READY_FIX` for controller integration
and independent rereview.
