### Finding Verdicts

- **Reserve feed water was rounded independently from its stated 1.5% and 2.5% formulas, violating the binding `rel_tol=1e-10` algebraic-anchor tolerance** — ADDRESSED. `tools/plimsoll/tools/gen_project_cases.py:221-222` now derives both masses from `27_000 * LONG_TON_TO_T`; `tools/plimsoll/tools/gen_project_cases.py:360` uses the normal value and formula-derived bounds, and `tools/plimsoll/tools/gen_project_cases.py:396` uses the deep value. The regenerated Queen Mary payload contains `411.498998064` and Python's exact binary-float rendering `685.8316634399999` at `tools/plimsoll/cases/projects/queen_mary_1913.project.json:111521` and `tools/plimsoll/cases/projects/queen_mary_1913.project.json:110260`. `tools/plimsoll/tests/test_project_cases.py:135-166` independently calculates both formula values, asserts the effective item masses at `rel_tol=1e-10`, and builds scenario totals from the independently calculated components instead of hard-coded aggregate literals. `docs/plimsoll-1.0/case-sources.md:103-110` now records the full-precision inputs and corrected totals.

### New Breakage in the Fix Diff

None. The four-file fix is internally consistent: generator, materialized Queen Mary payload, documentation, and regression assertions all carry the same formula-derived values. Generic and analytic fixtures were unchanged.

Focused arithmetic check: the formulas evaluate to `411.498998064` and `685.8316634399999`; recomputing the independently anchored ledger produces exactly `27851.62934079477` and `31926.26200617077`, matching the report and documentation. The report supplies fresh focused/relevant evidence of 43 tests passing after the fix and correctly labels the 394-test shared run as pre-fix historical evidence.

### Out-of-Scope Observations

None.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.

**Spec compliance:** Compliant for the scoped Task 3 fix.

**Task quality:** Approved.
