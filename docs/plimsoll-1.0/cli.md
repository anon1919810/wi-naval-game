# Calculation-core command line

Thin CLI adapter over the reviewed Plimsoll calculation core. This document
records the command surface and, in particular, the **exit-code contract** and
the `import-geometry` semantics. It describes observed, acceptance-tested
behaviour of the calculation-only CLI.

All commands are invoked as a module: `python -m plimsoll <command> ...`.
On a usage, input, serialization or output-write error, the CLI writes a single
structured JSON object to **stderr** whose `schema` is `plimsoll-cli-error-1`,
with empty stdout. A completed or partial calculation report may be written to
stdout; normal partial completion exits `1` with its report and empty stderr.
For `analyze`, `batch` and `sweep`, exit codes are:

- `0` — every requested stage / case / grid point completed and was persisted.
  The payload `status` is `"completed"`.
- `1` — the request was well-formed and ran, but one or more requested stages
  (or cases / grid points) did not complete. The payload `status` is
  `"partial"` (or the batch/sweep summary reports `"partial"`). Read the
  payload: stage `status` and `reason` are authoritative, the exit code only
  says "not all done".
- `2` — input, usage or output error: unreadable file, invalid strict JSON, schema
  mismatch, alias/path protection, unsupported arguments, or a condition /
  request that the core rejects as invalid input, serialization failure, or an
  `analyze` report destination that cannot be written. Always paired with a
  `plimsoll-cli-error-1` object on stderr.

`analyze`, `batch` and `sweep` compute; `import-geometry` only materializes
explicit geometry bytes into a self-contained project copy. `analyze`,
`batch` and `sweep` return `0 if result["status"] == "completed" else 1`;
`import-geometry` returns `0` on success or `2` on any CLI error.

## verify — explicit offline core verification

`verify [--suite quick|extended|all] --output-dir <absolute-directory> [--case-timeout-s 180] [--total-timeout-s 1800]`

This performs real calculations against declared idealized reference cases.
`quick` is the default (15 cases); `extended` has 26 cases; `all` is their
deduplicated union (38). The coverage includes dry/liquid scale, mirror and
keel-datum laws, nine ellipsoid meshes with three solved diagonal refinements,
and 12 actual single/pair flooding requests: 60/300 seconds at
0.5/0.25/0.125-second steps. Capacity, cancellation, opposite initial flow
directions and reversal prevention are separate controls. A requested duration
is a bound, not a promise to continue after hydraulic equilibrium.

```powershell
$env:PYTHONPATH=(Resolve-Path -LiteralPath './tools').Path
$env:PYTHONIOENCODING='utf-8'
& web/backend/.venv/Scripts/python.exe -B -m plimsoll verify --suite quick --output-dir 'C:\PlimsollVerify\quick'
& web/backend/.venv/Scripts/python.exe -B -m plimsoll verify --suite all --output-dir 'C:\PlimsollVerify\all'
```

These commands can take minutes. Positive finite wall-time limits are owned
by the parent; a stalled worker is terminated and reaped. Earlier evidence and
not-started/timeout/error cases remain visible. `--help` and `readme` perform
no calculation or output-file write. The packaged command uses only the
Python standard library and Plimsoll, without repository docs/tests or network.

The verification exit contract is distinct:

| Code | Meaning |
|---:|---|
| `0` | Complete, consistent measured package identity, every requested verification assertion passed, evidence published |
| `1` | Failed assertion, worker, deadline, or publication after execution began; inspect surviving evidence and diagnostics |
| `2` | Invalid usage or an unsafe/busy output directory rejected before calculation |

Success stdout is `plimsoll-cli-verification-summary-1`, with counts and the
actual paths of `core-verification.json`, `.csv` and `.md`. Anticipated errors
use `plimsoll-cli-error-1` on stderr. A failed output medium cannot promise
fresh files. An expected `model_limit` or `canceled` control may pass its
verification assertion; its raw physics status is retained separately.

All formats carry the same UUID `run_id` and `generation`. JSON, schema
`plimsoll-core-verification-1`, is authoritative: a partial checkpoint precedes
the first case and follows each case; CSV and Markdown are replaced before
the final JSON. This is not a three-file transaction. Partial or mixed-generation
files must never be treated as passing. Reuse is allowed only for this tool's
valid evidence; unrelated files, links/junctions and concurrent writers are
refused. Unknown/abandoned locks are retained rather than guessed stale; verify
the owner before manually removing `.plimsoll-core-verification.lock`.

Evidence includes literal requests, raw flags/residuals, signed transfer and
conservation records, loaded origins, file hashes and input seals at each
public-call boundary. It identifies measured disk sources rather than arbitrary
in-memory callable changes. Changes restored within the same call are outside
the input seal's scope. File locking also does not eliminate an adversarial OS
race between the last ownership check and filesystem replacement.

Analytic consistency, transformations, numerical refinement and model-boundary
controls are different evidence categories. None establishes external
experimental accuracy, historical-input accuracy or certification. The local
accepted result, costs and limits are in
[2026-10-10 verification](core-verification-2026-10-10.md); publication is a
separate step.

## analyze

`analyze <project> --condition <id> [--options <json>] [--output <path>] [--csv <path>]`

Computes one selected loading. `<project>` is a `plimsoll-project-1` document
and `--condition` selects a loading condition by `id`. `--options` is an
optional strict-JSON request document (`plimsoll-analysis-1` request schema).

The **default request set includes `propulsion`** (alongside loading, systems,
l0, geometry, equilibrium, hydrostatics and deck). Therefore a project that
lacks the propulsion facts it needs (e.g. no
`systems.propulsion.facts.shafts`) honestly reports `partial` and exits `1`
— its `propulsion` stage is `unavailable` with reason
`"requested output is incomplete or outside its model"`. **Scripts must inspect
the payload, not only the exit code**: exit `1` is expected and informative,
not a crash.

Verified examples (run against the bundled cases):

- `analyze .../generic_steamer.project.json --condition loaded`
  → exit `0`, payload `status="completed"`, no non-completed stage.
- `analyze .../analytic_box.project.json --condition loaded`
  → exit `1`, payload `status="partial"`, and the only cause is
  `stages.propulsion.status="unavailable"`.
- `analyze <project> --condition does_not_exist`
  → exit `2`, stderr `plimsoll-cli-error-1` (code `cli.calculation_input`).
  It is a usage/input error, never a partial result.

`--options` pointing at invalid strict JSON (e.g. duplicate object keys) is a
usage error → exit `2` with `cli.json_invalid`. The report output path may not
alias an explicitly read input → exit `2` with `cli.output_alias`.

Argparse failures (including absent commands, unknown options and missing
required arguments) use `cli.usage` and the same JSON error contract. `--help`
still prints ordinary help and exits `0`. Malformed sweep field types use
`cli.schema_invalid` with their exact input path.

`analyze` validates JSON and CSV serialization before any output is written.
`cli.output_serialization_failed` or `cli.output_write_failed` exits `2`, even
when the calculation itself completed. Its error context includes
`calculation_status` and `persisted_outputs`, the absolute paths actually
written before the failure. Each file is replaced atomically; multiple output
files are not a single transaction, so a later CSV write failure does not
claim that an already written JSON report was rolled back.

## batch

`batch <manifest> --out <dir> [--csv <path>]`

Runs an explicit case manifest (`plimsoll-batch-1`): an object with `cases`,
each a `{id, project, condition_id, options?}`. `project` paths are resolved
relative to the manifest. Each case is computed independently; a failing case
is recorded in the summary with its diagnostics and does **not** abort the
batch. Exit `0` only when every case completed *and* its result was persisted;
otherwise exit `1` (summary `status="partial"`). Invalid manifest schema → exit
`2` (`plimsoll-cli-error-1`).

## sweep

`sweep <document> --out <dir> [--csv <path>]`

Computes a bounded grid over resistance axes (`plimsoll-sweep-1`): an object
with `project`, `condition_id`, `base_options`, and `axes`. Axes are limited to
`resistance.speed_kn` (≤201 values) and `resistance.qpc` (≤21 values), with a
total grid of ≤1000 points; every value must be finite and positive, and
`source` must be a nonempty string or object. Each grid point is computed and
persisted independently; exit `0` only when every point completed *and* was
persisted, otherwise exit `1`.

The success path is covered by `test_core_cli.py` tests for a completed grid,
deterministic request identity, and a method-limited grid. The strict method
still reports an unavailable/model-limited point rather than inventing a value.

Invalid axes or schema → exit `2` (`plimsoll-cli-error-1`, `cli.schema_invalid`).

## import-geometry

`import-geometry <project> <geometry> --format <fmt> --keel-offset-m <n> --provenance <text|json> --estimate true|false --output <path>`

Materializes **explicitly supplied** geometry bytes into a self-contained
project copy and writes it to `--output`. Supported `--format` values:
`legacy-offsets-5`, `plimsoll-section-polygons-1`. It performs **no automatic
discovery, reference resolution, or migration**: it reads only the bytes the
caller hands it (via `<geometry>`), together with the declared `format`,
`keel-offset-m`, `provenance`, and `estimate`, and writes one owned project. A
missing geometry file, schema mismatch, invalid UTF-8, duplicate payload keys,
or a non-finite keel offset are all usage errors → exit `2` with
`plimsoll-cli-error-1` (`cli.input_read` / `cli.geometry_import` /
`cli.keel_offset_invalid` / ...). The output path may not alias an explicitly
read input → exit `2` (`cli.output_alias`).

`--provenance` accepts a **nonempty string or a JSON object**:

- Bare string (e.g. `"survey 1913"`) is kept verbatim as the source.
- A JSON object (e.g. `{"title": "Queen Mary 1913 型线"}`) is decoded and used
  as the structured source.
- A JSON string literal (`"\"survey 1913\""`) is decoded to the unquoted string.
- Only an **empty or whitespace-only** value is rejected with
  `cli.provenance_invalid` (exit `2`). Every other value is accepted: a JSON
  object becomes the structured source, while `null`, a number, an array and an
  unparseable bare string are all kept verbatim as their literal text.

## Error shape

Every CLI failure writes exactly one `plimsoll-cli-error-1` object to stderr:

```json
{
  "schema": "plimsoll-cli-error-1",
  "command": "analyze",
  "code": "cli.calculation_input",
  "message": "calculation input is invalid: ...",
  "input_path": "...",
  "diagnostics": [{"code": "...", "severity": "error", "path": "$....", "message": "...", "blocking": true}]
}
```

Where the failure originated inside the calculation core, `diagnostics` carries
the core's own structured diagnostics; otherwise a single CLI-level diagnostic
is supplied. No traceback is emitted to the user.
