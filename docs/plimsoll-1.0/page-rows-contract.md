# Declared page rows (ledger projection)

Status: v0, armour implemented (`tools/plimsoll/page_rows.py` + `systems.armour.fixed.page_rows`).
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

## Invariants (diagnostics, not silent behaviour)

| code | blocking | meaning |
|---|---|---|
| `page_rows.item_duplicate` | yes | the same ledger item is declared by two rows (double counting) |
| `page_rows.item_unknown` | yes | the declaration cites an id absent from the selected ledger |
| `page_rows.item_uncovered` | no | a bound ledger item is declared by no row (lists the ids) |
| `page_rows.mass_mismatch` | no | declared rows total ≠ the leaf's `ledger_mass_t` |
| `page_rows.item_mass_unknown` | no | an item has no known mass, so the row total is incomplete |
| `page_rows.extent_invalid` | no | `extents_m` is present but does not declare finite `aft_m`/`fore_m` |

`values.matches_ledger_mass` is the single boolean a caller can check; it is true
only when the declared rows cover the leaf exactly and sum to its ledger mass.

## What it refuses to invent

* **No length from a centroid.** With no declared `extents_m`, `length_m` stays
  `null` and `segment_status` is `unknown_no_declared_extent`. Queen Mary's belt
  length therefore remains unknown on this page — the documented 176 m extent
  would have to be declared with its own source before it may appear.
* **No area-as-length substitution**, no per-segment mass inferred from
  proportions, no smoothing of coverage gaps: `item_uncovered` names the items
  instead.
* **No rotating turret armour on the armour page.** Rotating gunhouse armour is
  attributed to `armament.main.revolving-mounts` in the ledger; the armour page
  projection reports only what the declared rows bind, so the boundary is the
  declaration rather than a convention.

## Reusing it for other pages

Weapons (typed rows for torpedoes/mines/misc weight), freeboard (deck segments)
and engines (power/boiler rows) follow the same shape: declare the row bindings on
the corresponding `systems.*` leaf, then call `project_declared_rows` with that
leaf. The core stays ship-agnostic: it knows only ids, the ledger, and the
invariants above.
