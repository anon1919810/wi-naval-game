"""Bounded, passive reader for SpringSharp 3.0 ``.sship`` / ``.dat`` files.

``preview`` is the whole public contract. It takes the original bytes, decodes
them strictly, splits exactly 280 positional records, and returns a mapping
report plus an editable canonical draft. It performs no I/O, executes nothing,
changes no locale and mutates nothing it was given.

Every rejection is a structured diagnostic on :class:`SshipImportError`; every
survivable problem is a non-blocking warning inside the preview, so a caller
sees what could not be interpreted before deciding to create a project.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import math
import os
import re

try:
    from . import project_io, sship_fields, sship_mapping
except ImportError:  # pragma: no cover - direct-module import convention
    import project_io
    import sship_fields
    import sship_mapping


SCHEMA = "plimsoll-sship-preview-1"
METHOD_VERSION = "springsharp-3.0-migration-1"
MIGRATION_SCHEMA = "plimsoll-sship-migration-1"

# Bounds checked before any expensive parsing.
MAX_BYTES = 1 << 20
MAX_LINE_CHARS = 4096
MAX_TOKEN_CHARS = 128

SUPPORTED_HEADERS = {
    sship_fields.SUPPORTED_DECIMAL_HEADER: ".",
    sship_fields.SUPPORTED_COMMA_HEADER: ",",
}
_KNOWN_OTHER_VERSIONS = {
    "SpringSharp Version 2.0": "2.0",
    "SpringSharp Version 1.0": "1.0",
    "SpringStyle Version 1.0": "1.0",
    "SpringStyle Version 1.1": "1.1",
}

_RECORD_SEPARATOR = re.compile(r"\r\n|\r|\n")
_EXPONENT = re.compile(r"[eE]")
_INTEGER = re.compile(r"[0-9]+")
_EXPONENT_TAIL = re.compile(r"[eE][+-]?[0-9]+")
_GROUP_SPACES = " \u00a0\u202f"

LIMITATIONS = (
    "Only the exact headers 'SpringSharp Version 3.0' and 'SpringSharp Version 3,0' are "
    "supported. SpringSharp 2.0, SpringStyle 1.x and unknown versions are rejected "
    "because their field meanings differ.",
    "No physical geometry is created: hull lines, offsets, hydrostatics, stability and "
    "flooding inputs stay unknown, and the imported draft cannot produce hydrostatic, "
    "GM, GZ, trim or roll results.",
    "No centre of gravity, moment of inertia, ballast condition or complete weight ledger "
    "is derived. The five declared miscellaneous weights plus an explicit unknown "
    "remainder item are not a displacement balance.",
    "The concept section's batteries, machinery and fuel are unadopted proposals: their "
    "ledger masses stay null until a user reviews and adopts an estimate, and the "
    "concept balance is deliberately absent, so no strength, steadiness or space screen "
    "is enabled.",
    "A generated working condition permits review of independent gun and fuel estimates. "
    "Shaft power is not stored in the source; the speed-to-machinery estimate remains "
    "unavailable until a user supplies power or the required balance assumptions.",
    "The raw broadside count stays null. The existing estimator's own fallback to the "
    "installed count is a screening assumption, not a sourced eligibility fact, and this "
    "import makes no broadside eligibility claim.",
    "The source program's normal displacement is not stored in the file. It is recorded "
    "only as a derived reference from L_ft * B_bulges_ft * T_ft * Cb / 35, never as a "
    "ledger mass or a measured displacement, and the moulded beam is never substituted "
    "for a missing beam at the bulges.",
    "Shell weights are read as pounds and the five miscellaneous weights as long tons in "
    "every saved file, whatever the saved display scale; calibre, armour and hull units "
    "follow their own selectors. Armour belt, bulkhead and bulge extents follow the "
    "armour scale selector saved at position 10, independently of the hull scale "
    "selector at position 3.",
    "The existing machinery and battery kernels use the declared moulded beam where the "
    "source would use the beam at the bulges; that adaptation is disclosed rather than "
    "silently applied.",
    "A bank whose layout, count, calibre, year, gun type or mount type falls outside an "
    "existing model's domain keeps its editable facts and its archive and is left without "
    "a concept estimate; nothing is clamped, relabelled or reinterpreted.",
    "Positions 247..279 are writer padding: they are archived verbatim and are never "
    "read as parameters.",
    "This is a bounded format migration, not whole-program parity: no claim of complete "
    "SpringSharp 3.0 behaviour, historical validation or research equivalence is made.",
)


class SshipImportError(ValueError):
    """Report one or more structured SpringSharp import failures."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        detail = "; ".join(
            f"{item.get('path', '$')}: {item.get('message', 'invalid input')}"
            for item in diagnostics[:3]
        )
        super().__init__(detail or "SpringSharp import failed")


def _diagnostic(code, path, message, *, severity="error", line=None, index=None):
    item = {"code": code, "severity": severity, "path": path, "message": message,
            "blocking": severity == "error"}
    if line is not None:
        item["line"] = line
    if index is not None:
        item["index"] = index
    return item


class _Values:
    """Parsed position values, keeping the exact raw text of every record."""

    def __init__(self, raw, values):
        self.raw = raw
        self.values = values


# ------------------------------------------------------------------ bytes ---

def _decode(data):
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise SshipImportError([_diagnostic(
            "sship.source.not_bytes", "$.data", "source content must be bytes")])
    data = bytes(data)
    if len(data) > MAX_BYTES:
        raise SshipImportError([_diagnostic(
            "sship.source.too_large", "$.data",
            f"source content is {len(data)} bytes; the supported maximum is {MAX_BYTES}")])
    if data.startswith(b"\xef\xbb\xbf"):
        encoding, codec, prefix = "utf-8-bom", "utf-8-sig", 3
    elif data.startswith(b"\xff\xfe"):
        encoding, codec, prefix = "utf-16-le-bom", "utf-16-le", 2
    elif data.startswith(b"\xfe\xff"):
        encoding, codec, prefix = "utf-16-be-bom", "utf-16-be", 2
    else:
        encoding, codec, prefix = "utf-8", "utf-8", 0
    try:
        # The byte-order mark is consumed here, so it can never leak into the
        # header record or into any archived field.
        return data[prefix:].decode(codec, errors="strict"), encoding
    except UnicodeDecodeError as error:
        raise SshipImportError([_diagnostic(
            "sship.source.encoding_invalid", "$.data",
            f"source content is not strict {encoding}: {error}")]) from error


def _split_records(text, count):
    """Split on CRLF/CR/LF only; return ``(records, tail_after_them)``.

    The text always ends in one record, even when the last field is empty and
    the file has no final newline, so a reader never silently loses a position.
    """
    records = []
    position = 0
    for match in _RECORD_SEPARATOR.finditer(text):
        records.append(text[position:match.start()])
        position = match.end()
        if len(records) == count:
            return records, text[position:]
    records.append(text[position:])
    return records, ""


# ---------------------------------------------------------------- numbers ---

class _NumberError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _parse_number(token, separator):
    """Parse one saved numeric token under the header's decimal convention.

    The opposite punctuation may only appear as a *correct* thousands group;
    an ambiguous or malformed grouping is rejected instead of guessed, and text
    fields never reach this function.
    """
    text = token.strip(_GROUP_SPACES)
    if not text:
        raise _NumberError("sship.field.number_invalid", "the value is empty")
    if len(text) > MAX_TOKEN_CHARS:
        raise _NumberError("sship.field.number_invalid",
                           f"the value is longer than {MAX_TOKEN_CHARS} characters")
    sign = 1.0
    if text[0] in "+-":
        sign = -1.0 if text[0] == "-" else 1.0
        text = text[1:]
    exponent = ""
    match = _EXPONENT.search(text)
    if match is not None:
        exponent = text[match.start():]
        text = text[:match.start()]
        if not _EXPONENT_TAIL.fullmatch(exponent):
            raise _NumberError("sship.field.number_invalid",
                               f"the exponent {exponent!r} is malformed")
    if not text:
        raise _NumberError("sship.field.number_invalid", "the value has no digits")
    opposite = "." if separator == "," else ","
    if text.count(separator) > 1:
        raise _NumberError("sship.field.number_invalid",
                           f"the declared decimal separator {separator!r} appears more "
                           f"than once")
    if separator in text:
        integer_part, fraction = text.split(separator)
        if not _INTEGER.fullmatch(fraction):
            raise _NumberError("sship.field.number_invalid",
                               f"the fractional part {fraction!r} is not a digit group")
    else:
        integer_part, fraction = text, ""
    digits = _integer_digits(integer_part, opposite)
    if fraction:
        digits = f"{digits}.{fraction}"
    if exponent:
        digits = f"{digits}{exponent}"
    try:
        value = float(digits)
    except (OverflowError, ValueError) as error:
        raise _NumberError("sship.field.number_invalid",
                           f"the value is outside the supported numeric range: {error}")
    value *= sign
    if not math.isfinite(value):
        raise _NumberError("sship.field.number_invalid",
                           "the value is not a finite number")
    return value


def _integer_digits(integer_part, opposite):
    """Validate an integer part and return it without its thousands groups."""
    separators = {character for character in integer_part
                  if character == opposite or character in _GROUP_SPACES}
    if not separators:
        if integer_part == "":
            return "0"
        if not _INTEGER.fullmatch(integer_part):
            raise _NumberError("sship.field.number_invalid",
                               f"the integer part {integer_part!r} is not a digit group")
        return integer_part
    if len(separators) > 1:
        raise _NumberError("sship.field.number_invalid",
                           "the value mixes incompatible thousands separators")
    separator = separators.pop()
    groups = integer_part.split(separator)
    if not _INTEGER.fullmatch(groups[0]) or not 1 <= len(groups[0]) <= 3:
        raise _NumberError("sship.field.number_invalid",
                           f"the thousands group {integer_part!r} is malformed")
    if len(groups) < 2 or any(len(group) != 3 for group in groups[1:]):
        raise _NumberError("sship.field.number_invalid",
                           f"the thousands group {integer_part!r} is malformed")
    return "".join(groups)


# ----------------------------------------------------------------- values ---

def _parse_field(index, record, separator, diagnostics):
    """Return the parsed value of one source position."""
    kind = sship_fields.kind_of(index)
    line = index + 2
    if kind == sship_fields.TEXT:
        return None if record.strip() == "" else record
    token = record.strip(_GROUP_SPACES)
    if token == "":
        return None
    try:
        if kind == sship_fields.BOOLEAN:
            lowered = token.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
            raise _NumberError("sship.field.boolean_invalid",
                               f"{token!r} is not a saved checkbox state")
        value = _parse_number(record, separator)
        if kind == sship_fields.SELECTOR:
            if not float(value).is_integer():
                raise _NumberError("sship.field.number_invalid",
                                   "a saved selection must be a whole number")
            if int(value) not in (0, 1):
                raise _NumberError(
                    "sship.scale.selector_unsupported",
                    f"saved scale selection {int(value)} is not a stable display unit; "
                    f"values 2 and 3 are commands that reset the scales and are not a "
                    f"saved unit")
            return int(value)
        if kind == sship_fields.ENUM and not float(value).is_integer():
            raise _NumberError("sship.field.number_invalid",
                               "a saved combo selection must be a whole number")
        if kind != sship_fields.ENUM and value < 0 \
                and index not in sship_fields.SIGNED_INDEXES:
            raise _NumberError("sship.field.negative",
                               f"the declared value {value} is negative")
    except _NumberError as error:
        if index in sship_fields.SHADOWED:
            # The original reader ignores this occurrence entirely.
            diagnostics.append(_diagnostic(
                "sship.field.ignored_invalid", f"$.fields[{index}]",
                f"{error}; this occurrence is never read by the original program and is "
                f"archived unchanged", severity="warning", line=line, index=index))
            return None
        diagnostics.append(_diagnostic(error.code, f"$.fields[{index}]",
                                       f"{token!r}: {error}", line=line, index=index))
        return None
    if kind in (sship_fields.INTEGER, sship_fields.ENUM):
        return int(value) if float(value).is_integer() else value
    return value


# ----------------------------------------------------------------- source ---

def _basename(filename):
    if not isinstance(filename, str) or not filename.strip():
        raise SshipImportError([_diagnostic(
            "sship.source.filename_invalid", "$.filename",
            "filename must be a nonempty string")])
    base = os.path.basename(filename.replace("\\", "/")).strip()
    if not base or base in {".", ".."}:
        base = "ship.sship"
    return base


def _header(record):
    if record in SUPPORTED_HEADERS:
        return record, SUPPORTED_HEADERS[record]
    known = _KNOWN_OTHER_VERSIONS.get(record)
    message = (f"{record!r} is a known unsupported SpringSharp version ({known}); its "
               f"field meanings differ from 3.0"
               if known else
               f"{record!r} is not a supported SpringSharp 3.0 header; expected "
               f"'SpringSharp Version 3.0' or 'SpringSharp Version 3,0'")
    raise SshipImportError([_diagnostic("sship.version_unsupported", "$.header", message)])


# --------------------------------------------------------------- assembly ---

def _field_records(records):
    """Build the 280 ordered field records with their default dispositions."""
    entries = []
    for index, record in enumerate(records):
        if index in sship_fields.RESERVED_INDEXES:
            disposition = "reserved"
            reason = ("ignored writer padding; archived verbatim and never read as a "
                      "parameter")
        elif index in sship_fields.SHADOWED:
            disposition = "duplicate"
            reason = ("the writer stores this mount count twice; the later occurrence is "
                      "the value a sequential reader keeps")
        else:
            disposition = "preserved"
            reason = "archived only; no canonical destination"
        entries.append({"index": index, "line": index + 2,
                        "name": sship_fields.name_of(index), "raw": record,
                        "disposition": disposition, "destinations": [], "reason": reason})
    return entries


def _counts(fields_list):
    """Exactly the four dispositions the contract names; they sum to 280."""
    counts = {}
    for disposition in ("mapped", "preserved", "duplicate", "reserved"):
        counts[disposition] = sum(1 for entry in fields_list
                                  if entry["disposition"] == disposition)
    return counts


def _read(data):
    """Decode, validate the header and parse every position."""
    text, encoding = _decode(data)
    records, notes = _split_records(text, sship_fields.FIELD_COUNT + 1)
    if len(records) < sship_fields.FIELD_COUNT + 1:
        raise SshipImportError([_diagnostic(
            "sship.fields.truncated", "$.data",
            f"the file holds {max(len(records) - 1, 0)} of {sship_fields.FIELD_COUNT} "
            f"parameter records")])
    header, separator = _header(records[0])
    raw = records[1:]
    diagnostics = []
    for index, record in enumerate(raw):
        if len(record) > MAX_LINE_CHARS:
            raise SshipImportError([_diagnostic(
                "sship.field.too_long", f"$.fields[{index}]",
                f"the record is {len(record)} characters; the supported maximum is "
                f"{MAX_LINE_CHARS}", line=index + 2, index=index)])
    values = [_parse_field(index, record, separator, diagnostics)
              for index, record in enumerate(raw)]
    errors = [item for item in diagnostics if item["severity"] == "error"]
    if errors:
        raise SshipImportError(errors)
    return {
        "raw": raw, "values": _Values(raw, values), "notes": notes, "header": header,
        "separator": separator, "encoding": encoding, "data": data,
        "diagnostics": diagnostics,
    }


def _source(filename, data, read):
    header = read["header"]
    version = f"3{read['separator']}0"
    return {
        "filename": filename,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_length": len(data),
        "encoding": read["encoding"],
        "header": header,
        "version": version,
        "decimal_separator": read["separator"],
    }


def _migration(source, read, derived, mapping, diagnostics):
    return {
        "schema": MIGRATION_SCHEMA,
        "method_version": METHOD_VERSION,
        "source": copy.deepcopy(source),
        "original_base64": base64.b64encode(read["data"]).decode("ascii"),
        "raw_fields": list(read["raw"]),
        "notes": read["notes"],
        "derived": copy.deepcopy(derived),
        "mapping": copy.deepcopy(mapping),
        "diagnostics": copy.deepcopy(diagnostics),
        "limitations": list(LIMITATIONS),
    }


def preview(data, *, filename="ship.sship"):
    """Read SpringSharp 3.0 bytes and return the full preview contract.

    Args:
        data (bytes): The original file content, exactly as selected.
        filename (str): Source filename; only its basename is reported.

    Returns:
        (dict): ``schema``, ``method_version``, ``source``, ``project``,
            ``fields``, ``counts``, ``diagnostics`` and ``limitations``.

    Raises:
        SshipImportError: If the content, header, record count or a populated
            field cannot be read. The error carries structured diagnostics.
    """
    base = _basename(filename)
    read = _read(data)
    source = _source(base, read["data"], read)
    diagnostics = read["diagnostics"]
    fallback = os.path.splitext(base)[0] or "ship"
    try:
        parts, dispositions = sship_mapping.project(
            read["values"], diagnostics, fallback_name=fallback)
    except (ValueError, OverflowError) as error:
        raise SshipImportError([_diagnostic(
            "sship.numeric_range", "$.data",
            f"the source values cannot be converted within the supported numeric range: {error}")]) from error
    entries = _field_records(read["raw"])
    for entry in entries:
        if entry["disposition"] == "reserved":
            continue
        disposition, destinations, reason = dispositions[entry["index"]]
        entry["disposition"] = disposition
        entry["destinations"] = destinations
        entry["reason"] = reason
    counts = _counts(entries)
    parts["mapping"]["counts"] = counts
    parts["mapping"]["fields"] = [
        {"index": entry["index"], "name": entry["name"],
         "disposition": entry["disposition"], "destinations": entry["destinations"],
         "reason": entry["reason"]} for entry in entries]
    project = _project(source, read, parts, diagnostics)
    return {
        "schema": SCHEMA,
        "method_version": METHOD_VERSION,
        "source": source,
        "project": project,
        "fields": entries,
        "counts": counts,
        "diagnostics": copy.deepcopy(diagnostics),
        "limitations": list(LIMITATIONS),
    }


def _project(source, read, parts, diagnostics):
    """Build the validated canonical draft with its source archive."""
    project = project_io.new_project(parts["name"], f"sship-{source['sha256'][:16]}")
    project["hull"] = parts["hull"]
    if parts["metadata"]:
        project["metadata"] = parts["metadata"]
    if parts["systems"]:
        project["systems"] = parts["systems"]
    project["weight_groups"] = parts["weight_groups"]
    project["loading_conditions"] = [{
        "id": "imported-working", "label": "Imported working condition (generated)",
        "reference_displacement_t": None, "overrides": {},
        "source": "Generated by Plimsoll for reviewing the migrated normal draft; not a source loading condition",
    }]
    diagnostics.append(_diagnostic(
        "sship.loading.generated", "$.loading_conditions[0]",
        "A working condition was generated to review estimates; no source condition, mass or CG is inferred.",
        severity="info"))
    if parts["concept_design"] is not None:
        project["concept_design"] = parts["concept_design"]
    project["sources"] = {
        "springsharp3": {
            "method_version": METHOD_VERSION,
            "filename": source["filename"],
            "sha256": source["sha256"],
        }
    }
    mapping = dict(parts["mapping"])
    project["migration"] = _migration(source, read, parts["derived"], mapping, diagnostics)
    try:
        return project_io.normalize_project(project)
    except project_io.ProjectValidationError as error:
        raise SshipImportError([
            _diagnostic("sship.project.invalid", item.get("path", "$.project"),
                        item.get("message", "the projected draft is invalid"))
            for item in error.diagnostics if item.get("severity") == "error"
        ] or [_diagnostic("sship.project.invalid", "$.project",
                          "the projected draft is invalid")]) from error


def convert(data, *, filename="ship.sship", name=None):
    """Return the canonical draft for the same bytes ``preview`` reports on.

    Args:
        data (bytes): The original file content.
        filename (str): Source filename; only its basename is archived.
        name (str, optional): Explicit project name replacing a blank or
            declared source name.

    Returns:
        (dict): Normalized canonical project with the source archive intact.

    Raises:
        SshipImportError: If the content cannot be read.
    """
    result = preview(data, filename=filename)
    if isinstance(name, str) and name.strip():
        project = copy.deepcopy(result["project"])
        project["name"] = name
        try:
            return project_io.normalize_project(project)
        except project_io.ProjectValidationError as error:
            raise SshipImportError(error.diagnostics) from error
    return result["project"]
