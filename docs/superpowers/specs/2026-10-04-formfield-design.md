# Y’s Formfield — homepage and splash, first version

User-approved direction, 2026-10-04. Implement a running local first version now; refine details after viewing. This instruction supersedes further design approval gates. Production deployment is outside this task.

## Identity and layout

- Brand: **Y’s Formfield**, all public UI/copy English. Personal portfolio of tools and experiments. Plimsoll is the first real featured work; no invented projects.
- Precise, modern, highly interactive. Restrained Apple/Linear/Swiss-style public frame with expressive work visuals. Default light, optional dark/system.
- Central large exhibit with compact header, work information underneath, real Explore Project action. No oversized marketing headline or generic card-filled landing page.
- Artwork is exclusively **top-view linework**, not side elevations or generated realistic ships. Source user-provided Queen Mary drawing, with subtle asymmetric construction geometry: large partial arcs, tangents, diagonal axes, localized grid, registration marks. No fabricated engineering measurements.
- User reattached the three references during implementation, now saved as `web/frontend/public/portfolio/ship-plan-01.png`, `ship-plan-02.png`, `ship-plan-03.png`. Use first as default, optionally switch among the three reference drawings within the single Plimsoll exhibit (not invented projects). Only show lower top-view regions, e.g. first image near y=290..451, second near y=290..451, third near y=350..542, with native widths. Ship bow points right. Preserve source/provenance, crop via SVG/CSS, no rendered model substitute. These are references, not interchangeable verified Queen Mary specifications. Earlier archived fallback is now superseded.

## Splash and transition

Total 2500 ms after essential artwork ready; no fake percentage. Pure black beginning, enlarged top-view vessel with bow upper-right, stern lower-left, around -28° relative to horizontal; parts out of viewport.

1. 0–100 ms: black.
2. 100–900 ms: sharp diagonal scan advances upper-left to lower-right. Passed area shows white vessel and decorative geometry on black.
3. 900–1100 ms: complete black/white drawing held.
4. 1100–1800 ms: reverse sharp scan travels lower-right to upper-left. Passed area simultaneously becomes white background and black linework, with identical artwork registration on both sides. Dark preference resolves to dark final theme without a white flash.
5. 1800–2500 ms: one composition scales and moves continuously into central exhibit, settling at -12° (approved range -10°..-15°). Header and work metadata enter during this stage.

New document entry/reload at the homepage plays splash. Direct About/app bookmarks bypass the homepage-only intro, whose settling target is the exhibit. In-app navigation/back home does not replay; browser Back must preserve selected exhibit/exploration state. Explicit Replay Intro available for design review. Reduced motion bypasses scans; focus, keyboard and touch remain usable. Essential asset failure must release loading, not trap a user behind black screen.

## Functional boundary

Public home, Work/About navigation, theme, replay, exhibit exploration/reset must work without calling auth/bootstrap or creating anonymous workspaces. Mouse movement subtly pans the illustration and moves an inspection focus; keyboard/touch equivalents and reset. No heavy 3D dependency.

Keep existing Plimsoll application/calculation/API/database/auth behavior. Existing `#/projects/...`, `#/runs/...`, `#/reports/...` remain valid. `#/plimsoll` enters existing app lazily; a real link returns to public home. Split public root from existing app entry without changing backend or existing forms. Scope public styling to avoid leaking app globals. Plimsoll UI language remains existing behavior; this task's English-only rule applies to the new public portfolio.

## Acceptance

Batch frontend tests once after implementation, production build, independent browser visual/interaction check desktop and mobile. Verify diagonal mask geometry, 2500 ms timeline, no splash on internal return, legacy routing, theme preference, reduced motion, no horizontal overflow, public no API bootstrap. No core calculation regression or server operations for this frontend task.

## Approved refinement: geometric vector studies

The user requested clearer redrawn linework with dense redundant marks removed. The three reference top views now inform hand-authored SVG geometric studies in VesselDrawing.tsx. This supersedes the initial raster-crop/filter rendering approach; source PNGs remain archived. Hull, turret and primary deck shapes retain a visual hierarchy, while decorative construction lines are masked outside the hull. The existing exhibit, 2.5-second scan and route behavior remain in place. These are artistic interpretations rather than measured naval plans.

## User correction: preserve the original drawing

The user rejected the geometric simplification as too sparse. The preceding redraw refinement is superseded. Render the original three top-view reference images, retaining their detailed fittings, deck texture and gray fills. Use restrained tonal cleanup and theme recoloring only; do not reconstruct the ship or claim recovered detail beyond the source resolution. A generated restoration trial was inspected and rejected because it altered local linework; it is not used by the website. The exhibit and 2.5-second transition remain unchanged.
