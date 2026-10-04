# Y’s Formfield First-Version Implementation Plan

> Execution: OpenCode was attempted twice, then cancelled after stalled implementation; Codex completed the remaining work inline. User requested implementation now and later visual refinement. Batch tests, no per-step full regression.

**Goal:** Running public portfolio homepage with approved 2.5-second splash, central interactive exhibit, and preserved Plimsoll entry.

**Architecture:** Retain existing `App.tsx` as lazy Plimsoll app. New public shell resolves public hashes versus legacy app hashes, keeps home mounted/stateful across internal navigation, and runs splash once per document. A reusable artwork composition is rendered identically in both scan layers and exhibit; clipped source top view and SVG construction geometry avoid asset substitutions.

**Tech Stack:** Existing React/TypeScript/Vite; CSS/SVG and browser animation APIs, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-04-formfield-design.md`

## Global Constraints

- Brand/copy and motion values as specified. No fabricated projects or engineering numbers.
- Existing isolated `feature/plimsoll-1.0` worktree. No desktop repository modifications, server access, deployment, backend refactors, commits or pushes in implementation run.
- Preserve the three reattached source PNGs in public assets with a source note; only top view appears.
- Public theme preferences local; existing server Theme stays light/dark only.
- Existing frontend suite is baseline evidence. One batch full frontend regression at end; no Python/core tests.

## Review Focus

- StrictMode duplicate effects: once-per-document splash, timers/animation cleanup.
- Public browse must not issue auth requests/bootstrap even after theme changes.
- Legacy project/run/report links and app return must remain functional.
- Mobile, keyboard, reduced motion and failed artwork loading must not trap splash or overflow.
- Geometry: true diagonal advancing/reversing edge, registered two-color layers, continuous fullscreen-to-exhibit transition.

## Task 1: Artwork, public composition and splash

**Files:** Create `web/frontend/src/portfolio/` modules for shell, artwork, splash, styles and theme; create `web/frontend/public/portfolio/` source asset/provenance. Implement focused functions/helpers for elapsed-phase and route classification as needed, rather than a huge single component.

- [x] Copy sources, construct correctly cropped/oriented top views and decorative SVG geometry.
- [x] Build central exhibit layout, compact brand/header, metadata and real actions. Work/About surfaces stay small and truthful.
- [x] Implement scan phases 100/800/200/700/700 ms, reverse color swap, final angle -12° and shrink/move to real exhibit geometry. Stable light/dark and reduced motion fallbacks.
- [x] Add meaningful route/timeline/no-bootstrap/navigation tests, keyboard/touch/reset support. Do not run whole suite per edit.

## Task 2: App seam and verification

**Files:** Modify `web/frontend/src/main.tsx`, minimally `web/frontend/src/App.tsx` for optional portfolio return, document first-version usage.

- [x] Lazy import Plimsoll, keep legacy hashes intact. Public page does not initialize app auth effects.
- [x] Preserve home state and intro completion across internal routes and browser Back.
- [x] Run one full frontend regression; rerun only the new portfolio file for corrections, then production build.
- [x] Review changed files and verify real browser desktop/mobile and main interactions. First-version usage and limits are in `docs/formfield-homepage.md`.
