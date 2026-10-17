"""Proportional allocation of one whole-battery mount estimate across laid-out rows.

This is a pure function over a finite declared domain. It touches no project, no
ledger and no file, and it mutates none of its arguments. It is deliberately
**not** the source estimate and **not** the layout-identity kernel:

* the recovered whole-battery mount total keeps its own source method
  ``sps-3b3-battery-totals-v1`` (see :data:`SOURCE_METHOD_VERSION`);
* this module carries the product policy ``proportional-row-mounts-v1`` (see
  :data:`POLICY`) and its own ``plimsoll-battery-mount-allocation-v1``.

The result names all three separately, so a reader can always tell which number
came from the recovered source, which from the layout identity and which from a
product decision.

Product policy
--------------
The recovered source provides one whole-battery mounts estimate and **no**
per-group split. This module applies an explicit, versioned product policy:

* each referenced row already carries its own independent mount weight (the
  legacy per-row mount estimate); that weight is the allocation weight;
* the source total is divided in the proportion of those weights, and the
  floating residual of the division is assigned to the **last row with a
  positive weight**, so the parts sum back to the source total;
* a zero-weight row keeps a zero share and a zero allocation;
* a positive source with an all-zero weight sum is **unavailable**; there is no
  equal-share and no first-row fallback;
* a known zero source gives explicit zero allocations.

The policy is a documented product decision; it is never claimed to be the
original program's own per-group allocation.

Domain rules
------------
Every wrong type, every negative and every non-finite number is refused
structurally through :class:`AllocationError` (its ``diagnostics`` carry
``severity``, ``code``, ``path``, ``message`` and ``blocking``). An **unknown**
fact -- a missing source total or a missing row weight -- is not a refusal: it
yields an ``unavailable`` reading whose values are ``None`` and which carries no
partial records. Sum and ratio overflow are guarded the same way: the reading is
``unavailable`` rather than a half-applied allocation.
"""

from __future__ import annotations

import copy
import json
import math

METHOD_VERSION = "plimsoll-battery-mount-allocation-v1"
POLICY = "proportional-row-mounts-v1"
# The recovered source estimate this product policy divides. Kept as its own
# literal so the source method and the product policy can never drift together;
# it equals ``battery_totals.METHOD_VERSION``.
SOURCE_METHOD_VERSION = "sps-3b3-battery-totals-v1"

MAX_ROWS = 2
ROW_FIELDS = ("battery_id", "target_id", "weight_t")


class AllocationError(ValueError):
    """A refused declaration, carrying structured blocking diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics
                                   if d.get("blocking", True)))


def _error(code, path, message):
    return {"code": code, "severity": "error", "path": path, "message": message,
            "blocking": True}


def _warning(code, path, message):
    return {"code": code, "severity": "warning", "path": path, "message": message,
            "blocking": False}


def _mass(value, path, *, nullable):
    """A finite non-negative number, or ``None`` when ``nullable`` and unknown.

    A ``bool``, a fractional object, another type, a negative value and a
    non-finite (or overflowed) value are all refused structurally; ``None`` is
    the only stand-in for *unknown* and is never read as a zero.
    """
    if value is None:
        if nullable:
            return None
        raise AllocationError([_error("battery_mass_allocation.invalid", path,
                                      "must be a finite non-negative number")])
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AllocationError([_error(
            "battery_mass_allocation.invalid", path,
            "must be a finite non-negative number, never a bool, a fractional object or "
            "another type")])
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        raise AllocationError([_error("battery_mass_allocation.domain", path,
                                      "exceeds the supported numeric range")])
    if not math.isfinite(number):
        raise AllocationError([_error("battery_mass_allocation.invalid", path,
                                      "must be a finite number")])
    if number < 0.0:
        raise AllocationError([_error("battery_mass_allocation.domain", path,
                                      "must be non-negative")])
    return number


def _identifier(value, path):
    if not isinstance(value, str) or not value.strip():
        raise AllocationError([_error("battery_mass_allocation.invalid", path,
                                      "must be a non-empty string")])
    return value


def _normalize_rows(rows):
    """Validate and copy the declared rows; the caller's list is never touched."""
    if not isinstance(rows, list):
        raise AllocationError([_error("battery_mass_allocation.invalid", "$.rows",
                                      "must be an array")])
    if len(rows) > MAX_ROWS:
        raise AllocationError([_error("battery_mass_allocation.domain", "$.rows",
                                      "at most %d rows are supported" % (MAX_ROWS,))])
    normalized = []
    battery_ids = set()
    target_ids = set()
    for position, raw in enumerate(rows):
        path = "$.rows[%d]" % (position,)
        if not isinstance(raw, dict):
            raise AllocationError([_error("battery_mass_allocation.invalid", path,
                                          "must be an object")])
        unsupported = sorted(set(raw) - set(ROW_FIELDS))
        if unsupported:
            raise AllocationError([_error(
                "battery_mass_allocation.unsupported_field", path + "." + unsupported[0],
                "unsupported field %r" % (unsupported[0],))])
        battery_id = _identifier(raw.get("battery_id"), path + ".battery_id")
        target_id = _identifier(raw.get("target_id"), path + ".target_id")
        if battery_id in battery_ids:
            raise AllocationError([_error("battery_mass_allocation.duplicate",
                                          path + ".battery_id",
                                          "battery IDs must be unique")])
        if target_id in target_ids:
            raise AllocationError([_error("battery_mass_allocation.duplicate",
                                          path + ".target_id",
                                          "mount target IDs must be unique")])
        battery_ids.add(battery_id)
        target_ids.add(target_id)
        normalized.append({
            "battery_id": battery_id,
            "target_id": target_id,
            "weight_t": _mass(raw.get("weight_t"), path + ".weight_t", nullable=True),
        })
    return normalized


def allocate(layout_id, source_mounts_t, rows, *, source=None):
    """Allocate one whole-battery mount total across at most two declared rows.

    ``layout_id`` names the selected layout and becomes the reading's stable
    ``id``. ``source_mounts_t`` is the recovered whole-battery mounts total, a
    finite non-negative number or ``None`` for *unknown*. ``rows`` is a list of
    at most two ``{"battery_id", "target_id", "weight_t"}`` records: the
    identifiers must be unique and non-empty, and each ``weight_t`` is the row's
    own independent mount weight, a finite non-negative number or ``None`` for
    *unknown*. The keyword-only ``source`` is recorded verbatim as the declared
    source text; it is never parsed.

    Returns a finite JSON reading with ``id``, ``method_version``, ``status``,
    ``values`` (``source_mounts_t``, ``legacy_mounts_t``, ``allocated_total_t``),
    ``records`` (``id``, ``target_id``, ``weight_t``, ``share``,
    ``allocated_mass_t``), ``diagnostics`` and ``provenance``. An unavailable
    allocation carries ``records == []`` and a ``None`` ``allocated_total_t``:
    it is never a partial allocation.
    """
    if not isinstance(layout_id, str) or not layout_id.strip():
        raise AllocationError([_error("battery_mass_allocation.invalid", "$.layout_id",
                                      "must be a non-empty string")])
    # The declared source text is a string or null. It is validated here, at the
    # entry, so a wrong type can never reach the result and raise a raw error
    # from the finite-JSON guard at the end.
    if source is not None and not isinstance(source, str):
        raise AllocationError([_error("battery_mass_allocation.invalid", "$.source",
                                      "must be a string or null")])
    normalized = _normalize_rows(rows)
    total = _mass(source_mounts_t, "$.source_mounts_t", nullable=True)

    diagnostics = []
    weights_known = all(row["weight_t"] is not None for row in normalized)
    legacy = None
    if normalized and weights_known:
        running = 0.0
        for row in normalized:
            running += row["weight_t"]
        if math.isfinite(running):
            legacy = running
        else:
            diagnostics.append(_warning(
                "battery_mass_allocation.overflow", "$.rows",
                "the row weight sum exceeds the supported numeric range"))

    reason = None
    allocated = None
    if not normalized:
        reason = "no rows are declared, so there is nothing to allocate"
    elif total is None:
        reason = "the whole-battery source total is unknown"
    elif not weights_known:
        reason = "at least one row weight is unknown"
    elif legacy is None:
        reason = "the row weight sum exceeds the supported numeric range"
    elif total == 0.0:
        # A determined zero whole total is an explicit zero allocation, whether
        # or not the (necessarily reconcilable) weights are positive.
        allocated = [0.0] * len(normalized)
    elif legacy <= 0.0:
        reason = ("the source total is positive but every row weight is zero; there is no "
                  "equal-share fallback")
    else:
        parts = []
        overflow = False
        for row in normalized:
            # Multiply the source by the *normalized ratio* rather than by the raw
            # weight first: the ratio is at most one, so a large-but-finite source
            # and a large-but-finite weight never overflow a product whose
            # mathematically finite share does not. Multiplying first would.
            try:
                part = total * (row["weight_t"] / legacy)
            except (ArithmeticError, ValueError):
                overflow = True
                break
            if not math.isfinite(part):
                overflow = True
                break
            parts.append(part)
        residual = None
        if not overflow:
            try:
                residual = total - math.fsum(parts)
            except (ArithmeticError, ValueError):
                residual = None
        if overflow or residual is None:
            reason = "a proportional share exceeds the supported numeric range"
        else:
            for index in range(len(parts) - 1, -1, -1):
                if normalized[index]["weight_t"] > 0.0:
                    parts[index] += residual
                    break
            if all(math.isfinite(value) and value >= 0.0 for value in parts):
                allocated = parts
            else:
                reason = "a proportional share exceeds the supported numeric range"

    if allocated is None:
        if reason is not None:
            diagnostics.append(_warning(
                "battery_mass_allocation.unavailable",
                "$.source_mounts_t" if total is None else "$.rows", reason))
        status = "unavailable"
        records = []
        allocated_total = None
    else:
        status = "available"
        allocated_total = total
        records = []
        for index, row in enumerate(normalized):
            weight = row["weight_t"]
            share = (weight / legacy) if (legacy is not None and legacy > 0.0) else 0.0
            records.append({
                "id": row["battery_id"],
                "target_id": row["target_id"],
                "weight_t": weight,
                "share": share,
                "allocated_mass_t": allocated[index],
            })

    result = {
        "id": layout_id,
        "method_version": METHOD_VERSION,
        "status": status,
        "values": {
            "source_mounts_t": total,
            "legacy_mounts_t": legacy,
            "allocated_total_t": allocated_total,
        },
        "records": records,
        "diagnostics": diagnostics,
        "provenance": {
            "source_method_version": SOURCE_METHOD_VERSION,
            "allocation_policy": POLICY,
            "declared_source": source,
        },
    }
    # A last invariant: nothing non-finite (and so nothing non-JSON) ever leaves.
    json.dumps(result, allow_nan=False)
    return result
