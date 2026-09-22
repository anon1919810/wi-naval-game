# Task 8F report — deterministic JSON/CSV exports

Status: **READY_FOR_INTEGRATION**

Started from authorized base `c0ca074e80fb34e7dd5ac19f6e54a9f947b4e761`.
The shared HEAD advanced independently to
`c95d01baf7391d189db604dd478e8863bce205b5` while this work was in progress;
Task 8F did not modify or stage those concurrent changes.

## Owned paths

- `tools/plimsoll/exports.py`
- `tools/plimsoll/tests/test_exports.py`
- `docs/plimsoll-1.0/export-api.md`

The report itself is the authorized scratch path. No package initializer,
coordinator, schema, CLI, numerical module, or existing case was edited.

## Public contract

- `serialize_report(result, format="json") -> str` requires schema
  `plimsoll-analysis-1` and returns deterministic JSON or generic lossless
  path/type CSV text.
- `write_report(result, path, format="json") -> None` validates and serializes
  before an owned same-directory temporary write, flush, fsync, close, and
  atomic replacement.
- The coordination-approved shared helpers
  `serialize_document(document, format="json") -> str` and
  `write_document(document, path, format="json") -> None` accept any finite
  JSON object without adding or interpreting a batch/sweep schema. The report
  API adds only its analysis-schema gate and delegates to the same serializer
  and atomic writer.

JSON sorts keys, retains the complete input tree, uses full Python JSON number
precision, rejects nonfinite values, emits literal Unicode, and ends in a
newline. CSV emits one row for every scalar and container with an unambiguous
JSON-bracket path, explicit value type and container size, nearest array-record
path, stage/status context, and repeated analysis/project/loading/request
identity. It retains null/zero/false/empty/absent distinctions, empty
containers, source/estimate/uncertainty, units/datums, and duplicate-text
diagnostics at distinct paths.

The destination parent must already exist. Failures preserve prior destination
bytes. Cleanup addresses only the exact owned temporary path, and a cleanup
failure is attached as a note without replacing the primary error.

## RED/GREEN evidence

All commands used `PYTHONIOENCODING=utf-8` and
`C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B`
(runtime Python 3.13.14).

1. JSON RED before the module existed:

   ```text
   -m unittest tools.plimsoll.tests.test_exports.ExportTests.test_json_is_deterministic_complete_and_does_not_mutate_result
   ModuleNotFoundError: No module named 'exports'
   Ran 1 test ... FAILED (errors=1)
   ```

   Minimal JSON implementation GREEN: `Ran 1 test ... OK`.

2. CSV RED before CSV support:

   ```text
   -m unittest tools.plimsoll.tests.test_exports.ExportTests.test_csv_long_form_preserves_types_context_and_literal_text
   ValueError: unsupported report format: 'csv'
   Ran 1 test ... FAILED (errors=1)
   ```

   Generic long-form walker GREEN with the JSON test: `Ran 2 tests ... OK`.

3. Atomic writer RED before the public function existed:

   ```text
   -m unittest tools.plimsoll.tests.test_exports.ExportTests.test_write_report_atomically_replaces_with_exact_serialized_bytes
   AttributeError: module 'exports' has no attribute 'write_report'
   Ran 1 test ... FAILED (errors=3)
   ```

   Success, validation-before-open, injected write/fsync/replace, and cleanup
   failure tests then passed: `Ran 4 tests ... OK`.

4. The public stdout contract was changed to Unicode text after coordination.
   Its focused RED observed `bytes is not an instance of str`; the text return
   implementation then passed.

5. The approved generic helper RED observed:

   ```text
   AttributeError: module 'exports' has no attribute 'serialize_document'
   Ran 1 test ... FAILED (errors=1)
   ```

   A second RED proved that the initial JSON encoder accepted integer keys;
   recursive JSON-tree validation was then added so only an actual JSON object
   tree is accepted.

## Final focused verification

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B -m unittest tools.plimsoll.tests.test_exports
& 'C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B -m py_compile tools/plimsoll/exports.py tools/plimsoll/tests/test_exports.py
git diff --check -- tools/plimsoll/exports.py tools/plimsoll/tests/test_exports.py docs/plimsoll-1.0/export-api.md
```

Exact focused test output:

```text
.........
----------------------------------------------------------------------
Ran 9 tests in 0.091s

OK
```

`py_compile` and `git diff --check` exited 0 with no output. A package-import
smoke test imported all four public functions from `tools.plimsoll.exports` and
serialized a generic object successfully.

No shared/full suite was run, as directed.

## Final SHA-256

```text
1c416dc36c2f49303784533064b8feceb1f37b742c8052ada4112ce2b0e74c8b  tools/plimsoll/exports.py
4b26c88700d5171b6ced342aeff58c106dd458798522daeb761330bcd0d1f87d  tools/plimsoll/tests/test_exports.py
957404df1b4f6c51163ae10e99f728d69a6ac625407191af5087914597680c6a  docs/plimsoll-1.0/export-api.md
```

## Integration boundary

Focused tests use a serializer-contract fixture and intentionally do not import
the concurrently developed analysis coordinator. Joint acceptance should pass
one real `compute_project` result through JSON and CSV after both owners freeze.
Batch/sweep schema construction and validation remain CLI ownership; the generic
document functions only serialize their supplied JSON object.
