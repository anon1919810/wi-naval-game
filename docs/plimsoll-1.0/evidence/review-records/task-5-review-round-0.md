### Spec Compliance

- ❌ Issues found: the implementation does not fully satisfy the declared finite/representable-output domain. A supported active partial state can silently underflow a positive permeability-scaled free-surface moment to `0.0` instead of rejecting the state (`tools/plimsoll/tank_geometry.py:177-178`, `tools/plimsoll/tank_geometry.py:211`; contract at `docs/plimsoll-1.0/tank-contract.md:84-95`).

### Strengths

- Requested liquid volume is kept as the authoritative mass quantity, while integrated geometry and its residual are reported separately; the legacy adapter also derives mass from the requested volume (`tools/plimsoll/tank_geometry.py:293`, `tools/plimsoll/tank_geometry.py:373-375`, `tools/plimsoll/tank_geometry.py:398-399`). The exact-conservation regression covers both direct and adapter paths (`tools/plimsoll/tests/test_tank_geometry.py:221-233`).
- The implementation uses the required combined slope normal, reports the normal-plane offset rather than confusing it with the slope intercept, and tests translated cap vertices against both plane forms (`tools/plimsoll/tank_geometry.py:302`, `tools/plimsoll/tank_geometry.py:373`, `tools/plimsoll/tests/test_tank_geometry.py:164-177`).
- Near-full states solve the smaller complementary phase and explicitly reject phases below the declared limit (`tools/plimsoll/tank_geometry.py:344-352`); empty/full/zero-permeability and locked-centroid behavior are covered at `tools/plimsoll/tests/test_tank_geometry.py:94-111`.
- Tests include independent tilted and joint-slope analytic anchors plus midpoint-column refinement (`tools/plimsoll/tests/test_tank_geometry.py:40-55`, `tools/plimsoll/tests/test_tank_geometry.py:127-150`). The adapter comparison protects ordinary upright `damage.flood_tank_state` behavior (`tools/plimsoll/tests/test_tank_geometry.py:299-310`).
- Mutable `source` and `estimate` provenance is deep-copied (`tools/plimsoll/tank_geometry.py:318-319`), and the result explicitly declares the no-additional-FSC policy and signed tensor convention (`tools/plimsoll/tank_geometry.py:149`, `tools/plimsoll/tank_geometry.py:317`).

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- `tools/plimsoll/tank_geometry.py:177-178`, `tools/plimsoll/tank_geometry.py:211` — `_surface` computes permeability-scaled area and moments with ordinary multiplication, while `_ensure_public_geometry_is_finite` accepts zero as finite. The focused probe used `length=1`, `beam=height=1e-12`, `permeability=2e-299`, upright half fill: it is exactly at the documented `1e12` aspect-ratio limit with a 0.5 active-phase fraction and a representable `2e-323` capacity, yet it returned geometric `i_u_m4=8.333333333333333e-38` and `available_i_u_m4=0.0`. This violates the explicit requirement that positive derived areas/moments be representable or rejected and can falsely erase one free-surface inertia component. Use checked positive multiplication (or explicitly reject a tighter numerical domain) for every positive permeability-scaled public quantity, and add a regression that requires either a positive representable result or `ValueError`. The current non-finite regression only covers overflow/non-finite values (`tools/plimsoll/tests/test_tank_geometry.py:263-269`).

#### Minor (Nice to Have)

- `tools/plimsoll/tank_geometry.py:357`, `tools/plimsoll/tank_geometry.py:366-376` — for complementary near-full solves, `volume_tolerance_m3` reports only the small-phase root tolerance even though `geometric_volume = gross - phase_volume` adds full-volume subtraction roundoff. The controller's focused probe (`L=7.13`, `B=3.17`, `H=2.73`, `mu=0.4`, fill `1-1e-10`, heel `33`, trim `17`) returned `volume_residual_m3=-3.552713678800501e-15` with `volume_tolerance_m3=4.936296704727284e-21` and `converged=True`. Requested mass remains exact and the discrepancy is only about one ulp of the full volume, so the geometry is credible, but the published tolerance does not bound the published residual. Report a reconstruction-aware full-volume tolerance separately from the controlling small-phase root tolerance (or name the existing field as phase tolerance), and assert both semantics in the near-full regression at `tools/plimsoll/tests/test_tank_geometry.py:235-248`.

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The central geometry, conservation, metadata, provenance, analytical tests, and legacy adapter are well structured, and the reported focused 26-test run plus integrated 394/394 run are consistent with the diff. However, the demonstrated successful zero from numerical underflow directly violates a binding audit requirement, so the task should not pass until the derived-product guard and regression are added; the near-full tolerance field should also be made honest about reconstruction roundoff.
