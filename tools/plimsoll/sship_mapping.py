"""Project parsed SpringSharp 3.0 values into an editable canonical draft.

The projection is pure: it reads already-parsed positions, records where every
field went, and returns plain JSON values. It performs no I/O, runs no
calculation kernel, and never invents a value the source did not declare.

Two rules run through the whole module:

* **Header-driven grouping.** Mount arithmetic comes from the saved per-mount
  table, never from swapping punctuation between text fields.
* **Unknown is unknown.** A value outside a supported domain is archived with a
  visible warning and leaves its canonical target empty; it is never clamped,
  relabelled or silently replaced.

Each of the seven saved fixed armour regions additionally gets its own
independent unknown-mass target, its own concept declaration and its own balance
role, created together in :meth:`Projection.build`. The import never adopts,
computes or deducts a single armour ton, and it never enables the empirical cost
reading or fabricates a balance section.
"""

from __future__ import annotations

import copy
import math

try:
    from . import auxiliary_weapons as auxiliary_kernel
    from . import concept_estimates as kernels
    from . import fixed_armour as fixed_armour_kernel
    from . import units
except ImportError:  # pragma: no cover - direct-module import convention
    import auxiliary_weapons as auxiliary_kernel
    import concept_estimates as kernels
    import fixed_armour as fixed_armour_kernel
    import units

try:
    from . import sship_fields as fields
except ImportError:  # pragma: no cover - direct-module import convention
    import sship_fields as fields


LONG_TON = "long_ton"

# The repository's shared unit table deliberately carries only the canonical
# display units, so the recovered in/mm, ft/m and lb/kg conversions are named here.
INCH_MM = 25.4
FT_M = 0.3048
POUND_KG = 0.45359237


def _thickness_m(value, selector):
    """Convert a saved armour or calibre plate thickness with its own selector."""
    return value * 0.0254 if selector == 0 else value / 1000.0


def _calibre_mm(value, selector):
    """Convert a saved calibre with that bank's own selector."""
    return value * INCH_MM if selector in (None, 0) else value

# Every imported declaration keeps one explicit, honest provenance string. The
# estimate flag stays unknown: whether the original program's own number was an
# estimate is not recorded in the file.
DECLARATION_SOURCE = (
    "SpringSharp 3.0 file declaration; the original bytes are archived in $.migration"
)
DISPLACEMENT_FORMULA = "displacement_lt = L_ft * B_bulges_ft * T_ft * Cb / 35"
FREEBOARD_FORMULA = (
    "FC_m = 0.6*FCaft + 0.4*FCfore; FD_m = 0.5*FDAft + 0.5*FDFor; "
    "AD_m = 0.5*ADAft + 0.5*ADFor; QD_m = 0.5*QDAft + 0.5*QDFor; "
    "representative_m = FC_m*fc + FD_m*fd + AD_m*ad + QD_m*qd with "
    "fc = fcLength/100, fd = fdLength/100, qd = qdLength/100, ad = 1 - fc - fd - qd; "
    "every height is converted to metres with the hull scale selector at position 3"
)

# Bounded mirrors of the existing estimate kernels: an out-of-domain bank is
# omitted from the concept section instead of being clamped into it.
MAX_CALIBRE_MM = 500.0
MAX_BARREL_CALIBRES = 100.0
MAX_ROUNDS_PER_GUN = 10000
MAX_SPEED_KN = 50.0
MAX_SCREWS = 8
YEAR_LOW, YEAR_HIGH = 1850, 1950

FREEBOARD_INDEXES = (18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29)
DISPLACEMENT_INDEXES = (13, 127, 15, 17)

# The recovered two-group layout reading this module maps into the concept
# section. The fractions are saved as percentages and the four heights follow the
# hull display scale selector, exactly as the freeboard page reads them; the two
# group-2 height flags are the recovered doubled-elevation/depression boxes.
LAYOUT_FORECASTLE_FRACTION_INDEX = 26
LAYOUT_FORWARD_DECK_FRACTION_INDEX = 23
LAYOUT_DECK_HEIGHTS = (("forward_fore_m", 27), ("forward_aft_m", 25),
                       ("aft_fore_m", 24), ("aft_aft_m", 22))
LAYOUT_DOUBLE_ELEVATION_INDEX = fields.SUPER_SUPER_BASE
LAYOUT_DOUBLE_DEPRESSION_INDEX = fields.SUB_SUB_BASE
# The recovered layout table this project accepts is 0..17; the source's own
# eighteenth entry is its "not set" selection, which is archived rather than
# mapped as a layout.
LAYOUT_SELECTOR_LIMIT = 17
# The layout domain, mirrored from the layout kernel: bounded paired counts and a
# bounded converted deck height. A bank outside it keeps its rows and its archive.
MAX_LAYOUT_MOUNTS = 1000
MAX_LAYOUT_BARRELS = 10000
MAX_LAYOUT_FREEBOARD_M = 100.0

# name, thickness index, length index, height index, canonical role
ARMOUR_ZONES = (
    ("belt_main", 80, 81, 82, "belt_main"),
    ("belt_ends", 83, 84, 85, "belt_ends"),
    ("belt_upper", 86, 87, 88, "belt_upper"),
    ("bulkhead", 89, 90, 91, "bulkhead"),
    ("bulge", 202, 203, 204, "armour_bulge"),
    ("deck", 107, None, None, "armour_deck"),
    ("conning", 108, None, None, "conning"),
)

# Every saved fixed region this importer maps into its own declaration. A region
# the source declares at all gets its **own** independent unknown-mass target, its
# own record and its own balance role; a region the source leaves blank gets no
# target and no record, because an empty saved region is not a declared zero
# armour. A region the source deliberately fills with a zero **is** declared, and
# it keeps that declared zero.
#
# The role vocabulary and the bounds below are the fixed-armour kernel's own, so
# an imported declaration is always inside the domain its kernel accepts.
FIXED_ARMOUR_ZONES = ("belt_main", "belt_ends", "belt_upper", "bulkhead", "bulge", "deck",
                      "conning")
FIXED_ARMOUR_SYSTEM = "armour.fixed.%s"
FIXED_ARMOUR_ROLE = dict(fixed_armour_kernel.ROLE_BY_KIND)
FIXED_ARMOUR_LABELS = {
    "belt_main": "Main belt", "belt_ends": "Ends belt", "belt_upper": "Upper belt",
    "bulkhead": "Torpedo bulkhead", "bulge": "Bulge", "deck": "Armour deck",
    "conning": "Conning towers",
}
# The armour deck's own saved inputs. ``deckFCBox``/``deckQDBox`` are the
# forecastle and quarter-deck plate thicknesses: the source stores them as
# separate plates, and this importer keeps them separate instead of merging them
# into one central thickness. 209 is the recovered seven-entry coverage selector
# index. The two segment lengths are the same saved percentages the freeboard
# page reads (position 26 forecastle, position 20 quarter-deck), converted to
# fractions of the waterline length.
DECK_FORECASTLE_THICKNESS_INDEX = 207
DECK_QUARTERDECK_THICKNESS_INDEX = 208
DECK_COVERAGE_INDEX = 209
CONNING_AFT_THICKNESS_INDEX = 210
DECK_FORECASTLE_FRACTION_INDEX = 26
DECK_QUARTERDECK_FRACTION_INDEX = 20
# Bounded mirrors of the fixed-armour domain: an out-of-domain saved value is
# archived with its own diagnostic and leaves its canonical field unknown, so an
# imported declaration is always inside the domain its kernel accepts.
MAX_FIXED_ARMOUR_THICKNESS_MM = fixed_armour_kernel.MAX_THICKNESS_MM
MAX_FIXED_ARMOUR_EXTENT_M = fixed_armour_kernel.MAX_EXTENT_M
MAX_FIXED_ARMOUR_HEIGHT_M = fixed_armour_kernel.MAX_HEIGHT_M
DECK_COVERAGE_SELECTORS = fixed_armour_kernel.DECK_SELECTOR_COUNT

# The five saved auxiliary weapon rows. Each weapon keeps its **own** scale
# selector, exactly as MainForm.cs:488-502 assigns them: the first torpedo row
# shares position 9 with the gun scales, and every other row has its own.
#
# The registry's legacy names at 190..197 call these rows deck_gun1/deck_gun2.
# MainForm.cs:728-735 shows they are weaponsControl.dcControl1/dcControl2, the two
# depth charge groups. The registry names are the archive's own and are kept
# verbatim; the alias is recorded here rather than rewritten in place.
AUXILIARY_ROWS = (
    # kind, id suffix, scale, count, loads, size, length, location
    ("torpedo", "torpedo1", 9, 77, 179, 79, 182, 184),
    ("torpedo", "torpedo2", 136, 78, 180, 181, 183, 185),
    ("mine", "mine1", 137, 186, 187, 188, None, 189),
    ("depth_charge", "depth_charge1", 138, 190, 192, 194, None, 196),
    ("depth_charge", "depth_charge2", 139, 191, 193, 195, None, 197),
)
AUXILIARY_SYSTEM = "weapons.auxiliary.%s"
AUXILIARY_LABELS = {
    "torpedo": "Torpedo tubes", "mine": "Mines",
    "depth_charge": "Depth charges",
}
AUXILIARY_LEGACY_ALIAS = (
    "the saved registry names deck_gun1/deck_gun2 at positions 190..197 are the two depth "
    "charge groups (MainForm.cs:728-735 weaponsControl.dcControl1/dcControl2); the archive "
    "keeps the registry names verbatim and this declaration records the depth charge "
    "reading they actually carry")
# Bounded mirrors of the auxiliary domain, so an imported declaration is always
# inside the domain its kernel accepts.
MAX_AUXILIARY_COUNT = 1000000
MAX_AUXILIARY_DIAMETER_MM = 2000.0
MAX_AUXILIARY_LENGTH_M = 100.0
MAX_AUXILIARY_UNIT_MASS_KG = 100000.0
AUXILIARY_LOCATIONS = 9
ENGINE_LABELS = ("Simple reciprocating", "Complex reciprocating", "Steam turbines")

MISC_LABELS = {
    "misc.vital": "Miscellaneous weight below water",
    "misc.hull": "Miscellaneous weight in the hull above water",
    "misc.deck": "Miscellaneous weight on the freeboard deck",
    "misc.above": "Miscellaneous weight above the freeboard deck",
    "misc.void": "Miscellaneous void weight",
}


def _bank_of(identifier):
    """``bank3`` is the third recovered bank, i.e. per-bank index 2."""
    try:
        return int(identifier.removeprefix("bank")) - 1
    except (AttributeError, ValueError):                # pragma: no cover - internal only
        return 0


def _fact(value):
    """Return an imported declaration fact with unknown estimate provenance."""
    return {"value": value, "source": DECLARATION_SOURCE, "estimate": None}


def _item(item_id, label, mass_t=None, role=None):
    record = {
        "id": item_id, "label": label, "mass_t": mass_t,
        "x_m": None, "y_m": None, "kg_m": None,
        "source": DECLARATION_SOURCE, "estimate": None,
    }
    if role is not None:
        record["role"] = role
    return record


def _leaf(facts, weight_item_ids, page_rows=None):
    leaf = {"source": DECLARATION_SOURCE, "estimate": None,
            "weight_item_ids": list(weight_item_ids), "facts": facts}
    if page_rows:
        leaf["page_rows"] = page_rows
    return leaf


class Projection:
    """Build the canonical draft and the per-field mapping record together."""

    def __init__(self, values, diagnostics, fallback_name):
        self.values = values
        self.diagnostics = diagnostics
        self.fallback_name = fallback_name
        self.dispositions = [
            ["preserved", [], "archived only; no canonical destination"]
            for _ in range(fields.FIELD_COUNT)
        ]
        self._bulged_beam_m = None
        self._hull = {}
        self._blank_selectors = set()
        # Filled transactionally by armour(), before any weight group or concept
        # section is built, so a record and its target are always created together.
        self._fixed_armour = []
        self._auxiliary = []
        self._auxiliary_items = []
        self._auxiliary_leaves = {}

    # ------------------------------------------------------------- records --

    def note(self, index, disposition, destinations=(), reason=""):
        # Source-only details have no canonical object. Their raw record is
        # evidence, not an active mapping or an invented archive destination.
        if disposition == "mapped" and destinations and all(
            path.startswith(("$.migration.mapping.banks.", "$.migration.mapping.armour."))
            for path in destinations
        ):
            disposition = "preserved"
            destinations = [f"$.migration.raw_fields[{index}]"]
            reason = "Source parameter archived without a canonical destination; " + reason
        entry = self.dispositions[index]
        entry[0] = disposition
        entry[1] = list(dict.fromkeys(([] if disposition == "preserved" else entry[1]) + list(destinations)))
        entry[2] = reason

    def mapped(self, index, destination, reason):
        self.note(index, "mapped", [destination], reason)

    def warn(self, code, path, message, **extra):
        item = {"code": code, "severity": "warning", "path": path,
                "message": message, "blocking": False}
        item.update(extra)
        self.diagnostics.append(item)

    # ----------------------------------------------------------- accessors --

    def text(self, index):
        return self.values.raw[index].strip()

    def number(self, index):
        value = self.values.values[index]
        return None if isinstance(value, bool) else value

    def whole(self, index):
        value = self.number(index)
        if value is None or not float(value).is_integer():
            return None
        return int(value)

    def flag(self, index):
        value = self.values.values[index]
        return None if value is None else bool(value)

    def label(self, index, labels, path):
        """Return the recovered label of a saved combo selection, or ``None``."""
        value = self.whole(index)
        if value is None:
            return None
        if not 0 <= value < len(labels):
            self.warn("sship.enum.unsupported", path,
                      f"saved selection {value} is outside the recovered list of "
                      f"{len(labels)} entries; it is archived and left unknown",
                      index=index, line=index + 2)
            return None
        return labels[value]

    # ---------------------------------------------------------- unit reads --

    def _hull_scale(self):
        return self.whole(fields.HULL_SCALE_INDEX)

    def _armour_scale(self):
        return self.whole(fields.ARMOUR_SCALE_INDEX)

    def _gun_scale(self, bank):
        return self.whole(fields.GUN_SCALE_BASE + bank)

    def _imperial(self, selector):
        return selector == 0

    def _require_selector(self, selector, position, group, path):
        """A blank scale selector is unknown, never an implicit imperial unit."""
        if selector is None and position not in self._blank_selectors:
            self._blank_selectors.add(position)
            self.warn("sship.scale.selector_unknown", path,
                      f"the {group} scale selector is blank, so its declared values have "
                      f"no unit; they are archived and every unit-dependent canonical "
                      f"target stays unknown", index=position, line=position + 2)

    def length_m(self, index, path, reason, selector=None):
        value = self.number(index)
        if value is None:
            return None
        if selector is None:
            selector = self._hull_scale()
            self._require_selector(selector, fields.HULL_SCALE_INDEX, "hull", path)
        if selector is None:
            return None
        metres = units.convert(value, "ft" if self._imperial(selector) else "m", "m")
        self.mapped(index, path, reason)
        return metres

    def armour_extent_m(self, index, path):
        """Armour extents are saved in feet and follow the **armour** scale selector.

        ``ArmourControl.cs`` reads every belt, bulkhead and bulge length, height
        and beam with ``fpCheck(value, Con.feet2metres, scale.SelectedIndex)``,
        where ``scale`` is the armour thickness selector saved at position 10 --
        the same selector, and the same ``in``/``mm`` wording, that governs the
        plate thicknesses. It is deliberately *not* the hull scale selector.
        """
        value = self.number(index)
        if value is None:
            return None
        selector = self._armour_scale()
        self._require_selector(selector, fields.ARMOUR_SCALE_INDEX, "armour", path)
        if selector is None:
            return None
        metres = units.convert(value, "ft" if self._imperial(selector) else "m", "m")
        self.mapped(index, path,
                    "declared foot extent converted with the armour scale selector saved "
                    "at position 10")
        return metres

    def thickness_m(self, index, path, reason):
        value = self.number(index)
        if value is None:
            return None
        selector = self._armour_scale()
        self._require_selector(selector, fields.ARMOUR_SCALE_INDEX, "armour", path)
        if selector is None:
            return None
        metres = _thickness_m(value, selector)
        self.mapped(index, path, reason)
        return metres

    def bounded(self, index, path, *, low=None, high=None, positive=False,
                integer=False, reason=""):
        """Map a declared value only when it is inside the supported domain."""
        value = self.number(index)
        if value is None:
            return None
        if integer and not float(value).is_integer():
            self.warn("sship.value.out_of_domain", path,
                      "the declared value is not a whole number; it is archived and left "
                      "unknown", index=index, line=index + 2)
            return None
        declared = int(value) if integer else float(value)
        if positive and declared <= 0:
            self.warn("sship.value.zero_not_positive", path,
                      "the declared value is not positive; it stays unknown and is not "
                      "treated as a supplied input", index=index, line=index + 2)
            return None
        if (low is not None and declared < low) or (high is not None and declared > high):
            self.warn("sship.value.out_of_domain", path,
                      f"the declared value {declared} is outside the supported range; it "
                      f"is archived and left unknown", index=index, line=index + 2)
            return None
        self.mapped(index, path, reason)
        return declared

    def mass_lt(self, index, item_id):
        """A declared miscellaneous weight: always long tons, whatever the scale."""
        value = self.number(index)
        self.note(index, "mapped", [f"$.weight_groups.misc.items.{item_id}.mass_t"],
                  "declared in long tons whatever the saved display scale; converted "
                  "with 1 long ton = 1.0160469088 t")
        return None if value is None else units.convert(value, LONG_TON, "t")

    # ------------------------------------------------------------ identity --

    def name(self):
        declared = self.text(0)
        if declared:
            self.mapped(0, "$.name", "ship name declared in the source file")
            return declared
        self.note(0, "mapped", ["$.name"],
                  "the source name is blank; the filename stem is used and this "
                  "substitution is recorded here")
        self.warn("sship.name.fallback", "$.name",
                  f"the source ship name is blank; the filename stem "
                  f"{self.fallback_name!r} is used as the project name")
        return self.fallback_name

    def metadata(self):
        facts = {}
        for index, key in ((1, "country"), (2, "type")):
            value = self.text(index)
            if value:
                facts[key] = _fact(value)
                self.mapped(index, f"$.metadata.{key}", "sourced identification text")
        hull_year = self.bounded(11, "$.metadata.design_year", low=YEAR_LOW,
                                 high=YEAR_HIGH, integer=True,
                                 reason="CCYY hull year inside the supported domain")
        facts["design_year"] = _fact(hull_year)
        engine_year = self.bounded(128, "$.metadata.engine_built_year", low=YEAR_LOW,
                                   high=YEAR_HIGH, integer=True,
                                   reason="CCYY engine year inside the supported domain")
        facts["engine_built_year"] = _fact(engine_year)
        return facts or None

    def hull(self):
        self._hull = {
            "lwl_m": self.length_m(13, "$.hull.lwl_m",
                                   "waterline length in the declared hull display unit"),
            "beam_m": self.length_m(14, "$.hull.beam_m",
                                    "moulded beam in the declared hull display unit"),
            "draught_normal_m": self.length_m(15, "$.hull.draught_normal_m",
                                              "normal draught in the declared hull "
                                              "display unit"),
            "block_coeff": self.bounded(17, "$.hull.block_coeff", low=0.0, high=1.0,
                                        reason="normal block coefficient inside [0, 1]"),
        }
        # The beam at the bulges is not a canonical hull key. It is archived with
        # its own provenance and used only for the source's derived displacement.
        self._bulged_beam_m = self.length_m(
            127, "$.migration.derived.beam_at_bulges_m",
            "beam at the bulges, archived for the source displacement formula only")
        return dict(self._hull)

    # ------------------------------------------------------------ derived ---

    def derived(self):
        long_tons = tonnes = None
        if (all(value is not None for value in self._hull.values())
                and self._bulged_beam_m is not None):
            length_ft = units.convert(self._hull["lwl_m"], "m", "ft")
            draught_ft = units.convert(self._hull["draught_normal_m"], "m", "ft")
            bulged_ft = units.convert(self._bulged_beam_m, "m", "ft")
            long_tons = (length_ft * bulged_ft * draught_ft
                         * self._hull["block_coeff"] / 35.0)
            if long_tons > 0.0:
                tonnes = units.convert(long_tons, LONG_TON, "t")
            else:
                self.warn("sship.derived.displacement_unknown", "$.migration.derived",
                          "the declared hull inputs give a non-positive derived normal "
                          "displacement; it is archived and never turned into a positive "
                          "target")
                long_tons = None
        elif self._bulged_beam_m is None and self._hull["lwl_m"] is not None:
            self.warn("sship.derived.bulged_beam_required", "$.migration.derived",
                      "the source normal displacement needs the beam at the bulges "
                      "(field 127); it is never replaced by the moulded beam, so no "
                      "displacement reference is derived")
        segments, inputs = self._freeboard_profile()
        representative = None if segments is None else sum(
            segment * fractions for segment, fractions in zip(segments, (
                inputs["length_fractions"][key] for key in ("fc", "fd", "ad", "qd"))))
        return {
            "beam_at_bulges_m": {
                "value": self._bulged_beam_m,
                "formula": "beam at the bulges in the declared hull display unit",
                "source_fields": [127],
                "note": "not a canonical hull key and never substituted for the moulded "
                        "beam",
            },
            "normal_displacement_long_tons": {
                "value": long_tons, "formula": DISPLACEMENT_FORMULA,
                "source_fields": list(DISPLACEMENT_INDEXES),
                "note": "the source program's own derived normal displacement; the file "
                        "stores no displacement, and this is never a ledger mass or a "
                        "measured displacement",
            },
            "normal_displacement_t": {
                "value": tonnes,
                "formula": DISPLACEMENT_FORMULA
                           + "; converted with 1 long ton = 1.0160469088 t",
                "source_fields": list(DISPLACEMENT_INDEXES),
            },
            "representative_freeboard_m": {
                "value": representative,
                "formula": FREEBOARD_FORMULA,
                "source_fields": list(FREEBOARD_INDEXES),
                "inputs": inputs or {},
            },
            "freeboard_forecastle_m": self._segment(segments, 0),
            "freeboard_flat_deck_m": self._segment(segments, 1),
            "freeboard_afterdeck_m": self._segment(segments, 2),
            "freeboard_quarterdeck_m": self._segment(segments, 3),
        }

    def _segment(self, segments, position):
        return {"value": None if segments is None else segments[position],
                "formula": FREEBOARD_FORMULA,
                "source_fields": list(FREEBOARD_INDEXES)}

    def _freeboard_profile(self):
        """The four recovered freeboard segments and the source length fractions.

        ``FreeboardControl.cs`` reads every profile height with
        ``fpCheck(value, Con.feet2metres, hull.scale.SelectedIndex)``, so the
        heights follow the hull scale selector; the four segments are then
        combined exactly as the recovered program combines them and weighted by
        the saved segment length percentages.
        """
        destination = "$.migration.derived.representative_freeboard_m"
        heights = {}
        for key, index in (("fc_aft", 28), ("fc_fore", 29), ("fd_aft", 25),
                           ("fd_fore", 27), ("ad_aft", 22), ("ad_fore", 24),
                           ("qd_aft", 18), ("qd_fore", 21)):
            metres = self.length_m(index, destination,
                                   "source freeboard height in the hull display unit")
            heights[key] = metres
        declared = {"fc": self.number(26), "fd": self.number(23), "qd": self.number(20)}
        if any(value is None for value in list(heights.values()) + list(declared.values())):
            self._archive_freeboard_heights()
            self.warn("sship.derived.freeboard_profile", "$.migration.derived",
                      "the source freeboard profile is incomplete, so no representative "
                      "freeboard is derived and no deck geometry is created")
            return None, None
        fractions = {key: value / 100.0 for key, value in declared.items()}
        fractions["ad"] = 1.0 - fractions["fc"] - fractions["fd"] - fractions["qd"]
        if any(value < 0.0 for value in fractions.values()):
            self._archive_freeboard_heights()
            self.warn("sship.derived.freeboard_profile", "$.migration.derived",
                      "the declared freeboard segment lengths do not form a valid "
                      "profile, so no representative freeboard is derived")
            return None, None
        segments = (
            0.6 * heights["fc_aft"] + 0.4 * heights["fc_fore"],
            0.5 * heights["fd_aft"] + 0.5 * heights["fd_fore"],
            0.5 * heights["ad_aft"] + 0.5 * heights["ad_fore"],
            0.5 * heights["qd_aft"] + 0.5 * heights["qd_fore"],
        )
        for index in (26, 23, 20):
            self.mapped(index, destination,
                        "declared freeboard segment length percentage")
        return segments, {"length_fractions": fractions, "declared_percent": declared,
                          "heights_m": heights}

    def _archive_freeboard_heights(self):
        for index in (28, 29, 25, 27, 22, 24, 18, 21):
            self.note(index, "preserved", [f"$.migration.raw_fields[{index}]"],
                      "incomplete freeboard profile; height archived without a derived value")

    # -------------------------------------------------------------- banks ---

    def _indexes(self, bank):
        """Every recovered position of one bank, addressed by recovered meaning."""
        return {
            "barrels": fields.BARRELS_BASE + 6 * bank,
            "calibre": fields.CALIBRE_BASE + 6 * bank,
            "gun_type": fields.GUN_TYPE_BASE + 6 * bank,
            "shell_weight": fields.SHELL_WEIGHT_BASE + 6 * bank,
            "magazine": fields.MAGAZINE_INDEXES[bank],
            "mounts": fields.MOUNTS_BASE + 3 * bank,
            "mount_type": fields.MOUNT_TYPE_BASE + 3 * bank,
            "layout_g1": fields.LAYOUT_G1_BASE + 3 * bank,
            "layout_g2": fields.LAYOUT_G2_BASE + bank,
            "year": fields.GUN_YEAR_BASE + bank,
            "barrel_length": fields.BARREL_LENGTH_BASE + bank,
            "armour": (fields.ARM_FACE_BASE + 3 * bank, fields.ARM_BACK_BASE + 3 * bank,
                       fields.ARM_BOTTOM_BASE + 3 * bank),
            "super_g1": fields.SUPER_MOUNTS_G1 + bank,
            "sub_g1": fields.SUB_MOUNTS_G1 + bank,
            "super_g2": fields.SUPER_MOUNTS_G2 + bank,
            "deck_g2": fields.DECK_MOUNTS_G2 + bank,
            "sub_g2": fields.SUB_MOUNTS_G2 + bank,
            "per_mount_g1": fields.BARRELS_PER_MOUNT_G1 + bank,
            "per_mount_g2": fields.BARRELS_PER_MOUNT_G2 + bank,
            "shadowed": (fields.SUPER_MOUNTS_G1_EARLY[bank],
                         fields.SUB_MOUNTS_G1_EARLY[bank],
                         fields.SUPER_MOUNTS_G2_EARLY[bank],
                         fields.DECK_MOUNTS_G2_EARLY[bank],
                         fields.SUB_MOUNTS_G2_EARLY[bank]),
            "earlier": (fields.SUPER_MOUNTS_G1_EARLY[bank],
                        fields.SUB_MOUNTS_G1_EARLY[bank]),
        }

    def banks(self):
        records = {}
        for bank in range(fields.BANK_COUNT):
            index = self._indexes(bank)
            identifier = f"bank{bank + 1}"
            calibre_in = self.number(index["calibre"])
            calibre_mm = None
            if calibre_in is not None:
                selector = self._gun_scale(bank)
                path = f"$.systems.weapons.{identifier}.facts.calibre_m"
                self._require_selector(selector, fields.GUN_SCALE_BASE + bank,
                                       f"gun bank {bank + 1}", path)
                if selector is not None:
                    calibre_mm = _calibre_mm(calibre_in, selector)
                    if calibre_mm <= 0:
                        calibre_mm = None
                        self.warn("sship.value.zero_not_positive", path,
                                  "zero calibre is archived; the canonical positive calibre remains unknown",
                                  index=index["calibre"], line=index["calibre"] + 2)
                    else:
                        self.mapped(index["calibre"], path,
                                    "calibre converted with this bank's own scale selector")
            gun_label = self.label(index["gun_type"], fields.GUN_TYPES,
                                   f"$.systems.weapons.{identifier}.facts.weapon_type")
            mount_label = self.label(index["mount_type"], fields.MOUNT_TYPES,
                                     f"$.systems.weapons.{identifier}"
                                     f".facts.mount_description")
            if gun_label is not None:
                self.mapped(index["gun_type"],
                            f"$.systems.weapons.{identifier}.facts.weapon_type",
                            "saved gun type selection mapped to the supported vocabulary")
            if mount_label is not None:
                self.mapped(index["mount_type"],
                            f"$.systems.weapons.{identifier}.facts.mount_description",
                            "saved mount type selection mapped to the supported "
                            "vocabulary")
            shell_lb = self.number(index["shell_weight"])
            if shell_lb is not None:
                self.mapped(index["shell_weight"],
                            f"$.systems.weapons.{identifier}.facts.projectile_mass_kg",
                            "shell weight is always saved in pounds and is converted to "
                            "kilograms whatever the saved calibre scale")
            rounds = self.number(index["magazine"])
            if rounds is not None and float(rounds).is_integer():
                self.mapped(index["magazine"],
                            f"$.systems.weapons.{identifier}.facts.rounds_per_gun",
                            "declared magazine rounds for one gun")
            elif rounds is not None:
                self.warn("sship.value.out_of_domain",
                          f"$.systems.weapons.{identifier}.facts.rounds_per_gun",
                          "fractional rounds are archived; no whole-number ammunition count is inferred",
                          index=index["magazine"], line=index["magazine"] + 2)
            barrel_length = self.number(index["barrel_length"])
            if barrel_length is not None:
                self.note(index["barrel_length"], "preserved", [],
                          "barrel length in calibres has no canonical metre key; it is "
                          "archived and used by the concept estimate")
            mounts = self.number(index["mounts"])
            if mounts is not None:
                self.mapped(index["mounts"],
                            f"$.migration.mapping.banks.{identifier}.mounts",
                            "total number of mounts declared for this bank")
            barrels = self.number(index["barrels"])
            if barrels is not None:
                self.mapped(index["barrels"],
                            f"$.migration.mapping.banks.{identifier}.barrels",
                            "total installed barrels declared for this bank")
            records[identifier] = {
                "identifier": identifier,
                "barrels_index": index["barrels"],
                "mounts_index": index["mounts"],
                "calibre_mm": calibre_mm,
                "gun_type": kernels.GUN_TYPES[fields.GUN_TYPES.index(gun_label)]
                if gun_label else None,
                "mount_type": kernels.MOUNT_TYPES[fields.MOUNT_TYPES.index(mount_label)]
                if mount_label else None,
                "gun_label": gun_label,
                "mount_label": mount_label,
                "placement": self._placement(bank, identifier),
                "shell_kg": None if shell_lb is None else shell_lb * POUND_KG,
                "rounds": rounds,
                "barrel_calibres": barrel_length,
                "year": self.number(index["year"]),
                "mounts": mounts,
                "barrels": barrels,
                "rotating_armour_m": self._rotating_armour(bank, identifier),
                "counts": self._counts(bank, identifier, index),
            }
        return records

    def _placement(self, bank, identifier):
        index = self._indexes(bank)
        first = self.label(index["layout_g1"], fields.LAYOUT_LABELS,
                           f"$.systems.weapons.{identifier}.facts.placement")
        second = self.label(index["layout_g2"], fields.LAYOUT_LABELS,
                            f"$.systems.weapons.{identifier}.facts.placement")
        for selector in (index["layout_g1"], index["layout_g2"]):
            if self.whole(selector) is not None:
                self.mapped(selector, f"$.systems.weapons.{identifier}.facts.placement",
                            "saved layout selection kept as descriptive text; it is not "
                            "an installed-count or eligibility claim")
        if first and second and first != second:
            return f"{first} / group 2: {second}"
        return first or second

    def _rotating_armour(self, bank, identifier):
        """The declared turret plate, using the first plate the source supplies."""
        face, rear, bottom = self._indexes(bank)["armour"]
        path = (f"$.systems.armour.fixed.rotating_armour.{identifier}.facts"
                f".thickness_m")
        for index in (face, rear, bottom):
            metres = self.thickness_m(index, path,
                                      "declared turret plate thickness in the armour "
                                      "display unit")
            if metres is None:
                continue
            if index != face:
                self.warn("sship.armour.turret_plates_archived",
                          f"$.systems.armour.fixed.rotating_armour.{identifier}",
                          "the source stores several turret plates per bank; only the "
                          "first declared plate becomes a fact and the others stay "
                          "archived", index=index, line=index + 2)
            return metres
        return None

    def _counts(self, bank, identifier, index):
        """Recovered group-1/group-2 mount arithmetic for one bank.

        The 211..235 block is the value a sequential reader keeps; the earlier
        copy of each count is never read and is never a fallback.
        """
        result = {"groups": [], "count_unknown": False, "count_inconsistent": False,
                 "barrels_inconsistent": False}
        shadowed = index["shadowed"]
        finals = (("super_g1", index["super_g1"]), ("sub_g1", index["sub_g1"]),
                  ("super_g2", index["super_g2"]), ("deck_g2", index["deck_g2"]),
                  ("sub_g2", index["sub_g2"]))
        values = dict((name, self.number(position)) for name, position in finals)
        for earlier, (name, position) in zip(shadowed, finals):
            earlier_value = self.number(earlier)
            self.note(earlier, "duplicate", [],
                      f"the writer stores this mount count twice; position {position} "
                      f"comes later and is the value a sequential reader keeps")
            if earlier_value is not None and earlier_value != values[name]:
                self.warn("sship.duplicate.value_conflict", f"$.fields[{earlier}]",
                          f"the earlier saved occurrence {earlier_value} disagrees with "
                          f"the later occurrence {values[name]}; only the later one is "
                          f"read", index=earlier, line=earlier + 2)
        mounts = self.number(index["mounts"])
        for name, position in finals:
            if values[name] is not None:
                self.mapped(position,
                            f"$.migration.mapping.banks.{identifier}.{name}",
                            "the later of the two saved occurrences of this mount count")
        if mounts is None or any(value is None for value in values.values()):
            result["count_unknown"] = True
            return result
        if (mounts < 0 or not float(mounts).is_integer()
                or any(value < 0 or not float(value).is_integer() for value in values.values())):
            result["count_inconsistent"] = True
            return result
        group_two = values["super_g2"] + values["deck_g2"] + values["sub_g2"]
        if abs(group_two - round(group_two)) > 1e-9 or group_two > mounts:
            result["count_inconsistent"] = True
            return result
        group_one = mounts - group_two
        if values["super_g1"] + values["sub_g1"] > group_one:
            result["count_inconsistent"] = True
            return result
        # GunControl.cs:578 derives group 1's deck mounts as the whole mount count
        # minus the other five declared slot counts, so it is computed here rather
        # than read from a position the source never saves.
        deck_one = group_one - values["super_g1"] - values["sub_g1"]
        for name, count, selector in (("g1", group_one, index["per_mount_g1"]),
                                      ("g2", group_two, index["per_mount_g2"])):
            layout_path = (f"$.concept_design.battery_layouts.{identifier}-layout"
                           f".group{2 if name == 'g2' else 1}")
            barrels, cradle, recovered_index = self._per_mount(
                selector, f"$.migration.mapping.banks.{identifier}.{name}.barrels_per_mount")
            self.note(selector, "mapped", [layout_path + ".mount_selector"],
                      "index into the recovered gunsInMount table, mapped as this group's "
                      "own recovered mount selector")
            result["groups"].append({"group": name, "count": int(count),
                                     "barrels_per_mount": barrels,
                                     "shared_cradle": cradle,
                                     "selector": recovered_index,
                                     "layout": self._layout_selector(
                                         index["layout_g1"] if name == "g1"
                                         else index["layout_g2"],
                                         layout_path + ".layout_index"),
                                     "elevated": int(values["super_g1"] if name == "g1"
                                                     else values["super_g2"]),
                                     "deck": int(deck_one if name == "g1"
                                                 else values["deck_g2"]),
                                     "depressed": int(values["sub_g1"] if name == "g1"
                                                      else values["sub_g2"])})
        if any(group["count"] > 0 and group["barrels_per_mount"] is None
               for group in result["groups"]):
            result["count_unknown"] = True
            return result
        # Position 31+6*bank is the bank's total installed gun barrels, not its
        # mount count and not one mount's barrel count. It must agree with both
        # mount groups before any concept model may be enabled.
        declared_barrels = self.number(index["barrels"])
        installed = sum(group["count"] * group["barrels_per_mount"]
                        for group in result["groups"] if group["count"] > 0)
        if declared_barrels is not None:
            if abs(declared_barrels - installed) > 1e-9:
                result["barrels_inconsistent"] = True
                self.warn("sship.battery.barrels_inconsistent",
                          f"$.migration.mapping.banks.{identifier}",
                          f"the declared total of {declared_barrels} installed barrels "
                          f"disagrees with the {installed} barrels implied by the two "
                          f"mount groups; the bank's facts and archive are preserved but "
                          f"no concept model is enabled for it",
                          index=index["barrels"], line=index["barrels"] + 2)
        return result

    def _per_mount(self, index, path):
        value = self.whole(index)
        if value is None:
            return None, None, None
        if not 0 <= value < len(fields.PER_MOUNT_BARRELS):
            self.warn("sship.enum.unsupported", path,
                      f"saved per-mount selection {value} is outside the recovered table "
                      f"of {len(fields.PER_MOUNT_BARRELS)} entries",
                      index=index, line=index + 2)
            return None, None, None
        self.mapped(index, path, "index into the recovered per-mount barrels table")
        return fields.PER_MOUNT_BARRELS[value], value in fields.SHARED_CRADLE_INDICES, value

    def _layout_selector(self, index, path):
        """The recovered layout selection of one group, or ``None`` when unset.

        The recovered table is 0..17. The source's own eighteenth entry is its
        "not set" selection: it is archived with its warning and mapped as
        unknown, never inferred as layout 0.
        """
        value = self.whole(index)
        if value is None:
            return None
        if not 0 <= value <= LAYOUT_SELECTOR_LIMIT:
            self.warn("sship.enum.unsupported", path,
                      f"saved layout selection {value} is outside the recovered table of "
                      f"0..{LAYOUT_SELECTOR_LIMIT} layouts, or is the program's own unset "
                      f"entry; it is archived and the layout stays unknown",
                      index=index, line=index + 2)
            return None
        self.mapped(index, path, "index into the recovered layout table")
        return value

    # ------------------------------------------------------------- armour ---

    def _fixed_armour_record(self, name, thickness, length, height, zones):
        """One saved fixed region's own target, record and archive facts.

        The target is created **independently and always with an unknown mass**:
        the import never adopts, computes or assumes a single armour ton. A
        declaration is created only when the source actually declares that
        region, and every value it carries is bounded before it is mapped, so an
        out-of-domain saved number is archived with a diagnostic and its
        canonical field simply stays unknown instead of producing a project the
        concept model would refuse.
        """
        facts = {"zone": _fact(FIXED_ARMOUR_ROLE[name])}
        declared = {"id": f"sship_{name}", "kind": name,
                    "system_id": FIXED_ARMOUR_SYSTEM % name,
                    "item_id": FIXED_ARMOUR_SYSTEM % name, "source": DECLARATION_SOURCE}
        known = False
        metres = self.thickness_m(
            thickness, f"$.systems.armour.fixed.{name}.facts.thickness_m",
            "armour thickness in the declared armour display unit")
        if metres is not None:
            facts["thickness_m"] = _fact(metres)
            value = self._bounded_armour_mm(metres * 1000.0, thickness, name, "thickness_mm",
                                            MAX_FIXED_ARMOUR_THICKNESS_MM)
            if value is not None:
                declared["thickness_mm"] = value
                known = True
        for key, position in (("length_m", length), ("height_m", height)):
            if position is None:
                continue
            metres = self.armour_extent_m(position, f"$.systems.armour.fixed.{name}.facts.{key}")
            if metres is None:
                continue
            if metres > 0.0:
                facts[key] = _fact(metres)
            high = (MAX_FIXED_ARMOUR_EXTENT_M if key == "length_m"
                    else MAX_FIXED_ARMOUR_HEIGHT_M)
            value = self._bounded_armour_m(metres, position, name, key, high)
            if value is not None:
                declared[key] = value
                known = True
        if name == "deck":
            known = self._deck_record(declared, facts, known) or known
        elif name == "conning":
            known = self._conning_record(declared, known) or known
        zones[name] = facts
        if not known:
            # A region the source leaves entirely blank is not a declared zero
            # armour, so it gets no target and no record at all.
            return None
        return declared

    def _bounded_armour_mm(self, millimetres, index, name, field, high):
        return self._bounded_armour(millimetres, index, name, field, high, "mm")

    def _bounded_armour_m(self, metres, index, name, field, high):
        return self._bounded_armour(metres, index, name, field, high, "m")

    def _bounded_armour(self, value, index, name, field, high, unit):
        """Map a converted saved number only when it is inside the declared domain."""
        if not math.isfinite(value) or value < 0.0 or value > high:
            self.warn("sship.armour.value_out_of_domain",
                      f"$.concept_design.fixed_armour.sship_{name}.{field}",
                      f"the saved {name} {field} of {value:g} {unit} is outside the supported "
                      f"0..{high:g} {unit} domain; it is archived and the canonical field stays "
                      f"unknown rather than being clamped",
                      index=index, line=index + 2)
            return None
        return value

    def _deck_record(self, declared, facts, known):
        """The deck's own saved plates, coverage selector and segment fractions."""
        layers = []
        for field, position, label in (("forecastle_mm", DECK_FORECASTLE_THICKNESS_INDEX,
                                        "deckFCBox"),
                                       ("quarterdeck_mm", DECK_QUARTERDECK_THICKNESS_INDEX,
                                        "deckQDBox")):
            metres = self.thickness_m(position, "$.systems.armour.fixed.deck.facts.deck_layer",
                                      "armour thickness in the declared armour display unit")
            if metres is None:
                continue
            layers.append(label)
            value = self._bounded_armour_mm(metres * 1000.0, position, "deck", field,
                                            MAX_FIXED_ARMOUR_THICKNESS_MM)
            if value is not None:
                declared[field] = value
                known = True
        if layers:
            facts["deck_layer"] = _fact("; ".join(layers))
            self.note(DECK_FORECASTLE_THICKNESS_INDEX, "mapped",
                      ["$.concept_design.fixed_armour.sship_deck.forecastle_mm"],
                      "declared forecastle deck plate; the plate is its own canonical layer "
                      "and is never merged into the central deck thickness")
            self.note(DECK_QUARTERDECK_THICKNESS_INDEX, "mapped",
                      ["$.concept_design.fixed_armour.sship_deck.quarterdeck_mm"],
                      "declared quarter-deck plate; the plate is its own canonical layer and is "
                      "never merged into the central deck thickness")
        selector = self.whole(DECK_COVERAGE_INDEX)
        if selector is not None:
            if 0 <= selector < DECK_COVERAGE_SELECTORS:
                # The recovered seven-way switch is an index, not an area. Mapping
                # the index never claims a covered plan area here; that reading
                # belongs to the fixed-armour kernel.
                declared["coverage_index"] = selector
                self.mapped(DECK_COVERAGE_INDEX,
                            "$.concept_design.fixed_armour.sship_deck.coverage_index",
                            "index into the recovered seven-entry deck coverage table")
                known = True
            else:
                self.warn("sship.armour.coverage_unsupported",
                          "$.concept_design.fixed_armour.sship_deck.coverage_index",
                          f"the saved deck coverage selection {selector} is outside the recovered "
                          f"table of {DECK_COVERAGE_SELECTORS} entries; it is archived and the "
                          f"deck coverage stays unknown rather than being inferred",
                          index=DECK_COVERAGE_INDEX, line=DECK_COVERAGE_INDEX + 2)
                self.note(DECK_COVERAGE_INDEX, "preserved",
                          [f"$.migration.raw_fields[{DECK_COVERAGE_INDEX}]"],
                          "saved deck coverage selection outside the recovered table")
        for field, position in (("forecastle_fraction", DECK_FORECASTLE_FRACTION_INDEX),
                            ("quarterdeck_fraction", DECK_QUARTERDECK_FRACTION_INDEX)):
            percentage = self.number(position)
            if percentage is None:
                continue
            if not math.isfinite(float(percentage)) or not 0.0 <= float(percentage) <= 100.0:
                self.note(position, "preserved", [f"$.migration.raw_fields[{position}]"],
                          "the saved deck segment length percentage is outside 0..100; the "
                          "canonical deck fraction stays unknown")
                continue
            declared[field] = float(percentage) / 100.0
            self.mapped(position, f"$.concept_design.fixed_armour.sship_deck.{field}",
                        "declared freeboard segment length percentage, converted to a fraction "
                        "of the waterline length")
            known = True
        known_fractions = [declared[key] for key in ("forecastle_fraction",
                                                     "quarterdeck_fraction")
                           if key in declared]
        if len(known_fractions) == 2 and sum(known_fractions) > 1.0:
            self.warn("sship.armour.deck_fraction_domain",
                      "$.concept_design.fixed_armour.sship_deck",
                      "the saved forecastle and quarter-deck percentages together exceed the "
                      "waterline length; both canonical fractions are left unknown rather than "
                      "reconciled or clamped",
                      index=DECK_FORECASTLE_FRACTION_INDEX, line=DECK_FORECASTLE_FRACTION_INDEX + 2)
            declared.pop("forecastle_fraction", None)
            declared.pop("quarterdeck_fraction", None)
        return known

    def _conning_record(self, declared, known):
        """The conning tower's own saved aft plate, beside its saved fore plate."""
        metres = self.thickness_m(CONNING_AFT_THICKNESS_INDEX,
                                  "$.concept_design.fixed_armour.sship_conning.aft_mm",
                                  "armour thickness in the declared armour display unit")
        if metres is None:
            return known
        value = self._bounded_armour_mm(metres * 1000.0, CONNING_AFT_THICKNESS_INDEX,
                                        "conning", "aft_mm", MAX_FIXED_ARMOUR_THICKNESS_MM)
        if value is None:
            return known
        declared["aft_mm"] = value
        return True

    def armour(self):
        zones = {}
        records = []
        for name, thickness, length, height, _role in ARMOUR_ZONES:
            record = self._fixed_armour_record(name, thickness, length, height, zones)
            if record is not None:
                records.append(record)
        self._fixed_armour = records
        inclination = self.number(201)
        if inclination is not None:
            zones["belt_main"]["inclination_deg"] = _fact(float(inclination))
            self.mapped(201, "$.systems.armour.fixed.belt_main.facts.inclination_deg",
                        "declared belt inclination")
        if self.whole(205) is not None:
            self.note(205, "preserved", [],
                      "the saved bulkhead type selection is archived; it has no canonical "
                      "structural equivalent")
        if self.number(206) is not None:
            self.mapped(206, "$.migration.mapping.armour.bulkhead_beam_m",
                        "declared bulkhead beam, archived for optional balance assumptions "
                        "a user may add")
        return zones

    # ------------------------------------------------------ auxiliary weapons --

    def _auxiliary_scaled(self, value_index, scale_index, path, label, name, field,
                          imperial, metric, high):
        """One saved auxiliary fact in canonical units, on that row's own scale.

        The recovered page gives every weapon its own unit selector, so a torpedo
        diameter saved in inches is never read through the mine row's scale. A
        blank, unsupported or out-of-domain selector leaves the canonical field
        unknown with its own diagnostic; nothing is clamped or defaulted.
        """
        value = self.number(value_index)
        if value is None:
            return None
        selector = self.whole(scale_index)
        self._require_selector(selector, scale_index, label, path)
        if selector is None:
            return None
        if selector == 0:
            converted = float(value) * imperial
            reason = ("saved %s in the declared imperial unit, converted with this row's "
                      "own scale selector" % (field,))
        elif selector == 1:
            converted = float(value)
            reason = ("saved %s already in the declared metric unit, read with this row's "
                      "own scale selector" % (field,))
        else:
            self.warn("sship.auxiliary.scale_unsupported", path,
                      f"the saved {label} unit selection {selector} is outside the recovered "
                      f"imperial/metric pair; the canonical {name} {field} stays unknown "
                      f"rather than being read in an assumed unit",
                      index=scale_index, line=scale_index + 2)
            return None
        if not math.isfinite(converted) or converted < 0.0 or converted > high:
            self.warn("sship.auxiliary.value_out_of_domain", path,
                      f"the saved {name} {field} of {converted:g} is outside the supported "
                      f"0..{high:g} domain; it is archived and the canonical field stays "
                      f"unknown", index=value_index, line=value_index + 2)
            return None
        self.mapped(value_index, path, reason)
        return converted

    def _auxiliary_count(self, value_index, path, name, field):
        value = self.number(value_index)
        if value is None:
            return None
        if not float(value).is_integer() or not 0 <= float(value) <= MAX_AUXILIARY_COUNT:
            self.warn("sship.auxiliary.value_out_of_domain", path,
                      f"the saved {name} {field} of {value!r} is not a whole count inside the "
                      f"supported 0..{MAX_AUXILIARY_COUNT} domain; it is archived and the "
                      f"canonical field stays unknown",
                      index=value_index, line=value_index + 2)
            return None
        self.mapped(value_index, path, "saved whole count of this auxiliary weapon row")
        return int(float(value))

    def _auxiliary_location(self, value_index, path, name):
        value = self.whole(value_index)
        if value is None:
            return None
        limit = 9 if name == 'torpedo' else 4
        if not 0 <= value < limit:
            self.warn("sship.auxiliary.location_unsupported", path,
                      f"the saved {name} location selection {value} is outside the recovered "
                      f"0..{limit - 1} table; it is archived and the canonical "
                      f"location stays unknown", index=value_index, line=value_index + 2)
            self.note(value_index, "preserved", [f"$.migration.raw_fields[{value_index}]"],
                      "saved location selection outside the recovered table")
            return None
        self.mapped(value_index, path, "index into the recovered location table")
        return value

    def auxiliary_weapons(self):
        """The five saved auxiliary rows: their own target, record and archive facts.

        A row the source leaves entirely blank, or leaves at a known zero, is
        omitted: an empty saved row is not a declared weapon and a deliberate zero
        is an ordinary empty row. Every other row gets its **own** independent
        unknown-mass target and its own declaration, created together here so no
        declaration can ever reference a target that does not exist. No auxiliary
        mass is computed, adopted or deducted by the import.
        """
        records, items, leaves = [], [], {}
        for kind, suffix, scale, count, loads, size, length, location in AUXILIARY_ROWS:
            path = "$.concept_design.auxiliary_weapons.sship_%s" % (suffix,)
            record = {"id": "sship_%s" % (suffix,), "kind": kind,
                      "system_id": AUXILIARY_SYSTEM % suffix,
                      "item_id": AUXILIARY_SYSTEM % suffix, "source": DECLARATION_SOURCE}
            record["count"] = self._auxiliary_count(count, path + ".count", kind, "count")
            record["loads"] = self._auxiliary_count(loads, path + ".loads", kind, "loads")
            record["location_index"] = self._auxiliary_location(location,
                                                                path + ".location_index",
                                                                kind)
            if kind == "torpedo":
                record["diameter_mm"] = self._auxiliary_scaled(
                    size, scale, path + ".diameter_mm", "torpedo", kind, "diameter",
                    INCH_MM, 1.0, MAX_AUXILIARY_DIAMETER_MM)
                record["length_m"] = self._auxiliary_scaled(
                    length, scale, path + ".length_m", "torpedo", kind, "length",
                    FT_M, 1.0, MAX_AUXILIARY_LENGTH_M)
            else:
                record["unit_mass_kg"] = self._auxiliary_scaled(
                    size, scale, path + ".unit_mass_kg", kind, kind, "unit mass",
                    POUND_KG, 1.0, MAX_AUXILIARY_UNIT_MASS_KG)
            declared = [value for value in record.values()
                        if isinstance(value, (int, float)) and value != 0]
            if not declared:
                # Nothing declared, or an ordinary all-zero row: no target and no
                # declaration, because neither is a declared auxiliary weapon. The
                # row itself stays archived exactly where it was.
                for index in (count, loads, size, location):
                    if index is not None:
                        self.note(index, "preserved", [f"$.migration.raw_fields[{index}]"],
                                  "saved auxiliary row is empty or an ordinary all-zero row; "
                                  "no target, no declaration and no mass are created")
                if length is not None:
                    self.note(length, "preserved", [f"$.migration.raw_fields[{length}]"],
                              "saved auxiliary row is empty or an ordinary all-zero row; no "
                              "target, no declaration and no mass are created")
                continue
            if kind == "depth_charge":
                record["source"] = "%s; %s" % (DECLARATION_SOURCE, AUXILIARY_LEGACY_ALIAS)
            records.append(record)
            items.append(_item(record["item_id"], AUXILIARY_LABELS[kind], None,
                               auxiliary_kernel.TARGET_ROLE))
            # The archive keeps the registry's own row name; the alias, not a
            # rewrite, is what tells a reader what the row really carries.
            leaves[record["system_id"]] = {
                "weapon_type": _fact(kind),
                "mount_description": _fact(
                    "%s; %s" % (suffix, AUXILIARY_LEGACY_ALIAS) if kind == "depth_charge"
                    else suffix)}
        self._auxiliary = records
        self._auxiliary_items = items
        self._auxiliary_leaves = leaves
        return records

    # --------------------------------------------------------- propulsion ---

    def propulsion(self):
        path = "$.systems.propulsion.machinery.facts"
        fuel = dict(zip(fields.FUEL_LABELS, (self.flag(index) for index in
                                             (114, 115, 116, 117, 118))))
        drive = dict(zip(fields.DRIVE_LABELS, (self.flag(index) for index in
                                               (122, 123, 124, 125))))
        engine = dict(zip(ENGINE_LABELS, (self.flag(index) for index in (119, 120, 121))))
        for name, index in zip(fields.FUEL_LABELS, (114, 115, 116, 117, 118)):
            if fuel[name] is not None:
                self.mapped(index, f"{path}.energy_source",
                            "saved fuel checkbox selection kept as descriptive text")
        for name, index in zip(fields.DRIVE_LABELS, (122, 123, 124, 125)):
            if drive[name] is not None:
                self.mapped(index, f"{path}.transmission",
                            "saved drive checkbox selection kept as descriptive text")
        for name, index in zip(ENGINE_LABELS, (119, 120, 121)):
            if engine[name] is not None:
                self.mapped(index, "$.concept_design.machinery.kind",
                            "saved engine checkbox selection mapped to the supported steam "
                            "vocabulary")
        kinds = [token for token, name in zip(kernels.ENGINE_KINDS, ENGINE_LABELS)
                 if engine[name]]
        shafts = self.bounded(112, f"{path}.shafts", low=1, high=MAX_SCREWS, integer=True,
                              reason="declared shaft count")
        speeds = {}
        for position, key in ((109, "max_speed_kn"), (110, "cruise_speed_kn")):
            speeds[key] = self.bounded(position, f"{path}.{key}", positive=True,
                                        high=MAX_SPEED_KN,
                                        reason="declared speed in knots")
        year = self.bounded(128, f"{path}.engine_built_year", low=YEAR_LOW, high=YEAR_HIGH,
                            integer=True, reason="CCYY engine year")
        coal = self.number(113)
        fuel_labels = [label for label, value in fuel.items() if value]
        drive_labels = [label for label, value in drive.items() if value]
        description = None
        if kinds:
            description = ("Steam turbine" if "turbine" in kinds else
                           ("Compound reciprocating steam engine" if "compound" in kinds
                            else "Simple reciprocating steam engine"))
        else:
            self.warn("sship.propulsion.engine_unspecified", f"{path}.engine_description",
                      "no supported steam engine kind is selected in the source")
        facts = {
            "shafts": _fact(shafts),
            "max_speed_kn": _fact(speeds["max_speed_kn"]),
            "cruise_speed_kn": _fact(speeds["cruise_speed_kn"]),
            "boilers": _fact(None),
            "design_power_kw": _fact(None),
            "trial_power_kw": _fact(None),
            "engine_description": _fact(description),
            "transmission": _fact("; ".join(drive_labels) or None),
            "energy_source": _fact("; ".join(fuel_labels) or None),
            "engine_built_year": _fact(year),
        }
        self.warn("sship.propulsion.power_unknown", f"{path}.design_power_kw",
                  "the source program derives shaft power from speed; no declared shaft "
                  "power is migrated, so both power facts stay unknown")
        unsupported = []
        if any(fuel[label] for label in ("Diesel motors", "Petrol motors", "Batteries")):
            unsupported.append("a non-coal/oil fuel is selected")
        if not any(fuel[label] for label in ("Coal fired boilers", "Oil fired boilers")):
            unsupported.append("no coal or oil fuel is selected")
        if len(kinds) != 1:
            unsupported.append("exactly one supported steam engine kind must be selected")
        return facts, unsupported, kinds[0] if kinds else None, coal

    # ----------------------------------------------------------- the draft --

    def weight_groups(self, banks):
        misc = []
        for position, item_id, role in zip(fields.MISC_WEIGHT_INDEXES,
                                           fields.MISC_WEIGHT_IDS,
                                           fields.MISC_WEIGHT_ROLES):
            misc.append(_item(item_id, MISC_LABELS[item_id],
                              self.mass_lt(position, item_id), role))
        misc.append(_item("misc.unknown",
                          "Structure and remaining weight (unknown)", None, "structure"))
        self.warn("sship.ledger.incomplete", "$.weight_groups.misc",
                  "the five declared miscellaneous weights are not a complete weight "
                  "ledger: structure, armament, machinery, fuel and the remaining items "
                  "are unknown, so no displacement balance, centre of gravity or ballast "
                  "condition is implied")
        weapon_items = []
        for record in banks.values():
            for group in record["counts"]["groups"]:
                if group["count"] <= 0:
                    continue
                prefix = f"weapons.{record['identifier']}.{group['group']}"
                weapon_items.extend((
                    _item(f"{prefix}.guns",
                          f"{record['identifier']} group {group['group']} bare guns",
                          None, "guns"),
                    _item(f"{prefix}.mounts",
                          f"{record['identifier']} group {group['group']} mounts",
                          None, "mounts"),
                    _item(f"{prefix}.ammunition",
                          f"{record['identifier']} group {group['group']} ammunition",
                          None, "ammunition"),
                ))
        groups = [{"id": "misc", "label": "Imported miscellaneous and unknown remainder",
                   "required": False, "items": misc}]
        if self._fixed_armour:
            # One independent unknown-mass target per declared fixed region. The
            # import never adopts or computes a single armour ton: every one of
            # these items stays unknown until a reader runs the region and adopts
            # the estimate explicitly.
            groups.append({"id": "armour",
                           "label": "Imported fixed armour (masses unadopted)",
                           "required": False,
                           "items": [_item(record["item_id"],
                                           FIXED_ARMOUR_LABELS[record["kind"]],
                                           None, FIXED_ARMOUR_ROLE[record["kind"]])
                                     for record in self._fixed_armour]})
        if weapon_items:
            groups.append({"id": "weapons",
                           "label": "Imported batteries (masses unadopted)",
                           "required": False, "items": weapon_items})
        if self._auxiliary_items:
            groups.append({"id": "auxiliary",
                           "label": "Imported auxiliary weapons (masses unadopted)",
                           "required": False, "items": list(self._auxiliary_items)})
        groups.append({"id": "propulsion",
                       "label": "Imported propulsion (masses unadopted)",
                       "required": False,
                       "items": [_item("propulsion.machinery", "Machinery and boilers",
                                       None, "machinery"),
                                 _item("propulsion.fuel", "Fuel and bunkers", None, "fuel")]})
        return groups

    def weapon_systems(self, banks):
        leaves = {}
        for record in banks.values():
            identifier = record["identifier"]
            facts = {}
            if record["calibre_mm"] is not None:
                facts["calibre_m"] = _fact(record["calibre_mm"] / 1000.0)
            if record["gun_type"] is not None:
                facts["weapon_type"] = _fact(record["gun_type"])
            if record["mount_type"] is not None:
                facts["mount_description"] = _fact(record["mount_type"])
            if record["placement"] is not None:
                facts["placement"] = _fact(record["placement"])
            if record["mounts"] is not None and float(record["mounts"]).is_integer():
                count = record["mounts"]
                facts["mount_count"] = _fact(int(count) if float(count).is_integer()
                                             else count)
                self.mapped(record["mounts_index"],
                            f"$.systems.weapons.{identifier}.facts.mount_count",
                            "total mounts declared for this bank")
            if record["rounds"] is not None and float(record["rounds"]).is_integer():
                facts["rounds_per_gun"] = _fact(
                    int(record["rounds"]) if float(record["rounds"]).is_integer()
                    else record["rounds"])
            if record["shell_kg"] is not None:
                facts["projectile_mass_kg"] = _fact(record["shell_kg"])
            item_ids, rows = [], []
            for group in record["counts"]["groups"]:
                if group["count"] <= 0:
                    continue
                prefix = f"weapons.{identifier}.{group['group']}"
                for role, label in (("guns", "bare guns"), ("mounts", "mounts"),
                                    ("ammunition", "ammunition")):
                    item_id = f"{prefix}.{role}"
                    item_ids.append(item_id)
                    rows.append({"row": f"{role}_{group['group']}", "group": group["group"],
                                 "weight_item_ids": [item_id], "source": DECLARATION_SOURCE,
                                 "estimate": None})
            leaves[identifier] = _leaf(facts, item_ids, rows)
            if record["barrels"] is not None and float(record["barrels"]).is_integer():
                leaves[identifier]["installed_guns"] = int(record["barrels"])
                self.mapped(record["barrels_index"],
                            f"$.systems.weapons.{identifier}.installed_guns",
                            "total installed barrels declared for this bank, independent of model eligibility")
        # Each declared auxiliary row keeps its own systems leaf and its own
        # unknown-mass target, created together with its declaration. The leaf is
        # addressed under systems.weapons, so its identifier is the item ID itself.
        for identifier, facts in self._auxiliary_leaves.items():
            leaves[identifier.removeprefix("weapons.")] = _leaf(facts, [identifier])
        return leaves

    def armour_systems(self, banks, zones):
        targets = {record["item_id"] for record in self._fixed_armour}
        leaves = {}
        for name, facts in zones.items():
            item_id = FIXED_ARMOUR_SYSTEM % name
            leaves[name] = _leaf(facts, [item_id] if item_id in targets else [])
        rotating = {}
        for record in banks.values():
            if record["rotating_armour_m"] is None:
                continue
            rotating[record["identifier"]] = _leaf(
                {"thickness_m": _fact(record["rotating_armour_m"]),
                 "zone": _fact("rotating_armour")}, [])
        if rotating:
            leaves["rotating_armour"] = rotating
        return leaves

    def propulsion_systems(self, facts):
        return {
            "machinery": _leaf(facts, ["propulsion.machinery"]),
            "fuel": _leaf({}, ["propulsion.fuel"]),
        }

    # --------------------------------------------------------- the concept --

    def batteries(self, banks):
        records = []
        for record in banks.values():
            identifier = record["identifier"]
            counts = record["counts"]
            if counts["count_unknown"]:
                self.warn("sship.battery.count_unknown",
                          f"$.migration.mapping.banks.{identifier}",
                          "a mount count of the authoritative later block is unknown, so "
                          "no group total is invented and no concept model is enabled for "
                          "this bank")
                continue
            if counts["count_inconsistent"]:
                self.warn("sship.battery.count_inconsistent",
                          f"$.migration.mapping.banks.{identifier}",
                          "the declared mount total and the group-1/group-2 mount counts "
                          "disagree, so the bank stays a preserved draft and no concept "
                          "model is enabled for it")
                continue
            if counts["barrels_inconsistent"]:
                continue
            for group in self._active_groups(counts["groups"]):
                prefix = f"weapons.{identifier}.{group['group']}"
                problems = self._battery_problems(record, group)
                if problems:
                    self.warn("sship.concept.battery_unsupported",
                              f"$.concept_design.batteries.{identifier}.{group['group']}",
                              "; ".join(problems) + "; the bank's editable facts and its "
                              "archive are preserved but its concept estimate is omitted")
                    continue
                records.append({
                    "id": f"{identifier}-{group['group']}",
                    "system_id": f"weapons.{identifier}",
                    "guns_item_id": f"{prefix}.guns",
                    "mounts_item_id": f"{prefix}.mounts",
                    "ammunition_item_id": f"{prefix}.ammunition",
                    "calibre_mm": record["calibre_mm"],
                    "barrel_calibres": float(record["barrel_calibres"]),
                    "year": int(record["year"]),
                    "gun_type": record["gun_type"],
                    "mount_type": record["mount_type"],
                    "mount_count": group["count"],
                    "barrels_per_mount": group["barrels_per_mount"],
                    "shared_cradle": group["shared_cradle"],
                    "rounds_per_gun": int(record["rounds"]),
                    "shell_mass_kg": record["shell_kg"],
                    "broadside_guns": None,
                })
        return records

    def _active_groups(self, groups):
        """Keep the saved mount groups exactly as the source declares them.

        The two groups are the original's own two-group layout identity: they
        carry their own recovered selector, their own layout reading and their own
        elevated/deck/depressed split. Two groups that happen to read alike are
        therefore still two groups, with two weight targets and two layout slots;
        merging them would lose the identity the layout model needs.
        """
        return [group for group in groups if group["count"] > 0]

    def battery_layouts(self, banks, batteries):
        """One canonical layout per bank whose group facts support one.

        A layout is only created when every field it needs is known: both groups'
        mount counts, recovered selectors and layout readings, and the deck
        profile. A bank whose saved facts cannot support that stays a preserved
        draft with a diagnostic, and no layout ever references a battery row that
        was not imported.
        """
        layouts = []
        by_id = {battery["id"]: battery for battery in batteries}
        for record in banks.values():
            identifier = record["identifier"]
            path = "$.concept_design.battery_layouts"
            counts = record["counts"]
            groups = counts["groups"]
            if not any(group["count"] > 0 for group in groups):
                # An ordinary empty saved bank has no layout identity at all, so no
                # unconfigured layout and no pending-armour warning is created.
                continue
            if counts["count_unknown"] or counts["count_inconsistent"] \
                    or counts["barrels_inconsistent"]:
                self.warn("sship.layout.draft", path,
                          f"the saved group counts of {identifier} are unknown or "
                          f"inconsistent, so no two-group layout is mapped for this bank; its "
                          f"facts and archive are preserved",
                          index=record["mounts_index"], line=record["mounts_index"] + 2)
                continue
            missing = []
            for group in groups:
                if group["count"] == 0:
                    continue
                battery = by_id.get(f"{identifier}-{group['group']}")
                if battery is None:
                    missing.append(f"{group['group']} has no imported battery row")
                if group["selector"] is None:
                    missing.append(f"the {group['group']} per-mount selection is unknown")
                if group["layout"] is None:
                    missing.append(f"the {group['group']} layout selection is unknown")
            profile = self._layout_deck_profile(identifier)
            if profile is None:
                missing.append("the saved freeboard profile is incomplete")
            else:
                missing.extend(self._layout_domain(groups, profile, identifier))
            if missing:
                self.warn("sship.layout.draft", path,
                          f"the saved file does not support a two-group layout for "
                          f"{identifier}: " + "; ".join(missing)
                          + "; the bank's facts and archive are preserved and no layout is "
                            "created", index=record["barrels_index"],
                          line=record["barrels_index"] + 2)
                continue
            layout = {
                "id": f"{identifier}-layout",
                "source": DECLARATION_SOURCE,
                "group1": None, "group2": None,
                "group2_double_elevation": self.flag(
                    LAYOUT_DOUBLE_ELEVATION_INDEX + _bank_of(identifier)),
                "group2_double_depression": self.flag(
                    LAYOUT_DOUBLE_DEPRESSION_INDEX + _bank_of(identifier)),
                "deck_profile": profile,
                "armour": None,
            }
            for name, group in (("group1", groups[0]), ("group2", groups[1])):
                layout[name] = {
                    "battery_id": f"{identifier}-{group['group']}",
                    "mount_selector": group["selector"],
                    "layout_index": group["layout"],
                    "elevated_mounts": group["elevated"],
                    "deck_mounts": group["deck"],
                    "depressed_mounts": group["depressed"],
                } if group["count"] > 0 else None
            self.warn("sship.layout.armour_pending",
                      f"$.concept_design.battery_layouts.{layout['id']}.armour",
                      "the source declares the group's turret plates as exact archived facts "
                      "but never enables the layout's complete two-group armour estimate; the "
                      "layout armour stays null until a reader chooses an independent target "
                      "and thicknesses in the normal form, and no armour mass is added or "
                      "adopted by the import")
            layouts.append(layout)
        return layouts

    def _layout_domain(self, groups, profile, identifier):
        """The bounds the layout domain adds on top of each battery row's own.

        Two rows can each be inside their own domain while the layout they form
        together is not: the paired mount count, the paired barrel count and the
        converted deck heights are all bounded on the pair. Such a bank keeps its
        rows, its facts and its archive; only the layout stays a draft.
        """
        problems = []
        mounts = sum(group["count"] for group in groups)
        barrels = sum(group["count"] * (group["barrels_per_mount"] or 0) for group in groups)
        if mounts > MAX_LAYOUT_MOUNTS:
            problems.append(f"the two saved groups declare {mounts} mounts, above the "
                            f"supported {MAX_LAYOUT_MOUNTS} for one layout")
        if barrels > MAX_LAYOUT_BARRELS:
            problems.append(f"the two saved groups declare {barrels} barrels, above the "
                            f"supported {MAX_LAYOUT_BARRELS} for one layout")
        for field, index in LAYOUT_DECK_HEIGHTS:
            if profile[field] > MAX_LAYOUT_FREEBOARD_M:
                problems.append(f"the saved {field} of {profile[field]:.3f} m is above the "
                                f"supported {MAX_LAYOUT_FREEBOARD_M:g} m deck height")
                self.note(index, "preserved", [f"$.migration.raw_fields[{index}]"],
                          "the converted deck height is outside the layout deck domain")
        return problems

    def _layout_deck_profile(self, identifier):
        """The six saved deck fields, converted to the canonical metre reading.

        The two segment lengths are saved as percentages and the source reads them
        as ordinary floating-point values, so a fractional percentage such as
        35.5 is a valid declaration; only a non-finite or out-of-range value is
        archived and leaves the profile unknown.
        """
        fractions = {}
        for field, index in (("forecastle_fraction", LAYOUT_FORECASTLE_FRACTION_INDEX),
                             ("forward_deck_fraction", LAYOUT_FORWARD_DECK_FRACTION_INDEX)):
            declared = self.number(index)
            if declared is None or not math.isfinite(float(declared)) \
                    or not 0.0 <= float(declared) <= 100.0:
                self.note(index, "preserved", [f"$.migration.raw_fields[{index}]"],
                          "the saved freeboard segment length percentage is unusable; the "
                          "deck profile stays unknown")
                return None
            fractions[field] = float(declared) / 100.0
            self.mapped(index, f"$.concept_design.battery_layouts.{identifier}-layout"
                               f".deck_profile.{field}",
                        "declared freeboard segment length percentage, converted to a "
                        "fraction of the waterline length")
        if fractions["forecastle_fraction"] + fractions["forward_deck_fraction"] > 1.0:
            self.note(LAYOUT_FORECASTLE_FRACTION_INDEX, "preserved", [],
                      "the saved forecastle and forward-deck percentages exceed the "
                      "waterline length; no deck profile is derived")
            return None
        profile = dict(fractions)
        for field, index in LAYOUT_DECK_HEIGHTS:
            metres = self.length_m(
                index, f"$.concept_design.battery_layouts.{identifier}-layout"
                       f".deck_profile.{field}",
                "saved freeboard height in the hull display unit, converted to metres")
            if metres is None:
                return None
            profile[field] = metres
        return profile

    def _battery_problems(self, record, group):
        problems = []
        calibre = record["calibre_mm"]
        if calibre is None:
            problems.append("the calibre is unknown")
        elif not 0.0 < calibre <= MAX_CALIBRE_MM:
            problems.append(f"the calibre {calibre} mm is outside the supported model range")
        length = record["barrel_calibres"]
        if length is None:
            problems.append("the barrel length in calibres is unknown")
        elif not 1.0 <= length <= MAX_BARREL_CALIBRES:
            problems.append("the barrel length in calibres is outside the supported range")
        year = record["year"]
        if year is None:
            problems.append("the battery year is unknown")
        elif not YEAR_LOW <= year <= YEAR_HIGH:
            problems.append(f"the battery year {year} is outside the supported range")
        if record["gun_type"] is None:
            problems.append("the gun type is unknown")
        if record["mount_type"] is None:
            problems.append("the mount type is unknown")
        barrels = group["barrels_per_mount"]
        if barrels is None:
            problems.append("the barrels per mount are unknown")
        elif group["shared_cradle"] and not 2 <= barrels <= 5:
            problems.append("a shared cradle requires 2..5 barrels per mount")
        rounds = record["rounds"]
        if rounds is None:
            problems.append("the rounds per gun are unknown")
        elif not 0 <= rounds <= MAX_ROUNDS_PER_GUN:
            problems.append("the rounds per gun are outside the supported range")
        elif not float(rounds).is_integer():
            problems.append("the rounds per gun are not a whole number")
        if record["shell_kg"] is not None and record["shell_kg"] <= 0:
            problems.append("the declared shell mass is outside the positive model domain")
        return problems

    def concept_design(self, banks, unsupported, kind, coal, derived):
        target = derived["normal_displacement_t"]["value"]
        batteries = self.batteries(banks)
        layouts = self.battery_layouts(banks, batteries)
        if target is None or target <= 0:
            if batteries or kind is not None or self._fixed_armour or self._auxiliary:
                self.warn("sship.concept.design_omitted", "$.concept_design",
                          "the source normal displacement is unknown, so no concept "
                          "design section is enabled; every mapped fact and every "
                          "unknown-mass fixed armour and auxiliary target stays editable "
                          "without a model")
            return None
        stern = self.label(16, fields.STERN_LABELS, "$.concept_design.stern")
        freeboard = derived["representative_freeboard_m"]["value"]
        config = {
            "schema": _CONCEPT_SCHEMA,
            "method": kernels.METHOD_VERSION,
            "source": DECLARATION_SOURCE,
            "estimate": True,
            "target_displacement_t": target,
            "hull_year": self.bounded(11, "$.concept_design.hull_year", low=YEAR_LOW,
                                      high=YEAR_HIGH, integer=True,
                                      reason="CCYY hull year inside the supported domain"),
            "freeboard_m": freeboard,
            "stern": kernels.STERN_TYPES[fields.STERN_LABELS.index(stern)]
            if stern else None,
            "screws": self.bounded(112, "$.concept_design.screws", low=1, high=MAX_SCREWS,
                                   integer=True, reason="declared shaft count"),
            "batteries": batteries,
            "battery_layouts": layouts,
            "balance": None,
        }
        if self._fixed_armour:
            # Each declared fixed region keeps its own independent unknown-mass
            # target. No cost section is ever created here: the empirical cost
            # reading stays off until a reader switches it on deliberately.
            config["fixed_armour"] = copy.deepcopy(self._fixed_armour)
            config['armour_review'] = {
                'source': DECLARATION_SOURCE,
                'belt_inclination_deg': self.bounded(
                    201, '$.concept_design.armour_review.belt_inclination_deg',
                    low=-89, high=89, reason='source inclination for dimensional warnings only'),
            }
            self.warn("sship.concept.fixed_armour_unadopted",
                      "$.concept_design.fixed_armour",
                      "the saved fixed armour regions are mapped as their own declarations and "
                      "their own unknown-mass targets; no armour mass is computed, adopted or "
                      "deducted from any other item by the import")
        if self._auxiliary:
            # Each declared auxiliary row keeps its own independent unknown-mass
            # target under the existing 'other' role. No cost section, balance
            # role or balance assumption is ever created here.
            config["auxiliary_weapons"] = copy.deepcopy(self._auxiliary)
            self.warn("sship.concept.auxiliary_unadopted",
                      "$.concept_design.auxiliary_weapons",
                      "the saved torpedo, mine and depth charge rows are mapped as their own "
                      "declarations and their own unknown-mass targets; no auxiliary mass is "
                      "computed, adopted or deducted by the import")
        if unsupported:
            self.warn("sship.concept.propulsion_unsupported", "$.concept_design.machinery",
                      "; ".join(unsupported) + "; no machinery or fuel estimate is enabled "
                      "and no diesel or other fuel is coerced into the steam domain")
            return config
        config["machinery"] = {
            "system_id": "propulsion.machinery", "item_id": "propulsion.machinery",
            "year": self.bounded(128, "$.concept_design.machinery.year", low=YEAR_LOW,
                                 high=YEAR_HIGH, integer=True, reason="CCYY engine year"),
            "kind": kind,
            "coal_pct": (None if coal is None
                         else float(coal) if 0.0 <= float(coal) <= 100.0 else None),
            "speed_kn": self.bounded(109, "$.concept_design.machinery.speed_kn",
                                     positive=True, high=MAX_SPEED_KN,
                                     reason="declared maximum speed in knots"),
            "shaft_power_kw": None,
        }
        if config["machinery"]["coal_pct"] is None and coal is not None:
            self.warn("sship.value.out_of_domain", "$.concept_design.machinery.coal_pct",
                      "the declared coal percentage is outside [0, 100]; it is archived "
                      "and left unknown", index=113, line=115)
        cruise = self.bounded(110, "$.concept_design.fuel.cruise_speed_kn", positive=True,
                              high=MAX_SPEED_KN, reason="declared cruise speed in knots")
        speed = config["machinery"]["speed_kn"]
        if cruise is not None and speed is not None and cruise > speed:
            self.warn("sship.value.out_of_domain",
                      "$.concept_design.fuel.cruise_speed_kn",
                      "the declared cruise speed exceeds the declared maximum speed; the "
                      "fuel section is left out rather than silently reordered",
                      index=110, line=112)
            cruise = None
        if cruise is None:
            return config
        config["fuel"] = {
            "system_id": "propulsion.fuel", "item_id": "propulsion.fuel",
            "range_nm": self.bounded(111, "$.concept_design.fuel.range_nm", positive=True,
                                     reason="declared range in nautical miles"),
            "cruise_speed_kn": cruise,
        }
        return config

    # --------------------------------------------------------------- build --

    def build(self):
        name = self.name()
        hull = self.hull()
        metadata = self.metadata()
        banks = self.banks()
        zones = self.armour()
        self.auxiliary_weapons()
        propulsion_facts, unsupported, kind, coal = self.propulsion()
        derived = self.derived()
        weight_groups = self.weight_groups(banks)
        return {
            "name": name,
            "hull": hull,
            "metadata": metadata,
            "systems": {
                "weapons": self.weapon_systems(banks),
                "armour": {"fixed": self.armour_systems(banks, zones)},
                "propulsion": self.propulsion_systems(propulsion_facts),
            },
            "weight_groups": weight_groups,
            "concept_design": self.concept_design(banks, unsupported, kind, coal, derived),
            "derived": derived,
            "mapping": {"scale_selectors": self._scale_selectors()},
        }

    def _scale_selectors(self):
        return {
            "hull": {"selector": self._hull_scale(), "units": ["ft", "m"]},
            "gun": [{"selector": self._gun_scale(bank), "units": ["in", "mm"]}
                    for bank in range(fields.BANK_COUNT)],
            "armour": {"selector": self._armour_scale(), "units": ["in", "mm"]},
            "per_mount_barrels_table": list(fields.PER_MOUNT_BARRELS),
            "shared_cradle_indices": sorted(fields.SHARED_CRADLE_INDICES),
        }


_CONCEPT_SCHEMA = "plimsoll-concept-design-1"


def project(values, diagnostics, *, fallback_name):
    """Return the projected draft parts and the per-field mapping record."""
    projection = Projection(values, diagnostics, fallback_name)
    return projection.build(), projection.dispositions
