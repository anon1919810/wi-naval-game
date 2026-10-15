# Verification Reliability and Inclined Stability Implementation Plan

> For agentic workers: Codex plans, reviews and independently accepts; OpenCode implements bounded units. User approved this order with “开始吧”. No further execution-method approval is needed.

**Goal:** Recover safely from transient Windows report replacement denial, then provide independently validated small-perturbation stability for trimmed loading equilibria and honest roll availability.

**Architecture:** Preserve the report writer's destination ownership, immutable source identity, JSON-last publication and runner deadlines. Add a separately versioned inclined-equilibrium stability result; do not relabel upright KM/GM or empirical concept scores.

**Tech stack:** Existing Python standard library and pytest; existing frontend only where required for interpreting new physical results. No new runtime dependencies.

**Spec:** The approved two priorities in this conversation, original comparison F08/F06, and current `docs/plimsoll-1.0/concept-design-coverage.md` boundaries.

## Global constraints

- Preserve all existing dirty work. Baseline: chat `work/plimsoll-reliability-stability/baseline.json`, with selected complete source backups.
- No staging, commits, resets, cleaning, deployment, security-policy changes or broad process termination.
- No inferred real-ship inertia, geometric details, historical validity or target-matching ballast.
- Keep upright hydrostatics, geometry limits and empirical concept-design results distinct.
- Save diagnostics and partial/failure evidence honestly. A worker report does not count as acceptance.

## Review focus

1. A replacement failure followed by a changed target or stolen lock must refuse publication, not overwrite it after sleeping.
2. Permanent denial and non-transient I/O errors terminate within a bounded retry budget; no retries after the caller's remaining budget.
3. The authoritative JSON stays last. Mixed generations, publication errors and total deadline failures cannot become a passing run.
4. Inclined stiffness depends on explicit axes and constrained/free degrees of freedom; analytic and numerical checks must validate those conventions.
5. Unknown inertia or unsupported geometry keeps roll unavailable. A positive static stiffness is not a full dynamic or safety validation.

## Task 1: Report publication recovery (F08)

**Files:** `tools/plimsoll/verification_report.py`; narrowly scoped CLI callback changes in `tools/plimsoll/app.py` if needed to pass a monotonic retry deadline; focused new tests and one status document. Existing verification modules contain pre-existing work and must be preserved.

- [x] Capture baseline tests and the prior real failure evidence.
- [x] Write and run failing tests for transient WinError 5/32/33 replacement failures, permanent failures, changed target/lock after a failure, deadline exhaustion, and JSON-last integrity.
- [x] Retry only identified transient replacement failures. Use finite attempt/backoff constants, revalidate ownership and expected destination bytes before every attempt, reuse only the owned temporary, and preserve existing cleanup/failure semantics.
- [x] Keep retry waiting inside the publication/caller budget. The initial non-retried publication of final timeout evidence may still be necessary; do not pretend synchronous filesystem calls are hard-preemptible.
- [x] Independently run focused report/CLI/runtime tests, real repeated `verify --suite quick` commands and publication stress on this Windows host.

Acceptance command:
`web/backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tools/plimsoll/tests/test_verification_report.py tools/plimsoll/tests/test_cli_verify.py tools/plimsoll/tests/test_verification_runtime.py tools/plimsoll/tests/test_verification_publication_retry.py`

## Task 2: Inclined-equilibrium small-perturbation stability (F06)

- [x] Inspect current geometry, equilibrium, GZ, free-liquid and roll contracts; pin the method and supported degrees of freedom before delegation.
- [x] Record the coordinate/sign convention, units, unavailable conditions and independent analytic references in a method design.
- [x] Write failing analytic and boundary tests, then implement the smallest separate kernel and coordinator integration.
- [x] Verify upright reduction, trimmed analytic bodies, symmetry, datum/scale transforms, perturbation refinement and independent restoring-lever checks.
- [x] Surface the new result with its definition and applicability; preserve unavailable roll without sourced inertia.
- [x] Recompute normal/deep Queen Mary cases, report geometry/inertia/resistance limitations, and run affected core/backend/frontend acceptance.

Task 2 API and tolerances were pinned in docs/plimsoll-1.0/inclined-small-angle-stability-design.md before implementation; final independent results are in docs/plimsoll-1.0/reliability-stability-2026-10-15.md. F07 migration, full SPS layout, cost and unrelated resistance-model expansion are outside this iteration.
