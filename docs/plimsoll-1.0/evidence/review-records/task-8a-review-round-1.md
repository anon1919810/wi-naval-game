# Task 8A independent review — round 1

Fix target: `93218ff..b2ffe83ed53b6a5d445301e0a29794be74e26570`

Scope: only the six paths in
`task-8-review-93218ff-b2ffe83.diff`, reviewed against the five findings in
`task-8a-review-round-0.md`. The unchanged geometry/stability adapters and all
other Task 8 work were not rereviewed.

## Verdicts

**Specification verdict: APPROVED WITH ONE MINOR FOLLOW-UP.** Both Important
round-0 findings and all three Minor round-0 findings are materially addressed.
Malformed L0/deck inputs can no longer bypass validation, missing direct-input
sources are explicit, the shape diagnostic is correctly routed, defaulted
estimate states are serialized, and cleanup no longer masks the primary save
failure. I found no Critical or Important regression in the fix diff.

**Code-quality verdict: APPROVED WITH ONE MINOR FOLLOW-UP.** Validation is now
ordered before physical-state early returns, deck validation has one shared
helper, and persistence preserves the primary exception without scanning or
deleting unrelated files. One new assumption-reporting detail overstates which
optional estimate defaults were actually used; it does not alter calculations
or file durability.

## Round-0 finding dispositions

1. **Important — malformed fields bypass early returns: ADDRESSED.**
   `tools/plimsoll/geometry_analysis.py:76-101` validates both draft spellings,
   all numeric fields, all estimate flags, and the source-map type before the
   missing-input return at lines 105-109 or shape-limit return at lines 127-134.
   `deck_immersion_events` validates the finite keel and supplied deck at lines
   463-469 before inspecting any equilibrium result. Null deck remains unknown.

2. **Important — empty source map treated as complete provenance: ADDRESSED.**
   `tools/plimsoll/geometry_analysis.py:90-101` treats absent/null/empty maps as
   supplying no provenance and emits both the map-level diagnostic and per-input
   missing-source diagnostics. `inputs` remains the literal caller copy, and the
   comparison source remains null rather than fabricated.

3. **Minor — shape-limit diagnostic points to `$.geometry`: ADDRESSED.**
   `tools/plimsoll/geometry_analysis.py:131-134` now uses `$.hull`.

4. **Minor — default estimate states only indirectly visible: ADDRESSED, with
   the narrower Minor finding below.** `tools/plimsoll/geometry_analysis.py:118-125`
   records each effective default as a sourced assumption and diagnostic while
   retaining original nulls in `inputs` and direct-input trace provenance.

5. **Minor — cleanup masks primary save failure: ADDRESSED.**
   `tools/plimsoll/project_store.py:53-70` catches the primary failure, attempts
   only the owned-path unlink, adds cleanup failure details to the same exception,
   and re-raises it. Successful `os.replace` consumes the temporary path and
   needs no follow-up unlink.

## New findings

### Critical

None.

### Important

None.

### Minor

1. **Estimate defaults are reported as “used” for absent optional values.**

   `tools/plimsoll/geometry_analysis.py:118-125` defaults all four estimate flags
   and emits `l0.default_assumption` for each one whenever the flag is absent or
   null. This includes `kg_is_estimate=True` when `kg_m` is absent and
   `displacement_unit_is_estimate=True` when `displacement_normal_t` is absent.
   Those defaults do not affect any quantity in that request, yet the diagnostic
   says they were used. The new test at
   `tools/plimsoll/tests/test_geometry_analysis.py:350-364` also expects the
   displacement estimate assumption without supplying reference displacement.

   This makes the assumptions list noisier and slightly overstates dependency
   provenance, contrary to its “actual arguments/used defaults” meaning. Default
   the KG and displacement estimate flags only when their corresponding optional
   value is present; retain the Cwp flag when Cwp is supplied or defaulted and
   the block-coefficient flag when the required coefficient is present. Numerical
   output is unaffected.

## Review evidence

I reviewed the updated fix section in `task-8-report.md`, the original phase
brief, the round-0 report, and the complete six-path supplied diff. I did not
rerun the recorded 97 targeted tests or the older shared suite, as directed. No
focused probe was needed because the remaining issue is directly determined by
the new unconditional flag loop and its test expectation.

The producer records 30 geometry, 18 persistence, 28 hydrostatics, and 21
project-I/O tests passing with actual Python 3.13.14, plus clean diff checks and
frozen hashes. That is producer evidence for the fix; this report does not
recharacterize it as an independent rerun.

## Unverified integration boundaries

- Persistent opening knowledge/origin and null-versus-empty save/reload behavior
  remain assigned to Task 8B. Scenario-level workarounds do not establish that
  canonical persistence contract.
- Immutable coordinator snapshots, recomputed request identity, calculator
  composition, external reference-content import, and cross-stage diagnostic
  preservation remain later integration work.
- Core CLI/batch/sweep and JSON/CSV export remain required by the current
  core-only scope. UI, deployment, HTML display, game export, and standalone
  packaging are deferred and were not assessed.
- The earlier shared 545-test run predates this fix. The targeted 97-test record
  covers the changed paths; a later controller-coordinated shared regression is
  still the integration gate.

