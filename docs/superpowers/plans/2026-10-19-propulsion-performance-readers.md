# Propulsion and performance readers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user-wide OpenCode workflow applies; Codex owns acceptance. No worker commits or deployment.

**Goal:** Connect existing native engine/performance facts to readable chapters, frozen reports and frozen comparison.

**Architecture:** A small pure reader projects the supported native result into engine and performance sections. Two presentational React readers reuse the existing dictionary, units, chapter reveal and frozen report gates; they never calculate physics or fetch data.

**Tech Stack:** Existing React 19, TypeScript, CSS, Vitest. No dependencies.

**Spec:** `docs/superpowers/specs/2026-10-19-propulsion-performance-readers.md`

## Global Constraints

- Only frontend and documentation. Preserve source physics, backend, deployment and all existing work.
- Source hp and nmi retain source identity; source engine/bunker mass LT, ledger mass t. Never relabel LT as t.
- Unknown, zero, false and absent are distinct. Numeric strings and nonfinite numbers are not known readings.
- Pending or failed preview hides old facts. Frozen readers use only that run's result, never live preview or current host design.
- Reuse existing bilingual enum labels and comparison gates. No new dependencies, safety verdicts, power curves or download features.
- Use only `opencode/deepseek-v4.1-flash-free`; no provider/model edits or paid fallback.

## Review Focus

- Manual machinery/fuel mass differs from source estimate; show both without splitting or adopting.
- Missing lock boolean or locked target does not imply unlocked or zero.
- Warning false is not a general pass; unknown does not imply no warning.
- Failed/mismatched frozen envelope with residual values reveals none.
- Cross chapter navigation preserves draft; frozen readers have no mutation/navigation controls.

## File responsibilities

- Create `web/frontend/src/components/propulsionPerformanceModel.ts`: `readPropulsionPerformance(result: unknown)` returns supported/problem plus engine/performance known facts, strict lock and ledger role readings. No React, I/O or calculations; all numeric units defined next to paths.
- Create `web/frontend/src/components/PropulsionPerformanceReadings.tsx`: exports `PropulsionReadings` and `PerformanceReadings`; props `result: unknown`, `state?: 'ready'|'pending'|'failed'|'frozen'`, `runId?: string`, `onEditField?: (field: string)=>void`, `onOpenChapter?: (chapter:string)=>void`. Absent callbacks render no inert controls.
- Create `web/frontend/src/i18n/propulsionPerformance.ts` and scoped CSS. Typed EN/ZH dictionaries, reuse vessel enum labels and ledger policy labels.
- Modify `ShipDesignEditor.tsx` to mount engine/performance views above fields, reuse its field reveal token. Add optional chapter callback to performance view.
- Modify `pages/Workbench.tsx` only to pass existing chapter navigation to the performance chapter.
- Modify `Sps3b3Readings.tsx` and its `StageStatus.tsx` call to pass parent envelope and gate the new frozen readers; reports must not fetch preview.
- Modify `designFeedbackModel.ts`/dictionary to add seven readings using existing spec extraction and numeric comparison; modify config model/dictionary for frozen shaft/range/lock facts using existing categorical/number rows. Update affected literal reading-count assertions and copy accurately.
- Create `__tests__/propulsion-performance.test.tsx` with approximately 12–20 meaningful cases. Extend an existing test only when an interface/count changed. No combinatorial test matrices.
- Create delivery note `docs/plimsoll-1.0/propulsion-performance-2026-10-19.md` as candidate; worker reports are not independent acceptance.

### Task 1: Pure projection and readable chapters

- [ ] Add focused failing tests for supported/partial/unsupported results; zero vs unknown; exact selectors; locks true/false/missing; machinery/fuel policy and LT vs t; true/false/unknown warning flags.
- [ ] Run `npm test -- src/__tests__/propulsion-performance.test.tsx` from `web/frontend` to demonstrate the missing behavior.
- [ ] Implement the projection and two typed bilingual cards. Source paths verified in `tools/plimsoll/sps_engine.py:140`, `sps_compat.py:765`, `sps_field_catalog.py:279` and `ship_design_mass.py:187`. Use source flags, never repeat their thresholds in JS. No broad refactor.
- [ ] Add pending/failed suppression, field callbacks and readonly tests; hook into native engine/performance chapters. Fields: speed_max_kn, speed_cruise_kn, range_nm, shafts, coal_percentage, trim. Related chapter buttons use existing Workbench goChapter.

### Task 2: Frozen integration and comparison

- [ ] Test readonly frozen views and parent requested/status/kernel mismatch suppression; new frozen readers have no navigation or preview call.
- [ ] Pass optional envelope to native report readings; only new views require that envelope when mounted through StageStatus, standalone pure readers still validate schema/method/status.
- [ ] Extend the existing comparison reading specs with engine.speedCruise (kn), engine.hpCruise (source hp), performance.strengthCross/strengthLong/seakeeping (empirical score), performance.metacentre (ft), performance.rollPeriod (s). Preserve current direction and compatibility gate. Extend config rows with screws, range, lock and target from each result's design.editing.
- [ ] Add comparison assertions for direction, unknown versus false, changed units and rejected pair; retain original tests.
- [ ] Run once the combined related cluster and build. Worker may rerun only the failing file after fixes. Report exact commands/results and changed files. No commits, push, production or user's data.

## Consolidated independent acceptance (Codex)

`npm test -- src/__tests__/propulsion-performance.test.tsx src/__tests__/armament-overview.test.ts src/__tests__/armament-overview-ui.test.tsx src/__tests__/native-report-readings.test.tsx src/__tests__/native-design-projection.test.tsx src/__tests__/ship-design.test.tsx src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx src/__tests__/sps3b3.test.tsx` then `npm run build`, from `web/frontend`. Correct actual existing filenames before running; do not run all tests.

Use an isolated local DB and real worker for synthetic native engine edits, one manual machinery binding, field reveal, save/reload, two runs, frozen report/compare, EN/ZH 390px, and one controlled pending/failure recovery. Inspect changed files and verify no source/backend/production mutation. Record tested and untested boundaries separately.

## Acceptance closure · 2026-10-19

Implementation and independent acceptance completed locally. The planned consolidated cluster passed (10 files / 140 tests, including lazy workspace regression). One substantive review finding on comparison payload status was fixed; only the two affected files were rechecked (33 passing, including 3 added regressions), followed by the final build. Real isolated API/worker/browser acceptance and source preservation passed; native print dialog/pagination remain untested. See `docs/plimsoll-1.0/propulsion-performance-2026-10-19.md` and its evidence JSON. This increment remains uncommitted and undeployed; prior release ae305b2 is live.
