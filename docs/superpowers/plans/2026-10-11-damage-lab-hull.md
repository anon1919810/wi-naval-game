# Damage laboratory hull and local cutaway implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the rectangular visual demo with a readable ship-shaped synthetic vessel and a real partial cutaway, using the same canonical offsets as Plimsoll's solver.

**Architecture:** Python and Three.js both consume the project's inline section polygons. The viewer preserves every original section vertex, lofts between declared stations, and cuts that same outer shell along the center plane; it never provides geometry to the solver. A separate synthetic vessel and experiment become the default demo, while the analytic rectangular rig remains unchanged as a numerical fixture.

**Tech Stack:** Existing Python Plimsoll kernel, React/TypeScript, Three.js 0.186, Vitest, unittest and pytest; no new dependencies.

**Spec:** User-approved description in chat on 2026-10-11, plus `docs/superpowers/specs/2026-10-10-damage-laboratory-design.md` for the existing laboratory's contracts. User approval covers implementation and local acceptance; no further implementation confirmation is needed.

## Global constraints

- Keep existing dirty work, existing analytic rig/experiments, kernel equations, Unity files, fonts and global styles byte-identical.
- No staging, commits, push or public deployment. Keep the existing feature branch and working directory because the lab is currently uncommitted there.
- All vessel offsets, mass/layout/crew/equipment values are explicitly synthetic estimates, not historical or calibrated data.
- Do not add visual superstructures or appendages absent from the canonical geometry.
- Replay must preserve accepted native attitude, water planes, nullable knowledge, immutable results and view lifetime.
- Centralize verification by feature cluster and retain local evidence.

## Review focus

- Different polygon vertex counts, cyclic starting vertices, winding and shifted keel datums must preserve the original cross sections without twisting or moving them.
- Full-hull and partial-cutaway views must use the same physical shell; the latter must retain half the hull and half the deck, with an open inspection plane rather than an opaque fill.
- Hidden modules must not be selectable through an opaque retained shell; exposed module picking and orbit dragging remain distinct.
- Render/replay/palette/context-loss/unmount must not leak resources or reset the camera merely because the accepted frame changes.
- The default demo must fit its rooms within its declared hull, reach a valid dry equilibrium, and produce conserved accepted flooding states rather than retaining the rectangular rig's old numbers.

## Task 1: Canonical vessel demonstration

**Files:** Create `tools/plimsoll/cases/damage_lab/synthetic-vessel.project.json`, `synthetic-vessel.experiment.json`, `tools/plimsoll/tests/test_damage_lab_vessel.py`; modify only the demo seam in `web/backend/plimsoll_web/damage_lab_runs.py`, associated tests, demo copy in `web/frontend/src/damageLab/Page.tsx` and `docs/plimsoll-1.0/damage-laboratory.md`.

**Interfaces:** The project keeps `plimsoll-project-1` and inline `plimsoll-section-polygons-1`; the experiment keeps `plimsoll-damage-lab-experiment-1`. `/api/damage-lab-demo` returns this new pair. Existing imports and saved analytic-rig results remain compatible.

- [x] Write a failing fixture/endpoint test before changing the demo. Assert a tapered bow and stern, raised end keel, closed nondegenerate section polygons, keel/deck/bilge definition and explicit source/estimate metadata.
- [x] Use a 36 m long, 8 m beam, 5.5 m deep synthetic vessel. Give it rounded/faceted bilges, a narrow forward stem and a tapered transom; at least 21 longitudinal stations. The builder may add stations at shape changes. Keep sections convex and the declared maximal bounds exact.
- [x] Use the three existing room identities with newly declared geometry: paired machinery at x=-4, y=+/-1.6, dimensions 8 x 3.2 x 3.2 m, bottom z=.8 m; forward control x=4, y=0, dimensions 7 x 5 x 2.8 m, bottom z=1.2 m. Keep the machinery region full-beam enough that all room corners fit. Equipment and duty stations fit those rooms. Base mass initially 320 t plus two separately owned 10 t engines; KG approximately 1.8 m. Any equilibrium-based adjustment must be explicit in metadata and reported.
- [x] The known starboard breach is at [-4,3.2,.8], where the chosen midbody profile also meets the declared room face. Use area .4 m2, Cd .6, duration 12 s, nominal step 1 s. Preserve the explicit game-estimate damage/crew rules. This remains a simple sea-link scenario, not a new ballistic solver.
- [x] Verify room containment at every crossed station and at each room end plane using the interpolated profile, plus module/station containment and no overlaps. Run dry/no-impact and damaged/breached variants through the actual core. Assert accepted endpoint, mass residual, native/projected state equality, preserved input offsets and known crew conservation; do not hardcode old box results.
- [x] Run `python -m unittest discover -s tools/plimsoll/tests -p 'test_damage_lab*.py' -v` and the backend damage-lab cluster with `PYTHONPATH=tools` and the existing backend venv.

## Task 2: Exact station envelope and partial cutaway

**Files:** Create `web/frontend/src/damageLab/hull.ts` and `hull.test.ts`; modify `Scene.tsx`, `Scene.test.tsx` and scoped `lab.css` only if needed.

**Interfaces:** `buildHullEnvelope(stations: Array<[number, number[][]]>, keelOffset: number): { sections: Vec3[][]; faces: Vec3[][] }` yields keel-relative canonical geometry. `cutHullFaces(faces: Vec3[][]): Vec3[][]` retains raw-body y<=0 without capping the inspection opening. Hull construction is pure and independently testable. Existing `bodyPoint`, `attitudeRows` and native-water clipping remain the coordinate/physics seams.

- [x] Add failing tests for preserved source vertices, closed bow/stern/deck, alternate vertex counts/windings/cyclic origins and nonzero keel datum. Every source vertex must occur on its own station contour; no decimation or invented external silhouette.
- [x] Normalize contour winding and choose stable port/starboard deck anchors. Parametrize the hull path and deck path separately, then use the union of their original normalized breakpoints across stations to keep every original corner. Added points only interpolate on an original polygon edge. Close end polygons with suitable triangulation, including concave profiles if supported. Keep outward-facing normals.
- [x] Add failing tests for cutting: the cut keeps a nonempty half shell/deck, emits intersections on y=0, removes y>0 shell faces and does not add an opaque center-plane cap. Do not clip the internal room or native-water volume to half size.
- [x] Render a readable neutral opaque shell with restrained directional/ambient lighting, deck/bilge/stem contour cues derived from the offsets, and sparse station lines only where helpful. Normal view hides internal clutter; partial cutaway opens starboard shell/deck and keeps the port exterior and meaningful compartment boundaries. No whole-shell disappearance.
- [x] Frame from actual geometry bounds, including non-centered stations and shifted datums. Default/reset view looks into the open side. Preserve the view across replay and mode toggles.
- [x] Use the visible outer shell for raycast occlusion, and the exposed modules for selection. Keep a drag threshold. Preserve native water and attitude, cleanup, context-loss retry, palette changes and HTML fallback. Test that replay/cutaway toggles reuse the renderer, resources dispose, and initialization failures clean any partially constructed resources.
- [x] Run `npm.cmd test -- --run src/damageLab` and `npm.cmd run build` in `web/frontend`.

## Task 3: Independent local acceptance

- [x] Codex reads every changed file against the pre-change baseline and reruns the feature clusters itself.
- [x] Read-only independent final review checks this iteration's geometry/data consistency, section winding/loft/cut correctness, picking occlusion and graphics lifecycle. User-authorized OpenCode remains implementer; if its pinned provider fails, use the user's existing Codex fallback authorization and record the evidence.
- [x] In the actual local browser import a fresh synthetic vessel, run the real bounded worker, inspect normal/cutaway views, orbit/zoom, exposed module selection, rewind/final accepted water and datum/attitude correspondence. Save both view screenshots and the frozen result.
- [x] Compare the frozen run's geometry exactly to the demo offsets, exported/native numbers and known crew conservation. Verify protected hashes and HEAD unchanged. Keep the local preview open and report the URL plus verification limits.

## Deliberate limits

The envelope is a piecewise loft through canonical sampled polygons. The core still integrates its declared sampled sections using its existing numerical method; no claim is made that the triangle mesh volume exactly equals that station quadrature between samples. Compartments remain explicit rectangular game abstractions. No appendages, historical hull, physical breach mesh, penetration, blast or structural-breakup model is added.
