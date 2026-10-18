# Native Armour Diagram Implementation Plan

> **For agentic workers:** Use the existing OpenCode delegation workflow. Steps use checkbox (`- [x]`) syntax. User has already authorized autonomous execution and final consolidated acceptance.

**Goal:** Explain native armour dimensions and weights visually, connect to the real editor, and derive frozen/exportable diagrams.

**Architecture:** One pure result reader feeds one SVG renderer and its selection/export UI. Workbench supplies settled preview and compatible saved baseline; saved result rendering supplies only its frozen native payload. Preserve the same authoritative design and ledger.

**Tech Stack:** Existing React/TypeScript/SVG, browser canvas, Vitest/Vite. No dependencies.

**Spec:** `docs/superpowers/specs/2026-10-18-armour-diagram-design.md`

## Global constraints

Frontend-only. No physics/backend/auth/persistence/source event changes; no dependencies/config/git writes/deployment. Preserve prior dirty batch (snapshot in task outputs). Do not portray unspecified positions as known placement. Consolidated tests, not field matrices.

## Review focus

- Mixed source page units vs normalized ft/in: display conversion once, never change source units.
- Missing/zero/invalid lengths and fractions: no guessed/clamped geometry or mass.
- Pending/error previews and saved baseline identity: no stale diagram/export or wrong highlights.
- Collapsed source fields: selecting Edit must actually reveal and focus, preserving input/queue state.
- Old/frozen results and exports: no live reads/mutations, no app-CSS-dependent image.

### Task 1: Pure diagram reader and shared freeboard geometry

**Files:** New `components/armourDiagramModel.ts`; optional focused `components/freeboardProfileModel.ts` if extracting shared geometry; new `__tests__/armour-diagram.test.ts`. Reuse `shipDesign.ts`, native constants and existing normalized freeboard paths in `Sps3b3Readings.tsx`.

**Interface:** `buildArmourDiagram(result, before?)` returns supported status, valid dimension context, per-region known/unknown facts, plotting validity, changed status, ledger readings and balance. Inputs are immutable native results; no API or formulas.

- [x] Add a compact set of contract tests for native gates, ft/in conversion, missing/zero/invalid geometry, all distinct deck selectors, policy-only changes, unchanged unknowns and frozen input immutability.
- [x] Implement the reader and share freeboard coordinate reading without changing the existing freeboard export result.

### Task 2: Renderer, selection and exports

**Files:** New `components/ArmourDiagram.tsx`, `components/armourDiagramExport.ts`, `i18n/armourDiagram.ts`, `styles/armourDiagram.css`, `__tests__/armour-diagram-ui.test.tsx`.

**Interface:** `<ArmourDiagram result baseline? state contextLabel onEditField?>`; render and export only settled supported data. Local selection/display preferences do not mutate projects. Export helper serializes a complete self-contained SVG and rasterizes it to PNG.

- [x] Add focused UI tests for pending/failure export gating, region selection/edit callbacks, changed status reset and standalone export contents/error handling.
- [x] Implement length bands, deck partition schematic, unknown-position/tower labels, selected mass/policy and balance; complete ZH/EN and keyboard support.
- [x] Implement SVG/PNG downloads with explicit colours/background, safe filenames and URL cleanup.

### Task 3: Native editor and frozen report integration

**Files:** Modify `pages/Workbench.tsx`, `components/ShipDesignEditor.tsx`, `components/Sps3b3Editor.tsx` only for targeted reveal/focus, `components/Sps3b3Readings.tsx`; extend bounded host test if needed.

**Interface:** Workbench passes preview state and compatible `saved.result` to the Armour chapter. A targeted reveal token lets `Sps3b3GroupView` open the matching group and focus `[data-field=...]` after it mounts. Native saved readings pass their own frozen result and run id, never preview API.

- [x] Connect region editing to existing fields and queue; preserve Changes panel and all native/physical routes.
- [x] Render frozen read-only diagram and exports; keep original freeboard PNG/text exports.

### Task 4: Consolidated acceptance and handoff

- [x] OpenCode runs `npm.cmd --prefix web/frontend test -- --pool=threads --maxWorkers=2 src/__tests__/armour-diagram.test.ts src/__tests__/armour-diagram-ui.test.tsx`, then `npm.cmd --prefix web/frontend run build`. Report changed files and unresolved limits; no full suites.
- [x] Codex reviews full increment against starting snapshot, runs new tests plus impacted native/feedback/report tests in one batch and builds. Actual UI/API/worker, download/image and preservation checks follow once assembled.
- [x] Save local delivery/evidence and update status. No commit, push or deploy.

Completion: Independently accepted locally on 2026-10-18. Codex repaired concrete final UI/export issues after two OpenCode review rounds, completed one impacted frontend batch with fix-specific serializer reruns, and verified actual downloads, mobile rendering and immutable runs after a later saved revision. See `docs/plimsoll-1.0/armour-diagram-2026-10-18.md`. No commit, push or deployment.
