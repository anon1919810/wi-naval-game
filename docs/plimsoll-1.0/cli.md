# Calculation-core command line

Thin CLI adapter over the reviewed Plimsoll calculation core. This document
records the command surface and, in particular, the **exit-code contract** and
the `import-geometry` semantics. It describes observed, acceptance-tested
behaviour; it does not assert that every success path is fully verified
(see the *Status* notes per command).

All commands are invoked as a module: `python -m plimsoll <command> ...`.
On any error the CLI writes a single structured JSON object to **stderr** whose
`schema` is `plimsoll-cli-error-1`; **stdout is reserved for the successful
report** and is empty whenever a command exits non-zero. Exit codes are:

- `0` — every requested stage / case / grid point completed and was persisted.
  The payload `status` is `"completed"`.
- `1` — the request was well-formed and ran, but one or more requested stages
  (or cases / grid points) did not complete. The payload `status` is
  `"partial"` (or the batch/sweep summary reports `"partial"`). Read the
  payload: stage `status` and `reason` are authoritative, the exit code only
  says "not all done".
- `2` — input or usage error: unreadable file, invalid strict JSON, schema
  mismatch, alias/path protection, unsupported arguments, or a condition /
  request that the core rejects as invalid input. Always paired with a
  `plimsoll-cli-error-1` object on stderr.

`analyze`, `batch` and `sweep` compute; `import-geometry` only materializes
explicit geometry bytes into a self-contained project copy. `analyze`,
`batch` and `sweep` return `0 if result["status"] == "completed" else 1`;
`import-geometry` returns `0` on success or `2` on any CLI error.

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

> **Status — not fully acceptance-verified.** The success path of `sweep`
> (a valid grid producing `exit 0` with a `"completed"` summary) is **not**
> covered by the current test suite. Existing tests verify only the axis /
> schema validation failures (exit `2`, `cli.schema_invalid`) and the
> no-output-before-validation guarantee. Treat `sweep`'s happy path as
> implemented-but-not-yet-confirmed until a full-grid acceptance test lands.

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
