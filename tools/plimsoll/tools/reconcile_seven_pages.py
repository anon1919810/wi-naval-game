"""Reconcile the frozen 191-field SPS observation inventory with core bindings.

This is an evidence map, not a claim that every observed historical input is
known for Queen Mary. In particular, a reusable adapter and a populated case
are distinct outcomes, and an approved exclusion is not evidence of
replacement.

The generator is a pure function of the committed proposal file, the frozen
inventory and the review policy declared below, so two consecutive runs produce
byte-identical output. It rewrites both the main proposal and the versioned
reverse-engineering gun-editor supplement.
"""

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/plimsoll-1.0/evidence"
PATH = EVIDENCE / "seven-page-binding-proposal.json"
SUPPLEMENT_PATH = EVIDENCE / "gun-editor-source-supplement.json"

POLICY_PHASE = "coverage_repair_2026_10_15"
SCHEMA = "plimsoll-seven-page-binding-proposal-2"
SUPERSEDED_SCHEMA = "plimsoll-seven-page-binding-proposal-1"
RECORD_COUNT = 191

SOURCE = {
    "assembly": "SpringSharpMono",
    "assembly_version": "3.0.3032.29945",
    "executable_sha256": "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc",
    "recovered_root": "outputs/SpringSharp3b3-recovered/SpringSharpMono",
    "recovery_basis": "ILSpy/REA decompilation plus per-method CIL byte verification in the "
                      "preceding reverse-engineering round; this file transcribes recovered C# "
                      "and does not execute the original program.",
    "scope_limit": "Every SpringSharp statement below is valid for this 3b3 binary only.",
}

SEMANTIC_VOCABULARY = {
    "scope_excluded_not_a_replacement":
        "Excluded by the approved scope of the earlier round. An exclusion records that "
        "Plimsoll does not do this; it is never counted as replacement coverage.",
    "presentation_phase_historical_not_retested":
        "Deferred in the 2026-09 core-only round. The deferred phase is recorded as "
        "history; today's web presentation was not re-tested for this record.",
    "same_quantity_different_derivation":
        "Same physical quantity in the same units, obtained by Plimsoll's own method or "
        "from declared data rather than the SpringSharp formula.",
    "same_concept_canonical_unit_variant":
        "Same concept expressed only in the Plimsoll canonical unit; the SpringSharp "
        "display-unit control has no separate implementation.",
    "related_measure_not_equivalent":
        "Adjacent measure. Related topic, different definition, dimension or domain; the "
        "Plimsoll value must never stand in for the SpringSharp field.",
    "different_semantics_unimplemented":
        "The SpringSharp control means something else entirely and that meaning is not "
        "implemented in Plimsoll.",
    "method_known_not_implemented":
        "The SpringSharp method is now recovered and known, but Plimsoll ships no "
        "versioned parity implementation and no validated comparison.",
    "source_expanded_not_implemented":
        "The record was a placeholder for an unobserved editor; recovered source now "
        "describes it in a versioned supplement, and the estimate chain is still absent.",
    "declaration_or_ledger_binding_only":
        "The binding reads a declared project fact or the selected loading ledger. It "
        "records ownership of a number, not a computation comparable to SpringSharp.",
    "unresolved_no_mapping":
        "No verified mapping is established for this observation.",
}

# Semantic relation wins over the status-derived default. Keys are frozen record IDs.
SEMANTIC_OVERRIDES = {
    "hull.derived.length_beam":
        "related_measure_not_equivalent",
    "performance.metacentric_height":
        "related_measure_not_equivalent",
    "guns.weights.broadside_lb":
        "related_measure_not_equivalent",
    "guns.weights.broadside_kg":
        "related_measure_not_equivalent",
    "guns.weights.armour":
        "declaration_or_ledger_binding_only",
    "armour.other.guns":
        "declaration_or_ledger_binding_only",
    "armour.settings.thickness_unit":
        "same_concept_canonical_unit_variant",
    "hull.dimensions.display_unit":
        "same_concept_canonical_unit_variant",
    "engines.speed_power.max_wave_power_pct":
        "related_measure_not_equivalent",
    "engines.speed_power.cruise_wave_power_pct":
        "related_measure_not_equivalent",
    "freeboard.ends.average":
        "same_quantity_different_derivation",
}

# Groups whose existing binding is a declared fact, ledger projection or preference.
DECLARATION_GROUPS = {
    "hull.ship", "hull.dimensions", "hull.displacement", "freeboard.deck_form",
    "freeboard.ends", "guns.battery_selection", "guns.weights",
    "armour.belts_bulkheads", "armour.bulkhead_geometry", "armour.other",
    "armour.settings", "engines.configuration", "engines.weights",
    "performance.displacement",
}
# Groups whose existing binding computes a quantity of the same kind by another method.
DERIVED_GROUPS = {"hull.derived", "engines.speed_power", "performance.stability_seakeeping"}

# Obsolete bindings withdrawn in this policy phase, retained as history only.
REJECTED_BINDINGS = {
    "performance.set_trim": [
        {"kind": "result", "path": "$.stages.equilibrium.data.trim_deg",
         "reason": "Solved longitudinal trim in degrees is a free-equilibrium output, not the "
                   "SpringSharp 'Set Trim' 0..100 steadiness adjustment."},
        {"kind": "result",
         "path": "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_t_m",
         "reason": "Required longitudinal moment for a declared target trim angle is an "
                   "independent physical study, not the SpringSharp steadiness adjustment."},
        {"kind": "result",
         "path": "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_kNm",
         "reason": "Same independent study in kN-m; listing it as the SpringSharp 'Set Trim' "
                   "result asserted a semantic equivalence that does not hold."},
    ],
    "performance.steadiness": [
        {"kind": "canonical_input", "path": "$.hull.roll_gyration_coeff",
         "reason": "The roll radius-of-gyration ratio feeds the physical small-angle roll "
                   "period; it is not an input to a 0..100 steadiness score."},
        {"kind": "result", "path": "$.stages.hydrostatics.data.values.gm_t_m",
         "reason": "Physical metacentric height in metres is not the SpringSharp steadiness "
                   "score."},
        {"kind": "result", "path": "$.stages.hydrostatics.data.loaded_roll.period_s",
         "reason": "Small-angle roll period in seconds is a time, not a 0..100 gunnery "
                   "steadiness score; the two must never complete each other's status."},
    ],
}

# Where the withdrawn semantics actually live in Plimsoll, kept explicitly separate.
RELATED_STUDIES = {
    "performance.set_trim": [
        {"plimsoll_path": "$.stages.equilibrium.data.trim_deg",
         "what_it_is": "Free-solved longitudinal trim in degrees for the requested condition.",
         "relation": "different_measure_not_sps_set_trim"},
        {"plimsoll_path": "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_kNm",
         "what_it_is": "Longitudinal moment required to reach a declared target trim angle "
                       "(tools/plimsoll/stability.py trim_target_study).",
         "relation": "independent_study_not_sps_set_trim"},
    ],
    "performance.steadiness": [
        {"plimsoll_path": "$.stages.hydrostatics.data.loaded_roll.period_s",
         "what_it_is": "Small-angle natural roll period in seconds for the selected loading; "
                       "needs positive selected GM and a sourced gyration ratio.",
         "relation": "physical_roll_period_not_sps_steadiness_score"},
        {"plimsoll_path": "$.stages.hydrostatics.data.values.gm_t_m",
         "what_it_is": "Physical metacentric height in metres.",
         "relation": "physical_gm_not_sps_steadiness_score"},
    ],
}

# Precise recovered evidence for the records this phase re-audited.
SOURCE_EVIDENCE = {
    "performance.set_trim": {
        "recovered_control": "PerformanceControl.cs:239 trimBoxTextChanged on the 'Trim' text box, "
                             "mirrored by trimBarScroll (:259) into trimBar.",
        "sps_units": "integer 0..100. The guard at :244/:252 tests 0..100 while the status "
                     "string reads 'Trim must be 1 to 100'; 0 is accepted by the code.",
        "sps_method": "steadiness = main.integerCheck(trimBox.Text); trimBar.Value = steadiness; "
                      "stabilityCalc() then applies stabilityAdj = stability * ((50 - steadiness) "
                      "/ 150 + 1) at :343, and seaboatCalc() applies "
                      "steadinessAdj = min(steadiness * seaboat, 100) at :419.",
        "sps_meaning": "An empirical 0..100 steadiness adjustment that scales the empirical "
                       "stability score, the gunnery-platform factor and the seakeeping score. "
                       "It is never converted to degrees and is not a longitudinal trim angle.",
        "plimsoll_interface": "$.stages.equilibrium.data.trim_deg and "
                              "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_kNm",
        "coverage": "No Plimsoll control reproduces the SpringSharp 0..100 steadiness "
                    "adjustment. The longitudinal study is retained as an independent physical "
                    "study and must not be reported as this control.",
    },
    "performance.steadiness": {
        "recovered_control": "PerformanceControl.cs:403 seaboatCalc, displayed in steadinessBox "
                             "at :420-422.",
        "sps_units": "0..100 score with 'n0' formatting. The separate rollPeriod at :368 is in "
                     "seconds; the two values are different quantities with different units.",
        "sps_method": "steadinessAdj = Math.Min(steadiness * seaboat, 100) at :419; bands are "
                      ">=69.5 steady, <30 unsteady (:423/:429); seakeeping = "
                      "seaboat * steadinessAdj / 50 when steadinessAdj < 50, else seaboat "
                      "(:441-:448).",
        "sps_meaning": "A gunnery-platform steadiness rating that multiplies a seaboat "
                       "(seakeeping) factor. It is a score, not a time and not a period.",
        "plimsoll_interface": "$.stages.hydrostatics.data.loaded_roll.period_s and "
                              "$.stages.hydrostatics.data.values.gm_t_m",
        "coverage": "Plimsoll has no 0..100 steadiness score. Its roll period is a physical "
                    "period in seconds and must not be used to complete this record; the SPS "
                    "steadiness, seaboat and roll-period concepts stay separate.",
    },
    "hull.derived.natural_speed": {
        "recovered_control": "HullControl.cs:1345 coSharpCalc, displayed in speedNaturalBox.",
        "sps_units": "knots as sqrt(feet): speedNatural = sqrt(lengthEffect) with lengthEffect "
                     "expressed in feet.",
        "sps_method": "coSharp = 0.4 * (beamBulges / length * 6)^(1/3) * sqrt(block / 0.52) at "
                      ":1347; lengthEffect = length + beamBulges / coSharp when "
                      "free.stern.SelectedIndex == 2, length + 0.5 * beamBulges / coSharp when "
                      "== 1, else length (:1350-:1361); speedNatural = sqrt(lengthEffect) at :1362.",
        "sps_meaning": "A stern-conditioned effective-length square root. It depends on the "
                       "stern selection, the beam at the bulges and the block coefficient, so it "
                       "is not a function of LWL alone.",
        "plimsoll_interface": "tools/plimsoll/hull.py natural_speed(): hull_speed_kn is the "
                              "sourced Froude wave speed and natural_speed_kn is a legacy "
                              "independent 1.09 * sqrt(L_ft) heuristic. Neither is a versioned "
                              "SPS parity method, and no coordinator stage exposes either.",
        "coverage": "The method is now known, so the old 'method undefined' label is withdrawn. "
                    "No implemented parity claim is made until a versioned method exists and has "
                    "been validated against the original assembly.",
    },
    "guns.battery_selection.editor_fields_unknown": {
        "recovered_control": "SpringSharpMono/GunControl.cs, the per-battery gun editor; the "
                             "control inventory is transcribed in the supplement.",
        "plimsoll_interface": "$.systems.weapons.<battery_id>.installed_guns / installed_count / "
                              "rounds_per_gun / broadside_guns as declared inputs that do drive "
                              "the declared mass models (systems.py _declared_count, :110-130; "
                              "page_rows.py weapons_page_rows; GunsEditor.tsx), plus "
                              "facts.projectile_mass_kg, facts.calibre_m, facts.mount_count and "
                              "the non-additive rotating_armour_component declaration.",
        "coverage": "See the supplement. The declared inputs exist and are live; what is missing "
                    "is the estimating chain: Plimsoll never derives a gun, mount, shell, "
                    "magazine or mount-armour mass from calibre, barrel length, design year, gun "
                    "type, mount type or the two-group raised/on-deck/below-deck layout.",
        "supplement_path": "docs/plimsoll-1.0/evidence/gun-editor-source-supplement.json",
    },
}

# Active metadata for the disputed records, rewritten to match the recovered
# semantics. The superseded wording is kept under historical metadata only.
ACTIVE_METADATA = {
    "performance.set_trim": {
        "limitation": "The recovered SpringSharp 'Set Trim' control is a 0..100 empirical "
                      "steadiness adjustment, not a trim angle. Plimsoll implements no such "
                      "adjustment, so this record has no active stage, condition, provenance or "
                      "result requirement. The equilibrium trim study remains an independent "
                      "physical study listed under related_plimsoll_studies.",
        "required_stages": [],
        "provenance_bindings": [],
        "canonical_inputs": [],
        "evidence": ["PerformanceControl.cs:239,259,343,419", "tools/plimsoll/stability.py"],
    },
    "performance.steadiness": {
        "limitation": "The recovered SpringSharp 'Steadiness' output is the 0..100 score "
                      "min(steadiness x seaboat, 100); the separate roll period in that program "
                      "is in seconds. Plimsoll computes neither the SPS score nor any stand-in "
                      "for it, so this record has no active stage, condition, provenance or "
                      "result requirement. loaded_roll.period_s stays a physical roll period and "
                      "must not complete this record.",
        "required_stages": [],
        "provenance_bindings": [],
        "canonical_inputs": [],
        "evidence": ["PerformanceControl.cs:368,403,419",
                     "$.stages.hydrostatics.data.loaded_roll.period_s"],
    },
    "hull.derived.natural_speed": {
        "limitation": "The recovered SpringSharp method is sqrt(lengthEffect), conditioned on "
                      "the stern selection, the beam at the bulges and the block coefficient. "
                      "Plimsoll ships no versioned parity method and has validated none, so no "
                      "stage, condition, provenance or result is claimed here. The legacy "
                      "1.09*sqrt(L_ft) helper stays an independent heuristic.",
        "required_stages": [],
        "provenance_bindings": [],
        "canonical_inputs": [],
        "evidence": ["HullControl.cs:1345-1362", "tools/plimsoll/hull.py natural_speed"],
    },
}

# Superseded active metadata, preserved verbatim as history.
HISTORICAL_METADATA = {
    "performance.set_trim": {
        "limitation": "Solved trim is available, but the stable request has no user trim target/"
                      "constraint semantic. Initial guesses must not impersonate a constraint.",
        "required_condition": None,
        "required_stages": ["equilibrium"],
        "provenance_bindings": [{"path": "$.stages.equilibrium.status"},
                                {"path": "$.stages.equilibrium.diagnostics[*]"}],
        "evidence": ["analysis-api.md", "project-extensions.md"],
    },
    "performance.steadiness": {
        "limitation": "L0 design roll_period_s exists, but no selected-loading roll-period result "
                      "combines selected GM with the declared gyration fact. Do not relabel L0 as "
                      "loaded performance.",
        "required_condition": None,
        "required_stages": ["hydrostatics"],
        "provenance_bindings": [{"path": "$.stages.hydrostatics.status"},
                                {"path": "$.stages.hydrostatics.diagnostics[*]"}],
        "canonical_inputs": [{"path": "$.hull.roll_gyration_coeff"}],
        "evidence": ["analysis-api.md", "project-extensions.md"],
    },
    "hull.derived.natural_speed": {
        "limitation": "Reviewed hull.natural_speed exists, but no coordinator stage exposes its "
                      "sourced Froude and legacy 1.09√Lft outputs.",
        "required_condition": None,
        "required_stages": [],
        "provenance_bindings": [],
        "canonical_inputs": [{"path": "$.hull.lwl_m"}],
        "evidence": ["hull.natural_speed"],
    },
}

AUDITED_THIS_REVIEW = {
    "performance.set_trim", "performance.steadiness", "hull.derived.natural_speed",
    "guns.battery_selection.editor_fields_unknown",
}


def review(record):
    """Return the reconciled (status, result path, limitation) for one record."""
    identity = record["id"]
    old = record.get("pre_reconciliation_disposition", record["current_disposition"])
    if old == "accepted_exclusion":
        return "excluded_by_approved_scope", None, \
            "User-approved non-calculation control or formula exclusion; an exclusion is not " \
            "evidence of SpringSharp replacement."
    if "presentation_deferred" in old or old == "presentation_deferred":
        return "presentation_deferred_historical_phase", None, \
            "Deferred in the 2026-09 core-only round and recorded as history. Today's web " \
            "presentation was not re-tested for this record, so no UI completion is claimed."
    if identity == "hull.derived.natural_speed":
        return "method_known_parity_not_implemented", None, \
            "SPS natural speed is sqrt(lengthEffect), stern-conditioned and computed in " \
            "HullControl.coSharpCalc. The method is known; no versioned Plimsoll parity exists " \
            "and none is validated."
    if identity == "guns.battery_selection.editor_fields_unknown":
        return "source_expanded_not_implemented", None, \
            "The editor was absent from the seven-page capture. Recovered GunControl.cs now " \
            "describes it in a versioned supplement; the estimating chain is still unimplemented."
    if identity == "performance.set_trim":
        return "unavailable_semantic_mismatch", None, \
            "SPS 'Set Trim' is a 0..100 empirical steadiness adjustment " \
            "(PerformanceControl.cs:239,259,343,419), not a target trim angle. The Plimsoll " \
            "longitudinal constraint study stays as an independent physical study."
    if identity == "performance.steadiness":
        return "unavailable_semantic_mismatch", None, \
            "SPS steadinessAdj = min(steadiness * seaboat, 100) is a 0..100 gunnery score " \
            "(PerformanceControl.cs:419); loaded_roll.period_s is a roll period in seconds. " \
            "Different quantity, different unit."
    if identity == "hull.derived.length_beam":
        return "implemented", "$.stages.l0.data.hull_ratios.design_lwl_over_beam", \
            "Plimsoll computes LWL/beam; SPS computes length/beamBulges (HullControl.cs:1348). " \
            "Related ratio with a different denominator."
    if identity.startswith("freeboard.segments."):
        segment = identity.split(".")[2]
        field = identity.rsplit(".", 1)[-1]
        key = {"forward": "fore_clearance_m", "aft": "aft_clearance_m", "length_pct": "length_pct"}[field]
        return "implemented_input_conditional", f"$.stages.deck.data.profile.segments[id={segment}].{key}", \
            "Only explicitly declared deck endpoints are evaluated; Queen Mary fixture has one centreline segment, not four historical SPS segments."
    if identity.startswith("guns.weights."):
        field = identity.rsplit(".", 1)[-1]
        if field == "armour":
            return "implemented_input_conditional", "$.stages.systems.data.page_rows[weapons.main].rotating_armour_component.rotating_armour_mass_t", \
                "Optional sourced subcomponent of selected mount mass; never added to displacement. Queen Mary has no independent component source."
        if field in {"guns", "mounts", "magazine"}:
            row = "ammunition" if field == "magazine" else field
            return "implemented", f"$.stages.systems.data.page_rows[weapons.<battery_id>].rows[row={row}].weight_t", \
                "Selected ledger projection; ammunition outfit is not fired broadside mass."
        if field in {"broadside_kg", "broadside_lb"}:
            unit = "kg" if field.endswith("kg") else "lb"
            return "implemented_input_conditional", f"$.stages.systems.data.page_rows[weapons.<battery_id>].broadside.mass_{unit}", \
                "Requires sourced projectile mass and declared broadside gun count."
    if identity.startswith("weapons.torpedoes.") or identity.startswith("weapons.mines.") or identity.startswith("weapons.depth_charge"):
        field = identity.rsplit(".", 1)[-1]
        typed = {"number": "tubes" if identity.startswith("weapons.torpedoes.") else "count",
                 "diameter": "diameter_mm", "length": "length_m", "sets": "sets",
                 "arrangement": "arrangement", "reloads": "reloads", "unit_weight": "unit_weight_kg"}
        if field.endswith("unit"):
            return "implemented_canonical_unit", None, "Torpedo diameter is millimetres and store unit weight kilograms; display-unit control is deferred."
        if field in {"weight", "total_weight"}:
            return "implemented_input_conditional", "$.stages.systems.data.page_rows[weapons.torpedo].rows[row=<store_id>].weight_t", \
                "Mass is linked from selected ledger only; absent bindings remain null."
        return "implemented_input_conditional", \
            f"$.stages.systems.data.page_rows[weapons.torpedo].rows[row=<store_id>].typed.{typed.get(field, field)}", \
            "Repeated, validated typed declarations are supported; historical unknown values remain null."
    if identity.startswith("weapons.misc_weight."):
        return "implemented_input_conditional", "$.stages.systems.data.page_rows[weapons.misc_weight].rows[row=<zone_id>].weight_t", \
            "Five positional zones exist; Queen Mary has no sourced allocation, so all five masses are null."
    if identity == "armour.settings.minimum_main_belt_length":
        return "implemented_input_conditional", "$.stages.systems.data.page_rows[armour.fixed].minimum_main_belt.length_m", \
            "Independent compartment-envelope engineering estimate; Queen Mary protected extents are not historically verified."
    if identity.startswith("armour.belts."):
        parts = identity.split(".")
        zone, field = parts[2], parts[-1]
        if zone == "total_weight":
            return "implemented_input_conditional", "$.stages.systems.data.page_rows[armour.fixed].groups[belts].weight_t", \
                "Only explicitly grouped, nonoverlapping declared belt rows are summed."
        if zone in {"main", "upper", "ends", "torpedo_bulkhead", "bulge"} and field in {"weight", "thickness", "length"}:
            key = {"weight": "weight_t", "thickness": "thickness_mm", "length": "length_m"}[field]
            return "implemented_input_conditional", f"$.stages.systems.data.page_rows[armour.fixed].rows[row={zone}].{key}", \
                "Selected ledger weight/declared thickness; row or length remains null without sourced inputs."
        if field == "height":
            return "implemented_input_conditional", f"$.stages.systems.data.page_rows[armour.fixed].rows[row={zone}].typed.height_m", \
                "Typed height must be explicitly supplied; Queen Mary has no sourced height declaration."
        return "unavailable_case_or_component_gap", None, "No distinct declared row or dimension for this SPS field; no inferred geometry or mass."
    if identity == "armour.conning.total":
        return "implemented", "$.stages.systems.data.page_rows[armour.fixed].rows[row=conning_tower].weight_t", \
            "Combined conning-tower ledger mass; fore/aft split unavailable."
    if identity == "armour.other.guns":
        return "implemented_input_conditional", "$.stages.systems.data.page_rows[weapons.main].rotating_armour_component.rotating_armour_mass_t", \
            "Read-only view of the same optional mount subcomponent; not a second fixed-armour ledger mass. Queen Mary remains unknown."
    if identity.startswith("armour.bulkhead_geometry."):
        field = {"main_belt_incline": "inclination_deg", "type": "construction_type",
                 "beam_between": "beam_between_m"}[identity.rsplit(".", 1)[-1]]
        return "implemented_input_conditional", f"$.stages.systems.data.page_rows[armour.fixed].rows[row=torpedo_bulkhead].typed.{field}", \
            "Optional typed declaration; no historical value is inferred for Queen Mary."
    if identity.startswith("armour.deck."):
        field = identity.rsplit(".", 1)[-1]
        if field == "total":
            return "implemented_input_conditional", "$.stages.systems.data.page_rows[armour.fixed].groups[deck].weight_t", \
                "Sum of explicitly grouped nonoverlapping deck rows."
        if field == "coverage":
            return "implemented_input_conditional", "$.stages.systems.data.deck_coverage.coverage_pct", \
                "100 × declared covered plan area / declared reference plan area; this is an explicit Plimsoll study, not a verified SPS formula. Queen Mary inputs remain unknown."
        return "implemented_input_conditional", f"$.stages.systems.data.page_rows[armour.fixed].rows[row=deck_{field}].weight_t", \
            "Requires separate sourced ledger row; Queen Mary currently supplies only one combined armour-deck row."
    if identity.startswith("armour.conning."):
        field = identity.rsplit(".", 1)[-1]
        return "implemented_input_conditional", f"$.stages.systems.data.page_rows[armour.fixed].rows[row=conning_{field}].weight_t", \
            "Requires separate sourced forward/aft ledger items; Queen Mary only has combined mass."
    if identity.startswith("armour.") and old == "armour_group_adapter_required":
        return "unavailable_case_or_component_gap", None, "The declared armour ledger does not identify this SPS subcomponent separately."
    if identity == "engines.speed_power.lock_power":
        return "implemented_input_conditional", "$.stages.resistance.data.fixed_power_study.speed_kn", \
            "Bracketed fixed-power request; outside method-valid bounds is unavailable/nonprimary."
    if identity.endswith("wave_power_pct"):
        return "implemented_input_conditional", "$.stages.resistance.data.rows[speed_kn=<x>].components.wave_fraction_pct", \
            "Taylor residual share or Holtrop RW share; these definitions are explicitly different."
    if identity == "engines.weights.pct_coal":
        return "implemented_input_conditional", "$.stages.propulsion.data.engine_page.coal_share_of_declared_fuel_pct", \
            "Selected coal/(coal+oil); unknown when fuel bindings incomplete."
    if identity == "engines.weights.load":
        return "implemented_input_conditional", "$.stages.propulsion.data.engine_page.variable_load_t", \
            "Only explicitly named mutually exclusive selected loading groups are summed."
    if identity in {"engines.configuration.energy_source", "engines.configuration.transmission"}:
        field = identity.rsplit(".", 1)[-1]
        return "implemented_input_conditional", f"$.stages.propulsion.data.engine_page.{field}", \
            "Explicit sourced text fact; absent input remains null."
    if old.startswith("bound") or old == "core_inputs_bound_presentation_deferred":
        path = next((entry.get("path") for entry in record.get("result_bindings", []) if entry.get("path")), None)
        return "existing_binding_conditioned", path, "Existing binding retained; case values and method applicability are assessed separately."
    return "unavailable_unresolved", None, "No verified computation binding for this observation."


def semantic_relation(record, status):
    identity = record["id"]
    if identity in SEMANTIC_OVERRIDES:
        return SEMANTIC_OVERRIDES[identity]
    if status == "excluded_by_approved_scope":
        return "scope_excluded_not_a_replacement"
    if status == "presentation_deferred_historical_phase":
        return "presentation_phase_historical_not_retested"
    if status == "unavailable_semantic_mismatch":
        return "different_semantics_unimplemented"
    if status == "method_known_parity_not_implemented":
        return "method_known_not_implemented"
    if status == "source_expanded_not_implemented":
        return "source_expanded_not_implemented"
    if status in {"unavailable_case_or_component_gap", "unobserved_source_limit",
                  "unavailable_unresolved"}:
        return "unresolved_no_mapping"
    if status == "implemented_canonical_unit":
        return "same_concept_canonical_unit_variant"
    if status.startswith("implemented"):
        return "same_quantity_different_derivation"
    if record["group"] in DECLARATION_GROUPS:
        return "declaration_or_ledger_binding_only"
    if record["group"] in DERIVED_GROUPS:
        return "same_quantity_different_derivation"
    return "related_measure_not_equivalent"


def verification(record, status):
    identity = record["id"]
    relation = semantic_relation(record, status)
    if identity in AUDITED_THIS_REVIEW:
        state = "re_audited_against_recovered_source_2026_10_15"
        basis = "Recovered SpringSharpMono C# (%s %s, exe sha256 %s) and the current Plimsoll " \
                "binding path were compared field by field." % (
                    SOURCE["assembly"], SOURCE["assembly_version"], SOURCE["executable_sha256"][:12])
        note = "Semantics only. No original-assembly behaviour was executed for this record in " \
               "this review, so no numeric parity is claimed."
    elif status == "excluded_by_approved_scope":
        state = "scope_excluded_not_verified"
        basis = "The approved scope of the earlier round."
        note = "An approved exclusion is not evidence of replacement and is never counted as " \
               "covered SpringSharp functionality."
    else:
        state = "not_re_audited_in_this_review"
        basis = "This phase re-audited only the disputed records and the previously unobserved " \
                "gun editor against recovered source."
        note = "Other fields of this record keep their earlier review. They are not re-verified " \
               "here, and an existing adapter or binding is not evidence of SpringSharp " \
               "equivalence."
    return {
        "state": state,
        "basis": basis,
        "note": note,
        "sps_equivalence_claim": False,
        "sps_equivalence_evidence": None,
        "executable_equivalence_run": False,
    }


def _control(identity, label, control, direction, units, default, handler, plimsoll, support,
             relation, coverage, audit_state, note):
    return {
        "id": identity,
        "sps_label": label,
        "sps_control": control,
        "direction": direction,
        "sps_units": units,
        "sps_default": default,
        "sps_handler": handler,
        "plimsoll_interface": plimsoll,
        "plimsoll_support": support,
        "semantic_relation": relation,
        "coverage": coverage,
        "plimsoll_audit_state": audit_state,
        "coverage_note": note,
    }


# Coverage vocabulary for the Plimsoll side of the comparison.
DECLARED_INPUT_NO_ESTIMATION = "declared_input_no_estimation"
DECLARED_FACT_UNREAD = "declared_fact_not_read_by_current_computation"
DERIVED_READOUT = "derived_readout_from_declared_inputs"
NO_DECLARED_FIELD = "no_field_in_enumerated_weapon_contract"
NOT_AN_SPS_INPUT = "not_a_user_input_in_sps"

READ = "verified_against_current_source_2026_10_15"
NOT_REAUDITED = "not_reaudited"

# Where the Plimsoll weapon contract and its computation live.
CONTRACT_EVIDENCE = ("tools/plimsoll/project_extensions.py WEAPON_FIELDS enumerates every "
                     "optional declared weapons fact; a field absent from that table cannot be "
                     "declared at all, which makes absence verifiable for declared inputs.")
ARMOUR_CONTRACT_EVIDENCE = (
    "tools/plimsoll/project_extensions.py PAGE_ROW_TYPED_FIELDS enumerates every allowed "
    "typed armour row field read in this review; a field absent from that table cannot be "
    "declared, which makes absence verifiable for declared inputs.")

AUDITED = (
    "Plimsoll side read from the current source on 2026-10-15: project_extensions.py "
    "WEAPON_FIELDS, systems.py _declared_count, page_rows.py weapons_page_rows and "
    "web/frontend/src/components/GunsEditor.tsx.")


def gun_editor_supplement():
    """Versioned transcription of the recovered SpringSharp gun editor.

    Every entry names the recovered control, its units, the method that consumes
    it, the closest Plimsoll interface and the honest coverage state. Absence of
    a Plimsoll field is asserted only where the declared weapons contract
    enumerates every permitted field; everywhere else the entry says the Plimsoll
    side was not re-audited rather than claiming a gap that was not looked for.
    """
    no_chain = "No Plimsoll estimating chain: "
    controls = [
        _control(
            "gun.barrels", "No. of Barrels:", "barrelsBox (TextBox, int)", "input",
            "count of barrels", "0", "barrelsEnter :403",
            "$.systems.weapons.<battery_id>.installed_guns (declared installed gun count; the "
            "generic installed_count is also accepted) and "
            "$.stages.systems.data.page_rows[weapons.<battery_id>].installed_guns.",
            "The declared count exists and is live: GunsEditor.tsx edits installed_guns / "
            "installed_count / rounds_per_gun; systems.py _declared_count (74) accepts "
            "installed_count, installed_guns or installed_tubes and drives the mass model; "
            "systems.py:240 reports row.installed_count; page_rows.py:769 reports "
            "installed_guns; test_gun-form and test_guns_page_rows cover it.",
            "same_quantity_declared_count_not_estimated", DECLARED_INPUT_NO_ESTIMATION, READ,
            "The declared installed count is the real Plimsoll counterpart and is not to be "
            "equated with the mount count. What is missing is only the SPS behaviour around "
            "it: the count is never generated from calibre, and there is no per-group or "
            "per-mount barrel split."),
        _control(
            "gun.calibre", "Calibre - Shell diameter/barrel length:",
            "calibreBox (TextBox, float) with scale (ComboBox 'in'/'mm')", "input",
            "inches internally; the scale combo converts a millimetre entry to inches",
            "0", "calibreEnter :413 -> main.fpCheck(text, Con.inch2mm, scale.SelectedIndex); "
            "calMet = calibre * 25.4",
            "$.systems.weapons.<battery_id>.facts.calibre_m (positive metres).",
            "Declared and validated by project_extensions.py WEAPON_FIELDS, but no module in "
            "tools/plimsoll reads it in this review, so it contributes no mass and no check. "
            "There is no inch/millimetre display control on the Plimsoll side.",
            "same_quantity_declared_fact_canonical_metres", DECLARED_FACT_UNREAD, READ,
            "A canonical-metre fact with no estimator behind it and no display-unit control."),
        _control(
            "gun.barrel_length", "Barrel length in calibres (tooltip)",
            "calLengthBox (TextBox, float)", "input", "calibres (dimensionless ratio)",
            "45", "calLengthEnter :420 -> main.fpCheck(text, Con.none, 0)",
            "$.systems.weapons.<battery_id>.facts.length_m is a length in metres, not a calibre "
            "ratio.",
            "length_m is declared and validated in WEAPON_FIELDS and is not read by the systems "
            "or page-row computation in this review. No calibre-ratio field exists in the "
            "enumerated contract.",
            "different_quantity_ratio_versus_length", NO_DECLARED_FIELD, READ,
            no_chain + "Plimsoll has no barrel-length-in-calibres input, so the SPS shell and "
                       "gun mass factors that consume it cannot be reproduced."),
        _control(
            "gun.year", "Date:", "dateBox (TextBox)", "input",
            "CCYY year, range-checked 1850..1950", "1950",
            "dateGunEnter :426 -> main.dateCalc :1647 (4-digit CCYY check); "
            "dateGunAdj = sqrt(main.dateAdjCalc(year))",
            "$.metadata and $.hull.sources carry ship and machinery years; "
            "$.systems.weapons.<battery_id>.facts has no design-year field.",
            "Ship and machinery years are declared project facts. The enumerated weapons "
            "contract (tools/plimsoll/project_extensions.py WEAPON_FIELDS) has no gun design "
            "year, and no technology adjustment is applied to a weapon.",
            "no_equivalent_field_for_gun_design_year", NO_DECLARED_FIELD, READ,
            no_chain + "There is no Plimsoll technology-year adjustment for a weapon design."),
        _control(
            "gun.gun_type", "Type of gun:", "gunType (ComboBox, 7 items)", "input",
            "categorical index 0..6: muzzle loading, breech loading, quick firing, anti-air, "
            "dual purpose, auto rapid fire, machine gun", "index 1",
            "typeChoiceSelectedIndexChanged :437 -> mountsCalc -> gunWeightCalc :847 and "
            "gunWarningsAll :1294",
            "$.systems.weapons.<battery_id>.facts.weapon_type (free text).",
            "Declared and validated in WEAPON_FIELDS; not read by the systems or page-row "
            "computation in this review.",
            "same_concept_free_text_not_index_driven", DECLARED_FACT_UNREAD, READ,
            "Free text cannot reproduce the index-driven mount factor and the historical "
            "gun/mount/date consistency warnings."),
        _control(
            "gun.mount_type", "Type of mounts:", "mountType (ComboBox, 7 items)", "input",
            "categorical index 0..6: broadside, Coles/Ericsson turret, open barbette, turret on "
            "barbette, deck and hoist, deck, casemate", "index 5",
            "mountChoiceSelectedIndexChanged :1098 sets mountAdj (0.5, 1, 0.7, 1, 1, 0.5, 0.5); "
            "mountsCalc -> gunWeightCalc :828 (base mountWeight) and armWeightCalc",
            "$.systems.weapons.<battery_id>.facts.mount_description (free text) and "
            "facts.mount_count (integer).",
            "Both fields are declared and validated in WEAPON_FIELDS. mount_count is not read by "
            "the systems or page-row computation in this review; the installed_count family is "
            "the count that does drive mass.",
            "same_concept_free_text_not_index_driven", DECLARED_FACT_UNREAD, READ,
            no_chain + "The mount-type index drives every mount and armour estimate."),
        _control(
            "gun.mounts_total", "No. of Mounts:", "mountsBox (TextBox, int)", "input",
            "count of mounts", "0",
            "mountNumberSelectedIndexChanged :470 -> mountChoiceSelectedIndexChanged -> "
            "mountsCalc :564",
            "$.systems.weapons.<battery_id>.facts.mount_count (integer) and the declared "
            "installed count family.",
            "mount_count is declared and validated in WEAPON_FIELDS and is not read by the "
            "systems or page-row computation in this review.",
            "same_quantity_declared_fact_not_estimated", DECLARED_FACT_UNREAD, READ,
            "The declared mount count is not to be equated with the SPS arrangement model: "
            "Plimsoll does not split mounts across two groups or derive per-group gun counts."),
        _control(
            "gun.guns_in_mount.g1", "Group 1: Total guns | mounts",
            "gunsInMountG1 (ComboBox, 15 items)", "input",
            "categorical index 0..14 naming barrels per mount (single, 2 row twin, 4 row quad, "
            "twin, 2-gun, 2 row quad, triple, 3-gun, 2 row sextuple, quad, 4-gun, 2 row octuple, "
            "quintuple, 5-gun, 2 row decuple)", "index 0",
            "mountNumberSelectedIndexChanged :462; perMountCalc :636 maps the index to a barrel "
            "count; weightAdjCalc :480 sets 0.75 for indices 3, 6, 9, 12",
            "No field for barrels-per-mount in the enumerated weapons contract; the declared "
            "installed count is a battery total, not a per-mount class.",
            CONTRACT_EVIDENCE,
            "no_declared_per_mount_barrel_class", NO_DECLARED_FIELD, READ,
            no_chain + "This index selects per-mount barrel counts, mount width classes and a "
                       "weight adjustment."),
        _control(
            "gun.guns_in_mount.g2", "Group 2: Total guns | mounts",
            "gunsInMountG2 (ComboBox, 15 items)", "input", "same 15 items as group 1",
            "index 0",
            "mountNumberSelectedIndexChanged :465; perMountCalc :636; weightAdjCalc :480",
            "No field for barrels-per-mount in the enumerated weapons contract; the declared "
            "installed count is a battery total, not a per-mount class.",
            CONTRACT_EVIDENCE,
            "no_declared_per_mount_barrel_class", NO_DECLARED_FIELD, READ,
            "Group 2 is an independent mount-width class for weight and armour."),
        _control(
            "gun.layout.g1", "Group 1 location", "layoutG1 (ComboBox, 19 items)", "input",
            "categorical index 0..18: centreline/sides distributed, ends fore>aft, ends "
            "aft>fore, fore deck forward/centre/aft, aft deck forward/centre/aft, none",
            "index 18",
            "layoutChoice_SelectedIndexChanged :558 -> mountsCalc -> layoutCalc :908 sets "
            "layoutText, gunPosition and superAft",
            "$.systems.weapons.<battery_id>.facts.placement (free text).",
            "Declared and validated in WEAPON_FIELDS; not read by the systems or page-row "
            "computation in this review.",
            "same_concept_free_text_not_index_driven", DECLARED_FACT_UNREAD, READ,
            no_chain + "The layout index positions mounts on the freeboard decks and sets the "
                       "aft-superfiring flag."),
        _control(
            "gun.layout.g2", "Group 2 location", "layoutG2 (ComboBox, 19 items)", "input",
            "same 19 items as group 1", "index 18",
            "layoutChoice_SelectedIndexChanged :558 -> layoutCalc :908",
            "$.systems.weapons.<battery_id>.facts.placement (free text).",
            "Declared and validated in WEAPON_FIELDS; not read by the systems or page-row "
            "computation in this review.",
            "same_concept_free_text_not_index_driven", DECLARED_FACT_UNREAD, READ,
            "Group 2 layout is independent of group 1."),
        _control(
            "gun.mounts.raised.g1", "Above deck: (group 1)",
            "superMountG1Box (TextBox, int)", "input", "count of raised mounts", "0",
            "superMountG1Box_TextChanged :497 -> mountSuperG1 -> mountsCalc :568; the "
            "superfiring label in gunString :1628 also tests this count",
            "No raised/below-deck split field in the enumerated weapons contract; "
            "facts.mount_count is a single total.",
            CONTRACT_EVIDENCE,
            "no_declared_mount_arrangement_split", NO_DECLARED_FIELD, READ,
            no_chain + "The raised/below-deck split is an SPS arrangement model."),
        _control(
            "gun.mounts.deck.g1", "On deck: (group 1)",
            "deckMountG1Box (TextBox, ReadOnly)", "output", "count of mounts", "derived",
            "mountsCalc :578 sets mountDeckG1 = mounts - raised.g1 - below.g1 - raised.g2 - "
            "below.g2 - deck.g2",
            "Not a user input in SPS. The nearest Plimsoll readout is the declared installed "
            "count reported by systems.py:240 and page_rows.py:769.",
            AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "A derived SPS readout, not an input. Plimsoll reports the declared installed count "
            "instead and performs no such split."),
        _control(
            "gun.mounts.below_deck.g1", "Below deck: (group 1)",
            "subMountG1Box (TextBox, int)", "input", "count of hull mounts (casemates)", "0",
            "subMountG1Box_TextChanged :503 -> mountSubG1 -> mountsCalc :570; gunString :1644 "
            "labels them hull mounts in casemates",
            "No hull/upper-deck mount split field in the enumerated weapons contract.",
            CONTRACT_EVIDENCE,
            "no_declared_mount_arrangement_split", NO_DECLARED_FIELD, READ,
            no_chain + "Casemate versus upper-deck mounting changes mount weight and free-gun "
                       "rating."),
        _control(
            "gun.guns.raised.g1", "Group 1 guns above deck",
            "superG1Box (TextBox, ReadOnly)", "output", "count of barrels", "derived",
            "mountsCalc :568 sets gunSuperG1 = mountSuperG1 * perMountG1",
            "No per-group barrel readout in Plimsoll.", AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "Derived SPS barrel count per group."),
        _control(
            "gun.guns.deck.g1", "Group 1 guns on deck", "deckG1Box (TextBox, ReadOnly)",
            "output", "count of barrels", "derived",
            "mountsCalc :580 sets gunDeckG1 = barrels - all other group gun counts",
            "No per-group barrel readout in Plimsoll.", AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "Derived SPS barrel count per group."),
        _control(
            "gun.guns.below_deck.g1", "Group 1 guns below deck",
            "subG1Box (TextBox, ReadOnly)", "output", "count of barrels", "derived",
            "mountsCalc :570 sets gunSubG1 = mountSubG1 * perMountG1",
            "No per-group barrel readout in Plimsoll.", AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "Derived SPS barrel count per group."),
        _control(
            "gun.mounts.raised.g2", "Above deck: (group 2)",
            "superMountG2Box (TextBox, int)", "input", "count of raised mounts", "0",
            "superMountG2Box_TextChanged :509 -> mountSuperG2 -> mountsCalc :572; superSuperChk "
            "doubles this count as gunSuperG2Adj",
            "No raised-mount split field in the enumerated weapons contract.",
            CONTRACT_EVIDENCE,
            "no_declared_mount_arrangement_split", NO_DECLARED_FIELD, READ,
            "Group 2 raised mounts may be superfiring over group 1."),
        _control(
            "gun.mounts.deck.g2", "On deck: (group 2)", "deckMountG2Box (TextBox, int)",
            "input", "count of mounts on the freeboard deck", "0",
            "deckMountG2Box_TextChanged :515 -> mountDeckG2 -> mountsCalc :574",
            "No per-group deck-mount field in the enumerated weapons contract.",
            CONTRACT_EVIDENCE,
            "no_declared_mount_arrangement_split", NO_DECLARED_FIELD, READ,
            "Group 2 deck mounts are subtracted from the group 1 deck remainder in SPS."),
        _control(
            "gun.mounts.below_deck.g2", "Below deck: (group 2)",
            "subMountG2Box (TextBox, int)", "input", "count of hull mounts", "0",
            "subMountG2Box_TextChanged :521 -> mountSubG2 -> mountsCalc :576",
            "No per-group hull-mount field in the enumerated weapons contract.",
            CONTRACT_EVIDENCE,
            "no_declared_mount_arrangement_split", NO_DECLARED_FIELD, READ,
            "Group 2 hull mounts, optionally one deck lower via subSubChk."),
        _control(
            "gun.guns.raised.g2", "Group 2 guns above deck",
            "superG2Box (TextBox, ReadOnly)", "output", "count of barrels", "derived",
            "mountsCalc :572 sets gunSuperG2 = mountSuperG2 * perMountG2",
            "No per-group barrel readout in Plimsoll.", AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "Derived SPS barrel count per group."),
        _control(
            "gun.guns.deck.g2", "Group 2 guns on deck", "deckG2Box (TextBox, ReadOnly)",
            "output", "count of barrels", "derived",
            "mountsCalc :574 sets gunDeckG2 = mountDeckG2 * perMountG2",
            "No per-group barrel readout in Plimsoll.", AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "Derived SPS barrel count per group."),
        _control(
            "gun.guns.below_deck.g2", "Group 2 guns below deck",
            "subG2Box (TextBox, ReadOnly)", "output", "count of barrels", "derived",
            "mountsCalc :576 sets gunSubG2 = mountSubG2 * perMountG2",
            "No per-group barrel readout in Plimsoll.", AUDITED,
            "sps_derived_readout_only", NOT_AN_SPS_INPUT, READ,
            "Derived SPS barrel count per group."),
        _control(
            "gun.superfiring.raised_two_up", "2 mounts up", "superSuperChk (CheckBox)",
            "input", "boolean", "unchecked",
            "superSubChkCheckedChanged :527 -> superMountsEnter :1762 (repaints the schematic) "
            "and mountsCalc :604 sets gunSuperG2Adj = 2 when checked else 1",
            "No superfiring-height flag in the enumerated weapons contract; the free text "
            "facts.placement can describe an arrangement but drives nothing.",
            CONTRACT_EVIDENCE,
            "no_declared_superfiring_flag", NO_DECLARED_FIELD, READ,
            no_chain + "This is the superfiring-height control: it doubles the group 2 raised "
                       "mounts in the super ratio and arms the barbette estimate."),
        _control(
            "gun.superfiring.below_deck_lower", "Lower deck", "subSubChk (CheckBox)", "input",
            "boolean", "unchecked",
            "superSubChkCheckedChanged :527; mountsCalc :612 sets gunSubG2Adj = 2 when checked; "
            "gunString :1717/:1729 labels lower casemates; armWeightCalc :1222 scales the "
            "barbette term by sqrt(dateGunAdj)",
            "No lower-deck flag in the enumerated weapons contract.", CONTRACT_EVIDENCE,
            "no_declared_superfiring_flag", NO_DECLARED_FIELD, READ,
            no_chain + "This is the lower-deck superfiring control for group 2 hull mounts."),
        _control(
            "gun.armour.face", "Face / Shield:",
            "armFaceBox (TextBox, float) in armour.scale units (in or mm)", "input",
            "inches or millimetres depending on the Armour page scale combo", "0",
            "armFaceEnter :540 -> main.fpCheck(text, Con.inch2mm, "
            "armour.scale.SelectedIndex) -> armWeightCalc :1169",
            "$.systems.armour.fixed typed rows carry declared belt/deck thicknesses, which are a "
            "different structure from mount face armour.",
            "The armour contract declares typed thicknesses and the rotating_armour_component "
            "projection reports a declared, non-additive split of an already-sourced mount mass "
            "(page_rows.py:326).",
            "different_structure_declared_only", DECLARED_INPUT_NO_ESTIMATION, READ,
            no_chain + "Plimsoll accepts a declared rotating-armour component; it never "
                       "derives one from calibre and layout."),
        _control(
            "gun.armour.side_rear", "Other above deck:",
            "armBackBox (TextBox, float) in armour.scale units", "input",
            "inches or millimetres", "0", "armBackEnter :546 -> armWeightCalc :1191",
            "No declared field for average side and rear mount armour thickness in the armour "
            "typed-row set read in this review.",
            ARMOUR_CONTRACT_EVIDENCE,
            "no_declared_mount_side_rear_thickness", NO_DECLARED_FIELD, READ,
            no_chain + "Average side and rear mount armour thickness."),
        _control(
            "gun.armour.barbette", "Barbette / Hoist:",
            "armBottomBox (TextBox, float) in armour.scale units", "input",
            "inches or millimetres", "0", "armBottomEnter :552 -> armWeightCalc :1222",
            "No declared barbette/hoist thickness field in the armour typed-row set read in "
            "this review.",
            ARMOUR_CONTRACT_EVIDENCE,
            "no_declared_barbette_thickness", NO_DECLARED_FIELD, READ,
            no_chain + "Barbette / below-deck armour thickness feeding the bottom-armour term."),
        _control(
            "gun.armour.weight", "Weight (t):", "armWeightBox (TextBox, ReadOnly)", "output",
            "long tons as computed", "derived",
            "armWeightCalc :1233 sets armWeight = face + back + bottom and writes 'n0'",
            "$.stages.systems.data.page_rows[weapons.<battery_id>].rotating_armour_component."
            "rotating_armour_mass_t",
            "A declared, non-additive split of the selected mount mass (page_rows.py:326, "
            "test_completion_mount_armour.py).",
            "declared_component_not_estimated", DECLARED_INPUT_NO_ESTIMATION, READ,
            "The estimate chain behind the SPS readout is unimplemented; Plimsoll requires a "
            "sourced component mass and never adds it to the ship."),
        _control(
            "gun.shell_weight_lb", "Shell weight - lbs/kg:", "shellWeightBox (TextBox, float)",
            "input", "pounds", "0 (auto-estimated)",
            "shellWeightEnter :448 -> main.fpCheck(text, Con.none, 0) -> "
            "shellWeightEnterCalc :760; a non-focused box is overwritten by shellWeightCalc :793",
            "$.systems.weapons.<battery_id>.facts.projectile_mass_kg (kg), and the "
            "counted_ammunition_mass model inputs.",
            "projectile_mass_kg is declared and read by page_rows.py weapons_page_rows as a "
            "reporting input when no ammunition model exists, and drives the counted "
            "ammunition outfit when one does (systems.py:110-130).",
            "same_quantity_declared_canonical_kg", DECLARED_INPUT_NO_ESTIMATION, READ,
            "Plimsoll stores projectile mass in kilograms and never estimates it. Note the "
            "recovered pound conversion constant is 0.45359236 while Plimsoll uses the exact "
            "0.45359237."),
        _control(
            "gun.shell_weight_kg", "Shell weight - kg:",
            "shellMetricBox (TextBox, float, disabled by default)", "input", "kilograms",
            "disabled",
            "shellMetricEnter :454 -> main.fpCheck(text, Con.pounds2kg, 1) -> "
            "shellWeightEnterCalc",
            "$.systems.weapons.<battery_id>.facts.projectile_mass_kg (kg) is the single "
            "canonical mass.",
            "One canonical kilogram fact; there is no separate pound entry to keep in step.",
            "canonical_single_unit", DECLARED_INPUT_NO_ESTIMATION, READ,
            "A display-unit entry around the same shell weight; Plimsoll has one canonical "
            "kilogram fact."),
        _control(
            "gun.shell_weight_lock",
            "Click to change shell weight scale or lock shell weights",
            "shellLockbtn (Button, 3-state) with shellLockState 0/1/2", "input", "state "
            "machine, no unit", "state 0 (auto)",
            "shellLockbtnClick :350 cycles state 0 (estimate shown, lb box editable) -> state 1 "
            "(kg box editable) -> state 2 (both locked, combined label)",
            "No lock affordance is needed: the single canonical kilogram fact is either "
            "declared or absent.",
            "Plimsoll has no shell estimate to lock, and no dual-unit shell entry.",
            "sps_ui_affordance_without_counterpart", NOT_AN_SPS_INPUT, READ,
            no_chain + "The lock exists to protect an estimate; Plimsoll has no estimate."),
        _control(
            "gun.rounds_per_barrel", "Shells per gun:", "magazineBox (TextBox, int)", "input",
            "rounds per gun barrel", "150",
            "magazineEnter :442 -> magazineCalc :808 sets magazineWeight = magazine * barrels * "
            "shellWeight / POUND2TON * 1.2444444 and broadsideWeight = barrels * shellWeight",
            "$.systems.weapons.<battery_id>.rounds_per_gun (declared; GunsEditor.tsx edits it) "
            "and $.stages.systems.data.page_rows[weapons.<battery_id>].per_gun_shell_kg.",
            "Live and load-bearing: systems.py:115 requires rounds_field == 'rounds_per_gun' and "
            ":130 builds the ammunition outfit mass from it; page_rows.py:654 reports "
            "per_gun_shell_kg.",
            "same_quantity_declared_count_not_estimated", DECLARED_INPUT_NO_ESTIMATION, READ,
            "Plimsoll multiplies declared rounds by a declared projectile (and charge) mass; "
            "SPS rounds are per barrel, so the products differ whenever the declared installed "
            "count is not the barrel count."),
        _control(
            "gun.description", "descriptionBox (RichTextBox)", "descriptionBox (RichTextBox)",
            "output", "free text", "derived",
            "gunString :1579 composes barrels, calibre in inches and mm, calibre length, shell "
            "weight lb/kg, rounds, gun and mount type names, the design year, both group "
            "layouts, raised/sub counts with the superfiring label and the free-gun sea-state "
            "wording",
            "$.stages.systems.data.page_rows[weapons.<battery_id>].rows, .broadside and "
            "$.stages.systems.data.deck_coverage report the underlying numbers as structured "
            "rows.",
            "Structured declared projections exist; a composed narrative paragraph does not.",
            "declared_rows_not_narrative", DERIVED_READOUT, READ,
            "The narrative text has no Plimsoll equivalent; only the ledger rows behind it do."),
        _control(
            "gun.layout_picture", "verticalPic / horizontalPic (PictureBox)",
            "verticalPic and horizontalPic, painted by verticalPicPaint :1805 and "
            "horizontalPicPaint :1880", "display", "schematic image, no numeric readout",
            "image resource",
            "superMountsEnter :1762 and superMountsLeave :1799 set activeBox and repaint",
            "No arrangement schematic; the web editors show declared counts and page rows.",
            "Read the current core and frontend sources; no equivalent schematic is produced.",
            "sps_display_without_counterpart", NOT_AN_SPS_INPUT, READ,
            "A schematic of the raised/below-deck mount arrangement carrying no number that "
            "Plimsoll would need."),
    ]
    methods = [
        {
            "id": "shell_weight_estimate",
            "name": "shellWeightCalc(calibre, calLength, dateFactor)",
            "location": "GunControl.cs:793",
            "formula": "weight = calibre^3 / 1.9830943211886; if calLength < 45 multiply by "
                       "(45 - sqrt(45 - calLength)) / 45, else if calLength > 45 multiply by "
                       "(45 + sqrt(calLength - 45)) / 45; finally multiply by dateFactor "
                       "(= sqrt(dateAdjCalc(year))).",
            "units": "pounds per shell",
            "consumers": ["gun.shell_weight_lb", "gun.shell_weight_kg", "gun.rounds_per_barrel",
                          "gun.guns_in_mount.g1", "gun.guns_in_mount.g2"],
            "plimsoll_equivalent": "$.systems.weapons.<battery_id>.facts.projectile_mass_kg is a "
                                   "declared fact, not this estimate.",
            "coverage": "no_estimating_method",
            "note": no_chain + "Plimsoll has no shell-mass estimate; projectile mass must be "
                               "declared with a source.",
        },
        {
            "id": "gun_mass",
            "name": "gunWeightCalc(calibre, calLength, barrels, dateAdj, gunType, mountType, "
                    "mountAdj, weightAdj)",
            "location": "GunControl.cs:815 (mass branch at :817-825)",
            "formula": "gunWeight = shellWeightCalc(calibre, calLength, dateAdj) * (calLength / "
                       "812.389434917877 * (1 + (1/calibre)^2.3297949327695)) * barrels, and "
                       "zero when calibre <= 0 or barrels <= 0.",
            "units": "pounds for the whole battery of barrels",
            "consumers": ["gun.barrels", "gun.calibre", "gun.barrel_length", "gun.year"],
            "plimsoll_equivalent": "$.stages.systems.data.page_rows[weapons.<battery_id>].rows"
                                   "[row=guns].weight_t is the declared ledger projection.",
            "coverage": "no_estimating_method",
            "note": "Plimsoll multiplies a declared unit mass by a declared installed count; "
                    "it never regenerates the mass from calibre.",
        },
        {
            "id": "mount_mass",
            "name": "gunWeightCalc mount branch",
            "location": "GunControl.cs:826-903",
            "formula": "base mountWeight by mountType (0:0.83, 2:3.33, 4:3.15, 5 and 6:1.08, "
                       "default 3.5); multiplied by a gunType factor that depends on whether "
                       "mountAdj < 0.6; then += 1 / calibre^0.313068808543972; then *= gunWeight; "
                       "if calibre > 10 multiply by (1 - 2.1623769 * calibre / 100); finally "
                       "*= weightAdj (the mount-count-weighted group adjustment).",
            "units": "pounds for the whole battery of mounts",
            "consumers": ["gun.gun_type", "gun.mount_type", "gun.barrels", "gun.calibre"],
            "plimsoll_equivalent": "$.stages.systems.data.page_rows[weapons.<battery_id>].rows"
                                   "[row=mounts].weight_t is the declared ledger projection.",
            "coverage": "no_estimating_method",
            "note": no_chain + "The mount estimate is entirely index-driven and calibre-driven.",
        },
        {
            "id": "mount_weight_adjustment",
            "name": "weightAdjCalc(mountNo) and perMountCalc(mountNoIndex)",
            "location": "GunControl.cs:480 and :636",
            "formula": "weightAdj = 0.75 when the guns-per-mount index is 3, 6, 9 or 12, else 1. "
                       "perMount maps the 15-index combo to barrels per mount (1, 2, 3, 4, 5, 6, "
                       "8, 10 by index).",
            "units": "dimensionless",
            "consumers": ["gun.guns_in_mount.g1", "gun.guns_in_mount.g2"],
            "plimsoll_equivalent": None,
            "coverage": "no_estimating_method",
            "note": no_chain + "Plimsoll has no barrel-per-mount class.",
        },
        {
            "id": "group_split",
            "name": "mountsCalc()",
            "location": "GunControl.cs:564",
            "formula": "Derives per-group barrel counts (raised, on deck, below deck) from the "
                       "mount counts and per-mount barrels; the group 1 deck remainder is mounts "
                       "minus all other group counts, and the group 1 barrel remainder is "
                       "barrels minus all other group barrels; then weights the group adjustments "
                       "and free-gun ratings by group mount counts.",
            "units": "counts and dimensionless ratios",
            "consumers": ["gun.mounts_total", "gun.mounts.raised.g1", "gun.mounts.raised.g2",
                          "gun.mounts.deck.g1", "gun.mounts.deck.g2",
                          "gun.mounts.below_deck.g1", "gun.mounts.below_deck.g2"],
            "plimsoll_equivalent": None,
            "coverage": "no_estimating_method",
            "note": "The two-group arrangement model (which mounts are raised, on deck or in "
                    "casemates) has no counterpart in the declared Plimsoll weapons contract.",
        },
        {
            "id": "superfiring_ratio",
            "name": "super ratio in mountsCalc",
            "location": "GunControl.cs:620-623",
            "formula": "super = (gunSuperG1 + gunSuperG2 * gunSuperG2Adj - gunSubG1 - gunSubG2 * "
                       "gunSubG2Adj) / barrels, then super = (super * max(7.5, calibre * 0.6) + "
                       "freeGun) / freeGun. gunSuperG2Adj and gunSubG2Adj are 2 when the "
                       "corresponding checkbox is set, else 1.",
            "units": "dimensionless",
            "consumers": ["gun.superfiring.raised_two_up",
                          "gun.superfiring.below_deck_lower", "gun.armour.barbette"],
            "plimsoll_equivalent": None,
            "coverage": "no_estimating_method",
            "note": no_chain + "The superfiring-height effect enters only through these two "
                               "checkboxes and the barbette estimate.",
        },
        {
            "id": "free_gun_rating",
            "name": "freeGunCalc(layout, mounts)",
            "location": "GunControl.cs:678",
            "formula": "Maps the 18 layout indices to a fore/aft split of the mount count and "
                       "returns a weighted free-gun rating built from the Freeboard page free-gun "
                       "values.",
            "units": "a free-gun rating in feet as carried by the Freeboard page",
            "consumers": ["gun.layout.g1", "gun.layout.g2", "gun.armour.barbette",
                          "gun.description"],
            "plimsoll_equivalent": None,
            "coverage": "no_estimating_method",
            "note": no_chain + "Plimsoll has no free-gun (weather-deck exposure) rating.",
        },
        {
            "id": "layout_text_and_position",
            "name": "layoutCalc(gunLayout, gunMounts, group)",
            "location": "GunControl.cs:908",
            "formula": "Sets layoutText, superAft and gunPosition (fractions of the fore or aft "
                       "freeboard deck length) for each of the 18 layout indices; indices 0-2, "
                       "9-11 force gunPosition to 1 for group 1 and 0 for group 2.",
            "units": "fraction of freeboard deck length",
            "consumers": ["gun.layout.g1", "gun.layout.g2"],
            "plimsoll_equivalent": None,
            "coverage": "no_estimating_method",
            "note": no_chain + "Mount longitudinal placement is an SPS arrangement model; "
                               "facts.placement is free text and drives nothing.",
        },
        {
            "id": "mount_armour_mass",
            "name": "armWeightCalc() and diameterCalc(mountWidth, calibre, weightAdj)",
            "location": "GunControl.cs:1127 and :1238",
            "formula": "diameter = num * calibre * (1 + (1/calibre)^num2) from the mount-width "
                       "class (num/num2 pairs 1.44/0.609725, 1.52/0.4205, 1.64/0.29, 1.8/0.2, "
                       "2.0/0.14), plus 12/calibre when calibre < 12, times 0.9 when weightAdj "
                       "< 1. gunHouseHeight = max(7.5, 0.625 * calibre) (twice the calibre for a "
                       "Coles/Ericsson turret). Face, back and bottom armour masses are assembled "
                       "from these diameters, the mount counts, the free-gun rating, super, "
                       "dateGunAdj and the three armour-thickness inputs; the code multiplies by "
                       "main.INCH = 0.0185, an empirical constant whose unit basis is not "
                       "asserted here.",
            "units": "reported as long tons in armWeightBox",
            "consumers": ["gun.armour.face", "gun.armour.side_rear", "gun.armour.barbette",
                          "gun.armour.weight"],
            "plimsoll_equivalent": "$.stages.systems.data.page_rows[weapons.<battery_id>]. "
                                   "rotating_armour_component.rotating_armour_mass_t is a "
                                   "declared component.",
            "coverage": "no_estimating_method",
            "note": no_chain + "Plimsoll treats mount armour only as a declared, non-additive "
                               "split of a sourced mount mass.",
        },
        {
            "id": "ammunition_mass",
            "name": "magazineCalc()",
            "location": "GunControl.cs:808",
            "formula": "magazineWeight = magazine * barrels * shellWeight / 2240 * 1.2444444 "
                       "(equivalently /1800); broadsideWeight = barrels * shellWeight.",
            "units": "magazineWeight uses the as-written 1.2444444/2240 factor; "
                     "broadsideWeight in pounds",
            "consumers": ["gun.rounds_per_barrel", "gun.shell_weight_lb"],
            "plimsoll_equivalent": "$.stages.systems.data.page_rows[weapons.<battery_id>]. "
                                   "ship_wide_ammunition_t, per_gun_shell_kg and "
                                   "broadside.mass_kg / mass_lb.",
            "coverage": "declared_mass_projection",
            "note": "Plimsoll computes ammunition mass from declared rounds and a declared "
                    "projectile (and charge) mass, not from a shell estimate; its broadside mass "
                    "excludes charge and outfit by design and uses the declared broadside count.",
        },
        {
            "id": "description_text",
            "name": "gunString()",
            "location": "GunControl.cs:1579",
            "formula": "Formats barrels, calibre (inches and mm), calibre length, shell weight "
                       "(lb and kg), rounds, gun type, mount type, design year, both group "
                       "layouts, raised and below-deck counts, the superfiring label and the "
                       "free-gun sea-state wording into the description box.",
            "units": "free text",
            "consumers": ["gun.description"],
            "plimsoll_equivalent": "$.stages.systems.data.page_rows[weapons.<battery_id>] "
                                   "structured rows.",
            "coverage": "declared_rows_not_narrative",
            "note": "Only the ledger rows behind the text have Plimsoll equivalents.",
        },
        {
            "id": "validation_warnings",
            "name": "gunWarningsAll()",
            "location": "GunControl.cs:1294",
            "formula": "Cross-checks gun type against mount type and design year (for example no "
                       "muzzle-loading gun in a modern turret before 1880, no anti-air gun before "
                       "1910) and calibre against gun type, raising status-bar warnings.",
            "units": "boolean warnings",
            "consumers": ["gun.gun_type", "gun.mount_type", "gun.year", "gun.calibre"],
            "plimsoll_equivalent": None,
            "coverage": "no_estimating_method",
            "note": no_chain + "Plimsoll has no historical gun/mount/date consistency checking.",
        },
    ]
    return {
        "schema": "plimsoll-gun-editor-source-supplement-1",
        "version": "1.0.0",
        "phase": POLICY_PHASE,
        "supersedes": None,
        "generated_by": "tools/plimsoll/tools/reconcile_seven_pages.py",
        "placeholder_record": "guns.battery_selection.editor_fields_unknown",
        "source": SOURCE,
        "evidence_boundary": [
            "This supplement transcribes recovered SpringSharpMono C# and does not execute the "
            "original program.",
            "A method transcribed here is not implemented in Plimsoll and carries no validated "
            "parity.",
            "Formulas are recorded as recovered, including empirical constants such as "
            "1.9830943211886 and main.INCH = 0.0185, whose unit basis is not asserted.",
            "Absence of a Plimsoll field is asserted only where the enumerated declared weapons "
            "or armour contract makes it verifiable; the result and UI surfaces were read for the "
            "entries marked verified_against_current_source_2026_10_15 and are otherwise marked "
            "not_reaudited rather than claimed absent.",
        ],
        "plimsoll_audit_note": AUDITED,
        "plimsoll_declared_inputs": [
            {"path": "$.systems.weapons.<battery_id>.installed_guns",
             "role": "declared installed gun count; drives the declared count mass model",
             "evidence": "systems.py _declared_count (74-90, 232-241), page_rows.py:769, "
                         "GunsEditor.tsx:130/211"},
            {"path": "$.systems.weapons.<battery_id>.rounds_per_gun",
             "role": "declared rounds per gun; drives the ammunition outfit mass",
             "evidence": "systems.py:115-130, page_rows.py:654, GunsEditor.tsx:211"},
            {"path": "$.systems.weapons.<battery_id>.broadside_guns",
             "role": "declared broadside count; broadside mass only",
             "evidence": "page_rows.py:292-312, :770"},
            {"path": "$.systems.weapons.<battery_id>.facts.projectile_mass_kg",
             "role": "declared projectile mass; reporting input when no ammunition model exists",
             "evidence": "page_rows.py:649 and the ammunition block at :676-800"},
            {"path": "$.systems.weapons.<battery_id>.facts.calibre_m",
             "role": "declared calibre in metres; validated but not read by the current "
                     "computation",
             "evidence": "project_extensions.py WEAPON_FIELDS (15)"},
            {"path": "$.systems.weapons.<battery_id>.facts.mount_count",
             "role": "declared mount count; validated but not read by the current computation",
             "evidence": "project_extensions.py WEAPON_FIELDS (18)"},
            {"path": "$.systems.weapons.<battery_id>.rotating_armour_component",
             "role": "declared non-additive mount-armour split of a sourced mount mass",
             "evidence": "page_rows.py:326, test_completion_mount_armour.py"},
        ],
        "controls": controls,
        "methods": methods,
        "coverage_counts": dict(sorted(Counter(c["coverage"] for c in controls).items())),
        "coverage_note": "Every estimating control in the recovered gun editor has no Plimsoll "
                         "estimating chain. What Plimsoll does have is declared, sourced inputs: "
                         "the installed count, rounds per gun, the broadside count, projectile "
                         "and charge mass, calibre and the rotating-armour component. None of "
                         "them is ever regenerated from calibre, barrel length, design year or "
                         "mount type.",
    }

def _write(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    records = data["records"]
    if len(records) != RECORD_COUNT or len({r["id"] for r in records}) != RECORD_COUNT:
        raise ValueError("the source observation inventory must contain %d unique IDs" % RECORD_COUNT)

    for record in records:
        identity = record["id"]
        status, path, note = review(record)
        record.setdefault("pre_reconciliation_disposition", record["current_disposition"])
        # Earlier scope decisions are kept as history, never erased by this phase.
        history = record.setdefault("disposition_history", [
            {"phase": "original_proposal", "disposition": record["pre_reconciliation_disposition"]},
            {"phase": "core_binding_reconciliation_2026_09",
             "disposition": record["current_disposition"],
             "core_review_status": (record.get("core_review") or {}).get("status")},
        ])
        history[:] = [entry for entry in history if entry.get("phase") != POLICY_PHASE]
        history.append({"phase": POLICY_PHASE, "disposition": status})

        # 1. Remove obsolete active canonical/result bindings, keeping them as history.
        rejected = REJECTED_BINDINGS.get(identity)
        if rejected:
            drop = {(entry["kind"], entry["path"]) for entry in rejected}
            for key, kind in (("canonical_inputs", "canonical_input"), ("result_bindings", "result")):
                kept = []
                for entry in record.get(key) or []:
                    if (kind, entry.get("path")) not in drop:
                        kept.append(entry)
                record[key] = kept
            record["historical_rejected_bindings"] = [
                dict(entry, withdrawn_phase=POLICY_PHASE) for entry in rejected]
            record["related_plimsoll_studies"] = RELATED_STUDIES.get(identity, [])
        if identity in SOURCE_EVIDENCE:
            record["source_evidence"] = SOURCE_EVIDENCE[identity]
        if identity in ACTIVE_METADATA:
            superseded = HISTORICAL_METADATA[identity]
            record.setdefault("historical_metadata", [{
                "phase": "original_proposal",
                "limitation": superseded["limitation"],
                "required_condition": superseded["required_condition"],
                "required_stages": superseded["required_stages"],
                "provenance_bindings": superseded["provenance_bindings"],
                "canonical_inputs": superseded.get("canonical_inputs", []),
                "evidence": superseded["evidence"],
            }])
            active = ACTIVE_METADATA[identity]
            record["limitation"] = active["limitation"]
            record["required_condition"] = None
            record["required_stages"] = active["required_stages"]
            record["provenance_bindings"] = active["provenance_bindings"]
            record["canonical_inputs"] = active["canonical_inputs"]
            record["evidence"] = active["evidence"]

        record["current_disposition"] = status
        record["core_review"] = dict(status=status, result_path=path, limitation=note,
                                     phase=POLICY_PHASE)
        record["semantic_relation"] = semantic_relation(record, status)
        record["verification"] = verification(record, status)
        if status.startswith("implemented") and path and not any(
                binding.get("path") == path for binding in record["result_bindings"]):
            record["result_bindings"].append({"path": path})

    supplement = gun_editor_supplement()
    _write(SUPPLEMENT_PATH, supplement)

    out = {
        "schema": SCHEMA,
        "supersedes_schema": SUPERSEDED_SCHEMA,
        "status": "coverage_baseline_repaired",
        "phase": POLICY_PHASE,
        "completion_claim": False,
        "sps_equivalence_claims": {
            "verified_records": 0,
            "statement": "No record in this file is verified as SpringSharp-equivalent. An "
                         "approved exclusion, an existing adapter or an available binding is "
                         "never counted as equivalence evidence.",
        },
        "inventory": data["inventory"],
        "checkpoint": {
            "note": "Coverage baseline repaired after the 2026-10-15 comparison. Disputed "
                    "performance bindings were withdrawn, the natural-speed method is recorded "
                    "as known-but-unimplemented, and the previously unobserved gun editor is "
                    "described in a versioned supplement.",
        },
        "selector_semantics": data["selector_semantics"],
        "semantic_relation_vocabulary": SEMANTIC_VOCABULARY,
        "supplement": {
            "gun_editor": {
                "path": "docs/plimsoll-1.0/evidence/gun-editor-source-supplement.json",
                "version": supplement["version"],
                "schema": supplement["schema"],
                "control_count": len(supplement["controls"]),
                "method_count": len(supplement["methods"]),
                "covers_record": "guns.battery_selection.editor_fields_unknown",
            },
        },
        "source": SOURCE,
        "disposition_counts": dict(sorted(Counter(r["current_disposition"] for r in records).items())),
        "semantic_relation_counts": dict(sorted(Counter(r["semantic_relation"] for r in records).items())),
        "verification_state_counts": dict(sorted(Counter(r["verification"]["state"] for r in records).items())),
        "records": records,
    }
    _write(PATH, out)
    print(json.dumps({"dispositions": out["disposition_counts"],
                      "semantic_relations": out["semantic_relation_counts"],
                      "verification": out["verification_state_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()