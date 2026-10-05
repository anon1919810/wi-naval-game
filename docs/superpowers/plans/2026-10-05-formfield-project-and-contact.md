# Formfield project detail and contact implementation plan

> For agentic workers: use the approved design below and the OpenCode delegation workflow. Codex owns review and acceptance. User preference overrides per-step test runs: verify the complete feature cluster once, then rerun only checks affected by defects.

**Goal:** Complete the English public portfolio with a Plimsoll detail page, factual technology stack and an author/contact page while preserving the existing tool entry.

**Architecture:** Extend the existing public hash classifier with `#/work/plimsoll`. Keep `#/plimsoll`, `#/projects`, `#/runs` and `#/reports` owned by the existing application. Reuse the public shell, right rail, artwork and transition controller; extract focused content components rather than another app or router.

**Tech stack:** Existing React/TypeScript/Vite, SVG/CSS and progressively enhanced browser View Transitions. No new dependencies.

**Spec:** User approved the next-round design in this conversation on 2026-10-05. Existing layout contract: `docs/formfield/sidebar-typography-2026-10-05.md`.

## Global constraints

- Desktop scope; maintain existing narrow-width fallback without a mobile redesign.
- Space Grotesk headings, Inter body. Preserve parallel font work and existing uncommitted files. No wholesale replacement of shared CSS.
- Header remains brand/theme only; persistent right rail remains Work/About. Detail belongs to Work.
- Home retains its detailed top-view drawings, 2500ms decode-gated opening, image controls and lens. Internal returns never automatically replay the opening.
- Only real capabilities and real screenshots; no fake calculations, statistics, credentials or project repository claims. Public pages never bootstrap a workspace or call its API.
- Contact email: `youxiang051110@163.com`; public profile: `https://github.com/anon1919810`.
- No backend, solver, Unity, dependency/lockfile or production deployment changes.

## Files and responsibilities

- Modify `web/frontend/src/portfolio/routes.ts`: exact detail route before the existing first-segment rules.
- Modify `Portfolio.tsx`: render detail/about content, route transitions, focus/scroll and home/tool return context.
- Create focused public content/contact components and a scoped supplementary stylesheet in `src/portfolio/`.
- Modify `transitions.ts` and add scoped transition CSS: home/detail artwork morph, 400ms, reduced-motion/unsupported fallback and latest-navigation-wins retirement.
- Add `public/portfolio/plimsoll-report.jpg` copied from the inspected real `docs/plimsoll-1.0/evidence/public-report-2026-10-04.jpg`.
- Add a focused test file for detail routing, API isolation, contact success/failure and navigation preservation. Existing tests remain applicable.
- Document final behavior, asset/source paths and verification in `docs/formfield/`.

## Approved content and visual design

Detail: BACK TO WORK, large Plimsoll heading, compact geometric artwork hero, OPEN PLIMSOLL. Numbered editorial sections: Overview, Capabilities, Workflow with real report image, Technology, Methods & Limits. Use flat rows, rules, generous spacing and the existing accent, not a generic card wall. Source material: latest `docs/plimsoll-1.0/advanced-workflow-handoff-2026-10-04.md` and manifests. State simplified damage and unknown/estimated inputs honestly; do not claim full SPS reproduction, CFD, structural or combat impact simulation.

Technology explains uses: React/TypeScript/Vite/SVG-CSS for interface; Python core; FastAPI and SQLAlchemy/Alembic for service; PostgreSQL and independent worker for storage/execution. Public About includes author Yang Duanming, tools/experiments direction, Built With for this site and GET IN TOUCH with mailto, COPY EMAIL and GitHub. No invented biography or contact form.

## Implementation cluster

- [x] Extend exact routing and content components; homepage adds VIEW PROJECT alongside the direct OPEN PLIMSOLL entry.
- [x] Implement About/contact, including visible success only after clipboard resolves and honest failure fallback.
- [x] Extend transition controller: home/detail morph reuses the selected drawing and names only visible elements; public chrome stays still. Direct deep link skips opening. Entering detail/about starts at top; returning home restores its scroll, selected reference and pan. Tool return respects the public entry context. Preserve Back/Forward, modified clicks, focus and replay.
- [x] Add meaningful tests after the implementation cluster, then run targeted tests and build once.
- [x] Codex independently reviews changes, runs final concentrated frontend checks, checks actual desktop browser and saves evidence/documentation and a scoped local commit.

Final evidence: `docs/formfield/project-detail-and-contact-2026-10-05.md`; 187 frontend tests and production build passed independently. No mobile or production deployment work.

## Review focus

1. Detail URL must not resolve to home or accidentally mount the tool. Legacy app URLs keep ownership.
2. Public detail/about remain usable without API and never create an anonymous workspace.
3. New View Transition names are unique among visible nodes; repeated navigation and reduced motion cannot strand state.
4. Returning home preserves exploration; long detail/contact navigation does not land midway through the new page or retain invisible focus.
5. Clipboard missing/rejection never shows Copied; contact links remain usable without clipboard access.

## Acceptance

From `web/frontend`: `npm.cmd run test -- src/__tests__/portfolio.test.tsx src/__tests__/portfolio-transitions.test.tsx src/__tests__/portfolio-content.test.tsx` and `npm.cmd run build`. Codex will run the final frontend suite once if all changes are frozen; no calculation-core regression is needed for these public-only changes.

Browser: 1024 and 1440 desktop; light/dark; detail deep link; Work/About/detail and tool return; contact copy; no horizontal overflow; new public pages work independently of API. Separately diagnose the user's local tool connection error with existing operations instructions; never initialize or overwrite a production database.
