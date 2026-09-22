"""Validate optional calculation-core inputs without invoking numerical kernels."""

import json
import math


METADATA_FIELDS = {"country": "text", "type": "text", "design_year": "integer",
                   "laid_down_year": "integer", "engine_built_year": "integer"}
PROPULSION_FIELDS = {"shafts": "count", "boilers": "count", "design_power_kw": "positive",
    "trial_power_kw": "positive", "max_speed_kn": "positive", "cruise_speed_kn": "positive",
    "engine_description": "text", "boiler_description": "text", "engine_built_year": "integer"}
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


def _system_fields(systems, item_ids, diagnostics):
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
        for key, child in value.items():
            # These are leaf payloads, not nested systems; their own validators
            # retain authority over their contents (source remains opaque).
            if key not in {"facts", "mass_models", "source", "fuel_bindings"}:
                visit(child, f"{path}[{json.dumps(key, ensure_ascii=False)}]", fields,
                      below_leaf or boundary or "facts" in value)
    propulsion = systems.get("propulsion")
    if isinstance(propulsion, dict):
        visit(propulsion, "$.systems.propulsion", PROPULSION_FIELDS)
        if "fuel_bindings" in propulsion:
            _fuel_bindings(propulsion["fuel_bindings"], item_ids, "$.systems.propulsion.fuel_bindings", diagnostics)
    visit(systems.get("weapons"), "$.systems.weapons", WEAPON_FIELDS)
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
        _keys(point, {"id", "x_m", "y_m", "z_m", "source", "estimate"}, p, diagnostics)
        for key in ("x_m", "y_m", "z_m"):
            _value(point.get(key), "signed" if key != "z_m" else "nonnegative", p + "." + key, diagnostics)
        if "source" in point or "estimate" in point:
            _metadata(point, p, diagnostics)
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


def validate_extensions(project, item_ids):
    """Return all optional-field diagnostics; never mutate or calculate the project."""
    diagnostics = []
    if "metadata" in project:
        _facts(project["metadata"], METADATA_FIELDS, "$.metadata", diagnostics)
    if "display_preferences" in project:
        prefs = project["display_preferences"]
        if _object(prefs, "$.display_preferences", diagnostics):
            choices = {"length": {"m", "ft"}, "mass": {"t", "kg", "long_ton"},
                       "power": {"kW", "shp"}, "speed": {"kn", "m_s"}, "angle": {"deg", "rad"}}
            _keys(prefs, set(choices), "$.display_preferences", diagnostics)
            for key in prefs.keys() & choices.keys():
                if not isinstance(prefs[key], str) or prefs[key] not in choices[key]:
                    _diag(diagnostics, "$.display_preferences." + key, "unsupported display unit for this dimension")
    _system_fields(project.get("systems"), item_ids, diagnostics)
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
    return diagnostics
