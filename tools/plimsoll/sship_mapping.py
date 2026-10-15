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
"""

from __future__ import annotations

try:
    from . import concept_estimates as kernels
    from . import units
except ImportError:  # pragma: no cover - direct-module import convention
    import concept_estimates as kernels
    import units

try:
    from . import sship_fields as fields
except ImportError:  # pragma: no cover - direct-module import convention
    import sship_fields as fields


LONG_TON = "long_ton"

# The repository's shared unit table deliberately carries only the canonical
# display units, so the recovered in/mm and lb conversions are named here.
INCH_MM = 25.4
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
ENGINE_LABELS = ("Simple reciprocating", "Complex reciprocating", "Steam turbines")

MISC_LABELS = {
    "misc.vital": "Miscellaneous weight below water",
    "misc.hull": "Miscellaneous weight in the hull above water",
    "misc.deck": "Miscellaneous weight on the freeboard deck",
    "misc.above": "Miscellaneous weight above the freeboard deck",
    "misc.void": "Miscellaneous void weight",
}


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
        for name, count, selector in (("g1", group_one, index["per_mount_g1"]),
                                      ("g2", group_two, index["per_mount_g2"])):
            barrels, cradle = self._per_mount(
                selector, f"$.migration.mapping.banks.{identifier}.{name}.barrels_per_mount")
            result["groups"].append({"group": name, "count": int(count),
                                     "barrels_per_mount": barrels,
                                     "shared_cradle": cradle})
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
            return None, None
        if not 0 <= value < len(fields.PER_MOUNT_BARRELS):
            self.warn("sship.enum.unsupported", path,
                      f"saved per-mount selection {value} is outside the recovered table "
                      f"of {len(fields.PER_MOUNT_BARRELS)} entries",
                      index=index, line=index + 2)
            return None, None
        self.mapped(index, path, "index into the recovered per-mount barrels table")
        return fields.PER_MOUNT_BARRELS[value], value in fields.SHARED_CRADLE_INDICES

    # ------------------------------------------------------------- armour ---

    def armour(self):
        zones = {}
        for name, thickness, length, height, role in ARMOUR_ZONES:
            facts = {"zone": _fact(role)}
            metres = self.thickness_m(
                thickness, f"$.systems.armour.fixed.{name}.facts.thickness_m",
                "armour thickness in the declared armour display unit")
            if metres is not None:
                facts["thickness_m"] = _fact(metres)
            for key, position in (("length_m", length), ("height_m", height)):
                if position is None:
                    continue
                metres = self.armour_extent_m(
                    position, f"$.systems.armour.fixed.{name}.facts.{key}")
                if metres is not None and metres > 0.0:
                    facts[key] = _fact(metres)
            zones[name] = facts
        inclination = self.number(201)
        if inclination is not None:
            zones["belt_main"]["inclination_deg"] = _fact(float(inclination))
            self.mapped(201, "$.systems.armour.fixed.belt_main.facts.inclination_deg",
                        "declared belt inclination")
        layers = []
        for position, layer in ((207, "deckFCBox"), (208, "deckQDBox")):
            if self.number(position) is None:
                continue
            layers.append(layer)
            self.note(position, "mapped", ["$.migration.mapping.armour.deck_layers"],
                      "declared deck armour plate; the plates are archived as separate "
                      "layers rather than merged into one thickness")
        if layers:
            zones["deck"]["deck_layer"] = _fact("; ".join(layers))
        if self.whole(209) is not None:
            self.warn("sship.armour.coverage_archived", "$.migration.derived",
                      "the saved deck coverage selection is an archived enum; it is never "
                      "converted into a covered plan area", index=209, line=211)
        if self.whole(205) is not None:
            self.note(205, "preserved", [],
                      "the saved bulkhead type selection is archived; it has no canonical "
                      "structural equivalent")
        if self.number(206) is not None:
            self.mapped(206, "$.migration.mapping.armour.bulkhead_beam_m",
                        "declared bulkhead beam, archived for optional balance assumptions "
                        "a user may add")
        return zones

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
        if weapon_items:
            groups.append({"id": "weapons",
                           "label": "Imported batteries (masses unadopted)",
                           "required": False, "items": weapon_items})
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
        return leaves

    def armour_systems(self, banks, zones):
        leaves = {name: _leaf(facts, []) for name, facts in zones.items()}
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
            for group in self._merge(counts["groups"], identifier):
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

    def _merge(self, groups, identifier):
        """Keep a different barrels-per-mount or cradle meaning in its own bank."""
        active = [group for group in groups if group["count"] > 0]
        if len(active) < 2:
            return active
        first, second = active
        if (first["barrels_per_mount"] == second["barrels_per_mount"]
                and first["shared_cradle"] == second["shared_cradle"]):
            return [{"group": first["group"], "count": first["count"] + second["count"],
                     "barrels_per_mount": first["barrels_per_mount"],
                     "shared_cradle": first["shared_cradle"]}]
        self.warn("sship.battery.groups_split",
                  f"$.migration.mapping.banks.{identifier}",
                  "the two saved mount groups differ in barrels per mount or in "
                  "shared-cradle meaning, so they are kept as separate canonical "
                  "batteries instead of being averaged into one")
        return active

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
        if target is None or target <= 0:
            if batteries or kind is not None:
                self.warn("sship.concept.design_omitted", "$.concept_design",
                          "the source normal displacement is unknown, so no concept "
                          "design section is enabled; every mapped fact stays editable "
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
            "balance": None,
        }
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
