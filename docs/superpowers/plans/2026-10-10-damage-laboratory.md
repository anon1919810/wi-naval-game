# Damage Laboratory Implementation Plan

> **For agentic workers:** Follow the tasks in order. The user's OpenCode delegation contract overrides the stock implementation/commit workflow: OpenCode implements; Codex independently reviews and verifies; no git mutation.

**Goal:** A local Three.js experiment page explaining one hit's module, grouped-crew and ship consequences using the actual Plimsoll flooding core.

**Architecture:** A pure Python damage-lab package validates and freezes experiment inputs, applies sourced gameplay effects and wraps the native flooding coordinator. The existing bounded database worker dispatches laboratory requests as a distinct kind. React owns the accessible form/report/timeline and lazy-loads a disposable Three.js inspector.

**Tech stack:** Existing Python/FastAPI/SQLAlchemy and React/TypeScript/Vite; add Three.js and its TypeScript declarations only. No database migration or Unity changes.

**Spec:** `docs/superpowers/specs/2026-10-10-damage-laboratory-design.md`.

## Global constraints

- Preserve every file recorded in the protected baseline at the task output directory, including dirty `tools/plimsoll/app.py`. Existing core formula files and legacy Unity files are read-only.
- No staging, commits, resets, cleaning, public deployment, secrets, model overrides, or unrelated refactors.
- Use the current flooding coordinator and its raw accepted-state semantics; no legacy damage.py path.
- All game effect rules and default crew counts are sourced estimates, not historical/medical predictions. Unknown stays null.
- Frame stepping uses event index; report state belongs to the frozen request, never the latest draft by coincidence.
- Space Grotesk / Inter, scoped styling, current light/dark theme, desktop first; preserve existing narrow-page behaviour.
- Batch test clusters; record failing regression checks before implementation and green checks after each complete cluster.

## Review focus

- Invalid or unsupported project subdivision: explain missing geometry/compartments before running; an explicit synthetic demo is a separate imported project, not invented ship data.
- A lab request ID opened through an analysis report URL: reject the wrong kind rather than rendering a malformed analysis report.
- Rapid condition/impact edits during HTTP or worker completion: retire stale responses and stop old playback.
- Core early stop/cancel with accepted rows: show useful last accepted state and native stop/validity, without the requested-duration endpoint.
- Unknown crew or power input: readable unavailable state, never zero injuries or a fake 100% capability.

## Task 1 — Pure aftermath contract and game events

**Create:** `tools/plimsoll/damage_lab/__init__.py`, `request.py`, `effects.py`, `coordinator.py`, `exports.py`.
**Tests:** `tools/plimsoll/tests/test_damage_lab.py` (focused subfiles are allowed).

**Consumes:** `project_io`, selected `loading`, public `analysis.compute_project`.
**Produces:** `normalize_request(project, condition_id, experiment)` tuple and
`run_experiment(project, condition_id, experiment, *, cancel_check=None)` JSON-compatible result.

- [ ] Write contract tests for no mutation, duplicate IDs, nonfinite/bool numbers, invalid geometry, metadata, foreign module/crew/breach links and null personnel. Confirm red before adding implementation.
- [ ] Implement strict normalized schemas and method-bound identity. Retain canonical project/condition IDs and source/estimate records.
- [ ] Implement specified localized AABB exposure, crew conservation and independent mechanical/flood/staff availability. Validate a known N=10, severity=1, casualty_fraction=.4, fatal_fraction=.25 case gives 6 available, 3 incapacitated, 1 dead at impact; no count is negative or counted twice.
- [ ] Pin builder-check choices: a crew group cannot staff two modules; modules/station boxes fit their compartment; off-face sea breaches and separated-compartment internal breaches fail; integrity=.5 and staffing=.5 produces .25, with documented zero/null propagation.
- [ ] Use simultaneous indexed events at t=0 and exact immutable state snapshots; explicit event causes contain module/group/compartment IDs.
- [ ] Call real flooding through analysis, map accepted rows to later effects, retain native output and complete validity/stop diagnostics. Match native water and equilibrium quantities exactly in projection.
- [ ] Real-core dry zero-impact and submerged-breach tests; test cancellation/early stops with real or explicitly stubbed native outcomes, without a fabricated successful result.
- [ ] Export deterministic full JSON and traceable CSV; reject nonfinite output.

Run: `python -m unittest discover -s tools/plimsoll/tests -p 'test_damage_lab*.py' -v`.
Pass: every new contract/effect/core-bridge check passes and at least one real nonzero flooding timeline was computed.

## Task 2 — Fixtures and standalone CLI

**Create:** `tools/plimsoll/damage_lab/__main__.py`, `tools/plimsoll/cases/damage_lab/` with an explicit synthetic canonical project and experiments.
**Create:** `docs/plimsoll-1.0/damage-laboratory.md` with reproducible local commands and model boundaries.

**Consumes:** Task 1 functions.
**Produces:** `python -m tools.plimsoll.damage_lab --project FILE --condition ID --experiment FILE --output FILE [--csv FILE]`.

- [ ] Include intact, localized machinery impact and explicit submerged breach experiments; a fixture declares real canonical compartments/weight ownership and known-zero initial added water.
- [ ] Strict JSON input parsing rejects duplicate keys/NaN. Protect input/output path aliases, emit structured errors and truthful nonzero exit status for partial/canceled computation. Include every input in the result for rerun.
- [ ] CLI subprocess round-trip reproduces fingerprint and physical result; different severity changes identity and damage. Unknown metadata/count edge cases have CLI regression tests.

Run: new unittest cluster plus three CLI fixture invocations into the task output directory, not tracked result files.

## Task 3 — Owner-scoped queue bridge

**Create:** `web/backend/plimsoll_web/damage_lab_runs.py`, `web/backend/tests/test_damage_lab_runs.py`.
**Modify only as needed:** `main.py`, `runs.py`, `worker.py`.

**Consumes:** Task 1 normalized identity, current `CalculationRun`/immutable revisions, authentication and cancellation protections.
**Produces:**

```
POST /api/projects/{project_id}/damage-lab-runs
GET  /api/projects/{project_id}/damage-lab-runs
GET  /api/damage-lab-runs/{run_id}
POST /api/damage-lab-runs/{run_id}/cancel
GET  /api/damage-lab-runs/{run_id}/export?format=json|csv
```

Create body: `{revision, condition_id, experiment}`. Route envelope matches existing run metadata, with damage-lab payload typed separately. A defaults/read endpoint may be added to prepare a sourced experiment from existing canonical compartments without inventing absent geometry.

- [ ] Test Bob cannot read/cancel/export Alice's run, wrong saved revision is 409, invalid experiment is 422, origins/CSRF retained, one-active limit shared with analysis.
- [ ] Distinguish request kind by schema and isolate analysis listing/report/export from lab result shapes. Preserve existing analysis request/response semantics.
- [ ] Extend the bounded compute dispatch and serializer only at its seam, keeping process cleanup, result-size limit, lease/CAS identity and cancellation rules.
- [ ] HTTP + actual worker fixture reaches a real complete or truthful partial core result; JSON/CSV downloads include matching frozen identity.

Run: set `PYTHONPATH=tools`, then `web/backend/.venv/Scripts/python.exe -m pytest web/backend/tests/test_damage_lab_runs.py web/backend/tests/test_runs.py web/backend/tests/test_audit_run_races.py -q`.

## Task 4 — React workflow and replay model

**Create:** `web/frontend/src/damageLab/` focused types, API adapter, draft/replay model, page and scoped stylesheet; focused tests.
**Modify:** `api.ts` (export the existing authenticated call helper, or add typed methods there), `App.tsx`, `portfolio/routes.ts`, one discoverable project/library entry.

**Consumes:** Saved project and Task 3 endpoints. No synthetic success payload in production.
**Produces:** `#/damage-lab/<project-id>`, setup, asynchronous execution, result inspection, timeline and export.

- [ ] Pure replay tests: simultaneous events advance separately; rewind restores the actual earlier state; stopped native trajectories cannot be scrubbed past their final accepted state.
- [ ] Page tests: queued/running/completed/partial/failed/canceled; changed project/condition/draft retires old response; cancel/unmount cleans polling; null values stay unavailable; no old damage panel under a new draft.
- [ ] Accessible project/loading/target controls and explicit game estimate inputs (severity, radius, duration, optional breach area/Cd and crew/rules). Allow editing/export/import of full experiment JSON where needed rather than silently hiding configuration.
- [ ] Default equipment/station placeholders are explicitly estimated; absent compartments produce unavailable state, unknown crew/power stays null until explicitly edited; the synthetic demo is an explicit project import rather than a silent ship replacement.
- [ ] Surface meaningful blocking diagnostics and unavailable layout; offer an explicit synthetic demo import through existing project import API.
- [ ] Implement playback pause/play/speed/next event and selection; snapshot state owns all displayed module/crew values.

Run: `npm.cmd --prefix web/frontend test -- --reporter=dot` and production build after Task 5.

## Task 5 — Three.js inspection surface

**Create:** lazy `DamageLabScene.tsx`/scene controller inside the new feature; geometry/projection helper tests.
**Modify:** frontend `package.json` and lockfile only for `three` and `@types/three`.

**Consumes:** Canonical geometry/layout, replay snapshot, selection and stable callbacks.
**Produces:** large orbitable/zoomable inspector, distinct compartments/equipment,
section/transparent inspection, selected damage, core water/attitude and impact marker.

- [ ] Render from canonical hull/compartment geometry with explicit coordinate adapter. Unit-test mapping `(1,2,3)->(1,3,-2)` and datum handling.
- [ ] Module click updates the HTML inspector; HTML list selection updates the scene. Orbit drag must not become an impact/selection click.
- [ ] Keep fills/labels legible, blue water, restrained damage accent; avoid arbitrary decorative grids or a final-damage fade.
- [ ] Dispose all resources/listeners/RAF/ResizeObserver/OrbitControls; WebGL unavailable/context loss has visible fallback and leaves the report usable. Respect reduced-motion and do not import/render a scene on portfolio routes.

Run: frontend full test cluster and `npm.cmd --prefix web/frontend run build`; inspect emitted chunks to confirm lazy Three.js.

## Task 6 — Independent local acceptance

Codex runs the commands itself, reads changed files and tests a genuine browser workflow. Worker report alone cannot close the task.

- [ ] Core lab/bridge cluster, full backend suite, full frontend suite/build; relevant existing core flooding/loading tests if no kernel changed.
- [ ] Start/reuse loopback services with an isolated migrated acceptance database and a functioning calculation worker; do not alter the user's existing data or services.
- [ ] Import synthetic demo, configure one impact, compute, select modules/crew, orbit, scrub/step, export, edit and rerun. Confirm stale result disappears and unchanged repeat has same identity.
- [ ] Retain desktop screenshot and acceptance JSON/report in task output directory. Report the simplified game damage/crew limits and any unavailable empirical/real-time validation.
- [ ] Confirm protected dirty hashes unchanged and legacy Unity/core formula files untouched.

No git integration step this round.
