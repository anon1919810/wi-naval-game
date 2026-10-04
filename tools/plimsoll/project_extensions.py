"""Validate optional calculation-core inputs without invoking numerical kernels."""

import json
import math


METADATA_FIELDS = {"country": "text", "type": "text", "design_year": "integer",
                   "laid_down_year": "integer", "engine_built_year": "integer"}
HULL_DESIGN_FIELDS = {"block_coeff_deep": "positive", "reference_displacement_normal_t": "nonnegative",
                      "reference_displacement_deep_t": "nonnegative"}
PROPULSION_FIELDS = {"shafts": "count", "boilers": "count", "design_power_kw": "positive",
    "trial_power_kw": "positive", "max_speed_kn": "positive", "cruise_speed_kn": "positive",
    "engine_description": "text", "boiler_description": "text", "engine_built_year": "integer",
    "energy_source": "text", "transmission": "text"}
WEAPON_FIELDS = {"calibre_m": "positive", "unit_mass_t": "nonnegative",
    "length_m": "positive", "diameter_m": "positive", "projectile_mass_kg": "nonnegative",
    "charge_mass_kg": "nonnegative", "rounds_per_gun": "integer", "mount_description": "text",
    "placement": "text", "weapon_type": "text", "mount_count": "integer"}
ARMOUR_FIELDS = {"thickness_m": "nonnegative", "length_m": "positive", "height_m": "positive",
    "area_m2": "nonnegative", "density_kg_m3": "positive", "inclination_deg": "signed",
    "zone": "text", "deck_layer": "text"}
DECK_FIELDS = {"form": "text", "stem_angle_deg": "signed", "ram_length_m": "nonnegative",
               "stern_overhang_m": "nonnegative"}
RESISTANCE_INPUTS = {"c_stern": "signed", "bulb_area_m2": "nonnegative",
    "bulb_height_m": "nonnegative", "transom_area_m2": "nonnegative",
    "additional_roughness_delta_ca": "nonnegative", "delta_cf": "nonnegative",
    "x_fore_perpendicular_m": "signed", "x_aft_perpendicular_m": "signed",
    "density_kg_m3": "positive", "gravity_m_s2": "positive",
    "kinematic_viscosity_m2_s": "positive"}
PAGE_ROW_TYPED_FIELDS = {"tubes": "integer", "carried": "integer", "sets": "integer",
    "diameter_mm": "positive", "length_m": "positive", "arrangement": "text",
    "count": "integer", "reloads": "integer", "kind": "text",
    "unit_weight_kg": "nonnegative", "mass_t": "nonnegative",
    "height_m": "positive", "inclination_deg": "signed", "beam_between_m": "positive",
    "construction_type": "text", "coverage_pct": "nonnegative"}
FLOODING_SCENARIO_SCHEMA = "plimsoll-flooding-scenario-1"
FLOODING_TANK_FIELDS = {"length_m": "positive", "beam_m": "positive", "height_m": "positive",
    "x_m": "signed", "y_m": "signed", "keel_to_bottom_m": "nonnegative",
    "fluid_density_t_m3": "positive", "initial_volume_m3": "nonnegative"}
FLOODING_CONNECTION_FIELDS = {"x_m": "signed", "y_m": "signed", "z_m": "signed",
    "area_m2": "nonnegative", "discharge_coefficient": "nonnegative",
    "fluid_density_t_m3": "positive", "aperture_height_m": "positive"}


def _diag(diagnostics, path, message, code="extension.invalid", warning=False):
    diagnostics.append(dict(code=code, severity="warning" if warning else "error",
                            path=path, message=message, blocking=not warning))


def _object(value, path, diagnostics):
    if not isinstance(value, dict):
        _diag(diagnostics, path, "must be an object")
        return False
    return True


def _keys(value, allowed, path, diagnostics):
    for key in value.keys() - allowed:
        _diag(diagnostics, f"{path}[{json.dumps(key, ensure_ascii=False)}]", "unsupported optional field")


def _value(value, kind, path, diagnostics, nullable=True):
    if value is None and nullable:
        _diag(diagnostics, path, "value is unknown", "extension.value_unknown", True)
        return False
    if kind == "text":
        valid = isinstance(value, str) and bool(value.strip())
    else:
        valid = (isinstance(value, (int, float)) and not isinstance(value, bool)
                 and math.isfinite(value))
        if valid and kind in ("positive", "count"):
            valid = value > 0
        elif valid and kind in ("nonnegative", "integer"):
            valid = value >= 0
        if valid and kind in ("integer", "count"):
            valid = isinstance(value, int)
    if not valid:
        _diag(diagnostics, path, f"must be a finite {kind} value (booleans are not numbers)")
    return valid


def _metadata(value, path, diagnostics, required=False):
    source, estimate = value.get("source"), value.get("estimate")
    if source is not None and not isinstance(source, (str, dict)):
        _diag(diagnostics, path + ".source", "source must be string, object or null")
    unknown = source in (None, "", {}) or isinstance(source, str) and not source.strip()
    if unknown:
        _diag(diagnostics, path + ".source", "source provenance is unknown",
              "extension.provenance_unknown", not required)
    if estimate is not None and not isinstance(estimate, bool):
        _diag(diagnostics, path + ".estimate", "estimate must be boolean or null")
    elif estimate is None:
        _diag(diagnostics, path + ".estimate", "estimate state is unknown",
              "extension.provenance_unknown", not required)


def _sha256(value, path, diagnostics):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        _diag(diagnostics, path, "must be a lowercase SHA-256 identity")


def _fact(value, kind, path, diagnostics, required=False):
    if not _object(value, path, diagnostics):
        return
    _keys(value, {"value", "source", "estimate"}, path, diagnostics)
    _value(value.get("value"), kind, path + ".value", diagnostics, nullable=not required)
    _metadata(value, path, diagnostics, required)


def _facts(value, fields, path, diagnostics):
    if not _object(value, path, diagnostics):
        return
    _keys(value, set(fields), path, diagnostics)
    for key in value.keys() & fields.keys():
        _fact(value[key], fields[key], path + "." + key, diagnostics)


def _rows(value, path, diagnostics, limit=10000):
    if not isinstance(value, list) or len(value) > limit:
        _diag(diagnostics, path, f"must be an array with at most {limit} entries")
        return []
    seen, rows = set(), []
    for index, row in enumerate(value):
        item_path = f"{path}[{index}]"
        if not _object(row, item_path, diagnostics):
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            _diag(diagnostics, item_path + ".id", "must be a unique nonempty ID")
        else:
            seen.add(identifier)
        rows.append((row, item_path))
    return rows


def _fuel_bindings(value, item_ids, path, diagnostics):
    if not _object(value, path, diagnostics):
        return
    _keys(value, {"coal", "oil"}, path, diagnostics)
    owners = set()
    for fuel, binding in value.items():
        p = path + "." + fuel
        if not _object(binding, p, diagnostics):
            continue
        _keys(binding, {"weight_item_ids", "absent", "source", "estimate"}, p, diagnostics)
        _metadata(binding, p, diagnostics, required=True)
        ids = binding.get("weight_item_ids")
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in item_ids for i in ids):
            _diag(diagnostics, p + ".weight_item_ids", "must link existing ledger item IDs")
            continue
        if len(set(ids)) != len(ids) or owners.intersection(ids):
            _diag(diagnostics, p + ".weight_item_ids", "fuel item ownership must be unique")
        owners.update(ids)
        if "absent" in binding and not isinstance(binding["absent"], bool):
            _diag(diagnostics, p + ".absent", "must be boolean")
        if not ids and binding.get("absent") is not True or ids and binding.get("absent") is True:
            _diag(diagnostics, p, "empty IDs require declared absence; absent fuel cannot own items")


def _page_rows(value, item_ids, path, diagnostics):
    if not isinstance(value, list) or not value:
        _diag(diagnostics, path, "page rows must be a nonempty array")
        return
    seen_rows, seen_items = set(), set()
    for index, row in enumerate(value):
        p = f"{path}[{index}]"
        if not _object(row, p, diagnostics):
            continue
        name = row.get("row")
        if not isinstance(name, str) or not name.strip() or name in seen_rows:
            _diag(diagnostics, p + ".row", "row must have a unique nonempty identifier")
        else:
            seen_rows.add(name)
        if "group" in row and (not isinstance(row["group"], str) or not row["group"].strip()):
            _diag(diagnostics, p + ".group", "group must be a nonempty identifier")
        ids = row.get("weight_item_ids", [])
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in item_ids for i in ids):
            _diag(diagnostics, p + ".weight_item_ids", "must name existing ledger items")
        elif len(set(ids)) != len(ids) or seen_items.intersection(ids):
            _diag(diagnostics, p + ".weight_item_ids", "an item may belong to only one row in a leaf")
        else:
            seen_items.update(ids)
        if "thickness_mm" in row:
            _value(row["thickness_mm"], "nonnegative", p + ".thickness_mm", diagnostics)
        extents = row.get("extents_m")
        if extents is not None and _object(extents, p + ".extents_m", diagnostics):
            _keys(extents, {"aft_m", "fore_m"}, p + ".extents_m", diagnostics)
            for key in ("aft_m", "fore_m"):
                _value(extents.get(key), "signed", p + ".extents_m." + key, diagnostics)
            aft, fore = extents.get("aft_m"), extents.get("fore_m")
            if (all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    and math.isfinite(v) for v in (aft, fore)) and fore <= aft):
                _diag(diagnostics, p + ".extents_m", "fore endpoint must be greater than aft endpoint")
        _metadata(row, p, diagnostics)
        typed = row.get("typed")
        if typed is not None:
            if not _object(typed, p + ".typed", diagnostics):
                continue
            _keys(typed, set(PAGE_ROW_TYPED_FIELDS), p + ".typed", diagnostics)
            for field, supplied in typed.items():
                if field in PAGE_ROW_TYPED_FIELDS and supplied is not None:
                    _value(supplied, PAGE_ROW_TYPED_FIELDS[field], p + ".typed." + field,
                           diagnostics, nullable=False)


def _system_fields(systems, item_ids, diagnostics, weight_groups=()):
    if not isinstance(systems, dict):
        return
    def visit(value, path, fields, below_leaf=False):
        if not isinstance(value, dict):
            return
        boundary = any(key in value for key in ("weight_item_ids", "status", "mass_models"))
        if below_leaf and (boundary or "facts" in value):
            _diag(diagnostics, path, "nested system below a declared system leaf is not allowed")
        if "facts" in value:
            if not boundary:
                _diag(diagnostics, path, "fact-bearing system must explicitly declare its ledger/status boundary")
            _facts(value["facts"], fields, path + ".facts", diagnostics)
            if "weight_item_ids" in value:
                ids = value["weight_item_ids"]
                if (not isinstance(ids, list)
                        or any(not isinstance(i, str) or not i or i not in item_ids for i in ids)
                        or len(set(ids)) != len(ids)):
                    _diag(diagnostics, path + ".weight_item_ids", "must link unique existing ledger item IDs")
        if "page_rows" in value:
            _page_rows(value["page_rows"], item_ids, path + ".page_rows", diagnostics)
        for key, child in value.items():
            # These are leaf payloads, not nested systems; their own validators
            # retain authority over their contents (source remains opaque).
            if key not in {"facts", "mass_models", "source", "fuel_bindings", "variable_load_groups", "page_rows", "rotating_armour_component"}:
                visit(child, f"{path}[{json.dumps(key, ensure_ascii=False)}]", fields,
                      below_leaf or boundary or "facts" in value)
    propulsion = systems.get("propulsion")
    if isinstance(propulsion, dict):
        visit(propulsion, "$.systems.propulsion", PROPULSION_FIELDS)
        if "fuel_bindings" in propulsion:
            _fuel_bindings(propulsion["fuel_bindings"], item_ids, "$.systems.propulsion.fuel_bindings", diagnostics)
        variable = propulsion.get("variable_load_groups")
        if variable is not None:
            path = "$.systems.propulsion.variable_load_groups"
            if _object(variable, path, diagnostics):
                _keys(variable, {"group_ids", "source", "estimate"}, path, diagnostics)
                _metadata(variable, path, diagnostics, required=True)
                groups = {g.get("id") for g in weight_groups if isinstance(g, dict)}
                ids = variable.get("group_ids")
                if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in groups for i in ids) or len(ids) != len(set(ids)):
                    _diag(diagnostics, path + ".group_ids", "must name unique existing loading groups")
    visit(systems.get("weapons"), "$.systems.weapons", WEAPON_FIELDS)
    weapons = systems.get("weapons") or {}
    if isinstance(weapons, dict):
        for battery, leaf in weapons.items():
            if not isinstance(leaf, dict) or leaf.get("rotating_armour_component") is None:
                continue
            path = f"$.systems.weapons.{battery}.rotating_armour_component"
            component = leaf["rotating_armour_component"]
            if not _object(component, path, diagnostics):
                continue
            _keys(component, {"mount_weight_item_id", "mass_t", "source", "estimate"}, path, diagnostics)
            mount_id = component.get("mount_weight_item_id")
            page_rows = leaf.get("page_rows")
            mount_rows = [row for row in page_rows if isinstance(row, dict) and row.get("row") == "mounts"] \
                if isinstance(page_rows, list) else []
            bound = {item for row in mount_rows
                     for item in (row.get("weight_item_ids") if isinstance(row.get("weight_item_ids"), list) else [])
                     if isinstance(item, str)}
            if (not isinstance(mount_id, str) or mount_id not in item_ids
                    or mount_id not in (leaf.get("weight_item_ids") or []) or mount_id not in bound):
                _diag(diagnostics, path + ".mount_weight_item_id",
                      "must name an existing item in this battery's mounts page row")
            _value(component.get("mass_t"), "nonnegative", path + ".mass_t", diagnostics)
            _metadata(component, path, diagnostics, required=component.get("mass_t") is not None)
    visit(systems.get("armour"), "$.systems.armour", ARMOUR_FIELDS)


def _deck(deck, diagnostics):
    path = "$.deck"
    if deck is None or not _object(deck, path, diagnostics):
        return
    _keys(deck, {"source", "estimate", "points", "segments", "facts", "reference_length_m"}, path, diagnostics)
    _metadata(deck, path, diagnostics)
    points = {}
    rows = _rows(deck.get("points"), path + ".points", diagnostics)
    if not rows:
        _diag(diagnostics, path + ".points", "supplied deck requires at least one point")
    for point, p in rows:
        _keys(point, {"id", "x_m", "y_m", "z_m", "source", "estimate", "freeboard_m"}, p, diagnostics)
        for key in ("x_m", "y_m", "z_m"):
            _value(point.get(key), "signed" if key != "z_m" else "nonnegative", p + "." + key, diagnostics)
        if "source" in point or "estimate" in point:
            _metadata(point, p, diagnostics)
        if "freeboard_m" in point:
            # Declared freeboard input (design view). value is a fact: finite and
            # >= 0; null/unknown is allowed and must NOT be substituted with 0.
            # z_m is never read as a freeboard source here.
            _fact(point["freeboard_m"], "nonnegative", p + ".freeboard_m", diagnostics)
        if isinstance(point.get("id"), str):
            points[point["id"]] = point
    for segment, p in _rows(deck.get("segments", []), path + ".segments", diagnostics):
        _keys(segment, {"id", "fore_point_id", "aft_point_id", "source", "estimate"}, p, diagnostics)
        refs = [segment.get(key) for key in ("aft_point_id", "fore_point_id")]
        if any(not isinstance(ref, str) or ref not in points for ref in refs):
            _diag(diagnostics, p, "segment must reference supplied aft and fore point IDs")
        else:
            a, f = (points[ref].get("x_m") for ref in refs)
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, f)) and a >= f:
                _diag(diagnostics, p, "fore point x must exceed aft point x")
        if "source" in segment or "estimate" in segment:
            _metadata(segment, p, diagnostics)
    if "reference_length_m" in deck:
        _fact(deck["reference_length_m"], "positive", path + ".reference_length_m", diagnostics)
    if "facts" in deck:
        _facts(deck["facts"], DECK_FIELDS, path + ".facts", diagnostics)


def _historical(rows, condition_ids, diagnostics):
    quantities = {"shaft_power_kw": {"kW", "shp"}, "displacement_t": {"t", "kg", "long_ton"},
                  "speed_kn": {"kn", "m_s"}, "range_nm": {"nm"}, "draught_m": {"m", "ft"}}
    for row, p in _rows(rows, "$.historical_comparisons", diagnostics):
        _keys(row, {"id", "quantity", "value", "unit", "condition_id", "speed_kn", "source", "estimate",
                    "raw_value", "raw_unit"}, p, diagnostics)
        quantity = row.get("quantity")
        if not isinstance(quantity, str) or quantity not in quantities:
            _diag(diagnostics, p + ".quantity", "unsupported historical comparison quantity")
        else:
            for key in ("unit", "raw_unit"):
                if key in row or key == "unit":
                    if not isinstance(row.get(key), str) or row[key] not in quantities[quantity]:
                        _diag(diagnostics, p + "." + key, "unit does not match comparison quantity")
        _value(row.get("value"), "nonnegative", p + ".value", diagnostics)
        if "raw_value" in row:
            _value(row["raw_value"], "nonnegative", p + ".raw_value", diagnostics)
        if not isinstance(row.get("condition_id"), str) or row["condition_id"] not in condition_ids:
            _diag(diagnostics, p + ".condition_id", "must identify an existing loading condition")
        if "speed_kn" in row or quantity in ("shaft_power_kw", "range_nm"):
            _value(row.get("speed_kn"), "positive", p + ".speed_kn", diagnostics,
                   nullable=quantity not in ("shaft_power_kw", "range_nm"))
        _metadata(row, p, diagnostics)


def _resistance(rows, diagnostics):
    for row, p in _rows(rows, "$.resistance_scenarios", diagnostics, 201):
        _keys(row, {"id", "method", "source", "estimate", "attitude_policy", "inputs", "input_provenance",
                    "qpc", "qpc_sensitivity", "table_id", "table_sha256", "friction_method",
                    "interpolation_method", "speed_conversion_method"}, p, diagnostics)
        _metadata(row, p, diagnostics, required=True)
        method = row.get("method")
        if method not in ("holtrop_mennen_1982", "taylor_gertler_source_axis_strict"):
            _diag(diagnostics, p + ".method", "explicit supported resistance method required")
        if row.get("attitude_policy") not in ("strict_upright", "selected_plane_longitudinal_trim_proxy_v1"):
            _diag(diagnostics, p + ".attitude_policy", "explicit supported attitude policy required")
        for key, expected in (("friction_method", "schoenherr_implicit_ittc_0.242"),
                              ("interpolation_method", "taylor_gertler_source_axis_strict"),
                              ("speed_conversion_method", "international_knot_exact")):
            if key in row and row[key] != expected:
                _diag(diagnostics, p + "." + key, "unsupported canonical method selection")
        if "table_id" in row:
            _value(row["table_id"], "text", p + ".table_id", diagnostics)
        if "table_sha256" in row:
            _sha256(row["table_sha256"], p + ".table_sha256", diagnostics)
        if "qpc" in row:
            _fact(row["qpc"], "positive", p + ".qpc", diagnostics, required=True)
        if "qpc_sensitivity" in row:
            grid = row["qpc_sensitivity"]
            if _object(grid, p + ".qpc_sensitivity", diagnostics):
                _keys(grid, {"values", "source", "estimate"}, p + ".qpc_sensitivity", diagnostics)
                _metadata(grid, p + ".qpc_sensitivity", diagnostics, required=True)
                values = grid.get("values")
                if not isinstance(values, list) or not 1 <= len(values) <= 21:
                    _diag(diagnostics, p + ".qpc_sensitivity.values", "requires 1..21 positive increasing values")
                else:
                    valid = [_value(v, "positive", p + f".qpc_sensitivity.values[{i}]", diagnostics, False)
                             for i, v in enumerate(values)]
                    if all(valid) and any(b <= a for a, b in zip(values, values[1:])):
                        _diag(diagnostics, p + ".qpc_sensitivity.values", "must be strictly increasing")
        inputs = row.get("inputs", {})
        provenance = row.get("input_provenance", {})
        if not _object(inputs, p + ".inputs", diagnostics) or not _object(provenance, p + ".input_provenance", diagnostics):
            continue
        allowed = set(RESISTANCE_INPUTS) | {"appendages", "bow_thruster"}
        _keys(inputs, allowed, p + ".inputs", diagnostics)
        _keys(provenance, set(inputs), p + ".input_provenance", diagnostics)
        for key, value in inputs.items():
            ip = p + ".inputs." + key
            if key in RESISTANCE_INPUTS:
                _value(value, RESISTANCE_INPUTS[key], ip, diagnostics)
            elif key == "appendages" and value is not None:
                if not isinstance(value, list):
                    _diag(diagnostics, ip, "must be an explicit array, [] for declared absence")
                else:
                    for i, app in enumerate(value):
                        ap = ip + f"[{i}]"
                        if _object(app, ap, diagnostics):
                            _keys(app, {"area_m2", "factor"}, ap, diagnostics)
                            _value(app.get("area_m2"), "nonnegative", ap + ".area_m2", diagnostics)
                            _value(app.get("factor"), "positive", ap + ".factor", diagnostics)
            elif key == "bow_thruster" and value is not None:
                if _object(value, ip, diagnostics):
                    _keys(value, {"present", "diameter_m", "coefficient"}, ip, diagnostics)
                    if not isinstance(value.get("present"), bool):
                        _diag(diagnostics, ip + ".present", "explicit boolean presence required")
                    for name in ("diameter_m", "coefficient"):
                        if name in value or value.get("present") is True:
                            _value(value.get(name), "positive", ip + "." + name, diagnostics)
                    if value.get("present") is False and any(name in value for name in ("diameter_m", "coefficient")):
                        _diag(diagnostics, ip, "absent thruster cannot carry increment geometry")
            if value is not None:
                meta = provenance.get(key)
                if _object(meta, p + ".input_provenance." + key, diagnostics):
                    _keys(meta, {"source", "estimate"}, p + ".input_provenance." + key, diagnostics)
                    _metadata(meta, p + ".input_provenance." + key, diagnostics, required=True)
        af, ff = inputs.get("x_aft_perpendicular_m"), inputs.get("x_fore_perpendicular_m")
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (af, ff)) and af >= ff:
            _diag(diagnostics, p + ".inputs", "fore perpendicular must be forward of aft perpendicular")


def _endurance(rows, diagnostics):
    for row, p in _rows(rows, "$.endurance_scenarios", diagnostics, 201):
        _keys(row, {"id", "method", "speed_kn", "power_kw", "fuels", "source", "estimate"}, p, diagnostics)
        if row.get("method") != "steady_simultaneous_fuel_consumption":
            _diag(diagnostics, p + ".method", "explicit steady simultaneous fuel method required")
        _metadata(row, p, diagnostics, required=True)
        if not isinstance(row.get("source"), str):
            _diag(diagnostics, p + ".source", "endurance kernel requires a source string")
        for key in ("speed_kn", "power_kw"):
            _value(row.get(key), "positive", p + "." + key, diagnostics)
        fuels = row.get("fuels")
        if not _object(fuels, p + ".fuels", diagnostics):
            continue
        _keys(fuels, {"coal", "oil"}, p + ".fuels", diagnostics)
        for fuel in ("coal", "oil"):
            config, fp = fuels.get(fuel), p + ".fuels." + fuel
            if not _object(config, fp, diagnostics):
                continue
            _keys(config, {"required", "burn_t_per_day", "reserve_t"}, fp, diagnostics)
            if not isinstance(config.get("required"), bool):
                _diag(diagnostics, fp + ".required", "must declare boolean required state")
            for key in ("burn_t_per_day", "reserve_t"):
                _value(config.get(key), "nonnegative", fp + "." + key, diagnostics)
            rate = config.get("burn_t_per_day")
            if isinstance(rate, (int, float)) and rate > 0 and config.get("required") is not True:
                _diag(diagnostics, fp, "positive burn requires required=true")


def _flooding_sea(value, path, diagnostics):
    if not _object(value, path, diagnostics):
        return None
    _keys(value, {"id", "fluid_density_t_m3", "source", "estimate"}, path, diagnostics)
    identity = value.get("id")
    if not isinstance(identity, str) or not identity.strip():
        _diag(diagnostics, path + ".id", "sea must declare a nonempty id")
        identity = None
    if "fluid_density_t_m3" in value:
        _value(value["fluid_density_t_m3"], "positive", path + ".fluid_density_t_m3", diagnostics)
    _metadata(value, path, diagnostics)
    return identity


def _flooding_tanks(value, sea_id, item_ids, path, diagnostics):
    """Return declared tank IDs; unknown geometry is retained, never substituted."""
    if not isinstance(value, list):
        _diag(diagnostics, path, "scenario tanks must be an array (absent is unknown)",
              "extension.value_unknown", True)
        return set()
    declared, seen = set(), set()
    for index, tank in enumerate(value):
        p = f"{path}[{index}]"
        if not _object(tank, p, diagnostics):
            continue
        identity = tank.get("id")
        if not isinstance(identity, str) or not identity.strip():
            _diag(diagnostics, p + ".id", "tank must declare a nonempty id")
            continue
        if identity in seen:
            _diag(diagnostics, p + ".id", "tank IDs must be unique within the scenario")
        seen.add(identity)
        declared.add(identity)
        if identity == sea_id:
            _diag(diagnostics, p + ".id", "tank ID must differ from the sea node ID")
        if identity in item_ids:
            _diag(diagnostics, p + ".id",
                  "tank ID collides with a ledger weight item; scenario water is additional mass "
                  "and the same liquid must not be counted twice")
        _keys(tank, {"id", "label"} | set(FLOODING_TANK_FIELDS)
              | {"permeability", "free_surface", "source", "estimate"}, p, diagnostics)
        for key, kind in FLOODING_TANK_FIELDS.items():
            if key in tank:
                _value(tank[key], kind, f"{p}.{key}", diagnostics)
        if "permeability" in tank:
            _value(tank["permeability"], "nonnegative", p + ".permeability", diagnostics)
            permeability = tank["permeability"]
            if (isinstance(permeability, (int, float)) and not isinstance(permeability, bool)
                    and permeability > 1):
                _diag(diagnostics, p + ".permeability", "permeability must be within [0, 1]")
        if tank.get("free_surface") is not None and not isinstance(tank["free_surface"], bool):
            _diag(diagnostics, p + ".free_surface", "free surface state must be boolean or null")
        _metadata(tank, p, diagnostics)
    return declared


def _flooding_connections(value, node_ids, path, diagnostics):
    if not isinstance(value, list):
        _diag(diagnostics, path, "scenario connections must be an array (absent is unknown)",
              "extension.value_unknown", True)
        return
    seen = set()
    for index, edge in enumerate(value):
        p = f"{path}[{index}]"
        if not _object(edge, p, diagnostics):
            continue
        identity = edge.get("id")
        if not isinstance(identity, str) or not identity.strip():
            _diag(diagnostics, p + ".id", "connection must declare a nonempty id")
        elif identity in seen:
            _diag(diagnostics, p + ".id", "connection IDs must be unique within the scenario")
        else:
            seen.add(identity)
        _keys(edge, {"id", "from", "to", "open", "source", "estimate"}
              | set(FLOODING_CONNECTION_FIELDS), p, diagnostics)
        for field in ("from", "to"):
            reference = edge.get(field)
            if not isinstance(reference, str) or reference not in node_ids:
                _diag(diagnostics, f"{p}.{field}",
                      "endpoint must reference the scenario sea node or a declared tank")
        if isinstance(edge.get("from"), str) and edge.get("from") == edge.get("to"):
            _diag(diagnostics, p, "connection must join two distinct nodes")
        for key, kind in FLOODING_CONNECTION_FIELDS.items():
            if key in edge:
                _value(edge[key], kind, f"{p}.{key}", diagnostics)
        if "discharge_coefficient" in edge:
            coefficient = edge["discharge_coefficient"]
            if (isinstance(coefficient, (int, float)) and not isinstance(coefficient, bool)
                    and coefficient > 1):
                _diag(diagnostics, p + ".discharge_coefficient",
                      "discharge coefficient must be within [0, 1]")
        if edge.get("open") is not None and not isinstance(edge["open"], bool):
            _diag(diagnostics, p + ".open", "connection open state must be boolean")
        _metadata(edge, p, diagnostics)


def _flooding_openings(value, path, diagnostics):
    # An explicit null is the sanctioned bridge for preserved unknown opening
    # knowledge; an array is supplied knowledge (possibly of no open point).
    if value is None:
        return
    if not isinstance(value, list):
        _diag(diagnostics, path, "scenario openings must be an array or null")
        return
    seen = set()
    for index, opening in enumerate(value):
        p = f"{path}[{index}]"
        if not _object(opening, p, diagnostics):
            continue
        _keys(opening, {"id", "open", "x_m", "y_m", "z_m", "kind", "source", "estimate"},
              p, diagnostics)
        identity = opening.get("id")
        if not isinstance(identity, str) or not identity.strip():
            _diag(diagnostics, p + ".id", "opening must declare a nonempty id")
        elif identity in seen:
            _diag(diagnostics, p + ".id", "opening IDs must be unique")
        else:
            seen.add(identity)
        if not isinstance(opening.get("open"), bool):
            _diag(diagnostics, p + ".open", "opening state must be explicitly boolean")
        for key in ("x_m", "y_m", "z_m"):
            _value(opening.get(key), "signed", f"{p}.{key}", diagnostics)
        _metadata(opening, p, diagnostics)


def _flooding_scenarios(value, item_ids, diagnostics):
    """Structurally validate saved flooding scenario drafts without solving."""
    for row, p in _rows(value, "$.flooding_scenarios", diagnostics, 201):
        _keys(row, {"id", "schema", "label", "duration_s", "time_step_s", "source", "estimate",
                    "sea", "tanks", "connections", "openings"}, p, diagnostics)
        if row.get("schema") != FLOODING_SCENARIO_SCHEMA:
            _diag(diagnostics, p + ".schema",
                  f"flooding scenario schema must be {FLOODING_SCENARIO_SCHEMA!r}")
        for key, kind in (("duration_s", "nonnegative"), ("time_step_s", "positive")):
            if key in row:
                _value(row[key], kind, f"{p}.{key}", diagnostics)
        _metadata(row, p, diagnostics)
        sea_id = _flooding_sea(row.get("sea"), p + ".sea", diagnostics)
        tank_ids = _flooding_tanks(row.get("tanks"), sea_id, item_ids, p + ".tanks", diagnostics)
        node_ids = tank_ids | ({sea_id} if isinstance(sea_id, str) else set())
        _flooding_connections(row.get("connections"), node_ids, p + ".connections", diagnostics)
        if "openings" in row:
            _flooding_openings(row["openings"], p + ".openings", diagnostics)


def validate_acceptance(record, condition_id, field, nominal, path):
    """Validate a stored audit record; this is not authorization to apply a proposal."""
    diagnostics = []
    if not _object(record, path, diagnostics):
        return diagnostics
    _keys(record, {"operation", "condition_id", "source_system_id", "source_model_id", "formula",
                   "method", "inputs", "input_provenance", "previous_mass_t", "new_mass_t",
                   "project_fingerprint", "input_fingerprint", "request_fingerprint"}, path, diagnostics)
    if record.get("operation") != "replace_weight_item_mass" or field != "mass_t":
        _diag(diagnostics, path, "acceptance is only defined for a mass replacement")
    if record.get("condition_id") != condition_id:
        _diag(diagnostics, path + ".condition_id", "acceptance must name its containing condition")
    for key in ("source_system_id", "source_model_id", "formula"):
        _value(record.get(key), "text", path + "." + key, diagnostics, False)
    if "method" in record and record["method"] not in (
            "volume_density_mass", "plate_area_thickness_density_mass", "counted_unit_mass", "counted_ammunition_mass"):
        _diag(diagnostics, path + ".method", "unsupported physical model method")
    for key in ("project_fingerprint", "input_fingerprint", "request_fingerprint"):
        _sha256(record.get(key), path + "." + key, diagnostics)
    _value(record.get("previous_mass_t"), "nonnegative", path + ".previous_mass_t", diagnostics, False)
    _value(record.get("new_mass_t"), "nonnegative", path + ".new_mass_t", diagnostics, False)
    if record.get("new_mass_t") != nominal:
        _diag(diagnostics, path + ".new_mass_t", "accepted mass must equal the numeric override")
    inputs, provenance = record.get("inputs"), record.get("input_provenance")
    if _object(inputs, path + ".inputs", diagnostics) and _object(provenance, path + ".input_provenance", diagnostics):
        _keys(provenance, set(inputs), path + ".input_provenance", diagnostics)
        for key, value in inputs.items():
            _value(value, "text" if key in ("count_field", "count_basis") else "nonnegative",
                   path + ".inputs." + str(key), diagnostics, False)
            meta, mp = provenance.get(key), path + ".input_provenance." + str(key)
            if _object(meta, mp, diagnostics):
                _metadata(meta, mp, diagnostics, required=True)
    return diagnostics


def _condition_definitions(project, item_ids, diagnostics):
    conditions = project.get("loading_conditions")
    if not isinstance(conditions, list):
        return
    by_id = {c.get("id"): c for c in conditions if isinstance(c, dict) and isinstance(c.get("id"), str)}
    for index, condition in enumerate(conditions):
        if not isinstance(condition, dict) or "definition" not in condition:
            continue
        definition = condition["definition"]
        path = f"$.loading_conditions[{index}].definition"
        if not _object(definition, path, diagnostics):
            continue
        _keys(definition, {"kind", "base_condition_id", "excluded_item_ids", "source", "estimate"}, path, diagnostics)
        if definition.get("kind") not in ("standard", "light"):
            _diag(diagnostics, path + ".kind", "must explicitly declare standard or light study")
        base_id = definition.get("base_condition_id")
        base = by_id.get(base_id) if isinstance(base_id, str) else None
        if base is None or base is condition or "definition" in base:
            _diag(diagnostics, path + ".base_condition_id", "must name another non-derived loading condition; chaining is not supported")
        ids = definition.get("excluded_item_ids")
        if (not isinstance(ids, list) or any(not isinstance(i, str) or i not in item_ids for i in ids)
                or len(set(ids)) != len(ids)):
            _diag(diagnostics, path + ".excluded_item_ids", "must explicitly list unique existing ledger items; an empty list means no deduction")
        if condition.get("overrides") or condition.get("override_provenance"):
            _diag(diagnostics, path, "a subtraction definition cannot also supply overrides or override provenance")
        _metadata(definition, path, diagnostics, required=True)


def validate_extensions(project, item_ids):
    """Return all optional-field diagnostics; never mutate or calculate the project."""
    diagnostics = []
    compartments = project.get("compartments")
    if isinstance(compartments, list):
        seen = set()
        for index, compartment in enumerate(compartments):
            path = f"$.compartments[{index}]"
            if not _object(compartment, path, diagnostics):
                continue
            identity = compartment.get("id")
            if not isinstance(identity, str) or not identity.strip():
                _diag(diagnostics, path + ".id", "compartment must declare a nonempty id")
            elif identity in seen:
                _diag(diagnostics, path + ".id", "compartment IDs must be unique")
            else:
                seen.add(identity)
    if "metadata" in project:
        _facts(project["metadata"], METADATA_FIELDS, "$.metadata", diagnostics)
    hull = project.get("hull")
    if isinstance(hull, dict) and "design_facts" in hull:
        _facts(hull["design_facts"], HULL_DESIGN_FIELDS, "$.hull.design_facts", diagnostics)
        supplied = hull["design_facts"]
        coefficient = supplied.get("block_coeff_deep", {}) if isinstance(supplied, dict) else {}
        value = coefficient.get("value") if isinstance(coefficient, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 1:
            _diag(diagnostics, "$.hull.design_facts.block_coeff_deep.value", "block coefficient must not exceed one")
    _condition_definitions(project, item_ids, diagnostics)
    if "display_preferences" in project:
        prefs = project["display_preferences"]
        if _object(prefs, "$.display_preferences", diagnostics):
            choices = {"length": {"m", "ft"}, "mass": {"t", "kg", "long_ton"},
                       "power": {"kW", "shp"}, "speed": {"kn", "m_s"}, "angle": {"deg", "rad"}}
            _keys(prefs, set(choices), "$.display_preferences", diagnostics)
            for key in prefs.keys() & choices.keys():
                if not isinstance(prefs[key], str) or prefs[key] not in choices[key]:
                    _diag(diagnostics, "$.display_preferences." + key, "unsupported display unit for this dimension")
    _system_fields(project.get("systems"), item_ids, diagnostics, project.get("weight_groups", []))
    armour = (project.get("systems") or {}).get("armour") or {}
    fixed = armour.get("fixed") or {}
    coverage = fixed.get("deck_coverage")
    if coverage is not None:
        path = "$.systems.armour.fixed.deck_coverage"
        if _object(coverage, path, diagnostics):
            fields = {"covered_plan_area_m2": "nonnegative", "reference_plan_area_m2": "positive"}
            _keys(coverage, set(fields), path, diagnostics)
            for key, kind in fields.items():
                if key in coverage:
                    fact = coverage[key]
                    _fact(fact, kind, path + "." + key, diagnostics,
                          required=isinstance(fact, dict) and fact.get("value") is not None)
            covered_fact = coverage.get("covered_plan_area_m2")
            reference_fact = coverage.get("reference_plan_area_m2")
            covered = covered_fact.get("value") if isinstance(covered_fact, dict) else None
            reference = reference_fact.get("value") if isinstance(reference_fact, dict) else None
            if (all(isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) for value in (covered, reference))
                    and covered > reference):
                _diag(diagnostics, path, "covered plan area cannot exceed reference plan area")
    study = fixed.get("minimum_main_belt")
    if study is not None:
        path = "$.systems.armour.fixed.minimum_main_belt"
        if _object(study, path, diagnostics):
            _keys(study, {"protected_compartment_ids", "aft_margin_m", "fore_margin_m",
                          "inventory_complete", "source", "estimate"}, path, diagnostics)
            ids = study.get("protected_compartment_ids")
            available = {c.get("id") for c in project.get("compartments", []) if isinstance(c, dict)}
            if (not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in available for i in ids)
                    or len(ids) != len(set(ids))):
                _diag(diagnostics, path + ".protected_compartment_ids",
                      "must list unique existing protected compartment IDs")
            for key in ("aft_margin_m", "fore_margin_m"):
                _value(study.get(key), "nonnegative", path + "." + key, diagnostics, False)
            if not isinstance(study.get("inventory_complete"), bool):
                _diag(diagnostics, path + ".inventory_complete", "must explicitly state completeness")
            _metadata(study, path, diagnostics, required=True)
            if study.get("estimate") is not True:
                _diag(diagnostics, path + ".estimate", "this independent engineering estimate must be marked estimated")
    if "deck" in project:
        _deck(project["deck"], diagnostics)
    conditions = project.get("loading_conditions")
    ids = {row["id"] for row in conditions if isinstance(row, dict) and isinstance(row.get("id"), str)} if isinstance(conditions, list) else set()
    if "historical_comparisons" in project:
        _historical(project["historical_comparisons"], ids, diagnostics)
    if "resistance_scenarios" in project:
        _resistance(project["resistance_scenarios"], diagnostics)
    if "endurance_scenarios" in project:
        _endurance(project["endurance_scenarios"], diagnostics)
    if "flooding_scenarios" in project:
        _flooding_scenarios(project["flooding_scenarios"], item_ids, diagnostics)
    return diagnostics
