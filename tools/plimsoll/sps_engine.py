# -*- coding: utf-8 -*-
"""原版 SpringSharp 3b3 动力页纯状态单元。

只复现原 ``EngineControl`` 的动力页状态：阻力/功率读数、机种与燃料描述、
源告警、机械/燃料/负载/船体余重链，以及 ``speedBtn_Click`` 的离散反算求解。

设计约束：
- 纯函数、无 GUI、无文件 IO、只用标准库；
- 输入字典不被修改；字段缺失 / ``None`` 表示未知，已知 ``0`` 是有效值；
- 复刻原 float32 边界：字段级 ``Single`` 舍入 + ``ToString()`` 七位有效数字往返；
- 未选择、未知、非法组合分开；单一缺项不抹掉独立读数；
- 只在原 ``engineCalc`` / ``bunkerCalc`` 明确的分支把 NaN 局部置 0 并留原因；
- 原非有限结果用 ``None`` + 诊断表示，不伪装成健康的 0；
- 出错时给出结构化诊断，不抛原始异常。

来源：SpringSharp 3b3 ``EngineControl``（原程序集
SHA256 82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc）：

* ``EngineControl.cs:377`` ``resistanceCalc``
* ``EngineControl.cs:438`` ``speedHpCalc``
* ``EngineControl.cs:460`` ``speedBtn_Click``（离散步进 + 文本往返求解）
* ``EngineControl.cs:538`` ``engineCalc``（含 :541-601 机种系数）
* ``EngineControl.cs:632`` ``engineLayout``（描述与年代告警）
* ``EngineControl.cs:888`` ``bunkerCalc``
* ``EngineControl.cs:924`` ``loadWeightCalc``
* ``EngineControl.cs:936`` ``hullWeightCalc``（H0 显示残差、H1 = H0 + 炮重 − 舷侧重）

这里不调用旧 ``engines.compute``（不是同一方法），也不改动显式重量台账。
这些是原版设计页读数，不涉及任何真实舰船。
"""
from __future__ import annotations

import math
import struct
from typing import Any

try:  # 作为 plimsoll 包的一部分导入
    from . import concept_estimates as _kernels
except ImportError:  # 直接以顶层模块导入（测试/脚本）
    import concept_estimates as _kernels

METHOD_VERSION = "sps-3b3-engine-v1"
SOURCE_ASSEMBLY = "SpringSharpMono 3.0.3032.29945"
SOURCE_SHA256 = "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc"

# ``MainForm.RANGE``：原 bunkerCalc 里的比例常数，不是页面的 range_nm 输入。
SOURCE_RANGE_CONSTANT = 7000.0

# --- 本单元消费的字段名（与 sship_fields 注册表一致） ----------------------

FUEL_ORDER = ("fuel_coal", "fuel_oil", "fuel_diesel", "fuel_petrol", "fuel_batteries")
ENGINE_ORDER = ("engine_simple", "engine_compound", "engine_turbine")
DRIVE_ORDER = ("drive_direct", "drive_geared", "drive_electric", "drive_hydraulic")

ENGINE_NUMERIC_PARAMETERS = (
    "speed_max_kn",
    "speed_cruise_kn",
    "range_nm",
    "shafts",
    "coal_percentage",
)
ENGINE_BOOLEAN_PARAMETERS = FUEL_ORDER + ENGINE_ORDER + DRIVE_ORDER
ENGINE_PARAMETERS = ENGINE_NUMERIC_PARAMETERS + ENGINE_BOOLEAN_PARAMETERS

# 原 hull 页导出的原生字段（tools/plimsoll/sps_hull.py 的 HULL_FIELDS）。
HULL_KEYS = ("length", "lengthEffect", "displacement", "coSharp", "wettedSurface", "dateEngine")
GUNS_KEYS = ("gunsWeight", "borneWeight", "magazine")
AUXILIARY_KEYS = ("weight", "miscWeight")
ARMOUR_KEYS = ("weight",)

DEFAULT_EDITING = {"power_locked": False, "power_hp": None, "locked_bunker_lt": None}

_READING_KEYS = (
    "hpMax",
    "hpCruise",
    "engine",
    "engineWeight",
    "dispFactor",
    "bunker",
    "bunkerMax",
    "loadWeight",
    "hullWeight",
    "hullWeightDisplayed",
)

_ENGINE_KEYS = (
    "hpMax",
    "hpCruise",
    "lengthPower",
    "speedHp",
    "friction",
    "wave",
    "powerWave",
    "frictMax",
    "frictCruise",
    "waveMax",
    "waveCruise",
    "powerWaveMax",
    "powerWaveCruise",
    "engine",
    "engineWeight",
    "dispFactor",
    "engineCount",
    "engineRecipSimple",
    "engineRecipComplex",
    "engineTurbine",
    "bunker",
    "bunkerMax",
    "loadWeight",
    "hullWeight",
    "hullWeightDisplayed",
    "pctCoal",
    "pctEngineWeight",
    "pctHullWeight",
    "pctLoadWeight",
    "speedMax",
    "speedCruise",
    "range",
    "screws",
    "fuelString",
    "engineString1",
    "engineString2",
    "driveString",
    "description",
    "fuelArray",
    "engineArray",
    "driveArray",
)

_PROVENANCE = {
    "kind": "original design-page state",
    "origin": "SpringSharp 3b3 EngineControl (resistanceCalc/speedHpCalc/engineCalc/"
              "engineLayout/bunkerCalc/loadWeightCalc/hullWeightCalc/speedBtn_Click)",
    "source_assembly": SOURCE_ASSEMBLY,
    "source_assembly_sha256": SOURCE_SHA256,
    "note": (
        "Reproduces the original engine page's derived readings and its discrete "
        "power-recalculation solver; float32 field boundaries and the 7-significant-digit "
        "text round-trip are reproduced. Not an equivalence proof and not any real ship."
    ),
    "units": {
        "hpMax": "hp",
        "hpCruise": "hp",
        "lengthPower": "ft",
        "friction": "wave/friction split of the resistance factor",
        "wave": "wave/friction split of the resistance factor",
        "engine": "long tons (machinery displacement)",
        "engineWeight": "long tons",
        "dispFactor": "dimensionless",
        "bunker": "long tons",
        "bunkerMax": "long tons",
        "loadWeight": "long tons",
        "hullWeight": "long tons (H1)",
        "hullWeightDisplayed": "long tons (H0)",
        "pctCoal": "percent",
        "speedMax": "kn",
        "speedCruise": "kn",
        "range": "nm",
    },
}

# 求解器安全上限：源循环无迭代界，未知输入下可能不收敛。
MAX_SOLVER_ITERATIONS = 2_000_000


# --- float32 / .NET Single 文本往返 ----------------------------------------

def _f32(value):
    """把 float64 舍入到 IEEE-754 单精度（原字段类型）。"""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return number
    try:
        return struct.unpack("<f", struct.pack("<f", number))[0]
    except OverflowError:
        return math.copysign(float("inf"), number)


def _g7(value):
    """近似 .NET ``Single.ToString()``（G 常规格式，7 位有效数字）。"""
    try:
        return format(float(value), ".7g")
    except (TypeError, ValueError, OverflowError):
        return None


def _reparse(value):
    """``speedMaxBox.Text = x.ToString()`` 之后的 ``float.Parse`` 边界。"""
    text = _g7(value)
    if text is None:
        return None
    try:
        return _f32(float(text))
    except (TypeError, ValueError, OverflowError):
        return None


def _div(a, b):
    """IEEE 除法：``x/0`` 给 ±inf，``0/0`` 给 nan，不抛异常。"""
    if b == 0.0:
        if a == 0.0 or not math.isfinite(a):
            return float("nan")
        return math.copysign(float("inf"), a)
    return a / b


def _pow(base, exponent):
    """``Math.Pow`` 语义：负底 + 非整数指数 -> None；非有限照原样传播。"""
    if base < 0.0 and exponent != int(exponent):
        return None
    try:
        result = base ** exponent
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    if isinstance(result, complex) or not isinstance(result, (int, float)):
        return None
    if not math.isfinite(result):
        return result
    return float(result)


# --- 诊断 ------------------------------------------------------------------

def _add(diags, code, severity, field, message):
    diags.append({"code": code, "severity": severity, "field": field, "message": message})


def _loc(path, field):
    return "%s.%s" % (path, field)


def _missing(diags, path, pairs):
    for field, value in pairs:
        if value is None:
            _add(diags, "missing_dependency", "error", _loc(path, field),
                 "%s is unknown or missing; the dependent reading is not invented" % field)


# --- 输入校验 --------------------------------------------------------------

def _validate_parameters(parameters, path, diags):
    """返回 (validated, fatal)。fatal 表示整单不可用。"""
    if not isinstance(parameters, dict):
        _add(diags, "invalid_root_type", "error", path,
             "parameters must be a mapping, got %s" % type(parameters).__name__)
        return {}, True

    out = dict(parameters)
    for name in ENGINE_NUMERIC_PARAMETERS:
        if name not in parameters:
            continue
        raw = parameters[name]
        if raw is None:
            out[name] = None
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _add(diags, "invalid_type", "error", _loc(path, name),
                 "%s must be a number or null, got %s" % (name, type(raw).__name__))
            out[name] = None
            continue
        try:
            value = float(raw)
        except (OverflowError, ValueError):
            value = float("inf")
        if not math.isfinite(value):
            _add(diags, "non_finite", "error", _loc(path, name),
                 "%s must be a finite real number" % name)
            out[name] = None
            continue
        if value < 0.0:
            _add(diags, "negative_input", "warning", _loc(path, name),
                 "%s is negative; kept as typed by the source field" % name)
        out[name] = value

    for name in ENGINE_BOOLEAN_PARAMETERS:
        if name not in parameters:
            continue
        raw = parameters[name]
        if raw is None:
            out[name] = None
        elif isinstance(raw, bool):
            out[name] = raw
        else:
            _add(diags, "invalid_type", "error", _loc(path, name),
                 "%s must be a boolean or null, got %s" % (name, type(raw).__name__))
            out[name] = None

    shafts = out.get("shafts")
    if shafts is not None:
        if float(shafts).is_integer():
            out["shafts"] = int(shafts)
        else:
            _add(diags, "invalid_value", "error", _loc(path, "shafts"),
                 "shafts must be a whole number, got %r" % shafts)
            out["shafts"] = None

    coal = out.get("coal_percentage")
    if coal is not None and not (0.0 <= coal <= 100.0):
        _add(diags, "coal_percentage_out_of_range", "warning",
             _loc(path, "coal_percentage"),
             "Percentage coal must be between 0% and 100%")
    return out, False


def _read_number(container, key):
    if not isinstance(container, dict) or key not in container:
        return None
    raw = container[key]
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        value = float(raw)
    except (OverflowError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _normalise_editing(editing, diags):
    out = dict(DEFAULT_EDITING)
    if isinstance(editing, dict):
        out.update(editing)
    elif editing is not None:
        _add(diags, "invalid_type", "error", "editing",
             "editing must be a mapping or null")
    out["power_locked"] = bool(out.get("power_locked"))
    for key in ("power_hp", "locked_bunker_lt"):
        value = out.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _add(diags, "invalid_type", "error", _loc("editing", key),
                 "%s must be a number or null" % key)
            out[key] = None
            continue
        value = float(value)
        if not math.isfinite(value):
            _add(diags, "non_finite", "error", _loc("editing", key),
                 "%s must be a finite real number" % key)
            out[key] = None
            continue
        out[key] = _f32(value)
    return out


# --- 机种系数（域内复用 concept_estimates 的同一恢复分支） -----------------

def _engine_coefficient(kind_index, year):
    """原 engineCalc :542-601。"""
    if year is not None and 1850 <= int(year) <= 1950:
        try:
            return float(_kernels.engine_coefficient(
                _kernels.ENGINE_KINDS[kind_index], int(year)))
        except ValueError:
            pass
    value = float(year) if year is not None else 0.0
    if kind_index == 0:
        if value < 1885:
            return 1.2 + (value - 1860) * 0.05
        if value < 1950:
            return 2.45 + (value - 1885) * 0.025
        return 4.075
    if kind_index == 1:
        if value < 1906:
            return 1.2 + (value - 1860) * 0.05
        if value < 1911:
            return 3.5 + (value - 1906)
        if value < 1950:
            return 7.5 + (value - 1910) * 0.025
        return 8.5
    if value < 1898:
        return 1.2 + (value - 1860) * 0.05
    if value < 1903:
        return 1.0 + (value - 1898) * 0.5
    if value < 1910:
        return 4 + (value - 1903)
    if value < 1950:
        return 11.0 + (value - 1910) * 0.2
    return 19.0


# --- engineLayout：描述与年代告警 ------------------------------------------

def _layout(params, year, path, diags):
    out = dict(params)
    fuel = [params.get(name) for name in FUEL_ORDER]
    raw_engine = [params.get(name) for name in ENGINE_ORDER]
    raw_drive = [params.get(name) for name in DRIVE_ORDER]

    # 无煤无油 -> 清空蒸汽机勾选（原 :638-644）。
    if fuel[0] is False and fuel[1] is False:
        engine = [False, False, False]
        for name in ENGINE_ORDER:
            out[name] = False
    else:
        engine = list(raw_engine)

    # 纯电池（无煤油、无柴油汽油）强制电传动（原 :801-810）。
    forced_electric = (
        fuel[4] is True and fuel[0] is False and fuel[1] is False
        and fuel[2] is False and fuel[3] is False
    )
    if forced_electric:
        for name, value in zip(DRIVE_ORDER, (False, False, True, False)):
            out[name] = value

    # 煤比例归一化（原 :860-878）。
    pct_coal = params.get("coal_percentage")
    if fuel[0] is False:
        pct_coal = 0.0
        out["coal_percentage"] = 0.0
    elif fuel[0] is True and fuel[1] is False and fuel[2] is False and fuel[3] is False:
        pct_coal = 100.0
        out["coal_percentage"] = 100.0
    elif fuel[0] is None:
        pct_coal = None

    drive_effective = [out.get(name) for name in DRIVE_ORDER]
    flags_known = all(flag is not None for flag in (fuel + engine + raw_drive))
    if flags_known:
        fuel_string = _fuel_string(fuel)
        engine_string1, engine_string2 = _engine_strings_final(
            fuel, engine, drive_effective, forced_electric)
        drive_string = _drive_string(drive_effective)
        description = fuel_string + engine_string1 + engine_string2 + drive_string
    else:
        _add(diags, "layout_undetermined", "error", _loc(path, "fuelArray"),
             "fuel/engine/drive selection is incomplete; the source description "
             "branches cannot be decided without inventing selections")
        fuel_string = engine_string1 = engine_string2 = drive_string = None
        description = None

    warnings = _layout_warnings(year, engine, raw_drive, fuel, pct_coal)
    return out, {
        "fuelArray": fuel,
        "engineArray": engine,
        "driveArray": [out.get(name) for name in DRIVE_ORDER],
        "fuelString": fuel_string,
        "engineString1": engine_string1,
        "engineString2": engine_string2,
        "driveString": drive_string,
        "description": description,
        "pctCoal": pct_coal,
        "warnings": warnings,
        "forced_electric": forced_electric,
    }


def _fuel_string(fuel):
    coal, oil, diesel, petrol, batteries = fuel
    if not any(fuel):
        return "No fuel, "
    if coal and not oil and not petrol:
        return "Coal fired boilers, "
    if not coal and oil and not petrol:
        return "Oil fired boilers, "
    if not coal and not oil and diesel and not petrol:
        return "Diesel "
    if not coal and not oil and not diesel and petrol:
        return "Petrol "
    if not coal and not oil and not diesel and not petrol and batteries:
        return "Battery powered "
    if coal and oil and not petrol:
        return "Coal and oil fired boilers, "
    return "ERROR: Revise fuels, "


def _engine_strings_final(fuel, engine, drive, forced_electric):
    """原 engineLayout :745-831 的机种描述，逐分支复刻。"""
    coal, oil, diesel, petrol, batteries = fuel
    simple, compound, turbine = engine
    direct, geared, electric, hydraulic = drive
    second = ""
    if coal or oil:
        if not any(engine):
            first = "ERROR: no steam engines, "
        elif simple and not compound and not turbine:
            first = "simple reciprocating steam engines, "
        elif not simple and compound and not turbine:
            first = "complex reciprocating steam engines, "
        elif not simple and not compound and turbine:
            first = "steam turbines, "
        elif simple and compound and not turbine:
            first = "reciprocating steam engines, "
        elif (simple or compound) and turbine:
            if simple and compound and turbine:
                first = "ERROR: Too many types of steam engines, "
            else:
                first = "reciprocating cruising steam engines"
                second = " and steam turbines "
        else:
            first = "ERROR: Revise fuels or engines, "
        if diesel or petrol or batteries:
            if batteries and not diesel:
                second += " plus batteries, "
            elif diesel and not batteries:
                second += " plus diesel motors, "
            else:
                second += " ERROR: Revise auxilliary fuel, "
    elif batteries:
        if forced_electric:
            first = ""
        elif direct or geared or hydraulic:
            first = "Internal combustion engines plus batteries, "
        else:
            first = "Internal combustion generators plus batteries, "
    elif (petrol or diesel) and electric and not direct and not geared:
        first = "Internal combustion generators, "
    else:
        first = "Internal combustion motors, "
    if batteries and petrol and (coal or oil):
        first = "ERROR: Too many different fuels, "
    return first, second


def _drive_string(drive):
    direct, geared, electric, hydraulic = drive
    if not any(drive):
        return "No drive to shaft"
    if direct and not geared and not electric and not hydraulic:
        return "Direct drive"
    if not direct and geared and not electric and not hydraulic:
        return "Geared drive"
    if not direct and not geared and electric and not hydraulic:
        return "Electric motors"
    if not direct and not geared and not electric and hydraulic:
        return "Hydraulic drive"
    if not direct and geared and electric and not hydraulic:
        return "Electric cruising motors plus geared drives"
    return "ERROR: Revise drives"


def _layout_warnings(year, engine, drive, fuel, pct_coal):
    """原 engineLayout 的年代告警与煤比例提示，稳定 code + 原文。"""
    warnings = []
    simple, compound, turbine = engine
    geared = drive[1]
    electric = drive[2]
    coal, oil, diesel, petrol, batteries = fuel

    def warn(code, condition, message, field):
        if condition:
            warnings.append({"code": code, "severity": "warning",
                             "field": field, "message": message})

    if year is not None:
        warn("too_early_geared_drives", year < 1911 and geared is True,
             "Warning: Too early for geared drives", "drive_geared")
        warn("too_early_diesel_motors", year < 1904 and diesel is True,
             "Warning: Too early for diesel motors", "fuel_diesel")
        warn("too_early_petrol_motors", year < 1898 and petrol is True,
             "Warning: Too early for petrol motors", "fuel_petrol")
        warn("too_early_batteries", year < 1898 and batteries is True,
             "Warning: Too early for batteries", "fuel_batteries")
        warn("too_early_steam_turbines", year < 1898 and turbine is True,
             "Warning: Too early for steam turbines", "engine_turbine")
        warn("too_early_oil_fired_boilers", year < 1898 and oil is True,
             "Warning: Too early for oil fired boilers", "fuel_oil")
        warn("too_early_electric_drives", year < 1898 and electric is True,
             "Warning: Too early for electric drives", "drive_electric")
        warn("too_early_complex_reciprocating", year < 1885 and compound is True,
             "Warning: Too early for complex reciprocating steam engines",
             "engine_compound")

    if coal is True and pct_coal is not None:
        prompt = (pct_coal == 0.0 or (pct_coal == 100.0 and oil is True)
                  or diesel is True or petrol is True)
        warn("coal_percentage_prompt", prompt,
             "Enter percentage of bunker tonnage devoted to coal fired boilers",
             "coal_percentage")
    return warnings


# --- 阻力 / 功率 -----------------------------------------------------------

def _power_length(length, effect, speed):
    """原 speedHpCalc :440-451，逐字段 float32 复刻。"""
    if speed <= 15.0:
        return _f32(_f32(length) - _f32(_f32(effect) - _f32(length)))
    if speed >= 25.0:
        return _f32(effect)
    inner = _f32(_f32(_f32(effect) - _f32(length)) * _f32(_f32(speed - 20.0) / 5.0))
    return _f32(inner + _f32(length))


def _speed_hp(hull, speed, path, diags):
    """原 speedHpCalc :438-458（Math.Pow 走 double，末尾 cast 回 Single）。"""
    if speed is None:
        return None, None
    length = hull.get("length")
    effect = hull.get("lengthEffect")
    displacement = hull.get("displacement")
    coefficient = hull.get("coSharp")
    wetted = hull.get("wettedSurface")
    year = hull.get("dateEngine")
    if None in (length, effect, displacement, coefficient, wetted):
        _missing(diags, path, [("hull.length", length), ("hull.lengthEffect", effect),
                               ("hull.displacement", displacement),
                               ("hull.coSharp", coefficient),
                               ("hull.wettedSurface", wetted)])
        return None, None
    length_hp = _power_length(length, effect, speed)
    if length_hp is None:
        return None, None
    if length_hp == 0.0:
        _add(diags, "zero_denominator", "error", _loc(path, "lengthPower"),
             "speedHpCalc divides by the power length, which is 0")
        return None, length_hp
    cbrt = _pow(displacement, 2.0 / 3.0)
    quartic = _pow(speed, 4.0)
    fraction = _pow(speed, 1.83)
    if cbrt is None or quartic is None or fraction is None:
        _add(diags, "power_domain", "error", _loc(path, "speed"),
             "speedHpCalc needs a real-valued power term for this speed")
        return None, length_hp
    value = _div(cbrt, length_hp) * coefficient * quartic + 0.01 * wetted * fraction
    value = _f32(_div(value * speed, 184.1666667))
    if year is not None and year < 1890:
        factor = _f32(1.0 + _f32(_f32(1890.0 - year) / 100.0))
        value = _f32(value * factor)
    return value, length_hp


def _wave_term(hull, speed, path, diags):
    """原 resistanceCalc :390-393 的波浪项（用 L，不用功率长度）。"""
    displacement = hull.get("displacement")
    length = hull.get("length")
    coefficient = hull.get("coSharp")
    if speed is None or None in (displacement, length, coefficient):
        _missing(diags, path, [("speed", speed), ("hull.displacement", displacement),
                               ("hull.length", length), ("hull.coSharp", coefficient)])
        return None
    if length == 0.0:
        _add(diags, "zero_denominator", "error", _loc(path, "wave"),
             "the wave resistance term divides by hull length, which is 0")
        return None
    cbrt = _pow(displacement, 2.0 / 3.0)
    quartic = _pow(speed, 4.0)
    if cbrt is None or quartic is None:
        _add(diags, "power_domain", "error", _loc(path, "wave"),
             "the wave resistance term needs a real-valued power for this speed")
        return None
    return _f32(_div(cbrt, length) * coefficient * quartic)


def _friction_term(wetted, speed):
    if wetted is None or speed is None:
        return None
    power = _pow(speed, 1.83)
    if power is None:
        return None
    return _f32(0.01 * wetted * power)


def _power_wave(wave, friction, speed):
    if wave is None or friction is None:
        return None
    if speed == 0.0:
        return 0.0
    total = wave + friction
    if total == 0.0:
        return None
    return _f32(_div(wave, total) * 100.0)


# --- engineCalc / bunker / weights -----------------------------------------

def _machinery(hp_max, coefficients, year, pct_coal, displacement, borne, armour, misc,
               path, diags):
    """原 engineCalc :600-624。返回 (engine, dispFactor, engineWeight, weights)。"""
    count = len(coefficients)
    if count == 0:
        total = 0.0
    else:
        total = _f32(0.0)
        for coefficient in coefficients:
            total = _f32(total + _f32(coefficient))
    average = _f32(_div(total, float(count))
                   * _f32(1.1 - _f32(_div(pct_coal, 1000.0))))
    raw = _f32(_div(hp_max, average))
    if year is not None and year < 1890:
        raw = _f32(_div(raw, _f32(1.0 + _f32(_f32(1890.0 - year) / 100.0))))
    if raw is not None and math.isnan(raw):
        _add(diags, "source_nan_to_zero", "warning", _loc(path, "engine"),
             "the source machinery displacement is NaN locally (engineCalc); set to 0")
        return 0.0, None, None, (0.0, None, None)
    raw = _finite(raw, diags, _loc(path, "engine"), "engine")
    if raw is None:
        return None, None, None, (None, None, None)
    if None in (displacement, borne, armour, misc):
        _missing(diags, path, [("hull.displacement", displacement),
                               ("guns.borneWeight", borne), ("armour.weight", armour),
                               ("auxiliary.miscWeight", misc)])
        return raw, None, None, (raw, None, None)
    load = _f32(_f32(_f32(raw + _f32(borne * 8.0)) + armour) + misc)
    disp_factor = _f32(min(_div(displacement, load), 10.0))
    weight = _f32(_div(raw, 2.0))
    if disp_factor is not None and disp_factor < 1.0:
        if 600.0 <= displacement < 5000.0:
            weight = _f32(weight * math.pow(disp_factor, 1.0 - displacement / 5000.0))
        elif displacement < 600.0:
            weight = _f32(weight * math.pow(disp_factor, 0.88))
    return raw, disp_factor, weight, (raw, disp_factor, weight)


def _bunker_of(range_value, pct_coal, year, hp_cruise, speed_cruise, displacement,
               reciprocating, path, diags):
    """原 bunkerCalc :888-917，逐字段 float32 复刻。"""
    if None in (range_value, pct_coal, hp_cruise, speed_cruise, displacement):
        return None
    if year is None:
        return None
    bunker = _div(_f32(range_value),
                  _f32(1.0 + _f32(_f32(0.4 * _f32(100.0 - pct_coal)) / 100.0)))
    if reciprocating or year < 1898:
        divisor = _f32(1.0 - _f32(_f32(1910.0 - year) / 70.0))
    elif year < 1920:
        divisor = _f32(1.0 + _f32(_f32(year - 1910.0) / 20.0))
    elif year < 1950:
        divisor = _f32(1.5 + _f32(_f32(year - 1920.0) / 60.0))
    else:
        divisor = 2.0
    bunker = _f32(_div(bunker, divisor))
    scale = _f32(_f32(_f32(_div(1.8, hp_cruise)) * SOURCE_RANGE_CONSTANT) * speed_cruise)
    scale = _f32(scale * 0.1)
    bunker = _div(bunker, scale)
    return _f32(bunker + _f32(displacement * 0.005))


def _percent_of(weight, displacement):
    if weight is not None and displacement is not None and displacement > 0.0:
        return _f32(_div(weight, displacement))
    return 0.0 if weight is not None else None


def _nan_to_zero(value, diags, field, method):
    if value is not None and isinstance(value, float) and math.isnan(value):
        _add(diags, "source_nan_to_zero", "warning", field,
             "the source %s result is NaN locally; set to 0" % method)
        return 0.0
    return value


def _finite(value, diags, field, reading):
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return None
        _add(diags, "non_finite_result", "error", field,
             "%s is not a finite real number under the original expression" % reading)
        return None
    return value


# --- evaluate ---------------------------------------------------------------

def evaluate(parameters, hull=None, guns=None, auxiliary=None, armour=None,
             *, editing=None, path="$"):
    """计算原版动力页的完整状态。

    ``parameters`` 是 sship_fields 注册名 -> 值（源页单位）。``hull`` / ``guns`` /
    ``auxiliary`` / ``armour`` 是各单元导出的原生字段。``None`` 表示未知；已知 0 有效。
    返回 ``{method_version, status, parameters, editing, engine, diagnostics, provenance}``；
    从不抛异常。
    """
    diags: list[dict[str, Any]] = []
    if not isinstance(parameters, dict):
        _add(diags, "invalid_root_type", "error", path,
             "parameters must be a mapping, got %s" % type(parameters).__name__)
        return {
            "method_version": METHOD_VERSION,
            "status": "unavailable",
            "parameters": {},
            "editing": _normalise_editing(editing, diags),
            "engine": {key: None for key in _ENGINE_KEYS},
            "diagnostics": diags,
            "provenance": dict(_PROVENANCE),
        }

    params, _ = _validate_parameters(parameters, path + ".parameters", diags)
    edit = _normalise_editing(editing, diags)

    hull_v = {key: _read_number(hull, key) for key in HULL_KEYS}
    guns_v = {key: _read_number(guns, key) for key in GUNS_KEYS}
    aux_v = {key: _read_number(auxiliary, key) for key in AUXILIARY_KEYS}
    armour_v = {key: _read_number(armour, key) for key in ARMOUR_KEYS}

    date_engine = hull_v.get("dateEngine")
    if date_engine is None:
        date_engine = _read_number(params, "engine_year")
    if date_engine is not None:
        date_engine = int(date_engine)
    hull_v["dateEngine"] = date_engine

    out_params, layout = _layout(params, date_engine, path + ".engine", diags)

    engine = {key: None for key in _ENGINE_KEYS}
    engine["fuelArray"] = layout["fuelArray"]
    engine["engineArray"] = layout["engineArray"]
    engine["driveArray"] = layout["driveArray"]
    engine["fuelString"] = layout["fuelString"]
    engine["engineString1"] = layout["engineString1"]
    engine["engineString2"] = layout["engineString2"]
    engine["driveString"] = layout["driveString"]
    engine["description"] = layout["description"]
    engine["pctCoal"] = layout["pctCoal"]

    speed_max = params.get("speed_max_kn")
    speed_cruise = params.get("speed_cruise_kn")
    range_value = params.get("range_nm")
    screws = params.get("shafts")
    pct_coal = layout["pctCoal"]

    if edit["power_locked"]:
        _add(diags, "power_lock_pending_recalc", "warning", _loc(path, "editing"),
             "Incomplete: Recalculate max speed")

    frict_max = _friction_term(hull_v["wettedSurface"], speed_max)
    frict_cruise = _friction_term(hull_v["wettedSurface"], speed_cruise)
    wave_max = _wave_term(hull_v, speed_max, path + ".engine", diags)
    wave_cruise = _wave_term(hull_v, speed_cruise, path + ".engine", diags)
    if speed_max is not None and hull_v["wettedSurface"] is None:
        _missing(diags, path + ".engine", [("hull.wettedSurface", None)])

    engine["frictMax"] = frict_max
    engine["frictCruise"] = frict_cruise
    engine["waveMax"] = wave_max
    engine["waveCruise"] = wave_cruise
    engine["friction"] = {"max": frict_max, "cruise": frict_cruise}
    engine["wave"] = {"max": wave_max, "cruise": wave_cruise}

    power_wave_max = _power_wave(wave_max, frict_max, speed_max)
    power_wave_cruise = _power_wave(wave_cruise, frict_cruise, speed_cruise)
    engine["powerWaveMax"] = power_wave_max
    engine["powerWaveCruise"] = power_wave_cruise
    engine["powerWave"] = {"max": power_wave_max, "cruise": power_wave_cruise}

    hp_max, length_power_max = _speed_hp(hull_v, speed_max, path + ".engine", diags)
    if speed_cruise is not None and speed_max is not None:
        cruise_speed = min(speed_cruise, speed_max)
    else:
        cruise_speed = speed_cruise
    hp_cruise, length_power = _speed_hp(hull_v, cruise_speed, path + ".engine", diags)
    if length_power is None:
        length_power = length_power_max
    engine["hpMax"] = hp_max
    engine["hpCruise"] = hp_cruise
    engine["lengthPower"] = length_power
    engine["speedHp"] = hp_cruise
    engine["speedMax"] = speed_max
    engine["speedCruise"] = speed_cruise
    engine["range"] = range_value
    engine["screws"] = screws

    # resistanceCalc 功率告警 :418-430（机种未定时不臆造）。
    if screws is not None and hp_max is not None and all(
            flag is not None for flag in layout["engineArray"]):
        simple, compound, turbine = layout["engineArray"]
        per_shaft = float("inf") if screws == 0 and hp_max > 0.0 else _div(hp_max, screws)
        if per_shaft > 20000.0 and not turbine and (simple or compound):
            _add(diags, "too_much_power_reciprocating", "warning",
                 _loc(path, "engine.engineArray"),
                 "Warning: Too much power for reciprocating engines")
        elif per_shaft > 75000.0:
            _add(diags, "too_much_power_shafts", "warning", _loc(path, "engine.shafts"),
                 "Warning: Too much power for number of propellor shafts")

    # engineCalc :538-624
    if all(flag is not None for flag in layout["engineArray"]):
        fuel = layout["fuelArray"]
        coefficients = []
        if layout["engineArray"][0]:
            coefficients.append(_engine_coefficient(0, date_engine))
        else:
            coefficients.append(0.0)
        if layout["engineArray"][1]:
            coefficients.append(_engine_coefficient(1, date_engine))
        else:
            coefficients.append(0.0)
        if layout["engineArray"][2] or fuel[3] or fuel[2] or fuel[4]:
            coefficients.append(_engine_coefficient(2, date_engine))
        else:
            coefficients.append(0.0)
        # engineCount 只在三个分支各自选中时 +1（原 :542-601）。
        engine_count = (1 if layout["engineArray"][0] else 0) \
            + (1 if layout["engineArray"][1] else 0) \
            + (1 if (layout["engineArray"][2] or fuel[3] or fuel[2] or fuel[4]) else 0)
        engine["engineCount"] = engine_count
        engine["engineRecipSimple"] = _f32(coefficients[0])
        engine["engineRecipComplex"] = _f32(coefficients[1])
        engine["engineTurbine"] = _f32(coefficients[2])
        used = []
        if layout["engineArray"][0]:
            used.append(coefficients[0])
        if layout["engineArray"][1]:
            used.append(coefficients[1])
        if layout["engineArray"][2] or fuel[3] or fuel[2] or fuel[4]:
            used.append(coefficients[2])
        if hp_max is None or pct_coal is None:
            _missing(diags, path + ".engine", [("hpMax", hp_max),
                                               ("pctCoal", pct_coal)])
            engine["engine"] = None
        else:
            raw, disp_factor, weight, _ = _machinery(
                hp_max, used, date_engine, pct_coal, hull_v["displacement"],
                guns_v["borneWeight"], armour_v["weight"], aux_v["miscWeight"],
                path + ".engine", diags)
            engine["engine"] = raw
            engine["dispFactor"] = disp_factor
            engine["engineWeight"] = weight
    else:
        _add(diags, "engine_undetermined", "error", _loc(path, "engine.engineArray"),
             "the selected engine kinds are incomplete; machinery cannot be summed")
        engine["engineCount"] = None

    if engine["engineWeight"] is not None:
        engine["pctEngineWeight"] = _percent_of(engine["engineWeight"],
                                                hull_v["displacement"])

    # bunkerCalc :888-922
    reciprocating = False
    if all(flag is not None for flag in layout["engineArray"]):
        reciprocating = bool(layout["engineArray"][0] or layout["engineArray"][1])
    bunker = _bunker_of(range_value, pct_coal, date_engine, hp_cruise, speed_cruise,
                        hull_v["displacement"], reciprocating, path + ".engine", diags)
    bunker = _nan_to_zero(bunker, diags, _loc(path, "engine.bunker"), "bunkerCalc")
    engine["bunker"] = _finite(bunker, diags, _loc(path, "engine.bunker"), "bunker")
    if engine["bunker"] is not None:
        engine["bunkerMax"] = _f32(engine["bunker"] * 1.8)

    # loadWeightCalc :924-934
    if None in (hull_v["displacement"], guns_v["magazine"], engine["bunker"]):
        _missing(diags, path + ".engine", [("hull.displacement", hull_v["displacement"]),
                                           ("guns.magazine", guns_v["magazine"]),
                                           ("engine.bunker", engine["bunker"])])
    else:
        engine["loadWeight"] = _f32(_f32(hull_v["displacement"] * 0.02)
                                    + guns_v["magazine"] + engine["bunker"])
        engine["pctLoadWeight"] = _percent_of(engine["loadWeight"],
                                              hull_v["displacement"])

    # hullWeightCalc :936-947：H0 为显示残差，H1 = H0 + 炮重 − 舷侧重
    formers = (hull_v["displacement"], guns_v["gunsWeight"], aux_v["weight"],
               armour_v["weight"], engine.get("engineWeight"), engine.get("loadWeight"),
               aux_v["miscWeight"])
    if None in formers:
        _missing(diags, path + ".engine", [
            ("hull.displacement", hull_v["displacement"]),
            ("guns.gunsWeight", guns_v["gunsWeight"]),
            ("auxiliary.weight", aux_v["weight"]),
            ("armour.weight", armour_v["weight"]),
            ("engine.engineWeight", engine.get("engineWeight")),
            ("engine.loadWeight", engine.get("loadWeight")),
            ("auxiliary.miscWeight", aux_v["miscWeight"])])
    elif guns_v["borneWeight"] is None:
        _missing(diags, path + ".engine", [("guns.borneWeight", None)])
    else:
        h0 = _f32(hull_v["displacement"] - guns_v["gunsWeight"] - aux_v["weight"]
                  - armour_v["weight"] - engine["engineWeight"] - engine["loadWeight"]
                  - aux_v["miscWeight"])
        engine["hullWeightDisplayed"] = h0
        engine["pctHullWeight"] = _percent_of(h0, hull_v["displacement"])
        engine["hullWeight"] = _f32(h0 + guns_v["gunsWeight"] - guns_v["borneWeight"])

    diags.extend(layout["warnings"])

    present = sum(1 for key in _READING_KEYS if engine.get(key) is not None)
    layout_complete = layout["description"] is not None
    if present == len(_READING_KEYS) and layout_complete:
        status = "available"
    elif present or layout_complete:
        status = "partial"
    else:
        status = "unavailable"

    return {
        "method_version": METHOD_VERSION,
        "status": status,
        "parameters": out_params,
        "editing": edit,
        "engine": engine,
        "diagnostics": diags,
        "provenance": dict(_PROVENANCE),
    }


# --- 离散反算求解（原 speedBtn_Click :460-530） ----------------------------

def _solve_power(parameters, editing, hull=None, path="$", diags=None):
    """返回 (parameters, editing, hit_limit)。逐字复刻源的七段/四段步进循环。"""
    diags = [] if diags is None else diags
    hull_v = {key: _read_number(hull, key) for key in HULL_KEYS}
    date_engine = hull_v.get("dateEngine")
    if date_engine is None:
        date_engine = _read_number(parameters, "engine_year")
    if date_engine is not None:
        date_engine = int(date_engine)
    hull_v["dateEngine"] = date_engine

    speed_cruise = parameters.get("speed_cruise_kn")
    range_value = parameters.get("range_nm")
    pct_coal = parameters.get("coal_percentage")
    fuel = [parameters.get(name) for name in FUEL_ORDER]
    engine_flags = [parameters.get(name) for name in ENGINE_ORDER]
    if fuel[0] is False:
        pct_coal = 0.0
    elif fuel[0] is True and fuel[1] is False and fuel[2] is False and fuel[3] is False:
        pct_coal = 100.0
    if fuel[0] is False and fuel[1] is False:
        engine_flags = [False, False, False]
    reciprocating = bool(engine_flags[0] or engine_flags[1])
    displacement = hull_v.get("displacement")

    store_power = _f32(editing.get("power_hp"))
    store_bunker_raw = editing.get("locked_bunker_lt")
    store_bunker = None if store_bunker_raw is None else _f32(store_bunker_raw)

    out_params = dict(parameters)
    out_editing = dict(editing)

    def hp_of(speed):
        return _speed_hp(hull_v, speed, path + ".engine", diags)[0]

    if store_power is None:
        _add(diags, "power_target_missing", "error", _loc(path, "editing.power_hp"),
             "no locked power target is stored; max speed was not recalculated")
        return out_params, out_editing, False
    if hp_of(0.0) is None:
        _add(diags, "solver_undetermined", "error", _loc(path, "editing"),
             "the power curve cannot be evaluated; max speed was not recalculated")
        return out_params, out_editing, False

    step = _f32(0.0)
    speed_field = _reparse(step)
    hp = hp_of(speed_field)
    hit_limit = False

    def advance(loop_step):
        nonlocal step, speed_field, hp
        step = _f32(step + loop_step)
        speed_field = _reparse(step)
        hp = hp_of(speed_field)

    loops = (
        (lambda: hp is not None and hp <= store_power and step < 50.0, 10.0),
        (lambda: hp is not None and hp >= store_power and step > 0.0, -1.0),
        (lambda: hp is not None and hp <= store_power and step < 50.0, 0.1),
        (lambda: hp is not None and hp >= store_power and step > 0.0, -0.01),
        (lambda: hp is not None and hp <= store_power and step < 50.0, 0.001),
        (lambda: hp is not None and hp >= store_power and step > 0.0, -0.0001),
        (lambda: hp is not None and hp <= store_power and step > 0.0, 1.0e-05),
    )
    for condition, loop_step in loops:
        for _ in range(MAX_SOLVER_ITERATIONS):
            if not condition() or not math.isfinite(step):
                break
            advance(loop_step)
        else:
            hit_limit = True
            break

    out_params["speed_max_kn"] = speed_field

    # 航程反算（原 :504-528），仅在 range > 0 时。
    if range_value is not None and range_value > 0.0 and store_bunker is not None:
        cruise = speed_cruise
        if cruise is not None and speed_field is not None:
            cruise = min(cruise, speed_field)
        hp_cruise = hp_of(cruise)
        rstep = _f32(0.0)
        range_field = _reparse(rstep)
        bunker = _bunker_of(range_field, pct_coal, date_engine, hp_cruise, speed_cruise,
                            displacement, reciprocating, path + ".engine", diags)

        def advance_range(loop_step):
            nonlocal rstep, range_field, bunker
            rstep = _f32(rstep + loop_step)
            range_field = _reparse(rstep)
            bunker = _bunker_of(range_field, pct_coal, date_engine, hp_cruise,
                                speed_cruise, displacement, reciprocating,
                                path + ".engine", diags)

        range_loops = (
            (lambda: bunker is not None and bunker <= store_bunker, 1000.0),
            (lambda: bunker is not None and bunker >= store_bunker, -100.0),
            (lambda: bunker is not None and bunker <= store_bunker, 10.0),
            (lambda: bunker is not None and bunker >= store_bunker, -1.0),
        )
        for condition, loop_step in range_loops:
            for _ in range(MAX_SOLVER_ITERATIONS):
                if not condition() or not math.isfinite(rstep):
                    break
                advance_range(loop_step)
            else:
                hit_limit = True
                break
        out_params["range_nm"] = range_field

    # 求解结束后源再次锁定（storePower/storeBunker 取新值）。
    final_hp = hp_of(out_params.get("speed_max_kn"))
    final_cruise = speed_cruise
    if final_cruise is not None and out_params.get("speed_max_kn") is not None:
        final_cruise = min(final_cruise, out_params.get("speed_max_kn"))
    final_bunker = _bunker_of(out_params.get("range_nm"), pct_coal, date_engine,
                              hp_of(final_cruise), speed_cruise, displacement,
                              reciprocating, path + ".engine", diags)
    out_editing["power_locked"] = True
    if final_hp is not None:
        out_editing["power_hp"] = _f32(final_hp)
    if final_bunker is not None and not math.isnan(final_bunker):
        out_editing["locked_bunker_lt"] = _f32(final_bunker)
    if hit_limit:
        _add(diags, "solver_iteration_limit", "error", _loc(path, "editing"),
             "the discrete solver did not converge inside %d iterations; the last "
             "finite step is reported, not a fabricated root" % MAX_SOLVER_ITERATIONS)
    return out_params, out_editing, hit_limit


# --- apply_edit -------------------------------------------------------------

def apply_edit(parameters, editing, command, hull=None, guns=None, auxiliary=None,
               armour=None, *, path="$"):
    """动力页编辑命令。返回 ``{parameters, editing, diagnostics}``，永不抛异常。

    处理 ``set_power_lock(enabled)`` / ``set_parameter``（动力页名称，含 ``power_hp``）/
    ``recalculate_power``。其它页面铁名称与通用集合由协调器 ``sps_compat`` 负责。
    """
    diags: list[dict[str, Any]] = []
    params = dict(parameters) if isinstance(parameters, dict) else {}
    edit = _normalise_editing(editing, diags)

    if not isinstance(command, dict):
        _add(diags, "invalid_command", "error", path, "command must be a mapping")
        return {"parameters": params, "editing": edit, "diagnostics": diags}

    kind = command.get("kind")

    if kind == "set_power_lock":
        enabled = command.get("enabled", command.get("value"))
        if not isinstance(enabled, bool):
            _add(diags, "invalid_command", "error", _loc(path, "enabled"),
                 "set_power_lock needs a boolean 'enabled'")
            return {"parameters": params, "editing": edit, "diagnostics": diags}
        if enabled:
            result = evaluate(params, hull, guns, auxiliary, armour)
            hp_max = result["engine"].get("hpMax")
            bunker = result["engine"].get("bunker")
            if hp_max is None:
                _add(diags, "power_target_missing", "error", _loc(path, "power_hp"),
                     "the current max power is unknown; the lock target was not stored")
            edit["power_locked"] = True
            edit["power_hp"] = None if hp_max is None else _f32(hp_max)
            edit["locked_bunker_lt"] = None if bunker is None else _f32(bunker)
            diags.extend(result["diagnostics"])
        else:
            edit["power_locked"] = False
        return {"parameters": params, "editing": edit, "diagnostics": diags}

    if kind == "set_parameter":
        name = command.get("name")
        value = command.get("value")
        if name == "power_hp":
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(float(value)):
                _add(diags, "invalid_value", "error", _loc(path, "power_hp"),
                     "power_hp must be a finite number")
                return {"parameters": params, "editing": edit, "diagnostics": diags}
            edit["power_hp"] = _f32(float(value))
            return {"parameters": params, "editing": edit, "diagnostics": diags}
        if name in ENGINE_BOOLEAN_PARAMETERS:
            if not isinstance(value, bool):
                _add(diags, "invalid_value", "error", _loc(path, str(name)),
                     "%s must be a boolean" % name)
                return {"parameters": params, "editing": edit, "diagnostics": diags}
            params[name] = value
            return {"parameters": params, "editing": edit, "diagnostics": diags}
        if name in ENGINE_NUMERIC_PARAMETERS:
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(float(value)):
                _add(diags, "invalid_value", "error", _loc(path, str(name)),
                     "%s must be a finite number" % name)
                return {"parameters": params, "editing": edit, "diagnostics": diags}
            params[name] = float(value)
            return {"parameters": params, "editing": edit, "diagnostics": diags}
        _add(diags, "out_of_scope", "error", _loc(path, str(name)),
             "%r is not an engine-page field; the coordinating command layer owns it"
             % (name,))
        return {"parameters": params, "editing": edit, "diagnostics": diags}

    if kind == "recalculate_power":
        out_params, out_editing, _ = _solve_power(params, edit, hull, path, diags)
        return {"parameters": out_params, "editing": out_editing, "diagnostics": diags}

    if kind == "set_scale":
        _add(diags, "no_engine_scale", "error", _loc(path, "page"),
             "the original engine page has no scale selector (page %r)"
             % (command.get("page"),))
        return {"parameters": params, "editing": edit, "diagnostics": diags}

    _add(diags, "unsupported_command", "error", path,
         "the engine unit does not handle command %r" % (kind,))
    return {"parameters": params, "editing": edit, "diagnostics": diags}
