# -*- coding: utf-8 -*-
"""原版 SpringSharp 3b3 船体页 + 干舷页：有界纯状态单元（hull / freeboard）。

只复现旧程序里"船体尺寸与干舷几何"这一块的算术与耦合，供兼容模式调用：

- ``HullControl``  ``lengthCalc`` / ``draughtCalc`` / ``displacementCalc`` /
  ``waterplaneAreaCalc`` / ``coSharpCalc``（HullControl.cs:1128-1163, 1210-1248,
  1250-1311, 1313-1343, 1345-1365）；
- ``HullControl.beamEnter`` 的普通船宽 → 凸出船宽 / 舱壁船宽耦合（HullControl.cs:1039-1067）；
- ``FreeboardControl``  ``depthLockBtnClick``（208-231）、``freeboardEnter``（234-288）、
  ``freeboardCalc``（387-494）、``freeboardCapCalc``（496-524）与两个估测按钮
  ``btnFlushClick`` / ``btnBreakClick``（339-385）。

设计约束：
- 纯函数、无 GUI、无文件 IO、只用标准库；两个公开接口都不修改传入对象；
- 规范内部单位 ft / long ton / degree（原程序内部单位）；``parameters`` 仍保持
  原保存页尺度（``hull_scale`` 0=英尺 1=米），干舷值跟随船体页尺度（原程序读
  ``hull.scale``）；
- 字段缺失 / ``None`` 一律表示未知（保持未知，不猜数）；已知 ``0`` 不是未知；
  错类型 / bool 冒充数值 / 非有限 → 结构化诊断，不抛原始异常；
- 浮点按 float64 计算，连续读数不四舍五入；只有原程序用 ``ToString("n2")``
  文本回读的地方（两个干舷预设、普通船宽耦合写回）才按源精度往返；
- 单一缺项不抹掉其它独立读数；值不可用时给 ``null`` + 该输出字段的诊断；
- 原式为 NaN / 非有限的领域（例如 Cb<0.3 的水线面修正、0 吃水）按源判为不可用，
  不补正数；有限负值按源保留（例如 depth lock 下可能出现的负干舷）。

来源：SpringSharp 3b3 原程序集 SHA256
``82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc``。
这些是经验 / 几何读数，不涉及任何真实舰船。

已知取舍（实现完成报告里同样列出）：
1. 原 ``beamEnter`` 只有一个分支条件 ``arm.scale.SelectedIndex == 1``：它决定凸出船宽框与
   舱壁船宽框**同一个**文本写成"米（n2）"还是"英尺（原样）"，随后两个框各自用**自己**
   页面尺度（凸出船宽用船体页、舱壁船宽用装甲页）``fpCheck`` 读回。两个尺度下拉可以
   各自独立选择，所以 ``hull_scale`` 与 ``armour_scale`` 不一致是原程序能到达的合法状态
   （原生文件 ``hull_scale=1`` / ``armour_scale=0`` 就是这样）。本单元**逐字复刻**这个
   混单位读数，并给出具名诊断 ``source_quirk``，不做"纠正"。
2. depth lock 的 8 个深度快照只在 ``depthLockBtnClick`` 的锁定分支写入（解锁不改快照）。
   锁定期间编辑 FC/QD 端点时，原程序由随后的 ``draughtCalc`` 按事件顺序把该端点重算成
   ``深度 - 吃水``，快照本身不变。本单元保持同一事件顺序：快照不动，端点值由快照导出
   （用户写进页面的值会被这个派生值覆盖）。锁定期间 FD/AD 四个框在原程序里禁用，本单元
   同样拒绝其编辑并给出告警。
3. 干舷页的深吃水读数（``draughtDeep``）依赖性能页 ``dispMaxLoad``；性能 / 发动机
   步进求解由父模块负责，本单元不输出。
4. ``bow`` / ``stern`` 缺失或 ``null`` 一律保持未知（相关读数给 ``null`` + 字段诊断），
   绝不代填 0；显式默认值（例如原生默认设计的 ``bow=0`` / ``stern=-1``）由上层 I/O /
   默认设计单元给出。索引 ``-1`` 是原程序可保存的"未选"状态，按其分支落空处理。
"""
from __future__ import annotations

import copy
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

METHOD_VERSION = "sps-3b3-hull-v1"

SOURCE_SHA256 = "82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc"

# MainForm 常数（原程序集）。
FEET2METRES = 0.3048
TON = 35.0              # 每长吨海水立方英尺
_DATE_SPAN = 66.666664  # MainForm.dateAdjCalc 1890 年前斜率

HULL_FIELDS = (
    "length", "lengthOA", "lengthStem", "beam", "beamBulges", "draught",
    "draughtSide", "block", "displacement", "coSharp", "lengthEffect",
    "lengthBeam", "coWaterPlane", "waterplaneArea", "wettedSurface",
    "speedNatural", "crewMin", "crewMax", "dateHull", "dateEngine",
    "dateAdjFloat",
)

FREEBOARD_FIELDS = (
    "freeFCFor", "freeFCAft", "freeFDFor", "freeFDAft", "freeADFor",
    "freeADAft", "freeQDFor", "freeQDAft", "fcLength", "fdLength", "adLength",
    "qdLength", "freeFC", "freeFD", "freeAD", "freeQD", "freeboard",
    "freeDistributed", "freeboardCap", "lengthBow", "lengthRam", "lengthStern",
)

# 注册参数名 -> 原 numeric 字段名（MainForm.openFileCalc 的赋值目标）。
ENDPOINTS = (
    ("freeboard_forecastle_fore", "freeFCFor"),
    ("freeboard_forecastle_aft", "freeFCAft"),
    ("freeboard_flat_deck_fore", "freeFDFor"),
    ("freeboard_flat_deck_aft", "freeFDAft"),
    ("freeboard_afterdeck_fore", "freeADFor"),
    ("freeboard_afterdeck_aft", "freeADAft"),
    ("freeboard_quarterdeck_fore", "freeQDFor"),
    ("freeboard_quarterdeck_aft", "freeQDAft"),
)
ENDPOINT_FIELDS = tuple(field for _param, field in ENDPOINTS)
ENDPOINT_PARAM = {param: field for param, field in ENDPOINTS}       # parameter -> field
ENDPOINT_PARAM_NAME = {field: param for param, field in ENDPOINTS}  # field -> parameter

# 锁定深度时原程序禁用的四个框（fdFor/fdAft/adFor/adAft）。
DEPTH_PINNED_FIELDS = frozenset({"freeFDFor", "freeFDAft", "freeADFor", "freeADAft"})

# 干舷段长百分比与固定比例。
_PERCENT_PARAMETERS = ("freeboard_forecastle_length", "freeboard_flat_deck_length",
                       "freeboard_quarterdeck_length")

# 船体页/干舷页里按页面尺度保存的长度型注册字段（bow 角不在其中）。
PAGE_LENGTH_PARAMETERS = (
    "length_waterline", "beam_moulded", "beam_at_bulges", "draught_normal",
    "freeboard_ram_length", "freeboard_length_stern",
) + tuple(param for param, _field in ENDPOINTS)

# 本单元消费的注册字段；其余页面字段原样保留。
CONSUMED_PARAMETERS = frozenset(PAGE_LENGTH_PARAMETERS + _PERCENT_PARAMETERS + (
    "hull_scale", "hull_year", "engine_year", "block_coefficient_normal",
    "stern", "bow", "shafts", "freeboard_length_bow",
    # follow_hull 耦合会写回的装甲页字段（本单元只在此一处触碰）
    "armour_bulkhead_beam", "armour_scale",
))

# 本单元编辑状态（其余键原样保留）。
EDITING_DEFAULTS = {
    "length_driver": "waterline",
    "displacement_driver": "block",
    "depth_locked": False,
    "bulkhead_beam_mode": "follow_hull",
}

LENGTH_DRIVERS = ("waterline", "overall")
DISPLACEMENT_DRIVERS = ("block", "displacement")
BULKHEAD_BEAM_MODES = ("follow_hull", "fixed")

_SOURCE_NOTES = (
    "HullControl.cs:808-841 length/block driver toggles and their button text",
    "HullControl.cs:1039-1067 beamEnter: bulges follows the ordinary beam; the shared bulkhead beam follows while noIntVoid",
    "HullControl.cs:1068-1116 bulges/block/displacement entries and their recalculations",
    "HullControl.cs:1128-1163 lengthCalc: stem, ram, stern extension, LWL/LOA driver",
    "HullControl.cs:1210-1248 draughtCalc: depth-locked endpoint rebuild and draughtSide",
    "HullControl.cs:1250-1311 displacementCalc: Cb<->displacement reciprocity, wetted surface, crew band",
    "HullControl.cs:1313-1343 waterplaneAreaCalc: stern/screw conditioned waterplane coefficient",
    "HullControl.cs:1345-1365 coSharpCalc: coSharp, length/beam, effective length, natural speed",
    "FreeboardControl.cs:208-231 depthLockBtnClick: the 8-point depth snapshot",
    "FreeboardControl.cs:234-288 freeboardEnter: page-scale text reads",
    "FreeboardControl.cs:339-385 btnFlushClick/btnBreakClick preset geometry",
    "FreeboardControl.cs:387-494 freeboardCalc: segment mixes and averages",
    "FreeboardControl.cs:496-524 freeboardCapCalc: beam/3 and submerged casemate branches",
    "ArmourControl.cs:554-562 bulkheadBeamBoxTextChanged: a focused edit clears noIntVoid",
)


# --------------------------------------------------------------- small helpers

def _diag(code: str, severity: str, field: str, message: str) -> dict:
    return {"code": code, "severity": severity, "field": field, "message": message}


def _n2(value: float) -> float:
    """C# ``float.ToString("n2")`` (half away from zero), read back as a float."""
    try:
        text = Decimal(repr(float(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return float(value)
    return float(text)


def _to_ft(value: float, page_scale: int) -> float:
    """Save page -> internal feet (``fpCheck(text, feet2metres, scale)``)."""
    return value / FEET2METRES if page_scale == 1 else value


def _from_ft(value: float, page_scale: int) -> float:
    """Internal feet -> save page (``metricCalc(x, feet2metres)``)."""
    return value * FEET2METRES if page_scale == 1 else value


def _beam_coupling_text(beam_ft: float, armour_scale: int) -> float:
    """``HullControl.beamEnter``'s single text for *both* coupled boxes.

    The source has one branch condition, ``arm.scale.SelectedIndex == 1``::

        if (arm.scale.SelectedIndex == 1)
            beamBulgesBox.Text = main.metricCalc(beam, Con.feet2metres).ToString("n2");
        else
            beamBulgesBox.Text = beam.ToString();

    and it reuses the same expression for ``arm.bulkheadBeamBox.Text``. So the text
    unit is chosen by the *armour* page combo even though the bulges box is re-read
    with the *hull* page combo. Nothing here is corrected: the mixed-unit read is
    the original behaviour and is flagged by a ``source_quirk`` diagnostic.
    """
    if armour_scale == 1:
        return _n2(beam_ft * FEET2METRES)   # metricCalc(...).ToString("n2")
    return float(beam_ft)                   # x.ToString()


def _page_text_read(text: float, page_scale: int) -> float:
    """``fpCheck(text, feet2metres, scale)``: each box reads with its own page unit."""
    return text if page_scale == 0 else text / FEET2METRES


def _preset_box_ft(value_ft: float, page_scale: int) -> float:
    """The preset buttons format with ``"n2"`` in *both* page units.

    ``freeEstBow`` is converted with ``metricCalc`` first when the hull page is
    metric, but ``fcForBox.Text = freeEstBow.ToString("n2")`` is unconditional.
    """
    display = value_ft if page_scale == 0 else value_ft * FEET2METRES
    rounded = _n2(display)
    return rounded if page_scale == 0 else rounded / FEET2METRES


def _pow(base: float, exponent: float):
    """C# ``Math.Pow`` in the real domain, or ``None`` where the source yields NaN."""
    try:
        result = float(base) ** float(exponent)
    except (OverflowError, ZeroDivisionError, ValueError, TypeError):
        return None
    if isinstance(result, complex) or not math.isfinite(result):
        return None
    return float(result)


def _coerce_number(value: Any):
    """(float, None) or (None, reason). Booleans are not numeric values here."""
    if isinstance(value, bool):
        return None, "boolean is not a numeric value"
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None, "value is not finite"
        return number, None
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except (TypeError, ValueError):
            return None, "text is not a numeric value"
        if not math.isfinite(number):
            return None, "value is not finite"
        return number, None
    return None, "unsupported value type %s" % type(value).__name__


def _copy_mapping(value: Any):
    """(mapping copy, reason or None) for the two validated containers."""
    if not isinstance(value, Mapping):
        return {}, "value must be a mapping"
    try:
        return copy.deepcopy(dict(value)), None
    except Exception:  # pragma: no cover - defensive, the contract says "never raise"
        return dict(value), "value contains uncopyable entries"


def _copy_editing(value: Any):
    """The editing state is optional: ``None`` means "no upper-layer edits yet"."""
    if value is None:
        return {}, None
    return _copy_mapping(value)


class _Reader:
    """Validated reads of one parameters/editing pair; never raises."""

    def __init__(self, source: Mapping, diags: list):
        self.source = source
        self.diags = diags

    def number(self, name: str):
        value = self.source.get(name)
        if value is None:
            return None
        number, reason = _coerce_number(value)
        if reason is not None:
            self.diags.append(_diag("invalid_parameter", "error", name,
                                    "%s: %s" % (name, reason)))
            return None
        return number

    def integer(self, name: str):
        value = self.source.get(name)
        if value is None:
            return None
        number, reason = _coerce_number(value)
        if reason is not None or abs(number - round(number)) > 1e-9:
            self.diags.append(_diag("invalid_parameter", "error", name,
                                    "%s must be an integer value" % name))
            return None
        return int(round(number))

    def enum(self, name: str, count: int):
        value = self.source.get(name)
        if value is None:
            return None
        number, reason = _coerce_number(value)
        if reason is not None:
            self.diags.append(_diag("invalid_parameter", "error", name,
                                    "%s: %s" % (name, reason)))
            return None
        index = int(round(number))
        # -1 is the source's "nothing selected" state; every equality test falls
        # through. Any other out-of-range index cannot be a combo selection.
        if abs(number - index) > 1e-9 or not -1 <= index < count:
            self.diags.append(_diag("invalid_parameter", "error", name,
                                    "%s must be an index -1..%d" % (name, count - 1)))
            return None
        return index


# ------------------------------------------------------------------ the solver

def _solve(parameters: Mapping, editing: Mapping, submerged_casemate: bool) -> dict:
    """One full source pass: readings + page write-backs + internals + diagnostics."""
    diags: list = []
    reader = _Reader(parameters, diags)

    # ---- page scales -------------------------------------------------------
    scale = _page_scale(parameters, "hull_scale", diags)
    armour_scale = _page_scale(parameters, "armour_scale", diags)

    def size(name):
        value = reader.number(name)
        return None if value is None else _to_ft(value, scale)

    length_param = size("length_waterline")
    beam = size("beam_moulded")
    beam_bulges = size("beam_at_bulges")
    draught = size("draught_normal")
    block_param = reader.number("block_coefficient_normal")
    endpoint_param = {field: size(param) for param, field in ENDPOINTS}
    percent_raw = {name: reader.number(name) for name in _PERCENT_PARAMETERS}
    length_bow = reader.number("freeboard_length_bow")   # degrees, never scaled
    length_ram = size("freeboard_ram_length")
    length_stern = size("freeboard_length_stern")
    shafts = reader.number("shafts")
    screws = None if shafts is None else int(shafts)

    hull_year = reader.integer("hull_year")
    engine_year = reader.integer("engine_year")
    # No default is invented here: a missing/null enum stays unknown and every
    # reading that depends on it comes back null with a field diagnostic.
    stern = reader.enum("stern", 4)
    bow = reader.enum("bow", 4)

    for name, value in (("length_waterline", length_param), ("beam_moulded", beam),
                        ("beam_at_bulges", beam_bulges), ("draught_normal", draught),
                        ("freeboard_ram_length", length_ram),
                        ("freeboard_length_stern", length_stern)):
        if value is not None and value < 0.0:
            diags.append(_diag("negative_input", "warning", name,
                               "%s is negative; the source fpCheck reports an error and keeps it"
                               % name))

    # ---- editing state -----------------------------------------------------
    edit = dict(editing) if isinstance(editing, Mapping) else {}
    length_driver = _edit_choice(edit, "length_driver", LENGTH_DRIVERS, "waterline", diags)
    displacement_driver = _edit_choice(edit, "displacement_driver",
                                       DISPLACEMENT_DRIVERS, "block", diags)
    bulkhead_beam_mode = _edit_choice(edit, "bulkhead_beam_mode",
                                      BULKHEAD_BEAM_MODES, "follow_hull", diags)
    locked_raw = edit.get("depth_locked")
    if locked_raw not in (None, True, False):
        diags.append(_diag("invalid_editing", "warning", "depth_locked",
                           "depth_locked must be a boolean"))
    depth_locked = locked_raw is True
    depths = edit.get("depths") if isinstance(edit.get("depths"), Mapping) else None

    def unavailable(field, why):
        diags.append(_diag("output_unavailable", "warning", field, why))
        return None

    # ---- length driver (HullControl.lengthCalc) ----------------------------
    overall_value = edit.get("overall_length")
    if overall_value is not None:
        overall_value, reason = _coerce_number(overall_value)
        if reason is not None:
            diags.append(_diag("invalid_editing", "error", "overall_length",
                               "overall_length: %s" % reason))
            overall_value = None
    use_overall = length_driver == "overall" and overall_value is not None
    if length_driver == "overall" and overall_value is None:
        diags.append(_diag("driver_fallback", "warning", "length_driver",
                           "overall_length is unavailable; reading the saved waterline instead"))

    length_oa = _to_ft(overall_value, scale) if use_overall else None
    length = None if use_overall else length_param

    if length_bow is None or endpoint_param["freeFCFor"] is None:
        length_stem = None
        diags.append(_diag("output_unavailable", "warning", "lengthStem",
                           "lengthStem needs the forecastle fore freeboard and the bow angle"))
    else:
        length_stem = endpoint_param["freeFCFor"] * math.tan(length_bow * math.pi / 180.0)

    extension = _extension_ft(length_bow, length_ram, length_stern, bow, length_stem)
    if use_overall:
        if extension is None:
            length = unavailable(
                "length", "length needs the overall length less its bow/stern additions")
        else:
            length = max(length_oa - extension, 0.0)
    elif length is None or extension is None:
        length_oa = unavailable(
            "lengthOA", "lengthOA needs the saved waterline length and the bow/stern additions")
    else:
        length_oa = length + extension

    # ---- displacement driver (HullControl.displacementCalc) ----------------
    block = None
    displacement = None
    if displacement_driver == "block":
        block = block_param
        if None in (length, beam_bulges, draught, block):
            displacement = unavailable(
                "displacement",
                "displacement needs the waterline length, bulged beam, draught and Cb")
        else:
            displacement = length * beam_bulges * draught * block / TON
    else:
        normal_displacement = edit.get("normal_displacement_lt")
        if normal_displacement is not None:
            normal_displacement, reason = _coerce_number(normal_displacement)
            if reason is not None:
                diags.append(_diag("invalid_editing", "error", "normal_displacement_lt",
                                   "normal_displacement_lt: %s" % reason))
                normal_displacement = None
        if normal_displacement is None:
            displacement = unavailable("displacement",
                                       "displacement driving needs normal_displacement_lt")
            block = unavailable("block", "Cb cannot be back-solved without a displacement")
        else:
            displacement = normal_displacement
            capacity = None
            if None not in (length, beam_bulges, draught):
                capacity = length * beam_bulges * draught / TON
            if not capacity:
                block = unavailable("block",
                                    "Cb cannot be back-solved from the current hull geometry")
            else:
                block = displacement / capacity

    # ---- coSharp / length-beam / effective length / natural speed ----------
    if not length or not beam_bulges or block is None:
        co_sharp = unavailable("coSharp",
                               "coSharp needs a non-zero waterline length, bulged beam and Cb")
    else:
        cube = _pow(beam_bulges / length * 6.0, 1.0 / 3.0)
        root = _pow(block / 0.52, 0.5)
        if cube is None or root is None:
            co_sharp = unavailable("coSharp", "the source coSharp form is not real here")
        else:
            co_sharp = 0.4 * cube * root

    if not length or not beam_bulges:
        length_beam = unavailable("lengthBeam",
                                  "lengthBeam needs the waterline length and bulged beam")
    else:
        length_beam = length / beam_bulges

    length_effect = None
    if stern is None:
        length_effect = unavailable("lengthEffect", "lengthEffect needs the stern type")
    elif stern == 2:
        length_effect = (unavailable("lengthEffect", "lengthEffect needs coSharp")
                         if co_sharp is None else beam_bulges / co_sharp + length)
    elif stern == 1:
        length_effect = (unavailable("lengthEffect", "lengthEffect needs coSharp")
                         if co_sharp is None else beam_bulges * 0.5 / co_sharp + length)
    else:
        length_effect = length

    if length_effect is None:
        speed_natural = unavailable("speedNatural", "speedNatural needs the effective length")
    else:
        speed_natural = _pow(length_effect, 0.5)
        if speed_natural is None:
            speed_natural = unavailable("speedNatural", "the effective length is negative")

    # ---- waterplane coefficient and area ----------------------------------
    co_waterplane = None
    if block is None or stern is None or screws is None:
        co_waterplane = unavailable(
            "coWaterPlane",
            "the source waterplane coefficient needs Cb, the stern type and the shaft count")
    else:
        effective = max(block, 0.4)
        power = _pow(effective, -3.56)
        denominator = None if power is None else 1.006 - 0.0056 * power
        if not denominator:
            co_waterplane = unavailable("coWaterPlane",
                                        "the source waterplane ratio is not a real number")
        else:
            ratio = effective / denominator
            if stern == 2:
                coefficient = min(0.262 + 0.81 * ratio, 1.0)
            elif stern == 1:
                coefficient = min(0.262 + 0.79 * ratio, 1.0)
            elif screws < 2 or block >= 0.75:
                coefficient = min(0.175 + 0.875 * ratio, 1.0)
            else:
                coefficient = 0.262 + 0.76 * ratio
            if block < 0.4:
                correction = _pow(block - 0.3, 1.55)
                coefficient = None if correction is None else coefficient - (0.0281 - correction)
            if coefficient is None:
                co_waterplane = unavailable(
                    "coWaterPlane",
                    "the source correction term is NaN below Cb 0.3 (original domain)")
            else:
                co_waterplane = coefficient

    if co_waterplane is None or length is None or beam is None:
        waterplane_area = unavailable(
            "waterplaneArea",
            "waterplaneArea needs the waterplane coefficient, length and moulded beam")
    else:
        waterplane_area = co_waterplane * length * beam

    # ---- draught side, wetted surface, crew band --------------------------
    draught_side = None
    if block is None or draught is None:
        draught_side = unavailable("draughtSide", "draughtSide needs Cb and the draught")
    else:
        power = _pow(block, -3.56)
        if power is None:
            draught_side = unavailable("draughtSide",
                                       "the source draught form is not real here")
        else:
            draught_side = ((1.006 - 0.0056 * power) * 2.0 - 1.0) * draught

    if None in (length, draught, displacement):
        wetted_surface = unavailable(
            "wettedSurface", "wettedSurface needs the length, draught and displacement")
    elif draught == 0.0:
        wetted_surface = unavailable("wettedSurface",
                                     "the source wetted surface divides by the draught")
    else:
        wetted_surface = length * draught * 1.7 + displacement * TON / draught

    crew_max = None
    crew_min = None
    if displacement is None:
        crew_max = unavailable("crewMax", "the source crew rule needs the displacement")
    elif displacement < 0.0:
        crew_max = unavailable("crewMax",
                               "the source crew rule has no real power of a negative displacement")
    else:
        powered = _pow(displacement, 0.75)
        if powered is None:
            crew_max = unavailable("crewMax", "the source crew rule overflowed")
        else:
            crew_max = int(powered * 0.65)
            crew_min = int(crew_max * 0.7692)

    # ---- dates (MainForm.dateCalc / dateAdjCalc) --------------------------
    if hull_year is None:
        date_adj = unavailable("dateAdjFloat", "the date adjustment needs the hull year")
    elif 1850 <= hull_year <= 1890:
        date_adj = 1.0 - (1890 - hull_year) / _DATE_SPAN
    elif 1891 <= hull_year <= 1950:
        date_adj = 1.0
    else:
        date_adj = 0.0
        diags.append(_diag("date_out_of_range", "warning", "hull_year",
                           "hull_year %s is outside the source 1850..1950 table" % hull_year))

    # ---- freeboard geometry (FreeboardControl.freeboardCalc) --------------
    fc_length = None if percent_raw["freeboard_forecastle_length"] is None \
        else percent_raw["freeboard_forecastle_length"] / 100.0
    fd_length = None if percent_raw["freeboard_flat_deck_length"] is None \
        else percent_raw["freeboard_flat_deck_length"] / 100.0
    qd_length = None if percent_raw["freeboard_quarterdeck_length"] is None \
        else percent_raw["freeboard_quarterdeck_length"] / 100.0
    if None in (fc_length, fd_length, qd_length):
        ad_length = unavailable(
            "adLength", "adLength needs the forecastle/flat deck/quarterdeck percentages")
    else:
        ad_length = 1.0 - fc_length - fd_length - qd_length
        if ad_length < 0.0:
            diags.append(_diag("segments_over_length", "warning", "adLength",
                               "the three deck percentages exceed the hull length"))

    endpoint = dict(endpoint_param)
    from_depths = {}
    if depth_locked:
        for param, field in ENDPOINTS:
            depth, depth_ok = _depth_value(depths, field, diags)
            if not depth_ok:
                if endpoint.get(field) is not None:
                    diags.append(_diag("depth_snapshot_missing", "warning", "depths",
                                       "no saved depth for %s; keeping the page value" % field))
                continue
            if draught is None:
                endpoint[field] = unavailable(field, "the locked depth needs the draught")
                continue
            endpoint[field] = depth - draught
            from_depths[field] = True

    free_fc = _fore_mix(endpoint["freeFCFor"], endpoint["freeFCAft"], 0.4)
    free_fd = _fore_mix(endpoint["freeFDFor"], endpoint["freeFDAft"], 0.5)
    free_ad = _fore_mix(endpoint["freeADFor"], endpoint["freeADAft"], 0.5)
    free_qd = _fore_mix(endpoint["freeQDFor"], endpoint["freeQDAft"], 0.5)
    for field, value, needs in (("freeFC", free_fc, ("freeFCFor", "freeFCAft")),
                                ("freeFD", free_fd, ("freeFDFor", "freeFDAft")),
                                ("freeAD", free_ad, ("freeADFor", "freeADAft")),
                                ("freeQD", free_qd, ("freeQDFor", "freeQDAft"))):
        if value is None:
            diags.append(_diag("output_unavailable", "warning", field,
                               "%s needs %s and %s" % (field, needs[0], needs[1])))

    if None in (free_fc, fc_length, free_fd, fd_length, free_ad, ad_length,
                free_qd, qd_length):
        freeboard = unavailable("freeboard",
                                "the freeboard average needs all four segments and lengths")
    else:
        freeboard = (free_fc * fc_length + free_fd * fd_length
                     + free_ad * ad_length + free_qd * qd_length)
        if freeboard < 0.0:
            diags.append(_diag("negative_freeboard", "warning", "freeboard",
                               "the source average is negative here; kept as computed"))

    if None in (free_fd, free_ad, fd_length, ad_length):
        free_distributed = unavailable("freeDistributed",
                                       "freeDistributed needs the FD/AD segments and lengths")
    elif fd_length + ad_length == 0.0:
        free_distributed = unavailable("freeDistributed",
                                       "the FD and AD lengths add up to zero")
    else:
        free_distributed = (free_fd * fd_length + free_ad * ad_length) / (fd_length + ad_length)

    if freeboard is None:
        freeboard_cap = unavailable("freeboardCap", "freeboardCap needs the freeboard average")
    elif beam is None:
        freeboard_cap = freeboard
        diags.append(_diag("cap_beam_unknown", "warning", "freeboardCap",
                           "the beam is unknown; the source catch keeps the average"))
    elif beam == 0.0:
        freeboard_cap = unavailable("freeboardCap", "the source cap divides by a zero beam")
    elif freeboard > beam / 3.0:
        freeboard_cap = freeboard * freeboard / (beam / 3.0)
    elif submerged_casemate:
        freeboard_cap = freeboard - 6.0
        if freeboard_cap < 0.0:
            diags.append(_diag("negative_freeboard_cap", "warning", "freeboardCap",
                               "the submerged casemate branch gives a negative cap; kept as computed"))
    else:
        freeboard_cap = freeboard

    # ---- write-backs into the saved page ----------------------------------
    updates = {}
    if length_driver == "overall" and length is not None:
        updates["length_waterline"] = _from_ft(length, scale)
    if displacement_driver == "displacement" and block is not None:
        updates["block_coefficient_normal"] = block
    for param, field in ENDPOINTS:
        if from_depths.get(field) and endpoint.get(field) is not None:
            updates[param] = _from_ft(endpoint[field], scale)

    hull = {
        "length": length, "lengthOA": length_oa, "lengthStem": length_stem,
        "beam": beam, "beamBulges": beam_bulges, "draught": draught,
        "draughtSide": draught_side, "block": block, "displacement": displacement,
        "coSharp": co_sharp, "lengthEffect": length_effect, "lengthBeam": length_beam,
        "coWaterPlane": co_waterplane, "waterplaneArea": waterplane_area,
        "wettedSurface": wetted_surface, "speedNatural": speed_natural,
        "crewMin": crew_min, "crewMax": crew_max, "dateHull": hull_year,
        "dateEngine": engine_year, "dateAdjFloat": date_adj,
    }
    freeboard_readings = {field: endpoint[field] for field in ENDPOINT_FIELDS}
    freeboard_readings.update({
        "fcLength": fc_length, "fdLength": fd_length, "adLength": ad_length,
        "qdLength": qd_length, "freeFC": free_fc, "freeFD": free_fd,
        "freeAD": free_ad, "freeQD": free_qd, "freeboard": freeboard,
        "freeDistributed": free_distributed, "freeboardCap": freeboard_cap,
        "lengthBow": length_bow, "lengthRam": length_ram, "lengthStern": length_stern,
    })
    # every unavailable reading carries a diagnostic on its own field
    mentioned = {diag["field"] for diag in diags}
    for field, value in list(hull.items()) + list(freeboard_readings.items()):
        if value is None and field not in mentioned:
            diags.append(_diag("output_unavailable", "warning", field,
                               "%s is unavailable because its inputs are unknown or undefined"
                               % field))

    internals = {
        "scale": scale, "armour_scale": armour_scale,
        "length": length, "lengthOA": length_oa, "beam": beam,
        "beamBulges": beam_bulges, "draught": draught, "block": block,
        "displacement": displacement, "dateAdjFloat": date_adj,
        "endpoints": dict(endpoint), "endpoint_from_depths": from_depths,
        "fcLength": fc_length, "fdLength": fd_length, "adLength": ad_length,
        "qdLength": qd_length, "freeboard": freeboard,
        "lengthBow": length_bow, "lengthRam": length_ram, "lengthStern": length_stern,
        "length_driver": length_driver, "displacement_driver": displacement_driver,
        "bulkhead_beam_mode": bulkhead_beam_mode, "depth_locked": depth_locked,
        "depths": depths, "stern": stern, "bow": bow, "screws": screws,
    }
    return {"hull": hull, "freeboard": freeboard_readings,
            "parameter_updates": updates, "internals": internals,
            "diagnostics": diags}


def _page_scale(parameters: Mapping, name: str, diags: list):
    raw = parameters.get(name)
    if raw is None:
        diags.append(_diag("page_scale_unknown", "warning", name,
                           "%s is unknown; the page is read as feet" % name))
        return 0
    number, reason = _coerce_number(raw)
    if reason is not None or number not in (0.0, 1.0):
        diags.append(_diag("page_scale_invalid", "warning", name,
                           "%s must be 0 or 1; the page is read as feet" % name))
        return 0
    return int(number)


def _edit_choice(edit: Mapping, name: str, allowed, default, diags):
    value = edit.get(name)
    if value is None:
        return default
    if value in allowed:
        return value
    diags.append(_diag("invalid_editing", "warning", name,
                       "%s must be one of %s" % (name, ", ".join(allowed))))
    return default


def _extension_ft(length_bow, length_ram, length_stern, bow, length_stem):
    """The source's bow-extension ladder, or ``None`` where it cannot be chosen."""
    if length_ram is not None:
        if length_ram <= 0.0:
            branch = False
        else:
            branch = None if bow is None else bow > 1
    else:
        # a missing ram length still cannot pick branch 1 when the bow is normal/bulbous
        branch = None if bow is None or bow > 1 else False
    if branch is True:
        extension = None if length_stem is None else max(length_stem, length_ram)
    elif branch is None:
        extension = None
    elif length_bow is None:
        extension = None
    elif length_bow > 0.0:
        extension = length_stem
    else:
        extension = 0.0
    if extension is None:
        return None
    if length_stern is None:
        return None
    if length_stern > 0.0:
        extension = extension + length_stern
    return extension


def _depth_value(depths, field: str, diags: list):
    """(feet, True) when the snapshot holds a usable depth, else (None, False)."""
    if depths is None or depths.get(field) is None:
        return None, False
    number, reason = _coerce_number(depths[field])
    if reason is not None:
        diags.append(_diag("invalid_editing", "error", "depths",
                           "depths.%s: %s" % (field, reason)))
        return None, False
    return number, True


def _fore_mix(fore, aft, fore_weight: float):
    """FC is ``.6 aft + .4 fore``; the other segments are a plain average."""
    if fore is None or aft is None:
        return None
    if fore_weight == 0.4:
        return aft + (fore - aft) * 0.4
    return fore + (aft - fore) * 0.5


# ------------------------------------------------------------- public surface

def _status(diags, readings, fatal):
    if fatal:
        return "unavailable"
    if any(d["severity"] == "error" for d in diags):
        return "partial"
    if any(value is None for value in readings):
        return "partial"
    return "available"


def evaluate(parameters: dict, *, editing: dict | None = None,
             submerged_casemate: bool = False) -> dict:
    """One source pass. Never raises; never mutates ``parameters`` or ``editing``.

    Returns ``{method_version, status, hull, freeboard, parameters, editing,
    diagnostics, provenance}``: readings in the original internal units
    (ft / long ton / degree); ``parameters`` still on the saved page scale with
    every unconsumed key preserved verbatim; ``editing`` carrying the filled
    defaults plus every caller key.
    """
    params, params_reason = _copy_mapping(parameters)
    edit, edit_reason = _copy_editing(editing)
    fatal = params_reason is not None

    diags = []
    if params_reason is not None:
        diags.append(_diag("invalid_parameters", "error", "parameters", params_reason))
    if edit_reason is not None:
        diags.append(_diag("invalid_editing", "error", "editing", edit_reason))

    if fatal:
        solved = {"hull": {name: None for name in HULL_FIELDS},
                  "freeboard": {name: None for name in FREEBOARD_FIELDS},
                  "parameter_updates": {}, "internals": {}, "diagnostics": []}
    else:
        solved = _solve(params, edit, bool(submerged_casemate))
    diags.extend(solved["diagnostics"])

    out_parameters = copy.deepcopy(params)
    out_parameters.update(solved["parameter_updates"])
    out_editing = _editing_out(edit)

    readings = list(solved["hull"].values()) + list(solved["freeboard"].values())
    return {
        "method_version": METHOD_VERSION,
        "status": _status(diags, readings, fatal),
        "hull": solved["hull"],
        "freeboard": solved["freeboard"],
        "parameters": out_parameters,
        "editing": out_editing,
        "diagnostics": diags,
        "provenance": {
            "method_version": METHOD_VERSION,
            "source_sha256": SOURCE_SHA256,
            "sources": list(_SOURCE_NOTES),
            "units": "ft / long ton / degree (original internal units)",
            "page_scale": "parameters stay on the saved hull page scale (0=feet, 1=metres)",
            "submerged_casemate": bool(submerged_casemate),
        },
    }


def _editing_out(edit: Mapping) -> dict:
    out = copy.deepcopy(dict(edit))
    for name, default in EDITING_DEFAULTS.items():
        value = out.get(name)
        if name == "depth_locked":
            usable = isinstance(value, bool)
        else:
            allowed = {"length_driver": LENGTH_DRIVERS,
                       "displacement_driver": DISPLACEMENT_DRIVERS,
                       "bulkhead_beam_mode": BULKHEAD_BEAM_MODES}[name]
            usable = value in allowed
        if not usable:
            out[name] = default
    return out


# ---------------------------------------------------------------- edit surface

def apply_edit(parameters: dict, editing: dict, command: dict) -> dict:
    """Apply one upper-layer edit command. The inputs are never mutated.

    Commands: ``set_parameter``, ``set_scale``, ``set_length_driver``,
    ``set_displacement_driver``, ``set_depth_lock``, ``freeboard_preset``.
    Returns ``{parameters, editing, diagnostics}``; re-run :func:`evaluate`
    to read the resulting hull/freeboard values.
    """
    params, params_reason = _copy_mapping(parameters)
    edit, edit_reason = _copy_editing(editing)
    diags = []
    if params_reason is not None:
        diags.append(_diag("invalid_parameters", "error", "parameters", params_reason))
    if edit_reason is not None:
        diags.append(_diag("invalid_editing", "error", "editing", edit_reason))
    if params_reason is not None:
        return {"parameters": params, "editing": edit, "diagnostics": diags}
    if not isinstance(command, Mapping):
        diags.append(_diag("invalid_command", "error", "command", "command must be a mapping"))
        return {"parameters": params, "editing": edit, "diagnostics": diags}
    kind = command.get("kind")
    if not isinstance(kind, str):
        diags.append(_diag("invalid_command", "error", "kind", "command.kind must be a string"))
        return {"parameters": params, "editing": edit, "diagnostics": diags}

    internals = _solve(params, edit, False)["internals"]

    if kind == "set_parameter":
        _set_parameter(params, edit, command, internals, diags)
    elif kind == "set_scale":
        _set_scale(params, edit, command, internals, diags)
    elif kind == "set_length_driver":
        _set_length_driver(params, edit, command, internals, diags)
    elif kind == "set_displacement_driver":
        _set_displacement_driver(params, edit, command, internals, diags)
    elif kind == "set_depth_lock":
        _set_depth_lock(params, edit, command, internals, diags)
    elif kind == "freeboard_preset":
        _freeboard_preset(params, edit, command, internals, diags)
    else:
        diags.append(_diag("unknown_command", "error", "kind",
                           "unknown command kind %r" % (kind,)))
        return {"parameters": params, "editing": edit, "diagnostics": diags}

    # the source's own recalculations write the derived values back into the page
    params.update(_solve(params, edit, False)["parameter_updates"])
    return {"parameters": params, "editing": edit, "diagnostics": diags}


def _command_number(command, name, diags, kind="number"):
    value, ok = _numeric_state(command.get("value"), kind, name, diags)
    return value, ok


def _numeric_state(value, kind, name, diags):
    if kind == "enum":
        number, reason = _coerce_number(value)
        if reason is not None or abs(number - round(number)) > 1e-9 \
                or not -1 <= int(round(number)) <= 3:
            diags.append(_diag("invalid_command_value", "error", name,
                               "%s must be an index -1..3" % name))
            return None, False
        return int(round(number)), True
    number, reason = _coerce_number(value)
    if reason is not None:
        diags.append(_diag("invalid_command_value", "error", name, "%s: %s" % (name, reason)))
        return None, False
    return number, True


def _set_parameter(params, edit, command, internals, diags):
    name = command.get("name")
    if not isinstance(name, str):
        diags.append(_diag("invalid_command_value", "error", "name",
                           "command.name must be a string"))
        return
    scale = internals.get("scale", 0)
    armour_scale = internals.get("armour_scale", 0)

    # editing-side specials (the source has no saved field for either)
    if name == "length_overall":
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        edit["overall_length"] = value
        if edit.get("length_driver") != "overall":
            diags.append(_diag("inactive_driver", "warning", "length_overall",
                               "length_driver is not overall, so this value is stored but unused"))
        return
    if name == "normal_displacement_lt":
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        edit["normal_displacement_lt"] = value
        edit["displacement_driver"] = "displacement"
        return
    if name == "hull_scale":
        diags.append(_diag("unsupported_parameter", "error", name,
                           "page scale changes go through set_scale"))
        return
    if name == "armour_bulkhead_beam":
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        params[name] = value
        edit["bulkhead_beam_mode"] = "fixed"
        return
    if name == "block_coefficient_normal":
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        params[name] = value
        edit["displacement_driver"] = "block"
        return

    if name == "beam_moulded":
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        params[name] = value
        beam_ft = _to_ft(value, scale)
        # HullControl.beamEnter writes one text (unit chosen by the armour page combo)
        # into both boxes; each box is then re-read with its own page combo.
        text = _beam_coupling_text(beam_ft, armour_scale)
        params["beam_at_bulges"] = _from_ft(_page_text_read(text, scale), scale)
        if edit.get("bulkhead_beam_mode", "follow_hull") != "fixed":
            params["armour_bulkhead_beam"] = _from_ft(
                _page_text_read(text, armour_scale), armour_scale)
        if scale != armour_scale:
            diags.append(_diag(
                "source_quirk", "warning", "beam_at_bulges",
                "the source picks the coupled box text with the armour page unit "
                "(armour_scale=%d) but re-reads the bulges box with the hull page unit "
                "(hull_scale=%d); the mixed-unit value is reproduced verbatim, not corrected"
                % (armour_scale, scale)))
        return

    if name == "length_waterline":
        if edit.get("length_driver") == "overall":
            diags.append(_diag("inactive_field", "warning", name,
                               "the source disables the waterline box while the overall length drives"))
            return
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        params[name] = value
        return

    if name in ENDPOINT_PARAM:
        field = ENDPOINT_PARAM[name]
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        if edit.get("depth_locked") is True and field in DEPTH_PINNED_FIELDS:
            diags.append(_diag("depth_locked_endpoint", "warning", name,
                               "the source disables this box while the depth is locked"))
            return
        params[name] = value
        # The 8-point depth snapshot is written only by depthLockBtnClick's lock case.
        # A locked endpoint edit is overwritten by the depth-derived value the way the
        # original's subsequent draughtCalc does (see _solve's parameter write-backs);
        # the snapshot itself is left exactly as it was taken.
        return

    if name in ("beam_at_bulges", "draught_normal", "freeboard_ram_length",
                "freeboard_length_stern") or name in _PERCENT_PARAMETERS \
            or name in ("freeboard_length_bow", "hull_year", "engine_year", "shafts"):
        value, ok = _command_number(command, name, diags)
        if not ok:
            return
        params[name] = value
        return

    if name in ("stern", "bow"):
        value, ok = _command_number(command, name, diags, kind="enum")
        if not ok:
            return
        params[name] = value
        return

    diags.append(_diag("unsupported_parameter", "error", name,
                       "this unit does not consume %s; use the owning page" % name))


def _set_scale(params, edit, command, internals, diags):
    if command.get("page") != "hull":
        diags.append(_diag("unsupported_page", "error", "page",
                           "set_scale only owns the hull and freeboard page"))
        return
    value = command.get("value")
    if isinstance(value, bool) or value not in (0, 1):
        diags.append(_diag("invalid_command_value", "error", "value",
                           "page scale must be 0 (feet) or 1 (metres)"))
        return
    target = int(value)
    current = internals.get("scale")
    if current is None:
        diags.append(_diag("invalid_state", "error", "hull_scale",
                           "the current page scale cannot be read"))
        return
    if current == target:
        return
    for name in PAGE_LENGTH_PARAMETERS:
        raw = params.get(name)
        if raw is None:
            continue
        number, reason = _coerce_number(raw)
        if reason is not None:
            continue
        params[name] = _from_ft(_to_ft(number, current), target)
    overall = edit.get("overall_length")
    if overall is not None:
        number, reason = _coerce_number(overall)
        if reason is None:
            edit["overall_length"] = _from_ft(_to_ft(number, current), target)
    params["hull_scale"] = target


def _set_length_driver(params, edit, command, internals, diags):
    value = command.get("value")
    if value not in LENGTH_DRIVERS:
        diags.append(_diag("invalid_command_value", "error", "value",
                           "length driver must be waterline or overall"))
        return
    if edit.get("length_driver", "waterline") == value:
        return
    scale = internals.get("scale", 0)
    if value == "overall":
        length_oa = internals.get("lengthOA")
        if length_oa is None:
            diags.append(_diag("driver_unavailable", "error", "lengthOA",
                               "the current overall length is unavailable"))
            return
        edit["overall_length"] = _from_ft(length_oa, scale)
    else:
        length = internals.get("length")
        if length is None:
            diags.append(_diag("driver_unavailable", "error", "length",
                               "the current waterline length is unavailable"))
            return
        params["length_waterline"] = _from_ft(length, scale)
    edit["length_driver"] = value


def _set_displacement_driver(params, edit, command, internals, diags):
    value = command.get("value")
    if value not in DISPLACEMENT_DRIVERS:
        diags.append(_diag("invalid_command_value", "error", "value",
                           "displacement driver must be block or displacement"))
        return
    if edit.get("displacement_driver", "block") == value:
        return
    if value == "displacement":
        displacement = internals.get("displacement")
        if displacement is None:
            diags.append(_diag("driver_unavailable", "error", "displacement",
                               "the current displacement is unavailable"))
            return
        edit["normal_displacement_lt"] = displacement
    else:
        block = internals.get("block")
        if block is None:
            diags.append(_diag("driver_unavailable", "error", "block",
                               "the current Cb is unavailable"))
            return
        params["block_coefficient_normal"] = block
    edit["displacement_driver"] = value


def _set_depth_lock(params, edit, command, internals, diags):
    value = command.get("value")
    if not isinstance(value, bool):
        diags.append(_diag("invalid_command_value", "error", "value",
                           "depth lock value must be a boolean"))
        return
    if value:
        if not isinstance(edit.get("depths"), Mapping):
            edit["depths"] = _depth_snapshot(internals, diags)
        edit["depth_locked"] = True
    else:
        edit["depth_locked"] = False


def _depth_snapshot(internals, diags) -> dict:
    depths = {}
    draught = internals.get("draught")
    for field in ENDPOINT_FIELDS:
        endpoint = internals.get("endpoints", {}).get(field)
        if endpoint is None or draught is None:
            diags.append(_diag("depth_snapshot_incomplete", "warning", "depths",
                               "no depth can be taken for %s" % field))
            depths[field] = None
        else:
            depths[field] = endpoint + draught
    return depths


def _freeboard_preset(params, edit, command, internals, diags):
    value = command.get("value")
    if value not in ("flush", "raised"):
        diags.append(_diag("invalid_command_value", "error", "value",
                           "the freeboard preset must be flush or raised"))
        return
    endpoint = _preset_endpoints(value, internals, diags)
    if endpoint is None:
        return
    scale = internals["scale"]
    for field, ft_value in endpoint.items():
        params[ENDPOINT_PARAM_NAME[field]] = _from_ft(ft_value, scale)
    # The buttons only write boxes. While the depth is locked the follow-up
    # draughtCalc derives every endpoint from the snapshot, so the preset is
    # overridden and the snapshot (written only at lock time) is left alone.
    if edit.get("depth_locked") is True:
        diags.append(_diag("depth_locked_preset", "warning", "freeboard_preset",
                           "the depth snapshot wins while locked; the preset endpoints are "
                           "overwritten by their depth-derived values"))


def _preset_endpoints(value: str, internals, diags):
    """``btnFlushClick`` / ``btnBreakClick``, incl. the source's n2 text round-trip."""
    length = internals.get("length")
    date_adj = internals.get("dateAdjFloat")
    if length is None or length < 0.0 or date_adj is None:
        diags.append(_diag("preset_unavailable", "error", "freeboard_preset",
                           "the preset estimate needs the hull length and the date adjustment"))
        return None
    scale = internals.get("scale", 0)
    estimate_bow = (1.1 - (1.0 - date_adj) * 0.5) * math.sqrt(length)
    estimate_other = (0.7 if value == "flush" else 0.9) * math.sqrt(length)
    bow = _preset_box_ft(estimate_bow, scale)
    other = _preset_box_ft(estimate_other, scale)
    if value == "flush":
        middle = _preset_box_ft((estimate_bow + estimate_other) / 2.0, scale)
        return {"freeFCFor": bow, "freeFCAft": middle, "freeFDFor": middle,
                "freeFDAft": other, "freeADFor": other, "freeADAft": other,
                "freeQDFor": other, "freeQDAft": other}
    half = _preset_box_ft(estimate_other / 2.0, scale)
    return {"freeFCFor": bow, "freeFCAft": other, "freeFDFor": other,
            "freeFDAft": other, "freeADFor": half, "freeADAft": half,
            "freeQDFor": half, "freeQDAft": half}
