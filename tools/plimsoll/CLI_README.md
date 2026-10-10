# Plimsoll calculation core — command line guide

This is the self-contained guide to the Plimsoll calculation core command line.
Print it with:

```bash
python -m plimsoll readme
```

The commands, exit codes, fingerprints and worked examples below were executed
against the bundled cases with Python 3.12, and their stated outcomes are what
was actually observed. The request-object examples that show *shape* (the
`sweep` document, the `batch` manifest, the `import-geometry` invocation) are
written to be faithful to the schemas; where one is marked as verified, its exit
code and output are a real run. It describes what this core actually computes
and what it refuses to guess. It is a design and comparison tool for ship
hydrostatics, stability, resistance, propulsion, endurance and flooding studies.
It is not a certified design tool, not a full SpringSharp reproduction, and it
carries no historical or class-approval claim.

---

## 1. Running it

There is no wheel and no installer. The core is the `plimsoll` package inside
this tree. Put its parent directory on `PYTHONPATH` and run it as a module.

**Linux / macOS:**

```bash
export PYTHONPATH=/path/to/tools        # the directory that CONTAINS plimsoll/
python -m plimsoll --help
```

**Windows PowerShell** — replace the one path with your own absolute path:

```powershell
$env:PYTHONPATH = 'C:\path\to\repo\tools'
& 'C:\path\to\python.exe' -m plimsoll --help
```

The production image does exactly this (`PYTHONPATH=/app/tools`, the package
copied to `/app/tools/plimsoll`), so the same commands work there unchanged.

**Python 3.12** is the verified runtime. The core has no third-party runtime
dependencies — only the standard library.

Every command runs correctly from an unrelated working directory: nothing
searches the current directory, and no project, calculation, network or
configuration file is discovered implicitly. Every input is an explicit
argument. In the examples below, relative paths are written as though you were
at the repository root, because that is what was actually run; from anywhere
else, pass absolute paths for the project, the options document and every
output.

---

## 2. Commands at a glance

| Command | What it does |
|---|---|
| `analyze` | Calculate one selected loading condition of one project |
| `batch` | Calculate an explicit list of cases from one manifest |
| `sweep` | Calculate a bounded grid over speed / QPC |
| `import-geometry` | Materialize explicitly supplied geometry bytes into a project copy |
| `readme` | Print this guide |

---

## 3. Exit codes and the error contract

| Code | Meaning |
|---:|---|
| `0` | The command did what it was asked. For `analyze`, every requested stage completed and the result was emitted to the configured outputs; for `batch` and `sweep`, every case / grid point completed and was persisted; for `readme`, the guide was written to stdout; for `import-geometry`, the project was written |
| `1` | The request was well formed and ran, but at least one requested stage, case or grid point did not complete. The result is still written, to stdout and/or to the requested files, and it is the real answer |
| `2` | Input, usage, schema, serialization or output-write error. One `plimsoll-cli-error-1` object on stderr, empty stdout |

Where the result goes on a successful run differs by command, because the
commands do different things:

* `analyze` defaults to `--output -`, which writes result JSON to **stdout**.
  `--csv report.csv` additionally writes CSV and keeps JSON on stdout. With
  `--output report.json`, JSON goes to that file and stdout stays empty;
  `--csv` can also be supplied. JSON is emitted to stdout only after all
  requested files have been written successfully.
* `batch` and `sweep` write numbered result files and a summary file into
  `--out`, plus the optional `--csv` summary. stdout stays empty.
* `import-geometry` writes one project document to `--output`. stdout stays
  empty.
* `readme` writes the guide to stdout and touches nothing else.

**Read the payload, not only the exit code.** Exit `1` is informative, not a
crash: a project that lacks propulsion facts honestly reports `partial`, writes
that partial result, and exits `1` with an empty stderr.

On exit `2` there is exactly one JSON object on **stderr** and stdout is empty:

```json
{
  "schema": "plimsoll-cli-error-1",
  "command": "analyze",
  "code": "cli.calculation_input",
  "message": "calculation input is invalid: ...",
  "input_path": "…",
  "diagnostics": [
    {"code": "…", "severity": "error", "path": "$.…", "message": "…", "blocking": true}
  ]
}
```

Errors the CLI anticipates — unreadable files, invalid strict JSON, schema
mismatches, path-alias protection, unsupported arguments, a rejected condition
or request, a failed serialization, an unwritable destination — are reported
this way rather than as a Python traceback. `cli.output_write_failed` and
`cli.output_serialization_failed` also carry `calculation_status` and
`persisted_outputs` — the absolute paths actually written before the failure,
so a partially written set is never reported as a rolled-back one.

`--help` and `readme --help` print ordinary help and exit `0`. `readme` is a
pure local read of one bundled file: no arguments, no project, no calculation,
no network, no writes.

---

## 4. `analyze` — one selected loading

```bash
python -m plimsoll analyze <project> --condition <id> [--options <json>] \
                             [--output <path>] [--csv <path>]
```

* `<project>` — a `plimsoll-project-1` document.
* `--condition <id>` — **required.** The `id` of one existing loading condition.
* `--options <json>` — optional request document (section 6).
* `--output <path>` — default `-`, meaning the result JSON goes to **stdout**.
* `--csv <path>` — also write the flat CSV form (section 9).

`--output` may not alias a file that was explicitly read (`cli.output_alias`).
Both output formats are serialized and validated before anything is written,
and each file is replaced atomically.

### Worked examples against the bundled cases

```bash
# Completes: every default stage is available in this project.
python -m plimsoll analyze tools/plimsoll/cases/projects/generic_steamer.project.json \
        --condition loaded --output result.json --csv result.csv
# exit 0, status "completed"

# Partial, honestly: this project has no propulsion facts.
python -m plimsoll analyze tools/plimsoll/cases/projects/analytic_box.project.json \
        --condition loaded
# exit 1, status "partial",
# stages.propulsion.status == "unavailable",
# stages.propulsion.reason == "requested output is incomplete or outside its model"

# An unknown condition is an input error, never a partial result.
python -m plimsoll analyze tools/plimsoll/cases/projects/analytic_box.project.json \
        --condition does_not_exist
# exit 2, cli.calculation_input

# Geometry at a real keel datum.
python -m plimsoll analyze tools/plimsoll/cases/projects/queen_mary_1913.project.json \
        --condition normal-engineering --output qm.json
# exit 0; geometry_datum.keel_offset_m == -9.9
```

Bundled project templates and their conditions:

| Project | `schema` | Conditions |
|---|---|---|
| `cases/projects/analytic_box.project.json` | `plimsoll-project-1` | `light`, `loaded` |
| `cases/projects/generic_steamer.project.json` | `plimsoll-project-1` | `coastal`, `loaded` |
| `cases/projects/queen_mary_1913.project.json` | `plimsoll-project-1` | `normal-engineering`, `deep-engineering` |

---

## 5. `batch` — an explicit case manifest

```bash
python -m plimsoll batch <manifest> --out <dir> [--csv <path>]
```

The manifest is a `plimsoll-batch-1` object — this exact two-case manifest was
run against the bundled generic steamer, and both cases completed:

```json
{
  "schema": "plimsoll-batch-1",
  "cases": [
    {"id": "loaded",  "project": "projects/steamer.json", "condition_id": "loaded"},
    {"id": "coastal", "project": "projects/steamer.json", "condition_id": "coastal",
     "options": {"stages": ["loading", "systems", "l0", "geometry",
                            "equilibrium", "hydrostatics", "deck", "propulsion"]}}
  ]
}
```

* `id` — nonempty and unique. It is a label only; it is never used as a path,
  so a hostile id cannot create or overwrite anything.
* `project` — resolved **relative to the manifest's own directory** unless
  absolute.
* `condition_id` — must exist in that project.
* `options` — optional, same request object as `analyze --options`.

Each case is independent. A failing case is recorded in the summary with its
diagnostics and does **not** abort the batch. The output directory receives
`0001.result.json`, `0002.result.json`, … (ordinal filenames, in manifest order)
plus `batch-summary.json`. The summary is `plimsoll-batch-result-1` with
`status` `completed` or `partial`; every row carries its own `status`,
`persistence` and the three fingerprints.

Exit `0` only when **every** case completed *and* its result was persisted.

---

## 6. `sweep` — a bounded speed / QPC grid

```bash
python -m plimsoll sweep <document> --out <dir> [--csv <path>]
```

The document is a `plimsoll-sweep-1` object:

```json
{
  "schema": "plimsoll-sweep-1",
  "project": "…/generic_steamer.project.json",
  "condition_id": "coastal",
  "base_options": {"stages": ["resistance"],
                   "resistance": {"scenario_id": "holtrop-trim-study", "speeds_kn": [10]}},
  "axes": [
    {"field": "resistance.speed_kn", "values": [8, 10, 12],
     "source": "declared speed grid", "estimate": false},
    {"field": "resistance.qpc", "values": [0.5, 0.55],
     "source": "declared qpc study", "estimate": true}
  ]
}
```

Limits, all enforced before any output is created:

* only `resistance.speed_kn` (≤ 201 values) and `resistance.qpc` (≤ 21 values);
* unique axis fields; every value finite and strictly positive;
* `source` a nonempty string or object, `estimate` a real boolean;
* total grid ≤ 1000 points.

Each point replaces `options.resistance.speeds_kn` with a one-element array
and/or `options.resistance.qpc_override` with a `{value, source, estimate}`
fact. Output is `NNNN.result.json` plus `sweep-summary.json`
(`plimsoll-sweep-result-1`), whose `declaration` echoes the whole input
document so a grid is reproducible from its own summary.

Verified behaviour — this grid was actually run against the bundled generic
steamer, with the document above:

```bash
python -m plimsoll sweep sweep.json --out out --csv sweep.csv
# holtrop-trim-study, speeds 8/10/12 kn x qpc 0.5/0.55
# exit 0, "completed", 6 points, 6 distinct request fingerprints,
# 1 shared project fingerprint (one selected project, six distinct requests)
```

A strict tabulated method stays honest instead of extrapolating: running the
same grid against `taylor-trim-study` at 8/10/12 kn returns exit `1`,
summary `partial`, and every point's `resistance.status == "model_limit"` with
a `taylor.outside_table` diagnostic.

---

## 7. `import-geometry` — materialize explicit geometry bytes

```bash
python -m plimsoll import-geometry <project> <geometry> \
        --format <fmt> --keel-offset-m <n> \
        --provenance <text|json> --estimate true|false \
        --output <path>
```

`--format` is `legacy-offsets-5` (payload schema `plimsoll-offsets-1`) or
`plimsoll-section-polygons-1`. The command reads **only the bytes you name**,
together with your declared format, keel offset, provenance and estimate flag.
It performs no automatic discovery, reference resolution or migration, and it
writes one self-contained project copy whose `geometry.kind` is `offsets`, with
the raw content SHA-256, the keel offset and your provenance recorded under
`geometry.source`.

```bash
# The bundled queen_mary_1913_offsets.json is a legacy-offsets-5 payload, so the
# analytic box project below is the smallest case it can be imported into.
python -m plimsoll import-geometry \
        tools/plimsoll/cases/projects/analytic_box.project.json \
        tools/plimsoll/cases/queen_mary_1913_offsets.json \
        --format legacy-offsets-5 --keel-offset-m -1.0 \
        --provenance '{"title": "Queen Mary 1913 lines"}' \
        --estimate true --output imported.project.json
```

This shape was run and wrote a project whose `geometry.kind` is `offsets` with
`keel_offset_m` `-1.0` and the structured provenance recorded; the reusable form
above shows a non-ASCII title.

`--provenance` accepts a nonempty string kept verbatim, a JSON object used as
structured source, or a JSON string literal decoded to its unquoted string.
Only an empty or whitespace-only value is refused
(`cli.provenance_invalid`).

This is the CLI's **explicit** import path for geometry, and the way to bring
an external type table or section set into a project from the command line. It
reads **only the bytes you name**, together with your declared format, keel
offset, provenance and estimate flag. It performs no automatic discovery,
reference resolution or migration, and it writes one self-contained project copy
whose `geometry.kind` is `offsets`, with the raw content SHA-256, the keel
offset and your provenance recorded under `geometry.source`.

A project can of course already arrive with usable geometry: one saved from a
previous import, or one built by a workspace or a script that materialized a
reference hull in memory. Those need no import step. What no path does is
*resolve* geometry for you at compute time — a project whose geometry is still
an unresolved `offsets_reference` reports the `geometry` stage as `unavailable`
with `analysis.geometry_not_materialized`, and nothing is filled in silently.
Import is how you turn an external reference into owned, self-contained
geometry.

---

## 8. The request options object

Only these keys are accepted; anything else is an error.

| Key | Meaning |
|---|---|
| `stages` | Unique subset of the fifteen stage names (below). Omitting it requests the default set |
| `equilibrium` | Solver options: `rho_t_m3`, `heel_bounds_deg`, `trim_bounds_deg`, `heel_deg`, `target_trim_deg`, `max_iterations`, `initial`, `liquid_loads`. Effective defaults are echoed back |
| `gz_angles_deg` | 1–201 finite, strictly increasing angles. **Required when `gz` is requested** |
| `hydrostatic_waterlines_above_keel_m` | 1–201 increasing waterlines. **Required when `hydrostatic_curve` is requested** |
| `bonjean_waterlines_above_keel_m` | 1–201 increasing waterlines. **Required when `bonjean` is requested** |
| `resistance` | `{scenario_id}` **or** `{scenario}`, plus `speeds_kn`; optional `qpc_override`; `mode`; `fixed_shaft_power_kw` |
| `endurance_scenario_id` | An existing project `endurance_scenarios[].id`. Required for `endurance` |
| `flooding` | `{scenario, options}`. Required for `flooding` |

Notes that matter in practice:

* Supplying a grid does **not** request its stage, and requesting a stage
  without its grid is an error. The two are separate decisions.
* `resistance` needs an explicit scenario and speeds. `qpc_override` is
  `{value, source, estimate}` with a positive value — this is the same explicit
  override the sweep axis uses, so no project mutation is needed.
* `mode: "fixed_power"` additionally requires `fixed_shaft_power_kw`, one
  sourced `qpc_override`, and at least two bracketing speeds. It never
  extrapolates past the submitted grid.
* Speed × QPC sample count must not exceed 1000.
* Unknown keys, booleans where numbers belong, non-finite numbers and a
  resistance fluid density that conflicts with the selected equilibrium density
  are all rejected before any calculation starts.

---

## 9. The result: `plimsoll-analysis-1`

```jsonc
{
  "schema": "plimsoll-analysis-1",
  "status": "completed | partial | canceled",
  "project_id": "…", "condition_id": "…",
  "project_fingerprint": "…", "input_fingerprint": "…", "request_fingerprint": "…",
  "request": {"schema": "plimsoll-analysis-request-1", "condition_id": "…", "options": {…}},
  "input_snapshot": { /* the normalized canonical project actually used */ },
  "units": {…}, "coordinates": {…}, "geometry_datum": {…},
  "method_versions": {…}, "sources": {…},
  "diagnostics": [ … ], "validity": {…},
  "stages": { /* all fifteen envelopes are always present */ }
}
```

### The fifteen stages

`loading`, `systems`, `l0`, `geometry`, `equilibrium`, `hydrostatics`, `gz`,
`deck`, `hydrostatic_curve`, `bonjean`, `resistance`, `propulsion`,
`endurance`, `historical`, `flooding`.

Default request set: `loading`, `systems`, `l0`, `geometry`, `equilibrium`,
`hydrostatics`, `deck`, `propulsion`. **This default includes `propulsion`**,
which is why a project without propulsion facts exits `1`.

Dependencies may run with `requested: false`; every stage is present either
way, so a consumer never has to guess whether a stage was skipped or lost.

### Stage envelope

```jsonc
{
  "status": "not_requested",
  "requested": false,
  "dependencies": [],
  "reason": null,
  "validity": {"complete": false, "converged": null,
               "model_applicable": null, "historical_validated": null},
  "method_versions": {}, "assumptions": [], "diagnostics": [], "data": null
}
```

Stage `status` is one of `completed`, `not_requested`, `unavailable`, `failed`,
`canceled`, `model_limit`.

Top-level `status` is `canceled` if a requested stage cancels, otherwise
`completed` only when every requested stage completed **and**
`validity.complete` is true, otherwise `partial`.

### The four validity axes are separate, and three of them are tri-state

| Axis | Meaning |
|---|---|
| `complete` | boolean — the requested output was produced |
| `converged` | `true` / `false` / `null`. `null` means *not assessed*: the stage either has no iterative solve to converge, or it never ran, or it did not get far enough to have an answer |
| `model_applicable` | `true` / `false` / `null`. `null` means *not assessed* for the same reason |
| `historical_validated` | always `null`. This core never certifies historical validity |

A `null` on either tri-state axis is **not** "unknown" in the sense of a missing
measurement, and it is not a pass. Read `status` and `reason` first: a stage that
is `not_requested` has `converged: null` because it was never asked to do
anything, and one that is `unavailable` or `failed` may have `null` because it
stopped before it could report. Only a stage that is `completed` with an
explicit `converged` value is saying anything about convergence.

`status == "completed"` never means "empirically validated". Read
`validity.model_applicable` and the diagnostics for what the number actually
means.

### A model limit is not a result

When a stage reports `status: "model_limit"` (or
`validity.model_applicable: false`), **none of its numbers are primary-valid**.
The stage ran, and it may well have returned values — a `power_rows` entry, a
`rows` list, a study — but every one of those is outside the method's valid
range. Do not quote any of them as a computed answer, and do not treat the
stage's output as usable input to a downstream statement.

Where a stage offers a labelled alternative to its primary result, it says so in
the data itself, and that label is part of the claim:

* `primary_result: false` marks a row or block that is a **study or proxy**, not
  the quantity the request was for — a non-primary applicability row, a bracket
  or bisection result, a comparison.
* `validity.complete: false` alongside `model_limit` marks a study that was
  produced under a condition it cannot be extended from.

Read those fields before quoting a figure, and say which of the two it is:
the requested quantity, or a labelled proxy for it.

### Units, coordinates and datum

Canonical values are metres, metric tonnes, knots, kilowatts and degrees.
Every result carries them explicitly:

```json
"units": {"length": "m", "mass": "t", "speed": "kn", "power": "kW", "angle": "deg"},
"coordinates": {"x_positive": "forward", "x_origin": "midships",
                "y_positive": "starboard", "z_origin": "keel"},
"geometry_datum": {"keel_offset_m": -9.9, "coordinate_origin": "explicit_geometry_datum"}
```

`kg_m` is measured upward **from the keel**, and the geometry model carries its
own explicit `keel_offset_m`. Nothing infers one from the other, and nothing
infers a keel offset from a waterline. Supported explicit conversions:
`t`/`kg`/`long_ton`, `m`/`ft`, `kn`/`m_s`, `kW`/`shp`, `deg`/`rad`; crossing
dimensions is an error.

### Identity — three fingerprints, three different questions

* `project_fingerprint` — the normalized project as a whole. Two runs that
  differ only in which loading condition was selected share it.
* `input_fingerprint` — the *selected loading* for this run: the resolved
  weight ledger and mass moments for that one condition. A different condition
  gives a different value, because the selected loading really is different.
* `request_fingerprint` — snapshot **plus** condition **plus** effective
  options **plus** method versions. Two sweep points on one project share the
  first and differ in the third.

Verified on the bundled generic steamer, `coastal` vs `loaded`:

| | `coastal` | `loaded` | same? |
|---|---|---|---|
| `project_fingerprint` | `ed81316ba46d15e2…` | `ed81316ba46d15e2…` | yes |
| `input_fingerprint` | `3945264df02634ae…` | `1dd8c3a366535d92…` | **no** |
| `request_fingerprint` | `516e352a1e464790…` | `738fdf98fd0ee898…` | **no** |

Use `request_fingerprint` to decide whether a stored result can be reused for a
new request. Method versions travel with it:

```json
"method_versions": {"coordinator": "selected-loading-analysis-2",
                    "geometry": "geometry-analysis-1",
                    "stability": "loaded-projected-equilibrium-2",
                    "request": "plimsoll-analysis-request-1"}
```

### Null is not zero

An unknown value is JSON `null`. Zero is a known value and is never treated as
missing. Booleans are not numbers, and `NaN` / infinities are invalid input,
not "very large".

A useful consequence you can rely on: `deck_coverage.coverage_pct` is `100 ×
covered plan area / reference plan area` **only when both areas are known**;
otherwise it is `null` with `status: "unavailable"`. Nothing is substituted.

### Source and estimate are tri-state, per field

`estimate` is `true` for an estimate, `false` for explicitly confirmed
non-estimated provenance, and **`null` when that provenance is unknown**. A
missing item `estimate` normalizes to `null` with a warning; it is never
silently treated as `false`. For overridden fields, an item-level estimate is
`true` if any field is estimated, else `null` if any field is unknown, else
`false` — so an aggregate estimate can never conceal one unknown field. The
same discipline runs through the results: read the sibling `*_source` and
`*_estimate` keys beside every value.

### Diagnostics

Every diagnostic is `{code, severity, path, message, blocking}` and carries
`stage` plus `source_path` inside the result. Stage-level and the flattened
top-level list hold the same records; they are never coalesced by message.
`severity` is `info`, `warning` or `error`. Warnings are not failures: an
incomplete input may still produce a usable selected-loading answer, and the
warning tells you what to go and supply.

### CSV

`--csv` writes a generic flatten of the whole result: one row per JSON node,
with `path`, `parent_path`, `key`, `index`, `value_type`, `value`,
`container_size`, `stage`, `stage_status`, `record_path`, plus
`analysis_status`, `project_id`, `condition_id` and all three fingerprints
repeated on every row. Object and array nodes carry an empty `value` and a
`container_size`. It is a faithful export, not a fixed summary table, so no
numeric row assumption is needed to read it.

---

## 10. Project JSON versus result JSON/CSV

These are different objects and are easy to confuse.

| | Project JSON | Result JSON / CSV |
|---|---|---|
| `schema` | `plimsoll-project-1` | `plimsoll-analysis-1` |
| Direction | **input** | **output** |
| Produced by | The web workspace, or `import-geometry` | `analyze` / `batch` / `sweep` |
| Contains | Hull, geometry, weight ledger, loading conditions, systems, sources | Selected masses, hydrostatics, GZ, resistance, validity, diagnostics |
| Contains results? | **No.** `result`, `results`, `cache`, `cache_key` and `input_fingerprint` are rejected as project fields, so a stored result can never change its own input fingerprint | Yes |

**Getting a project JSON from the web workspace.** The workspace stores
normalized projects and immutable per-revision snapshots. The two `GET`
endpoints below are read-only and safe to call:

* `GET /api/projects` lists them.
* `GET /api/projects/{project_id}` returns
  `{"project_id", "revision", "project": {…}}` — the `project` member is a
  complete `plimsoll-project-1` document and can be fed straight to `analyze`.

Creating a project (`POST /api/projects`, with a bundled `template` or `null`)
**changes workspace state**. Treat it as an operation to be agreed first, not as
a lookup. The web path deliberately refuses unresolved external geometry: an
`offsets_reference` project must be materialized before it can be used.

**Getting a result from the web workspace.** Queuing a run is `POST
/api/projects/{project_id}/runs {"revision", "condition_id", "options"}` — a
mutating operation that spends worker time and writes a stored result, so it
needs agreement first. The read-only halves are `GET /api/runs/{run_id}` for an
existing run and `GET /api/runs/{run_id}/export?format=json|csv`, which returns
exactly the bytes `analyze` would have written.

Both paths produce the same `plimsoll-analysis-1` document with the same three
fingerprints, so a result obtained in the browser is directly comparable with
one computed on the command line.

---

## 11. Guidance for an AI reading these results

**You are reading, not operating.** Everything in this guide is a *reference*
for how to interpret existing JSON, CSV and diagnostics. It is not a standing
authorization to change anything. Reading, summarizing and explaining are the
default. Before you do any of the following, say what you intend to do and get
agreement:

* change a project, a weight item, a loading condition, a `source` or an
  `estimate` — any edit that changes what a future calculation would produce;
* recompute, and overwrite or replace an existing result, CSV or summary file;
* run `import-geometry` and write a project document;
* call a mutating API operation — `POST`, `PUT`, `PATCH`, `DELETE`, including
  creating a workspace, saving a project, queuing a run or exporting one.

Prefer writing new outputs to new paths over overwriting anything. If you were
asked only to explain a result, stop at the explanation.

1. **Inspect before you summarize.** Read `status`, every
   `stages.<name>.status`, each `stages.<name>.reason`, and every diagnostic.
   A number inside a `partial` result is a real number, but it is not the whole
   answer.
2. **Never read a `null` as `0`**, and never read `estimate: null` as `false`.
   If a value you need is `null`, say which input is missing.
3. **Ask for the missing source input.** Diagnostics name the exact JSON path
   (`$.weight_groups[0].items[0].x_m`,
   `$.systems.propulsion.facts.shafts`,
   `$.stages.resistance…`). That path is the question to ask. Do not invent a
   plausible number to fill it.
4. **Keep the uncertainty visible.** When you report a value, carry its
   `source` and `estimate` with it, and say when they are `null`. An estimate
   presented as a measurement is a different claim from the same number
   honestly labelled.
5. **Watch the model boundary.** `status: "model_limit"` with
   `validity.model_applicable: false` means the input is outside the method's
   valid range — for example speeds outside the registered Taylor table. No value
   in that stage is primary-valid. Report it as "outside the model's range", not
   as a computed value, and if you quote any number from it, label it as the
   study or proxy it is (see "A model limit is not a result").
6. **Compare deliberately, and say what differs.** Comparing two results means
   naming the difference rather than assuming there is none. Report the
   conditions, the effective options and the method versions on each side, and
   keep each result's own fingerprints attached to it. Two different
   `request_fingerprint`s are not an obstacle to a comparison — they are the
   record of what was varied — but they do mean the two are not the same
   calculation, and a difference between them is a difference between *those two
   requests*. Identical `request_fingerprint` plus identical method versions is
   what establishes that a stored result may be replayed or reused. A
   non-default `estimate`, a `null` or a model limit on either side is part of
   what is being compared.
7. **State the boundary of the whole tool.** Hydrostatics, stability,
   resistance, propulsion, endurance and connected quasi-static flooding. No
   armour penetration, no explosion, no CFD, no full seakeeping, no structural
   strength, no historical cost, no combat-damage simulation — and no
   certification of any kind.

---

## 12. More detail in this repository

* `docs/plimsoll-1.0/cli.md` — the command surface and exit-code contract.
* `docs/plimsoll-1.0/data-contract.md` — the `plimsoll-project-1` contract,
  units, coordinates, provenance and the input fingerprint.
* `docs/plimsoll-1.0/analysis-api.md` — the exact result layout and request
  rules.
* `docs/plimsoll-1.0/project-extensions.md` — optional system facts, scenarios
  and historical comparison rows.
* `docs/plimsoll-1.0/geometry-import-api.md` — `import-geometry` semantics.
* `docs/plimsoll-1.0/current-status.md` and `core-release-2026-10-10.md` —
  what is reviewed and what is still open.
* `tools/plimsoll/README.md` — the module history and known-open items.
