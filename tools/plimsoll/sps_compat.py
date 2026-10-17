# -*- coding: utf-8 -*-
"""SpringSharp 3b3 兼容协调器：声明校验、依赖图编排与编辑路由。

只做三件事，都是纯函数（无 I/O、无工程写入、不修改输入）：

- ``normalize(design)``：校验原兼容声明 ``sps_3b3_design``；未知/padding 键诊断，
  已知部分保留为纯预览；值按 ``sship_fields`` 注册表种类严格校验，``None`` 是未知；
- ``compute(design)``：按 船体→部件→动力→原性能图 的顺序编排，输出原 numeric
  字段命名；缺依赖给 ``null`` + 诊断，不臆造 0；
- ``apply_edit(design, command)``：把命令路由到 ``sps_hull`` / 部件 / 动力单元，
  通用 ``set_parameter`` / ``set_scale`` / ``set_notes`` 由本模块处理，返回新声明与预览。

性能图照抄 ``PerformanceControl.cs``（recoilCalc / flotationCalc 复用已验收的
``sps_performance``）。原 C# 只读比对，本文件不含恢复源码。原程序集 SHA256
``82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc``。

已知边界：本单元不声明与原程序等价；部件/动力单元的 native 字段名按其 brief
契约读取，缺失即 ``null``。非有限原结果用 ``null`` + 原因表示，不伪装健康 0。
"""
from __future__ import annotations

import copy
import importlib
import math
import json
from typing import Any, Mapping

if __package__:
    from . import sship_fields, sps_field_catalog, sps_performance, sps_single
else:
    import sship_fields
    import sps_field_catalog
    import sps_performance
    import sps_single

SCHEMA = "plimsoll-sps3b3-design-1"
RESULT_SCHEMA = "plimsoll-sps3b3-result-1"
METHOD_VERSION = "sps-3b3-compat-v1"

SOURCE_SHA256 = "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc"

TON = 35.0          # 每长吨海水立方英尺
POUND2TON = 2240.0  # MainForm 常数

_ROOT_KEYS = ("schema", "source", "parameters", "editing", "notes")
_EDITING_KEYS = ("length_driver", "overall_length", "displacement_driver",
                 "normal_displacement_lt", "depth_locked", "depths",
                 "bulkhead_beam_mode", "power_locked", "power_hp", "locked_bunker_lt", "locked_shell_groups",
                 "armour_read_context", "deep_waterplane_ft2", "submerged_casemate", "shell_weight_lb")
_DRIVERS = {
    "length_driver": ("waterline", "overall"),
    "displacement_driver": ("block", "displacement"),
    "bulkhead_beam_mode": ("follow_hull", "fixed"),
}

# 有界拷贝限制（防溢出/超大 payload）。
MAX_TEXT = 200_000
MAX_TOTAL_BYTES = 1_048_576
MAX_RECORDS = 10_000

_PARAMETER_NAMES = frozenset(sship_fields.NAMES[:sship_fields.PADDING_FIRST])

_RESULT_SECTIONS = ("hull", "freeboard", "guns", "auxiliary", "armour", "engine",
                    "performance")


# --------------------------------------------------------------- diagnostics

def _diag(diags, code, severity, field, message):
    diags.append({"code": code, "severity": severity, "field": field, "message": message})


def _status_from(diags, values, fatal=False):
    if fatal:
        return "unavailable"
    if any(d["severity"] == "error" for d in diags):
        return "partial"
    if any(value is None for value in values):
        return "partial"
    return "available"


def _is_number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
    except (ValueError, OverflowError):
        return False


def _number(value):
    return float(value) if _is_number(value) else None


# ---------------------------------------------------------- bounded copying

def _bounded_copy(value, diags, path, counter, depth=0, seen=None):
    """JSON-safe deep copy with size/count/text bounds; never raises."""
    if seen is None:
        seen=set()
    counter[0] += 1
    if counter[0] > MAX_RECORDS or depth > 64:
        if counter[0] <= MAX_RECORDS+1:
            _diag(diags,'input_bound','error',path,'Design exceeds the record or nesting limit')
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            _diag(diags, "non_finite", "error", path,
                  "%s must be a finite number" % path)
            return None
        if isinstance(value, int) and abs(value) > 2 ** 63:
            _diag(diags, "out_of_range", "error", path, "%s is too large" % path)
            return None
        return value
    if isinstance(value, str):
        if len(value) > MAX_TEXT:
            _diag(diags, "text_too_long", "error", path,
                  "%s exceeds %d characters" % (path, MAX_TEXT))
            return value[:MAX_TEXT]
        return value
    if isinstance(value, Mapping):
        if id(value) in seen:
            _diag(diags,'cyclic_input','error',path,'Design must be acyclic JSON')
            return None
        seen.add(id(value))
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _diag(diags, "invalid_key", "error", path,
                      "%s has a non-string key" % path)
                continue
            out[key] = _bounded_copy(item, diags, "%s.%s" % (path, key), counter, depth+1, seen)
            if counter[0] > MAX_RECORDS:break
        seen.remove(id(value))
        return out
    if isinstance(value, (list, tuple)):
        if id(value) in seen:
            _diag(diags,'cyclic_input','error',path,'Design must be acyclic JSON')
            return None
        seen.add(id(value));out=[]
        for i,item in enumerate(value):
            out.append(_bounded_copy(item,diags,'%s[%d]'%(path,i),counter,depth+1,seen))
            if counter[0] > MAX_RECORDS:break
        seen.remove(id(value))
        return out
    _diag(diags, "not_json_safe", "error", path,
          "%s has unsupported type %s" % (path, type(value).__name__))
    return None


# --------------------------------------------------------------- normalize

def _validate_parameter(name, value, diags, path):
    index = sship_fields.NAMES.index(name)
    kind = sship_fields.KINDS[index]
    if value is None:
        return None
    field = "%s.parameters.%s" % (path, name)
    if kind == sship_fields.TEXT:
        if not isinstance(value, str):
            _diag(diags, "invalid_parameter_type", "error", field,
                  "%s must be text or null" % name)
            return None
        if len(value) > MAX_TEXT:
            _diag(diags, "text_too_long", "error", field, "%s is too long" % name)
            return value[:MAX_TEXT]
        return value
    if kind == sship_fields.BOOLEAN:
        if isinstance(value, bool):
            return value
        _diag(diags, "invalid_parameter_type", "error", field,
              "%s must be a boolean or null" % name)
        return None
    if kind == sship_fields.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            _diag(diags, "invalid_parameter_type", "error", field,
                  "%s must be a strict integer or null" % name)
            return None
        return int(value)
    if kind in (sship_fields.ENUM, sship_fields.SELECTOR):
        if isinstance(value, bool) or not isinstance(value, int):
            _diag(diags, "invalid_parameter_type", "error", field,
                  "%s must be a selection index or null" % name)
            return None
        choices = sps_field_catalog.catalog()["fields"].get(name, {}).get("choices")
        low = -1 if kind == sship_fields.ENUM else 0
        high = (len(choices) - 1) if choices else 1
        if not low <= value <= high:
            _diag(diags, "parameter_out_of_range", "error", field,
                  "%s index %d outside %d..%d" % (name, value, low, high))
            return None
        return int(value)
    # NUMBER
    if _is_number(value):
        return float(value)
    _diag(diags, "invalid_parameter_type", "error", field,
          "%s must be a finite number or null" % name)
    return None


def _validate_editing(editing, diags, path):
    if editing is None:
        return {}
    if not isinstance(editing, Mapping):
        _diag(diags, "invalid_editing", "error", "%s.editing" % path,
              "editing must be a mapping or null")
        return {}
    out = {}
    for key, value in editing.items():
        field = "%s.editing.%s" % (path, key)
        if key not in _EDITING_KEYS:
            _diag(diags, "unknown_editing_key", "error", field,
                  "unknown editing key %r" % (key,))
            continue
        if key in _DRIVERS:
            if value is None:
                continue
            if value in _DRIVERS[key]:
                out[key] = value
            else:
                _diag(diags, "invalid_editing", "error", field,
                      "%s must be one of %s" % (key, list(_DRIVERS[key])))
        elif key in ("depth_locked", "power_locked", "submerged_casemate"):
            if isinstance(value, bool):
                out[key] = value
            elif value is not None:
                _diag(diags, "invalid_editing", "error", field,
                      "%s must be a boolean or null" % key)
        elif key == 'armour_read_context':
            if isinstance(value, Mapping) and not set(value)-{'belt_main_cwp','belt_upper_cwp','deck_machinery_lt','belt_height_ft'} and all(v is None or _is_number(v) for v in value.values()):
                out[key]=dict(value)
            else:
                _diag(diags,'invalid_editing','error',field,'Armour read context requires known finite scalars or null')
        elif key=='shell_weight_lb':
            if isinstance(value,Mapping) and set(value)<=set('12345') and all(v is None or _is_number(v) for v in value.values()):
                out[key]=dict(value)
            else:
                _diag(diags,'invalid_editing','error',field,'Shell snapshots need groups 1..5 and finite values or null')
        elif key == 'locked_shell_groups':
            if isinstance(value, list) and len(value) <= 5 and all(type(item) is int and 1 <= item <= 5 for item in value):
                out[key] = sorted(set(value))
            else:
                _diag(diags, 'invalid_editing', 'error', field, 'locked_shell_groups requires group numbers 1..5')
        elif key == "depths":
            if value is None:
                continue
            if isinstance(value, Mapping):
                out[key] = _bounded_copy(value, diags, field, [0])
            elif isinstance(value, (list, tuple)):
                out[key] = _bounded_copy(list(value), diags, field, [0])
            else:
                _diag(diags, "invalid_editing", "error", field,
                      "depths must be a mapping or list")
        else:
            if value is None:
                continue
            if _is_number(value):
                out[key] = float(value)
            else:
                _diag(diags, "invalid_editing", "error", field,
                      "%s must be a finite number or null" % key)
    return out


def normalize(design: dict) -> dict:
    """Validate a compatibility declaration. Never raises; inputs not mutated."""
    diags: list = []
    fatal = False
    if not isinstance(design, Mapping):
        _diag(diags, "invalid_root", "error", "$",
              "design must be a mapping, got %s" % type(design).__name__)
        return {"design": {"schema": None, "source": None, "parameters": {},
                           "editing": {}, "notes": None},
                "status": "unavailable", "diagnostics": diags}

    counter = [0]
    total = _bounded_copy(design, diags, "$", counter)
    try:
        if len(json.dumps(total,ensure_ascii=False).encode('utf-8')) > MAX_TOTAL_BYTES:
            _diag(diags,'input_bound','error','$','Design exceeds 1 MiB')
            fatal=True
    except (ValueError, TypeError, UnicodeError):
        fatal=True
    if not isinstance(total, Mapping):
        fatal = True
        total = {}

    for key in total:
        if key not in _ROOT_KEYS:
            _diag(diags, "unknown_key", "error", "$.%s" % key,
                  "unknown root key %r; allowed: %s" % (key, list(_ROOT_KEYS)))
            fatal = True

    schema = total.get("schema")
    if schema is None:
        _diag(diags, "missing_schema", "error", "$.schema",
              "schema is required and must be %r" % SCHEMA)
        schema_out = None
    elif not isinstance(schema, str):
        _diag(diags, "invalid_type", "error", "$.schema", "schema must be a string")
        schema_out = None
    elif schema != SCHEMA:
        _diag(diags, "wrong_schema", "error", "$.schema",
              "schema %r is not %r" % (schema, SCHEMA))
        schema_out = None
    else:
        schema_out = SCHEMA

    source = total.get("source")
    if source is not None and not isinstance(source, str):
        _diag(diags, "invalid_type", "error", "$.source", "source must be a string or null")
        source = None
    if isinstance(source, str) and len(source) > MAX_TEXT:
        source = source[:MAX_TEXT]

    notes = total.get("notes")
    if notes is not None and not isinstance(notes, str):
        _diag(diags, "invalid_type", "error", "$.notes", "notes must be a string or null")
        notes = None
    if isinstance(notes, str) and len(notes) > MAX_TEXT:
        notes = notes[:MAX_TEXT]

    raw_params = total.get("parameters")
    parameters = {}
    if raw_params is None:
        pass
    elif not isinstance(raw_params, Mapping):
        _diag(diags, "invalid_type", "error", "$.parameters",
              "parameters must be a mapping or null")
    else:
        for name, value in raw_params.items():
            if not isinstance(name, str) or name not in _PARAMETER_NAMES:
                _diag(diags, "unknown_parameter", "error",
                      "$.parameters.%s" % name,
                      "unknown or padding parameter %r" % (name,))
                continue
            parameters[name] = _validate_parameter(name, value, diags, "$")

    editing = _validate_editing(total.get("editing"), diags, "$")

    normalized = {
        "schema": schema_out,
        "source": source,
        "parameters": parameters,
        "editing": editing,
        "notes": notes,
    }
    status = "unavailable" if fatal else (
        "partial" if any(d["severity"] == "error" for d in diags) else "available")
    return {"design": normalized, "status": status, "diagnostics": diags}


# ------------------------------------------------------------ section access

def _num(section, *names):
    if not isinstance(section, Mapping):
        return None
    for name in names:
        if name in section:
            return _number(section[name])
    return None


def _int(section, *names):
    value = _num(section, *names)
    if value is None:
        return None
    return int(value) if float(value).is_integer() else None


def _flag(section, *names):
    if not isinstance(section, Mapping):
        return None
    for name in names:
        if name in section and isinstance(section[name], bool):
            return section[name]
    return None


def _groups(section):
    if isinstance(section, Mapping):
        groups = section.get("groups")
        if isinstance(groups, (list, tuple)):
            return list(groups)
    return []


def _pow(base, exponent):
    if base is None:
        return None
    if base < 0.0 and exponent != int(exponent):
        return None
    try:
        result = base ** exponent
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    except TypeError:
        return None
    if isinstance(result, complex) or not math.isfinite(result):
        return None
    return float(result)


def _finite(value):
    if value is None or not math.isfinite(value):
        return None
    return float(value)


# ---------------------------------------------------------- performance graph

def _conc_gun(weight, barrels, mount_adj, mounts, broadside):
    if barrels == 0:
        return 0.0
    if weight is None or barrels is None or broadside in (None, 0.0):
        return None
    guns = mounts if mounts else barrels
    if guns == 0:
        return None
    conc = weight * barrels / broadside
    if barrels > 0:
        if mount_adj is not None and mount_adj > 0.6:
            factor = _pow(4.0 / guns, 0.25)
            if factor is None:
                return None
            conc *= factor - 1.0
        else:
            conc *= -0.1
    else:
        conc = 0.0
    return conc


def _concentration(guns):
    broadside = _num(guns, "broadside")
    if broadside is None:
        return None
    if broadside <= 0.0:
        return 1.0
    total = 1.0
    for group in _groups(guns):
        term = _conc_gun(
            _num(group, "shellWeight", "shell_weight"),
            _int(group, "barrels"),
            _num(group, "mountAdj", "mount_adj"),
            _int(group, "mounts"),
            broadside,
        )
        if term is None:
            return None
        total += term
    return total


def _super_factor_long(guns):
    """superFactorLongCalc; returns (value, gun1TigerMode). None when undecidable."""
    base = _num(guns, "superFactor", "super_factor")
    g1 = _groups(guns)[0] if _groups(guns) else {}
    layout1 = _int(g1, "layoutG1", "layout_group1")
    layout2 = _int(g1, "layoutG2", "layout_group2")
    mounts = _int(g1, "mounts")
    mounts_g1 = _int(g1, "mountsG1", "mounts_group1")
    mounts_g2 = _int(g1, "mountsG2", "mounts_group2")
    pos1 = _num(g1, "positionG1", "position_group1")
    pos2 = _num(g1, "positionG2", "position_group2")
    if None in (base, layout1, layout2, mounts, mounts_g1, mounts_g2):
        return None, False
    if (layout1 in (0, 9) or layout2 in (0, 9)) and mounts in (3, 4):
        return base, True
    if (mounts_g1 > 0 and mounts_g2 == 0
            and (3 <= layout1 <= 8 or 12 <= layout1 <= 17)) \
            or (mounts_g2 > 0 and mounts_g1 == 0
                and (3 <= layout2 <= 8 or 12 <= layout2 <= 17)):
        return base * 0.8, False
    if mounts_g1 > 0 and mounts_g2 > 0:
        if pos1 is None or pos2 is None:
            return None, False
        if abs(pos1 - pos2) < 0.2:
            return base * 0.8, False
    return 2.0 * base - 1.0, False


def performance_graph(sections: Mapping, *, path: str = "$") -> dict:
    """Transcribe PerformanceControl.cs over native section fields.

    ``sections`` keys: hull, freeboard, guns, auxiliary, armour, engine.
    Returns ``{performance, diagnostics}``; a missing input makes only its own
    readings ``null`` + a diagnostic, never a silent 0.
    """
    diags: list = []
    hull = sections.get("hull") if isinstance(sections, Mapping) else None
    free = sections.get("freeboard") if isinstance(sections, Mapping) else None
    guns = sections.get("guns") if isinstance(sections, Mapping) else None
    aux = sections.get("auxiliary") if isinstance(sections, Mapping) else None
    arm = sections.get("armour") if isinstance(sections, Mapping) else None
    eng = sections.get("engine") if isinstance(sections, Mapping) else None

    def need(**named):
        missing = [k for k, v in named.items() if v is None]
        for k in missing:
            _diag(diags, "missing_dependency", "error", "%s.performance.%s" % (path, k),
                  "performance needs %s from the upstream sections" % k)
        return not missing

    # base geometry
    displacement = _num(hull, "displacement")
    beam = _num(hull, "beam")
    beam_bulges = _num(hull, "beamBulges", "beam_bulges")
    draught = _num(hull, "draught")
    length = _num(hull, "length")
    length_beam = _num(hull, "lengthBeam", "length_beam")
    waterplane = _num(hull, "waterplaneArea", "waterplane_area")
    wetted = _num(hull, "wettedSurface", "wetted_surface")
    crew_min = _num(hull, "crewMin", "crew_min")
    date_hull = _num(hull, "dateHull", "date_hull")
    date_adj = _num(hull, "dateAdjFloat", "date_adj_float")
    free_distributed = _num(free, "freeDistributed", "free_distributed")
    free_cap = _num(free, "freeboardCap", "freeboard_cap")
    free_avg = _num(free, "freeboard")

    guns_weight = _num(guns, "gunsWeight", "guns_weight")
    borne = _num(guns, "borneWeight", "borne_weight")
    arm_weight = _num(guns, "armWeight", "arm_weight")
    magazine = _num(guns, "magazine")
    super_factor = _num(guns, "superFactor", "super_factor")
    broadside = _num(guns, "broadside")

    misc_vital = _num(aux, "miscWeightVital", "misc_weight_vital")
    misc_hull = _num(aux, "miscWeightHull", "misc_weight_hull")
    misc_deck = _num(aux, "miscWeightDeck", "misc_weight_deck")
    misc_above = _num(aux, "miscWeightAbove", "misc_weight_above")
    misc_void = _num(aux, "voidWeight", "void_weight")
    misc_weight = _num(aux, "miscWeight", "misc_weight")
    aux_weight = _num(aux, "weight")
    space_hull = _num(aux, "spaceHull", "space_hull")
    space_deck = _num(aux, "spaceDeck", "space_deck")
    torp1 = {}
    aux_groups = _groups(aux)
    for group in aux_groups:
        if isinstance(group, Mapping) and group.get("group") in ("torp1", "torpedo1"):
            torp1 = group
    if not torp1 and aux_groups:
        torp1 = aux_groups[0] if isinstance(aux_groups[0], Mapping) else {}

    armour_weight = _num(arm, "weight")
    weight_conning = _num(arm, "weightConning", "conningWeight", "weight_conning")
    weight_belt_upper = _num(arm, "weightBeltUpper", "beltUpperWeight")
    weight_belt_main = _num(arm, "weightBeltMain", "beltMainWeight")
    weight_belt_ends = _num(arm, "weightBeltEnds", "beltEndsWeight")
    weight_deck = _num(arm, "weightDeck", "deckWeight")
    bulkhead_weight = _num(arm, "weightBulkhead", "bulkheadWeight")
    bulkhead_type = _int(arm, "bulkheadType", "bulkhead_type")
    bulkhead_beam = _num(arm, "bulkheadBeam", "bulkhead_beam")
    bulkhead = _num(arm, "bulkhead", "bulkheadThickness", "bulkhead_thickness")
    bulkhead_length = _num(arm, "bulkheadLength", "bulkhead_length")
    bulkhead_height = _num(arm, "bulkheadHeight", "bulkhead_height")

    engine_weight = _num(eng, "engineWeight", "engine_weight")
    hull_weight = _num(eng, "hullWeight", "hull_weight")          # H1
    bunker = _num(eng, "bunker")
    load_weight = _num(eng, "loadWeight", "load_weight")
    hp_max = _num(eng, "hpMax", "hp_max")
    speed_max = _num(eng, "speedMax", "speed_max")
    frict_max = _num(eng, "frictMax", "friction")
    wave_max = _num(eng, "waveMax", "wave")
    steadiness_raw = sections.get("steadiness") if isinstance(sections, Mapping) else None
    steadiness = None
    if isinstance(steadiness_raw, int) and not isinstance(steadiness_raw, bool):
        steadiness = steadiness_raw
    elif isinstance(steadiness_raw, str):
        try:
            steadiness = int(steadiness_raw.strip())
        except ValueError:
            steadiness = None

    perf: dict[str, Any] = {}

    # displacements -----------------------------------------------------------
    if displacement is not None and load_weight is not None:
        perf["dispLight"] = _finite(displacement - load_weight)
    else:
        need(displacement=displacement, loadWeight=load_weight)
        perf["dispLight"] = None
    if displacement is not None and bunker is not None:
        perf["dispStandard"] = _finite(displacement - bunker)
        perf["dispMaxLoad"] = _finite(displacement + 0.8 * bunker)
    else:
        need(displacement=displacement, bunker=bunker)
        perf["dispStandard"] = None
        perf["dispMaxLoad"] = None
    draught_deep = _num(hull, "draughtDeep", "draught_deep")
    if draught_deep is None and None not in (draught, displacement, perf['dispMaxLoad'], waterplane) and waterplane != 0:
        draught_deep = _finite(draught + (perf['dispMaxLoad'] - displacement) / (waterplane / TON))
    perf["draughtDeep"] = draught_deep
    if perf["dispMaxLoad"] is not None and length and beam_bulges and draught_deep:
        block_deep = perf["dispMaxLoad"] / (length * beam_bulges * draught_deep / TON)
        perf["blockDeep"] = _finite(min(1.0, block_deep))
    else:
        perf["blockDeep"] = None
        if perf["dispMaxLoad"] is not None and not draught_deep:
            _diag(diags, "missing_dependency", "error", "%s.performance.blockDeep" % path,
                  "blockDeep needs hull.draughtDeep (deep draught) from the hull section")

    # room --------------------------------------------------------------------
    room_float = None
    if None not in (magazine, displacement, borne, engine_weight, misc_vital,
                    misc_hull, space_hull) and displacement != 0.0:
        denom_room = 1.0 - space_hull
        if denom_room != 0.0:
            room_float = (magazine + displacement * 0.02 + borne * 6.4
                          + engine_weight * 3.0 + misc_vital + misc_hull) \
                / (displacement * 0.94) / denom_room
            room_float = _finite(room_float)
    if room_float is None:
        need(magazine=magazine, displacement=displacement, borneWeight=borne,
             engineWeight=engine_weight, miscVital=misc_vital, miscHull=misc_hull,
             spaceHull=space_hull)
    perf["roomFloat"] = room_float
    if room_float is not None and bulkhead_weight is not None and bulkhead_weight > 0.1 \
            and bulkhead_beam not in (None, 0.0) and beam is not None:
        perf["roomHull"] = _finite(room_float * beam / bulkhead_beam)
    elif room_float is not None:
        perf["roomHull"] = room_float
    else:
        perf["roomHull"] = None
    if None not in (waterplane, crew_min, free_distributed, space_deck) and crew_min:
        perf["roomDeck"] = _finite(waterplane / TON / 15.0 * (1.0 - space_deck)
                                   / crew_min * free_distributed)
    else:
        need(waterplaneArea=waterplane, crewMin=crew_min,
             freeDistributed=free_distributed, spaceDeck=space_deck)
        perf["roomDeck"] = None
    room_deck = perf["roomDeck"]

    # superFactorLong ---------------------------------------------------------
    super_factor_long, tiger = _super_factor_long(guns)
    if super_factor_long is not None and perf["roomHull"] is not None:
        super_factor_long = _finite(super_factor_long * perf["roomHull"])
    else:
        super_factor_long = None
    perf["superFactorLong"] = super_factor_long
    perf["gun1TigerMode"] = tiger

    # structural weight / strength -------------------------------------------
    bulkhead_add = bulkhead_weight if (bulkhead_type == 1 and bulkhead_weight
                                       and bulkhead_weight > 0) else 0.0
    struct_numerator = None
    if hull_weight is not None:
        struct_numerator = hull_weight + bulkhead_add
    struct_weight = None
    if struct_numerator is not None and None not in (wetted, length, free_cap, waterplane):
        denom = wetted + 2.0 * length * free_cap + waterplane
        if denom != 0.0:
            struct_weight = _finite(struct_numerator * POUND2TON / denom)
    if struct_weight is None:
        need(hullWeight=hull_weight, wettedSurface=wetted, freeboardCap=free_cap,
             waterplaneArea=waterplane)
    perf["structWeight"] = struct_weight

    concentration = _concentration(guns)
    perf["concentration"] = concentration
    strength_cross = None
    if None not in (struct_weight, beam_bulges, draught, free_distributed) \
            and None not in (displacement, broadside, borne, arm_weight,
                             weight_conning, concentration, super_factor, hp_max) \
            and displacement not in (0.0, None) and date_hull is not None:
        inner = math.sqrt(beam_bulges * (draught + free_distributed)) if \
            beam_bulges * (draught + free_distributed) >= 0 else None
        if inner not in (None, 0.0):
            bracket = (displacement + (broadside + borne + arm_weight + weight_conning)
                       * (concentration * super_factor) + max(hp_max, 0.0) / 100.0)
            strength_cross = struct_weight / inner / (bracket / displacement) * 0.6
            strength_cross = _finite(strength_cross)
            if strength_cross is not None and date_hull < 1900:
                strength_cross = _finite(strength_cross * (1.0 - (1900.0 - date_hull) / 100.0))
    perf["strengthCross"] = strength_cross

    strength_long = None
    if None not in (hull_weight, length, draught, free_cap, displacement,
                    weight_belt_ends, borne, arm_weight, super_factor_long) \
            and date_hull is not None and (draught + free_cap) not in (0.0, None) \
            and length != 0.0:
        base_len = _pow(length / (draught + free_cap), 2.0)
        if base_len is not None:
            load = displacement + weight_belt_ends * 3.0 \
                + (borne + arm_weight) * super_factor_long * 2.0
            if load != 0.0:
                strength_long = (hull_weight + bulkhead_add) / (base_len * load) * 850.0
                strength_long = _finite(strength_long)
                if strength_long is not None and date_hull < 1900:
                    strength_long = _finite(strength_long
                                            * (1.0 - (1900.0 - date_hull) / 100.0))
    perf["strengthLong"] = strength_long

    strength_comp = None
    if strength_cross is not None and strength_long is not None:
        if strength_cross > strength_long and strength_long != 0.0:
            ratio = _pow(strength_cross / strength_long, 0.25)
            strength_comp = _finite(strength_long * ratio) if ratio is not None else None
        elif strength_cross != 0.0:
            ratio = _pow(strength_long / strength_cross, 0.1)
            strength_comp = _finite(strength_cross * ratio) if ratio is not None else None
    perf["strengthComp"] = strength_comp

    # stability ---------------------------------------------------------------
    stability = None
    if None not in (weight_conning, borne, arm_weight, super_factor, misc_hull,
                    misc_deck, misc_above, weight_belt_upper, weight_belt_main,
                    weight_belt_ends, weight_deck, hull_weight, guns_weight,
                    free_avg, draught) and draught != 0.0:
        stability = (weight_conning * 5.0 + (borne + arm_weight)
                     * (2.0 * super_factor - 1.0) * 4.0 + misc_hull * 2.0
                     + misc_deck * 3.0 + misc_above * 4.0 + weight_belt_upper * 2.0
                     + weight_belt_main + weight_belt_ends + weight_deck
                     + (hull_weight + guns_weight - borne) * 1.5 * free_avg / draught)
        if room_deck is not None and room_deck < 1.0 and None not in (engine_weight,
                                                                     misc_vital, misc_void):
            stability += (engine_weight + misc_vital + misc_void) * (1.0 - room_deck) ** 2
        if stability > 0.0 and None not in (displacement, beam_bulges, length_beam) \
                and length_beam != 0.0:
            inner = displacement * (beam_bulges / draught) / stability * 0.5
            if inner >= 0.0:
                root = math.sqrt(inner)
                quarter = _pow(8.76755 / length_beam, 0.25)
                stability = _finite(root * quarter) if quarter is not None else None
        else:
            stability = _finite(stability)
    perf["stability"] = stability

    stability_adj = None
    if stability is not None and steadiness is not None:
        stability_adj = _finite(stability * ((50.0 - steadiness) / 150.0 + 1.0))
    else:
        need(stability=stability, steadiness=steadiness)
    perf["stabilityAdj"] = stability_adj

    # seaboat / steadiness / seakeeping --------------------------------------
    seaboat = None
    if None not in (free_cap, displacement, stability, beam_bulges, length,
                    weight_belt_ends, hull_weight, borne, arm_weight,
                    super_factor_long, draught, frict_max, wave_max):
        p1 = _pow(displacement, 0.2)
        p2 = _pow(stability * 5.0 * (beam_bulges / length), 0.2)
        p3 = _pow(free_cap / length * 20.0, 0.5) if free_cap / length * 20.0 >= 0 else None
        denom = displacement + weight_belt_ends * 3.0 + hull_weight / 3.0 \
            + (borne + arm_weight) * super_factor_long
        if None not in (p1, p2, p3) and p1 and length and denom != 0.0:
            inner = free_cap / (2.4 * p1)
            if inner >= 0.0:
                seaboat = math.sqrt(inner) * (p2 * p3 * (displacement / denom)) * 8.0
                if draught / beam_bulges < 0.3:
                    ratio = draught / beam_bulges / 0.3
                    if ratio >= 0.0:
                        seaboat *= math.sqrt(ratio)
                fric_frac = frict_max / (frict_max + wave_max)
                if fric_frac < 0.55 and speed_max not in (None, 0.0):
                    fric_factor = _pow(fric_frac, 2.0)
                    if fric_factor is None:
                        seaboat = None
                    else:
                        seaboat *= fric_factor
                else:
                    seaboat *= 0.3025
                seaboat = _finite(min(seaboat, 2.0)) if seaboat is not None else None
    if seaboat is None:
        need(freeboardCap=free_cap, stability=stability, frictMax=frict_max,
             waveMax=wave_max)
    perf["seaboat"] = seaboat
    steadiness_adj = None
    if seaboat is not None and steadiness is not None:
        steadiness_adj = _finite(min(float(steadiness) * seaboat, 100.0))
    perf["steadinessAdj"] = steadiness_adj
    seakeeping = None
    if seaboat is not None and steadiness_adj is not None:
        seakeeping = _finite(seaboat * steadiness_adj / 50.0) if steadiness_adj < 50.0 \
            else _finite(seaboat)
    perf["seakeeping"] = seakeeping
    perf["steadiness"] = steadiness

    metacentre = None
    if beam is not None and stability_adj is not None:
        supported = _pow(beam, 1.5)
        if supported is not None:
            metacentre = _finite(supported * (stability_adj - 0.5) / 0.5 / 200.0)
    perf["metacentre"] = metacentre
    roll_period = None
    if metacentre is not None and metacentre > 0.0 and beam_bulges is not None:
        roll_period = _finite(0.42 * beam_bulges / math.sqrt(metacentre))
    perf["rollPeriod"] = roll_period
    if metacentre is not None and metacentre <= 0.0:
        _diag(diags, "negative_gm_roll_unknown", "warning",
              "%s.performance.rollPeriod" % path,
              "roll period is unknown when GM <= 0; it is not computed from |GM|")

    # source flags ------------------------------------------------------------
    tender = None if stability_adj is None else stability_adj <= 0.995
    capsize = None if metacentre is None else metacentre <= 0.0
    perf["tenderWarn"] = tender
    perf["capsizeWarn"] = capsize
    if steadiness_adj is not None:
        perf["steady"] = steadiness_adj >= 69.5
        perf["unsteady"] = steadiness_adj < 30.0
    else:
        perf["steady"] = None
        perf["unsteady"] = None
    if seakeeping is not None:
        perf["badSea"] = seakeeping < 0.7
        perf["poorSea"] = 0.7 <= seakeeping < 0.995
        perf["goodSea"] = 1.2 <= seakeeping < 1.5
        perf["fineSea"] = seakeeping >= 1.5
    else:
        perf["badSea"] = perf["poorSea"] = perf["goodSea"] = perf["fineSea"] = None

    # recoil / flotation / hits via the accepted kernel ----------------------
    capped_flag = None
    gun_groups = _groups(guns)
    if gun_groups and all(isinstance(g, Mapping) for g in gun_groups):
        known = []
        for group in gun_groups:
            mount_type = _int(group, "mountType", "mount_type")
            sub_g1 = _num(group, "gunSubG1", "gun_sub_g1")
            if mount_type is None or sub_g1 is None:
                known.append(None)
            else:
                known.append(bool(mount_type == 0 and sub_g1 + sub_g1 > 0))
        capped_flag = any(known) if None not in known else None
    kernel_inputs = {
        "broadside_lb": broadside,
        "displacement_lt": displacement,
        "freeboard_distributed_ft": free_distributed,
        "freeboard_cap_ft": free_cap,
        "gun_super_factor": super_factor,
        "beam_bulges_ft": beam_bulges,
        "stability_adjusted": stability_adj,
        "steadiness_adjusted": steadiness_adj,
        "composite_strength": strength_comp,
        "use_capped_freeboard": capped_flag,
        "waterplane_sqft": waterplane,
        "room_float": room_float,
        "date_float": date_adj,
        "first_gun_calibre_in": _num(gun_groups[0], "calibre") if gun_groups else None,
        "hull_length_ft": length,
        "draught_ft": draught,
        "bulkhead_thickness_in": bulkhead,
        "bulkhead_length_ft": bulkhead_length,
        "bulkhead_height_ft": bulkhead_height,
        "space_hull_fraction": space_hull,
        "first_torpedo_weapon_weight_lt": _num(torp1, "weaponWeight", "weapon_weight"),
        "first_torpedo_count": _int(torp1, "number"),
        "first_torpedo_diameter_in": _num(torp1, "size", "sizeIn"),
    }
    kernel = sps_performance.evaluate(kernel_inputs, path="%s.performance" % path,source_single=True)
    for entry in kernel["diagnostics"]:
        entry = dict(entry)
        entry["field"] = entry.get("field")
        diags.append(entry)
    perf["recoil"] = kernel["values"]["recoil_index"]
    perf["flotation"] = kernel["values"]["flotation_lb"]
    perf["damageShell"] = kernel["values"]["shell_hits"]
    perf["damageTorp"] = kernel["values"]["torpedo_hits"]
    perf["damageShellCalibreIn"] = kernel["values"]["shell_reference_calibre_in"]
    perf["damageTorpSizeIn"] = kernel["values"]["torpedo_reference_diameter_in"]

    # cost --------------------------------------------------------------------
    if None not in (displacement, load_weight, engine_weight, borne, date_hull):
        cost = (displacement - load_weight) * 0.00014 + engine_weight * 0.00056 \
            + (borne * 8.0) * 0.00042
        if date_hull + 2.0 > 1914.0:
            cost *= 1.0 + (date_hull + 1.5 - 1914.0) / 5.5
        perf["costDollars"] = _finite(cost)
        perf["costPounds"] = _finite(cost / 4.0)
    else:
        need(displacement=displacement, loadWeight=load_weight,
             engineWeight=engine_weight, borneWeight=borne, dateHull=date_hull)
        perf["costDollars"] = None
        perf["costPounds"] = None

    perf["warnings"] = [d for d in diags
                        if d["severity"] == "warning" and d["field"]
                        and d["field"].startswith("%s.performance" % path)]
    perf["ratings"] = {
        "seakeeping": "fine" if perf["fineSea"] else
                      "good" if perf["goodSea"] else
                      "poor" if perf["poorSea"] else
                      "bad" if perf["badSea"] else None,
        "steadiness": "steady" if perf["steady"] else
                      "unsteady" if perf["unsteady"] else None,
        "stability": "tender" if perf["tenderWarn"] else
                     ("ok" if perf["tenderWarn"] is not None else None),
    }
    return {"performance": perf, "diagnostics": diags}


# ------------------------------------------------------------------- compute

def _null_section(fields):
    return {name: None for name in fields}


def _import(name, diags, path):
    try:
        return importlib.import_module('.' + name, __package__) if __package__ else importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - depends on sibling modules
        _diag(diags, "module_unavailable", "error", "%s.%s" % (path, name),
              "sibling unit %r is not importable: %s" % (name, exc))
        return None


def _optional_import(name):
    """Import an optional unit; absence is not a diagnostic."""
    try:
        return importlib.import_module('.' + name, __package__) if __package__ else importlib.import_module(name)
    except Exception:  # pragma: no cover - depends on sibling modules
        return None


def _call(fn, args, kwargs, diags, path, module):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        _diag(diags, "module_error", "error", "%s.%s" % (path, module),
              "%s raised %s: %s" % (module, type(exc).__name__, exc))
        return None


def compute(design: dict) -> dict:
    """Run the compatibility dependency graph. Never raises; inputs not mutated."""
    norm = normalize(design)
    params = norm["design"]["parameters"]
    editing = norm["design"]["editing"]
    diags = list(norm["diagnostics"])

    sections: dict[str, Any] = {key: None for key in _RESULT_SECTIONS}
    result = {
        "schema": RESULT_SCHEMA,
        "method_version": METHOD_VERSION,
        "status": "unavailable",
        "design": norm["design"],
        "hull": None,
        "freeboard": None,
        "guns": None,
        "auxiliary": None,
        "armour": None,
        "engine": None,
        "performance": None,
        "review": None,
        "diagnostics": diags,
        "provenance": None,
    }
    if norm["status"] == "unavailable":
        return result

    submerged = editing.get('submerged_casemate', False)
    hull_mod = _import("sps_hull", diags, "$")
    hull_out = None
    if hull_mod is not None:
        hull_out = _call(hull_mod.evaluate, (params,),
                         {"editing": editing, "submerged_casemate": submerged},
                         diags, "$", "sps_hull")
    if hull_out:
        diags.extend(hull_out.get("diagnostics", []))
        sections["hull"] = hull_out.get("hull")
        sections["freeboard"] = hull_out.get("freeboard")
        sections['hull'],sections['freeboard']=sps_single.hull_readings(params,editing,sections['hull'],sections['freeboard'])

    components_mod = _import("sps_components", diags, "$")
    if components_mod is not None:
        comp_out = _call(components_mod.evaluate,
                         (params, sections["hull"], sections["freeboard"]), {'editing':editing},
                         diags, "$", "sps_components")
        if comp_out:
            diags.extend(comp_out.get("diagnostics", []))
            sections["guns"] = comp_out.get("guns")
            sections["auxiliary"] = comp_out.get("auxiliary")
            sections["armour"] = comp_out.get("armour")

    engine_mod = _import("sps_engine", diags, "$")
    if engine_mod is not None:
        eng_out = _call(engine_mod.evaluate,
                        (params, sections["hull"], sections["guns"],
                         sections["auxiliary"], sections["armour"]),
                        {"editing": editing}, diags, "$", "sps_engine")
        if eng_out:
            diags.extend(eng_out.get("diagnostics", []))
            sections["engine"] = eng_out.get("engine")

    trim_raw = params.get("trim")
    if isinstance(trim_raw, str) and trim_raw.strip().lstrip("+-").isdigit():
        sections["steadiness"] = int(trim_raw.strip())
    elif isinstance(trim_raw, int) and not isinstance(trim_raw, bool):
        sections["steadiness"] = trim_raw
    else:
        _diag(diags, "invalid_trim", "warning", "$.parameters.trim", "Trim is unknown or is not integer text")
        sections["steadiness"] = None
    if 'deep_waterplane_ft2' in editing and sections['hull']:
        h=sections['hull'];eng=sections['engine'] or {};area=editing['deep_waterplane_ft2']
        h['draughtDeep']=None if not area or h.get('draught') is None or eng.get('bunker') is None else h['draught']+.8*eng['bunker']/(area/TON)
    graph = performance_graph(sections, path="$.performance")
    diags.extend(graph["diagnostics"])
    if sections['hull'] is not None:
        sections['hull']['draughtDeep']=graph['performance'].get('draughtDeep')

    graph_sections = ("hull", "freeboard", "guns", "auxiliary", "armour", "engine")
    result["hull"] = sections["hull"]
    result["freeboard"] = sections["freeboard"]
    result["guns"] = sections["guns"]
    result["auxiliary"] = sections["auxiliary"]
    result["armour"] = sections["armour"]
    result["engine"] = sections["engine"]
    result["performance"] = graph["performance"]

    values = [sections[key] for key in graph_sections] + [graph["performance"]]
    result["status"] = _status_from(diags, values)

    review_mod = _optional_import("sps_gun_review")
    if review_mod is not None and hasattr(review_mod, "evaluate"):
        review = _call(review_mod.evaluate,
                       (params, sections["hull"], sections["guns"],
                        sections["auxiliary"], sections["armour"],
                        sections["engine"], graph["performance"]), {'freeboard':sections['freeboard']},
                       diags, "$", "sps_gun_review")
        if isinstance(review, Mapping):
            result["review"] = review

    result["provenance"] = {
        "method_version": METHOD_VERSION,
        "source_sha256": SOURCE_SHA256,
        "units": "native source units: ft / in / lb / lt / kn / nm",
        "note": ("Coordinates the source-compatible units; performance readings "
                 "reuse the accepted sps_performance kernel. Not a claim of full "
                 "original-program equivalence."),
        "hull_module": getattr(hull_mod, "METHOD_VERSION", None),
        "components_module": getattr(components_mod, "METHOD_VERSION", None),
        "engine_module": getattr(engine_mod, "METHOD_VERSION", None),
        "review_module": getattr(review_mod, "METHOD_VERSION", None),
    }
    return result


# ---------------------------------------------------------------- apply_edit

_HULL_COMMANDS = ("set_length_driver", "set_displacement_driver", "set_depth_lock",
                  "freeboard_preset")
_COMPONENT_COMMANDS = ("lock_shells", "unlock_shells", "armour_defaults", "set_shell_weight")
_ENGINE_COMMANDS = ("set_power_lock", "recalculate_power")

# Canonical value key is ``value``; these aliases are accepted at the gateway.
_VALUE_ALIASES = ("value", "enabled", "driver", "preset")

# (unit_choices) -> multiplicative factor between the first (imperial) and the
# second (metric) member, matching the source's metric conversions.
_UNIT_FACTORS = {
    ("in", "mm"): 25.4,
    ("ft", "m"): 0.3048,
    ("lb", "kg"): 0.45359236,
}

_PAGE_OWNER = {
    "hull": "sps_hull",
    "freeboard": "sps_hull",
    "guns": "sps_components",
    "weapons": "sps_components",
    "armour": "sps_components",
    "engine": "sps_engine",
}


def _command_value(command):
    """First documented value key present (``value`` canonical; aliases accepted)."""
    for key in _VALUE_ALIASES:
        if key in command:
            return command[key]
    return None


def _canonical_command(command):
    """A copy of ``command`` with its value key normalised to ``value``."""
    canon = dict(command)
    if "value" not in canon:
        for key in _VALUE_ALIASES[1:]:
            if key in canon:
                canon["value"] = canon[key]
                break
    return canon


def _field_page(name):
    if not isinstance(name, str):
        return None
    return sps_field_catalog.catalog()["fields"].get(name, {}).get("page")


def _owner_for(command):
    """The sibling module that owns ``command`` (None => coordinator-owned)."""
    kind = command.get("kind")
    if kind in _HULL_COMMANDS:
        return "sps_hull"
    if kind in _COMPONENT_COMMANDS:
        return "sps_components"
    if kind in _ENGINE_COMMANDS:
        return "sps_engine"
    if kind == "set_parameter":
        if command.get('name') in ('ship_name','country','ship_type'):
            return None
        if command.get('name') in ('armour_bulkhead_beam','length_overall','normal_displacement_lt'):
            return 'sps_hull'
        if command.get('name') == 'power_hp':
            return 'sps_engine'
        return _PAGE_OWNER.get(_field_page(command.get("name")))
    return None


def _scale_fields(page):
    fields = sps_field_catalog.catalog()["fields"]
    return sorted({spec["scale_ref"] for spec in fields.values()
                   if spec["page"] == page and spec["scale_ref"]})


def _quantize(value):
    """Emulate the original program's default float->text round trip."""
    if value is None:
        return None
    return float("%.7g" % value)


def _set_all_scales(design, value, diags):
    """Source global action: convert every page scale through one decision."""
    if value not in (0, 1):
        _diag(diags, "invalid_command_value", "error", "$.command.value",
              "set_all_scales value must be 0 or 1")
        return
    # Original global choice locks shells, changes selectors from armour back
    # through the weapon banks, changes hull last, then unlocks every shell.
    design['editing']['locked_shell_groups']=list(range(1,6))
    for name in reversed(sps_field_catalog.ALL_SCALE_FIELDS):
        _set_single_scale(design,name,value,diags)
    design['editing']['locked_shell_groups']=[]


def _set_page_scale(design, page, value, diags):
    """Convert only the named page's fields between imperial and metric."""
    if page == "hull" and value in (2, 3):
        # HullControl dropdown 2/3 = global "all metric" / "all imperial";
        # the source applies it once and does not persist 2/3.
        _set_all_scales(design, 1 if value == 2 else 0, diags)
        return
    if value not in (0, 1):
        _diag(diags, "invalid_command_value", "error", "$.command.value",
              "scale value must be 0 or 1")
        return
    scale_fields = _scale_fields(page)
    if not scale_fields:
        _diag(diags, "no_page_scale", "error", "$.command.page",
              "page %r has no page-unit selector" % (page,))
        return
    for scale_name in scale_fields:
        _set_single_scale(design,scale_name,value,diags)


def _set_single_scale(design,scale_name,value,diags):
    current=design['parameters'].get(scale_name)
    if current==value:return
    if current not in (0,1) or type(value) is not int or value not in (0,1):
        _diag(diags,'scale_unknown','error','$.parameters.'+scale_name,'A unit conversion needs known original and target units')
        return
    if scale_name=='hull_scale':
        _delegate(design,'sps_hull',dict(kind='set_scale',page='hull',value=value),diags)
        return
    for name,spec in sps_field_catalog.catalog()['fields'].items():
        if spec['scale_ref']!=scale_name:continue
        raw=design['parameters'].get(name)
        if raw is None or not _is_number(raw):continue
        factor=_UNIT_FACTORS.get(tuple(spec['unit_choices'] or []))
        if factor is not None:
            design['parameters'][name]=_quantize(raw*factor if value==1 else raw/factor)
    design['parameters'][scale_name]=value
    if scale_name.startswith('gun'):
        bank=int(scale_name[3])
        if bank not in design['editing'].get('locked_shell_groups',[]):
            _delegate(design,'sps_components',dict(kind='set_parameter',name='gun%d_calibre'%bank,value=design['parameters'].get('gun%d_calibre'%bank)),diags)


def _delegate(new_design, owner, command, diags):
    """Hand a command to the owning sibling unit, if it is available."""
    module = _import(owner, diags, "$")
    if module is None or not hasattr(module, "apply_edit"):
        return
    params = new_design["parameters"]
    editing = new_design["editing"]
    if owner == "sps_hull":
        out = _call(module.apply_edit, (params, editing, command), {},
                    diags, "$", owner)
    elif owner == "sps_components":
        context = compute(new_design)
        out = _call(module.apply_edit, (params, editing, command),
                    {'hull': context.get('hull'), 'freeboard': context.get('freeboard')},
                    diags, "$", owner)
    else:  # sps_engine
        context = compute(new_design)
        out = _call(module.apply_edit, (params, editing, command),
                    {name: context.get(name) for name in ('hull','guns','auxiliary','armour')},
                    diags, "$", owner)
    if isinstance(out, Mapping):
        if isinstance(out.get("parameters"), Mapping):
            updated=dict(out['parameters'])
            for name,value in updated.items():
                if name in _PARAMETER_NAMES and sship_fields.KINDS[sship_fields.NAMES.index(name)] in (sship_fields.INTEGER,sship_fields.ENUM,sship_fields.SELECTOR) and isinstance(value,float) and value.is_integer():
                    updated[name]=int(value)
            new_design["parameters"] = updated
        if isinstance(out.get("editing"), Mapping):
            new_design["editing"] = out["editing"]
        diags.extend(out.get("diagnostics", []))


def _apply_generic_parameter(design, command, diags):
    """Set a coordinator-owned parameter (e.g. the performance `trim`)."""
    name = command.get("name")
    if name not in sps_field_catalog.catalog()["fields"]:
        _diag(diags, "unknown_parameter", "error", "$.command.name",
              "unknown parameter %r" % (name,))
        return
    value = command.get("value")
    validated = _validate_parameter(name, value, diags, "$")
    if validated is None and value is not None:
        return  # rejected; a diagnostic has already been recorded
    design["parameters"][name] = validated


def apply_edit(design: dict, command: dict) -> dict:
    """Apply one compatibility edit command. Returns new design + preview."""
    norm = normalize(design)
    diags = list(norm["diagnostics"])
    current = norm["design"]

    if not isinstance(command, Mapping):
        _diag(diags, "invalid_command", "error", "$.command", "command must be a mapping")
        return {"design": current, "preview": None, "status": "partial",
                "diagnostics": diags}
    kind = command.get("kind")
    if not isinstance(kind, str):
        _diag(diags, "invalid_command", "error", "$.command.kind",
              "command.kind must be a string")
        return {"design": current, "preview": None, "status": "partial",
                "diagnostics": diags}

    canon = _canonical_command(command)
    new_design = copy.deepcopy(current)
    if kind=='set_parameter' and canon.get('name') in _PARAMETER_NAMES:
        checked=_validate_parameter(canon['name'],canon.get('value'),diags,'$.command')
        if any(d.get('severity')=='error' for d in diags):
            return dict(design=current,preview=compute(current),status='partial',diagnostics=diags)
        canon['value']=checked
    before=compute(current)
    if isinstance(before.get('armour'),Mapping):
        new_design['editing']['armour_read_context']=copy.deepcopy(before['armour'].get('read_context',{}))

    if kind=='set_parameter' and canon.get('name') in sps_field_catalog.ALL_SCALE_FIELDS:
        _set_single_scale(new_design,canon['name'],canon.get('value'),diags)
    elif kind == "set_notes":
        notes = canon.get("notes", canon.get("value"))
        if notes is not None and not isinstance(notes, str):
            _diag(diags, "invalid_command_value", "error", "$.command.notes",
                  "notes must be a string")
        else:
            new_design["notes"] = notes
    elif kind == "set_all_scales":
        _set_all_scales(new_design, _command_value(canon), diags)
    elif kind == "set_scale":
        page = canon.get("page")
        value = _command_value(canon)
        if page == "hull" and value in (0, 1):
            # delegate so the hull page conversion is performed exactly once
            _delegate(new_design, "sps_hull", canon, diags)
        else:
            _set_page_scale(new_design, page, value, diags)
    else:
        owner = _owner_for(canon)
        if owner is not None:
            if kind == "set_parameter" and canon.get("name") == "block_coefficient_normal":
                # the original hull slider drives the block-coefficient driver
                new_design["editing"]["displacement_driver"] = "block"
            _delegate(new_design, owner, canon, diags)
        elif kind == "set_parameter":
            _apply_generic_parameter(new_design, canon, diags)
        else:
            _diag(diags, "unknown_command", "error", "$.command.kind",
                  "unknown command kind %r" % (kind,))

    _refresh_edit_context(new_design,canon,before)
    preview = compute(new_design)
    status = "partial" if any(d["severity"] == "error" for d in diags) else "available"
    return {"design": new_design, "preview": preview,
            "status": status, "diagnostics": diags}


def _refresh_edit_context(design,command,before):
    """Keep source callback snapshots separate from a freshly opened file."""
    kind=command.get('kind');name=command.get('name','');edit=design['editing']
    interim=compute(design);h=interim.get('hull') or {};g=interim.get('guns') or {}
    context=edit.setdefault('armour_read_context',{})
    length_change=kind in ('set_length_driver','freeboard_preset','armour_defaults','set_all_scales') or (
        kind=='set_scale' and command.get('page') in ('hull','freeboard','armour')) or name in (
        'length_waterline','length_overall','beam_moulded','bow','freeboard_length_bow','freeboard_ram_length',
        'freeboard_length_stern','freeboard_forecastle_fore','freeboard_quarterdeck_aft') or (
        name=='draught_normal' and edit.get('depth_locked'))
    main_refresh=length_change or name.startswith('armour_belt_main_') or name in ('block_coefficient_normal','normal_displacement_lt','armour_scale')
    upper_refresh=length_change or name.startswith('armour_belt_upper_') or name=='armour_scale'
    if main_refresh:
        context['belt_main_cwp']=h.get('coWaterPlane')
    if upper_refresh:
        context['belt_upper_cwp']=h.get('coWaterPlane')
    if main_refresh or upper_refresh or name.startswith('armour_belt_ends_'):
        fresh=copy.deepcopy(design)
        fresh['editing']['armour_read_context'].pop('belt_height_ft',None)
        if kind=='freeboard_preset' and not edit.get('depth_locked'):
            # The source assigns QD aft before these remaining boxes. Its last
            # length callback caches the warning height at that intermediate
            # profile, while later endpoint writes update the final profile.
            pending=['freeboard_quarterdeck_fore','freeboard_afterdeck_aft','freeboard_afterdeck_fore']
            if command.get('value')=='flush':pending.append('freeboard_flat_deck_aft')
            previous=(before.get('design') or {}).get('parameters',{})
            for field in pending:fresh['parameters'][field]=previous.get(field)
        context['belt_height_ft']=(compute(fresh).get('armour') or {}).get('maxBeltHeight')
    deck_refresh=length_change or name.startswith('freeboard_') or name in ('stern','shafts','block_coefficient_normal') or name.startswith('armour_deck_')
    if deck_refresh:
        context['deck_machinery_lt']=(interim.get('engine') or {}).get('engineWeight')
    if name=='beam_moulded':
        edit['deep_waterplane_ft2']=(before.get('hull') or {}).get('waterplaneArea')
    elif kind!='set_notes' and not name.startswith('armour_'):
        edit.pop('deep_waterplane_ft2',None)
    cap_refresh=name=='beam_moulded' or name.startswith('freeboard_') or kind=='freeboard_preset' or (name=='draught_normal' and edit.get('depth_locked'))
    if cap_refresh:
        edit['submerged_casemate']=any(row.get('mountType')==0 and (row.get('gunSubG1') or 0)+(row.get('gunSubG2') or 0)>0 for row in g.get('groups',[]))


def report(result: dict, *, format: str = "txt"):
    """Render a report via the optional ``sps_report`` unit (None if absent).

    The coordinator owns no report formulas; this only forwards immutable
    computed data to the report unit's ``build`` + ``serialize``.
    """
    diags = []
    module = _import("sps_report", diags, "$")
    if module is None or not (hasattr(module, "build") and hasattr(module, "serialize")):
        return None
    built = _call(module.build, (result,), {}, diags, "$", "sps_report")
    if built is None:
        return None
    return _call(module.serialize, (built,), {"format": format},
                 diags, "$", "sps_report")


field_catalog = sps_field_catalog.catalog

__all__ = ["normalize", "compute", "apply_edit", "performance_graph", "report",
           "field_catalog", "SCHEMA", "RESULT_SCHEMA", "METHOD_VERSION"]
