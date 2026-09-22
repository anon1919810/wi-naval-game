# Explicit geometry analysis helpers

`geometry_analysis.py` implements `geometry-analysis-1`. These helpers do not
solve a new equilibrium, discover files, read a ship repository, alter project
input or change ledger KG. The coordinator remains responsible for the immutable
project/loading snapshot and request fingerprint. See the predeclared
[analytic acceptance](geometry-analysis-validation.md) and
[loaded solver contract](stability-api.md).

## Public geometry preparation

```python
stability.prepare_geometry(hull, options=None)
```

The return tuple is `(stationed_hull, vertices, axis_extents, metadata)`.
`vertices` contains `[x,y,z]` coordinates as tuples; `axis_extents` contains
positive x/y/z lengths. Metadata includes the explicit keel datum, copied source
and estimate, bounds, station/vertex counts, quadrature and sealed capacity.
All returned data belongs to the caller; editing it does not alter input.
Canonical `kind="offsets"` geometry owns its `keel_offset_m`; a stationed object
requires `options.keel_offset_m`. Malformed options or geometry raise `ValueError`.
This public wrapper calls the existing solver adapter unchanged.

`geometry.waterline_intervals(poly, q, d)` exposes the existing intersection
rules: merged occupied y intervals on `z=q*y+d`, preserving concave gaps and
coincident edges. Its input polygon must already be validated. It does not
infer a one-sided derivative at contact. The legacy
`_line_chord_halfwidth(poly, q, d, n=200)` signature and None-for-no-intersection
behavior remain; it now sums the same public intervals.

## Parameterized L0 study

```python
parameterized_hydrostatics(hull) -> dict
```

Required inputs are `lwl_m`, `beam_m`, `block_coeff`, and `draught_normal_m`
when that key is present, otherwise `draught_m`. A present null normal draft
does not silently fall back to a different draft. Missing required values give
`status="unavailable"`, null values and field diagnostics. Booleans/nonfinite
numeric input is rejected before the legacy float coercions. Positive dimensions,
`0.2 <= Cb <= Cwp <= 1` and `Cwp >= 0.3` bound this model. An explicitly supplied
deck/depth must exceed draft; infeasible shape/deck conditions give `model_limit`.

Actual arithmetic and its formula/source trace come from `hydrostatics.compute`.
The scenario is `parameterized_design_waterline_not_loaded_equilibrium`. It
retains the one-parameter upright waterplane shape, Morrish KB and small-angle
roll assumptions; it does not prove a watertight geometry or a loaded attitude.
The original `inputs` remain unchanged, including unknown source/estimate values.
An absent/null Cwp explicitly assumes 0.8 and an absent/null roll gyration
coefficient assumes 0.38; seawater density is the legacy 1.025 t/m³. Every used
default is listed with its value, source and estimated status, plus diagnostics.
Unknown inputs are still null in `inputs`. `effective_inputs` records the
actual arguments passed to the calculator.

Unknown KG yields null GM/roll period; explicit KG=0 is a known value.
`reference_displacement` is an independent comparison, never substituted for
calculated mass. An explicit zero reference is retained and has a null percentage
deviation with a diagnostic; positive references retain legacy discrepancy
warnings verbatim. Legacy warning strings become structured diagnostics without
deduplication. Raw source fields and direct-input estimate flags remain available;
derived model quantities remain estimates even when input dimensions are measured.

## Explicit reference-hull materialization

```python
materialize_reference_hull(
    parameters, *, keel_offset_m, source, estimate,
    n_stations=81, n_section=48,
) -> dict
```

All six parameters must be supplied and finite: `lwl_m`, `beam_m`, `draught_m`,
`block_coeff`, `waterplane_coeff`, `depth_m`. Here **depth_m explicitly means
the constant closed deck height above keel**. The adapter passes it as both
the legacy generator's depth and deck arguments; it never chooses `T*1.6`.
All are positive, deck is above draft, and the generator requires
`0.2 <= Cb < Cwp <= 1`, `Cwp >= 0.3`. The strict inequality excludes the
singular vertical-side limit of this particular power-law generator; explicit
box polygon input remains valid. Source is a nonempty string/object and input
estimate is a boolean. Stations use cosine spacing with integer count 3–401;
section subdivisions are integers 8–128.

The returned canonical `offsets` geometry contains `plimsoll-section-polygons-1`,
shifted into the declared geometry keel datum and checked by `prepare_geometry`.
It is always estimated generated geometry. Provenance retains the original
parameters, input source/estimate, generator, method version, resolution,
assumptions and SHA-256 of the serialized offsets payload (sorted keys, compact
UTF-8 JSON, no nonfinite values). It can be passed to the existing loaded solver.
This function is explicit materialization of chosen parameters, not external
reference-file import. Source-preserving import of selected external content
remains a coordinator/persistence integration task.

## Selected-plane measures

```python
measures_at_plane(hull, plane, *, rho_t_m3=1.025, geometry_options=None) -> dict
```

`plane` supplies finite `p`, `q`, `waterline_d_m` in the **geometry datum**:
`z=p*x+q*y+d`. An existing successful solver result can be passed directly.
A supplied failed equilibrium is rejected. These are waterplane slopes, not
Euler rotations. Density must be positive and is serialized in the result.

Every section clips at `d+p*x` with slope q. Volume and buoyancy centres use
the same validated `StationedHull.integrate` clipping and trapezoidal moments
as the loaded solver. `kb_m` is the body-axis z-coordinate of buoyancy above
the declared keel, not world vertical height in an inclined state. Returned
`sections` retain x, local intercept and submerged area.

Waterplane area includes the factor `s=sqrt(1+p²+q²)`; its projected xy area
is also returned. Centroidal moments use orthonormal in-plane coordinates
`u=s/t*x`, `v=p*q/t*x+t*y`, where `t=sqrt(1+q²)` and the intercept is removed
before projection. `it_m4=integral((v-vc)² dA)`,
`il_m4=integral((u-uc)² dA)`, and the product moment is also reported.
Interval y moments are exact for each polygon intersection. Across stations,
the interval width/first/second moment scalars are interpolated linearly;
their x and x² weighted integrals are analytical segment integrals. This avoids
the incorrect trapezoid-of-x² answer even for a three-station box, but retains
station discretization error for curved hulls.

Form coefficients use explicitly named body-axis reference quantities:

- Length: x support of the piecewise-linear station waterline chords, including
  zero-width endpoints adjacent to a positive chord. This is a station-support
  approximation, not a refined waterline endpoint search.
- Beam: total extreme y span of occupied waterline intervals; gaps remain excluded
  from area/moments.
- Draft: the midships waterline intercept above the declared keel, `d-keel`.
- Midships area: linearly interpolated submerged area at x=0. `Cm=A0/(B*T)`,
  `Cp=V/(L*A0)`, `Cb=V/(L*B*T)`, `Cwp=Awp_xy/(L*B)`.

At inclined attitudes these numbers are explicitly
`inclined_body_axis_ratios_not_upright_empirical_inputs`; they are not conventional
upright resistance coefficients and need not satisfy their usual bounds.
Unavailable reference dimensions produce null coefficients with a diagnostic.
Only an exactly upright, partially immersed, non-contact plane exposes BM_T,
BM_L, KM_T and TPC. Their geometric values do not establish loaded stability.
Coincident boundary edges keep their geometric area/moments but suppress these
derivative-based quantities and empirical eligibility. Empty/full contact and
out-of-envelope planes carry `model_limit` and explicit envelope states; known
clipped volume remains distinguishable from missing quantities.

`upright_empirical_eligible` is only this geometry-side prerequisite. It does
not certify any resistance method's speed, hull-form or other validity ranges.
Slight loaded trim still reports false here. A later resistance adapter must
explicitly declare and trace any permitted small-trim approximation.

`wetted_surface` is a **longitudinal station-girth integral**: integrate lengths
of the submerged portions of original polygon edges along x. It excludes the
artificial waterline-closing segment and both end faces, and ignores longitudinal
surface slopes. It is always marked estimated. At box draft 2 m it reports
200 m², not the complete closed-shell 224 m². More stations do not remove this
method's missing longitudinal slope/end-face terms.

## Requested Bonjean and hydrostatic grids

```python
bonjean_table(hull, waterlines_above_keel_m, *, geometry_options=None)
hydrostatic_table(hull, waterlines_above_keel_m, *, rho_t_m3=1.025,
                 geometry_options=None)
```

Both require 1–201 explicit, finite, strictly increasing levels. They generate
no implicit default grid. Each row retains the requested keel-relative height
and the geometry-datum ordinate. Geometry is prepared once for the table.

Bonjean reuses the existing `StationedHull.bonjean_curve` and returns section
area in m² and x positions at every requested level. Exact lower/upper contact
can report a known zero/full section area with `model_limit`; outside the hull's
global height support, area is null with a diagnostic. A Bonjean table is not a
loading-dependent GZ curve.

Hydrostatic rows evaluate upright p=q=0 reference planes with explicit density,
preserving `model_limit` rows. The scenario is
`constrained_upright_reference_waterlines`, with `loading_equilibrium_claim=false`.
No row claims to balance the selected loading mass.

## Supplied deck geometry

```python
deck_clearance(deck, plane, *, keel_offset_m)
deck_immersion_events(deck, samples, *, keel_offset_m)
```

`deck` is null (unknown) or an object containing explicit nonempty `source`,
boolean `estimate`, and 1–10000 `points`. Each point has a unique nonempty `id`
and finite `x_m`, `y_m`, `z_m`; z is **above keel**. This phase defines a helper
input, not a new canonical project schema field. A caller with a deck profile
must explicitly supply its chosen sampled points and provenance.

The signed normal clearance is
`(z+keel-p*x-q*y-d)/sqrt(1+p²+q²)`. Positive is dry, negative immersed and exact
zero is a sampled contact. The original deck definition, point clearances,
limiting point, plane and datum accompany the result. No section vertex is
automatically promoted to a physical deck edge.

Event samples use the existing curve shape `{angle_deg, equilibrium}` with
1–201 strictly increasing angles. A failed equilibrium yields an unavailable row
and breaks any sign bracket. Reports distinguish exact sampled contact, already
immersed first sample, and `sampled_sign_bracket` (direction and both endpoint
point IDs). A bracket has a null event angle; there is no interpolation or new
equilibrium solve masquerading as a refined event. The last dry sample has
`dry_at_last_sample_event_unknown`. `safe_angle_deg` is always null.
Deck contact is explicitly separate from open-point downflooding and does not
establish watertightness or maximum safe angle.

## Status and verification boundaries

Calculation envelopes separate completion of the helper's required inputs,
model applicability and historical validation. Non-iterative geometry/L0 outputs
have `numerical_convergence=null`; they do not borrow the loaded solver's
convergence. Optional unknown quantities can remain null in a completed helper
with their diagnostic. Historical validation is always null. Malformed API
requests raise `ValueError`; unsupported physical states retain explicit
`unavailable` or `model_limit` results as described above. Public numerical
payloads are checked for JSON serializability with nonfinite numbers disabled.

The tests use the predeclared exact algebraic tolerance 1e-10 for box/triangle
quantities and datum translation. The reference-hull 41/48 to 81/96 refinement
checks stay below 1%, and the materialized output is also passed through the
real loaded solver with scaled residual below 1e-6. These are generic numerical
fixtures, not historical ship validation.
