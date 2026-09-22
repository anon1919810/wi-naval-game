### Spec Compliance

- ✅ Spec compliant for the two round-0 findings. Positive permeability-scaled free-surface quantities now use checked multiplication and reject underflow, while an exactly zero signed product of area remains valid (`tools/plimsoll/tank_geometry.py:47-52`, `tools/plimsoll/tank_geometry.py:194-207`; `docs/plimsoll-1.0/tank-contract.md:76-80`).
- ✅ Complementary near-full solves now distinguish the controlling phase-root residual/tolerance from reconstruction roundoff, and the published total tolerance conservatively bounds the published total residual (`tools/plimsoll/tank_geometry.py:399-421`; `docs/plimsoll-1.0/tank-contract.md:25-35`).
- ⚠️ Integration status: the reported 28 focused tests passed after these fixes. The reported 394-test full suite predates this commit and is historical evidence only; a post-fix shared suite remains for the controller's later integration gate.

### Strengths

- `_checked_scaled_product` handles signed `i_uv_m4` without conflating a legitimate symmetry zero with underflow of a nonzero value (`tools/plimsoll/tank_geometry.py:47-52`, `tools/plimsoll/tank_geometry.py:202-207`).
- The underflow regression reproduces the exact supported-domain case from round 0 and requires an explicit domain failure (`tools/plimsoll/tests/test_tank_geometry.py:288-293`).
- The residual fix retains tight small-phase geometry semantics and adds a separately observable reconstruction term rather than loosening the phase solver (`tools/plimsoll/tank_geometry.py:402-421`).
- The near-full regression checks both the phase residual against its tight tolerance and the reconstructed total residual against its total bound (`tools/plimsoll/tests/test_tank_geometry.py:250-265`).

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None.

#### Minor (Nice to Have)

- None.

### Assessment

**Task quality:** Approved

**Reasoning:** The scoped changes directly fix both round-0 findings with clear public semantics and focused regressions, without weakening the geometry solver or masking numerical failure. Post-fix whole-suite integration is still pending and should be handled at the shared integration gate.
