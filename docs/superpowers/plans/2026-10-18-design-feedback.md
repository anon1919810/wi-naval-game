# Design Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. OpenCode implements; Codex accepts.

**Goal:** Make native design changes and frozen comparisons understandable and reduce initial workspace loading.

**Architecture:** Pure readers compare authoritative saved/native result records. A guarded preview hook supplies only the saved Workbench baseline; historical report comparisons use immutable run snapshots. Route splitting is independent of calculation semantics.

**Tech Stack:** Existing React 19, TypeScript, Vite, Vitest, FastAPI pure preview API. No dependencies added.

**Spec:** `docs/superpowers/specs/2026-10-18-design-feedback-design.md`

## Global Constraints

Preserve native source event order, unknown values, method and basis identities, manual mass choices, draft guards and frozen reports. No core/backend changes, new dependencies, git writes or deployment. User requests one consolidated acceptance at the end and fewer repeated tests.

## Review Focus

- Baseline preview returns after a project/save change: discard it, never compare against another project or revision.
- Pending/failed queue still carries last-known results: mark stale, withhold current deltas, retain optimistic inputs and retry.
- Native source units/scales changed: compare recorded physical readings, show correct source input units, no fake parameter deltas across scales.
- Historical runs differ in method/basis/schema/identity: withhold mismatched deltas without hiding the report itself.
- Lazy loading fails or language/theme changes: actual import retry works; never remount a dirty Workbench merely for copy/theme.

### Task 1: Pure comparisons and copy

**Files:** Create focused `components/designFeedbackModel.ts`, `i18n/designFeedback.ts`, `__tests__/design-feedback.test.ts`. Reuse `shipDesign.ts`, `nativeReportReadings.ts`, types/catalog.
**Interfaces:** Before/current native records plus explicit identity/context produce metric rows, changed input rows, changed role rows, and incompatibility reasons; no network or ship formula.
- [x] Write bounded tests for known, zero, unknown, pending, manual mass, source units and identity mismatch; cover strengths using existing saved output path.
- [x] Implement pure readers and localized display contract, retaining unknowns and signs.

### Task 2: Workbench and frozen Report UX

**Files:** New `components/DesignFeedback.tsx`, `components/useSavedDesignPreview.ts`, scoped CSS; modify `Workbench.tsx`, `ShipDesignEditor.tsx`, `Report.tsx`; targeted component/host tests.
**Interfaces:** Workbench supplies saved `view`, draft/host preview and pending/errors; hook returns saved baseline with loading/retry. Frozen report supplies two run views only.
- [x] Add deferred-response tests for saved baseline reset/switch and queue stale result gating, plus frozen comparison/manual role transitions.
- [x] Build compact cards/tables, changed-input/role disclosure, local chapter links, pending/failure/retry status.
- [x] Keep UI focus/leave guards and immutable report comparison identity checks intact.

### Task 3: Route loading

**Files:** Modify `App.tsx`, optional focused lazy-page component; new `__tests__/workspace-lazy.test.tsx` or extend existing shell tests.
**Interfaces:** Route shell chooses lazy component with fallback, failed module state with explicit page reload recovery, mounted route identity stable.
- [x] Add focused tests proving Library doesn't import heavy pages, actual retry and stable draft under language/theme changes.
- [x] Split Workbench and Report; optional Run split only if it helps without circular shared imports. Keep existing shell CSS eager.

### Task 4: Consolidated acceptance and delivery

- [x] OpenCode runs one focused developer batch after assembly: `npm.cmd --prefix web/frontend test -- --pool=threads --maxWorkers=2 src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx src/__tests__/workspace-lazy.test.tsx` (adapt exact new filenames in report), then `npm.cmd --prefix web/frontend run build`. No full suites.
- [x] Codex independently reviews changed files, runs the focused new tests plus impacted existing native, report, queue and shell tests in one command, and builds once. Repair rounds only for concrete failures.
- [x] Codex performs isolated local browser/API/worker flow and reads before/after asset dependency closures; core/backend hashes must match baseline. Save receipts externally.
- [x] Document actual delivered behavior, measurements and verification limits; no commit/deploy, no automatic memory writes.


Completion: accepted locally on 2026-10-18. See `docs/plimsoll-1.0/design-feedback-2026-10-18.md`. A failed dynamic import was proven cached by the browser; recovery uses an explicit reload before the editor mounts. Parent repaired concrete identity/cache defects after the second review round, reran only affected tests, and completed actual browser/API/worker acceptance. No commit, push or deployment.
