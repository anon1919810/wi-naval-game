### Spec Compliance

- ❌ Issues found: the Queen Mary reserve-feed-water masses do not reproduce their declared algebraic assumptions at the binding `rel_tol=1e-10`. The normal item stores `411.499` for `1.5% * 27000 long_ton * 1.0160469088`, whose exact result is `411.498998064` (relative difference `4.70e-9`), and the deep override stores `685.832` for the documented 2.5% scenario, whose exact result is `685.83166344` (relative difference `4.91e-7`). See `tools/plimsoll/tools/gen_project_cases.py:358` and `tools/plimsoll/tools/gen_project_cases.py:394`; the rounded resulting totals are then asserted verbatim at `tools/plimsoll/tests/test_project_cases.py:135-136` instead of testing the formulas.
- ⚠️ Cannot verify from diff: the historical accuracy and exact wording of the cited external primary/secondary sources. The diff does verify that source status, unresolved boundaries, and historical-validation limits are recorded in `docs/plimsoll-1.0/case-sources.md:10-56` and `docs/plimsoll-1.0/case-sources.md:109-120`; source-content verification would require consulting those external works.

### Strengths

- The generator cleanly centralizes schema, unit, coordinate, group, source, uncertainty, and damage-preset construction (`tools/plimsoll/tools/gen_project_cases.py:21-141`). Queen Mary geometry is materialized with the required schema and `-9.9 m` keel datum, while the reference fixtures are independent and analytic (`tools/plimsoll/tools/gen_project_cases.py:156-169`, `tools/plimsoll/tools/gen_project_cases.py:464-527`).
- Queen Mary has all nine required groups, explicit inclusion boundaries, unique per-item ownership, no residual mass, separate raw displacement comparisons, normal/deep engineering scenarios, and systems that only reference weight-item IDs (`tools/plimsoll/tools/gen_project_cases.py:188-253`, `tools/plimsoll/tools/gen_project_cases.py:377-451`).
- The tests exercise real normalization/loading, byte-for-byte regeneration, independent mass anchors, analytic geometry, and explicit compartment/opening/dry-state contracts (`tools/plimsoll/tests/test_project_cases.py:59-95`, `tools/plimsoll/tests/test_project_cases.py:97-186`, `tools/plimsoll/tests/test_project_cases.py:188-226`). The report clearly labels proposed mutation coverage as reasoning rather than performed evidence.
- Mechanical inspection of every materialized payload from the review diff found nine groups in each project, unique item IDs and ownership tokens, resolved system references, finite strictly ordered station data, symmetric transverse sections, uncertainty intervals containing each Queen Mary nominal, and the intended geometry bounds/datum: box 3 stations with `z=0..8`, steamer 81 with `z=0..8`, and Queen Mary 141 with `z=-9.9..5.1`.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- `tools/plimsoll/tools/gen_project_cases.py:358`, `tools/plimsoll/tools/gen_project_cases.py:394`, `tools/plimsoll/tests/test_project_cases.py:135-136` — reserve feed water is rounded independently from its stated formulas, so the generated fixture and tests violate the binding tolerance for exact algebraic/unit anchors. Derive both masses from `27000 * LONG_TON_TO_T` at generation time, update the committed payloads/documented totals, and assert the 1.5% and 2.5% formulas directly at `rel_tol=1e-10` rather than locking in rounded totals.

#### Minor (Nice to Have)

None.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The fixture structure, provenance boundaries, ownership, geometry, and tests are otherwise strong and match the Task 3 design. The feed-water literals are a small numerical change, but they contradict an explicit acceptance tolerance and allow tests to certify values that do not match their own declared formulas.
