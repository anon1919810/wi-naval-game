# Native Armament and Vessel Overview Implementation Plan

> **For agentic workers:** User explicitly chose autonomous execution with OpenCode implementation and Codex acceptance. Use the existing opencode-delegate workflow; no additional confirmation or implementation subagents. Checkboxes track deliverables.

**Goal:** Show the native vessel configuration as one readable design, with editable armament composition and immutable report/compare views.

**Architecture:** Pure readers of supported native results feed a compact overview and five-bank composition reader. Existing host owns commands, saved baseline and field reveal. Existing report owns frozen stage identity and comparison compatibility.

**Tech Stack:** Existing React/TypeScript, SVG/canvas, Vitest/Vite. No dependencies.

**Spec:** `docs/superpowers/specs/2026-10-18-vessel-overview-design.md`

## Global constraints

Frontend-only; preserve the starting 37 dirty paths and existing armour/feedback behavior. No staging/commit/push/deploy, new dependency, queue or physics calculation. Only selected ledger masses in t; source battery masses long_ton, projectile lb, normalized lengths ft/thickness in. Unknown is not zero. Consolidated tests.

## Review focus

- Same barrel count with distinct 15-way selectors remains distinguishable; missing/duplicate bank identities do not reorder batteries.
- Mixed source page scales do not change normalized output unit interpretation; source estimates are not selected ledger masses.
- Failed queued command retaining pending=1 withholds data as failed, not pending/stale; selection preserves keyboard focus.
- Frozen comparison observes existing identity gates and comparison-minus-current direction, including categorical selector changes.
- Standalone XML/downloads and actual 390px parent-grid sizing both work, with complete CJK labels.

### Task 1: Pure readers and focused contracts

**Files:** Create `web/frontend/src/components/armamentModel.ts`, `vesselOverviewModel.ts`; create `src/__tests__/armament-overview.test.ts`. Reuse shipDesign/sps3b3Model/units and compareFrozen helpers.

**Interfaces:** `buildArmament(result:unknown,baseline?:unknown)` yields five ordered bank records, distinct two-group source facts, returned source estimates and global ledger roles, supported/problem/change state. `buildVesselOverview(result:unknown)` yields six chapter sections of labelled facts with explicit unit identities; no formulas or API.

- [x] Add/run compact failing contracts for native gates; scrambled/missing/duplicate bank identities; zero vs unknown; distinct selectors/layoutNone; source FT/IN/LT/LB vs metric ledger; baseline dimension/selector/policy changes; immutable input.
- [x] Implement readers, preserving source declarations and never partitioning ledger masses. Validate with real native reference `outputs/vessel-overview-2026-10-18/native-reference.json` in the chat folder.

### Task 2: Interface and exports

**Files:** Create `components/ArmamentComposition.tsx`, `armamentExport.ts`, `VesselDesignOverview.tsx`, `i18n/vesselOverview.ts`, `styles/vesselOverview.css`; create `__tests__/armament-overview-ui.test.tsx`.

**Interfaces:** `<ArmamentComposition result baseline? state contextLabel? runId? onEditField?>`; `<VesselDesignOverview result state contextLabel? runId? onOpenChapter?>`. Use ready/pending/failed/frozen semantics as ArmourDiagram. Pure `armamentSvg` returns complete XML and existing download helpers write SVG/PNG.

- [x] Pin focused UI behaviors: error/pending gating; select via keyboard and retain focus; Edit returns gunN_calibre; manual ledger is separate; safe unsupported/frozen behavior; XML parser and full five-bank export independent of selection; visible SVG/PNG errors.
- [x] Implement restrained specification-sheet overview and two-group composition, complete EN/ZH choice copies, responsive internal scrolling, self-contained exports. All hooks before conditional returns.

### Task 3: Existing host and frozen comparison integration

**Files:** Modify `components/ShipDesignEditor.tsx`, `pages/Workbench.tsx`, `components/Sps3b3Readings.tsx`, `pages/Report.tsx`; optionally small extension of `components/DesignFeedback.tsx` and its model for compatible configuration view.

**Interfaces:** Overview chapter receives settled host result and real chapter callback. Guns chapter passes compatible saved baseline and reuses its reveal token for bank edit. Native frozen readings receive only their saved stage. A compact configuration table consumes existing compatible `compareFrozen` output / frozen facts, plus report run identity verdicts; current and comparison columns must be explicit.

- [x] Integrate the live overview and guns composition, avoid duplicate full frozen diagram on live overview while retaining result/history navigation. Preserve physical project behavior.
- [x] Add read-only overview/armament to native frozen report and configuration comparison using existing compatibility gates and labels. Preserve old exports and all armour behavior.

### Task 4: One assembly gate and independent acceptance

- [x] OpenCode runs `npm.cmd --prefix web/frontend test -- --pool=threads --maxWorkers=2 src/__tests__/armament-overview.test.ts src/__tests__/armament-overview-ui.test.tsx`, then `npm.cmd --prefix web/frontend run build`; report changed files and unresolved limits.
- [x] Codex reviews increment and runs these + impacted native/feedback/report tests in one batch/build; fix-specific reruns only. Actual browser/API/worker, downloads/visual/mobile and immutable source/history acceptance follow after assembly. See delivery record for the 167 impacted cases, one scoped test-query fix and final copy-only build.
- [x] Save delivery/evidence and status. No commit, push or deploy. See `docs/plimsoll-1.0/vessel-overview-2026-10-18.md` and matching evidence JSON.
