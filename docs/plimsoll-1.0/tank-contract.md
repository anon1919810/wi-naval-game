# Inclined rectangular-tank liquid geometry contract

Date: 2026-09-22. This contract defines `tools.plimsoll.tank_geometry`
method version `rectangular-liquid-geometry-1`.

## Public interface

```python
liquid_state(tank, volume_m3, heel_deg=0, trim_deg=0) -> dict
from_legacy_flood_tank(tank, heel_deg=0, trim_deg=0) -> dict
```

The tank is an axis-aligned rectangular compartment with required finite fields
`length_m`, `beam_m`, `height_m`, `x_m`, `y_m`,
`keel_to_bottom_m`, and `permeability`. Dimensions are positive and
permeability is in `[0, 1]`. `free_surface` defaults to true and must be a
boolean. Booleans are never accepted as numbers.

`volume_m3` is conserved physical liquid volume. It must be between zero and
`capacity_m3 = permeability * gross_volume_m3`. On every successful call:

- `requested_volume_m3` and `volume_m3` equal the validated request exactly.
- `geometric_volume_m3` is the occupied volume found by geometric integration.
- `integrated_volume_m3 = permeability * geometric_volume_m3`.
- `volume_residual_m3 = integrated_volume_m3 - requested_volume_m3`.
- `phase_volume_residual_m3` is the signed root residual expressed as
  occupied-liquid volume; for a complementary void solve its sign is reversed.
- `phase_volume_tolerance_m3` is the tight tolerance that controls the
  smaller-phase root and therefore the free-surface geometry.
- `volume_reconstruction_roundoff_m3` is the observed difference between
  the reconstructed full-volume residual and the phase residual.
- `volume_tolerance_m3` is a reconstruction-aware bound:
  `phase_volume_tolerance_m3 + volume_reconstruction_roundoff_m3`, rounded
  upward when needed. It bounds the published `volume_residual_m3`.
- `fill_fraction = requested_volume_m3 / capacity_m3`.

The separately reported integration residual never changes mass. Empty liquid
has a null centroid. Full liquid has the compartment geometric centre. A
partial active liquid reports its integrated centroid in hull body
coordinates: x forward from midships, y starboard, and z above keel.

## Plane and free-surface convention

The public angles are slope angles, not sequential Euler rotations:

```text
p = tan(trim_deg)
q = tan(heel_deg)
n = (-p, -q, 1) / sqrt(1 + p² + q²)
n dot r = h
d = h / n_z
z = p*x + q*y + d
```

The method clips the rectangular box in local coordinates, integrates the
convex polyhedron, and then translates results to hull coordinates.
`plane_offset_local_m` is the unit-normal offset `h_local` in centred tank
coordinates. `plane_offset_m` is the hull-coordinate unit-normal offset
`h`, so every reported cap vertex satisfies
`dot(plane_normal, vertex) = plane_offset_m`. It is not the slope-form
intercept `d`; consumers obtain that intercept as
`plane_offset_m / plane_normal[2]`.

The free-surface basis is orthonormal and right-handed:
`basis_u cross basis_v = normal`. It reports geometric area moments about the
surface centroid:

```text
i_u_m4  = integral(v² dA)
i_v_m4  = integral(u² dA)
i_uv_m4 = integral(u*v dA)
```

`i_uv_m4` is a signed product of area. The corresponding inertia tensor uses
off-diagonal `-i_uv_m4`. Fields prefixed by `available_` include the uniform
permeability factor; unprefixed area and moments are geometric. A nonzero
permeability-scaled area or moment that falls below the positive floating-point
range is rejected. An exactly zero `i_uv_m4` or `available_i_uv_m4` remains
valid because symmetry can make the signed product of area genuinely zero.

`free_surface.applicability` and `free_surface.converged` describe the
surface calculation separately from the top-level volume-root
`converged`. Empty, full, and locked states have an inactive surface and
`free_surface.converged = null`.

## Assumptions and method limits

The model assumes a rectangular compartment, uniform permeability, and a
planar liquid surface horizontal in the world frame. Uniform permeability
scales available volume, free-surface area, and area moments. It does not
change fill depth or centroid for the same fill fraction.

The declared numerical domain is serialized in every result:

- `abs(heel_deg) < 89` and `abs(trim_deg) < 89`;
- partial active geometry has
  `max(length, beam, height) / min(length, beam, height) <= 1e12`;
- the smaller of the liquid and void phases is at least `1e-13` of capacity;
- gross volume, available capacity, requested adapter volume, centroids,
  plane offsets, polygons, areas, and moments must be finite and representable.

Gross volume and capacity use exponent-scaled multiplication, so a
mathematically representable product does not depend on dimension order.
Empty and full algebraic states do not use the partial-geometry aspect-ratio
limit, but their products and public outputs must still be representable.
Positive values below the floating-point range and values above it are
rejected. Unsupported or unresolved states raise `ValueError`; they never
return zero, infinity, a last iterate, or plausible free-surface inertias.
Error-bound fields are conservative bounds: if their exact positive product
would underflow, they round upward to the smallest representable positive
float instead of understating the bound.

For fills above one half, the solver integrates the smaller complementary void
phase and obtains the liquid centroid by central symmetry. This keeps a
near-full free surface controlled by the small phase rather than by a
tolerance scaled to the full tank.

## Locked-centroid proxy and FSC policy

`free_surface=False` selects an explicit `locked_centroid_proxy`. Its
upright centroid is

```text
z = keel_to_bottom_m + fill_fraction * height_m / 2
```

It emits `liquid.locked_centroid_proxy`. Closing a valve alone is not evidence
that real liquid has no free surface.

Every result declares
`fsc_policy = "centroid_geometry_no_additional_fsc"`. The inclined centroid
already captures the moving-liquid effect. A caller must not add an empirical
free-surface correction for the same liquid.

## Legacy adapter

`from_legacy_flood_tank` requires finite `flood_fraction` in `[0, 1]` and
positive finite `fluid_density_t_m3`. It obtains capacity through the same
checked path as `liquid_state`, sets requested volume to
`flood_fraction * capacity_m3`, and reports:

```text
added_displacement_t = fluid_density_t_m3 * requested_volume_m3
```

The adapter adds no FSC. For ordinary upright rectangular tanks its volume,
mass, x/y position, and occupied-height centroid agree with
`damage.flood_tank_state`. Input `source` and `estimate` provenance is
deep-copied into the result.
