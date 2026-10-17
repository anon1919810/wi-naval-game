# Battery Layout Implementation Plan

> **For agentic workers:** Use the user-required opencode-delegate workflow for implementation. Codex owns scope, review and independent acceptance. Steps use checkbox syntax.

**Goal:** Preserve two mount groups, derive SPS position-weighted freeboard/height and offer one explicitly adopted mixed-armour mass.

**Architecture:** Optional `concept_design.battery_layouts` references existing battery rows. A separate pure kernel owns layout and paired armour; existing v1 component estimates retain their identities. Existing systems proposals and atomic selected-condition adoption are reused.

**Tech Stack:** Existing Python core/FastAPI/React/TypeScript; no new dependencies.

**Spec:** `docs/plimsoll-1.0/battery-layout-contract.md`.

## Global Constraints

- Preserve published baseline `7ce1cb9` and legacy numeric outputs; no commit/push/deploy in implementation sessions.
- Unknown is not zero. Reject contradictory declared facts; incomplete drafts remain saveable.
- No fabricated geometry/CG, duplicate armour ownership, automatic adoption or edits to other conditions.
- Original assembly hash and 191-observation inventory remain frozen; no recovered source redistribution.
- Run focused tests red before implementation; Codex independently reruns acceptance.

## Review Focus

- Same barrel count with different original mount selectors must retain different geometry meaning.
- Identical active groups must survive import separately, including elevated/depressed counts.
- Missing profile/flags may not silently become a flat profile or false checkbox.
- Layout-owned and legacy row-owned armour must not both estimate the same groups.
- Layout changes must invalidate old proposals and preserve already adopted masses until reviewed again.

## Task 1: Source vectors and baseline

- [x] Generate and independently rerun original assembly probe; supplement with 469 count-consistent mixed cases after excluding inconsistent original test inputs.
- [x] Freeze 416 existing v1 numerical readings and run the baseline (205 tests /1005 subtests).
- [x] Review the contract against source and existing project ownership; resolve material ambiguities before implementation.

## Task 2: Core layout and paired armour

Files: create `tools/plimsoll/battery_layout.py`, `tools/plimsoll/tests/test_battery_layout.py`, `tools/plimsoll/tests/test_battery_layout_workflow.py`; modify `concept_design.py`, `verification.py` and existing related tests only as required.

Interfaces: exact `validate_layouts` and `evaluate` signatures/results in the spec. No new analysis stage.

- [x] Write failing tests for original numeric samples, unknown/zero distinction, two-group integer average, selector compatibility, invalid references/counts and all five review cases.
- [x] Run new tests and retain expected feature-missing failure output.
- [x] Implement kernel, declaration/ownership integration, independent model registration and design_balance layout readings; preserve absent-feature outputs.
- [x] Run `web/backend/.venv/Scripts/python.exe -B -m pytest tools/plimsoll/tests/test_battery_layout.py tools/plimsoll/tests/test_battery_layout_workflow.py tools/plimsoll/tests/test_battery_armour.py tools/plimsoll/tests/test_battery_armour_workflow.py tools/plimsoll/tests/test_concept_design.py tools/plimsoll/tests/test_concept_unknown_inputs.py -q` with `PYTHONPATH=tools`, `PYTHONUTF8=1`.

## Task 3: Migration and normal editor

Files: modify `sship_mapping.py`, migration tests, `ConceptDesignEditor.tsx`, `conceptDesign.ts`, `DesignBalanceResults.tsx`, `i18n/concept.ts`; create a focused `BatteryLayoutEditor.tsx` if needed to avoid further growing the main editor.

- [x] Write failing migration/editor tests for identical-but-distinct groups, unknown flags, units, references, server-derived readings and stale proposals.
- [x] Preserve group identity on new imports, canonical layout profile and original archive; do not rewrite existing user JSON.
- [x] Implement normal form controls and returned readings, with no client-side engineering formulas.
- [x] Run core `test_sship_import.py`/`test_cli_sship.py`; backend `test_sship_import.py`/`test_mass_proposals.py`; frontend `npm.cmd run test -- --pool=threads --maxWorkers=2` and `npm.cmd run build`.

## Task 4: Independent acceptance and handoff

- [x] Codex reads every changed production file and independently reruns source vectors/comparison and targeted core/backend acceptance.
- [x] Check unchanged v1 readings, schema round trips, numeric bounds and original-source/inventory hashes.
- [x] Validate actual local API/worker and browser save/adopt/recompute/reopen with a synthetic mixed-layout project, base and other-condition preservation.
- [x] Run final appropriate regression and built-in quick verification at the accepted source identity.
- [x] Write a coverage increment and acceptance report with exact tested limits; leave fixed armour zones as the next independent unit.
