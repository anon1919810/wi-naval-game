# Task 8D source importer — independent review round 1

Reviewed fix HEAD `c0ca074e80fb34e7dd5ac19f6e54a9f947b4e761`, base
`3dd85fbcc6e3f77336aa748151b4e3aee21bca5d`. Scope is only the three paths in
`task-8-review-3dd85fb-c0ca074.diff` and the two findings from round 0. This
reviewer did not produce the Task 8D files.

**Specification verdict: APPROVED.** The Important persistence-boundary defect
and Minor structured-error defect are both addressed. The source importer now
rejects newly supplied provenance that cannot survive strict UTF-8 persistence,
and oversized JSON integers consistently return the documented structured
import diagnostic.

**Code-quality verdict: APPROVED.** Both repairs reuse existing validation and
diagnostic paths, remain local to their input boundaries, and add focused
regressions without changing geometry construction or shared adapters. I found
no new breakage in the fix diff.

The producer recorded 12 dedicated passing tests after focused RED evidence;
the controller matched all three frozen hashes. Per the review instruction, I
did not repeat accepted tests or run a full suite because the filtered fix left
no concrete unresolved doubt requiring a new probe.

## Round-0 dispositions

### Important 1 — ADDRESSED: caller source is valid UTF-8 scalar content

`tools/plimsoll/geometry_import.py:167-176` deep-copies the accepted caller
source and passes the copy through `_validate_unicode` at the rooted
`$.source` path before it can enter the returned geometry trace. The recursive
validator covers a direct string, nested object values, nested arrays, and
object keys. It raises `GeometryImportError` with the existing blocking
`geometry_import.unicode_scalar_invalid` diagnostic rather than replacing or
normalizing text.

`tools/plimsoll/tests/test_geometry_import.py:145-172` covers a lone-surrogate
string, object value, nested value, and nested key; it verifies the expected
source-rooted paths. The positive nested Chinese object is preserved exactly
and the complete imported project encodes under strict UTF-8. The documented
contract at `docs/plimsoll-1.0/geometry-import-api.md:29-36` matches this
behavior.

### Minor 1 — ADDRESSED: conversion-limit integers stay structured

`tools/plimsoll/geometry_import.py:70-84` moves `int(token)` inside the existing
conversion guard and translates both `ValueError` and `OverflowError` into
`_StrictJSONError` with code `geometry_import.number_out_of_range`.
`_parse_content` already converts that internal error to a blocking
`GeometryImportError` at `$.content`, so the public API no longer leaks the
interpreter's integer-conversion exception.

`tools/plimsoll/tests/test_geometry_import.py:249-272` now uses a 5,000-digit
integer, exceeding the interpreter's default bounded conversion threshold, and
asserts the same structured code and path as other parser range failures. The
implementation neither queries nor changes the interpreter limit, consistent
with `docs/plimsoll-1.0/geometry-import-api.md:52-59`.

## Findings

No Critical, Important, or Minor findings in the round-1 fix.

## Scope boundary

This verdict approves the Task 8D content-import fix only. Package imports,
coordinator/CLI/export integration, schema application, and whole-core
regression remain separate phase gates.
