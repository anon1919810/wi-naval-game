# Loaded equilibrium and sampled stability curves

`tools.plimsoll.stability` implements method `loaded-projected-equilibrium-1`.
It uses the coordinate/force contract in `coupled-stability-contract.md`.

```python
solve_loaded_equilibrium(hull, loading_state, options=None) -> dict
stability_curve(hull, state, angles_deg, openings=None, options=None) -> dict
```

The optional fifth curve argument preserves existing four-argument calls. The
curve passes the same density, explicit datum, bounds and moving liquid loads
to every sample, stiffness evaluation, zero and opening-immersion solve. Each
sample replaces only `heel_deg` with its requested angle.

## Ready geometry and loading

The adapter copies and validates materialized `kind="offsets"` geometry with
an explicit finite `keel_offset_m`. Its payload schema must be
`plimsoll-section-polygons-1` or `plimsoll-offsets-1`. The latter needs explicit
positive `deck_z_m`, five or more five-number rows, nonnegative halfbreadths
and negative keel ordinates around the importer's fixed z=0 anchor. Both
representations require strictly increasing station x positions. Polygon
sections must be simple; holes, multiple contours and touching/self-crossing
boundaries are unsupported. Repeated closure/consecutive points are harmless.
Degenerate point/line sections are allowed at the two ends; flat, full-area
ends are preserved. Derived extents and sealed-envelope capacity must be
finite and positive.

An existing object with `.stations` is also accepted after copying and the same
validation, independently of Python import identity. It requires
`options.keel_offset_m`; no keel inference or repository file discovery occurs.

`kind="parameters"` and unresolved `offsets_reference` return not-ready
diagnostics. This does not remove L0 analytical calculations. A caller may
separately request a named reference-hull materialization with complete
dimensions/coefficients, explicit datum and estimated provenance, then pass
those materialized polygons here. The solver never invents offsets from a
partial parameter record. Editable project draft validation remains unchanged.

Base loading requires `complete_mass`, `complete_cg`, positive finite
`values.total_mass_t`, all three CG coordinates, and no blocking diagnostics.
The reference displacement in coverage is never used as physical mass.
Input identities, diagnostics, provenance, coverage and uncertainty are copied
to `loading`; geometry source/estimate and discretization accompany the result.

## Options and result semantics

| Option | Default / meaning |
| --- | --- |
| `rho_t_m3` | 1.025 t/m³; positive finite ambient water density, serialized in the result |
| `heel_deg` | Absent means free heel; present fixes heel while draft/trim remain free |
| `heel_bounds_deg` | `[-85, 85]`; ordered limits strictly inside (-89, 89) |
| `trim_bounds_deg` | `[-45, 45]`; ordered limits strictly inside (-89, 89) |
| `max_iterations` | 50 per attempt, integer in [1, 1000] |
| `initial` | Optional `trim_deg` and `heel_deg` hints within the declared bounds; fixed heel takes precedence |
| `keel_offset_m` | Required for legacy stationed objects; canonical records carry their own datum |
| `liquid_loads` | Additional explicit liquids as defined in the coupled/tank contracts |

All numbers reject booleans and nonfinite values. Each liquid has a nonempty
unique tank ID, absent from the base effective-item IDs, requested volume and
positive density. Callers remain responsible for excluding the same physical
liquid under any different ledger identity. The solver recomputes its centroid
at every trial attitude, conserves requested mass exactly, and adds no FSC.
`free_surface=False` retains the tank method's solid-proxy warning. Liquid
snapshots keep geometry residuals separate from conserved mass.

The initial draft is bracketed using all vertex supports `z-p*x-q*y`; a single
48-step intercept bisection seeds simultaneous draft/trim/heel Newton updates.
Central numerical derivatives, a bounded reduction line search and a smaller
difference stencil at contact kinks safeguard the solve. An unsuccessful
explicit initial attitude may be retried once from neutral angles, with the
same physical inputs, bounds and tolerances and a recorded diagnostic.
Singular Jacobians, saturated capacity, overload, exhausted iteration budgets
and nonreducing residuals fail explicitly. This is a local solver; it does not
prove uniqueness across disconnected equilibrium branches or select a globally
stable branch. Finite-difference perturbations are derivative evaluations;
accepted trial attitudes stay within the declared bounds.
Targets within 1e-12 of full capacity as a fraction of that capacity are
conservatively classified as saturated/unresolved rather than assigned a
unique free-surface draft.

The internal stopping target is 1e-10 scaled residual. The returned state is
reevaluated and must satisfy the declared 1e-6 maximum: volume/target volume,
longitudinal arm/length, and transverse arm/beam. Prescribed heel constrains
only volume and the projected longitudinal arm; the transverse arm is the
reported GZ. `residuals.raw` contains m³ for volume and metres for moments.

Successful results contain slope angles, p/q, intercepts in both geometry and
keel datums, buoyancy centres, density, GZ, orthonormal axes, raw/scaled
residuals, solver limits/iterations/evaluations, geometry metadata, base/added/
total mass and moments, effective CG, and liquid snapshots. All moments and
`*_cg_m`/`cg_m` coordinates use the geometry datum; `cg_keel_m` and
`buoyancy_centre_keel_m` use the declared keel. `input_fingerprint` remains the
base loading fingerprint, not a hash of added options; the analysis coordinator
must include effective options in its calculation/cache fingerprint.

`converged`, `validity.complete`, `model_applicable`, `historical_validated`
and `safe` are separate. Historical validation and overall safety remain null.
Failure results contain structured blocking diagnostics and no reusable GZ or
last-iterate equilibrium. Invalid curve request structures (angle ordering or
opening fields) raise `ValueError`; unsupported geometry returns failed rows.

## Curves, openings and limits

Curve angles are strictly increasing. Each row contains its own equilibrium
and validity, including explicit failures rather than a previous good state.
`initial_stiffness_m` is the centred finite-difference slope dGZ/dheel in radians
at zero heel, with longitudinal equilibrium solved at ±0.01°. It includes
moving liquid geometry. For asymmetric or already listed loading it is this
defined derivative, not automatically an upright GM. It is null if either
near-zero attitude cannot be solved. A positive derivative never implies safety.

Openings require unique `id`, finite `x_m`, `y_m`, `z_m` above keel and explicit
boolean `open`. Closed openings do not contribute. Normal clearances use the
same waterplane normal as buoyancy. An observed positive-to-negative clearance
bracket is refined; an already immersed first sample remains a sampled cutoff.
`openings=None` means unknown and produces a diagnostic; `[]` explicitly
declares no open points supplied. Generic section vertices do not identify real
deck edges, so `deck_edge_immersion` remains null with a separate unknown status.

`zero_crossings` contains refined actual sign brackets and their crossing
direction. A bracket after detected downflooding is not intact-valid. The
reported `avs_deg` is the first detected positive-to-negative bracketed root
that is intact-valid relative to the supplied opening definitions; missing
opening information leaves it null. Sparse sampling can miss intermediate
crossings/immersion and does not establish a global first event. Users must
refine the angle sampling for their geometry and intended range.

The maximum is labelled `sampled_maximum`, not an optimized peak. Endpoints
distinguish positive/nonpositive samples, failed samples and requested angles
outside model limits. A positive final sample is never relabelled AVS. The
sealed-envelope integration is not proof of a physical watertight deck.

## Shared kernel and compatibility

`geometry._line_chord_halfwidth` retains its historical name but now computes
half the total occupied y measure, including disjoint intervals and coincident
boundary edges. `awp` is geometric inclined-plane intersection area; at exact
edge contact it is not a one-sided volume derivative. The new solver uses
numerical derivatives and never substitutes symmetric-upright KM.

Legacy scalar/list/dict signatures remain unchanged. The old trim result adds
`equilibrium_model="legacy_lcb_only_not_projected_moment_equilibrium"`; its
target cannot represent full loaded moment equilibrium without KG/TCG.
No legacy damage `stable` flag is reused as the new solver's safety result.

## Independent evidence

`tests/test_stability_loading.py` uses unchanged independent box and ellipsoid
oracle scripts and direct analytic shallow-prism/tank stiffness expressions.
At ellipsoid (161 stations, 128 section vertices), an observed run had free
scaled residual at most 4.51e-14 and prescribed-heel residual 3.08e-16. The final
(81,64)→(161,128) change was at most 0.13633% across the predeclared metrics,
below 1%; station and section refinement are also checked independently.
These are numerical fixture results, not historical validation of any ship.
