# Native armour design diagram

User approved autonomous execution on 2026-10-18: diagram first, armour first, same design/ledger, edit links, changed-region emphasis, frozen report and SVG/PNG export. OpenCode implements; Codex accepts once assembled. No commit, push or deployment. Preserve the already accepted, uncommitted design-feedback batch.

## Meaning and boundaries

The source stores belt length/height/thickness, deck fractions and a coverage selector, but **no belt starting station, vertical placement, tower positions or real waterplane shape**. The result's `bulkheadType` means Additional/Strengthened bulkheads, not a known transverse or torpedo-bulkhead layout. Do not invent those facts.

Create an explanatory diagram, explicitly labelled as schematic. Reuse the existing freeboard endpoints as context. Below them show separate length-proportion bands for main/end/upper belts, bulkheads and bulges. Their displayed centring is a presentation convention, never an installation interval; state that positions are unspecified. Only band LENGTH is proportional; show declared height, thickness and inclination as numbers, not invented depth/plate geometry. Do not split the end belt into guessed fore/aft lengths. Plan view is a deck partition schematic: quarterdeck / central / forecastle fractions where valid, with beam identified but no claimed hull outline or protected area. Coverage selectors 0-6 retain their distinct names; box machinery/magazine positions remain unspecified. Conning forward/aft thicknesses appear as labelled items, not positioned towers.

Missing, null, negative, non-finite or out-of-domain values never become plausible shapes; known zero remains zero. Overlong bands/fractions outside the valid total are diagnosed visibly rather than silently clamped. Show independently known labels even where geometry cannot be plotted. No new ship formula, geometric area, coverage percentage, armour rating or inferred CG.

## Data contract

Read supported native `ShipDesignResult` schema/method only. Normalized hull/freeboard/armour outputs are feet/inches regardless of the input page scales; convert only for display, using explicit units. Prefer the existing reader unit facilities; thickness must stay explicitly labelled in/mm, not take an arbitrary hull-length unit. A display unit switch must never issue a source scale command. Avoid dependencies on catalogue/network for historical drawing.

Read estimate and selected masses, estimated/declared policies and the overall balance only from `ledger`/`balance`. No mass reconstruction or additional ledger items. Reuse existing `ledgerEntries`/`balanceOf` readers. Workbench receives confirmed native result plus the actual saved baseline (already supplied by the feedback batch). Highlight a region when its known dimensions, coverage, mass or policy differ, not two unchanged unknowns. Only compare a compatible same-project/basis saved reading. Describe highlights as observed changes, not cause or quality.

While native edits/preview are pending or failed, withhold numeric drawing and export; keep a concise state message and the existing retry path. Never show old confirmed output as the latest changed drawing. After save, highlights reset with the baseline. Language/theme/selection changes must preserve draft, queue and focus.

## Interface

Place the diagram in the native Armour chapter above its existing fields; retain all existing inputs. Selecting a region by mouse or keyboard exposes its source dimensions, selected/estimated mass and policy. An explicit Edit button reveals the relevant existing field group, scrolls and focuses its first meaningful field. Do not add duplicate inputs or change queue semantics. The existing Changes panel stays available above it. The same diagram is read-only inside native saved results (`Sps3b3Readings`, native variant only); it reads frozen stage data and carries the run identity. Old native reports gain a derived view without mutation or live preview. Unsupported/missing old data gives a clear unavailable state; compatibility/physical reports remain unchanged.

Chinese and English labels and boundaries must be complete. At 390px the drawing may scroll inside its panel with a readable minimum width; the page must not widen. Use existing design tokens, restrained distinct colours/patterns, keyboard selection and descriptive SVG title/description. No redesign, artwork or WebGL dependency.

## Export

SVG and PNG export the same complete schematic, including labels, units, legend, bounds, masses and run/revision/context label. Standalone SVG must have explicit colours/fonts and namespace, not depend on app CSS. PNG uses that SVG and an explicit readable background. Errors are visible, URLs cleaned up, unsafe names sanitized. Pending/failed/unsupported drawing cannot export. Selection must not make the exported data disappear. Source reports and prior freeboard PNG exports remain intact.

## Acceptance

One bounded developer test batch and build after assembly, followed by Codex's single impacted frontend batch and build. Fix-specific reruns only. Independent browser/API/worker acceptance uses the private harness and synthetic backup: select/edit main belt, check highlight and weight/balance, pending/failure gating, save/reload reset, run/frozen report, later draft leaves old report unchanged, actual SVG/PNG downloads, ZH/dark/390px. Check exported files and raster pixels. Core/backend hashes and previous uncommitted feature files must be preserved except the named integration points. No unchanged Python or exhaustive field matrix reruns.
