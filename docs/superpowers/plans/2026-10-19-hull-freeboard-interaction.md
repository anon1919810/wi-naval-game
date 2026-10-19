# Hull and freeboard interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. OpenCode implements this bounded increment in the current checkout; Codex owns scope, review and acceptance. No worker commits or deployment.

**Goal:** Make the native hull/freeboard chapters readable and interactive while preserving source computation and frozen result identity.

**Architecture:** A pure native-result projection reads normalized hull/freeboard, own driver/lock declarations and existing balance. One typed bilingual reading component and one shared SVG serializer serve live and frozen contexts; field reveals and all mutations use the existing native host.

**Tech Stack:** Existing React 19, TypeScript, CSS, Vitest; existing SVG/PNG download functions. No dependencies.

**Spec:** `docs/superpowers/specs/2026-10-19-hull-freeboard-interaction.md`

## Global Constraints

- Base cc194c2dedc8b23823f70624f7b4b0dbe9bdf475; only the two new planning docs are initially dirty. Work in the current repo, preserve them. Prior release 1ee8415 is live.
- Only web/frontend/src and documentation. No core/backend/deploy/package/model/provider edits, no new APIs or ship formulas, no commits/push/deploy.
- Native result schema/method and payload available|partial are mandatory. Pending/failed suppress values and actions. Preserve zero/false/unknown, negative freeboard, manual ledger masses and all legacy compatibility exports.
- Normalized lengths ft, source displacement LT, hull edit overall_length is in its saved hull page unit, normal_displacement_lt is LT; lengthBow and freeboard_length_bow are deg. Compare normalized source values; display conversions do not write design values.
- One initial focused test, one combined related batch/build at finish; only rerun a failed file or genuinely changed boundary. Approximately 18–24 new meaningful cases; no matrix, no full core/backend suites.

## Review Focus

- Missing or false driver/lock does not silently become a default, and unavailable payload residuals are not quoted.
- Freeboard coordinates need declared station inputs. Guard legacy helper's missing bow/stern zero fallbacks in this new reader; leave legacy helper behavior unchanged.
- Flush/raised presets under depth lock preserve source snapshot priority; no impossible edit affordance for the four pinned FD/AD endpoints.
- Coincident points remain independently selectable through the endpoint list and keyboard; selection does not replace focused SVG markup.
- Frozen status/kernel/basis failures withhold new readings/config, and downloaded output contains all endpoints regardless of selection.

## Files and interfaces

- Create `components/hullFreeboardModel.ts`: `readHullFreeboard(result: unknown, baseline?: unknown)` returns supported/problem, hull facts, strict own drivers, own lock, eight keyed endpoints with real edit fields and changed flags, four source fractions, guarded `FreeboardGeometry | null`, balance facts. Import FREEBOARD_ENDPOINTS/readFreeboardGeometry/profile mappings, never copy physics or silently infer absent source values. Use 1e-6 only for drawing fraction-domain tolerance, not for altering facts/highlights.
- Create `components/HullFreeboardReadings.tsx`: exports `HullReadings` and `NativeFreeboardProfile`; common props result, baseline?, state ready|pending|failed|frozen, contextLabel?, runId?, onEditField?. Stable attributes `data-hull-readings`, `data-freeboard-profile`, `data-freeboard-point=<source output key>`, `data-freeboard-select`, `data-freeboard-edit=<source parameter>`, `data-state`, `data-changed`. Frozen has no selection/edit affordance; export buttons may remain.
- Create `components/freeboardProfileSvg.ts`: escaped self-contained SVG serialization from the same projection used onscreen, showing all endpoints and context; per-instance ids. Import generic usable `downloadArmourDiagramSvg`, `downloadArmourDiagramPng` and filename sanitizer for downloads rather than duplicating browser rasterization. Keep SVG focus nodes stable while selection changes through React state/CSS.
- Create `i18n/hullFreeboard.ts` and scoped `styles/hullFreeboard.css`; typed complete EN/ZH, current fonts/theme, compact diagram with endpoint list/panel, no new UI framework.
- Modify `ShipDesignEditor.tsx`: hull and freeboard new views above source fields, share existing reveal token, replace native legacy profile rather than show two. No new queue or effect that edits a value.
- Modify `pages/Workbench.tsx`: pass the same scoped saved baseline to hull/freeboard as guns/armour already use. Do not alter currentRun or physical project routes.
- Modify `Sps3b3Readings.tsx`: gated native hull/profile plus existing propulsion/performance; legacy nonnative SpsFreeboardProfile unchanged. Existing gate `propulsionEnvelopeGate` is envelope-only and reusable; model still independently validates payload.
- Modify `sps3b3Model.ts` only for `resolvedUnit(field.name === 'freeboard_length_bow') => 'deg'`, before generic scale handling. No value conversions or source catalogue mutations.
- Modify `designConfigModel.ts` and its existing dictionary: group freeboard, the three extra hull facts, strict own driver/lock labels, eight endpoint lengths and four source fractions displayed as percentages. Reuse numeric/categorical row rendering and canonical LT support; do not change summary reading count or comparison gates.
- Create `__tests__/hull-freeboard.test.tsx` (split pure/UI only if readability needs it). Extend existing tests only where actual interfaces/assertions changed.
- Create candidate delivery note `docs/plimsoll-1.0/hull-freeboard-2026-10-19.md`, explicitly no independent acceptance until parent writes it.

## Task 1: Reading model and hull chapter

- [ ] Add focused tests for strict native status/method/schema, zero/unknown/false, driver declarations, page-vs-normalized units and source LT vs ledger t; show failing behavior before implementation.
- [ ] Run `npm test -- src/__tests__/hull-freeboard.test.tsx` from web/frontend once for initial behavior.
- [ ] Implement projection and HullReadings, mount it with existing field callbacks. Hull fields are length_waterline, beam_moulded, beam_at_bulges, draught_normal, block_coefficient_normal. LOA and displacement remain readings with current driver controls above; don't create a callback to a nonexistent catalogue field.
- [ ] Correct only the bow-angle unit display and test it under both hull scales.

## Task 2: Interactive freeboard and export

- [ ] Test eight identities (including equal coordinates), point selection/reveal without mutation, changed reset with baseline, known negative and zero heights, missing offsets/fractions, pending/failed suppression, and locked FD/AD behavior.
- [ ] Implement serializer and component using existing geometry functions. The full endpoint list and selection panel carry detailed labels; diagram labels may be compact to prevent collisions. Guard drawing readiness without removing independent known facts.
- [ ] Retain PNG and add SVG from the same all-endpoint serialization, escaped context and labels, explicit white background and source/display unit names. Show errors instead of silent failures; neither selection nor edit callback changes an export's content scope.

## Task 3: Frozen report and comparison integration

- [ ] Test readonly/report envelope mismatch and unavailable residual rejection, own-result driver/lock extraction, comparison sign and units, bilingual keys/export escaping.
- [ ] Mount new frozen views behind existing envelope gate; hide legacy profile only for native results. Extend existing config rows for new hull/freeboard fields; preserve snapshot identity/method/basis gates and original 16 reading specs.
- [ ] Run once from web/frontend: `npm test -- src/__tests__/hull-freeboard.test.tsx src/__tests__/armour-diagram.test.ts src/__tests__/armour-diagram-ui.test.tsx src/__tests__/propulsion-performance.test.tsx src/__tests__/ship-design.test.tsx src/__tests__/sps3b3.test.tsx src/__tests__/design-feedback.test.ts src/__tests__/design-feedback-ui.test.tsx src/__tests__/native-design-projection.test.tsx src/__tests__/workspace-lazy.test.tsx` then `npm run build`. Confirm the two existing armour test filenames before running; do not broaden to all suites. Report exact results/files and limitations.

## Codex final acceptance

Read-only review once, independently run the related cluster/build, then use localhost isolated SQLite and real API/worker/browser to select/reveal/change two endpoints and a hull input, exercise one preset and depth lock, retain manual machinery mass, save/reload, calculate two revisions, compare frozen reports, download EN/ZH SVG+PNG, check 390px and one delayed/failed preview recovery. Preserve baseline run and all core/backend/deploy hashes. Record tested/unverified states; no full unchanged matrices or automatic second deployment.
