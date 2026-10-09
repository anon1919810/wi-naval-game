# Plimsoll 1.0 systems, resistance, and endurance contract

This contract defines the Task 7 calculation kernels consumed by the later
project-analysis coordinator. It does not define or implement
`analysis.resistance_for_loading`; that coordinator must derive each resistance
request from the selected loading and equilibrium state.

## Systems and the weight ledger

`systems.summary(project, state)` accepts a canonical project and the selected
`plimsoll-loading-1` state. The selected loading ledger is the only mass and CG
authority. A systems row links existing effective items through
`weight_item_ids`; links never add mass. Output retains the selected condition,
project fingerprint, loading input fingerprint, effective item provenance, and
the loading diagnostics.

The reviewed Task 3 forms are supported directly. A top-level leaf such as
`propulsion`, `cargo`, or `ballast` contains `weight_item_ids`. Nested leaves such
as `weapons.main`, `weapons.secondary`, and `weapons.torpedo` are flattened to
those dotted result IDs. `installed_guns` or `installed_tubes` maps to
`installed_count`; `broadside_guns` maps independently to `broadside_count`.
Installation and ammunition formulas use installed count. Broadside count is a
combat-output field and never scales ledger mass.

A row declared `status: present` must link at least one selected-ledger item.
An empty `weight_item_ids` list is unknown ownership, not known zero mass, and
produces blocking `systems.present_without_weight_items`. A genuinely absent
system uses `status: absent` with a reason.

An extended row may declare:

```json
{
  "status": "present",
  "weight_item_ids": ["engine-item"],
  "source": "builder return",
  "estimate": false,
  "mass_models": [
    {
      "id": "engine-volume-check",
      "method": "volume_density_mass",
      "linked_weight_item_id": "engine-item",
      "inputs": {"volume_m3": 12.5, "density_kg_m3": 8000.0},
      "comparison_tolerance": {"relative": 0.01, "absolute_t": 0.01},
      "source": "declared physical check",
      "estimate": false
    }
  ]
}
```

Supported physical checks are `volume_density_mass`,
`plate_area_thickness_density_mass`, `counted_unit_mass`, and
`counted_ammunition_mass`. Counted models may select `installed_count`,
`installed_guns`, or `installed_tubes`; a model with a separate installed-unit
boundary may instead declare an integer `count_value` and named `count_basis`.
Broadside fields are rejected as mass multipliers. The ammunition method uses
an installed-count field, `rounds_per_gun`, and separate projectile and charge
masses in kilograms. A difference outside the declared
comparison tolerance produces `systems.mass_mismatch` and a review-required
`replace_weight_item_mass` proposal. Summary is read-only: the formula result is
never added to the ledger total and never overwrites a manually reviewed mass.
An explicit absent system uses `status: absent` plus a reason and yields no fake
zero performance.

Every physical model must declare a non-empty `source` and boolean `estimate`
before it can calculate or propose a change. An estimated model must additionally
provide `input_provenance` for every formula input; each entry has its own
non-empty source and boolean estimate status. Missing or malformed provenance is
rejected rather than converted into an untraceable ledger proposal.

Unknown item IDs, repeated links, links shared by multiple system leaves,
unknown effective masses, and an incomplete loading ledger prevent a complete
systems total. Canonical loading ownership diagnostics remain visible. This is
how rotating mount armour and ammunition remain represented exactly once: their
existing ledger item and `includes` tokens carry ownership; no system page
creates a second weight.

The Queen Mary case declares nineteen checks over existing ledger IDs. Thirteen
fixed-protection checks preserve the legacy bounding-box area, nominal plate
thickness, and 7,850 kg/m3 density. The areas are explicitly rounded estimates;
the strict algebraic comparison therefore exposes their small differences from
the already reviewed three-decimal ledger masses as proposals. It does not fit
area back from mass. Six armament checks preserve the accepted Task 3 formulas:
eight installed main guns, four installed twin main mounts, eighty main rounds
per installed gun, sixteen installed secondary guns and mount allowances, and
150 secondary rounds per installed gun. The main-mount boundary includes
rotating gunhouse armour and hoists above the fixed trunk. Fixed barbettes stay
in `armour.fixed`; no mass moves between ledger items.

## Engine and endurance semantics

`engines.compute(case)` preserves the existing `plimsoll-engines-1` interface.
Compatibility defaults are named in `result.methods`:

- `legacy_rounded_0.7457_kw_per_shp` preserves existing power results.
- `legacy_rounded_0.514444_m_s_per_kn` preserves existing Froude results.

New calculations select `international_mechanical_hp_precise` and
`international_knot_exact`; these route through `units.convert`. A caller must
select methods explicitly, so an existing result is never silently redefined.

`bunker_total_t` is available only when both `coal_t` and `oil_t` are known.
Fuel input traces preserve both the selected mass-field and binding sources.
Explicit fuel absence supplies known zero with the absence declaration's
estimate flag; an omitted binding supplies unknown. Fuel totals use tri-state
aggregation, while steady endurance uses the scenario and consumed fuel masses
only. Unused fuel and unrelated position/power metadata do not change it.
Optional displacement and LWL validate finite positive numbers whenever
provided. Fuel totals, endurance and calibration outputs must remain finite;
binary-scaled Admiralty evaluation preserves representable results whose
intermediate product would overflow.

Taylor table completeness is separate from turbulent-friction eligibility.
`speed_power_curve` applies the named project policy `Re >= 1e5`, consistent
with the existing Holtrop project policy. This is not a universal transition
threshold or empirical validation. Below it, a populated table may still return
a complete algebraic estimate, but `primary_result` and `model_applicable` are
false with `resistance.reynolds_policy`. The selected-plane adapter preserves
the per-speed diagnostic and eligibility through QPC rows, fixed-power inverse
studies and aggregate validity; one eligible speed never promotes another.
An explicit zero is a known zero. If one mass is unknown,
`bunker_known_subtotal_t` reports the known partial mass while total and fuel
percentage remain null with `engines.bunker_partial`. Historical `range_nm` and
`range_at_speed_kn` remain cited comparison inputs; they are not predictions.

Computed endurance requires an explicit fixed-operating-point scenario:

```json
{
  "method": "steady_simultaneous_fuel_consumption",
  "speed_kn": 12.0,
  "power_kw": 5000.0,
  "fuels": {
    "coal": {"required": true, "burn_t_per_day": 40.0, "reserve_t": 80.0},
    "oil": {"required": true, "burn_t_per_day": 20.0, "reserve_t": 20.0}
  },
  "source": "declared operating scenario",
  "estimate": true
}
```

Each positive per-fuel burn rate uses only that fuel's available mass after its
own reserve. The first required stream exhausted limits time; range is
`hours * speed_kn`. A zero burn rate declares an unused stream and does not emit
JSON infinity. A positive burn must declare `required: true`; an optional
positive stream would leave post-depletion operation undefined and is rejected.
Scenario `source` and boolean `estimate` metadata are required. Unknown required mass, reserve, or consumption makes endurance
null with a blocking diagnostic. This is a steady scenario estimate, not an
engine map or an energetic interchange between coal and oil.

## Holtrop--Mennen 1982

`holtrop.compute(inputs)` is the versioned `holtrop_mennen_1982` method. It uses
the 1982 form factor, wave regression, appendage, bulb, immersed-transom, and
correlation equations. It does not mix in the 1984 form factor, the 1984
three-Froude-band wave regression, or propulsion regressions. SI units are used
inside the equations, the exact international knot is `1852/3600 m/s`, and the
public result reports resistance in kN and effective power in kW.

Required inputs are waterline length, beam, fore and aft moulded drafts,
displacement volume, `CM`, `CWP`, LCB in percent of LWL positive forward, stern
factor, bulb and transom areas, appendage list, speed, density, gravity, and
kinematic viscosity. Missing bulb/transom areas or appendage list are unknown.
Explicit zero areas and `appendages: []` declare the corresponding absence.
Bulb height is required only for positive bulb area. Explicit wetted area is
preferred; otherwise the result labels the 1982 wetted-surface regression.

The optional 1982 bow-thruster increment is declared with
`bow_thruster: {present: false}` or a positive tunnel diameter and coefficient.
Additional roughness is declared once as `additional_roughness_delta_ca`;
explicit zero declares the base scenario. If either choice is missing, the
six-component equation remains available but scenario completeness and
`primary_result` are false. Base `CA` already represents the 1982 standard
roughness/still-air correlation, so callers must not add it twice.

Piecewise equality is deterministic: c12 uses its middle branch at 0.02 and
0.05; c7 at 0.11 and 0.25; c15 at 512 and 1727; c16 uses the polynomial at
`CP=0.8`; lambda uses the constant-offset branch at `L/B=12`; c4 includes 0.04;
and c6 is zero at `FnT>=5`. Source-rounded discontinuities are retained. Zero
bulb and transom areas short-circuit singular dependent formulas. Negative PB is
permitted when the 1982 equations remain real; the exact PB divisor zero is not.

Algebraic validity and empirical eligibility are separate. Raw arithmetic
overflow, singularity, invalid real-power bases, bools, NaN, infinity, and
unrepresentable scalars raise contextual `HoltropError` subclasses; no partial
total escapes. A finite `Fn>0.5` result receives the paper's high-speed warning.
The separate `Re>=1e5` primary-result rule is explicitly a conservative project
policy, not a limit claimed by Holtrop and Mennen. The method asserts no
universal `CB>=0.55` cutoff. Negative CA remains a signed correction with a
warning rather than being clamped or treated as automatic arithmetic failure.

### Fixed conformance benchmark

The frozen hypothetical/source-reproduction inputs are LWL 205 m, beam 32 m,
fore/aft draft 10 m, volume 37,500 m3, `CM=.98`, `CWP=.75`, LCB `-.75%`, bulb
area 20 m2 at 4 m above keel, transom area 16 m2, appendage area 50 m2 with
factor 1.50, stern factor +10, and 25 kn. Constants are `rho=1025 kg/m3`,
`g=9.81 m/s2`, and `nu=1.188e-6 m2/s`; wetted area uses the labeled regression.

The independent NTUA 1982 reproduction supplies the component targets: RF
869.47, RAPP 8.83, RW 556.63, RB 0.049, RTR 0, RA 220.53, and total 1791.54 kN;
effective power is 23039 kW. Tests use the source-fixed 0.1% relative tolerance,
with 0.005 kN printed-resolution floor, 0.0005 kN for RB, exact zero for RTR,
and 0.5 kW floor for power. Aggregation, `PE=RT*V`, density scaling, and force
normalization are tested separately at `1e-10` algebraic tolerance.

The primary 1982 numerical table is internally inconsistent: its printed
`CA=.000352`, `CF=.001390`, `RA=221.98 kN`, and `RF=869.63 kN` violate the
invariant `RA/RF=CA/CF`. Its printed 1793.26 kN total is only an informational
literal-table comparison. The discrepancy remains unresolved and is not used to
tune constants or relax component acceptance.

## Schoenherr and Taylor--Gertler

`resistance.friction_coefficient` requires one of two exact method IDs:

- `conn_1953_schoenherr_approx` is the retained explicit compatibility formula
  `0.4631/log10(Re)^2.6`.
- `schoenherr_implicit_ittc_0.242` solves
  `0.242/sqrt(CF)=log10(Re*CF)` and identifies that convention in trace output.

The legacy `schoenherr_cf` name still returns the Conn approximation. Numerical
solvability of the implicit equation is not a claim of turbulent applicability.
Official ITTC Table 2 anchors from `Re=1e5` through `1e10` are checked at the
six-decimal printed tolerance of `5e-7`; inverse and residual identities use
`1e-10`.

Taylor tables contain residuary coefficient `CR=RR/(0.5 rho S V2)`, not a pure
wave coefficient. `S` is static hull wetted area; appendages remain separate.
The Molland cells are printed as `CR*1000`, so stored values use scale `1e-3`.
Roughness `delta CF` is separate and applied once.

`taylor_gertler_source_table(table)` adds exact printed headings
`L/volume^(1/3) = [10,9,8,7,6,5.5]` by index to a copy of the tracked table. It
does not rewrite raw cells or the compatibility axis. Generic tables must
provide their exact headings explicitly.

The tracked compatibility axis is retained at its original nine-decimal
precision. Its serialized `source_axis_mapping` declares the by-index
association and the policy `round(1 / heading**3, 9)`; the adapter verifies that
rounding policy with only floating-representation tolerance. A generic mapping
without that audited rounding declaration must associate each explicit heading
with its stored reciprocal cube at the fixed `1e-10` algebraic tolerance.
Strict mode requires `source_axes.l_over_volume_cuberoot`, validates the declared
mapping policy, and interpolates on those exact headings. It never reconstructs
source headings from the rounded compatibility axis.

`residual_from_table(..., method="taylor_gertler_source_axis_strict")`
interpolates in the printed length-volume coordinate. It returns unavailable
outside stored axes and when any positive-weight corner is missing. Exact nodes
ignore unrelated zero-weight corners. Method, coordinate, completeness, trace,
and structured diagnostics remain in the result. The separately named
`legacy_volume_ratio_clip_renormalize` default preserves endpoint clipping,
interpolation in `volume/L^3`, and missing-corner weight renormalization for
existing callers; those behaviors are approximations, not source conformance.

The primary Gertler DTMB Report 806 page definitions could not be retrieved
through normal public access. Independent published sources support LWL, but
release text must retain that primary-page source gap. The stored subset covers
only `CP=.50-.80`, `Fn=.16-.58`, source length-volume ratio 5.5--10, and populated
breadth/draft cells. Broader original-series ranges do not expand stored data.

## Task 8 consumption boundary

The later coordinator should accept a normalized project, selected loading
state, upright equilibrium result, speeds, and explicit method configuration.
It must derive displacement and geometry independently for every loading
condition. Normal and deep results must never reuse a design-waterline mass,
draft, volume, area, or coefficient. A heeled or damaged equilibrium is not an
upright empirical resistance input unless a separately validated method exists.

For Holtrop, the coordinator builds the explicit input object above and calls
`holtrop.compute` once per speed. It must not fabricate bulb, transom,
appendage, stern, roughness, or bow-thruster data. For Taylor, it supplies the
selected state's LWL, static hull wetted area, CP, B/T, and volume/LWL3; adapts
the tracked table with `taylor_gertler_source_table`; and selects strict source
axis, implicit Schoenherr, exact knot conversion, a declared roughness delta,
and a declared QPC. `speed_power_curve` records each selected method and applies
roughness and QPC once.

Missing required geometry or table corners yields an unavailable total and a
diagnostic. It never becomes zero. The coordinator must copy the loading input
fingerprint, method IDs, source/estimate metadata, assumptions, units,
applicability, and structured diagnostics into exports and UI results.

### Named resistance scenarios

A coordinator may offer a named estimated bare-hull scenario only when every
otherwise unavailable choice is declared as data with source and estimate
metadata. At minimum, a Holtrop scenario option must state stern factor, bulb
presence and geometry, immersed-transom presence and area, appendage presence
and each area/factor, bow-thruster presence and any increment inputs, and the
additional-roughness choice. Explicit `present: false`, zero area, or an empty
appendage list means declared absence for that scenario; historical silence
does not. A power scenario must separately declare QPC and support QPC
sensitivity because shaft power varies inversely with it. Shape extras may be
sourced or labeled engineering estimates, but their status must survive into
the result.

The current Queen Mary, generic steamer, and analytic-box case augmentation
does not provide those Holtrop shape/scenario options. Their scalar hull and
offset data alone do not establish bulb, transom, appendage, or efficiency
assumptions and do not make a Holtrop estimate eligible. Task 8 may materialize
named options after the reviewed geometry interface is available; until then
the coordinator must return unavailable rather than infer them or treat a
scalar Froude number as validation.

## Sources and evidence limits

- J. Holtrop and G. G. J. Mennen, “An approximate power prediction method,”
  *International Shipbuilding Progress* 29(335), 166--170 (1982), DOI
  10.3233/ISP-1982-2933501, is formula authority.
- E. Karageorgos, NTUA diploma thesis (2015), PDF pages 85--86, is the independent
  component reproduction benchmark, not formula authority.
- Molland, Turnock, and Hudson, *Ship Resistance and Propulsion* (2011), printed
  pages 206, 208, 236, and 495--498, supports Taylor normalization and the stored
  subset.
- The official 8th ITTC proceedings, formal discussion printed page 104,
  supplies the `0.242` implicit convention and rounded friction table.

The source papers and supplied textbook excerpt are not release assets. These
benchmarks reproduce equations and table normalization; they do not validate
accuracy against Queen Mary trials or any measured vessel.
