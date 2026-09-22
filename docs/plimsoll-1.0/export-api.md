# JSON and CSV export API

`tools.plimsoll.exports` serializes an already computed result. It performs no
calculation, project normalization, file discovery, or network operation.

The public analysis-result functions are:

```python
serialize_report(result, format="json") -> str
write_report(result, path, format="json") -> None
```

`result` must be a JSON object whose schema is exactly
`plimsoll-analysis-1`. Calculation status is retained as data. A partial,
canceled, failed-stage, or model-limit result can therefore be exported
successfully; saving bytes does not change or certify its physics status.

Thin commands that construct another defined result envelope can use the
schema-neutral functions:

```python
serialize_document(document, format="json") -> str
write_document(document, path, format="json") -> None
```

These require a JSON object at the root and add no schema or batch-specific
fields. All nested values must be JSON types, object keys must be strings, and
numbers must be finite. The report functions apply their schema check and then
use the same generic implementation.

## JSON

JSON output is deterministic UTF-8 text with sorted object keys, two-space
indentation, a final newline, and Python's lossless JSON number rendering.
`NaN` and infinities are rejected. The complete input tree is retained,
including nulls, empty containers, snapshots, requests, identities, units,
datums, provenance, assumptions, validity, stage data, and diagnostics.

`serialize_report` and `serialize_document` return Unicode text for direct use
with text stdout. The write functions encode that text as UTF-8.

## CSV long form

CSV output uses the standard CSV quoting rules, UTF-8 text, a fixed header, and
one row for every scalar and container in the source tree. Dictionary members
are ordered by key and arrays retain input order. Literal string cells preserve
commas, quotes, newlines, and Chinese text; CSV quoting is the only cell escape
layer.

Each row has these columns:

| Column | Meaning |
| --- | --- |
| `path` | Unique bracket-notation path from `$`; object keys are JSON string literals and array positions are zero-based indices. |
| `parent_path` | Path of the containing object or array; empty only for the root. |
| `key` | Literal object key for a member row. |
| `index` | Decimal array index for an array-member row. |
| `value_type` | `object`, `array`, `null`, `boolean`, `integer`, `number`, or `string`. |
| `value` | Literal scalar text; strings are unchanged, booleans are `true`/`false`, and numbers use JSON rendering. Blank for nulls and containers. |
| `container_size` | Member count for objects or element count for arrays, including `0`; blank for scalars. |
| `stage` | Analysis stage for rows below a stage envelope or a top-level diagnostic record. |
| `stage_status` | Status copied from that stage envelope. |
| `record_path` | Path of the closest containing array record, including the record row itself. |
| `analysis_status` | Repeated top-level status context when it is scalar. |
| `project_id`, `condition_id` | Repeated top-level selection identity when scalar. |
| `project_fingerprint`, `input_fingerprint`, `request_fingerprint` | Repeated project, loading, and request identities when scalar. |

The row for a container is required even when it is empty. Consequently an
empty object, empty array, explicit null, zero, false, and empty string remain
distinct. An absent field has no path row. Nested source, estimate, uncertainty,
unit, datum, and diagnostic fields remain ordinary addressable rows. Equal
diagnostic messages are not coalesced because their array paths and stage
contexts remain distinct.

The long form is generic. Convenience context columns can be blank for
non-analysis documents, while every source field still appears at its lossless
path. Consumers should use the explicit `value_type` and container rows when
reconstructing data rather than inferring a type from a blank cell.

## Persistence and errors

The write functions fully validate and serialize before opening a temporary
file. The destination parent directory must already exist. They create one
owned temporary file in that directory, write UTF-8 bytes, flush and `fsync`,
close it, then atomically replace the destination. This supports Windows, where
an open temporary file cannot be replaced.

Serialization or I/O errors propagate to the caller. Any prior destination
bytes remain in place when validation, write, flush, or replacement fails. On
failure, only the exact owned temporary path is removed; unrelated files are
never scanned or deleted. If cleanup also fails, the original exception remains
primary and the cleanup error is attached as an exception note.
