"""Segmented belt and layered-deck armour panels as a pure geometry kernel.

This is the independent flat-panel model that follows whole-battery adoption. It
is deliberately **not** another recovered ``SpringSharp`` expression and it is
not part of the adapted configuration method: it carries its own
``plimsoll-armour-panels-v1`` so a reader can always tell a declared rectangular
armour plate from an empirical reading.

The kernel is a pure function over a finite declared domain. It never touches a
project, a ledger or a file, it never clamps an out-of-domain number, and it
never invents a default: no material density, no implicit number of sides, no
implicit angle and no silently inherited empirical thickness or size. ``None``
means *unknown*; a declared ``0`` is a real zero. A known zero count or a known
zero thickness is a determined zero, and a known count of zero needs no
dimension to prove it.

Geometry
--------
* Developed width: ``area = length × width × count``; the angle is not read.
* Projected width: ``developed width = width / cos(radians(inclination_deg))``;
  the signed angle is from the vertical for belts and bulkheads and from the
  horizontal for decks, but both signs give the same area.
* ``volume = developed area × thickness_mm / 1000``; ``mass_t = volume ×
  density_kg_m3 / 1000``. There is no fabrication allowance, taper, support,
  fastener, curved area or coverage-union overlap test.

Provenance and availability are independent: a number can be mathematically
available while a generated proposal stays unadoptable. Adoption requires the
project geometry source and the region source, plus a plate source and a density
source for each positive-mass plate. A missing source never erases the
mathematically available numbers.
"""

from __future__ import annotations

import copy
import math
import re

METHOD_VERSION = "plimsoll-armour-panels-v1"
DEFAULT_PATH = "$.concept_design.armour_geometry"

# The repository's ASCII id grammar, copied verbatim from battery_layout.py:190.
ID_PATTERN = re.compile(r"\A[A-Za-z0-9_.-]{1,80}\Z")

ELIGIBLE_KINDS = ("belt_main", "belt_ends", "belt_upper", "bulkhead", "deck")
VERTICAL_KINDS = ("belt_main", "belt_ends", "belt_upper", "bulkhead")
HORIZONTAL_KINDS = ("deck",)
WIDTH_BASES = ("developed", "projected")

MAX_REGIONS = 50
MAX_PLATES_PER_REGION = 100

MAX_EXTENT_M = 5000.0
MAX_THICKNESS_MM = 2000.0
MAX_DENSITY_KG_M3 = 30000.0
MAX_COUNT = 1000000
MIN_ANGLE_DEG = -89.0
MAX_ANGLE_DEG = 89.0

ROOT_FIELDS = ("source", "regions")
REGION_FIELDS = ("fixed_armour_id", "source", "plates")
PLATE_FIELDS = ("id", "source", "density_source", "length_m", "width_m",
                "thickness_mm", "density_kg_m3", "count", "width_basis",
                "inclination_deg")

STATUS_AVAILABLE = "available"
STATUS_PARTIAL = "partial"
STATUS_UNAVAILABLE = "unavailable"


class ArmourGeometryError(ValueError):
    """A refused panel declaration, reported with structured diagnostics."""

    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__("; ".join(d["message"] for d in diagnostics if d.get("blocking", True)))


def _diag(code, message, path, blocking=True):
    return {"severity": "error" if blocking else "warning",
            "code": code, "path": path, "message": message, "blocking": blocking}


def _present(value):
    """A source only counts for adoption when it is a nonempty string."""
    return isinstance(value, str) and value.strip() != ""


def _finite_json(value):
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ArmourGeometryError([_diag("armour_geometry.non_finite",
                                         "a derived reading is not a finite number",
                                         DEFAULT_PATH)])
    return value


# ------------------------------------------------------------- declaration --

def _reject_unknown(raw, allowed, path, diagnostics):
    for key in raw:
        if key not in allowed:
            diagnostics.append(_diag(
                "armour_geometry.unsupported_field",
                "unknown field %r is not part of the declaration" % (key,),
                path + "." + str(key)))


def _optional_string(raw, field, path, diagnostics):
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s must be a string or null" % field,
                                 path + "." + field))
        return None
    return value


def _id_string(raw, field, path, diagnostics):
    value = raw.get(field)
    if value is None:
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s must be a string id" % field,
                                 path + "." + field))
        return None
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s must match the repository id grammar" % field,
                                 path + "." + field))
        return None
    return value


def _optional_int(raw, field, path, diagnostics, low, high):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s must be an integer or null" % field,
                                 path + "." + field))
        return None
    if value < low or value > high:
        diagnostics.append(_diag("armour_geometry.domain",
                                 "%s must be between %s and %s" % (field, low, high),
                                 path + "." + field))
        return None
    return int(value)


def _optional_number(raw, field, path, diagnostics, *, low=None, high=None,
                     low_open=False, negative=False):
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s must be a finite number or null" % field,
                                 path + "." + field))
        return None
    try:
        value = float(value)
    except (OverflowError, ValueError):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s exceeds the supported numeric range" % field,
                                 path + "." + field))
        return None
    if not math.isfinite(value):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "%s must be a finite number" % field,
                                 path + "." + field))
        return None
    if not negative and value < 0.0:
        diagnostics.append(_diag("armour_geometry.domain",
                                 "%s must not be negative" % field,
                                 path + "." + field))
        return None
    if low is not None:
        if low_open:
            if value <= low:
                diagnostics.append(_diag("armour_geometry.domain",
                                         "%s must be greater than %s" % (field, low),
                                         path + "." + field))
                return None
        elif value < low:
            diagnostics.append(_diag("armour_geometry.domain",
                                     "%s must be at least %s" % (field, low),
                                     path + "." + field))
            return None
    if high is not None and value > high:
        diagnostics.append(_diag("armour_geometry.domain",
                                 "%s must be at most %s" % (field, high),
                                 path + "." + field))
        return None
    return value


def _optional_basis(raw, path, diagnostics):
    value = raw.get("width_basis")
    if value is None:
        return None
    if value not in WIDTH_BASES:
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "width_basis must be 'developed', 'projected' or null",
                                 path + ".width_basis"))
        return None
    return value


# --------------------------------------------------------------- normalize --

def _fixed_map(fixed_armour):
    result = {}
    if not isinstance(fixed_armour, (list, tuple)):
        return result
    for record in fixed_armour:
        if not isinstance(record, dict):
            continue
        rid = record.get("id")
        if isinstance(rid, str) and rid not in result:
            result[rid] = record.get("kind")
    return result


def _normalize_plate(raw_plate, path, diagnostics):
    if not isinstance(raw_plate, dict):
        diagnostics.append(_diag("armour_geometry.invalid", "plate must be an object", path))
        return None
    _reject_unknown(raw_plate, PLATE_FIELDS, path, diagnostics)
    # Every field is declared even when a later evaluation will not read it.
    return {
        "id": _id_string(raw_plate, "id", path, diagnostics),
        "source": _optional_string(raw_plate, "source", path, diagnostics),
        "density_source": _optional_string(raw_plate, "density_source", path, diagnostics),
        "length_m": _optional_number(raw_plate, "length_m", path, diagnostics,
                                     low=0.0, high=MAX_EXTENT_M),
        "width_m": _optional_number(raw_plate, "width_m", path, diagnostics,
                                    low=0.0, high=MAX_EXTENT_M),
        "thickness_mm": _optional_number(raw_plate, "thickness_mm", path, diagnostics,
                                         low=0.0, high=MAX_THICKNESS_MM),
        "density_kg_m3": _optional_number(raw_plate, "density_kg_m3", path, diagnostics,
                                          low=0.0, high=MAX_DENSITY_KG_M3, low_open=True),
        "count": _optional_int(raw_plate, "count", path, diagnostics, 0, MAX_COUNT),
        "width_basis": _optional_basis(raw_plate, path, diagnostics),
        "inclination_deg": _optional_number(raw_plate, "inclination_deg", path, diagnostics,
                                            low=MIN_ANGLE_DEG, high=MAX_ANGLE_DEG, negative=True),
    }


def _normalize_plates(raw_plates, path, diagnostics):
    plates_path = path + ".plates"
    if raw_plates is None:
        # Missing is incomplete, never a declared zero.
        return None
    if not isinstance(raw_plates, list):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "plates must be an array or null", plates_path))
        return None
    if len(raw_plates) > MAX_PLATES_PER_REGION:
        diagnostics.append(_diag("armour_geometry.too_many",
                                 "at most %d plates per region are supported" % MAX_PLATES_PER_REGION,
                                 plates_path))
    plates = []
    seen = set()
    for index, raw_plate in enumerate(raw_plates):
        plate_path = "%s[%d]" % (plates_path, index)
        plate = _normalize_plate(raw_plate, plate_path, diagnostics)
        if plate is None:
            continue
        plate_id = plate["id"]
        if plate_id is not None:
            if plate_id in seen:
                diagnostics.append(_diag("armour_geometry.duplicate_id",
                                         "plate id %r is declared more than once" % plate_id,
                                         plate_path + ".id"))
            else:
                seen.add(plate_id)
        plates.append(plate)
    return plates


def _normalize_region(raw_region, path, fixed_map, diagnostics):
    if not isinstance(raw_region, dict):
        diagnostics.append(_diag("armour_geometry.invalid", "region must be an object", path))
        return None
    _reject_unknown(raw_region, REGION_FIELDS, path, diagnostics)

    fid_path = path + ".fixed_armour_id"
    raw_fid = raw_region.get("fixed_armour_id")
    fixed_armour_id = None
    if raw_fid is None:
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "fixed_armour_id must name an existing fixed armour record",
                                 fid_path))
    elif not isinstance(raw_fid, str):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "fixed_armour_id must be a string", fid_path))
    elif ID_PATTERN.fullmatch(raw_fid) is None:
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "fixed_armour_id must use the ASCII id grammar", fid_path))
    elif raw_fid not in fixed_map:
        diagnostics.append(_diag("armour_geometry.reference_unknown",
                                 "fixed armour record %r does not exist" % raw_fid, fid_path))
    elif fixed_map[raw_fid] not in ELIGIBLE_KINDS:
        diagnostics.append(_diag("armour_geometry.ineligible_kind",
                                 "fixed armour kind %r is not eligible for the panel model"
                                 % (fixed_map[raw_fid],), fid_path))
    else:
        fixed_armour_id = raw_fid

    return {
        "fixed_armour_id": fixed_armour_id,
        "source": _optional_string(raw_region, "source", path, diagnostics),
        "plates": _normalize_plates(raw_region.get("plates"), path, diagnostics),
    }


def _normalize_regions(raw_regions, fixed_armour, path, diagnostics):
    fixed_map = _fixed_map(fixed_armour)
    if raw_regions is None:
        return []
    regions_path = path + ".regions"
    if not isinstance(raw_regions, list):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "regions must be an array or null", regions_path))
        return []
    if len(raw_regions) > MAX_REGIONS:
        diagnostics.append(_diag("armour_geometry.too_many",
                                 "at most %d regions are supported" % MAX_REGIONS,
                                 regions_path))
    regions = []
    seen_fixed = set()
    for index, raw_region in enumerate(raw_regions):
        region_path = "%s[%d]" % (regions_path, index)
        region = _normalize_region(raw_region, region_path, fixed_map, diagnostics)
        if region is None:
            continue
        fixed_armour_id = region["fixed_armour_id"]
        if fixed_armour_id is not None:
            if fixed_armour_id in seen_fixed:
                diagnostics.append(_diag("armour_geometry.duplicate_id",
                                         "fixed armour record %r is declared more than once"
                                         % fixed_armour_id,
                                         region_path + ".fixed_armour_id"))
            else:
                seen_fixed.add(fixed_armour_id)
        regions.append(region)
    return regions


def normalize(config, fixed_armour, path=DEFAULT_PATH):
    """Normalize the declared armour geometry root, or ``None`` when null.

    ``config`` is the geometry root itself -- ``{source, regions}`` -- never a
    whole project or a ``concept_design`` wrapper: an adapter normalizes
    wrappers elsewhere. A non-object root is refused rather than silently read
    as absent, unknown keys are refused, a missing ``regions`` list becomes an
    empty ``[]`` and a declared ``source`` is always preserved. Structural
    faults, wrong types, nonfinite or negative numbers, out-of-domain numbers,
    duplicate ids and unknown or ineligible references are refused with
    :class:`ArmourGeometryError`. Unknown draft numbers and sources are
    normalized to ``None`` and never invented.
    """
    if config is None:
        return None
    diagnostics = []
    if not isinstance(config, dict):
        diagnostics.append(_diag("armour_geometry.invalid",
                                 "armour_geometry must be an object or null", path))
        raise ArmourGeometryError(diagnostics)
    _reject_unknown(config, ROOT_FIELDS, path, diagnostics)
    source = _optional_string(config, "source", path, diagnostics)
    regions = _normalize_regions(config.get("regions"), fixed_armour, path, diagnostics)
    if any(d.get("blocking") for d in diagnostics):
        raise ArmourGeometryError(diagnostics)
    return {"source": source, "regions": regions}


# ---------------------------------------------------------------- evaluate --

def _angle_convention(kind):
    if kind in VERTICAL_KINDS:
        return "from_vertical"
    if kind in HORIZONTAL_KINDS:
        return "from_horizontal"
    return None


def _plate_provenance(plate, region, kind, root_source):
    return {
        "method_version": METHOD_VERSION,
        "fixed_armour_id": region.get("fixed_armour_id"),
        "kind": kind,
        "plate_id": plate.get("id"),
        "source": root_source,
        "plate_source": plate.get("source"),
        "density_source": plate.get("density_source"),
        "width_basis": plate.get("width_basis"),
        "inclination_deg": plate.get("inclination_deg"),
        "width_angle_convention": _angle_convention(kind),
        "count": plate.get("count"),
    }


def _region_provenance(region, kind, root_source, plate_count):
    return {
        "method_version": METHOD_VERSION,
        "fixed_armour_id": region.get("fixed_armour_id"),
        "kind": kind,
        "source": root_source,
        "region_source": region.get("source"),
        "width_angle_convention": _angle_convention(kind),
        "plate_count": plate_count,
    }


def _evaluate_plate(plate, region, kind, root_source, path):
    diagnostics = []
    count = plate.get("count")
    length = plate.get("length_m")
    width = plate.get("width_m")
    thickness = plate.get("thickness_mm")
    density = plate.get("density_kg_m3")
    basis = plate.get("width_basis")
    angle = plate.get("inclination_deg")

    area = None
    volume = None
    mass = None

    if count == 0:
        # A declared zero count is a determined zero and needs no dimension.
        area = 0.0
        volume = 0.0
        mass = 0.0
    else:
        if length is not None and width is not None and count is not None:
            if basis == "projected":
                if angle is not None:
                    developed_width = width / math.cos(math.radians(angle))
                    area = length * developed_width * count
                else:
                    diagnostics.append(_diag(
                        "armour_geometry.incomplete",
                        "a projected width basis needs inclination_deg",
                        path + ".inclination_deg", blocking=False))
            elif basis == "developed":
                # The developed basis never reads the angle.
                area = length * width * count
            else:
                diagnostics.append(_diag(
                    "armour_geometry.incomplete",
                    "width_basis is required to compute the developed area",
                    path + ".width_basis", blocking=False))

        if thickness == 0:
            # A known zero thickness determines a zero volume and mass even
            # while the area may still be unknown.
            volume = 0.0
            mass = 0.0
        elif thickness is not None and area is not None:
            volume = area * thickness / 1000.0
            if density is not None:
                mass = volume * density / 1000.0

    if area is not None and volume is not None and mass is not None:
        status = STATUS_AVAILABLE
    elif area is None and volume is None and mass is None:
        status = STATUS_UNAVAILABLE
    else:
        status = STATUS_PARTIAL

    adoptable = False
    # Adoption is about a known mass, not about a known area: a plate whose mass
    # is determined (including a determined zero from a zero count or a zero
    # thickness) can be adopted even while its area stays unknown.
    if mass is not None and _present(root_source) and _present(region.get("source")):
        if mass > 0.0:
            if _present(plate.get("source")) and _present(plate.get("density_source")):
                adoptable = True
        else:
            adoptable = True
        if not adoptable:
            diagnostics.append(_diag(
                "armour_geometry.source_missing",
                "a positive-mass plate needs both a plate source and a density source",
                path, blocking=False))

    return {
        "id": plate.get("id"),
        "method_version": METHOD_VERSION,
        "status": status,
        "adoptable": adoptable,
        "values": {
            "area_m2": _finite_json(area),
            "volume_m3": _finite_json(volume),
            "mass_t": _finite_json(mass),
        },
        "diagnostics": diagnostics,
        "provenance": _plate_provenance(plate, region, kind, root_source),
    }


def evaluate(region, kind, *, source=None, path=DEFAULT_PATH):
    """Evaluate one normalized region into finite per-plate and region readings.

    Pure: it reads ``region`` only, mutates nothing and performs no I/O. Numbers
    stay available even when provenance is insufficient; ``adoptable`` and the
    diagnostics explain any missing source. Unknown inputs never fall back to a
    zero or to an empirical value.
    """
    if not isinstance(region, dict):
        region = {}
    if kind not in ELIGIBLE_KINDS:
        # Curved bulges and conning towers have no rectangular panel geometry;
        # an adapter normalizes region kinds before evaluation, so a raw curved
        # kind is a programming error rather than a silently empty result.
        raise ArmourGeometryError([_diag(
            "armour_geometry.ineligible_kind",
            "kind %r is not eligible for the panel model" % (kind,), path)])
    diagnostics = []
    plates = region.get("plates")
    root_source = source
    region_source = region.get("source")

    if not plates:
        diagnostics.append(_diag(
            "armour_geometry.incomplete",
            "the region is opted in but has no declared plate list",
            path + ".plates", blocking=False))
        return {
            "id": region.get("fixed_armour_id"),
            "method_version": METHOD_VERSION,
            "status": STATUS_UNAVAILABLE,
            "adoptable": False,
            "values": {"area_m2": None, "volume_m3": None, "mass_t": None,
                       "known_mass_subtotal_t": 0.0},
            "records": [],
            "diagnostics": diagnostics,
            "provenance": _region_provenance(region, kind, root_source, 0),
        }

    records = []
    for index, plate in enumerate(plates):
        plate_path = "%s.plates[%d]" % (path, index)
        records.append(_evaluate_plate(plate, region, kind, root_source, plate_path))

    areas = [record["values"]["area_m2"] for record in records]
    volumes = [record["values"]["volume_m3"] for record in records]
    masses = [record["values"]["mass_t"] for record in records]

    # Area and volume sum every declared layer; the model never tests coverage.
    complete_area = all(value is not None for value in areas)
    complete_volume = all(value is not None for value in volumes)
    complete_mass = all(value is not None for value in masses)

    region_area = sum(areas) if complete_area else None
    region_volume = sum(volumes) if complete_volume else None
    region_mass = sum(masses) if complete_mass else None
    known_subtotal = sum(value for value in masses if value is not None)

    statuses = [record["status"] for record in records]
    if all(state == STATUS_AVAILABLE for state in statuses):
        status = STATUS_AVAILABLE
    elif all(state == STATUS_UNAVAILABLE for state in statuses):
        status = STATUS_UNAVAILABLE
    else:
        status = STATUS_PARTIAL

    if not complete_mass:
        diagnostics.append(_diag(
            "armour_geometry.incomplete",
            "at least one declared plate is unknown; the complete mass is unavailable "
            "and only the known subtotal remains",
            path, blocking=False))

    if complete_mass and not (_present(root_source) and _present(region_source)):
        diagnostics.append(_diag(
            "armour_geometry.source_missing",
            "adoption requires the project geometry source and the region source",
            path, blocking=False))

    adoptable = (complete_mass
                 and _present(root_source)
                 and _present(region_source)
                 and all(record["adoptable"] for record in records))

    return {
        "id": region.get("fixed_armour_id"),
        "method_version": METHOD_VERSION,
        "status": status,
        "adoptable": adoptable,
        "values": {
            "area_m2": _finite_json(region_area),
            "volume_m3": _finite_json(region_volume),
            "mass_t": _finite_json(region_mass),
            "known_mass_subtotal_t": _finite_json(known_subtotal),
        },
        "records": records,
        "diagnostics": diagnostics,
        "provenance": _region_provenance(region, kind, root_source, len(records)),
    }
