# -*- coding: utf-8 -*-
"""SpringSharp 3b3 兼容字段目录：222 个有效可编辑字段，按原设计 7 页分组。

来源（只读）：
- 位置/类型的权威注册表：``sship_fields``（本目录既有恢复产物，280 位置）；
- 页归属：``MainForm.cs:479-803`` ``openFileCalc`` 里每个位置被写进哪个控件；
- 选项文字：各控件 ``InitializeComponent`` 的 ``Items.AddRange`` 与
  ``WeaponControl`` 的 ``torpLocation`` / ``mineLocation`` / ``dcLocation``；
- 单位与尺度：``Con.inch2mm`` / ``Con.feet2metres`` / ``Con.pounds2kg`` 的使用点，
  以及 ``hull_scale`` 0=feet/1=metres、各页 scale 0=英制/1=公制。

有效可编辑字段 = ``sship_fields`` 位置 0..246 中，去掉 25 个被后写块覆盖的早期
影子项（``sship_fields.SHADOWED``）与 33 个 padding（``reserved_padding_*``）后剩下的
222 项。早期影子项在 ``parameters`` 里保留，但在这里不作为独立可编辑字段。

本模块只声明静态目录，不计算、不读写文件、不引入依赖。
"""
from __future__ import annotations

from typing import Any, Mapping

if __package__:
    from . import sship_fields as _registry
else:
    import sship_fields as _registry

CATALOG_SCHEMA = "plimsoll-sps3b3-field-catalog-1"

PAGE_ORDER = ("hull", "freeboard", "guns", "weapons", "armour", "engine", "performance")
PAGE_LABELS = {
    "hull": "Hull",
    "freeboard": "Freeboard",
    "guns": "Guns",
    "weapons": "Weapons",
    "armour": "Armour",
    "engine": "Machinery",
    "performance": "Performance",
}

# --- 源选项表（照抄原控件，不新造） ---------------------------------------
# 页面尺度选项只有正常 0/1 两态；原 HullControl 下拉的 2/3（全公制/全英制）
# 是一次性全局动作，不作为持久尺度值，单独在 controls 里暴露。
HULL_SCALE_CHOICES = ("feet", "metres")
GLOBAL_SCALE_CHOICES = ("all metric", "all imperial")
IMPERIAL_METRIC_CHOICES = ("in", "mm")
LENGTH_CHOICES = ("ft", "m")
WEIGHT_CHOICES = ("lb", "kg")
STERN_CHOICES = _registry.STERN_LABELS
BOW_CHOICES = ("Normal bow", "Bulbous bow - straight", "Bulbous bow - forward", "Ram Bow")
GUN_TYPE_CHOICES = _registry.GUN_TYPES
MOUNT_TYPE_CHOICES = _registry.MOUNT_TYPES
LAYOUT_CHOICES = _registry.LAYOUT_LABELS
PER_MOUNT_CHOICES = ('Single mount', '2 row twin mount', '4 row quad mount', 'Twin mount', '2-gun mount',
                     '2 row quad mount', 'Triple mount', '3-gun mount', '2 row sextuple mount', 'Quad mount',
                     '4-gun mount', '2 row octuple mount', 'Quintuple mount', '5-gun mount', '2 row decuple mount')
BULKHEAD_TYPE_CHOICES = ("Additional bulkheads", "Strengthened bulkheads")
DECK_COVERAGE_CHOICES = (
    "Armoured deck - multiple decks", "Armoured deck - single deck",
    "Protected deck - multiple decks", "Protected deck - single deck",
    "Box over machinery", "Box over magazines", "Box over machinery & magazines",
)
TORPEDO_LOCATION_CHOICES = (
    "deck mounted carriage/fixed tube", "deck mounted side rotating tube",
    "deck mounted centre rotating tube", "deck mounted reload",
    "submerged bow tube", "submerged stern tube",
    "submerged bow & stern tube", "submerged side tube", "below water reload",
)
MINE_LOCATION_CHOICES = (
    "Above water - Stern racks/rails", "Below water - bow tubes",
    "Below water - stern tubes", "Below water - side tubes",
)
DC_LOCATION_CHOICES = (
    "Stern depth charge racks", "Depth charge throwers",
    "Hedgehog style A/S mortars", "Squid style A/S mortars",
)
FUEL_CHOICES = _registry.FUEL_LABELS
ENGINE_KIND_CHOICES = ("Simple reciprocating", "Complex reciprocating", "Steam turbines")
DRIVE_CHOICES = _registry.DRIVE_LABELS

_AUTO_LABEL_OVERRIDES = {
    "ship_name": "Ship name",
    "ship_type": "Ship type",
    "length_waterline": "Length at waterline",
    "beam_moulded": "Beam (moulded)",
    "beam_at_bulges": "Beam at bulges",
    "draught_normal": "Draught (normal)",
    "block_coefficient_normal": "Block coefficient (normal)",
    "hull_scale": "Hull page units",
    "hull_year": "Hull year",
    "engine_year": "Machinery year",
    "misc_weight_vital": "Misc weight, vital (long tons)",
    "misc_weight_hull": "Misc weight, hull (long tons)",
    "misc_weight_deck": "Misc weight, deck (long tons)",
    "misc_weight_above": "Misc weight, above deck (long tons)",
    "misc_weight_void": "Misc weight, void (long tons)",
    "freeboard_ram_length": "Ram length",
    "trim": "Trim",
    "deck_gun1_count": "Depth charge thrower 1 count",
    "deck_gun2_count": "Depth charge thrower 2 count",
}


def _auto_label(name: str) -> str:
    explicit = _AUTO_LABEL_OVERRIDES.get(name)
    if explicit:
        return explicit
    words = name.replace("_", " ").split()
    out = []
    for word in words:
        if word in ("gun", "gun1", "gun2", "gun3", "gun4", "gun5") and out:
            out.append(word.capitalize())
        else:
            out.append(word.capitalize())
    text = " ".join(out)
    for token in (" Gun1", " Gun2", " Gun3", " Gun4", " Gun5"):
        text = text.replace(token, token.replace(" ", " "))
    return text


# --- 页归属（MainForm.openFileCalc） --------------------------------------
def _page_indices() -> dict:
    pages: dict[str, set] = {key: set() for key in PAGE_ORDER}
    pages["hull"].update({0, 1, 2, 3, 11, 13, 14, 15, 17, 127, 128})
    pages["freeboard"].update({16, 134, 135})
    pages["freeboard"].update(range(18, 31))
    pages["guns"].update(range(4, 9))
    pages["guns"].update(range(31, 61))
    pages["guns"].update(range(61, 77))
    pages["guns"].update(range(92, 107))
    pages["guns"].update(range(129, 134))
    pages["guns"].update(range(140, 145))
    pages["guns"].update(range(145, 149))
    pages["guns"].update(range(149, 179))
    pages["guns"].update(range(211, 246))
    pages["weapons"].update({9, 12, 77, 78, 79, 136, 137, 138, 139})
    pages["weapons"].update(range(179, 198))
    pages["weapons"].update({198, 199, 200, 246})
    pages["armour"].update({10, 107, 108})
    pages["armour"].update(range(80, 92))
    pages["armour"].update(range(201, 211))
    pages["engine"].update(range(109, 126))
    pages["performance"].update({126})
    return pages


def _specs() -> list:
    """(name, source_index, page, kind, unit, scale_ref, unit_choices,
    choices, allows_unselected, value_bounds) —— 每项一个可编辑字段。"""
    pages = _page_indices()
    specs = []
    gun_chars = "12345"

    def add(name, *, unit=None, scale_ref=None, unit_choices=None, choices=None,
            enum=False, integer=False, boolean=False, min_value=None,
            max_value=None, page=None):
        index = _registry.NAMES.index(name)
        specs.append({
            "name": name,
            "source_index": index,
            "page": page or _page_for(index, pages),
            "kind": _registry.KINDS[index],
            "unit": unit,
            "scale_ref": scale_ref,
            "unit_choices": list(unit_choices) if unit_choices else None,
            "choices": list(choices) if choices else None,
            "allows_unselected": bool(enum),
            "min_value": min_value,
            "max_value": max_value,
        })

    # --- hull page ---
    for name in ("ship_name", "country", "ship_type"):
        add(name, page="hull")
    add("hull_scale", page="hull", choices=HULL_SCALE_CHOICES)
    add("hull_year", page="hull", unit="year", integer=True, min_value=0)
    for name in ("length_waterline", "beam_moulded", "draught_normal", "beam_at_bulges"):
        add(name, page="hull", unit="ft", scale_ref="hull_scale",
            unit_choices=LENGTH_CHOICES)
    add("block_coefficient_normal", page="hull", unit=None)
    add("engine_year", page="hull", unit="year", integer=True, min_value=0)

    # --- freeboard page ---
    add("stern", page="freeboard", choices=STERN_CHOICES, enum=True)
    add("bow", page="freeboard", choices=BOW_CHOICES, enum=True)
    for name in ("freeboard_quarterdeck_aft", "freeboard_quarterdeck_fore",
                 "freeboard_afterdeck_aft", "freeboard_afterdeck_fore",
                 "freeboard_flat_deck_aft", "freeboard_flat_deck_fore",
                 "freeboard_forecastle_aft", "freeboard_forecastle_fore",
                 "freeboard_length_stern", "freeboard_length_bow",
                 "freeboard_ram_length"):
        add(name, page="freeboard", unit="ft", scale_ref="hull_scale",
            unit_choices=LENGTH_CHOICES)
    for name in ("freeboard_quarterdeck_length", "freeboard_flat_deck_length",
                 "freeboard_forecastle_length"):
        add(name, page="freeboard", unit="%", scale_ref="length_waterline")

    # --- guns page ---
    for n in gun_chars:
        scale = "gun%s_scale" % n
        add(scale, page="guns", choices=IMPERIAL_METRIC_CHOICES)
        add("gun%s_barrels" % n, page="guns", unit="count", min_value=0)
        add("gun%s_calibre" % n, page="guns", unit="in", scale_ref=scale,
            unit_choices=IMPERIAL_METRIC_CHOICES)
        add("gun%s_type" % n, page="guns", choices=GUN_TYPE_CHOICES, enum=True)
        add("gun%s_shell_weight" % n, page="guns", unit="lb", min_value=0)
        add("gun%s_mounts" % n, page="guns", unit="count", min_value=0)
        add("gun%s_mount_type" % n, page="guns", choices=MOUNT_TYPE_CHOICES, enum=True)
        add("gun%s_layout_group1" % n, page="guns", choices=LAYOUT_CHOICES, enum=True)
        add("gun%s_layout_group2" % n, page="guns", choices=LAYOUT_CHOICES, enum=True)
        for face in ("face", "rear", "bottom"):
            add("gun%s_turret_%s_armour" % (n, face), page="guns", unit="in",
                scale_ref="armour_scale", unit_choices=IMPERIAL_METRIC_CHOICES)
        add("gun%s_year" % n, page="guns", unit="year", integer=True, min_value=0)
        add("gun%s_barrel_length_calibres" % n, page="guns", unit="calibres")
        add("gun%s_magazine_rounds" % n, page="guns", unit="rounds", min_value=0)
        for group in ("group1", "group2"):
            add("gun%s_super_mounts_%s" % (n, group), page="guns", unit="count", min_value=0)
            add("gun%s_sub_mounts_%s" % (n, group), page="guns", unit="count", min_value=0)
        add("gun%s_deck_mounts_group2" % n, page="guns", unit="count", min_value=0)
        add("gun%s_superstructure_above" % n, page="guns")
        add("gun%s_submarine_mount" % n, page="guns")
        add("gun%s_barrels_per_mount_group1" % n, page="guns", choices=PER_MOUNT_CHOICES,
            enum=True)
        add("gun%s_barrels_per_mount_group2" % n, page="guns", choices=PER_MOUNT_CHOICES,
            enum=True)

    # --- weapons / auxiliary page ---
    add("torpedo1_scale", page="weapons", choices=IMPERIAL_METRIC_CHOICES)
    add("torpedo2_scale", page="weapons", choices=IMPERIAL_METRIC_CHOICES)
    add("mine1_scale", page="weapons", choices=WEIGHT_CHOICES)
    add("deck_gun1_scale", page="weapons", choices=WEIGHT_CHOICES)
    add("deck_gun2_scale", page="weapons", choices=WEIGHT_CHOICES)
    for name in ("misc_weight_vital", "misc_weight_hull", "misc_weight_deck",
                 "misc_weight_above", "misc_weight_void"):
        add(name, page="weapons", unit="lt")
    for n in ("1", "2"):
        add("torpedo%s_count" % n, page="weapons", unit="count", min_value=0)
        add("torpedo%s_rounds" % n, page="weapons", unit="count", min_value=0)
        add("torpedo%s_size" % n, page="weapons", unit="in", scale_ref="torpedo%s_scale" % n,
            unit_choices=IMPERIAL_METRIC_CHOICES)
        add("torpedo%s_length" % n, page="weapons", unit="ft", scale_ref="torpedo%s_scale" % n,
            unit_choices=LENGTH_CHOICES)
        add("torpedo%s_location" % n, page="weapons", choices=TORPEDO_LOCATION_CHOICES,
            enum=True)
    add("mine1_count", page="weapons", unit="count", min_value=0)
    add("mine1_rounds", page="weapons", unit="count", min_value=0)
    add("mine1_size", page="weapons", unit="lb", scale_ref="mine1_scale",
        unit_choices=WEIGHT_CHOICES)
    add("mine1_location", page="weapons", choices=MINE_LOCATION_CHOICES, enum=True)
    for n in ("1", "2"):
        add("deck_gun%s_count" % n, page="weapons", unit="count", min_value=0)
        add("deck_gun%s_rounds" % n, page="weapons", unit="count", min_value=0)
        add("deck_gun%s_size" % n, page="weapons", unit="lb", scale_ref="deck_gun%s_scale" % n,
            unit_choices=WEIGHT_CHOICES)
        add("deck_gun%s_location" % n, page="weapons", choices=DC_LOCATION_CHOICES, enum=True)

    # --- armour page ---
    add("armour_scale", page="armour", choices=IMPERIAL_METRIC_CHOICES)
    for name in ("armour_belt_main_thickness", "armour_belt_ends_thickness",
                 "armour_belt_upper_thickness", "armour_bulkhead_thickness",
                 "armour_bulge_thickness", "armour_deck_thickness",
                 "armour_deck_forecastle_thickness", "armour_deck_quarterdeck_thickness",
                 "armour_conning_forward_thickness", "armour_conning_aft_thickness"):
        add(name, page="armour", unit="in", scale_ref="armour_scale",
            unit_choices=IMPERIAL_METRIC_CHOICES)
    for name in ("armour_belt_main_length", "armour_belt_main_height",
                 "armour_belt_ends_length", "armour_belt_ends_height",
                 "armour_belt_upper_length", "armour_belt_upper_height",
                 "armour_bulkhead_length", "armour_bulkhead_height",
                 "armour_bulge_length", "armour_bulge_height",
                 "armour_bulkhead_beam"):
        add(name, page="armour", unit="ft", scale_ref="armour_scale",
            unit_choices=LENGTH_CHOICES)
    add("armour_belt_main_inclination", page="armour", unit="deg")
    add("armour_bulkhead_type", page="armour", choices=BULKHEAD_TYPE_CHOICES, enum=True)
    add("armour_deck_coverage", page="armour", choices=DECK_COVERAGE_CHOICES, enum=True)

    # --- engine page ---
    add("speed_max_kn", page="engine", unit="kn", min_value=0)
    add("speed_cruise_kn", page="engine", unit="kn", min_value=0)
    add("range_nm", page="engine", unit="nm", min_value=0)
    add("shafts", page="engine", unit="count", integer=True, min_value=0)
    add("coal_percentage", page="engine", unit="%", min_value=0, max_value=100)
    for name in ("fuel_coal", "fuel_oil", "fuel_diesel", "fuel_petrol", "fuel_batteries",
                 "engine_simple", "engine_compound", "engine_turbine",
                 "drive_direct", "drive_geared", "drive_electric", "drive_hydraulic"):
        add(name, page="engine")

    # --- performance page ---
    add("trim", page="performance", unit="trim", integer=True, min_value=0, max_value=100)

    return specs


def _page_for(index: int, pages: dict) -> str:
    for key in PAGE_ORDER:
        if index in pages[key]:
            return key
    return "hull"


_ALIASES = {
    "deck_gun1_count": ("depthcharge1_count",),
    "deck_gun2_count": ("depthcharge2_count",),
    "deck_gun1_size": ("depthcharge1_size",),
    "deck_gun2_size": ("depthcharge2_size",),
    "deck_gun1_rounds": ("depthcharge1_rounds",),
    "deck_gun2_rounds": ("depthcharge2_rounds",),
    "deck_gun1_location": ("depthcharge1_location",),
    "deck_gun2_location": ("depthcharge2_location",),
    "deck_gun1_scale": ("depthcharge1_scale",),
    "deck_gun2_scale": ("depthcharge2_scale",),
}

EFFECTIVE_FIELD_COUNT = 222

# 原程序全局尺度动作覆盖的 12 个页面尺度选择器（0/1）。
ALL_SCALE_FIELDS = (
    "hull_scale",
    "gun1_scale", "gun2_scale", "gun3_scale", "gun4_scale", "gun5_scale",
    "torpedo1_scale", "torpedo2_scale", "mine1_scale",
    "deck_gun1_scale", "deck_gun2_scale", "armour_scale",
)

RESOLVED_UNIT = {
    "hull_scale": 1,
    "torpedo1_scale": 1, "torpedo2_scale": 1,
    "mine1_scale": 1, "deck_gun1_scale": 1, "deck_gun2_scale": 1,
    "armour_scale": 1,
    "gun1_scale": 1, "gun2_scale": 1, "gun3_scale": 1, "gun4_scale": 1, "gun5_scale": 1,
}


def _resolved_unit(spec: dict, parameters: Mapping | None) -> str | None:
    if not spec["scale_ref"] or not spec["unit_choices"]:
        return spec["unit"]
    if not isinstance(parameters, Mapping):
        return spec["unit"]
    scale = parameters.get(spec["scale_ref"])
    if isinstance(scale, bool) or not isinstance(scale, (int, float)):
        return spec["unit"]
    if float(scale).is_integer() and int(scale) == RESOLVED_UNIT.get(spec["scale_ref"]):
        return spec["unit_choices"][1]
    return spec["unit_choices"][0]


def catalog(parameters: Mapping | None = None) -> dict:
    """Return the static 222-field catalog, optionally resolving page units.

    ``parameters`` is only read to resolve a scaled field's current unit; the
    catalog itself never depends on a particular design.
    """
    specs = _specs()
    fields = {}
    pages = {key: [] for key in PAGE_ORDER}
    for spec in specs:
        name = spec["name"]
        entry = dict(spec)
        entry["label"] = _auto_label(name)
        entry["aliases"] = list(_ALIASES.get(name, ()))
        entry["unit_resolved"] = _resolved_unit(spec, parameters)
        fields[name] = entry
        pages[spec["page"]].append(name)
    return {
        "schema": CATALOG_SCHEMA,
        "field_count": len(specs),
        "page_order": list(PAGE_ORDER),
        "page_labels": dict(PAGE_LABELS),
        "pages": {key: {"label": PAGE_LABELS[key], "fields": names}
                  for key, names in pages.items()},
        "fields": fields,
        "controls": {
            "length_driver": {"choices": ["waterline", "overall"],
                              "default": "waterline", "editable_keys": ["overall_length"]},
            "displacement_driver": {"choices": ["block", "displacement"],
                                    "default": "block",
                                    "editable_keys": ["normal_displacement_lt"]},
            "depth_lock": {"default": False, "editable_keys": ["depths"],
                           "snapshot_ft": 8},
            "bulkhead_beam_mode": {"choices": ["follow_hull", "fixed"],
                                   "default": "follow_hull"},
            "power_lock": {"default": False,
                           "editable_keys": ["power_hp", "locked_bunker_lt"]},
            "freeboard_presets": ["flush", "raised"],
            "global_scale": {
                "command": "set_all_scales",
                "choices": list(GLOBAL_SCALE_CHOICES),
                "value_map": {"all metric": 1, "all imperial": 0},
                "scale_fields": list(ALL_SCALE_FIELDS),
            },
            "commands": ["set_parameter", "set_scale", "set_all_scales",
                         "set_length_driver", "set_displacement_driver", "set_depth_lock",
                         "freeboard_preset", "set_power_lock", "recalculate_power",
                         "lock_shells", "unlock_shells", "armour_defaults", "set_notes"],
        },
    }


field_catalog = catalog

__all__ = ["catalog", "field_catalog", "CATALOG_SCHEMA", "PAGE_ORDER", "PAGE_LABELS",
           "EFFECTIVE_FIELD_COUNT", "ALL_SCALE_FIELDS", "GLOBAL_SCALE_CHOICES"]
