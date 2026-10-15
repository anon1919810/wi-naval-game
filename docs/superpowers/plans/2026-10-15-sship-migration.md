# SpringSharp 3.0 Migration Implementation Plan

> For agentic workers: Codex owns scope, review and acceptance; OpenCode implements the two bounded units. User explicitly requested continuing with .sship migration. No execution-method reconfirmation, commits or deployment.

**Goal:** Preview and migrate supported SpringSharp 3.0 files into editable, source-preserving Plimsoll projects through CLI and the existing web import workflow.

**Architecture:** A pure bounded positional parser/projection owns original bytes and mapping provenance. CLI and authenticated web adapters call that same parser. Web save reparses frozen original bytes and checks the current preview digest before creating a new project.

**Tech stack:** Existing Python standard library, pytest, FastAPI/SQLAlchemy, React/TypeScript/Vitest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-15-sship-migration-design.md`.

## Global constraints

- Preserve the existing 85 dirty-file baseline at chat `work/plimsoll-sship-migration/baseline.json` and backups. This is already a linked worktree.
- No staging, commit, reset, clean, dependency installation, config changes, deploy, unrelated refactor or rewriting prior F08/F06 code.
- Original recovered C# remains outside product source. Local field evidence may be read, not copied as executable code into product.
- First supported format is exact 3.0 headers with dot/comma decimal; 2.0/1.x/unknown versions explicitly rejected.
- New projects are drafts with unknown geometry, incomplete ledger/CG and no fabricated offsets, positions, ballast or balance assumptions. Archive original bytes/notes/fields.
- Workers run only focused commands below; Codex runs independent oracles, broad regressions, browser/worker acceptance and protection checks.

## Review focus

1. Mixed scale selectors, grouped locale numbers, shell pounds and misc long tons cannot silently change dimensions.
2. Duplicate mount positions must follow the original final-occurrence precedence; padding cannot become real inputs.
3. Preview, cancel, replacement file, delayed response and rapid double-save must not mix a source filename, bytes, digest or project.
4. No input/existing output overwrite, partial database import or preview project creation; source/hash/archive survives export/reimport.
5. Unsupported conceptual layout/count/model domains produce visible preserved drafts, not fabricated weight/CG, whole-SPS parity or a physical success claim.

## Unit 1 Core conversion and CLI

**Create:** `tools/plimsoll/sship_import.py`, optional focused `sship_fields.py`/`sship_mapping.py`, `tests/test_sship_import.py`, `tests/test_cli_sship.py` and labelled synthetic fixture files if useful.
**Modify:** `tools/plimsoll/app.py` only to register/handle `import-sship`; preserve existing analysis/verify/publication behavior. A short CLI_README section may be added after focused tests pass, no other docs.

**Consumes:** spec, original MainForm/Hull/Gun/Weapons/Freeboard/Engine/Armour evidence, existing project_io/concept_design/units contracts.
**Produces:** exact `sship_import.preview(data, *, filename)` contract and source archive specified in the design; `SshipImportError.diagnostics`. Canonical project validates, is immutable relative to input, and does not auto-adopt estimates.

- [x] Write meaningful failing tests for registry positions, both decimal headers/encodings/newlines, independent mixed units, duplicate precedence, G1/G2 count consistency, unsupported-domain draft behavior and exact original byte/notes preservation.
- [x] Run red before implementation; save a bounded log outside product.
- [x] Implement bounded passive parsing and projection through existing canonical validation. Include sourced editable hull/metadata/weapons/armour/propulsion/misc facts, supported unadopted concept models and explicit limitations.
- [x] Write failing CLI tests for preview/conversion, malformed input and source/existing/symlink/hardlink destination protection; implement thin adapter.
- [x] Run focused green and stop. Report exact files, counts, mapping limitations and outstanding concerns.

Acceptance (PYTHONPATH=repo/tools, existing backend venv python):
`python -B -m pytest -q -p no:cacheprovider tools/plimsoll/tests/test_sship_import.py tools/plimsoll/tests/test_cli_sship.py tools/plimsoll/tests/test_project_io.py tools/plimsoll/tests/test_concept_design.py tools/plimsoll/tests/test_concept_unknown_inputs.py`

## Unit 2 Authenticated web preview and save

**Create:** `web/backend/plimsoll_web/sship_imports.py`, `web/backend/tests/test_sship_import.py`, `web/frontend/src/components/sshipFile.ts`, optional `SshipMigrationPreview.tsx`, `web/frontend/src/__tests__/sship-import.test.tsx` and helper tests.
**Modify:** backend main.py route/models only, frontend ProjectImport.tsx, api.ts, types.ts, workspace.ts. Only narrowly justified updates to existing import tests. Preserve prior dirty changes and JSON import behavior. No shared core files.

**Consumes:** Unit 1 API. Expose standard ProjectImportPreview plus optional migration source/fields/counts/diagnostics/limitations, no converted project payload needed by browser.
**Produces:** `/api/projects/sship-preview` and `/api/projects/sship-import` with `source_sha256` required on save, and the existing ProjectView. Same origin/CSRF/auth and 8 MiB middleware unchanged; 1 MiB decoded source bound.

- [x] Write/run red backend tests: preview no rows, invalid/base64/size/version, stale digest refuses without writes, save reparses/retains original, new owner UUID/revision and isolation.
- [x] Add thin endpoints/service calling the core; never trust client mapping/project and do not change database schema/config.
- [x] Write/run red component tests for bounded binary read, locale-preserving original bytes, preview/cancel/reselect/stale responses/digest, one save/new name, failure/retry and unmount/busy coordination with existing JSON/template creation.
- [x] Integrate separate SpringSharp chooser and migration details into existing ProjectImport. English/Chinese copy and existing styles; no page redesign.
- [x] Run focused green and stop; report files, counts and limitations. No broad suite/build/browser from worker.

Acceptance:
Backend: `python -B -m pytest -q -p no:cacheprovider tests/test_sship_import.py tests/test_project_import.py` from web/backend with tools+backend PYTHONPATH (use exact existing import-test file names discovered in repository).
Frontend: `npm.cmd test -- --maxWorkers=1 src/__tests__/sship-import.test.tsx src/__tests__/project-import.test.tsx` plus the exact new helper-test file if separate (discover existing import test name rather than guessing).

## Codex final acceptance

- [x] Read actual changed files, review returned state/outcome; reject specific defects in the same OpenCode session, at most two failed review rounds before taking bounded repairs inline.
- [x] Independently test source-derived synthetic files with fixed expected conversions, counts and exact archive/notes, plus adversarial boundaries; identify any real user sample separately.
- [x] Run appropriate core/backend/frontend regressions and production build; current source identity verified by final quick if packaged Python source changed. Do not repeatedly rerun unchanged long stress suites.
- [x] Real chooser -> preview -> cancel/reselect -> name -> save/open -> edit -> calculate/estimate -> canonical export/reopen in isolated local harness; validate missing physics and no source overwrite.
- [x] Independent final code review and baseline protection check. Update current status/coverage as a new checkpoint without rewriting frozen 191-row inventory or older evidence.
- [x] Deliver acceptance JSON, report, converted controlled samples and evidence under chat outputs/Plimsoll-sship-migration-2026-10-15. No live deployment or commit.


## Execution acceptance note

OpenCode implemented the two units; its core run was interrupted and not accepted after independent review still found defects. Codex completed bounded semantic repairs using observed red/green tests. Final evidence is in the chat outputs/Plimsoll-sship-migration-2026-10-15 directory. The native browser download attempt and an independent persistent Blob probe were both canceled; exact canonical API JSON export and browser restoration were accepted instead. This limitation remains explicitly unverified and is the first follow-up task, not a native-download success claim. No commits or deployment.
