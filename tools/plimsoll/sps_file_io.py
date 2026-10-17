"""Pure SpringSharp 3b3 ``.sship`` serializer and reader.

This module is the file-format half of the SpringSharp 3b3 parity work. It turns
the saved byte stream into a *design* mapping and back, and it does nothing else:
no project schema, no UI, no CLI and no filesystem access. Every function is pure
and takes the caller's bytes or mapping without mutating what it was given.

Public contract
---------------
``loads(data)``
    ``bytes`` -> ``design`` (``read(data)["design"]``).
``read(data)``
    ``bytes`` -> ``{design, source, diagnostics, raw_records}``. ``source`` is
    ``{sha256, encoding, version}``; ``raw_records`` is the positional record
    block exactly as saved (280 records for 3.0, 136 for 2.0).
``dumps(design, *, decimal_separator='.', padding=None)``
    ``design`` -> ``bytes``; the original 3.0 header, 280 record lines and the
    note tail, UTF-8 with no byte-order mark.
``from_migration(migration)``
    Re-read a ``sship_import`` migration archive from its immutable
    ``original_base64`` copy without touching the archive.
``default_design()``
    A fresh-window 3b3 design carrying declarative product defaults.
``to_project(design, *, name=None)``
    Deliberately unimplemented here; project integration belongs to the parent
    unit.

Design shape
------------
``{"schema": "plimsoll-sps3b3-design-1", "source": str, "parameters": {...},
   "editing": {}, "notes": str}``.

``parameters`` holds the 247 recovered registry positions ``0..246`` keyed by
their :mod:`sship_fields` names; the 33 writer padding positions ``247..279`` are
never parameters. Values are typed by the registry: text stays text (a blank
record is ``""``), numbers are ``float`` (a blank record is ``None``), integers
and selections are ``int``, and checkbox states are ``bool`` (a blank record is
``None``). An unknown effective number prevents export: the source reuses a
previous numeric parse for an empty line, so a blank cannot represent unknown.

Version support
---------------
* **3.0** -- both the dot and comma headers. This is the only format the shipped
  binary still writes.
* **2.0** -- the legacy 136-record layout, read through declarative,
  evidence-backed mapping of the reader's conditional branches. Positions the
  2.0 reader never restored keep the fresh-window default. The reader never
  recognises a ``2,0`` header, so none is written.
* **SpringStyle 1.0 / 1.1** -- recognised by the original and refused with the
  program's own "no longer supported" notice; this module refuses them the same
  way instead of guessing a mapping.
* **anything else** -- refused as an unknown header.

Units and fidelity notes
------------------------
* Numeric values are the saved text parsed under the file's own decimal
  convention; no unit conversion is attempted anywhere, so independent page
  scales (hull, gun, armour, weapon) survive a round trip verbatim.
* The 25 duplicated mount-count records (positions 34/35/154/164/169 and their
  banks) are written from the authoritative later block (211/216/221/226/231),
  exactly as the 3.0 reader's last-assignment-wins behaviour implies.
* The 33 padding records default to the value the original writer repeated there
  (gun 5's group-1 barrels-per-mount), which is ``0`` for a fresh window; a
  caller may override them with an explicit list of exactly 33 records.
* The only known formatting difference from a fresh native save is the block
  coefficient: the source stores ``0.550``, this module stores ``0.55``.
* Line ends are written as CRLF (the shipped Windows writer used
  ``Environment.NewLine``) and the note tail is appended with no added newline.

Nothing here embeds or reinterprets recovered program code; the tables it relies
on are the declarative position registry and the declarative new-design default
record block.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
import struct
from decimal import Decimal, ROUND_HALF_UP

try:  # pragma: no cover - package import vs direct-module convention
    from . import sship_fields, sship_import
except ImportError:  # pragma: no cover
    import sship_fields
    import sship_import


__all__ = [
    "FileIOError",
    "SCHEMA",
    "loads",
    "read",
    "dumps",
    "from_migration",
    "default_design",
    "to_project",
]


SCHEMA = "plimsoll-sps3b3-design-1"

HEADER_DOT = sship_fields.SUPPORTED_DECIMAL_HEADER
HEADER_COMMA = sship_fields.SUPPORTED_COMMA_HEADER
HEADER_LEGACY = "SpringSharp Version 2.0"
SPRINGSTYLE_1X = ("SpringStyle Version 1.0", "SpringStyle Version 1.1")

DEFAULT_SOURCE = "SpringSharp3b3 new-design defaults"

FIELD_COUNT = sship_fields.FIELD_COUNT
PARAMETER_COUNT = sship_fields.PADDING_FIRST
PADDING_COUNT = FIELD_COUNT - PARAMETER_COUNT
LEGACY_FIELD_COUNT = 136

# The reader's conditional 2.0 branches and the writer's terminator.
_LEGACY_SEPARATOR_INDEX = 21
_LINE = "\r\n"
_SEPARATORS = (".", ",")
_SPACES = " \u00a0\u202f"
_MODERN_HEADERS = {HEADER_DOT: ".", HEADER_COMMA: ","}

# Recovered combo-box ranges for every ENUM position; a selection outside its
# range cannot be assigned to the shipped control and is refused here.
_ENUM_BOUNDS = {
    16: (-1, 3),                                        # stern type
    33: (0, 6), 39: (0, 6), 45: (0, 6), 51: (0, 6), 57: (0, 6),   # gun type
    63: (0, 6), 66: (0, 6), 69: (0, 6), 72: (0, 6), 75: (0, 6),   # mount type
    64: (0, 18), 67: (0, 18), 70: (0, 18), 73: (0, 18), 76: (0, 18),  # layout g1
    134: (-1, 3),                                       # bow type
    149: (0, 18), 150: (0, 18), 151: (0, 18), 152: (0, 18), 153: (0, 18),  # layout g2
    184: (0, 8), 185: (0, 8),                           # torpedo location
    189: (0, 3),                                        # mine location
    196: (0, 3), 197: (0, 3),                           # deck-gun location
    205: (0, 1),                                        # bulkhead type
    209: (0, 6),                                        # deck coverage
    **{index: (0, 14) for index in range(236, 246)},    # barrels per mount
}
_ENUM_DEFAULT_BOUNDS = (0, None)

# Position the shipped 3.0 writer repeated 33 times: gun 5, group 1.
_PADDING_VALUE_INDEX = sship_fields.BARRELS_PER_MOUNT_G1 + sship_fields.BANK_COUNT - 1

# Early (ignored) record -> authoritative later record, one entry per bank.
_SHADOW_TO_AUTHORITY = {}
for _bank in range(sship_fields.BANK_COUNT):
    _SHADOW_TO_AUTHORITY[sship_fields.SUPER_MOUNTS_G1_EARLY[_bank]] = \
        sship_fields.SUPER_MOUNTS_G1 + _bank
    _SHADOW_TO_AUTHORITY[sship_fields.SUB_MOUNTS_G1_EARLY[_bank]] = \
        sship_fields.SUB_MOUNTS_G1 + _bank
    _SHADOW_TO_AUTHORITY[sship_fields.SUPER_MOUNTS_G2_EARLY[_bank]] = \
        sship_fields.SUPER_MOUNTS_G2 + _bank
    _SHADOW_TO_AUTHORITY[sship_fields.DECK_MOUNTS_G2_EARLY[_bank]] = \
        sship_fields.DECK_MOUNTS_G2 + _bank
    _SHADOW_TO_AUTHORITY[sship_fields.SUB_MOUNTS_G2_EARLY[_bank]] = \
        sship_fields.SUB_MOUNTS_G2 + _bank
del _bank
assert len(_SHADOW_TO_AUTHORITY) == len(sship_fields.SHADOWED) == 25

_PARAMETER_NAMES = sship_fields.NAMES[:PARAMETER_COUNT]
_PADDING_NAMES = frozenset(sship_fields.NAMES[PARAMETER_COUNT:])
_PARAMETER_NAME_SET = frozenset(_PARAMETER_NAMES)


# Declarative values saved by an untouched original 3b3 window.
DEFAULT_RECORDS = (
    "Enter ship name",
    "Enter country",
    "Enter ship type",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "1950",
    "0",
    "0",
    "0",
    "0",
    "-1",
    "0.550",
    "0",
    "0",
    "15",
    "0",
    "0",
    "30",
    "0",
    "0",
    "20",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "1",
    "0",
    "0",
    "0",
    "0",
    "0",
    "1",
    "0",
    "0",
    "0",
    "0",
    "0",
    "1",
    "0",
    "0",
    "0",
    "0",
    "0",
    "1",
    "0",
    "0",
    "0",
    "0",
    "0",
    "1",
    "0",
    "0",
    "0",
    "150",
    "0",
    "5",
    "18",
    "0",
    "5",
    "18",
    "0",
    "5",
    "18",
    "0",
    "5",
    "18",
    "0",
    "5",
    "18",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "False",
    "50",
    "0",
    "1950",
    "1950",
    "1950",
    "1950",
    "1950",
    "1950",
    "-1",
    "0",
    "0",
    "0",
    "0",
    "0",
    "45",
    "45",
    "45",
    "45",
    "45",
    "150",
    "150",
    "150",
    "150",
    "18",
    "18",
    "18",
    "18",
    "18",
    "0",
    "0",
    "0",
    "0",
    "0",
    "False",
    "False",
    "False",
    "False",
    "False",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "False",
    "False",
    "False",
    "False",
    "False",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
    "0",
)


class FileIOError(ValueError):
    """Report one or more structured SpringSharp file I/O failures.

    Every failure is a diagnostic mapping with ``code``, ``severity``, ``path``,
    ``message`` and ``blocking`` keys, mirroring :class:`sship_import.SshipImportError`.
    """

    def __init__(self, diagnostics):
        self.diagnostics = [dict(item) for item in diagnostics]
        detail = "; ".join(
            f"{item.get('path', '$')}: {item.get('message', 'invalid input')}"
            for item in self.diagnostics[:3]
        )
        super().__init__(detail or "SpringSharp file I/O failed")


def _error(code, path, message, *, line=None, index=None):
    return sship_import._diagnostic(code, path, message, severity="error",
                                     line=line, index=index)


def _info(code, path, message):
    return sship_import._diagnostic(code, path, message, severity="info")


class _Collector:
    """Accumulate write-time errors so one call reports every problem."""

    def __init__(self):
        self.errors = []

    def error(self, code, path, message):
        self.errors.append(_error(code, path, message))

    def raise_if_any(self):
        if self.errors:
            raise FileIOError(self.errors)


# ------------------------------------------------------------------ typing ---

def _type_default(index):
    """Type one position from :data:`DEFAULT_RECORDS` under the registry rules."""
    kind = sship_fields.kind_of(index)
    record = DEFAULT_RECORDS[index]
    if kind == sship_fields.TEXT:
        return "" if record.strip() == "" else record
    value = sship_import._parse_field(index, record, ".", [])
    if kind == sship_fields.BOOLEAN:
        return value
    return value


def _default_parameters():
    """A fresh dictionary of the 247 typed fresh-window default parameters."""
    return {name: _type_default(index)
            for index, name in enumerate(_PARAMETER_NAMES)}


# ------------------------------------------------------------------ reading ---

def _decode(data):
    try:
        return sship_import._decode(data)
    except sship_import.SshipImportError as error:
        raise FileIOError(error.diagnostics) from error


def _check_line(index, record):
    if len(record) > sship_import.MAX_LINE_CHARS:
        raise FileIOError([_error(
            "sship.field.too_long", f"$.fields[{index}]",
            f"the record is {len(record)} characters; the supported maximum is "
            f"{sship_import.MAX_LINE_CHARS}", line=index + 2, index=index)])


def _value_at(index, record, separator, diagnostics):
    """One position's value under the recovered registry typing."""
    kind = sship_fields.kind_of(index)
    value = sship_import._parse_field(index, record, separator, diagnostics)
    if kind == sship_fields.TEXT:
        return "" if value is None else value
    if value is None:
        if kind in (sship_fields.ENUM, sship_fields.SELECTOR):
            diagnostics.append(_error(
                "sship.field.blank", f"$.fields[{index}]",
                "a saved selection cannot be blank", line=index + 2, index=index))
        return None
    if kind == sship_fields.ENUM:
        low, high = _ENUM_BOUNDS.get(index, _ENUM_DEFAULT_BOUNDS)
        if value < low or (high is not None and value > high):
            diagnostics.append(_error(
                "sship.field.out_of_range", f"$.fields[{index}]",
                f"the saved selection {value} is outside the recovered range "
                f"[{low}, {high}]", line=index + 2, index=index))
            return None
    return value


def _raise_errors(diagnostics):
    errors = [item for item in diagnostics if item.get("severity") == "error"]
    if errors:
        raise FileIOError(errors)


def _modern_parameters(records, separator, diagnostics):
    values = []
    for index in range(FIELD_COUNT):
        record = records[index]
        _check_line(index, record)
        values.append(_value_at(index, record, separator, diagnostics))
    return {name: values[index] for index, name in enumerate(_PARAMETER_NAMES)}


def _subtract(minuend, subtrahend):
    """Numeric difference, or ``None`` when either side is blank."""
    numeric = (int, float)
    if isinstance(minuend, bool) or isinstance(subtrahend, bool):
        return None
    if isinstance(minuend, numeric) and isinstance(subtrahend, numeric):
        return minuend - subtrahend
    return None


def _legacy_parameters(records, separator, diagnostics):
    """Map the 136-record 2.0 block onto the 3.0 design parameters.

    The branches below are the reader's own conditional 2.0 behaviour: positions
    it never restored keep the fresh-window default, and the handful of derived
    controls are recomputed exactly as the reader recomputed them.
    """
    values = []
    for index in range(LEGACY_FIELD_COUNT):
        record = records[index]
        _check_line(index, record)
        if index == 16:
            # The 2.0 stern position is a checkbox string, not a stern index.
            values.append(record.startswith("True"))
            continue
        values.append(_value_at(index, record, separator, diagnostics))

    parameters = _default_parameters()
    for index in range(134):  # the 2.0 reader stops before bow / ram
        if index == 16:
            parameters[sship_fields.NAMES[16]] = 1 if values[16] else 0
            continue
        if index == 23:
            derived = _subtract(values[23], values[26])
            if derived is not None:
                parameters[sship_fields.NAMES[23]] = derived
            continue
        parameters[sship_fields.NAMES[index]] = values[index]

    for offset in range(4):  # 2.0 reuses the torpedo-1 scale four times
        parameters[sship_fields.NAMES[136 + offset]] = values[9]

    for bank in range(sship_fields.BANK_COUNT):
        group1 = sship_fields.LAYOUT_G1_BASE + 3 * bank
        parameters[sship_fields.NAMES[sship_fields.LAYOUT_G2_BASE + bank]] = \
            values[group1]

    parameters[sship_fields.NAMES[181]] = values[79]

    # ClearMenu resets these controls before any legacy assignment. A pristine
    # window's unselected (-1) designer state is not the file-open reset state.
    parameters['bow'] = 0
    beam = values[14]
    if beam is not None:
        try:
            single = lambda number: struct.unpack('f', struct.pack('f', number))[0]
            beam = single(beam)
            if values[3] == 1:
                beam = single(beam / single(0.3048))
            bulkhead_beam = single(beam - 20.0)
            if not math.isfinite(bulkhead_beam):
                raise OverflowError('beam is outside source Single range')
            parameters[sship_fields.NAMES[206]] = float(
                Decimal(bulkhead_beam).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        except (OverflowError, ArithmeticError, struct.error) as error:
            diagnostics.append(_error('sps.legacy.dimension_overflow','$.fields[14]',str(error)))

    for bank in range(sship_fields.BANK_COUNT):
        parameters[sship_fields.NAMES[sship_fields.SUPER_MOUNTS_G1 + bank]] = \
            values[sship_fields.SUPER_MOUNTS_G1_EARLY[bank]]
        parameters[sship_fields.NAMES[sship_fields.SUB_MOUNTS_G1 + bank]] = \
            values[sship_fields.SUB_MOUNTS_G1_EARLY[bank]]

    diagnostics.extend([
        _info("sps.legacy.version_2_0", "$.source",
              "SpringSharp 2.0 layout: only 136 records exist, so every position "
              "the 2.0 reader never restored keeps the fresh-window default."),
        _info("sps.legacy.fd_length", "$.fields[23]",
              "2.0 stores no flat-deck length; it is recomputed as record[23] minus "
              "record[26] and can differ from a native save in the last digits."),
        _info("sps.legacy.stern_boolean", "$.fields[16]",
              "the 2.0 stern position is a checkbox; it maps to the small-transom "
              "stern index 1 when true and to the file-open reset index 0 otherwise."),
        _info("sps.legacy.scales_reused", "$.fields[136]",
              "2.0 has one weapon scale; the torpedo-2, mine and both depth-charge "
              "scales copy the torpedo-1 scale at position 9."),
        _info("sps.legacy.layout_g2", "$.fields[149]",
              "2.0 has a single layout selector; the group-2 selector copies the "
              "group-1 value."),
        _info("sps.legacy.torpedo2_size", "$.fields[181]",
              "2.0 stores one torpedo size; torpedo 2 copies torpedo 1."),
        _info("sps.legacy.bulkhead_beam", "$.fields[206]",
              "2.0 writes (internal moulded beam in feet minus 20).ToString(n2) "
              "into the armour page, which then reads that text in its own units."),
        _info("sps.legacy.per_mount_defaults", "$.fields[236]",
              "2.0 stores no barrels-per-mount selector; those positions keep the "
              "fresh-window default 0."),
    ])
    return parameters


def read(data):
    """Read SpringSharp bytes and return the design plus its source provenance.

    Args:
        data (bytes): The original file content, exactly as selected.

    Returns:
        (dict): ``design``, ``source`` (``sha256``, ``encoding``, ``version``),
            ``diagnostics`` and ``raw_records``.

    Raises:
        FileIOError: If the content, header, record count or a populated field
            cannot be read. The error carries structured diagnostics.
    """
    text, encoding = _decode(data)
    digest = hashlib.sha256(bytes(data)).hexdigest()
    header_records, rest = sship_import._split_records(text, 1)
    header = header_records[0]
    diagnostics = []

    if header in _MODERN_HEADERS:
        separator = _MODERN_HEADERS[header]
        records, notes = sship_import._split_records(rest, FIELD_COUNT)
        if len(records) < FIELD_COUNT:
            raise FileIOError([_error(
                "sship.fields.truncated", "$.data",
                f"the file holds {len(records)} of {FIELD_COUNT} parameter records")])
        parameters = _modern_parameters(records, separator, diagnostics)
        version = "3.0"
    elif header == HEADER_LEGACY:
        separator = header[_LEGACY_SEPARATOR_INDEX]
        if separator not in _SEPARATORS:
            separator = "."
        records, notes = sship_import._split_records(rest, LEGACY_FIELD_COUNT)
        if len(records) < LEGACY_FIELD_COUNT:
            raise FileIOError([_error(
                "sship.fields.truncated", "$.data",
                f"the file holds {len(records)} of {LEGACY_FIELD_COUNT} legacy "
                f"records")])
        parameters = _legacy_parameters(records, separator, diagnostics)
        version = "2.0"
    elif header in SPRINGSTYLE_1X:
        raise FileIOError([_error(
            "sship.version_unsupported", "$.header",
            "Sorry, This file format is no longer supported - there are too many "
            "differences; it will be quicker to recreate the ship from scratch")])
    else:
        raise FileIOError([_error(
            "sship.version_unknown", "$.header",
            f"{header!r} is not a recognised SpringSharp header; expected a 3.0 or "
            f"2.0 header")])

    _raise_errors(diagnostics)
    design = {
        "schema": SCHEMA,
        "source": f"{header}; sha256 {digest}",
        "parameters": parameters,
        "editing": {},
        "notes": notes,
    }
    return {
        "design": design,
        "source": {"sha256": digest, "encoding": encoding, "version": version},
        "diagnostics": diagnostics,
        "raw_records": list(records),
    }


def loads(data):
    """Read bytes and return just the design mapping (``read(data)["design"]``)."""
    return read(data)["design"]


# ------------------------------------------------------------------ writing ---

def _format_number(value, path, collector, separator):
    if value is None:
        return ""
    if isinstance(value, bool):
        collector.error("sps.parameter.number_invalid", path,
                        "a number field cannot carry a checkbox state")
        return ""
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            collector.error("sps.parameter.number_invalid", path,
                            "the number is not finite")
            return ""
        text = str(int(value)) if value.is_integer() else repr(value)
    else:
        collector.error("sps.parameter.number_invalid", path,
                        f"{value!r} is not a number")
        return ""
    if separator == ",":
        text = text.replace(".", ",")
    return text


def _format_selection(index, value, path, collector):
    kind = sship_fields.kind_of(index)
    if value is None:
        collector.error("sps.parameter.selection_missing", path,
                        "a saved selection cannot be blank")
        return ""
    if isinstance(value, bool):
        collector.error("sps.parameter.selection_invalid", path,
                        f"{value!r} is not a whole-number selection")
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        collector.error("sps.parameter.selection_invalid", path,
                        f"{value!r} is not a whole-number selection")
        return ""
    if kind == sship_fields.SELECTOR:
        low, high = 0, 1
    else:
        low, high = _ENUM_BOUNDS.get(index, _ENUM_DEFAULT_BOUNDS)
    if value < low or (high is not None and value > high):
        collector.error("sps.parameter.selection_out_of_range", path,
                        f"the selection {value} is outside the recovered range "
                        f"[{low}, {high}]")
        return ""
    return str(value)


def _format_field(index, name, value, collector, separator):
    kind = sship_fields.kind_of(index)
    path = f"$.design.parameters[{name!r}]"
    if kind == sship_fields.TEXT:
        if not isinstance(value, str):
            collector.error("sps.parameter.text_invalid", path,
                            f"{value!r} is not text")
            return ""
        if "\r" in value or "\n" in value:
            collector.error("sps.parameter.multiline", path,
                            "a single-line text field cannot contain a carriage "
                            "return or line feed")
            return ""
        return value
    if kind == sship_fields.BOOLEAN:
        if value is None:
            return ""
        if value is True:
            return "True"
        if value is False:
            return "False"
        collector.error("sps.parameter.boolean_invalid", path,
                        f"{value!r} is not a checkbox state")
        return ""
    if kind in (sship_fields.ENUM, sship_fields.SELECTOR):
        return _format_selection(index, value, path, collector)
    return _format_number(value, path, collector, separator)


def _format_padding_value(value, separator, collector, path):
    if value is None:
        return "0"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, str):
        if "\r" in value or "\n" in value:
            collector.error("sps.padding_invalid", path,
                            "a padding record cannot contain a line break")
            return "0"
        return value.replace(".", ",") if separator == "," else value
    return _format_number(value, path, collector, separator)


def _validate_padding(padding):
    """Return the padding entries as a list, or raise on a malformed argument."""
    if padding is None:
        return None
    if isinstance(padding, (str, bytes, bytearray)) or not isinstance(padding, (list, tuple)):
        raise FileIOError([_error(
            "sps.padding_invalid", "$.padding",
            "padding must be a sequence of exactly 33 records")])
    if len(padding) != PADDING_COUNT:
        raise FileIOError([_error(
            "sps.padding_length", "$.padding",
            f"padding must hold exactly {PADDING_COUNT} records; got "
            f"{len(padding)}")])
    return list(padding)


def dumps(design, *, decimal_separator=".", padding=None):
    """Serialize a design to SpringSharp 3.0 bytes.

    Args:
        design (dict): A ``plimsoll-sps3b3-design-1`` mapping.
        decimal_separator (str): ``"."`` (default) or ``","``; the header and
            every number follow it.
        padding (list, optional): Exactly 33 records for the writer padding
            block; defaults to the value the original repeated there.

    Returns:
        (bytes): UTF-8 without a byte-order mark.

    Raises:
        FileIOError: If the design, a value or the padding cannot be written.
            The error carries structured diagnostics.
    """
    if decimal_separator not in _SEPARATORS:
        raise FileIOError([_error(
            "sps.decimal_separator_invalid", "$.decimal_separator",
            f"the decimal separator must be '.' or ','; got {decimal_separator!r}")])
    if not isinstance(design, dict):
        raise FileIOError([_error("sps.design_invalid", "$.design",
                                  "the design must be a mapping")])
    if design.get("schema") != SCHEMA:
        raise FileIOError([_error(
            "sps.design_schema", "$.design.schema",
            f"the design schema must be {SCHEMA!r}")])
    parameters = design.get("parameters")
    if not isinstance(parameters, dict):
        raise FileIOError([_error(
            "sps.design_parameters", "$.design.parameters",
            "the design must carry a parameters mapping")])
    notes = design.get("notes", "")
    if notes is None:
        notes = ""
    if not isinstance(notes, str):
        raise FileIOError([_error("sps.design_notes", "$.design.notes",
                                  "notes must be text")])

    given = set(parameters)
    errors = []
    for key in sorted(map(str, given - _PARAMETER_NAME_SET)):
        if key in _PADDING_NAMES:
            errors.append(_error(
                "sps.parameter.padding", f"$.design.parameters[{key!r}]",
                "writer padding is not an editable parameter; pass it through the "
                "padding argument"))
        else:
            errors.append(_error(
                "sps.parameter.unknown", f"$.design.parameters[{key!r}]",
                "the parameter name is not part of the recovered registry"))
    for key in sorted(map(str, _PARAMETER_NAME_SET - given)):
        errors.append(_error(
            "sps.parameter.missing", f"$.design.parameters[{key!r}]",
            "the parameter is required for a complete write"))
    for index,name in enumerate(_PARAMETER_NAMES):
        if index not in sship_fields.SHADOWED and parameters.get(name) is None and sship_fields.KINDS[index]!=sship_fields.TEXT:
            errors.append(_error('sps.parameter.unknown', '$.design.parameters.'+name,
                'Original SpringSharp cannot represent an unknown numeric or selection value; fill this input before .sship export'))
    if errors:
        raise FileIOError(errors)

    padding_entries = _validate_padding(padding)

    collector = _Collector()
    records = []
    for index in range(PARAMETER_COUNT):
        source_index = _SHADOW_TO_AUTHORITY.get(index, index)
        name = sship_fields.name_of(source_index)
        records.append(_format_field(source_index, name, parameters[name],
                                     collector, decimal_separator))
    if padding_entries is None:
        value = parameters[sship_fields.name_of(_PADDING_VALUE_INDEX)]
        text = _format_padding_value(
            value, decimal_separator, collector,
            f"$.design.parameters[{sship_fields.name_of(_PADDING_VALUE_INDEX)!r}]")
        records.extend([text] * PADDING_COUNT)
    else:
        records.extend(
            _format_padding_value(item, decimal_separator, collector,
                                  f"$.padding[{offset}]")
            for offset, item in enumerate(padding_entries))
    collector.raise_if_any()

    header = "SpringSharp Version 3" + decimal_separator + "0"
    text = _LINE.join([header] + records) + _LINE + notes
    return text.encode("utf-8")


# --------------------------------------------------------- migration / project ---

def from_migration(migration):
    """Re-read a ``sship_import`` migration archive from its original bytes.

    Args:
        migration (dict): Either the migration mapping itself or a wrapper with a
            ``migration`` key holding it.

    Returns:
        (dict): The design read from ``original_base64``; the archive is never
            mutated.

    Raises:
        FileIOError: If the archive or its original bytes cannot be read.
    """
    archive = migration
    if isinstance(migration, dict) and "original_base64" not in migration \
            and isinstance(migration.get("migration"), dict):
        archive = migration["migration"]
    if not isinstance(archive, dict):
        raise FileIOError([_error("sps.migration_invalid", "$.migration",
                                  "the migration archive must be a mapping")])
    encoded = archive.get("original_base64")
    if not isinstance(encoded, str) or not encoded:
        raise FileIOError([_error(
            "sps.migration_base64_missing", "$.migration.original_base64",
            "the migration archive carries no original_base64 payload")])
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise FileIOError([_error(
            "sps.migration_base64_invalid", "$.migration.original_base64",
            f"the original_base64 payload is not valid base64: {error}")]) from error
    return loads(data)


def default_design():
    """Return a fresh-window 3b3 design with its declarative product defaults."""
    return {
        "schema": SCHEMA,
        "source": DEFAULT_SOURCE,
        "parameters": _default_parameters(),
        "editing": {},
        "notes": "",
    }


def to_project(design, *, name=None):
    """Not implemented here; canonical project assembly belongs to the parent unit.

    Raises:
        NotImplementedError: Always. This module stays a pure file codec.
    """
    raise NotImplementedError(
        "project integration is provided by the parent Plimsoll unit; "
        "sps_file_io only reads and writes SpringSharp bytes")
