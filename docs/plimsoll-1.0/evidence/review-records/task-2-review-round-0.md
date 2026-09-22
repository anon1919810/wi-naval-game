### Spec Compliance

- ✅ Spec compliant. The implementation defensively normalizes input, selects a known condition, applies only present override keys, preserves literal zero/null semantics and provenance, and returns the required loading schema, identifiers, units/coordinates, effective items, group rows, values, coverage, uncertainty, completeness flags, diagnostics, and condition-sensitive fingerprint (`tools/plimsoll/loading.py:337`, `tools/plimsoll/loading.py:351`, `tools/plimsoll/loading.py:377`, `tools/plimsoll/loading.py:427`, `tools/plimsoll/loading.py:443`, `tools/plimsoll/loading.py:491`).
- ✅ Unknown mass, missing positive-mass positions, empty required groups, all-zero designs, and active ownership collisions remain explicit and blocking; reference displacement is diagnostic only and never supplies residual mass (`tools/plimsoll/loading.py:404`, `tools/plimsoll/loading.py:414`, `tools/plimsoll/loading.py:366`, `tools/plimsoll/loading.py:443`, `tools/plimsoll/loading.py:470`, `tools/plimsoll/loading.py:480`).
- ✅ The conservative interval implementation uses endpoint products for signed positions, strictly positive total-mass bounds for CG division, explicit nominal dependencies, missing-estimate-bound diagnostics, and override-bound clearing (`tools/plimsoll/loading.py:224`, `tools/plimsoll/loading.py:250`, `tools/plimsoll/loading.py:271`, `tools/plimsoll/loading.py:288`, `tools/plimsoll/loading.py:298`, `tools/plimsoll/loading.py:318`, `tools/plimsoll/loading.py:382`).
- ✅ Required ownership, coverage, provenance, and interval limitations are documented (`docs/plimsoll-1.0/loading-contract.md:36`, `docs/plimsoll-1.0/loading-contract.md:51`).
- ⚠️ Cannot verify from this diff: legacy `weights.synthesize` runtime compatibility and the reported 15 legacy / 361 full-regression results live outside the changed files. The package confirms `weights.py` was untouched, and the report supplies clean results; per the review rules these suites were not repeated.

### Strengths

- The public calculations keep known partial mass/moments distinct from complete results and expose supported axes independently, preventing an incomplete contribution from becoming a plausible full CG (`tools/plimsoll/loading.py:67`, `tools/plimsoll/loading.py:446`, `tools/plimsoll/loading.py:449`, `tools/plimsoll/loading.py:457`).
- Ownership is evaluated after overrides, so overriding the standalone child to zero removes effective double counting without mutating the source project (`tools/plimsoll/loading.py:111`, `tools/plimsoll/loading.py:377`, `tools/plimsoll/tests/test_loading.py:237`).
- Tests use analytical anchors and exercise null versus zero, axis completeness, required-empty groups at 99% reference coverage, ownership overlap, validation failures, signed intervals, cleared inherited bounds, and tri-state provenance (`tools/plimsoll/tests/test_loading.py:78`, `tools/plimsoll/tests/test_loading.py:132`, `tools/plimsoll/tests/test_loading.py:183`, `tools/plimsoll/tests/test_loading.py:197`, `tools/plimsoll/tests/test_loading.py:237`, `tools/plimsoll/tests/test_loading.py:290`, `tools/plimsoll/tests/test_loading.py:317`, `tools/plimsoll/tests/test_loading.py:340`, `tools/plimsoll/tests/test_loading.py:380`).
- Focused outside-diff check for the named dependency risk: Task 1's `normalize_project` deep-copies and supplies item defaults before validation, while `validate_project` rejects malformed input; this supports the loading layer's immutability and direct-key assumptions (`tools/plimsoll/project_io.py:88`, `tools/plimsoll/project_io.py:704`, `tools/plimsoll/project_io.py:802`).

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

- `tools/plimsoll/loading.py:389`: `loading.uncertainty_override_cleared` reports a path shaped like `$.loading_conditions.<condition-id>.overrides...`, but `loading_conditions` is an array. This prevents a consumer from resolving the diagnostic to the actual input element and becomes ambiguous for IDs containing path punctuation. Retain the selected condition index and emit the same indexed path convention used for weight items, with safe object-key notation for the override ID.

### Assessment

**Task quality:** Approved

**Reasoning:** The implementation satisfies Task 2's numerical and semantic requirements with independent behavioral tests and clear separation between nominal completeness, provenance, coverage, and uncertainty. The diagnostic-path defect is localized metadata quality and does not affect loading results or certification decisions.

**Review check:** No tests were run; the reported focused, legacy, and full-suite executions already cover the reviewed behavior, and code inspection raised no unanswered numerical doubt requiring a probe.
