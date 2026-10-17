# -*- coding: utf-8 -*-
"""原版 SpringSharp 3b3 性能页：四个经验读数的有界纯数值单元。

只复现旧性能页的两个计算函数的经验公式，供后续兼容模式调用：

- ``recoilCalc``   -> ``recoil_index``
- ``flotationCalc`` -> ``flotation_lb`` / ``shell_hits`` / ``torpedo_hits``
  以及两个参考标签 ``shell_reference_calibre_in`` / ``torpedo_reference_diameter_in``。

设计约束：
- 纯函数、无 GUI、无文件 IO、只用标准库；
- 输入字典不被修改；字段缺失 / ``None`` 一律表示未知，已知 ``0`` 不是未知；
- 浮点按 float64 计算，不四舍五入、不夹紧负的原式结果；
- 分支与常数严格照原式，不用启发式替代；单一缺项不抹掉独立的其它读数；
- 出错时给出结构化诊断，不抛原始异常。

来源：SpringSharp 3b3 ``PerformanceControl.recoilCalc`` / ``flotationCalc``
（原程序集 SHA256 82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc）。
这些是经验评分读数，不是假想进水 / 穿甲 / 作战仿真。
"""
from __future__ import annotations

import math
from typing import Any

METHOD_VERSION = "sps-3b3-performance-v1"

# MainForm 常数（原程序集）。
TON = 35.0

SOURCE_SHA256 = "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc"

_NUMERIC_FIELDS = (
    "broadside_lb",
    "displacement_lt",
    "freeboard_distributed_ft",
    "freeboard_cap_ft",
    "gun_super_factor",
    "beam_bulges_ft",
    "stability_adjusted",
    "steadiness_adjusted",
    "composite_strength",
    "waterplane_sqft",
    "room_float",
    "date_float",
    "first_gun_calibre_in",
    "hull_length_ft",
    "draught_ft",
    "bulkhead_thickness_in",
    "bulkhead_length_ft",
    "bulkhead_height_ft",
    "space_hull_fraction",
    "first_torpedo_weapon_weight_lt",
    "first_torpedo_diameter_in",
)

_BOOL_FIELDS = ("use_capped_freeboard",)

_INTEGER_FIELDS = ("first_torpedo_count",)

_KNOWN_FIELDS = frozenset(_NUMERIC_FIELDS + _BOOL_FIELDS + _INTEGER_FIELDS)

_READING_KEYS = (
    "recoil_index",
    "flotation_lb",
    "shell_hits",
    "torpedo_hits",
    "shell_reference_calibre_in",
    "torpedo_reference_diameter_in",
)

_PROVENANCE = {
    "kind": "empirical performance rating",
    "origin": "SpringSharp 3b3 PerformanceControl.recoilCalc / flotationCalc",
    "source_assembly_sha256": SOURCE_SHA256,
    "note": (
        "Reproduces the original performance page's empirical scoring readings; "
        "not a flooding-loading, armour-penetration or combat simulation."
    ),
    "units": {
        "recoil_index": "dimensionless rating",
        "flotation_lb": "lb",
        "shell_hits": "shells",
        "torpedo_hits": "torpedoes",
        "shell_reference_calibre_in": "in",
        "torpedo_reference_diameter_in": "in",
    },
}


# --- 内部工具 --------------------------------------------------------------

def _add(diags, code, severity, reading, field, message):
    diags.append({
        "code": code,
        "severity": severity,
        "reading": reading,
        "field": field,
        "message": message,
    })


def _loc(path, field):
    return f"{path}.{field}"


def _int_fits_float(value):
    """整数是否能无损地放进 float64（超出即无法参与原式的浮点除法）。"""
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(converted)


def _missing(diags, reading, path, fields):
    for field in fields:
        _add(diags, "missing_dependency", "error", reading, _loc(path, field),
             f"{reading} needs {field!r}, which is unknown or missing")


def _undetermined(diags, reading, path, field, why):
    _add(diags, "undetermined_branch", "error", reading, _loc(path, field), why)


def _zero(diags, reading, path, field):
    _add(diags, "zero_denominator", "error", reading, _loc(path, field),
         f"{reading} divides by {field!r}, which is known 0")


def _power(diags, reading, path, field):
    _add(diags, "power_domain", "error", reading, _loc(path, field),
         f"{reading} raises {field!r} to a fractional power outside the real domain")


def _finite(diags, reading, path, value):
    if value is None or not math.isfinite(value):
        _add(diags, "non_finite_result", "error", reading, path,
             f"{reading} is not a finite real number under the original expression")
        return None
    if value < 0.0:
        _add(diags, "negative_result", "warning", reading, path,
             f"{reading} is negative; kept as produced by the original expression")
    return float(value)


def _cpow(base, exponent):
    """System.Math.Pow 语义：负底 + 非整数指数 -> NaN；非有限 / 越界 -> None。"""
    if base < 0.0 and exponent != int(exponent):
        return None
    try:
        result = base ** exponent
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    if isinstance(result, complex) or not math.isfinite(result):
        return None
    return float(result)


# --- 输入校验 --------------------------------------------------------------

def _validate(inputs, path):
    """返回 (validated, fatal)。fatal 为根级契约被破坏，整单不可用。"""
    if not isinstance(inputs, dict):
        diags = []
        _add(diags, "invalid_root_type", "error", None, path,
             f"inputs must be a mapping, got {type(inputs).__name__}")
        return {}, True, diags

    validated: dict[str, Any] = {}
    fatal = False
    diags: list[dict] = []
    for key, raw in inputs.items():
        if key not in _KNOWN_FIELDS:
            _add(diags, "unknown_key", "error", None, _loc(path, str(key)),
                 f"unknown input key {key!r}; only the documented fields are allowed")
            fatal = True
            continue
        if raw is None:
            validated[key] = None
            continue
        if key in _BOOL_FIELDS:
            if isinstance(raw, bool):
                validated[key] = raw
            else:
                _add(diags, "invalid_type", "error", None, _loc(path, key),
                     f"{key!r} must be a boolean or null, got {type(raw).__name__}")
                validated[key] = None
            continue
        if key in _INTEGER_FIELDS:
            if isinstance(raw, bool):
                _add(diags, "invalid_type", "error", None, _loc(path, key),
                     f"{key!r} must be an integer, not a boolean")
                validated[key] = None
            elif isinstance(raw, int):
                if _int_fits_float(raw):
                    validated[key] = raw
                else:
                    _add(diags, "out_of_range", "error", None, _loc(path, key),
                         f"{key!r} is outside the float64 range and cannot be used as a count")
                    validated[key] = None
            elif isinstance(raw, float) and math.isfinite(raw) and float(raw).is_integer():
                validated[key] = int(raw)
            else:
                _add(diags, "invalid_type", "error", None, _loc(path, key),
                     f"{key!r} must be an integer or null, got {type(raw).__name__}")
                validated[key] = None
            continue
        # 数值字段。
        if isinstance(raw, bool):
            _add(diags, "invalid_type", "error", None, _loc(path, key),
                 f"{key!r} must be a number, not a boolean")
            validated[key] = None
        elif isinstance(raw, (int, float)):
            try:
                value = float(raw)
            except (OverflowError, ValueError):
                _add(diags, "non_finite", "error", None, _loc(path, key),
                     f"{key!r} must be a finite real number, got a value outside the "
                     "float64 range")
                validated[key] = None
            else:
                if math.isfinite(value):
                    validated[key] = value
                else:
                    _add(diags, "non_finite", "error", None, _loc(path, key),
                         f"{key!r} must be a finite real number, got {raw!r}")
                    validated[key] = None
        else:
            _add(diags, "invalid_type", "error", None, _loc(path, key),
                 f"{key!r} must be a number or null, got {type(raw).__name__}")
            validated[key] = None
    return validated, fatal, diags


# --- 各读数 ----------------------------------------------------------------

def _recoil(v, diags, path):
    reading = "recoil_index"
    required = ("broadside_lb", "displacement_lt", "freeboard_distributed_ft",
                "gun_super_factor", "beam_bulges_ft")
    missing = [k for k in required if v.get(k) is None]
    if missing:
        _missing(diags, reading, path, missing)
        return None

    displacement = v["displacement_lt"]
    beam = v["beam_bulges_ft"]
    if displacement == 0.0:
        _zero(diags, reading, path, "displacement_lt")
        return None
    if beam == 0.0:
        _zero(diags, reading, path, "beam_bulges_ft")
        return None

    cbrt = _cpow(displacement, 1.0 / 3.0)
    if cbrt is None:
        _power(diags, reading, path, "displacement_lt")
        return None

    base = (v["broadside_lb"] / displacement) * v["freeboard_distributed_ft"] \
        * v["gun_super_factor"] / beam
    inner = _cpow(cbrt / beam * 3.0, 2.0)
    if inner is None:
        _power(diags, reading, path, "beam_bulges_ft")
        return None
    recoil = base * inner * 7.0

    # 原式：stabilityAdj > 0 才做该除法；已知 0 / 负都不进入。
    stability = v.get("stability_adjusted")
    if stability is None:
        _undetermined(diags, reading, path, "stability_adjusted",
                      "recoil adjustment branch (stability_adjusted > 0) cannot be decided")
        return None
    if stability > 0.0:
        steadiness = v.get("steadiness_adjusted")
        if steadiness is None:
            _missing(diags, reading, path, ["steadiness_adjusted"])
            return None
        denom = stability * ((50.0 - steadiness) / 150.0 + 1.0)
        if denom == 0.0:
            _zero(diags, reading, path,
                  "stability_adjusted * ((50 - steadiness_adjusted)/150 + 1)")
            return None
        recoil = recoil / denom
    return _finite(diags, reading, path, recoil)


def _flotation(v, diags, path):
    reading = "flotation_lb"
    composite = v.get("composite_strength")
    if composite is None:
        _missing(diags, reading, path, ["composite_strength"])
        return None

    if composite >= 0.0:
        use_capped = v.get("use_capped_freeboard")
        if use_capped is None:
            _undetermined(diags, reading, path, "use_capped_freeboard",
                          "freeboard branch (capped vs distributed) cannot be decided")
            return None
        freeboard_key = "freeboard_cap_ft" if use_capped else "freeboard_distributed_ft"
        missing = [k for k in ("waterplane_sqft", "displacement_lt", freeboard_key,
                               "stability_adjusted") if v.get(k) is None]
        if missing:
            _missing(diags, reading, path, missing)
            return None

        flotation = (v[freeboard_key] * v["waterplane_sqft"] / TON
                     + v["displacement_lt"]) / 2.0
        stability = v["stability_adjusted"]
        if stability > 1.0:
            flotation = flotation * math.sqrt(stability)
        else:
            powered = _cpow(stability, 4.0)
            if powered is None:
                _power(diags, reading, path, "stability_adjusted")
                return None
            flotation = flotation * powered
        if composite < 1.0:
            flotation = flotation * composite
    else:
        # 负 composite：基础直接置 0，之后仍按原式读 room / date。
        flotation = 0.0

    room = v.get("room_float")
    date = v.get("date_float")
    missing = [k for k in ("room_float", "date_float") if v.get(k) is None]
    if missing:
        _missing(diags, reading, path, missing)
        return None

    if room > 1.0:
        powered = _cpow(room, 2.0)
        if powered is None:
            _power(diags, reading, path, "room_float")
            return None
        flotation = flotation / powered
    else:
        if room == 0.0:
            _zero(diags, reading, path, "room_float")
            return None
        flotation = flotation / room
    flotation = flotation * date
    return _finite(diags, reading, path, flotation)


def _shell(v, diags, path, flotation):
    reading = "shell_hits"
    calibre = v.get("first_gun_calibre_in")
    if calibre is None:
        _undetermined(diags, reading, path, "first_gun_calibre_in",
                      "reference calibre branch (calibre > 0 vs explicit 0) cannot be "
                      "decided; unknown is not treated as 0")
        return None, None
    # 原式：calibre > 0 用本炮，否则（含明确 0）用 6 in 比较弹。
    reference = calibre if calibre > 0.0 else 6.0

    if flotation is None:
        _missing(diags, reading, path, ["flotation_lb"])
        return None, reference
    date = v.get("date_float")
    if date is None:
        _missing(diags, reading, path, ["date_float"])
        return None, reference
    cubed = _cpow(reference, 3.0)
    if cubed is None:
        _power(diags, reading, path, "first_gun_calibre_in")
        return None, reference
    denom = cubed / 2.0 * date
    if denom == 0.0:
        _zero(diags, reading, path, "first_gun_calibre_in^3 / 2 * date_float")
        return None, reference
    return _finite(diags, reading, path, flotation / denom), reference


def _torpedo_reference_diameter(v):
    weight = v.get("first_torpedo_weapon_weight_lt")
    if weight is None:
        # 未知弹重无法判定基准分支，标签同样未知。
        return None
    if weight > 0.0:
        # 正弹重分支按声明口径标注；count 缺失不把标签改成 20in。
        return v.get("first_torpedo_diameter_in")
    return 20.0


def _torpedo(v, diags, path, flotation):
    reading = "torpedo_hits"
    reference = _torpedo_reference_diameter(v)

    required = ("room_float", "beam_bulges_ft", "bulkhead_thickness_in",
                "bulkhead_length_ft", "hull_length_ft", "bulkhead_height_ft",
                "draught_ft", "stability_adjusted", "space_hull_fraction")
    missing = [k for k in required if v.get(k) is None]
    if missing:
        _missing(diags, reading, path, missing)
        return None, reference
    if flotation is None:
        _missing(diags, reading, path, ["flotation_lb"])
        return None, reference

    room = v["room_float"]
    beam = v["beam_bulges_ft"]
    length = v["hull_length_ft"]
    draught = v["draught_ft"]
    if length == 0.0:
        _zero(diags, reading, path, "hull_length_ft")
        return None, reference
    if draught == 0.0:
        _zero(diags, reading, path, "draught_ft")
        return None, reference
    if room == 0.0:
        _zero(diags, reading, path, "room_float")
        return None, reference
    if length + beam == 0.0:
        _zero(diags, reading, path, "hull_length_ft + beam_bulges_ft")
        return None, reference

    first = _cpow(flotation / 10000.0, 1.0 / 3.0)
    second = _cpow(beam / 75.0, 2.0)
    bulkhead_base = (v["bulkhead_thickness_in"] / 2.0 * v["bulkhead_length_ft"] / length) \
        / 0.65 * v["bulkhead_height_ft"] / draught
    third = _cpow(bulkhead_base, 1.0 / 3.0)
    if first is None:
        _power(diags, reading, path, "flotation_lb")
        return None, reference
    if second is None:
        _power(diags, reading, path, "beam_bulges_ft")
        return None, reference
    if third is None:
        _power(diags, reading, path, "bulkhead_thickness_in/bulkhead_length_ft/draught_ft")
        return None, reference

    torpedo = (first + second + third * flotation / 35000.0 * beam / 50.0) \
        / room * length / (length + beam)

    stability = v["stability_adjusted"]
    if stability < 1.0:
        powered = _cpow(stability, 4.0)
        if powered is None:
            _power(diags, reading, path, "stability_adjusted")
            return None, reference
        torpedo = torpedo * powered
    torpedo = torpedo * (1.0 - v["space_hull_fraction"])

    weight = v.get("first_torpedo_weapon_weight_lt")
    count = v.get("first_torpedo_count")
    if weight is None:
        # 未知弹重：源式 >0 分支无法判定，不臆造基准值。
        _undetermined(diags, reading, path, "first_torpedo_weapon_weight_lt",
                      "torpedo weight branch (weight > 0 vs explicit non-positive) "
                      "cannot be decided; no baseline is substituted")
        return None, reference
    if weight > 0.0:
        # 正弹重分支要求可用的正 count；否则该不自洽输入不可算。
        if count is None:
            _missing(diags, reading, path, ["first_torpedo_count"])
            return None, reference
        if count <= 0:
            _add(diags, "invalid_value", "error", reading,
                 _loc(path, "first_torpedo_count"),
                 "first_torpedo_weapon_weight_lt > 0 requires a positive "
                 "first_torpedo_count")
            return None, reference
        per_torpedo = weight / count
        if per_torpedo == 0.0:
            _zero(diags, reading, path,
                  "first_torpedo_weapon_weight_lt / first_torpedo_count")
            return None, reference
        torpedo = torpedo * (1.313 / per_torpedo)
    # weight 已知且非正：源式的 else 基准分支，不做重量缩比。
    return _finite(diags, reading, path, torpedo), reference


# --- 公开接口 --------------------------------------------------------------

def evaluate(inputs: dict, *, path: str = "$", source_single: bool = False) -> dict:
    """计算原版性能页的四个经验读数。

    ``inputs`` 是字段 -> 数值 / 布尔 / null 的映射；``None`` 表示未知（已知 0 不是未知）。
    返回 ``{method_version, status, values, diagnostics, provenance}``；从不抛异常。
    """
    validated, fatal, diags = _validate(inputs, path)
    values = {key: None for key in _READING_KEYS}

    if not fatal:
        recoil = _recoil(validated, diags, path)
        flotation = _flotation(validated, diags, path)
        if flotation is not None and source_single:
            try:
                if __package__:
                    from .sps_single import flotation as source_flotation
                else:
                    from sps_single import flotation as source_flotation
                flotation=_finite(diags,'flotation_lb',path,source_flotation(validated))
            except (ArithmeticError,ValueError,TypeError) as error:
                _add(diags,'source_single_unavailable','error','flotation_lb',path,str(error));flotation=None
        shell, shell_reference = _shell(validated, diags, path, flotation)
        torpedo, torpedo_reference = _torpedo(validated, diags, path, flotation)
        values["recoil_index"] = recoil
        values["flotation_lb"] = flotation
        values["shell_hits"] = shell
        values["torpedo_hits"] = torpedo
        values["shell_reference_calibre_in"] = shell_reference
        values["torpedo_reference_diameter_in"] = torpedo_reference

    present = sum(1 for value in values.values() if value is not None)
    if present == len(_READING_KEYS):
        status = "available"
    elif present:
        status = "partial"
    else:
        status = "unavailable"

    return {
        "method_version": METHOD_VERSION,
        "status": status,
        "values": values,
        "diagnostics": diags,
        "provenance": dict(_PROVENANCE),
    }
