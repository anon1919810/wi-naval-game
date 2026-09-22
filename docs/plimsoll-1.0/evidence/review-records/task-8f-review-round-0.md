# Task 8F exports — independent review round 0

Reviewed commit `9985e8f470e27d3f8254aed6bb9942293526f2df`, base
`c0ca074e80fb34e7dd5ac19f6e54a9f947b4e761`, and exactly the three paths in
`task-8-review-c0ca074-9985e8f.diff`. This reviewer did not produce the export
implementation.

**Specification verdict: APPROVED.** The four public APIs preserve complete
already-computed analysis or generic CLI documents as deterministic finite
JSON and lossless path/type CSV. Status, stage envelopes, identities,
null/zero/false/empty/absent distinctions, nested provenance, units/datums, and
repeated diagnostics remain observable. Serialization performs no calculation.
Atomic writes validate before opening a temporary and preserve existing bytes
on every reviewed failure path.

**Code-quality verdict: APPROVED.** Validation, JSON/CSV formatting, and atomic
persistence are separated cleanly. The tree validator rejects non-JSON types,
non-string object keys, cycles, nonfinite floats, and non-UTF-8 text before a
destination is touched. The CSV walker uses unambiguous JSON-bracket paths and
retains container rows and array order. The writer owns one exact temporary
path, closes it before replacement for Windows, and keeps the primary exception
when cleanup also fails.

No Critical, Important, or Minor findings.

## Evidence assessment

The nine accepted producer tests cover deterministic full JSON roundtrip,
lossless CSV types and contexts, repeated diagnostics, literal Unicode and CSV
special characters, generic documents, invalid JSON trees, no calculator
import, atomic success, validation-before-open, injected write/fsync/replace
failures, unrelated-file preservation, and cleanup-failure exception priority.
The controller matched the three frozen hashes. The implementation and docs
agree that destination parents must already exist and that export success does
not certify calculation status.

Per the review brief, I did not repeat the accepted suite or run a full suite;
the complete filtered diff left no concrete unresolved doubt requiring a
focused probe.

## Integration boundary

This verdict approves the serializer/persistence phase only. A real
coordinator result flowing through JSON and CSV remains later joint acceptance,
along with CLI batch/sweep envelopes and their persistence reporting. The
fixture is not numerical acceptance and no whole-core completion is claimed.
