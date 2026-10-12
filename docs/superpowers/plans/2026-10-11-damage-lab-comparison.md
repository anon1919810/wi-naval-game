# Damage laboratory comparison and explanations plan

> **For agentic workers:** Use superpowers:executing-plans for implementation. The user has asked Codex to implement directly and keep verification concentrated by feature cluster.

**Status:** Proposed next round; planning only. Public release remains the committed `e43410c` implementation.

**Goal:** Help a player explain which modules and crew were affected, why a wall changed the outcome, and how an opening changed the ship's accepted flooding state.

**Architecture:** Reuse immutable laboratory results, representative paths and the existing numerical core. Add named synthetic presets, a read-only comparison of two completed trials, and target-level explanations derived from structured evidence. This round changes how experiments are prepared and understood; it does not add another damage solver.

**Tech Stack:** Existing Python, React and Three.js; no new dependencies.

**Spec / current contract:** [Damage laboratory](../../plimsoll-1.0/damage-laboratory.md). The proposed additions below implement the user's established goal of explaining module, hull and crew effects. Their ordering is Codex's recommendation, not a newly approved implementation scope.

## Global constraints

- Preserve all parallel core-verification/CLI edits. Start local; public release follows acceptance and user authorization.
- Keep `compartment-fragment-rays-1`, native flooding/equilibrium/GZ equations and frozen run records unchanged.
- Representative rays are normalized game samples. Do not label them actual fragment count, explosive energy, real armor penetration or medically validated casualties.
- Camera stays under user control. Only explicit **locate** changes the view.
- Keep unknown personnel/power unknown. Do not convert an unknown value or missing hydraulic solution into zero.
- Use accepted event indices for replay; do not infer a more precise threshold crossing or detonation timeline.
- No new fuse, blast-pressure, fire, repair or repeated-hit model in this round. Those remain separate possible future projects.

## Review focus

1. Two different project revisions or solver methods must not silently appear as a controlled comparison.
2. Changing seed, sampling count or multiple inputs must remain visible; a difference alone is not causal attribution to one wall.
3. Restoring a preset or viewing a saved trial must not modify a frozen result, overwrite a project revision or enqueue a calculation automatically.
4. Unknown crew/power and stopped/canceled runs must not produce reassuring zero deltas or extrapolated final outcomes.
5. Selecting comparison records must not move the camera or replace the active replay without an explicit **view trial** action.

## Task 1: Three useful synthetic experiment presets

**Files:** Create `web/frontend/src/damageLab/presets.ts`; modify `Page.tsx`; create `presets.test.ts`.

**Interface:** `buildPreset(project: ProjectDocument, baseline: Experiment, preset: 'shielded' | 'transmitted' | 'sea-opening'): Experiment`. Return a new draft; require compatibility with the existing synthetic fixture's rooms and geometry. Unsupported custom layouts receive an explanation rather than guessed sea connectivity.

- [ ] Add **Bulkhead shielding**, **Partial transmission**, and **Sea opening** choices to the synthetic example workflow.
- [ ] Use the same declared origin, normalized severity, range, seed and 128 samples in the shielding pair. Change only the shared-wall transmission, from 0 to 0.35. The sea-opening preset adds the already accepted explicit exterior proxy response.
- [ ] Presets keep their synthetic/game provenance. They never set a historically calibrated armor class or real explosive mass.
- [ ] Applying a preset prepares a draft and shows assumptions. Running still requires the existing run action; incompatible manual/generated links are surfaced through admission.
- [ ] Verify input immutability, unsupported geometry, and no automatic enqueue. Confirm the three drafts through the existing preview endpoint.

## Task 2: Compare two completed trials

**Files:** Create `comparison.ts`, `Comparison.tsx` and `comparison.test.ts`; modify `Page.tsx` and `lab.css`.

**Interfaces:** `compareTrials(a: LabRun, b: LabRun)` consumes completed run records and their results, and produces compatibility reasons, changed inputs, per-module factor/power deltas, crew count deltas, breach-area deltas and accepted final ship deltas. Check identity against the frozen `input_snapshot.id/revision`, `condition_id` and `method_versions`. `Comparison` displays the two named runs and their provenance; fetch full records through existing `api.readRun(id, signal)` only after selection.

- [ ] Allow A/B selection from completed records in the current project. Require the same project/revision, loading condition, numerical method versions and completed accepted endpoints for quantitative comparison.
- [ ] Show all changed experiment inputs. Different seed/count, several changed inputs or differing duration are flagged as an uncontrolled comparison; do not claim one setting alone caused the result.
- [ ] Show both `final_state.time_s` and `simulated_duration_s`. Equal requested duration does not guarantee equal accepted endpoints; flag differing endpoint times and do not interpolate or describe them as a same-time comparison.
- [ ] Compare mechanical, flooding and staffing factors separately, preserving their existing multiplicative relationship rather than adding losses, followed by effective availability and available shaft power. Show water volume in m³ and mass in t separately, plus heel and trim. Unknown operands produce an unknown difference.
- [ ] Display crew available/incapacitated/dead/evacuated estimates without inventing evacuation paths or speed predictions.
- [ ] A/B selection is read-only and retains active replay/camera. Explicit **view trial A/B** uses the existing saved-trial restoration flow.
- [ ] Two records belonging to the same old revision may be compared read-only. Their **view trial** actions explain any current-revision mismatch instead of silently failing or bypassing the existing guard.
- [ ] Verify incompatible revisions/methods, unknown values, cancellation during record fetch and no mutation of records or active playback.

## Task 3: Explain a selected target from its evidence

**Files:** Create `consequences.ts` and `consequences.test.ts`; modify `Inspector.tsx`, `Detonation.tsx` and `narrative.ts`.

**Interface:** `explainTarget(result: LabResult, frame: number, target: InspectionTarget)` returns visible contributing paths, boundary responses and factor changes with their original identifiers and `game/core/mixed` source labels. Consume structured records, never parse event messages.

- [ ] For direct module/crew exposure, show the contributing paths and transmission sequence; rank the most significant paths and allow inspection of the remainder.
- [ ] For a generated hole, connect declared boundary load and threshold to the recorded area, then use native `flows` and `edge_transfers` to describe recorded flow. Add their existing shapes to the frontend `ShipState` type as needed. Label compartment water as aggregate when several paths can contribute; never attribute all of it to one opening. Separate estimated opening response from numerical flooding results.
- [ ] For effective availability, explain mechanical loss, water-threshold disabling and lost staffing as distinct contributions. Link back to the first accepted event recording each effect.
- [ ] Explanations at a pre-detonation frame must not reveal already applied damage or openings. No stable hydraulic endpoint means no invented final heel/trim or survivability judgment.
- [ ] Verify shielding attribution, absent/unknown evidence and pre-burst visibility using the existing closed/transmitted frozen fixtures.

## Concentrated local acceptance

After integrating the feature cluster, run the new pure-model checks together with the existing laboratory UI checks and `npm.cmd run build`. Reuse the existing Python laboratory cluster only if the request/core integration changes. Avoid repeated whole-project regressions for presentation edits.

Use one local synthetic project to run the three presets and compare the shielding pair. Confirm: the untouched opposite module stays at 100% with a closed wall; 35% transmission exposes it with the recorded path contribution; the declared sea opening produces native accepted water. Inspect target explanations, unknown values, A/B input differences, saved-trial restoration and camera retention once in the browser.

## Later directions

Once experiments can be explained and compared, consider direct spatial editing of origin/boundary responses, then calibration of gameplay damage curves against explicit designer benchmarks. Persistent fire, repairs and repeated hits need their own state/time model. Real penetration or blast validation would be separate research and should not be implied by more elaborate graphics.
