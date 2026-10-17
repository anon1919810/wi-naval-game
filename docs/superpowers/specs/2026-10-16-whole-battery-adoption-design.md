# 整炮组炮座估重采纳闭环

User approved execution of the next-delivery-and-mass-loop plan. This document makes its candidate proportional policy concrete for implementation. All earlier read-only totals remain read-only.

## Declaration and identity

Optional `concept_design.battery_mass_allocation = {source: string|null, layout_ids: string[]|null}`. Absent/null adds no result family and changes no prior models. null IDs mean unknown selection, [] explicit no selected layouts; only explicit selected layout IDs opt in. Unique existing layout IDs, no overlap in referenced battery or mount-target ownership across selected layouts. Existing project/system ownership checks remain authoritative. Preserve no implicit import activation.

New pure module `battery_mass_allocation.py`, method `plimsoll-battery-mount-allocation-v1`; policy `proportional-row-mounts-v1`; source estimate method `sps-3b3-battery-totals-v1`. Public validation/evaluation functions documented by implementer, finite JSON and structured diagnostics. Relative and legacy direct imports both supported.

## Policy

For each selected layout, reuse the recovered whole-battery mounts estimate once. Compute each referenced row's independent old mount estimate as its allocation weight, reading only facts necessary for mounts (do not make allocation depend on ammunition). Weight is not current ledger mass. Positive total requires known nonnegative weights and a positive finite weight sum. Allocate proportionally and assign floating residual to the last nonzero row so parts conserve the source total. A zero-count row has zero share; known zero whole total and all zero row weights give explicit zero allocations. Unknown source, weight or required target blocks the complete allocation; there is no guessed share and no first-row fallback. Unreferenced zero groups create no target; positive unreferenced groups are unavailable. Bound referenced zero rows still have their existing target and can propose clearing an old positive mass.

The group yields readonly source total, old-row subtotal, selected ledger total, per-battery allocation weights/shares/target IDs/allocated metric tonnes, availability, diagnostics and provenance. Source empirical total and product allocation policy must be separately visible and recorded. It does not change source gun, ammunition or complete layout-armour formulas. Existing gun/ammunition/armour adoption remains available through its existing targets.

## Generated models and atomic adoption

For all explicitly selected layouts suppress old per-row mount models even when the new estimate is unavailable, preventing an implicit fallback. Register at most one new model per existing mount target; never add a ledger item. Do not suppress unrelated guns/ammunition/armour or another layout. Turning the mode off returns old generation but does not silently undo any accepted ledger value.

Use the existing empirical-estimate model interface, with source/kernel and allocation-method/policy/weights/group metadata included in model inputs so the existing receipt preserves them. Use zero comparison tolerance for allocated mount models, so every nonexact target yields a proposal; an already-exact target need not be rewritten.

Acceptance ruling: an actual mixed case left18.964502663166t unmatched because the existing layout-armour difference was inside its5% tolerance and generated no proposal. For explicitly selected layouts only, existing gun and complete layout-armour models therefore also use zero comparison tolerance, recorded as `whole-battery-exact-alignment-v1` in comparison_policy. Their formulas/method identities and ammunition stay unchanged. They remain individually reviewed choices; the new mount cohort is still the atomic proportional group. This exposes a complete explicit alignment path without silently raising the physical accuracy claim or changing other layouts.

Adoption recomputes the immutable original project as before. When a submitted new allocation proposal belongs to a group, all still-pending recomputed proposals of that allocation group must be submitted together; otherwise structured rejection before any writes. Already-exact members have no pending proposal and do not block. Reject stale/forged identities and preserve unrelated conditions/base weights/positions/archive/old receipts. Do not trust client-supplied cohort metadata. No new API endpoint.

UI reuses the existing proposal table: explicit selection of one allocation group member selects its pending group as one declared choice, shows the cohort/policy, and deselection clears that group. Conflicting alternative models for an item must not leave an invalid half-selected group; server cohort validation remains decisive. Choice ownership must retire synchronously and permanently on changed project/revision/condition/request/run, dirty draft or request mismatch (including A→B→A).

## UI, reports and compatibility

Adapter/UI payload contract: each `battery_mass_allocation[]` record uses layout id; `values` has `source_mounts_t,legacy_mounts_t,allocated_total_t,selected_mounts_t`. `records[]` uses battery id, own `method_version`, `target_id,weight_t,share,allocated_mass_t,selected_mass_t`. The source total/allocations come from the pure allocator; selected values are independently read from explicit target IDs, even if allocation is unavailable. Mark adapter reading partial when independent selected facts are known. Provenance contains `source_method_version,allocation_policy,declared_source`. No numeric computation in the browser.

Generated model inputs include `method_version='plimsoll-battery-mount-allocation-v1'`, `allocation_group_id='battery-mounts:'+layout_id`, `allocation_policy='proportional-row-mounts-v1'`, `allocation_target_ids=[...]`, and source/weight details. UI obtains a pending cohort by matching the supported method version and allocation_group_id in proposal.model.inputs; server independently recomputes pending membership and never trusts client metadata. These keys are also persisted in the standard acceptance.inputs receipt.

An ordinary optional section with source and explicit layout selection, no autoselected layout, explains scope and product policy. Protect referenced layouts/batteries from silent deletion/repointing or show a precise invalid-reference error; no silent clearing or selecting another row. New family `design_balance.battery_mass_allocation[]`, per-layout stable ID and method family, exposed before unrelated hull/balance early returns. Shared workbench/report readings and ID/method gated comparison use server values only. Reports keep requested&&completed parent gate. Both languages name source total, old-row subtotal, allocated groups and selected ledger separately.

## Acceptance

Approximately 10–15 central scenarios, expanding only for an actual uncovered risk: differing selectors/shared cradle once, sum conservation, zero source/zero row, unknown weight/target, overlap rejection, absence compatibility, no old mount duplicates, readonly analysis, atomic subset rejection/exact member, valid whole-group adoption, stale/tampered proposal, other conditions/base and receipts preserved, and post-adoption balance + reload. Do not rerun original native matrices or unrelated full core suites. Parent independently runs the focused phase batch and a real API/worker/browser preview→adopt→recompute→reopen chain before acceptance.
