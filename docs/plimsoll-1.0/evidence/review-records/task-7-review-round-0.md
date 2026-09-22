### Spec Compliance

- ❌ Issues found: Task 7 implements the requested systems, Holtrop, Taylor/Schoenherr, engine, source-case, and test surfaces, but it does not fully satisfy the fixed missing-versus-zero, source-specific provenance, and strict Taylor source-axis contracts. The blocking details are under Important.
- ⚠️ Cannot verify from this task diff: `analysis.resistance_for_loading`, selected-state/scenario/QPC assembly, and export/UI propagation belong to Task 8 and are not Task 7 failures.
- ⚠️ Cannot verify from this task diff: the fixed benchmarks establish formula/table conformance, not historical Queen Mary accuracy or broad empirical validity. The source audit was not repeated, per the review instructions.
- ⚠️ Test boundary: accepted frozen evidence reports 482 tests, 0 failures/errors in 137.817 s, and the implementer reports 115 targeted tests green. I did not rerun either suite.

### Strengths

- `tools/plimsoll/systems.py:234`, `tools/plimsoll/systems.py:349`, `tools/plimsoll/systems.py:370`: linked item IDs are deduplicated for totals, cross-system ownership is blocking, and the result explicitly names the selected loading ledger as the sole mass authority. Physical calculations become review proposals rather than extra mass (`tools/plimsoll/systems.py:328`).
- `tools/plimsoll/engines.py:67`, `tools/plimsoll/engines.py:251`, `tools/plimsoll/engines.py:317`: endurance keeps fuels separate, partial bunker data is exposed only as a known subtotal, and explicit zero remains distinct from unknown.
- `tools/plimsoll/holtrop.py:370`, `tools/plimsoll/holtrop.py:459`, `tools/plimsoll/holtrop.py:475`: the full resistance aggregation is explicit, optional-scenario completeness is separated from arithmetic availability, and `primary_result` is separated from the numerical result. The independent component benchmark and algebraic identities in `tools/plimsoll/tests/test_holtrop.py:46` and `tools/plimsoll/tests/test_holtrop.py:69` are strong tests rather than a total-only fit.
- `tools/plimsoll/resistance.py:248`, `tools/plimsoll/resistance.py:279`: strict Taylor out-of-domain and missing-corner cases return unavailable with blocking structured diagnostics, while the legacy clipping/renormalization path remains separately named.
- `tools/plimsoll/tests/test_systems_integration.py:97`, `tools/plimsoll/tests/test_systems_integration.py:110`, `tools/plimsoll/tests/test_systems_integration.py:123`: the tests directly protect ledger authority, review-only proposals, and installed-versus-broadside count semantics.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- `tools/plimsoll/systems.py:212`, `tools/plimsoll/systems.py:217`, `tools/plimsoll/systems.py:274`, `tools/plimsoll/systems.py:363`: a row declared `status: "present"` with `weight_item_ids: []` is accepted as complete, receives `ledger_mass_t: 0.0`, and can make the whole summary complete with `linked_total_mass_t: 0`. That converts missing ownership/mass into a known zero and bypasses the documented explicit-absence route at `docs/plimsoll-1.0/systems-resistance-contract.md:58`. The focused probe returned `{'complete': True, 'row_mass': 0.0, 'linked_total': 0, 'diagnostics': []}`. Require at least one linked ledger item for a present system, or require a separately named, sourced declaration for a genuinely zero-mass present system; otherwise emit a blocking diagnostic. Add a test beside `tools/plimsoll/tests/test_systems_integration.py:205`, which currently covers only an entirely empty systems object.
- `tools/plimsoll/systems.py:312`, `tools/plimsoll/systems.py:313`, `tools/plimsoll/systems.py:328`: physical mass models can omit `source` and `estimate`, yet still calculate a mass and emit a review-required ledger replacement proposal. Project normalization only checks that `systems` is a dict (`tools/plimsoll/project_io.py:785`), so there is no upstream provenance gate. This violates the fixed source-specific/provenance requirements in `.superpowers/sdd/2026-09-22-plimsoll-1.0/task-7-brief.md:9` and `.superpowers/sdd/2026-09-22-plimsoll-1.0/task-7-brief.md:10`. Validate a non-empty source and boolean estimate before calculating or proposing; estimated empirical inputs should also retain their declared dependencies/provenance. Add negative tests for missing and malformed metadata.
- `tools/plimsoll/resistance.py:197`, `tools/plimsoll/resistance.py:207`, `tools/plimsoll/resistance.py:181`: strict Taylor mode accepts a table with no `source_axes.l_over_volume_cuberoot` and reconstructs the source axis from the compatibility `volumetric` axis, although the published Task 7 contract says generic tables must provide exact headings explicitly (`docs/plimsoll-1.0/systems-resistance-contract.md:207`). A focused synthetic probe returned a complete strict result (`cr=0.015`) with `source_axes_present=False`. In addition, the tracked-table adapter accepts heading-to-node disagreement at `abs_tol=5e-10`, while the fixed benchmark requires `1e-10` (`docs/plimsoll-1.0/taylor-benchmark-design.md:37`). Require the exact source-axis declaration for strict mode and validate its node association at the fixed algebraic tolerance; update the synthetic strict fixtures at `tools/plimsoll/tests/test_resistance.py:112` to declare the source axis explicitly.

#### Minor (Nice to Have)

- `tools/plimsoll/holtrop.py:24`, `tools/plimsoll/holtrop.py:60`, `tools/plimsoll/holtrop.py:63`: all `_number` failures construct `HoltropInputError` without a field path, so the structured diagnostic path remains the default `$` even though the message names the field. The test at `tools/plimsoll/tests/test_holtrop.py:237` checks only that a `path` key exists (`tools/plimsoll/tests/test_holtrop.py:247`). Pass precise paths such as `$.speed_kn` and indexed appendage paths into the exception, and assert their values.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The resistance formulas, compatibility separation, ledger ownership checks, and independent tests are substantial and carefully implemented. The present-system zero collapse and untraceable mass proposals violate core data-integrity rules, and strict Taylor mode currently overstates the source-axis declaration it has actually verified.
