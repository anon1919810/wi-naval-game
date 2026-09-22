# Task 8G binding preparation report

Status: **PREPARATION_READY — provisional, no implementation claim**

This read-only preparation maps every immutable seven-page record in
`task-8g-binding-proposal.json`. It does not change production code, run a
numerical test, expand the approved exclusions, or claim that pending bindings
are implemented.

## Coverage checkpoint

- Inventory: 191 unique original IDs (184 page records plus 7 common controls).
- Observation state: 190 observed, 1 unobserved gun-battery editor record.
- Approved scientific exclusions: exactly 26, unchanged.
- Proposal ordering exactly matches the immutable inventory.
- 53 records have current canonical/stage paths, including five whose later
  rendering is presentation-only.
- 10 additional records are presentation controls deferred by the user's
  computation-only scope.
- 1 record remains observation-limited.
- 101 records need a binding projection, typed schema extension, or one of the
  bounded adapter families below. This is a record count, not 101 proposed
  modules or algorithms.

Inventory SHA-256:
`b4b979b73b48a8e8b9f668375f4be0616ee3af5f882b72ede05b46b32f007d07`.

Proposal SHA-256:
`0a9aae8e54e72747255c5f3009fca0942c6f8f2ac8992efc9e95cd2f19e0187c`.

The mapping was prepared at repository HEAD
`4bec0818b5fccda5dc060e18425bc9762dc13a19` while coordinator/CLI work was
still active. It records these interface hashes and must be reconciled after
freeze before implementation:

```text
analysis.py            249ff374d57926971911edc901812baa6b1dfa293a6697610730c460549588a5
project_extensions.py  91040fc54849b387eb736cbbaa102c896f0450d7541b3cf5c31d124d60b2b14d
project_io.py           aa87146c94b74acf670f9ef69f69eccdbeb8d18c4d4386fdc4896f8239d2460e
```

## Highest-priority bounded adapters

1. **Weapons mass presentation adapter.** Use the selected ledger as the only
   mass authority while exposing gun, mount, ammunition and rotating-armour
   subtotals through explicit linked-item includes/excludes. Add independent
   broadside kg/lb from broadside count and typed projectile mass with complete
   provenance. Never require unrelated unknown mass inputs for broadside and
   never count shared armour twice.

2. **Repeated-store typed inputs.** Add real repeated torpedo, mine and depth
   charge rows with carried/reload/arrangement semantics, plus positional
   miscellaneous weights. Current generic weapon facts and system leaves cover
   some dimensions/counts and ledger ownership but do not define these exact
   semantics. Unknown historical data remains null; declared absence can be
   zero only with source/estimate.

3. **Armour grouping adapter.** Bind typed armour facts and selected linked
   masses into belt, deck and conning groups. The adapter must honor zone and
   deck-layer facts, item includes/excludes, and shared ownership. Physical
   model results are comparisons/proposals rather than a second ledger.

4. **Loaded stability/design-display split.** Add a selected-loading roll-period
   result from selected GM and a declared gyration fact. Keep it distinct from
   L0 design-waterline roll output. Separately expose reviewed design natural
   speed and form-ratio results; do not label them selected-loading results.

5. **Multi-condition binding orchestration.** Run identified normal, deep/full,
   standard and light conditions separately and retain each `condition_id`,
   `input_fingerprint` and `request_fingerprint`. Standard/light exist only when
   explicitly created; no guessed consumable subtraction or name/index fallback.

6. **Deck segment projection.** Join stored segment endpoint IDs to
   `stages.deck.data.points[*].normal_clearance_m`, and divide segment length by
   the explicit `profile.reference_length_m` only when requested. Missing fore
   or aft segments stay unknown. Existing whole-profile coverage and mean
   clearance paths remain authoritative.

7. **Request/classification adapters.** Define fixed-power versus predicted-power
   mode in request identity, explicit variable-load group classification, and a
   real trim-target constraint if the product retains “Set Trim.” Initial solver
   guesses do not constitute a trim constraint.

## Concrete unresolved computational gap

`armour.settings.minimum_main_belt_length` has no approved algorithm or stable
result path. Machinery/magazine compartment extents are not yet a reviewed
minimum-belt rule. The proposal therefore leaves this as
`unresolved_computational_gap`; full compartment extent, a Queen Mary constant,
or an SPS-style proxy must not be substituted.

## Already bindable result surfaces

- Loading and group totals:
  `$.stages.loading.data.values.total_mass_t` and
  `$.stages.loading.data.groups[id=<id>].total_mass_t`, always with the explicit
  result `condition_id` and fingerprints.
- Geometry/hydrostatics: selected waterline dimensions, area, coefficients,
  wetted surface and GM under `$.stages.hydrostatics.data`.
- Deck: point normal clearances and profile segments/coverage/mean under
  `$.stages.deck.data`.
- Stability: solved draught/trim/heel and GZ maximum, roots, endpoint and
  downflooding under equilibrium/GZ stages.
- Resistance/power: selected speed rows at
  `$.stages.resistance.data.rows[*]` and `power_rows[*]`; kernel component paths
  remain method-specific (`kernel` versus `kernel_row`).
- Propulsion/endurance: selected fuel masses and exact
  `$.stages.endurance.data.values.hours|range_nm`.
- Flooding: status, timeline/downflooding and optional remaining-GZ data are
  retained by the flooding stage, though none of the 191 SPS records authorizes
  converting them into excluded shell/torpedo hit-count scores.

## Verification

The preparation validator parsed both JSON files and asserted exact ordered ID
equality, 191 unique records, exactly 26 exclusions, exactly one unobserved
record, immutable source SHA-256, and only the 15 stable analysis stage names.

```text
PASS records=191 unique=191 exclusions=26 unobserved=1 stage_names_valid=true
with_input_or_result=156
```

No numerical tests or full suite were run. The next producer should first
reconcile the three checkpoint hashes, then split implementation ownership by
the bounded adapter families rather than treating the 101 pending field records
as independent tasks.
