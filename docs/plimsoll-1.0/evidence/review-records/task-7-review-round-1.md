# Task 7 independent review — round 1

Date: 2026-09-22

Reviewer role: independent Task 7 reviewer by explicit controller ruling after
the original reviewer resume and replacement spawn failed with the harness
thread limit. This reviewer implemented Task 8 persistence/geometry helpers,
not Task 7. Task 8 files remained frozen throughout this separate read-only
review. No Task 7 code, test, case or documentation was edited.

Reviewed fix range: `df9e83522f00fb6f06754a6992c363d116516860` to
`08b81c9749abe74bf069d34f18ae79f7e453802c`, restricted to the twelve paths in
`task-7-review-df9e835-08b81c9.diff`. Read the original round-0 findings,
Task 7 brief, round-1 fix report, scoped diff, current relevant implementation
and tests, and controller's Taylor precision ruling in `progress.md`.

## Spec compliance verdict

**Approved for the scoped Task 7 review fixes.** All four original findings
are addressed. The Taylor change follows the explicit controller clarification
of nine-decimal compatibility storage while retaining the original generic
algebraic tolerance. No newly introduced blocking spec violation was identified
within the twelve-path fix.

## Per-finding disposition

### 1. Present system with no ledger ownership — ADDRESSED

`tools/plimsoll/systems.py:251` checks an empty `weight_item_ids` list before
accumulation and emits blocking `systems.present_without_weight_items` at
`:254`. It marks the row incomplete; `:319` therefore retains
`ledger_mass_t=null`. The global blocking gate makes the summary incomplete
and `:421` keeps `linked_total_mass_t=null`. The separately named
`ledger_known_mass_t` / `linked_known_mass_t` may still be zero as empty known
subtotals; those are not represented as complete total masses.

Explicit absence still follows the existing reason-bearing absent branch.
A present system can link an actual known-zero ledger item without converting
unknown ownership into absence. There is no new residual mass or second mass
authority.

Behavioral regression: `tools/plimsoll/tests/test_systems_integration.py:242`
checks incomplete summary, null row/total mass, the blocking diagnostic and
its exact field path. Documentation at
`docs/plimsoll-1.0/systems-resistance-contract.md:25` matches this behavior.

### 2. Untraceable physical mass proposals — ADDRESSED

`tools/plimsoll/systems.py:41` adds `_physical_model_metadata`: nonempty textual
or meaningful structured source, explicit boolean model estimate and an input
object are required. Estimated models additionally require per-input provenance
covering every declared formula input, with nonempty source and boolean estimate
on each entry. Non-estimated models retain their explicit model-level provenance
without a newly invented requirement for redundant per-input declarations.

The gate is called at `tools/plimsoll/systems.py:335`, before `_calculated_mass`
and before construction of any replacement proposal. Calculated checks continue
to copy the declared inputs, sources, estimate and input-provenance objects;
the ledger remains authoritative and proposals remain review-required.

Negative regressions are at
`tools/plimsoll/tests/test_systems_integration.py:210` and `:226`.
The six new Queen Mary per-input provenance records are inserted in
`tools/plimsoll/tools/gen_project_cases.py:498`, `:522`, `:551`, `:590`, `:613`
and `:638`, with matching metadata-only insertions in the committed case.
The scoped case diff changes no accepted mass, CG, installed/broadside count
boundary or calculation formula. `tools/plimsoll/tests/test_project_cases.py:226`
checks complete provenance coverage for each weapon model.
The contract is documented at
`docs/plimsoll-1.0/systems-resistance-contract.md:66`.

### 3. Strict Taylor source-axis declaration and precision — ADDRESSED

`tools/plimsoll/resistance.py:252`–`:263` now requires an explicit aligned
`source_axes.l_over_volume_cuberoot` list and validates its association before
interpolating. The former reconstruction of source headings from the stored
compatibility axis is gone. Sorting source-heading/index pairs retains the
corresponding original cell indexes.

The validator at `tools/plimsoll/resistance.py:161` has two distinct policies:

- Generic/default `algebraic_1e-10` uses the fixed relative and absolute `1e-10`
  tolerance at `:183`–`:189`; it does not retain the former `5e-10` relaxation.
- Explicit `rounded_reciprocal_cube_9_decimal_places` requires decimal_places=9
  and compares each stored node with `round(1 / heading**3, 9)`, at relative
  tolerance zero and absolute `1e-15` for representation only (`:174`–`:182`).
  This tests the declared rounding operation, not equality to the exact cube.

The audited tracked adapter declares the printed headings by index at `:213`
and serializes the association, compatibility policy, decimal count, tolerance
and source note at `:215`–`:240`. It copies the table, leaving raw cells and
the original compatibility axis untouched. A caller-supplied generic heading
list takes the exact-association policy. Strict successful, unavailable and
speed-curve results preserve the mapping at `:314`, `:346`, `:368` and `:568`.

Regressions explicitly cover missing/incorrect source headings
(`tools/plimsoll/tests/test_resistance.py:197`), tracked by-index rounding and
unchanged cells (`:229`), a `2e-10` mismatch rejection (`:258`), and row mapping
propagation (`:286`). The midpoint assertion uses the already declared
algebraic tolerance, rather than exact Python float equality.

This matches the controller ruling in `progress.md` and its documentary
clarification at `docs/plimsoll-1.0/taylor-benchmark-design.md:38` and
`docs/plimsoll-1.0/systems-resistance-contract.md:221`. The change does not
relax source-cell tolerances, alter source data or fit trial performance.

### 4. Holtrop numeric diagnostic paths — ADDRESSED

`tools/plimsoll/holtrop.py:68` derives `$.<field>` by default. All `_number`
type, range, conversion and nonfinite failures pass that path to the structured
exception (`:71`, `:76`, `:79`, `:82`). Appendage numeric calls pass indexed
paths (`:250`, `:255`); bow-thruster numbers pass their nested paths (`:364`,
`:367`). Appendage container/row errors also identify their location.

The regression at `tools/plimsoll/tests/test_holtrop.py:249` asserts actual
`$.speed_kn` and `$.appendages[0].area_m2` values, not merely existence of the
path key. These changes affect error attribution and do not alter equations.

## New breakage and quality verdict

**Quality: Approved for this scoped fix.** No new blocking breakage found.
The changes are localized validation, metadata propagation and diagnostic
attribution. The source-axis policy is explicit rather than an implicit loose
numeric tolerance. The generator/case diff is provenance-only and the new
system gate retains the distinction between known subtotals and unknown totals.
Tests exercise observable invalid/valid behavior, source association and output
paths; they do not merely assert new function names or documentation text.

## Verification boundary

The implementer's accepted evidence is 121 targeted tests passing in 2.781 s.
Per controller instruction this review did **not** rerun those accepted tests
or the historical full suite. No concrete uncovered runtime doubt required a
new probe after reading the scoped implementation and its focused regressions.
The old 482-test result was not treated as a fresh post-fix pass.

Read-only checks performed:

- Inspected the complete twelve-path fix using grouped `git diff df9e835
  08b81c9 -- <scoped paths>` plus relevant surrounding implementation and tests.
- `git diff --check df9e835 08b81c9 -- <all twelve paths>` exited 0.
- Computed SHA-256 for all twelve current files using `Get-FileHash`; every
  value exactly matches `task-7-fix-round-1-report.md`. Thus the accepted targeted
  evidence and reviewed committed fix refer to the same Task 7 file contents.

## Out-of-scope observations

- This approval does not cover Task 8 selected-loading/scenario/QPC assembly,
  exports/UI propagation or proposal application into base versus condition
  overrides. Those remain explicitly coordinated later work.
- Historical source accuracy and the original empirical formula/table audit
  were not repeated. Metadata and benchmark conformance do not establish
  historical Queen Mary validation or general model applicability.
- Existing nonnumeric Holtrop semantic/domain exceptions are not all guaranteed
  to have field-specific paths; the original minor finding concerned `_number`
  attribution and is addressed. No broader diagnostic redesign is required by
  this review.
- Task 6 and Task 8 changes in the shared worktree were not included in this
  verdict. Task 8's own implementation and future review remain separate.

Final disposition: **4/4 original findings ADDRESSED; scoped spec and quality
verdict Approved; no new blocking findings.**
