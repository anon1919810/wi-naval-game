# Battery Armour Implementation Plan

> **For agentic workers:** Use the user's prescribed OpenCode implementation workflow; Codex independently reviews and verifies. Work in the existing linked worktree. No staging or commits.

**Goal:** Close the declared battery-armour thickness -> estimate -> reviewed ledger adoption workflow.
**Architecture:** A pure versioned kernel feeds optional per-battery configuration, existing empirical mass models and atomic adoption. A distinct complete gun-mount-armour role preserves the fixed/rotating distinction.
**Tech Stack:** Existing Python core and React/TypeScript frontend, no new dependencies.
**Spec:** `docs/superpowers/specs/2026-10-15-battery-armour-design.md`.

## Constraints and review focus

Preserve all 99 baseline dirty files; change only the approved surface. Frozen 191 inventory, original executable, migration mapping and F06/F08 kernels stay unchanged. No dependency/configuration changes, deploy, Git mutations or external messages.

Review missing vs zero; single homogeneous groups vs mixed groups; inactive/missing unrelated ammunition fields; target ownership and complete-armour role; fixed barbette mass never described as wholly rotating.

### Task 1: Pure kernel and independently reproducible source vectors

- [x] Write failing tests in `tools/plimsoll/tests/test_battery_armour.py`, then implement `tools/plimsoll/battery_armour.py:estimate(...)` from the pinned source.
- [x] Run the new tests, finite-domain and boundary cases. Codex separately produces original-assembly vectors and compares them.
- [x] Add the module to verification source identity when consistent with the current identity mechanism; retain all old method identities.

### Task 2: Optional configuration, unique models and balance role

- [x] Add failing integration cases, then extend `concept_design.py` with nullable optional armour configuration, ownership validation and an independently generated `concept.<id>.armour` model.
- [x] Add `gun_mount_armour` to role validation and each dependent source armWeight aggregate without double counting legacy rotating armour; preserve old results.
- [x] Test atomic adoption, stale rejection, incomplete inputs, source archive, base ledger/other-condition preservation and canonical JSON roundtrip.

### Task 3: Ordinary editor and final acceptance

- [x] Add failing frontend behavior tests. Extend `ConceptDesignEditor.tsx`, `conceptDesign.ts`, `i18n/concept.ts`; reuse quantities and proposal UI.
- [x] Independently run core concept/migration/adoption regressions, backend mass-proposal integration, frontend relevant tests and production build. Commands in the OpenCode brief are authoritative.
- [x] Codex browser acceptance uses the existing isolated harness, then fresh read-only review and dirty-file/source preservation. Write dated report and evidence, update current coverage only after acceptance.


Execution note: OpenCode implemented; Codex independently accepted and completed bounded arithmetic-range and proposal-label repairs after two review rounds. Native download and full layout parity remain outside acceptance. Evidence: docs/plimsoll-1.0/battery-armour-2026-10-15.md.
