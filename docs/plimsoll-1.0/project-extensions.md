# Optional calculation-core input contract

These optional fields extend `plimsoll-project-1`; `project_extensions` validates
them through `project_io.normalize_project`. It does not run calculators, read
files, accept proposals, or provide a second mass authority. The coordinator
consumes selected validated fields; a declared fact still needs an applicable
method and sufficient input before it produces a number.

Unknown values are null. Present numeric bool/nonfinite values are rejected.
Unknown provenance is retained with diagnostics, not normalized to measured data.
New typed objects reject unsupported keys; unrelated existing JSON extension
fields and reviewed legacy system structures are preserved.

## Facts and metadata

A fact is `{value, source, estimate}`. Source is a string/object/null; estimate
is true/false/null. Missing source/estimate is diagnosed as unknown without
rewriting the literal input. Numeric dimensions use their named SI unit; count
fields require integers. Nonempty text is required when a text value is known.

| Container | Allowed facts |
| --- | --- |
| `metadata` | country, type, design_year, laid_down_year, engine_built_year |
| `systems.propulsion.facts` | shafts, boilers, design_power_kw, trial_power_kw, max_speed_kn, cruise_speed_kn, engine_description, boiler_description, engine_built_year |
| `systems.weapons.<leaf>.facts` | calibre_m, unit_mass_t, length_m, diameter_m, projectile_mass_kg, charge_mass_kg, rounds_per_gun, mount_description, placement, weapon_type, mount_count |
| `systems.armour.<leaf>.facts` | thickness_m, length_m, height_m, area_m2, density_kg_m3, inclination_deg, zone, deck_layer |
| `deck.facts` | form, stem_angle_deg, ram_length_m, stern_overhang_m |

Year/count values are nonnegative integers, except shafts/boilers require positive
counts. Positive physical dimensions, speeds, powers and density must exceed zero;
mass, ammunition/count, thickness, area, ram/overhang may be zero. Angles are
signed. No invented physical angle or QPC upper cutoff is imposed here.

System facts live on a leaf declaring weight_item_ids, status or mass_models.
Such a boundary cannot contain nested system declarations, including beneath
intermediate containers. The facts, mass_models, source and fuel_bindings
payloads are not child systems; source content remains opaque. A fact leaf's
present weight_item_ids must be an array of unique existing ledger item IDs.
Empty links or a status-only leaf can remain a draft; systems.summary retains
authority for present/absent consistency, ledger accounting and shared ownership.
Existing scalar installed/broadside counts, raw power and mass_models retain their
reviewed meanings; new facts neither replace nor silently reinterpret those keys.
Existing count/formula keys remain the authoritative mass-model inputs. If a fact
is used to construct a later physical-model proposal, that operation must show
the explicit mapping and provenance rather than create a second contribution.

`display_preferences` accepts length m/ft, mass t/kg/long_ton, power kW/shp,
speed kn/m_s and angle deg/rad. These are display/import choices only; canonical
`units` remain fixed. No values are converted during schema validation.

## Fuel ownership

`systems.propulsion.fuel_bindings` has optional coal/oil entries:

```json
{
  "coal": {"weight_item_ids": ["coal-bunker"], "source": "ledger allocation", "estimate": true},
  "oil": {"weight_item_ids": [], "absent": true, "source": "explicitly absent", "estimate": false}
}
```

IDs must exist, be unique within each fuel and not overlap between fuels.
Empty IDs require `absent: true`; an absent fuel cannot own items. An absent
binding means unknown ownership. Every present binding, including declared
absence, requires nonempty string/object source and boolean estimate. Missing,
null or blank provenance is an error for this calculable declaration; nullable
descriptive facts retain their separate unknown-value semantics.
Later engine/endurance input comes from those
IDs' selected effective masses; no name matching or duplicate ledger is defined.

## Deck and profile

`deck` may be null, otherwise it declares source/estimate and 1..10000 points.
Each point has a unique nonempty ID and x_m/y_m/z_m, with z above keel and
nonnegative. Coordinates may be null in a draft; supplied values must be finite.
Optional point source/estimate overrides preserve finer attribution.

Optional `segments` have unique IDs, aft_point_id and fore_point_id referencing
supplied points. Where both x values are known, fore x must exceed aft x.
Optional segment source/estimate is preserved. Optional `reference_length_m` is
a positive typed fact for coverage percentages. Segments do not duplicate point
heights, declare watertightness, or automatically become downflooding openings.
The coordinator must reject incomplete geometry for clearance computation and
label partial/overlapping profile coverage instead of assuming full coverage.
No legacy upright B/2 immersion estimate is established by this schema.

`systems.armour.fixed.deck_coverage` is an independent plan-area study with
`covered_plan_area_m2` and `reference_plan_area_m2` facts. Each fact uses
`{value, source, estimate}`. Known areas require a nonempty source and a boolean
estimate flag; covered area may be zero, reference area must be positive, and
covered area cannot exceed reference area. Missing areas remain unknown.
This geometry ratio does not change armour mass or derive area from plate mass.
It is a Plimsoll engineering definition, not a claimed SPS formula.

`systems.weapons.<battery>.rotating_armour_component` may declare
`{mount_weight_item_id, mass_t, source, estimate}`. The parent ID must belong
to that battery's `mounts` page row. A known nonnegative component mass needs
a nonempty source and boolean estimate; `mass_t: null` remains unknown. The
selected loading ledger supplies the parent mounting mass. If the component
exceeds that selected mass, the study is unavailable with a diagnostic.
The component is a nonadditive split inside the parent item: it never creates
another displacement or fixed-armour mass. Queen Mary has no sourced split.

## Resistance scenarios

`resistance_scenarios` is an array (at most 201) of unique IDs, method,
attitude_policy, source and boolean estimate. Methods are
`holtrop_mennen_1982` or `taylor_gertler_source_axis_strict`. Attitude policy is
`strict_upright` or explicit `selected_plane_longitudinal_trim_proxy_v1`.
The proxy's future outputs must be estimated, non-primary and model_applicable
false regardless of input provenance. Validation does not establish empirical
eligibility or make an incomplete scenario calculable.

`inputs` permits c_stern, bulb_area_m2, bulb_height_m, transom_area_m2,
additional_roughness_delta_ca, delta_cf, x_fore_perpendicular_m,
x_aft_perpendicular_m, density_kg_m3, gravity_m_s2, kinematic_viscosity_m2_s,
appendages and bow_thruster. Coefficients/coordinates follow their kernel units.
Positive density/gravity/viscosity, nonnegative areas/roughness/heights, and fore
x greater than aft x are checked. appendages is an explicit array of area_m2 and
positive factor objects; [] declares absence. bow_thruster declares boolean
present, with positive diameter_m/coefficient when supplied; absent thrusters
cannot carry increment geometry. Unknowns remain null or omitted; no bulb,
transom, appendage or roughness default is inserted. Loaded displacement, draft,
beam and length cannot be overridden through this shape-scenario object.

Every non-null inputs entry requires an input_provenance entry with nonempty
source and boolean estimate; structured appendage/thruster entries use their
containing entry's provenance. Orphan provenance keys are errors. Optional qpc
is a positive sourced typed fact. Optional qpc_sensitivity is
`{values: [...], source, estimate}`, 1..21 positive strictly increasing samples.
No scenario silently adds a default QPC.

Optional table_id/table_sha256 retain table identity. A present table_sha256
must contain exactly 64 lowercase hexadecimal characters; null is invalid.
Optional friction_method,
interpolation_method and speed_conversion_method only accept the reviewed
implicit Schoenherr, strict source-axis Taylor and exact international-knot IDs.
Missing required table/method/scenario inputs remain the coordinator's explicit
unavailable boundary. All assumptions must appear in request identity/results.

## Endurance and historical comparisons

`endurance_scenarios` is an array (at most 201) with unique IDs and the reviewed
steady_simultaneous_fuel_consumption method. It contains speed_kn, power_kw,
source (nonempty string), boolean estimate, and coal/oil fuels. Each fuel declares
boolean required, nonnegative burn_t_per_day and reserve_t. Unknown burn/reserve
is retained; known positive burn requires required=true. Actual available fuel
comes only from selected ledger bindings. The schema computes no range.

`historical_comparisons` rows have unique id, quantity, value, unit, condition_id,
source and estimate. Supported quantities/units are shaft_power_kw (kW/shp),
displacement_t (t/kg/long_ton), speed_kn (kn/m_s), range_nm (nm) and draught_m
(m/ft). A real existing condition is required. Power/range comparisons require
an explicit positive speed_kn; other quantities may include it. Optional raw
value/unit preserve original attribution. Unknown value/provenance remains
unknown. Later comparison requires exact condition/speed, compatible conversion
and explicit diagnostics; no historical-validation claim follows from a match.

## Stored acceptance audit

`loading_conditions[].override_provenance[item_id][field]` is specified by the
data contract. Its optional acceptance object is only valid for mass_t and
contains operation replace_weight_item_mass, matching condition_id,
source_system_id, source_model_id, formula, inputs, input_provenance,
previous_mass_t, new_mass_t and three lowercase SHA-256 identities:
project_fingerprint, input_fingerprint and request_fingerprint. New mass must
equal the containing numeric override. Both previous_mass_t and new_mass_t
are required finite nonnegative numbers; missing/null/bool values are errors.
Optional method is one of the four
reviewed systems mass-model methods. Inputs are nonnegative numeric values,
except count_field/count_basis text; every input has source/boolean estimate.

This record is audit data, not proof that a proposal is fresh or authorized.
The later application API must recompute identity from current normalized
request/options, compare its binding, and recompute the actual systems proposal
and source from the current project before changing a selected-condition mass.
Comparing two echoed client hashes is insufficient. Schema validation does not
implement the application operation or rewrite any base/other-condition item.
