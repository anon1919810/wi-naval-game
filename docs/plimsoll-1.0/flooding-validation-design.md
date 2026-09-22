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

## Analytic floating-body feedback anchor

Before promoting the Task6 prototype, add a fully coupled symmetric case whose
continuous solution is independent of the equilibrium implementation. Use a
20×10×6 m rectangular ship with keel z=0 and centred base loading of 401.8 t at
KG=1 m. Sea and tank water both have density 1.025 t/m³. A centred 4×2×4 m
rectangular tank, bottom z=0 and permeability1, initially contains 8 m³. That
water is additional to the base mass, not already counted in its ledger. The
initial total displacement is 410 t and draft is exactly 2 m. Use the same
A=0.1 m², Cd=0.6, g=9.80665 m/s² and t=5 s as above; the sea connection is at
(0,0,0.1) m and stays submerged on both sides. Hull and loading symmetry keep
heel and trim zero; their numerical solutions must still be checked.

Let Awp=200 m², S=8 m², V0=8 m³ and K=Cd*A*sqrt(2g). As the hull sinks,

```
d(V) = M_base/(rho*Awp) + V/Awp
H(V) = d(V) - V/S
a = 1/S - 1/Awp = 0.12 per m²
H0 = 1 m
dH/dt = -a*K*sqrt(H)
V(t)-V0 = [H0 - (sqrt(H0)-a*K*t/2)^2] / a
```

This gives inflow 1.2756512554179793 m³ and draft 2.00637825627709 m at 5 s.
The independent oracle emits all inputs and answers under `coupled_heave`;
it imports no production code. This is a continuously rebalanced floating
body, unlike the fixed-sea-relative-to-hull fixture. It detects a stale sea
plane/draft or omitted added-water mass.

Use the same 0.5/0.25/0.125 s refinement. Inflow error must decrease and the
finest result must be within 1% of the analytic inflow; draft-change error uses
1% of the analytic *draft increase*, not 1% of total draft. Require absolute
heel and trim <=1e-6 degrees and the existing scaled equilibrium residual
limit at every accepted state. The separate volume/mass conservation criterion
remains 1e-10 of its declared scale. No capacity, contact or downflooding
boundary occurs in this fixture. Passing it verifies this idealized feedback
law, not historical flooding behaviour.

## Coupled-body and limit tests

An independent instantaneous inclined-head anchor uses adjacent 10×1×3m tanks
centred at (x,y)=(0,−0.5) and (0,+0.5), both bottom z=0, permeability1 and
15m³ of water. Their common aperture is (0,0,0.25), with the same A,Cd,g above.
Choose trim slope p=0.1 and heel slope q=0.2; neither liquid plane hits a top
or bottom edge. The slope intercepts are d_port=1.5+0.5q and
d_starboard=1.5−0.5q. With s=√(1+p²+q²), the world-vertical pressure heads are
1.35/s and 1.15/s, and initial flow from port to starboard is
Cd A √(2g×0.2/s). Equal body-frame fill heights must therefore produce a
nonzero transfer. This anchor catches omission of horizontal position,
inclination normalization or the shared datum; use algebraic tolerance1e−10.
Its answer is emitted by the independent oracle script alongside the upright
time integrals. It specifies a frozen instant, not a ship equilibrium.

- Empty/full tanks, explicit zero permeability, zero-area or closed connections, no apertures, equal head and head reversal.
- Multiple internal edges must remain conservative when one source has limited water or a receiver approaches capacity.
- At every accepted coupled step recompute moving-liquid centres and the full force/moment equilibrium, carrying all convergence/geometry diagnostics. The step must not be labelled successful if the equilibrium solve fails.
- Mirror tank y coordinates and opening y coordinates: volume history stays equal and heel changes sign, within the predeclared numerical tolerances.
- Closing a valve removes flow on that edge; it does not suppress an existing free surface.
- Distinguish scheduled completion, canceled job, equilibrium failure, downflooding event and capacity/model limit. No timeline silently truncates and reports completion.
- Known deck openings may trigger events; absent openings keep downflooding unknown. A positive GM alone never certifies survival.
- Selected nontrivial coupled scenario: compare endpoint volumes, draft and angles for dt and dt/2; report residuals and require differences below1% away from zero, with a predeclared absolute near-zero angle bound. Retain identical scenario input/fingerprint for deterministic replay.

All scenario geometry, Cd and initial water data carry source/estimate metadata. Queen Mary scenario tanks are layout proxies until actual subdivision and openings are documented.

## Source basis and independent reproducible answers

The [USBR Water Measurement Manual, chapter9 section5](https://www.usbr.gov/tsc/techreferences/mands/wmm/chap09_05.html) describes submerged-orifice discharge from differential head and a discharge coefficient incorporating contraction/loss effects. Its experimental coefficient and low-head restriction concern a specific calibrated irrigation structure; neither is a universal ship-damage constant. Plimsoll requires an explicit, sourced or estimated Cd.

The [USACE HEC-HMS outlet reference](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/reservoir-modeling/reservoir-modeling-concepts-and-equations/outlets) likewise uses an opening-centre elevation, area and entered coefficient, while warning that insufficiently submerged openings need a different flow regime. This supports the point-orifice approximation and its applicability warning; it does not validate a moving ship, partial aperture, trapped air or blast hole.

The analytic two-tank and sea-fill answers above are independently executable in [flooding_oracles.py](evidence/flooding_oracles.py), which imports no Plimsoll code. With the predeclared5s fixture, the paired transfer is1.24034731541798m³ (total retained30m³), and the fixed-sea inflow is1.8348043474001763m³. These are exact solutions of the chosen constant-Cd, fixed-attitude ODE. Keep the0.5/0.25/0.125s refinement and1% criterion unchanged; matching this ODE is not empirical flooding validation. Source/model uncertainty near zero differential head remains distinct from numerical convergence.
