# Damage laboratory fragmentation implementation plan

**Goal:** Explain a declared detonation through deterministic representative fragment paths, compartment-boundary shielding, estimated module losses and generated hydraulic links, locally accepted before release.

**Architecture:** An optional `detonation` block selects the new game model; omitted blocks preserve the existing localized-hit behavior. Python traces bounded paths through declared rectangular compartments and records results. React configures boundary responses and renders frozen traces; the existing flooding core consumes the merged explicit/generated links unchanged.

**Tech stack:** Existing Python standard library, React, Three.js. No new dependency.

**Approved scope:** User requests detonation position, bulkhead shielding and fragment paths, linking module damage and breaches to the current core. Codex implements directly, local acceptance only, concentrated checks.

## Decisions and limits

- Use normalized game exposure, not explosive mass, blast-pressure, penetration or medical predictions. Do not add fire, fuse or repeated-hit models.
- Origin must be strictly inside exactly one nonoverlapping rectangular room; finite range, 32..512 representative rays and integer seed. A seeded rotation of equal-area spherical directions gives reproducible sampling.
- All compartment faces stop fragments by default. Explicit boundary responses permit transmission; internal links require opposing shared faces, sea responses must be explicitly declared on exterior proxy faces. Unmodelled space is blocked, never silently sea.
- Each ray visits rooms in distance order. Record module/station intersections before the next face; transmitted exposure falls at faces and with distance. Each target is counted at most once per ray. Stations remain aggregate game estimates.
- Boundary absorbed exposure may create one hydraulic breach at its declared proxy point, using a supplied threshold and maximum area. The new opening does not retroactively remove shielding during this instantaneous event. Preserve manual breaches; reject duplicate generated/manual interfaces.
- Generated areas are bounded by the geometric interface area and declared maximum. Reports retain seed, paths, target contributions, boundary loads, generated links and applied links. All new estimates carry provenance.
- The existing numerical core owns flooding, equilibrium and GZ; no edits to its equations. Replay contains an indexed detonation event before damage effects and uses explicit metadata rather than parsing prose.
- Paths are static explanatory geometry, revealed after the detonation event. No per-fragment animation or cosmetic explosion in this round. Replay never moves the camera.
- Preserve all pre-existing edits and unrelated core verification files. No commit or deployment.

## Work

- [x] Python admission and bounded tracing: add `fragmentation.py`, integrate optional validation in `request.py`; targeted checks for shielding, transmission, deterministic paths, bad geometry and generated breaches.
- [x] Coordinator bridge: retain legacy behavior, add frozen fragmentation report and events; feed generated breaches to the real core without modifying input or double-counting water.
- [x] UI: origin/seed/count/boundary controls, path toggle and selected path inspection, text records and source labels. Keep the previous replay/module/crew features.
- [x] Acceptance: run the focused Python laboratory cluster, frontend laboratory cluster and production build after integration; run actual local worker experiments, inspect shielding/path/breach/flooding replay in the browser and save evidence.

## Accepted evidence

28 focused Python checks and 24 focused frontend checks passed; production build passed. Two actual worker runs compare a sealed shared boundary and 35% transmission. The closed run keeps the port module at 100%; the transmitting run records port exposure 0.00442023 and integrity 99.55798%. Both generate one 0.0391903 m² declared sea-proxy link and the native core accepts 1.29289 m³ added water at 12 seconds. Pre-burst replay hides paths and holes. A browser-discovered endpoint-height bug was repaired and pinned by the renderer check. The 16 protected unrelated files retain their baseline SHA-256 hashes. No commit or public deployment.

## Acceptance cases

Closed wall blocks an otherwise reachable module; transmission allows only reduced influence. Zero severity/range causes no damage/breach. Identical frozen input reproduces identical paths and estimates. A generated sea link appears exactly once in native flooding connections and yields accepted added water when submerged. Returning to the pre-detonation frame hides paths and generated breaches. Existing legacy fixture counts and camera behavior remain unchanged.
