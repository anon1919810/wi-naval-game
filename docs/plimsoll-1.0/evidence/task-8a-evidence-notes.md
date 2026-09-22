# Task 8A retained evidence

The geometry JSON and two Python reproduction scripts in this directory are
byte-for-byte copies of the producer's scratch artifacts. The numerical JSON
was generated for the initial phase (`1a482a1`), before the validation and
persistence cleanup fix in `b2ffe83`. It is historical evidence for the named
implementation, not a claim that a new full regression was run after the fix.

- `task-8-geometry-evidence.json`: box/triangle/inclined-plane anchors,
  41×48 to 81×96 refinement, six isolated in-memory mutation results.
- `task-8-geometry-evidence.py`: the exact generating script; run from any cwd
  using the documented development interpreter. It resolves the repository from
  its own location. A rerun replaces its adjacent JSON, so preserve the committed
  historical record when comparing a later implementation.
- `task-8-persistence-mutations.py`: four isolated persistence mutations.
- `review-records/task-8a-phase-report.md`: snapshot of the producer report at
  phase completion, including literal commands, timings and frozen hashes for
  the 97 post-fix targeted tests. The continuing Task 8B report is separate.
- `review-records/task-8a-review-round-0.md` and `...-round-1.md`: independent
  specification and quality verdicts; the remaining minor assumption-label
  issue is recorded for subsequent integration/final review.

These scripts do not change production source. They intentionally run selected
test assertions against in-memory source mutations; they are not substitutes for
the core end-to-end acceptance or the final source-frozen full regression.
