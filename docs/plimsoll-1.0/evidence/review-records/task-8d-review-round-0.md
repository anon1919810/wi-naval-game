# Task 8D source importer — independent review round 0

Reviewed HEAD `3dd85fbcc6e3f77336aa748151b4e3aee21bca5d`, base
`96555848fd8640d3e1700a2aed1c6f00a6d32af0`. Read the complete handoff brief,
producer report, three-path filtered diff and shared adapter/normalizer context.
Scope is geometry_import.py, tests/test_geometry_import.py and
geometry-import-api.md only. This reviewer did not produce these files.

**Specification verdict: NEEDS CHANGES.** The main import path meets the pure
content, immutable input, explicit format/datum, provenance and adapter reuse
contract. One Important persistence-boundary gap and one Minor structured-error
gap remain. No Critical finding.

**Code-quality verdict: NEEDS CHANGES.** The implementation is focused and keeps
parsing, declarations, provenance and shared geometry preparation separate.
The two gaps are localized validation omissions; they do not require a new
geometry loader, kernel change or schema redesign.

## Important 1 — caller source can make a successful import unsavable as UTF-8

`tools/plimsoll/geometry_import.py:167-174` checks only that caller source is a
nonblank string or nonempty object and then copies it. Unicode scalar validation
at lines 92-107 and 148 is applied only to parsed content. The supplied source is
inserted into the returned geometry trace at line 230. Final normalization at
line 261 does not reject unpaired surrogate strings.

Concrete public calls with otherwise valid analytic box content and either
`source="\ud800"` or `source={"title": "\ud800"}` both returned an imported
project. Encoding that project with the same UTF-8 serialization policy as
project_store raised UnicodeEncodeError. Thus import reports success but the
new caller-supplied provenance prevents the promised save/relocate/reopen flow.
This is distinct from preserving unrelated pre-existing project data: the
unsavable text is newly accepted by this importer.

Validate Unicode scalars in the caller source, including nested object keys and
values, before returning the imported project. Use the existing structured
GeometryImportError diagnostics with a source-rooted path. Add string/object
regressions and retain the positive Chinese source roundtrip. No silent text
replacement is appropriate because source identity must be preserved.

## Minor 1 — integer conversion limit escapes structured import diagnostics

`tools/plimsoll/geometry_import.py:70-71` calls int(token) outside its try block.
An integer token with 5,000 digits raises Python's integer-conversion-limit
ValueError before math.isfinite is reached. `_parse_content` at lines 131-142
catches _StrictJSONError, JSONDecodeError and RecursionError, but not this
conversion failure. A focused public call produced raw ValueError with no
diagnostics attribute.

The content is rejected, so this does not produce incorrect geometry. It does
break the documented structured-error contract used by the thin CLI, and the
producer's 400-digit case does not exercise the interpreter's 4,300-digit gate.
Wrap the int conversion failure into the existing structured number/range
failure and add a token longer than the interpreter limit to the parser test.
Do not raise or disable the interpreter limit.

## Satisfied requirements and evidence

- No file I/O or reference lookup exists in the importer. Only caller bytes
  determine content. Prior typed offsets_reference geometry is copied into
  provenance, without resolving or reading its path.
- Exact UTF-8 bytes determine raw SHA-256; explicit format/schema agreement is
  enforced. Parsed payload remains under geometry.offsets, and source namespaces
  remain separate. Caller estimate is not promoted to historical validity.
- The legacy representation keeps all rows and explicit positive deck and is
  labeled as the legacy section generator. Geometry preparation delegates to
  stability.prepare_geometry. No hidden station sorting, hull/deck defaults,
  origin shift, dimension rewrite or new numerical solver is introduced.
- The project is normalized into an owned copy before geometry replacement and
  again afterward. Input project/content remain untouched. Other project data
  is preserved apart from documented defaults. Failed imports perform no save.
- Tests include the independent 480 m3 box with nonzero datum, legacy row
  preservation, content-hash sensitivity, Chinese save/move/reopen, invalid
  geometry, duplicate JSON keys and preservation of canonical diagnostics.
- Ordinary package/direct imports follow the authorized convention. Separate
  package-import work is outside this review.

Accepted producer evidence was not rerun: 11 dedicated tests, 95 directly
related tests, and the later 11-test check after package work appeared. Scoped
`git diff --check 9655584 3dd85fb -- tools/plimsoll/geometry_import.py tools/plimsoll/tests/test_geometry_import.py docs/plimsoll-1.0/geometry-import-api.md`
passed.

## Focused read-only probe

One stdin Python probe used the declared executable with `-B` and
`PYTHONIOENCODING=utf-8`. It created an in-memory canonical draft and three
polygon stations at x=-10,0,10 with section corners (-3,7),(3,7),(3,11),(-3,11).
It then called the public importer with source string/object lone-surrogate
cases and a separate 5,000-digit JSON integer token. It wrote no files and did
not rerun accepted tests.

```text
source_string_surrogate IMPORT_ACCEPTED
serialization_error UnicodeEncodeError
source_object_surrogate IMPORT_ACCEPTED
serialization_error UnicodeEncodeError
integer_5000_digits ValueError diagnostics False
```

No production/index changes, full-suite execution or subagents were used.
Coordinator, CLI/export, schema fixes and complete core acceptance remain
separate gates; no additional finding is assigned to those out-of-scope phases.
