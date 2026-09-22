# Geometry analysis acceptance before Task 8 integration

Declared 2026-09-22 before implementing the unified geometry-analysis adapter.
These are analytic requirements, not passed production results. They complement
the coupled-equilibrium, tank and resistance validation designs.

## Upright rectangular prism and Bonjean curves

Use a prismatic hull with length 20 m, beam 6 m, closed envelope height 5 m,
x in [-10, 10], y in [-3, 3], keel z=0. Retain finite end sections. For a
requested upright waterline h strictly between 0 and 5 m:

- Each station's submerged section area A(h)=6h m². A Bonjean table must retain
  station position, waterline ordinate, keel datum and the section-area unit.
- Displacement volume V(h)=120h m³; longitudinal/transverse buoyancy centres
  are zero; KB=h/2 above keel.
- Horizontal waterplane area is 120 m², transverse second moment 360 m⁴,
  and longitudinal second moment 4000 m⁴.
- BM_T=3/h m, BM_L=(100/3)/h m. At h=2 m: V=240 m³, KB=1 m,
  BM_T=1.5 m and KM_T=2.5 m. At rho=1.025 t/m³ displacement is 246 t;
  TPC is 1.23 t/cm. At h=4 m displacement is 492 t.
- Waterline length 20 m, beam 6 m, Cb=Cm=Cp=Cwp=1. These remain valid for a
  physical blunt-ended box; a generic loader must not automatically call every
  finite end section a missing bow or stern.

Test requested waterlines 1, 2 and 4 m. Use the global algebraic relative and
absolute tolerances 1e-10 for this exact straight-sided integration. Full/empty
envelope contact needs its own explicit status rather than finite-difference
GM claims. Outside supported draft/geometry rows must preserve unavailable or
out-of-envelope state. A hydrostatic sweep is a constrained upright reference
study and does not assert that each row satisfies the chosen loading's mass.

Translate all hull ordinates and its declared geometry keel by +7 m; the same
keel-relative requests must preserve all physical outputs. Geometry-datum
waterline ordinates change by +7 m. This must not alter the project ledger KG.

## Independent triangular section anchor

Use a longitudinal prism of length 20 m whose submerged section is the triangle
(y,z)=(-3,5),(3,5),(0,0). For 0<h<5, top width is 6h/5 and section area
A(h)=3h²/5. Thus V(h)=12h², KB=2h/3, Awp=24h, and
I_T=20*(6h/5)³/12. At h=2, section area is 2.4 m², V=48 m³,
KB=4/3 m, Awp=48 m² and I_T=23.04 m⁴. This prevents passing Bonjean and
hydrostatic tests by a box-only linear area assumption. Same 1e-10 algebraic
tolerance; no production routine should supply the expected answers.

## Wetted area method identity

For the rectangular prism above, submerged bottom plus two longitudinal sides
have area 20*6+2*20h. A station-girth integral equals this quantity; it does not
include its two wet end faces. The complete closed prism shell adds 2*6h.
At h=2 the two method-specific answers are 200 m² and 224 m² respectively.
Neither may be silently substituted for the other. Preserve method, end-face
policy, approximation flag and units in the result and exported provenance.

A girth integral also ignores longitudinal surface slopes on a changing
section. Increasing station count alone does not remove that modeling error.
If used for the first release, call it a girth-based approximation and carry an
estimate marker even when the underlying offsets are measured. A triangulated
shell method instead needs explicit topology/correspondence and convergence
evidence; no need to invent a triangulation from incompatible sections.

At inclined attitudes, each section clips against z=q*y+(d+p*x), using exactly
the selected equilibrium's p, q and d. Legacy helpers with only heel/intercept
cannot be presented as trim-aware. Dimensional coefficients, geometric frames
and empirical resistance eligibility must remain separately identified.

## Supplied deck points

For any explicitly declared deck point (x,y,z) above keel, normal clearance
from a plane z=p*x+q*y+d in the same datum is
(z-p*x-q*y-d)/sqrt(1+p²+q²). Use this exact signed distance for geometry tests;
an upright body-axis vertical distance is not the inclined normal clearance.
Positive/negative represent dry/immersed points. Missing deck geometry remains
unknown. Deck immersion and an open downflooding point are different events.

Curve reporting must distinguish sampled contact, an actual refined sign
bracket, and an unknown event beyond requested sampling. A last dry sample
does not establish a maximum safe angle or proof of a watertight deck.
