# Task 8C thin CLI — frozen checkpoint handoff

Date: 2026-09-22  
Authorized base: `7a673b97279866d9a052efadaf0dbf46de58a02b`  
Shared HEAD at freeze: `4bec0818b5fccda5dc060e18425bc9762dc13a19`  
Status: **CHECKPOINT_FROZEN — NOT READY_FOR_INTEGRATION**

The user requested a prompt project/status handoff before the full Task 8C
acceptance could be completed. This report records a coherent tested checkpoint;
it does not claim the CLI phase, Task 8, or the current calculation core is
complete.

## Owned paths at this checkpoint

- `tools/plimsoll/app.py`
- `tools/plimsoll/__main__.py`
- `tools/plimsoll/tests/test_core_cli.py`

`docs/plimsoll-1.0/cli.md` has not been created because the public command set is
not yet complete. No legacy CLI, package initializer, coordinator, exporter,
schema, kernel, case, or other owner's file was edited.

## Implemented and tested

- `python -m plimsoll --help` dispatches through `app.main` from an unrelated
  Chinese directory with only the package parent on `PYTHONPATH`.
- The `analyze` path loads an explicit project, reads an optional exact options
  object, calls `analysis.compute_project` once, validates JSON and optional CSV
  from that same result through the accepted exporter APIs, and returns 0 only
  for native top-level `completed` status.
- Explicit JSON reads use strict UTF-8, duplicate-key and nonfinite-number
  rejection. Result destinations cannot alias explicit inputs or each other.
- Early JSON/alias failures use one `plimsoll-cli-error-1` object on stderr with
  empty stdout and exit 2.
- The batch path validates a strict `plimsoll-batch-1` manifest, resolves project
  paths relative to the manifest, keeps input order, uses ordinal filenames,
  continues after project/calculation failures, records native identities and
  structured diagnostics, and writes a generic exporter-produced summary.
- A real loading-only batch exercised the current coordinator with a valid case,
  malformed project, missing condition, unsafe-looking ID, and a later valid
  case. The three valid calculations were saved as ordinals 0001, 0004 and 0005;
  the ID never controlled a path.
- Sweep manifest validation rejects duplicate/unknown axes, booleans,
  nonpositive values, more than 201 speeds, more than 21 QPC samples, and grids
  above 1000 points before creating the output directory.

The analyze exactly-once JSON+CSV test is the one authorized focused coordinator
mock. Batch verification uses the real current coordinator rather than a stub.

## TDD and focused verification

All commands ran from
`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0` with
`PYTHONIOENCODING=utf-8`, package-parent `PYTHONPATH=tools`, and:

```text
C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe -B
```

The executable reports Python `3.13.14` (Jun 11 2026, MSC v.1944, AMD64).

RED evidence, in implementation order:

1. Entry point: one failure because `plimsoll.__main__` did not exist.
2. Analyze once/two formats: one assertion failure (`-1 != 0`) while the command
   handler was intentionally unimplemented.
3. Structured JSON and alias guard: two failures because raw exceptions returned
   exit 1 instead of structured exit 2.
4. Batch: one failure because the unimplemented command emitted a traceback.
5. Sweep validation: seven subtest failures because the unimplemented command
   emitted a traceback and exit 1.

Each focused RED became green before the next behavior was started. Final
checkpoint command:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH=(Resolve-Path 'tools').Path
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_core_cli.py -v
```

Result:

```text
Ran 6 tests in 2.774s
OK
```

`git diff --check` passed for the three owned paths. No full suite, staging, or
commit was performed. The previously accepted 140 Task 8E package tests were not
repeated.

## Required work still unfinished

- No real single-case subprocess acceptance yet exists for analytic box,
  generic steamer, or Queen Mary normal/deep results, deterministic fingerprints,
  changed physical input identity, reference-geometry unavailability, or native
  partial/model-limit exit 1.
- The sweep success path exists as work in progress but has not passed the
  required real 3x2 speed/QPC integration, deterministic identity/provenance,
  continuation, JSON summary, or optional CSV acceptance. It must not be treated
  as accepted behavior.
- `import-geometry` is present only in the parser. It has no handler or accepted
  tests for either format, explicit overwrite, or old-byte preservation.
- Argparse usage failures still use argparse text rather than the required
  structured error envelope. Analyze write/serialization failures are not yet
  translated into the documented post-calculation structured failure, and
  batch/sweep second-output failure behavior needs dedicated acceptance.
- Batch/sweep malformed-key coverage, optional summary CSV, output-alias cases,
  and deterministic reruns remain incomplete.
- The CLI documentation and final real-dependency checkpoint remain unwritten.
- Coordinator code and typed canonical resistance/endurance scenario data were
  still being finalized concurrently. Final CLI acceptance must use their frozen
  versions and the committed exporter, without replacing them with stubs.

## Frozen SHA-256

```text
19D3E47E3816F4986FF4901CA0D708592139949987C7E88B5530FAFCEF6A7C8E  tools/plimsoll/app.py
664439202065C86EEC4F2192C9838E5E01A0C1FBFCD0EAD0E11B15EA04990C59  tools/plimsoll/__main__.py
9E27E55CFDB8EEE228C177EE406050131934C4B618CDBA01039F86AB36BBA884  tools/plimsoll/tests/test_core_cli.py
```

These paths are frozen for controller preservation. Resume from this checkpoint
with RED tests for the unfinished behaviors; do not promote it directly as a
completed CLI.
