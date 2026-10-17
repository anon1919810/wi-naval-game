# 分段装甲带与分层甲板

This is the next independently accepted unit after whole-battery adoption, authorized by the user to proceed autonomously. It adds a geometric flat-panel model, not another SPS recovered expression.

## Useful finished behavior

Choose an existing main/end/upper belt, transverse bulkhead or deck record, then declare one or more rectangular plates. A segmented belt uses adjacent plates with individually declared lengths/thicknesses; a layered deck uses multiple plates whose masses sum. Declare a plate count explicitly for two sides or repeated panels. No implicit doubling. Existing fixed-armour records keep their empirical inputs for comparison, but only the selected model contributes to mass proposals and armour estimate totals.

## Canonical declaration

Optional `concept_design.armour_geometry = {source: string|null, regions: [{fixed_armour_id: string, source: string|null, plates: [{id: string, source: string|null, density_source: string|null, length_m: number|null, width_m: number|null, thickness_mm: number|null, density_kg_m3: number|null, count: integer|null, width_basis: 'developed'|'projected'|null, inclination_deg: number|null}]}]}`. Absent/null preserves the complete old shape and models. Present regions=[] opts in no region. Each existing fixed record may appear once; only kinds belt_main/belt_ends/belt_upper/bulkhead/deck are eligible in this first geometry unit. Curved bulges/conning towers and gun-house geometry remain outside the rectangular model; their old empirical capability is preserved.

Region membership explicitly selects the geometry model for that region, even if unfinished. Missing plate list or empty list is incomplete, not a declared zero. A known zero plate count is explicit no plate. Plate IDs unique within each region, fixed IDs unique across regions; missing references rejected. Save unknown draft facts; reject wrong types, negative/nonfinite values and unknown keys structurally. At most 50 regions and 100 plates/region. Existing IDs retain the repository's ASCII ID grammar. Domains: length/width 0..5000 m, thickness 0..2000 mm, density >0..30000 kg/m³, count 0..1000000 integer, angle -89..89 degrees. Null always unknown.

## Geometry and provenance

New pure `armour_geometry.py`, method `plimsoll-armour-panels-v1`. Evaluate per plate and per region, no project mutation or I/O. All outputs finite JSON and independent value availability/diagnostics. Keep legacy direct import fallback.

For developed width, area = length × width × count and angle is not read. For projected width, developed width = width / cos(angle), with signed angle from the vertical for belts/bulkheads and from the horizontal for decks. Both signs have the same area. Angle is required only in projected mode. Thickness is normal plate thickness. Volume = developed area × thickness_mm / 1000; metric mass = volume × declared density / 1000. Unknown count/dimension/thickness/density produces unknown dependent values; known count=0 produces zero area/volume/mass without reading irrelevant dimensions. Known zero thickness may determine zero mass while area remains unknown; label that dependency behavior. Do not clamp out-of-domain outputs or add fabrication allowance, taper, supports, fasteners or curved area.

Numbers can be mathematically available while provenance is insufficient. Generated proposals require a nonempty region/project geometry source and nonempty plate geometry source plus density_source for each contributing positive-mass plate. No default material density, no silently inherited empirical thickness/size, no implicit angle or number of sides. Diagnostic and adoptable flag explain missing source. This model supplies no CG, coverage overlap test, ballistic protection or structural adequacy; existing ledger positions remain authoritative.

Implementation contract: both the root geometry source and region source are required for adoption. Pure API `normalize(config, fixed_armour, path)` and `evaluate(region, kind, *, source=None, path=...)`; output method `plimsoll-armour-panels-v1`, `id=fixed_armour_id`, `status`, `adoptable`, `values={area_m2,volume_m3,mass_t,known_mass_subtotal_t}`, and `records` for per-plate readings with stable plate IDs, same method, status/adoptable/values. Missing source does not erase mathematically available values. Old fixed-armour comparison marks `active_mass_model='geometry'` at record root.

## Integration and adoption

New separate `design_balance.armour_geometry[]` family, records id=fixed_armour_id; stage family/record method match. Values include area_m2, volume_m3, mass_t, known_mass_subtotal_t, per-plate readings and origins. Complete mass unknown if any declared plate is unknown; no known-subtotal substitute. Expose independently before unrelated hull/balance early returns.

Opted-in fixed regions suppress their old SPS mass models, including when geometry is unavailable. Old SPS fixed readings remain numerical comparisons with explicit `active_mass_model='geometry'` metadata and a translated inactive-for-adoption notice. They are not silently relabeled as geometric output. Armour totals use exactly one chosen component per fixed region: geometry mass/method when opted in, otherwise old SPS result. An unknown geometry result cannot fall back to known SPS mass. Current selected ledger actual remains independent. No new ledger or target. Protect referenced fixed records against removal/rename/kind changes until unlinked.

Use a new physical systems method `armour_panels_mass_v1`; `_calculated_mass` recomputes the pure panel model from complete declared inputs, instead of trusting an opaque accepted mass or calling it empirical_estimate_v1. Existing model metadata/input provenance and `_analysis_proposals` physical receipt path apply; record geometry method version and complete per-plate declarations/source in inputs. Reuse current atomic selected-condition adoption with recomputation, stale/forged rejection and history; do not auto-adopt. No API endpoint needed.

Physical model inputs are `{method_version,region_kind,geometry_source,region}` with `region` carrying the complete normalized plate declaration. Recompute this declaration, validate the version and kind, require its adoptable flag, and reject opaque precomputed mass. Generated model/proposal `concept_component='fixed_armour'` remains a presentation category, not an empirical-method claim. Persisted receipts validate this method's nested declaration specifically; do not relax other methods' numeric input rules.

## Ordinary UI and saved reporting

New ArmourGeometryEditor with optional enable, source, explicit eligible-region selection, per-region plate rows, add/remove plate controls and inputs. Enabling never selects a region or invents density/geometry. Fields state angle convention based on region kind and width basis. Canonical metres/mm persist through display preferences. Warn that overlapping or layered declarations are user-specified and count separately; do not imply automatic intersection detection.

Shared result projection and full report show active geometric estimate next to explicitly inactive empirical comparison; plate area m², volume m³ and metric mass with correct units. ID/method/availability gated deltas for region and plate readings; requested&&completed saved-report parent gate. Both Chinese/English. No frontend engineering formula.

## Acceptance anchors and stage batch

- Two identical developed plates L10 × W2 m × 100 mm × 7850 kg/m³ => area40 m², volume4 m³, mass31.4 t.
- Same projected W2 m at ±60° => area80 m², volume8 m³, mass62.8 t; developed basis ignores that angle and remains31.4 t.
- A two-layer deck adds each explicitly declared layer once; unknown layer blocks complete mass but retains known subtotal.
- Known zero, missing angle only for projected basis, missing density source, invalid inputs, duplicate IDs/references, and finite boundaries.
- Absent compatibility; opted-in incomplete geometry suppresses empirical adoption and totals fallback; switching off restores old suggestion without changing selected ledger.
- Real save→run→review→adopt→recompute→reopen preserves all positions, other conditions, archives and unrelated receipts. Forged/stale proposals rejected.

Use roughly 12–18 central scenarios and an independent hand calculation. Final run only new geometry/unit/workflow and related model/adoption tests; shared frontend stage batch + build. Reuse earlier source vectors, no original native probes for this new geometric method, no entire repository retest after each edit.
