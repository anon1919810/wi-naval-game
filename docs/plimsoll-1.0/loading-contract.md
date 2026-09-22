# Plimsoll 1.0 loading contract

`loading.resolve_loading(project, condition_id)` accepts a canonical
`plimsoll-project-1`, normalizes a defensive copy, and requires an existing
loading-condition ID. It returns `schema: plimsoll-loading-1`; it never mutates
the project or fabricates residual mass from reference displacement.

The result carries `project_id`, `condition_id`, canonical `units` and
`coordinates`, `project_fingerprint`, and `input_fingerprint`. The project hash
identifies normalized project input. The result hash is the SHA-256 of canonical
JSON containing that project hash and the selected condition ID, so condition
selection always changes derived identity.

`effective_items` contains deep-copied items after applying only override keys
that are present. A present zero is known zero and a present `null` is unknown.
Each row adds `group_id`, `group_label`, sorted `overridden_fields`, and
`provenance` containing the unchanged source and tri-state estimate value.
`groups` reports item count, known and complete mass, known and complete x/y/z
moments, axis completeness and group CGs. The aggregate `values` object reports:

- `known_mass_t`, the subtotal of known masses;
- `total_mass_t`, which is `null` when any mass is unknown or a required group
  has no items;
- `known_moments_t_m`, partial x/y/z moment subtotals;
- `moments_t_m`, whose individual axes are `null` when incomplete; and
- `lcg_m`, `tcg_m`, and `kg_m`, exposed independently when their axis is
  complete and total mass is known and positive.

`complete_mass` also requires no active ownership overlap. `complete_cg`
requires complete mass, all three axes and positive total mass. Unknown
coordinates on a zero-mass item do not block a moment or CG. An empty optional
group is intentionally absent; an explicit zero item makes a required group
nonempty. A zero-mass whole design has no defined CG and receives a blocking
diagnostic.

## Ownership and coverage

Each positive- or unknown-mass item owns its own ID and every string in
`includes`. If two active items own the same token, a blocking
`loading.ownership_overlap` diagnostic prevents complete mass and CG. An item
overridden to zero owns no mass. Tags are semantic: unmarked overlaps and
synonyms cannot be detected automatically, and a parent that includes a child
ID must not be added alongside a positive standalone child.

`coverage` contains the selected reference displacement, modeled/reference
ratio and percent, and signed unallocated mass (`reference - modeled`). A
missing reference yields `null` fields. Values outside 95–105% receive a
warning, but reference coverage neither creates mass nor repairs missing groups,
unknown values or ownership overlap.

## Provenance and uncertainty

`provenance` counts `estimate: true`, `false`, and `null` separately. Missing
source metadata or unknown estimate status places the item in
`unverified_item_ids`; unknown is never treated as confirmed non-estimated.

`uncertainty` is a conservative engineering interval, not a confidence
interval. It multiplies every nonnegative mass range by each signed position
range using all endpoint products, sums contribution extrema, and divides the
moment interval by the strictly positive total-mass interval using all endpoint
quotients. Correlation is intentionally discarded, so bounds may be wide.
Known values without bounds are held at their nominal values and listed in
`conditional_on_nominal_fields`. Estimated items missing bounds are listed in
`missing_estimate_bounds` and receive a diagnostic. Unknown mass, an unsupported
axis, a nonpositive lower mass bound, a missing required group, or ownership
overlap prevents the affected full CG interval from being certified.

An override clears any inherited interval for the overridden field and emits
`loading.uncertainty_override_cleared`; the base interval describes the base
value and is not silently widened or reused as override-specific evidence.
