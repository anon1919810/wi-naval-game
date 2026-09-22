# Task 4 review fix round 1 — COMMITTED_FOR_REVIEW

Base: `b7cffabc1d7c6ff7ed88424e0ba2eba5f2279ba9`.
Review: `task-4-review-round-0.md`, two Important findings.
Commit: `e12a6e38305b479c5f8026ff7c3b2d5cfb1845c3`
(`fix: report the first immersed opening correctly`). No full regression was
run for this fix. No other task, root evidence, primary
checkout or Unity files were edited. The round changes only three owned paths:
`tools/plimsoll/stability.py`, `tools/plimsoll/tests/test_stability_loading.py`,
and `docs/plimsoll-1.0/stability-api.md`. The two owned geometry modules remain
unchanged from the base. The exact three changed paths were committed after
controller authorization, matching the frozen hashes and passing both working
and staged diff-check. Post-commit index is empty; the three paths have no
working-tree difference from HEAD. No push occurred. The original reviewer is
to perform the scoped follow-up review.

## Finding 1: opening attribution

Reproduced the supplied two-opening case: angles [0,20], `first=(0,5,4.5)` and
`later=(0,10,6)`. RED: refined immersion angle was correctly near atan(.1), but
the returned opening ID was `later`. Fix selects the ID from the minimum
clearance at the returned refined equilibrium, preserving sampled attribution
only for the already-immersed sampled case. The added regression independently
checks the atan(.1) angle, bracketed-event type and `first` identity.

## Finding 2: malformed containers

RED reproductions covered the reported null `initial`, null liquid `tank` and
null curve `state`, and adjacent container/member paths: list initial/tank,
null liquid entry, null values/diagnostics/effective_items, null elements in
diagnostics/effective_items, non-array angle/opening collections and non-object
openings. Also tested unsupported geometry combined with null loading state.

Fix explicitly validates each traversed container. `_failed` does not fail
while assembling diagnostics from malformed input: it preserves usable upstream
diagnostic objects and the full original loading payload, then adds the blocking
failure diagnostic. Both curve result paths use a guarded fingerprint. Invalid
angle/opening request collections raise the documented `ValueError` before
geometry evaluation. Invalid loading/nested solver options retain failed-result
and per-row failure behavior. No `AttributeError`, `Exception` or catch-all was
added to exception handlers; implementation faults remain visible.

## Verification

Working directory:
`C:/Users/杨睿/Documents/Codex/2026-09-17/shi/work/plimsoll-1.0`.
Exact RED/GREEN command:

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B -m unittest discover -s tools/plimsoll/tests -p test_stability_loading.py
```

RED: 36 tests in 10.137 s, 2 failures and 17 subtest errors. Failures showed
the wrong opening name and accepted empty-dict opening container; errors showed
the raw AttributeError/TypeError escape paths. Existing numerical cases passed.

GREEN: **36 tests in 10.170 s, zero failures/errors**. Includes all original
force/moment, liquid stiffness, independent box/ellipsoid refinement, datum,
singularity, high-trim and legacy geometry cases. Numerical equations, root
tolerances, iteration bounds, sampling/root policy and moving-liquid method
were not changed. No broad regression repetition was needed for these fixes;
the controller owns the next shared full regression and scoped reviewer return.

`git diff --check -- tools/plimsoll/stability.py tools/plimsoll/tests/test_stability_loading.py`
returned no output. The final three-path diff-check also returned no output.
The controller subsequently authorized and this agent created only the exact
three-path commit identified above. No full-suite rerun or push was performed.
The earlier shared 482-test pass predates this review fix; it is not relabelled
as coverage of this commit. The 36-test focused run above covers this fix and
all original stability numerical tests. The next Task 6/8 shared integration
will provide the next full-suite verification.
