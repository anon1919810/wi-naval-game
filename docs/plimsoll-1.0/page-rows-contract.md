# Declared page rows (ledger projection)

Status: declared row projection used by fixed armour, main/secondary guns,
torpedo/mine/depth-charge groups and the five miscellaneous-weight zones.
This document is the contract for every SPS page that needs "page rows": it says
what a declared row is, which invariants the projection must enforce, and what it
must refuse to invent.

## The gap this closes

An SPS page shows rows (Belts & Bulkheads, deck segments, torpedo/mine rows,
engine rows). Before this layer there was **no declared correspondence** between
those rows and the weight ledger. For Queen Mary the SPS armour page declared 8
rows (main / upper / ends / armour_deck ×2 / torpedo_bulkhead / barbette /
conning tower) while the ledger carries 13 armour items, with **different ids and
different granularity**. Nothing could answer "which ledger mass is the `main`
row, and does it sum to the ledger's armour group?".

## The contract

A leaf of `systems.*` may declare `page_rows`: an array of rows, each

```json
{"row": "main",                    // stable row identifier (SPS page row)
 "label": "Main belt",             // display label
 "thickness_mm": 229.0,            // declared nominal thickness (or null → echoed from plate model)
 "weight_item_ids": ["armour-belt-229mm"],   // the binding: which ledger items make up this row
 "extents_m": {"aft_m": -60.0, "fore_m": 116.0},  // optional; only when actually declared
 "source": "…", "estimate": true}
```

The projection (`page_rows.project_declared_rows`) then:

1. resolves every declared id against **the selected loading ledger**
   (`effective_items`) — the single mass authority — and takes `mass_t` from there;
   it never recomputes mass from area × thickness;
2. echoes geometry provenance (`area_m2`, `thickness_mm`) from the leaf's
   `plate_area_thickness_density_mass` models when the row does not declare a thickness;
3. reports unknowns as unknown.

Rows may declare a `group` identifier. The projection reports a subtotal only
from the rows in that group; if any member mass is unknown the subtotal is
`null`. A ledger item can belong to only one row in a leaf, so grouping never
creates a second physical mass. Queen Mary declares separate belts, bulkheads,
deck, barbette and conning groups.

## Invariants (diagnostics, not silent behaviour)

| code | blocking | meaning |
|---|---|---|
| `page_rows.item_duplicate` | yes | the same ledger item is declared by two rows (double counting) |
| `page_rows.item_unknown` | yes | the declaration cites an id absent from the selected ledger |
| `page_rows.item_uncovered` | no | a bound ledger item is declared by no row (lists the ids) |
| `page_rows.mass_mismatch` | no | declared rows total ≠ the leaf's `ledger_mass_t` |
| `page_rows.item_mass_unknown` | no | an item has no known mass, so the row total is incomplete |
| `page_rows.extent_invalid` | no | `extents_m` is present but does not declare finite `aft_m`/`fore_m` |

`values.matches_ledger_mass` is true only when the declared rows cover the leaf
exactly and sum to its ledger mass. It is `null` when the leaf or a linked item
has unknown mass; `null` is not zero or a passing reconciliation.

## What it refuses to invent

* **No length from a centroid.** With no declared `extents_m`, `length_m` stays
  `null` and `segment_status` is `unknown_no_declared_extent`. Queen Mary's belt
  length therefore remains unknown on this page. The separate minimum-belt
  study takes an explicitly complete set of protected compartment extents and
  end margins; it is an engineering estimate, not an SPS formula or a substitute
  for the physical belt extent.
* **No area-as-length substitution**, no per-segment mass inferred from
  proportions, no smoothing of coverage gaps: `item_uncovered` names the items
  instead.
* **No rotating turret armour on the armour page.** Rotating gunhouse armour is
  attributed to `armament.main.revolving-mounts` in the ledger; the armour page
  projection reports only what the declared rows bind, so the boundary is the
  declaration rather than a convention.

## Reusing it for other pages

Weapons use the same selected-ledger row projection. Repeated torpedo, mine and
depth-charge rows accept typed declarations (counts, dimensions, arrangement),
and reject invalid numeric fields and duplicate item bindings. Their mass still
comes only from the linked ledger item; a typed unit weight never silently adds
mass. The five positional miscellaneous rows remain unknown for Queen Mary
because their ledger allocations are not sourced.

Deck endpoint freeboards are computed from the selected flotation plane and
declared deck points; they are geometric results, not mass projections. The
engine view reads declared facts, the installed machinery ledger subtotal and
explicitly named selected loading groups. These are separate adapters and do
not reuse `project_declared_rows`.

Armour-deck coverage is another separate adapter under
`stages.systems.data.deck_coverage`. It divides explicitly sourced protected
plan area by explicitly sourced reference plan area. Plate surface area and
ledger mass are not substitutes, and Queen Mary retains an unknown result until
both plan areas are supplied.
