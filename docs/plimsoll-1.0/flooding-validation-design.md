# Quasi-static flooding: independent validation design

Written before Task 6 implementation, 2026-09-22. This specifies a vented-liquid, added-mass model. It does not model compressed air, internal pressure networks, waves, sloshing, progressive structural failure or projectile holes dynamically changing shape.

## Flow law and conservation

For an aperture with explicitly supplied area A and discharge coefficient Cd, use positive pressure heads at its centre. Let `hi=max(surface_i_world_height-aperture_world_height,0)` and similarly `hj`. In the supported small-aperture approximation:

```
Q_i_to_j = Cd*A*sign(hi-hj)*sqrt(2*g*abs(hi-hj))
```

An empty/dry side has zero hydrostatic head. A closed connection has exactly zero flow. Both dry or equal-head sides have zero flow. All lengths are metres and Q is m3/s; density is explicit and must be identical across connected water nodes in this incompressible single-fluid model. Do not quietly mix fresh water and seawater in this version.

World vertical head is the signed distance along the unit waterplane normal, not a raw body-z difference at nonzero inclination. Sea surface and tank liquid planes must share the same datum/normal. For a tank plane `n dot r=c`, its head at aperture r is `max(c-n dot r,0)`.

An internal edge transfers one identical volume from source to destination. Sea exchange alone changes total onboard water. For each accepted step:

```
sum(V_after)-sum(V_before) = sum(signed_sea_exchange)
added_water_mass = density*sum(V)
```

Use the conserved requested volumes for the mass ledger; tank clipping residuals are separately reported and cannot inject water mass. No lost-buoyancy subtraction is combined with this added-mass treatment.

Never clamp each node independently after transferring: this silently loses water. Bound/shorten a step before applying a conservative edge transfer, and report actual accepted duration and transfer. A full compartment can no longer accept water in the vented free-surface model without overflow/pressure information. If continued predicted inflow would require that unsupported regime, stop with a visible capacity/model-limit reason unless an explicitly modeled overflow connection resolves it. Do not invent a pressure or silently discard excess water.

## Analytic frozen-attitude anchors

The flow kernel needs a fixed-attitude validation mode independent of the full floating-body solve. These analytical fixtures are not a substitute for integration tests with repeated equilibrium.

For two identical upright tanks with horizontal area S, a bottom connection, and both sides continuously submerged, define the positive height difference H=h1-h2. Before equalization:

```
sqrt(H(t)) = sqrt(H0) - Cd*A*sqrt(2*g)*t/S
H(t) = square(max(the preceding expression,0))
transferred_volume(t) = S*(H0-H(t))/2
```

Use S=10 m2, tank height=5 m, initial heights2 m and1 m, A=0.1 m2, Cd=0.6 and g=9.80665 m/s2. Check t=5 s. Both initial and final heads remain submerged and no capacity boundary is near. Total30 m3 is exact at every accepted step. The reference comes from integrating `dH/dt=-2*Cd*A*sqrt(2*g*H)/S`, not production stepping.

For one upright tank filled from a sea level held at hs, with constant horizontal area S and initial height h0:

```
sqrt(hs-h(t)) = sqrt(hs-h0) - Cd*A*sqrt(2*g)*t/(2*S)
```

Use the same S,A,Cd,g, hs=3 m, h0=1 m, check t=5 s. Sea exchange equals the tank-volume increase. Reverse the initial ordering to test outflow.

Predeclare timestep sequence0.5,0.25,0.125 s. Errors in transferred volume must decrease under refinement and the finest result must be within1% of the analytic transfer. Conservation is a separate arithmetic criterion: `abs(error)<=1e-10*max(1,total_volume,absolute_sea_exchange)` per run. Do not weaken conservation because the ODE is approximate.

## Coupled-body and limit tests

- Empty/full tanks, explicit zero permeability, zero-area or closed connections, no apertures, equal head and head reversal.
- Multiple internal edges must remain conservative when one source has limited water or a receiver approaches capacity.
- At every accepted coupled step recompute moving-liquid centres and the full force/moment equilibrium, carrying all convergence/geometry diagnostics. The step must not be labelled successful if the equilibrium solve fails.
- Mirror tank y coordinates and opening y coordinates: volume history stays equal and heel changes sign, within the predeclared numerical tolerances.
- Closing a valve removes flow on that edge; it does not suppress an existing free surface.
- Distinguish scheduled completion, canceled job, equilibrium failure, downflooding event and capacity/model limit. No timeline silently truncates and reports completion.
- Known deck openings may trigger events; absent openings keep downflooding unknown. A positive GM alone never certifies survival.
- Selected nontrivial coupled scenario: compare endpoint volumes, draft and angles for dt and dt/2; report residuals and require differences below1% away from zero, with a predeclared absolute near-zero angle bound. Retain identical scenario input/fingerprint for deterministic replay.

All scenario geometry, Cd and initial water data carry source/estimate metadata. Queen Mary scenario tanks are layout proxies until actual subdivision and openings are documented.
