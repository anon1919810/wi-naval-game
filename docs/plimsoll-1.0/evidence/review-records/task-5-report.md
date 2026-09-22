# Task 5 implementation report

Date: 2026-09-22
Base: `b9d5f34b9ee14b3205f571c39bfda90994d536dd`
Branch: `feature/plimsoll-1.0`

## Scope

Owned production artifacts:

- `tools/plimsoll/tank_geometry.py`
- `tools/plimsoll/tests/test_tank_geometry.py`
- `docs/plimsoll-1.0/tank-contract.md`

`tools/plimsoll/damage.py` remains unchanged. The compatibility entry point is
`tank_geometry.from_legacy_flood_tank`.

## RED evidence

The prepared baseline first ran its inherited analytical suite:

```text
python.exe -B -m unittest tools.plimsoll.tests.test_tank_geometry -v
Ran 18 tests in 0.063s
OK
```

Seven audit-focused behaviors were added before the fixes. The same command
then produced the expected RED result:

```text
Ran 25 tests in 0.126s
FAILED (failures=4, errors=5)
```

The output showed requested-volume drift (`18.799999999992774 != 18.8`),
factor-order underflow to zero and intermediate overflow, missing near-full
applicability metadata, accepted non-finite output, undeclared aspect-ratio
failure, and missing method/convention metadata. The ordinary upright legacy
comparison already passed and guards compatibility rather than an audit defect.

## Implementation and audit disposition

1. `volume_m3` and `requested_volume_m3` preserve the validated request exactly.
   Integrated water, occupied geometry, and `integrated - requested` residual
   are separate; adapter mass uses requested volume.
2. Partial fills solve the smaller liquid/void phase. High fills use central
   symmetry for centroid and section geometry. Complementary sections match
   through phase fraction `1e-12`; active phases below `1e-13` are explicitly
   outside the numerical domain.
3. One `frexp`/`ldexp` path computes gross volume, capacity, adapter volume,
   and added mass without factor-order overflow or underflow.
4. Every successful public geometric number is checked finite.
5. Partial active geometry declares maximum aspect ratio `1e12`; point
   deduplication scales from the smallest dimension.
6. Results serialize method version, slope convention, assumptions, domain,
   applicability, surface convergence, basis handedness, moment definitions,
   and tensor off-diagonal `-i_uv_m4`.
7. Mutable `source` and `estimate` provenance is deep-copied.
8. `free_surface=False` remains the warning-bearing locked-centroid proxy.
9. `plane_offset_m` is explicitly the unit-normal offset `h` in
   `n dot r = h`; the slope intercept is `d = h / n_z`. A translated
   joint-heel/trim regression evaluates both equations at every cap vertex.

## Focused verification

Interpreter: `C:/Users/杨睿/.workbuddy/binaries/python/versions/3.13.12/python.exe`
with `-B` and `PYTHONIOENCODING=utf-8`.

Final command, launched from outside the repository:

```powershell
& 'C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B `
  'C:\Users\杨睿\Documents\Codex\2026-09-17\shi\work\plimsoll-1.0\tools\plimsoll\tests\test_tank_geometry.py' -v
```

```text
Ran 26 tests in 0.129s
OK
```

A deterministic direct API sweep over 200 random ordinary-scale tanks and
joint heel/trim states checked exact conserved request, reported residual
tolerance, active/converged surface status, and finite centroids:

```text
RANDOM_GEOMETRY_SANITY cases=200 pass=200
```

## Mutation proof

An in-memory scratch load replaced exactly one expression:

```text
keel_to_bottom_m + fraction*height/2
    ->
keel_to_bottom_m + fraction*height
```

No production file was changed. Existing independent test
`test_locked_liquid_proxy_is_explicit` failed on the expected centroid:

```text
AssertionError: False is not true : 2.0 != 1
Ran 1 test in 0.001s
FAILED (failures=1)
MUTATION_KILLED locked-centroid one-half omission
```

The harness required exactly this one failure and exited zero.

## Self-review and declared limits

Coverage includes empty/full/zero permeability, upright/joint slopes, analytic
wedges, mirror and translation symmetry, permeability, midpoint quadrature
refinement, near-full complement symmetry, legacy compatibility, factor-order
extremes, explicit numerical rejection, finite public fields, and moment
conventions. Inputs remain unchanged.

A controller review caught that the first contract draft called the normal
offset `h` a slope intercept `d`. Before changing production metadata, the
new translated joint-slope test and existing metadata test were run against
the old string and failed exactly twice:

```text
Ran 26 tests in 0.142s
FAILED (failures=2)
```

After correcting the serialized `angle_convention` and contract, the final
26-test focused run above passed. Unit-normal offset arithmetic itself was
preserved.

Active phases below `1e-13` and partial aspect ratios above `1e12` are rejected
as applicability limits. Empty/full states can exceed the partial ratio when
their products and public outputs remain representable.

## Shared integration status

After Task 5 and disjoint Task 3 both reached the integration gate, the
controller ran exactly one combined full suite and polled its original session
to completion:

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B tools/plimsoll/run_all_tests.py
```

```text
Ran 394 tests in 116.530s
OK
PLIMSOLL_REGRESSION run=394 fail=0
exit=0
```

The suite ran with the final Task 5 files unchanged since the 26-test focused
gate. Pre-commit HEAD was
`c6eea8f37ff0d4a739a1da6c57d48ca7f8b36787`. The Task 5 commit is scoped to
the three owned production artifacts; disjoint Task 3 files remain unstaged.

Scoped commit:

```text
abf41b8 feat(plimsoll): add inclined tank liquid geometry
3 files changed, 848 insertions(+)
```

## Independent review round 1 fixes

Review at fix base
`80fb8d88e63ec1c64831087a85ff263d273ee461` requested two corrections.

First, a supported active tank with `L=1`, `B=H=1e-12`,
`permeability=2e-299`, and half fill returned a positive geometric
`i_u_m4` whose permeability-scaled value silently underflowed to zero.
The RED regression failed because no `ValueError` was raised. Active
available area and moments now use checked multiplication. Nonzero
underflow/overflow rejects the state; a truly zero signed `i_uv_m4` remains
valid. The focused reproduction now raises:

```text
ValueError free_surface.available_i_u_m4 is below the positive numerical range
```

Second, the complementary reconstruction could have a full-volume residual
larger than its small-phase root tolerance by one full-volume ulp. The RED
regression errored on the missing phase fields. Results now distinguish:

- `phase_volume_residual_m3` and `phase_volume_tolerance_m3`, which retain
  the tight small-phase root semantics;
- `volume_reconstruction_roundoff_m3`, the observed reconstruction delta;
- `volume_tolerance_m3`, the upward-rounded total bound on the published
  full-volume residual.

For the reviewer fixture, the final values are:

```text
phase residual       -3.3024358775567078e-21
phase tolerance       4.936296704727284e-21
reconstruction delta  3.5527103763646233e-15
full residual        -3.552713678800501e-15
full tolerance        3.552715312661329e-15
```

Post-fix focused command:

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\杨睿\.workbuddy\binaries\python\versions\3.13.12\python.exe' -B tools/plimsoll/tests/test_tank_geometry.py -v
```

```text
Ran 28 tests in 0.164s
OK
```

The earlier 394-test shared run predates these review fixes and is retained
above only as historical integration evidence. Per controller coordination,
no post-fix full suite has run yet because Task 7 is editing disjoint files.

Scoped review-fix commit:

```text
080fbda fix(plimsoll): guard tank geometry numerical bounds
3 files changed, 91 insertions(+), 7 deletions(-)
```
