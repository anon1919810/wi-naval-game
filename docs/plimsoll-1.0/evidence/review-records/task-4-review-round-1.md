### Spec Compliance

- ✅ The two round-0 findings are addressed in the scoped diff from `b7cffabc1d7c6ff7ed88424e0ba2eba5f2279ba9` to `e12a6e38305b479c5f8026ff7c3b2d5cfb1845c3`.
- **Finding 1 — Addressed:** `tools/plimsoll/stability.py:494` obtains the controlling opening from the refined equilibrium returned by the immersion bracket. The already-immersed sampled path retains its sampled identity. `tools/plimsoll/tests/test_stability_loading.py:345` reproduces the two-opening ordering change and asserts both the independent atan(.1) event angle and the correct `first` identity.
- **Finding 2 — Addressed:** `tools/plimsoll/stability.py:179`, `:200`, `:237` explicitly validate diagnostic/value/item, liquid/tank and initial-attitude containers before member access. `_failed` at `:366` safely preserves usable diagnostic objects and the original malformed loading payload, and curve fingerprint handling at `:421` guards non-object loading. Opening/request validation now produces the documented ValueError before geometry evaluation (`:422`, `:434`); loading and nested solver-option errors retain structured failed results. No blanket AttributeError or Exception catch was introduced.

### Strengths

- `tools/plimsoll/tests/test_stability_loading.py:354`, `:367`, `:382`, `:390`: focused regressions cover both original null failures and adjacent malformed containers, both public APIs, no reusable failed GZ, blocking diagnostics, null fingerprints, and unsupported geometry combined with null loading.
- `docs/plimsoll-1.0/stability-api.md:103`, `:127`: documentation now describes the validated container boundaries and root-state opening attribution consistently with the implementation.
- `tools/plimsoll/stability.py:494`: the immersion fix changes event attribution only; projected moment equations, root tolerance, bounded iterations, liquid conservation and datum transformations are untouched by this diff.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None remaining from the two original findings; no new blocking issue caused by these fixes was identified.

#### Minor (Nice to Have)

- None within this scoped re-review.

### Checks and boundaries

- Read the round-1 implementation report and the supplied three-path diff once. No source rereads, Git commands, subagents, broader task review or test reruns were performed.
- The reported focused RED-to-GREEN evidence is 36 tests, zero failures/errors, 10.170 s, including the original stability numerical tests and five new regression methods. The reviewed test code exercises the identified defects directly; no additional unresolved doubt warranted another probe.
- The shared 482-test pass predates this fix and is not claimed as validation of this commit. The next shared integration run remains controller-owned. This scoped approval does not expand the earlier documented boundaries concerning downstream integration, historical validity or global branch uniqueness.

### Assessment

**Task quality:** Approved

**Reasoning:** Both demonstrated defects are corrected at their cause and have targeted behavioral regressions. The changes preserve the numerical and physical contracts reviewed in round 0, with explicit error boundaries rather than broad exception suppression.
