"""Reconcile the frozen 191-field SPS observation inventory with core bindings.

This is an evidence map, not a claim that every observed historical input is
known for Queen Mary. In particular, a reusable adapter and a populated case
are distinct outcomes.
"""

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "docs/plimsoll-1.0/evidence/seven-page-binding-proposal.json"


def review(record):
    identity = record["id"]
    old = record.get("pre_reconciliation_disposition", record["current_disposition"])
    if old == "accepted_exclusion":
        return "excluded_by_approved_scope", None, "User-approved non-calculation control or formula exclusion."
    if "presentation_deferred" in old or old == "presentation_deferred":
        return "presentation_deferred", None, "Core-only phase; presentation is not delivered."
    if identity == "hull.derived.natural_speed":
        return "unavailable_method_undefined", None, "No agreed natural-speed definition or source; no number is fabricated."
    if identity == "guns.battery_selection.editor_fields_unknown":
        return "unobserved_source_limit", None, "This editor was not visible in the seven-page source capture."
    if identity == "hull.derived.length_beam":
        return "implemented", "$.stages.l0.data.hull_ratios.design_lwl_over_beam", "Design LWL/beam and selected-plane body-axis ratio are separate."
    if identity.startswith("freeboard.segments."):
        segment = identity.split(".")[2]
        field = identity.rsplit(".", 1)[-1]
        key = {"forward": "fore_clearance_m", "aft": "aft_clearance_m", "length_pct": "length_pct"}[field]
        return "implemented_input_conditional", f"$.stages.deck.data.profile.segments[id={segment}].{key}", \
            "Only explicitly declared deck endpoints are evaluated; Queen Mary fixture has one centreline segment, not four historical SPS segments."
    if identity.startswith("guns.weights."):
        field = identity.rsplit(".", 1)[-1]
        if field == "armour":
            return "unavailable_component_split", None, "Rotating armour is included in mount ledger mass; no independent armour subtotal is sourced."
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
        return "unavailable_component_split", None, "Rotating gunhouse armour is included in mount mass, without a sourced separate subtotal."
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
    if identity == "performance.set_trim":
        return "implemented_as_constraint_study", "$.stages.equilibrium.data.trim_target_study.required_longitudinal_moment_kNm", \
            "Independent target-moment study; free equilibrium is unchanged."
    if identity == "performance.steadiness":
        return "implemented_input_conditional", "$.stages.hydrostatics.data.loaded_roll.period_s", \
            "Needs positive selected GM and sourced gyration coefficient; Queen Mary selected GM is unavailable."
    if old.startswith("bound") or old == "core_inputs_bound_presentation_deferred":
        path = next((entry.get("path") for entry in record.get("result_bindings", []) if entry.get("path")), None)
        return "existing_binding_conditioned", path, "Existing binding retained; case values and method applicability are assessed separately."
    return "unavailable_unresolved", None, "No verified computation binding for this observation."


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    records = data["records"]
    if len(records) != 191 or len({r["id"] for r in records}) != 191:
        raise ValueError("the source observation inventory must contain 191 unique IDs")
    for record in records:
        status, path, note = review(record)
        record.setdefault("pre_reconciliation_disposition", record["current_disposition"])
        record["core_review"] = dict(status=status, result_path=path, limitation=note,
                                     evidence="tools/plimsoll/analysis.py and tools/plimsoll/tests/test_completion_*.py")
        if status.startswith("implemented"):
            record["current_disposition"] = status
            if path and not any(binding.get("path") == path for binding in record["result_bindings"]):
                record["result_bindings"].append({"path": path})
    data["status"] = "core_binding_reconciled_with_declared_gaps"
    data["completion_claim"] = False
    data["core_review_counts"] = dict(sorted(Counter(r["core_review"]["status"] for r in records).items()))
    data["checkpoint"] = {"note": "Reconciled against current source and focused completion tests; final 45-item acceptance audit is separate."}
    data["disposition_counts"] = dict(sorted(Counter(r["current_disposition"] for r in records).items()))
    PATH.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").replace("\n", "\r\n").encode("utf-8"))
    print(json.dumps(data["core_review_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
