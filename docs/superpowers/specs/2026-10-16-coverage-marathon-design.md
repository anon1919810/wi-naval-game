# SPS Coverage Marathon Design

User authorization: autonomously design and execute a broad 2–3 hour goal, reduce repeated checks, and accept at stage boundaries. After the initial proposal the user explicitly expanded scope beyond armour. Start: **2026-10-15 18:03:47 UTC** (2026-10-16 02:03:47 Asia/Shanghai). Target handoff around 05:03 local; at least two hours of useful work, not repeated tests or idle padding.

## Outcome and workflow

Deliver three connected capabilities: fixed armour estimates, original SPS empirical cost readings, and a coherent import → edit → save/run → review/apply → rerun/read workflow. Existing battery layouts and their accepted changes remain intact. Use the existing Python/FastAPI/React architecture and existing atomic selected-condition proposal adoption. Codex owns contract, source review and stage acceptance; OpenCode implements bounded units. The user's autonomous-execution request replaces repeated design approval and per-edit test gates.

Checkpoints are approximately 45–60 minutes apart: kernel/integration, normal forms/migration, final combined acceptance. During implementation only syntax/import checks or focused diagnosis needed to proceed; do not run full regressions repeatedly. At stage ends run one relevant batch. Final full frontend run/build and core/backend batches occur once after production changes stabilize. Preserve all pre-existing dirty work; no reset/clean, new dependencies, commit/push/deploy, global UI restyling, fonts or artwork edits.

## Source and methods

Original `SpringSharpMono` 3.0.3032.29945, executable SHA256 `82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc`. Read-only recovered sources are outside the product repository under `C:/Users/杨睿/Documents/Codex/2026-10-14/reverse-engineer-anything/outputs/SpringSharp3b3-recovered/SpringSharpMono/`.

- ArmourControl.cs602–626: main/end/upper belts; 654–685: bulkhead/bulge; 694–725: seven deck selectors; 727–735: combined fore/aft conning mass.
- PerformanceControl.cs534–544: cost; EngineControl.cs924–933: load mass = displacement × .02 + magazine + bunker.
- Original mass convention: lengths ft, thickness in, mass long tons, INCH=.0185. All project declarations stay m/mm/metric tonnes. Cost outputs retain the original historical empirical million-pound/million-dollar labels and fixed 4:1 ratio, not live exchange rates or market prices.
- New method identities: `sps-3b3-fixed-armour-v1`, `sps-3b3-cost-v1`. Existing adapted/v1/v2 methods retain their identities and outputs when the new sections are absent.

## Fixed armour declaration

Optional `concept_design.fixed_armour`: array, max50, absent/null disabled. Each record has common keys `id`, `kind`, `system_id`, `item_id`, `source` and only the fields relevant to its kind. ID follows battery-layout ASCII `[A-Za-z0-9_.-]{1,80}` and is unique.

| kind | role | fields |
| --- | --- | --- |
| belt_main, belt_upper | same name | thickness_mm, length_m, height_m |
| belt_ends | belt_ends | thickness_mm, length_m, height_m |
| bulkhead | bulkhead | thickness_mm, length_m, height_m |
| bulge | armour_bulge | thickness_mm, length_m, height_m |
| deck | armour_deck | thickness_mm, coverage_index, forecastle_fraction, quarterdeck_fraction, forecastle_mm, quarterdeck_mm |
| conning | conning | thickness_mm (fore), aft_mm |

All engineering fields and bindings may be null in a saved draft. Wrong types, nonfinite numbers, negatives, fractional selectors, unknown keys/kinds and duplicate IDs/targets are rejected. Thickness 0..2000mm, extent 0..5000m, height 0..100m; deck selector0..6, fractions0..1 and known sum≤1. Do not silently clamp or fill nulls. Kind is one of the seven explicit choices; the editor may initially choose belt_main when adding an otherwise empty record.

Target must be an existing ledger item owned by the chosen system leaf; distinct from every other generated component, balance target and fixed-armour record. Existing selected mass is preserved until explicit adoption. When balance exists, target role must match the kind. A binding can remain incomplete in a draft, as for layout armour. Record removal removes only its declaration, not a ledger item or adopted mass. If a reader already includes this armour in another weight, expose the scope and let them split it; never deduct automatically.

Pure module `tools/plimsoll/fixed_armour.py` exports:

- `validate_configs(raw, path='$.concept_design.fixed_armour') -> list[dict]`, with `ArmourValidationError(ValueError)` carrying diagnostics.
- `evaluate(record, context, path='$.concept_design.fixed_armour') -> dict`.
- `METHOD_VERSION`, source identity/scope constants and `ROLE_BY_KIND`.

`context` is a dictionary of optional **canonical** declared/derived facts: `length_m`, `beam_m`, `co_waterplane`, `waterplane_area_m2`, `displacement_t`, `machinery_mass_t`, `ammunition_mass_t`. Its fact provenance must travel in the result. Returned object: `id`, `kind`, `method_version`, `status` (`available`/`unavailable`), `values` including `total_long_tons`/`mass_t` and relevant area/breakdown readings, `diagnostics`, `provenance`. Missing relevant facts produce null with a reason. Irrelevant missing context must not disable a simple plate or a known-zero result.

### Formulas and dependencies

- Main/upper belts: `[length_ft + ((hull_length_ft-length_ft)/hull_length_ft)^(1-Cwp) × beam_ft] × height_ft × thickness_in × .0185 ×2`. Positive armour requires known hull L/B/Cwp and length≤hull L; unsupported geometry returns unavailable rather than NaN. Belt_ends/bulkhead/bulge: `2 × length_ft × height_ft × thickness_in × .0185`.
- Deck: exactly ArmourControl.weightDeckCalc. With `a=fc`, `q=qd`, `C=Cwp`, `L=length_ft`, `B=beam_ft`, fore area `pow(2a,1-C²)×B×L×a/2`; quarter area `pow(q,1-C)×B×L×q/4 + (pow(q,1-C)+pow(2q,1-C))×B×L×q/4`. For selectors0..3 central area=`(waterplane_area_sqft-fore-quarter)×1.01`. For4 machinery box=`(machinery_lt×3/(disp_lt×.94)×.65×L+16)×(B+16)-256`; for5 use ammunition_lt instead of machinery_lt×3; for6 sum both. TotalLT=`(central_area×central_thickness_in + fore_area×fore_thickness_in + quarter_area×quarter_thickness_in)×.0185`. Do not merge coverage choices or create an actual armour mesh. Preserve the original positive box margin when a **known zero** selected component is read. Unknown is not that zero.
- Conning: `10 × (disp_lt/10000)^(2/3) × (fore_in+aft_in)`; returned fore/aft contributions may be separate, proposal is combined exactly once.
- No angle multiplier is invented: source belt inclination is used by warnings, not weight. No physical CG or dimensions are inferred for conning towers. Reject unsafe/negative/nonfinite arithmetic as unavailable; do not propose an impossible mass.

### Integration

Build minimal context from canonical hull and declared concept target. Obtain Cwp/waterplane from existing versioned proxy helpers, but do **not** require unrelated freeboard/stern/shaft facts for simple planar plates/conning. Existing `hull_proxy` requires more facts than these kernels: do not put all fixed-armour generation behind it.

Register available bound results as `concept_fixed_armour.<id>` using existing `_model`, independent method version, standard 5% comparison policy and original source scope. Expose `design_balance.fixed_armour` readings before early returns. Full declaration/context/provenance go in an allowed scalar `origin` JSON text; model inputs must respect existing flat receipt keys. Do not widen the receipt schema for nested data.

## Empirical cost

Optional `concept_design.cost`: null/absent disabled, object `{source: string|null}` enabled. No new ledger target and no cost adoption endpoint. Pure `tools/plimsoll/concept_cost.py` exports `METHOD_VERSION`, source constants and `evaluate(inputs, path='$.concept_design.cost')` where inputs contains optional canonical `displacement_t`, `hull_year`, `machinery_mass_t`, `ammunition_mass_t`, `fuel_mass_t`, `borne_mass_t`.

Read **selected-condition** role masses for machinery/ammunition/fuel and the existing selected bare-gun borne calculation. Never substitute proposed masses. Reuse explicit balance roles, but do not require known structural mass or unrelated performance assumptions. If needed masses/arrangement/year/target are missing, or relevant positive/unknown masses are unclassified or gun-role entries are not bound to a declared battery, return unavailable with diagnostic. Empty explicitly allocated roles can be zero. Cost stays independently available when unrelated physical stages fail.

Convert t→LT. LoadLT=`dispLT×.02 + ammoLT + fuelLT`; baseUSDmillion=`(dispLT-loadLT)×.00014 + machineryLT×.00056 + (borneLT×8)×.00042`. When hull_year+2>1914 multiply by `1+(hull_year+1.5-1914)/5.5`; otherwise1. GBPmillion=USDmillion/4. Source float32 branch boundary year1912/1913 must be tested. Unknown, overflow, nonpositive displacement, impossible negative light basis or unsupported year cannot become a plausible zero price.

Output `design_balance.cost` with own method/scope, status, inputs, values (`usd_million`,`gbp_million`,`load_long_tons`,`light_basis_long_tons`,`year_factor`, three cost contributions) and diagnostics/provenance. New feature absent → no added cost field, preserving old result shape. Show source currency convention near values and source basis, without pretending to estimate modern currency/inflation.

## Migration and ordinary UI

New imports create an independent unknown-mass fixed-armour target per enabled source region (including a known zero region if deliberately represented); never adopt a computed mass. Preserve exact original archive. Map only supported bounded known declarations; unsupported ones remain archived with a diagnostic and no dangling reference. Do not automatically enable cost or fabricate balance roles/assumptions on import.

Armour positional fields: main80/81/82, ends83/84/85, upper86/87/88, bulkhead89/90/91; bulge202/203/204; central deck107, fore207, quarter208, selector209; conning fore108/aft210; fractions fc26%, qd20%. Extents use the armour display scale, fractional deck lengths are percentages. Thickness follows armour scale; hull context remains canonical hull units. Records and targets must be created transactionally in Projection.build; preserve old user JSON.

Normal editor supports kind-specific fields, existing system/item bindings, add/remove, explicit unknowns, m/ft display and canonical mm/m. Focused `FixedArmourEditor.tsx`; reuse `declaredInputs.tsx`, `QuantityField`, existing ownership helpers. Component labels/roles join the existing proposal panel without broad refactors. Show returned armour readings and cost in `DesignBalanceResults.tsx` even when unrelated balance portions are unavailable.

The third workstream improves continuity: one compact current-revision review guide in the existing workbench, explaining missing bindings/inputs, save/run requirement and explicit adoption order; provide an openable synthetic combined example and a concise workflow document. Use existing run/proposal state, avoid new APIs or duplicate engineering calculations. Dirty/stale/current-condition protections must remain intact. No automatic choice of proposals, role assignment, balance convergence or mass replacement.

### Saved reports and comparisons

The third workstream also makes the new and existing concept components readable in the saved full report/print, rather than leaving nested results only in raw JSON. Share a small `ConceptComponentReadings` projection between the workbench and report stage, covering fixed armour, layout readings and cost with their own method/source/status. The full-report projection retains its existing parent gate: only requested/completed design_balance envelopes show numbers; unavailable/failed/canceled parent stages keep diagnostics and raw evidence. Workbench independent component readings continue their own explicit availability policy. Do not globally relax StageStatus gates.

Extend `reportMetrics` for explicit concept result paths, never by recursively treating metadata/inputs as outputs. Match fixed-armour/layout rows by unique ID, not array position; missing/duplicate IDs or unavailable child results are blocked. Long tons retain LT, cost retains original SPS currency units. Where both parent stages are completed and saved component methods match, comparison may show deltas. If the component method changed or is unavailable, no numeric delta. Absent optional features do not add empty report sections.

For new sections, `concept_design.evaluate` adds a `methods` dictionary only when fixed_armour or cost is declared: fixed_armour and cost own versions, and the layout version when applicable. The existing coordinator already copies `data.methods` into the stage's `method_versions`, allowing conservative report-comparison gating without changing global request identities or old absent-feature output. Do not alter `_analysis_request.VERSIONS` for this work.

## Acceptance boundaries

At each stage inspect changed production files once and run one relevant batch. Source numeric vectors are generated **once** with read-only original assembly methods; do not repeat large probes merely because a file changed. Cover seven deck selectors, all fixed kinds, scale equivalence, zero/unknown, invalid context, year1912/1913, selected vs proposed masses, global binding ownership and stale adoption. Separate complete original method execution from values assigned before GUI dependency failure.

Final combined browser/API/worker exercise: edit/save → run → select fixed armour and existing layout armour on distinct items → adopt/rerun → review the updated machinery/ammunition/fuel proposals and explicitly adopt a cost-driving component → read changed cost → change input/save and confirm old mass persists until re-review → reopen. Armour alone is not a direct cost input in the source formula: an armour-only adoption must not magically change selected machinery or cost; only the next explicit relevant adoption can do so. Preserve base ledger, another condition, source archive and existing layout declarations. Run one bounded frontend full suite/build, core/backend relevant batches, one quick current-source check; any failure may receive targeted repair/recheck. Prior iteration's accepted test records are historical, not evidence for new changes.

No whole-program parity, real-ship precision, protection rating, physical armour mesh/CG or modern cost claim. Frozen 191-observation inventory stays frozen; append a new coverage increment instead of inflating its denominator.

## Fourth increment: auxiliary weapons mass and migration

User requested broader coverage beyond armour. Add optional `concept_design.auxiliary_weapons` (max50 records), independent of gun batteries and fixed armour. Common fields `id`, `kind`, `system_id`, `item_id`, `source`; engineering fields `count`, `loads`, `location_index`, plus `diameter_mm`,`length_m` for `torpedo`, or `unit_mass_kg` for `mine`/`depth_charge`. All facts/bindings may be null in a draft. IDs/ownership follow fixed armour; global target uniqueness includes all generated components and the balance structure target. Integer count/loads 0..1000000, diameter0..2000mm, length0..100m, unit_mass0..100000kg; location torpedo0..8, others0..3; unknown keys/nonfinite/out-of-domain rejected. Changing kind retains identity/source/binding and only common legal fields. A bound target uses existing role `other` when balance is configured: combined weapon+mount mass is counted once in the selected ledger; do not relabel it as bare guns/ammunition or invent a new strength/space contribution.

Pure `tools/plimsoll/auxiliary_weapons.py` exports `METHOD_VERSION='sps-3b3-auxiliary-weapons-v1'`, `validate_configs(raw,path)` with `AuxiliaryValidationError`, `evaluate(record,context,path)`. Context only needs optional `hull_year` for active torpedoes (whole1800..2100); accept canonical fact dictionaries as other kernels. Result common `id/kind/method_version/status/values/diagnostics/provenance/origin`, values `weapon_long_tons`, `mount_long_tons`, `total_long_tons`, `mass_t`, `mount_factor`. Invalid/negative/nonfinite arithmetic unavailable, JSON always finite. Source WeaponControl.cs325..534 and original binary SHA as above. Origin full declaration/context as JSON text within existing receipt contract.

Recovered mass rules (do not port the source code/control graph): torpedo positive diameter/length/count gives `weaponLT=(pi*diameter_in^2*length_ft / ((max(1907-year,0)+25)*937) + .004*(year-1890))*count`. Known zero count, diameter or length gives known zero without unrelated missing facts; otherwise missing relevant input is unavailable. `loads` is the number of sets in the source torpedo description/area, NOT a weight multiplier: source's zero-to-one area mutation must not rewrite canonical input. Mine/DC `weaponLT=(count+loads)*unit_mass_lb/2240`: here loads means reload count, size means full unit mass (not explosive charge). Known-zero mass or known-zero total count may short-circuit; unknown reloads are not zero. Torpedo factors loc0/3/8=.25, loc1/2/4/5/6/7=1; mine loc0=.25,1/2/3=1; depth_charge loc0=.25,1/2=.5,3=10. `mountLT=weaponLT*factor`, total=sum. A positive weapon with unknown location cannot give a complete estimate. Keep source terms separate and propose combined total exactly once.

Integrate independent `concept_auxiliary.<id>` generated models before hull_proxy, expose `design_balance.auxiliary_weapons` before early returns; optional methods map adds `auxiliary_weapons` identity when declared, retaining old absent-feature output. Normal editor add/remove/binding, explicit unknown fields, translated location choices, kind-specific loads labels, unit conversion via QuantityField. Shared returned-reading report projection and reportMetrics keyed unique ID + child availability/method + parent gates. No client engineering formulas. No automatic adoption.

Migration source five rows: torpedo1 scale9/count77/loads179/diameter79/length182/location184; torpedo2 scale136/count78/loads180/diameter181/length183/location185; mine scale137/count186/loads187/size188/location189; depth_charge1 scale138/count190/loads192/size194/location196; depth_charge2 scale139/count191/loads193/size195/location197. Scale0 original in/ft or lb, scale1 mm/m or kg, using each weapon's own scale. Registry's legacy deck_gun names at190..197 actually refer to dcControl1/2 in MainForm.cs716..742: preserve archive/registry names, document alias instead of rewriting history. Active bounded records create independent unknown-mass target + owned leaf transactionally. Ordinary all-zero rows may be omitted; positive/unknown activity with unsupported facts remains archived with diagnostic and no dangling binding. Cost/balance remain disabled on import. Preserve exact source and old projects.

Source acceptance: add separate original assembly numeric vectors for all17 location choices, year boundary1907, zero/unknown and reload semantics; don't rerun armour vectors. Final combined sample includes three new kinds on distinct targets. Confirm source rows imported with scale equivalence, preserved archive, new proposals require explicit adoption, stale protection and other conditions unchanged. Scope covers mass only, not weapon space, arcs, explosive performance or full-program equivalence.

## Fifth increment: armour length and height review

Add optional `concept_design.armour_review` null/absent disabled, object `{source:string|null,belt_inclination_deg:number|null}` enabled; signed angle -89..89, unknown stays unknown. Read-only and no mass target/model/adoption. The same explicitly declared angle applies to main/end belts, as in the source. Pure `tools/plimsoll/armour_review.py` exports validate_config + `ReviewValidationError`, `evaluate(records,context,config,path)` + `METHOD_VERSION='sps-3b3-armour-review-v1'`. No dependency on new mass kernels beyond normalized declarations; no edits to fixed_armour.py/concept_cost.py.

Canonical context facts optional length_m,draught_m,freeboard_m,room_hull_ratio,composite_strength. Outputs `method_version/status/values/checks/diagnostics/provenance`, with finite/null values; each check has stable string id, nullable record_id, status pass/warning/unavailable, code,message,values. Do not turn missing/ambiguous records into passing checks or reject/prohibit mass adoption because a warning is raised. Aggregate status available only when all applicable checks readable; partial otherwise. Source sourcehash and explicit adapted input provenance accompany output. No physical protection/safety certificate.

ArmourControl.cs628..690 rules: per main belt `normal_length_ratio=length_m / hull_length_m /.65`. Combined main+ends length check only when exactly one of each kind is declared with known lengths; source warns if sum>hull length (independent of thickness). Missing/duplicate kind -> unavailable diagnostic; do not choose first or sum arbitrary regions. For each main/end belt, max height `(draught_m+freeboard_m)/cos(abs(inclination_deg)*pi/180) + .02*.3048`; warn only when known thickness>0 and height>limit; known thickness0 passes this check without unrelated geometry (source short circuit). Upper belt limit freeboard_m+.01*.3048, warn only thickness>0. Bulge/bulkhead limit draught_m+freeboard_m, compare height even if thickness0 (as source). Deck/conning have no such checks and create no fake checks.

MainForm.cs1900..1919 displays minimum engine/magazine length only if composite strength is known and >=.5; source NaN/lower uses default text. Here `minimum_main_belt_length_m=hull_length_m*.65*room_hull_ratio + .01*.3048` only with known positive hull length, known nonnegative room ratio and known strength>=.5. Otherwise unavailable, keep explicit dependency diagnostics. Each main belt can compare declared length against that minimum; warning if shorter. Both this formula and existing room ratio are empirical, no spatial engine arrangement reconstruction. `values.minimum_main_belt_length_m` plus per-record normal_length_ratio, maximum_height_m/declared_height_m/declared_length_m as relevant. Per-check/source method version gates in report comparisons; don't recursively compare inputs as outputs.

Integration: emit independent height/normal-length readings early before unrelated hull_proxy failures using declared project hull dimensions and concept freeboard. Minimum length may remain unavailable until existing performance output provides space.hull_ratio and strength composite; compute once again at final return to supply those returned values, never substitute proposed masses. Expose `design_balance.armour_review` + methods.armour_review when optional configured; absent old results unchanged. Import known bounded source angle201 into armour_review with declared source when fixed records exist, unsupported angle remains archived + diagnostic/null (cost and balance remain disabled). Normal editor enable/source/signed inclination with source scope note; shared normal/saved report prints checks/status/reasons. No client formulas. Add explicit comparison metric for singleton minimum length only when review status supports it and matching own/parent methods; per-record metrics keyed by check id/record_id if implemented, never array position.

Acceptance: angle changes height limit but not mass; negative/positive angle symmetric; 0-degree metre/foot margin anchor, upper/bulge/bulkhead distinct rules, main+ends duplicate/missing guard, thickness0 short circuit, unknown geometry, minimum length strength .499/.5 boundary and selected-vs-proposed conditions. Source method vector probe may add a separate small maxBeltHeight/beltCover matrix without rerunning the original armour mass matrix; minimum-length formula has a separately stated source-expression check if complete GUI method cannot run. Same phase-end batching as above.
