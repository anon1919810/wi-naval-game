# Liquid glass integration implementation plan

> Execution: OpenCode implements this bounded unit; Codex independently reviews and accepts it, as required by the user's AGENTS.md. No commit or deployment.

**Goal:** Apply the approved clear glass prototype to the local Formfield/Plimsoll navigation, primary controls and tool entry cards.

**Architecture:** One eagerly imported, scoped CSS module owns reusable `--ff-glass-*` material tokens and explicit adapters for existing component classes. Preserve the current React markup, event handlers, typography, layout and data flow. The source prototype is `C:/Users/杨睿/Documents/Codex/2026-10-15/https-ruiqichenbiec-github-io-design-systems/outputs/glass-preview/styles.css`.

**Tech stack:** Existing React, TypeScript, Vite and CSS; no new dependencies.

**Spec:** The user approved the clear prototype (92% UI transparency setting, 0.077 surface tint, 16px Gaussian backdrop blur, strong polished button edges) and the proposed navigation/button/tool-card integration in this chat with “接入吧”. This plan records implementation choices within that approved scope.

## Constraints and review focus

- Modify only `web/frontend/src/main.tsx` and create `web/frontend/src/styles/liquid-glass.css`; this plan is the only documentation addition. The checkout has unrelated dirty work, including Library and Workbench. Preserve it.
- Scope material tokens to `.ff-shell`, `.app-shell`, `.ff-tool-shell` and reusable `ff-glass-*` classes. Do not replace global brand, typography, canvas, semantic error/warning colors or theme state. Read both the root `data-theme` and public `data-ff-theme` conventions correctly.
- Public surfaces: compact header controls, drawing tool buttons/picker, and a restrained glass treatment behind the existing large-type rail navigation. Preserve all rail glyph/underline animations, drawing controls' absolute positioning and title-entry hit areas/pseudo-elements.
- Workspace surfaces: main `.button`/`.icon-button` controls, selected chapter navigation, sticky toolbar/header and template entry cards. Keep dense editor fields, table cells and report text on their existing reading surfaces. Do not turn every element into a blurred layer.
- Blur only bounded surface containers or standalone glass controls; child buttons use transparent fill/rims/shadows without nested backdrop filtering. No ancestor opacity/filter changes, WebGL, SVG filters, new animation loops or animated blur.
- Maintain disabled, busy, pressed, current, destructive and focus-visible distinctions. Decoration cannot intercept events or cover text. Hover must not override pressed feedback; respect existing motion/audio behaviors.
- Preserve 390px mobile layout, dark-theme contrast, reduced-motion behavior and print output. Use an opaque readable fallback if backdrop filtering is unsupported.
- Do not use the prototype's demo JS, reset styles, scene backgrounds or fonts. Keep the site's existing content and imagery.

## Task 1: Material module and adapters

- [x] Read the prototype's variable, surface and button recipes and the site's existing CSS specificity/pseudo-elements.
- [x] Add `liquid-glass.css` with prefixed material variables, reusable surface/button recipes, light/dark overrides, bounded adapters, focus/disabled/hover/active handling, reduced motion, print and unsupported-browser fallback.
- [x] Import it eagerly after existing base/workspace CSS in `main.tsx`. Ensure adapters survive the workspace chunk's later stylesheet insertion using scoped selectors, without `!important` proliferation.
- [x] Preserve existing component dimensions and positions; any optical rim must fit the current hit target and must not create horizontal overflow.

## Task 2: Acceptance

- [x] From `web/frontend`, run `npm.cmd run build` and `npm.cmd run test`. Report existing failures without modifying unrelated implementation or tests.
- [x] Run `git diff --check -- web/frontend/src/main.tsx web/frontend/src/styles/liquid-glass.css docs/superpowers/plans/2026-10-15-liquid-glass.md` and inspect the exact changed files.
- [x] Codex independently checks real local public and anonymous workspace pages: light/dark, language switch, navigation and drawing tools, template entry, button disabled/focus/pressed states, 390px mobile layout and console errors. Use a disposable local SQLite database for workflow checks.
- [x] Capture real-page screenshots and provide the local preview URL. Do not claim performance benchmarking or production deployment.

## Acceptance evidence — 2026-10-15

- Codex independently built the frontend successfully. Vite retains the existing large-chunk warning.
- Final complete suite: `npm.cmd run test -- --reporter=dot --maxWorkers=4`, **57 files / 933 tests passed** (91.21 s). An earlier full run observed one armour unit-display failure while other feature files were changing; the isolated armour suite then passed 15/15 before this final complete pass. Those feature files were not edited for glass integration.
- Browser: real public, library and workbench pages on `http://127.0.0.1:5173/`, with a disposable SQLite backend. Light/dark, English/Chinese, navigation, drawing selection, inspect toggle and template project entry were checked. At a 390 px viewport the public, library and workbench document widths did not exceed the viewport.
- Computed styles confirm 11 px buttons/navigation, 12 px icons and bounded 16 px backdrop blur. Primary/selected/disabled controls, visible keyboard focus, pressed-vs-hover depth, reduced-motion transforms and print reset were checked through browser developer emulation; all emulation and viewport overrides were restored.
- Read-only review findings were repaired: workspace specificity, primary state precedence, picker pressed depth, selected navigation marker, print precedence, standalone focus and unsupported-filter fallback. The unsupported-browser fallback was source-reviewed; no older-browser compatibility or performance benchmark is claimed.
- Screenshots are in the chat workspace's `outputs/site-integration/`. Local preview only; no commit or deployment.
