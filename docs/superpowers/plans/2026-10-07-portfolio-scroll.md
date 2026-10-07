# Portfolio Scroll and Entry Implementation Plan

> **For agentic workers:** Use the user-required OpenCode implementation workflow. Codex owns scope, review and independent acceptance. The design and execution method were approved in chat; proceed without another approval gate.

**Goal:** Give the public portfolio a precise scroll response, a quieter header, and one clear Plimsoll tool entry in each Work view.

**Architecture:** Preserve native document scrolling, the hash router and existing shared-art/circular route transitions. Use one disposable scroll controller per visible public page to measure reading sections and paint bounded SVG/CSS changes; React updates only for section identity, not every frame. A reusable title-link component owns radial text preview and the optional adjacent project link.

**Tech Stack:** Existing React, TypeScript, SVG, CSS, Web Audio and Vitest. No dependencies.

**Spec:** Approved conversation through 2026-10-07, captured in Design below; current source and docs/formfield/CHANGELOG.md are the baseline.

## Global Constraints

- Desktop only: inspect 1440, 1280 and 1024 widths. Preserve existing smaller-screen usability; no mobile redesign.
- Space Grotesk headings, Inter body; protect font files, global tokens, workspace components/styles, backend and data.
- Keep the current paper colours, 12-column alignment, stacked detail descriptions, real formulas and selected reference artwork.
- Decorative labels/tooltips in English. No invented engineering values, random numerical changes or new annotations.
- Native scroll, no scroll hijack, no new animation package, no per-frame React render. Stop work while hidden/offscreen and dispose observers/listeners/RAF/timers.
- Reduced motion presents readable static artwork and instant navigation; current-section information remains available. No autonomous looping decoration.
- Group tests by feature cluster, then run the full frontend suite/build once after integration. No commit/push/deploy in this implementation task.

## Design

### Header and entry

- Remove SYSTEM and OS-theme following. Stored legacy `system` resolves to light and is replaced by manual light/dark. Do not change workspace theme logic.
- Sound: geometric speaker SVG plus one wave; diagonal mute slash; no text box. Keep an accessible name/pressed state and English title. Reuse the existing mute preference and AudioContext lifecycle.
- Replay: small incomplete circle at upper right, static at rest, rotates on hover/focus. Accessible `Replay intro`; existing replay behavior. Remove footer Replay and footer Contact; About retains complete contact section.
- Home and detail H1s remain semantic headings but contain the real tool link. Visible spelling stays `Plimsoll`; accessible link name `Open Plimsoll`. Existing CTA refs now point to title anchors, preserving return focus and prefetch.
- Title black at rest with short underline and a small arrow. Pointer entry sets the blue radial fill origin; radius covers the farthest word corner. Existing lower-case i dot becomes Swiss red (#E2231A) on preview without changing its shape or spacing. Only that dot is red, not the stem. Underline extends simultaneously (~300ms damped ease). Mouse leave reverses; interrupted re-entry keeps current circle/origin until fully closed. Keyboard preview originates at word centre. Primary click holds blue/red through tool transition; modifier/new-tab behavior remains native.
- On home only, VIEW PROJECT expands to the right of the title on its baseline. It is smaller and muted-blue at rest, brand-blue radial fill/underline on its own preview. Title and action share a hover/focus region, including their gap; moving to the action retains title preview. Brief delayed close after leaving the whole region. Focus reveals the action; touch/non-hover fallback keeps it reachable. Hidden secondary link must not intercept pointer or create invisible tab stops; title focus reveals it before Tab advances.
- Remove both standalone OPEN PLIMSOLL buttons. Detail has no VIEW PROJECT self-link. Do not duplicate transition names.

### Reading and sound

- At desktop widths >=901, detail section H2 remains at top:32px within its own section, and releases at section end. Do not pin whole paragraphs, change columns or shrink reading text.
- Reading ruler below the persistent Work/About rail only for long About/detail views. Track height fits available viewport; hide ruler at existing small-screen fallback. Major marks correspond to measured document section positions; minor marks communicate proportional reading distance. Thin neutral line, short ticks, blue current square and compact label such as `02 / CAPABILITIES`.
- Hover/focus target mark turns red while current location remains blue; ample invisible hit area. Activate scrolls to that section using native smooth scrolling, instant for reduced motion, and gives keyboard focus to its heading without triggering the hash router. Ruler is a labelled secondary navigation, not nested inside the main nav landmark.
- Detail major sections: Overview, Capabilities, Workflow, Technology, Methods & Limits. About: Collection, Person, Plimsoll, Scale, Friction, Power, Built with, Contact. Existing study numbering stays unchanged; ruler numbering is page reading order.
- Section sounds are a short, softer damped tick in the existing synthesised sound family. No sound on initial mount, route placement, resize, fonts arriving or hidden-page restoration. Only user scrolling or an explicit ruler activation can arm a section sound. Debounce quick traversal to the final settled section (~140ms), with boundary hysteresis (~24px) and one tick per actual stable section change. Muting suppresses pending/current audio; shared throttle prevents overlapping preview/section sounds. Never construct/unlock AudioContext from passive scroll/hover.

### Scroll studies

- Work: preserve faint draft circles/datum. Main compass/tick ring slowly rotates within about 8 degrees and translates within about 18px across the available scroll distance. Keep upright labels, coherent tangent/point relationships, and clipped off-page geometry. Reverse continuously; short damped catch-up stops after settling.
- About local progress is based on each figure passing through viewport, clamped 0..1 and reversible. No motion for offscreen figures; at most one dominant moving focus (nearest viewport centre).
- Harmonic: retain full faint graph; moving dark trace segment and small cursor follow the real a=3,b=2,phi=pi/2 curve.
- Scale: emphasize velocity/dimension guides as the study crosses the viewport, then the complete Fr/Re formulas. Do not break formula terms apart.
- Friction: marker follows the actual Conn Cf/Re curve, with synchronized horizontal/vertical projections to axes. No fake ship measurement/readout.
- Power: velocity and opposing resistance vectors emphasize in sequence with the complete effective-power equation. No disappearing prose.
- Native route reveal cleanup remains authoritative; real scroll cancels route masking as before. Replays and entering workspace cancel pending scroll jobs/sounds.

## File responsibilities

- New `web/frontend/src/portfolio/TitleEntry.tsx` plus narrowly scoped CSS: shared title and secondary preview link.
- New `web/frontend/src/portfolio/ReadingRuler.tsx`, `readingScroll.ts`, `scrollStudies.ts` (or a comparably small cohesive decomposition): section projection, lifecycle, event-driven motion painting.
- Modify `Portfolio.tsx`, `ProjectDetail.tsx`, `AboutContent.tsx`, `Contact.tsx`, `RailNav.tsx` only as needed for composition, refs and section metadata.
- Modify `pageGeometry.tsx/.css`, `content.css`, `portfolio.css` for measured SVG groups, sticky headings and controls; `previewAudio.ts` for the quieter section voice; `theme.ts` for manual preference.
- Add focused behavior tests under `src/__tests__`; update existing entry/control assertions without discarding navigation, lifecycle, data or accessibility coverage.
- Update `docs/formfield/CHANGELOG.md` and add a concise local handoff when verified. Clearly distinguish implementation, verification and deployment.

## Review Focus

1. Pointer quickly crosses title/project gap and reverses; preview must continue, hidden link must not swallow clicks. Test in entry cluster.
2. Existing keyboard/modified links and return focus survive title replacement. Test route/control cluster.
3. Rapid scroll, boundary jitter and programmatic layout changes must not emit repeated or unsolicited sounds. Test controller with fake geometry/time.
4. Route replacement, replay, hidden tab and dynamic reduced-motion must clean up jobs and preserve visible content. Test lifecycle cluster.
5. Short page/viewport, font resize, bottom section and missing browser SVG methods must clamp geometry and leave a usable static fallback. Test controller math and browser desktop layouts.

## Task 1: Title entry and header controls

- [x] Add behavioral tests for real tool entry through both H1s, secondary focus transfer, preview reversal/hold, no SYSTEM mode, icon replay/sound access and persisted manual theme.
- [x] Run that feature cluster to observe expected failures, then implement the component and existing-route integration. Keep original glyph metrics when isolating the i dot.
- [x] Run `npm.cmd run test -- src/__tests__/portfolio.test.tsx src/__tests__/portfolio-content.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/workspace-motion.test.tsx` and new entry tests together.

## Task 2: Reading ruler, sticky titles and section sound

- [x] Add pure controller tests for clamped section projection, hysteresis, gesture arming, traversal debounce, mount/resize silence and cleanup.
- [x] Implement section metadata, sibling navigation rail wrapper, section focus/scroll and sticky title styles. Reuse audio lifecycle/throttle; add section voice bounds to audio tests.
- [x] Run new reading tests plus existing preview-audio and route tests as one cluster. Preserve plain native scroll and instant reduced-motion target behavior.

## Task 3: Scroll-linked diagrams

- [x] Test bounded/reversible progress, real Cf curve coordinates and lifecycle/static fallback with no SVG geometry API.
- [x] Implement SVG groups/projection cursor and event-driven paint with a bounded settling tail. Full figures/formulas remain legible in every state.
- [x] Run scroll/geometry/route cluster once; ensure page transition cancellation remains covered.

## Task 4: Independent acceptance

- [x] Codex reads all changed files, checks protected paths and runs `npm.cmd run test` then `npm.cmd run build` in `web/frontend`, plus `git diff --check` at repo root.
- [x] Browser at 1440/1280/1024: Work and detail title previews, i dot isolation, gap crossing, project/tool round trip, replay/sound/theme, keyboard, sticky title release, proportional ruler and About figure progression. Check light/dark, dynamic reduced-motion, no horizontal overflow or leftover masks.
- [x] Record exact passing totals and known validation limits in handoff. Leave reviewed local preview available. Implementation does not imply commit or release.

## API references checked during planning

- MDN `Window.scrollY`: https://developer.mozilla.org/en-US/docs/Web/API/Window/scrollY (clamp overscroll; fractional coordinates).
- MDN CSS `position`: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/position (sticky constrained by its containing block).

## Acceptance record

Completed locally on 2026-10-07. Codex independently accepted 28 frontend test files / 496 tests (0 skipped), a 95-module production build, and desktop browser checks. See [acceptance handoff](../../formfield/scroll-acceptance-2026-10-07.md). No commit, push or deployment in this round. Audio lifecycle and envelope were tested; subjective listening remains unverified.
