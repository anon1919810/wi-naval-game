# Weight explanation and report delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. OpenCode implements this current-checkout increment; Codex owns scope, review and acceptance. User has approved autonomous execution; no additional approval stop or worker commit/deploy.

**Goal:** Explain the existing managed mass ledger, compare every frozen role, and deliver readable native A4 design reports while preserving complete-report printing.

**Architecture:** One pure weight projection and comparison model read saved native payloads; a shared reader serves live/frozen hosts and reveals existing role controls. Report-only print scope and stylesheet reuse the existing print lifecycle, preserving frozen identity and screen state.

**Tech Stack:** Existing React19, TypeScript, CSS/SVG, Vitest; no dependency/API changes. Model opencode/deepseek-v4.1-flash-free.

**Spec:** docs/superpowers/specs/2026-10-19-weight-report-design.md

## Global Constraints

- Base b48ed8d9d03243f184aa124b61ab45ea9d93b14b; only these two planning docs start dirty. Hull/freeboard source3a5bc9f is live; prior data preserved. No git commits, push, deployment, model/provider edits or re-delegation by worker.
- Only web/frontend/src and new delivery docs. Core/backend/deploy/dependencies and existing output evidence remain untouched.
- Support native schema/method/available|partial strictly; reuse envelope and comparable-pair gates. All saved masses in this model are t; no LT relabeling, default CG or inferred unknown0.
- Six presentation groups use the exact role mapping in the spec. Unknown extra roles survive; unknown/negative/zero/optionalother remain distinct. Authoritative total/balance is read, not rebuilt from group sums.
- Only existing commands write a design. Selection is read-only; role reveal must land on real existing controls. Frozen views never preview or reveal an editable host.
- Duplicate role identity always produces one explicit conflict row, even if repeated values match: no first-wins or sum. Its quantities/policy/bindings/deltas are unknown; affected group totals and frozen differences stay unknown, it is not optionalother and has no role-edit action. Preserve id/conflict explanation and authoritative balance.
- Native design print scope is local; full scope and physical printing preserve prior behavior. Actual PDF rendering is a parent acceptance gate, not a worker success assumption.

## Review Focus

- A role absent/unknown on either side must not acquire zero; a mode/binding change with equal mass remains a real categorical change.
- Optional other and new unknown roles must not be omitted, double-counted, or block a legitimate complete ledger.
- Pending/failed host and incompatible frozen envelope/basis must not quote stale numbers through either the new view or a left-visible legacy table.
- Print after a previous print, print after switching scope, and afterprint restore must keep original screen details/unit state; compact scope must not walk a hidden source appendix.
- SVG minimum widths, table scroll, long identity labels and inherited dark colors must not clip A4 output or force microscopic whole-report scaling.

## Files and interfaces

- Create components/weightBreakdownModel.ts: `readWeightBreakdown(result:unknown,baseline?:unknown)` with supported/problem, own basis/complete/balance, ordered roles/groups, own mode/item_ids/estimateT/selectedT/adoptionDeltaT, strict changed flags, totals explanation; and `weightComparisonRows(current:unknown,comparison:unknown)` producing complete ordered union with comparison-minus-current deltas and own policy/bindings. Reuse shipDesign ledger helpers and native constants. No mutable module accumulator.
- Create components/WeightBreakdownReadings.tsx: `WeightBreakdownReadings({result,baseline?,state?,contextLabel?,runId?,onEditRole?})`, state ready|pending|failed|frozen. Stable data-weight-breakdown/data-state, data-weight-group/data-weight-select, data-weight-role/data-weight-edit/data-changed. Render accessible paired bars plus complete reachable group/role readings; frozen has no edit/selection affordance. SVG and table formatted quantities must match the same mass prefs.
- Create components/WeightRoleComparison.tsx: table from the pure comparison rows with explicit side labels, policy/bindings and both deltas; stable data-weight-comparison/data-weight-comparison-row. Four readable columns with stacked quantities are acceptable for A4; complete rows/header remain printable.
- Create i18n/weightBreakdown.ts with typed complete EN/ZH, including print-scope copy; reuse shipDesignRoleLabel for role ids. Create styles/weightBreakdown.css and styles/reportPrint.css using existing theme tokens and report-only print rules. Do not redesign fonts/global site.
- Modify components/ShipDesignEditor.tsx ShipDesignLedgerSection to mount reader, own stable role-reveal ref/event callback to open `.sps-bindings` and focus existing role control; retain bindings/declared mass/position flows and avoid duplicate leading totals. Current real controls are `.sps-ledger-role[data-role]`, RoleBinding and DeclaredMassRow with `data-item`.
- Modify pages/Workbench.tsx to pass the same scoped saved.result baseline to ShipDesignLedgerSection already used by hull/armour. No new preview fetch.
- Modify components/Sps3b3Readings.tsx to mount frozen gated weight reader and mark native duplicate original text/native-key/provenance sections as secondary for design-scope paper only. Screen and exports remain complete; compatibility nonnative behavior remains.
- Modify components/DesignFeedback.tsx to mount full WeightRoleComparison from already gated frozenNativeSides. Preserve 16 reading specs, direction and current/compare validity checks. Avoid repeated frozen role block; draft role feedback remains.
- Modify pages/Report.tsx and components/useReportPrint.ts to add local scope choice/default and report identity strip, defer appendix only when the selected scope needs it, apply paper marker and preserve beforeprint/afterprint lifecycle. Existing physical report-print.test.tsx cases must continue to pass. Inline print controls are sufficient; do not add a generic settings framework.
- Create __tests__/weight-breakdown.test.tsx (pure+UI; split only for readability), extend report-print.test.tsx where real lifecycle behavior is new. Candidate delivery docs/plimsoll-1.0/weight-report-2026-10-19.md must clearly await independent parent/browser/PDF acceptance.

## Task 1: Managed weight reading and real role reveal

- [ ] Write focused tests for supported/partial vs unavailable native status, finite/unknown/zero/negative, missing/duplicate/extra roles, optionalother, strict complete, group incompleteness and direct authoritative totals. Pin source estimate5800/selected6000 => adoption200 without altering balance.difference.
- [ ] Run `npm test -- src/__tests__/weight-breakdown.test.tsx` once to establish expected failing behavior.
- [ ] Implement the pure projection and paired-bar reading with changed/saved baseline behavior and complete EN/ZH. Unknown group amounts must stay unknown; chart must accommodate negative values, no invented fractions.
- [ ] Mount in the existing ledger section and pass saved baseline. Test selecting a category makes no command, explicit role reveal opens/focuses the actual control, pending/failed suppress new values/actions, frozen is read-only.

## Task 2: Complete frozen weight-role comparison

- [ ] Add focused cases for current6100/compare6000 => selected delta−100t, independent estimate delta, policy/binding-only changes, known→unknown, unknown extra role and incompatible basis/status.
- [ ] Implement ordered complete comparison rows/table, gate at FrozenDesignSummary pair, retain side identity and16readings. Reuse dictionaries/units and avoid live project lookups.
- [ ] Mount frozen weight reader behind existing envelope gate; failed/unrequested/mismatched kernel cannot quote a readable-looking residual payload.

## Task 3: A4 design/full print scope

- [ ] Extend real lifecycle tests for native defaultdesign, explicitfull appendix, repeatedbeforeprint, switching scope, afterprint restore, absence of raw JSON, unchanged snapshot/units; preserve existing physical defaultfull cases.
- [ ] Add local report scope control and clear save-as-PDF wording, read-only paper identity and scoped A4 stylesheet. Design scope removes duplicate native original/key/provenance material only from paper, never required diagnostics or requested physical stages; full preserves original appendix.
- [ ] Handle all current diagrams and role/config comparison tables. Print SVGs fit aspect ratio with all content and readable text; if necessary render print-only sections/tables from the same pure data. No new server PDF endpoint or UI implementation jargon.
- [ ] Run one final related cluster below, then npm run build. Only retry files implicated by actual failures; no unchanged core/backend full suites.

```text
npm test -- src/__tests__/weight-breakdown.test.tsx src/__tests__/report-print.test.tsx src/__tests__/report.test.tsx src/__tests__/report-navigation.test.tsx src/__tests__/report-comparison.test.ts src/__tests__/native-report-readings.test.tsx src/__tests__/native-report-metrics.test.ts src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx src/__tests__/ship-design.test.tsx src/__tests__/hull-freeboard.test.tsx src/__tests__/workspace-lazy.test.tsx
npm run build
```

## Parent final acceptance

One read-only code review, one independent related cluster/build. Isolated real API/worker/browser: baseline run, group/role reveal, machinery6000→6100t plus one binding/pending-error recovery, save/reload/run2/frozen comparison and old run preservation; EN/ZH and390px/dark. Generate actual EN/ZH design PDFs and one full PDF through beforeprint/afterprint; extract and render/inspect for A4, font/identity/role completeness, graph clipping, repeated headers and screen restore. Record source/runtime preservation and artifacts, close owned processes, leave this increment uncommitted/undeployed.
