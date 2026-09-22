# Coupled stability integration decisions

Design fixed before Task 4 implementation, 2026-09-22. These are requirements and independent derivations, not passed-test claims. Read `equilibrium-validation-design.md` and `tank-validation-design.md` first.

## Coordinates and constrained GZ

All calculations use the one plane `z = p*x + q*y + d`, with `p=tan(trim)` and `q=tan(heel)`. These are slope angles, not successive Euler rotations. Its normal is `n=(-p,-q,1)/s`, `s=sqrt(1+p*p+q*q)`. Define horizontal, orthonormal axes:

```
u = (1+q*q, -p*q, p) / (s*sqrt(1+q*q))
v = (0, 1, q) / sqrt(1+q*q)
```

Here `u` is the projected longitudinal axis, `v=n cross u`, and `u cross v=n`. With `delta=B-G`, a free equilibrium has `delta dot u=0`, `delta dot v=0` and the volume residual zero. This is equivalent to both moment equations in the earlier design.

For a GZ curve with prescribed `q`, allow longitudinal equilibrium by solving `delta dot u=0` together with displacement. The restoring arm is `GZ=delta dot v`. In particular,

```
GZ = (delta_y + q*delta_z) / sqrt(1+q*q)
longitudinal_condition = delta_x + p*delta_z
                         - p*q*(delta_y + q*delta_z)/(1+q*q)
```

The second term matters when a heeled state has a nonzero transverse restoring arm. Simply setting the unprojected legacy LCB to LCG is insufficient; setting only `delta_x+p*delta_z=0` in the constrained-heel problem also omits coupling. The condition follows independently from the derivative of the unit plane normal with respect to `p` at fixed `q`.

Validation must check the axis identities and an independently constructed inclined box state. Pure heel reduces to the conventional expression `(By-Gy)*cos(heel)+(Bz-Gz)*sin(heel)`. At free equilibrium GZ must be zero to the declared residual tolerance. A positive GM is local information, not a general safety certificate.

## Geometry adapter

Materialized canonical geometry uses `kind=offsets` and one explicit payload schema:

- Existing `plimsoll-offsets-1`: five-number rows with explicit `deck_z_m`; convert through `offsets` without any repository scan.
- `plimsoll-section-polygons-1`: `stations=[[x_m, [[y_m,z_m], ...]], ...]`, the existing `StationedHull` representation.

`keel_offset_m` is the geometric z coordinate of the declared keel. Thus a canonical KG maps to `Gz_geometry=KG+keel_offset_m`; reported buoyancy centres and waterline intercepts must also provide keel-relative values. A missing offset is not silently inferred from minimum polygon z. A translated geometry with its translated offset must produce the same physical answer.

Validate finite numbers, unique sorted station positions, finite section points and positive overall extent/volume before solving. Geometry source/estimate status and discretization remain visible in results. Enclosed section polygons define a finite sealed hull envelope, not unlimited reserve buoyancy. Preserve the old APIs where necessary and label their approximations honestly.

## Liquid load integration

Task 5's explicit liquid geometry is the only moving-liquid centroid calculation. Task 4 may accept `options.liquid_loads`, each with `{tank, volume_m3, fluid_density_t_m3}`. These are *additional* loads; the caller must not also count them in the base weight ledger. Require unique tank IDs, explicit positive density, and valid tank geometry. Keep base and added mass/moments separately in the result.

At every trial plane, recompute each liquid centroid using the same slope angles. Convert its keel-relative z into the geometry datum, combine with the base mass/moments, and then evaluate equilibrium. Use requested liquid volume as the conserved physical volume; report the geometry integration residual separately. Do not let small root/integration residuals create or destroy water mass. No additional FSC for these same liquids. Closing a connection alone does not lock a liquid centroid; `free_surface=False` is an explicit solid-proxy assumption and must retain its warning.

The resulting effective mass and CG, base loading identity, liquid snapshot and residuals must be returned so flooding and exports can audit them. Never mutate the loading state or options.

## Numerical and validity reporting

Solve within explicitly declared finite slope-angle bounds, by safeguarded iterations or a demonstrably equivalent bounded method. No unchecked last iterate may be marked converged. Return raw and scaled volume/moment residuals, iteration limits, bounds, method version and angle convention. The accepted residual threshold remains at most `1e-6` in the previously specified scales; a tighter internal root tolerance is allowed.

Convergence, completeness, model applicability, and historical validation are separate. Unsupported angle/geometry, impossible displacement, singular state or exhausted iterations must produce a visible failed result or structured exception, not a plausible last-good state.

Each GZ sample must expose its own equilibrium and validity. Distinguish sampled maximum from a solved peak; positive sampled endpoint from a bracketed zero; model-angle termination from a physical loss of stability. Compute sign-changing roots only when genuinely bracketed. A root beyond first supplied open-point immersion must not be labelled a valid intact stability limit. Missing openings leave downflooding unknown, with a diagnostic.

Open-point geometry is canonical x/y/z above keel and an explicit open/closed state. Report deck-edge immersion separately from supplied opening immersion: the sealed-envelope model can still be mathematically integrated, but immersion is not evidence of a real watertight deck or unrestricted validity. No invented opening locations.

Independent tests include exact box formula construction, prescribed-heel longitudinal coupling, shifted datums, mirrored transverse loading, liquid-induced small-angle slope (without duplicate FSC), overload/nonconvergence, genuine zero bracketing and cutoff labels, plus predeclared non-box resolution refinement. Existing legacy callers retain their contracts and receive no hidden Queen Mary constants.
