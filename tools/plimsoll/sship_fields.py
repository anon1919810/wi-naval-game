"""The recovered SpringSharp 3.0 positional field registry.

Positions are evidence, not inference. Every entry below was read from the
local 3b3 save handler (``MainForm.cs``) and recorded in the chat format
evidence file; the ordering is the file order the writer used, so a reader must
assign positions the same way and must let the **last** assignment win where the
3.0 writer stores a control twice.

Nothing here parses, executes or reinterprets recovered program code: this is a
declarative table of positions, names and value kinds.
"""

FIELD_COUNT = 280
PADDING_FIRST = 247
SUPPORTED_VERSION = "3.0"
SUPPORTED_DECIMAL_HEADER = "SpringSharp Version 3.0"
SUPPORTED_COMMA_HEADER = "SpringSharp Version 3,0"

# Value kinds.
TEXT = "text"
NUMBER = "number"
INTEGER = "integer"
BOOLEAN = "boolean"
ENUM = "enum"
SELECTOR = "selector"

# Recovered GunControl.cs per-mount index table; the value is barrels per mount.
PER_MOUNT_BARRELS = (1, 2, 4, 2, 2, 4, 3, 3, 6, 4, 4, 8, 5, 5, 10)
# The shared-cradle ("N-gun mount") entries of that same table.
SHARED_CRADLE_INDICES = frozenset({3, 6, 9, 12})

GUN_TYPES = (
    "Muzzle loading gun", "Breech loading gun", "Quick firing gun", "Anti-air gun",
    "Dual purpose gun", "Auto rapid fire gun", "Machine gun",
)
MOUNT_TYPES = (
    "in broadside mount", "in Coles/Ericsson turret mount", "in open barbette mount",
    "in turret on barbette mount", "in deck and hoist mount", "in deck mount",
    "in casemate mount",
)
STERN_TYPES = ("cruiser", "small_transom", "large_transom", "round")
STERN_LABELS = ("Cruiser stern", "Transom stern - small", "Transom stern - large",
                "Round stern")
LAYOUT_LABELS = (
    "Centreline - distributed", "Centreline - ends (fore >= aft)",
    "Centreline - ends (aft >= fore)", "Centreline - fore deck forward",
    "Centreline - fore deck", "Centreline - fore deck aft",
    "Centreline - aft deck forward", "Centreline - aft deck", "Centreline - aft deck aft",
    "Sides - distributed", "Sides - ends (fore >= aft)", "Sides - ends (aft >= fore)",
    "Sides - fore deck forward", "Sides - fore deck", "Sides - fore deck aft",
    "Sides - aft deck forward", "Sides - aft deck", "Sides - aft deck aft", "None",
)
ENGINE_KINDS = ("simple", "compound", "turbine")
FUEL_LABELS = (
    "Coal fired boilers", "Oil fired boilers", "Diesel motors", "Petrol motors",
    "Batteries",
)
DRIVE_LABELS = ("Direct", "Geared", "Electric", "Hydraulic")

# Fields the original reader stores twice. The writer emits the early copy first
# and the 211..235 block last, and a plain sequential assignment means the last
# one wins. The earlier copy is therefore never read.
SUPER_MOUNTS_G1_EARLY = tuple(34 + 6 * bank for bank in range(5))
SUB_MOUNTS_G1_EARLY = tuple(35 + 6 * bank for bank in range(5))
SUPER_MOUNTS_G2_EARLY = tuple(154 + bank for bank in range(5))
DECK_MOUNTS_G2_EARLY = tuple(164 + bank for bank in range(5))
SUB_MOUNTS_G2_EARLY = tuple(169 + bank for bank in range(5))
SHADOWED = frozenset(
    SUPER_MOUNTS_G1_EARLY + SUB_MOUNTS_G1_EARLY + SUPER_MOUNTS_G2_EARLY
    + DECK_MOUNTS_G2_EARLY + SUB_MOUNTS_G2_EARLY
)
assert len(SHADOWED) == 25

# The authoritative, later block.
SUPER_MOUNTS_G1 = 211
SUB_MOUNTS_G1 = 216
SUPER_MOUNTS_G2 = 221
DECK_MOUNTS_G2 = 226
SUB_MOUNTS_G2 = 231
BARRELS_PER_MOUNT_G1 = 236
BARRELS_PER_MOUNT_G2 = 241

# Per-bank strides recovered from the writer.
HULL_SCALE_INDEX = 3
GUN_SCALE_BASE = 4
ARMOUR_SCALE_INDEX = 10
BARRELS_BASE, CALIBRE_BASE, GUN_TYPE_BASE = 31, 32, 33
SHELL_WEIGHT_BASE = 36
GUN_ARM_FACE_BASE = 92
MOUNTS_BASE, MOUNT_TYPE_BASE, LAYOUT_G1_BASE = 62, 63, 64
GUN_YEAR_BASE = 129
BARREL_LENGTH_BASE = 140
MAGAZINE_INDEXES = (61, 145, 146, 147, 148)
LAYOUT_G2_BASE = 149
SUPER_SUPER_BASE = 159
SUB_SUB_BASE = 174
ARM_FACE_BASE, ARM_BACK_BASE, ARM_BOTTOM_BASE = 92, 93, 94
BANK_COUNT = 5

# Positions whose declared meaning the original program reads as a number that
# may be negative; every other numeric position rejects a negative value.
SIGNED_INDEXES = frozenset({19, 29, 30, 201})

# Miscellaneous weights are read with fpCheck(..., Con.none, 0): long tons, in
# every display unit, in every saved file.
MISC_WEIGHT_INDEXES = (12, 198, 199, 200, 246)
MISC_WEIGHT_IDS = ("misc.vital", "misc.hull", "misc.deck", "misc.above", "misc.void")
MISC_WEIGHT_ROLES = ("misc_vital", "misc_hull", "misc_deck", "misc_above", "misc_void")


def _entry(name, kind):
    return (name, kind)


_REGISTRY = (
    # 0..30 identity, display selectors, hull dimensions and freeboard profile.
    _entry("ship_name", TEXT),
    _entry("country", TEXT),
    _entry("ship_type", TEXT),
    _entry("hull_scale", SELECTOR),
    _entry("gun1_scale", SELECTOR),
    _entry("gun2_scale", SELECTOR),
    _entry("gun3_scale", SELECTOR),
    _entry("gun4_scale", SELECTOR),
    _entry("gun5_scale", SELECTOR),
    _entry("torpedo1_scale", SELECTOR),
    _entry("armour_scale", SELECTOR),
    _entry("hull_year", INTEGER),
    _entry("misc_weight_vital", NUMBER),
    _entry("length_waterline", NUMBER),
    _entry("beam_moulded", NUMBER),
    _entry("draught_normal", NUMBER),
    _entry("stern", ENUM),
    _entry("block_coefficient_normal", NUMBER),
    _entry("freeboard_quarterdeck_aft", NUMBER),
    _entry("freeboard_length_stern", NUMBER),
    _entry("freeboard_quarterdeck_length", NUMBER),
    _entry("freeboard_quarterdeck_fore", NUMBER),
    _entry("freeboard_afterdeck_aft", NUMBER),
    _entry("freeboard_flat_deck_length", NUMBER),
    _entry("freeboard_afterdeck_fore", NUMBER),
    _entry("freeboard_flat_deck_aft", NUMBER),
    _entry("freeboard_forecastle_length", NUMBER),
    _entry("freeboard_flat_deck_fore", NUMBER),
    _entry("freeboard_forecastle_aft", NUMBER),
    _entry("freeboard_forecastle_fore", NUMBER),
    _entry("freeboard_length_bow", NUMBER),
    # 31..60 the five gun groups (barrels, calibre, type, two early group-1
    # mount counts that 211..220 override, and the always-pounds shell weight).
    _entry("gun1_barrels", NUMBER),
    _entry("gun1_calibre", NUMBER),
    _entry("gun1_type", ENUM),
    _entry("gun1_super_mounts_group1_early", NUMBER),
    _entry("gun1_sub_mounts_group1_early", NUMBER),
    _entry("gun1_shell_weight", NUMBER),
    _entry("gun2_barrels", NUMBER),
    _entry("gun2_calibre", NUMBER),
    _entry("gun2_type", ENUM),
    _entry("gun2_super_mounts_group1_early", NUMBER),
    _entry("gun2_sub_mounts_group1_early", NUMBER),
    _entry("gun2_shell_weight", NUMBER),
    _entry("gun3_barrels", NUMBER),
    _entry("gun3_calibre", NUMBER),
    _entry("gun3_type", ENUM),
    _entry("gun3_super_mounts_group1_early", NUMBER),
    _entry("gun3_sub_mounts_group1_early", NUMBER),
    _entry("gun3_shell_weight", NUMBER),
    _entry("gun4_barrels", NUMBER),
    _entry("gun4_calibre", NUMBER),
    _entry("gun4_type", ENUM),
    _entry("gun4_super_mounts_group1_early", NUMBER),
    _entry("gun4_sub_mounts_group1_early", NUMBER),
    _entry("gun4_shell_weight", NUMBER),
    _entry("gun5_barrels", NUMBER),
    _entry("gun5_calibre", NUMBER),
    _entry("gun5_type", ENUM),
    _entry("gun5_super_mounts_group1_early", NUMBER),
    _entry("gun5_sub_mounts_group1_early", NUMBER),
    _entry("gun5_shell_weight", NUMBER),
    # 61..79 ammunition, mount counts, mount and layout selectors, torpedoes.
    _entry("gun1_magazine_rounds", NUMBER),
    _entry("gun1_mounts", NUMBER),
    _entry("gun1_mount_type", ENUM),
    _entry("gun1_layout_group1", ENUM),
    _entry("gun2_mounts", NUMBER),
    _entry("gun2_mount_type", ENUM),
    _entry("gun2_layout_group1", ENUM),
    _entry("gun3_mounts", NUMBER),
    _entry("gun3_mount_type", ENUM),
    _entry("gun3_layout_group1", ENUM),
    _entry("gun4_mounts", NUMBER),
    _entry("gun4_mount_type", ENUM),
    _entry("gun4_layout_group1", ENUM),
    _entry("gun5_mounts", NUMBER),
    _entry("gun5_mount_type", ENUM),
    _entry("gun5_layout_group1", ENUM),
    _entry("torpedo1_count", NUMBER),
    _entry("torpedo2_count", NUMBER),
    _entry("torpedo1_size", NUMBER),
    # 80..108 armour thickness, extents and turret armour.
    _entry("armour_belt_main_thickness", NUMBER),
    _entry("armour_belt_main_length", NUMBER),
    _entry("armour_belt_main_height", NUMBER),
    _entry("armour_belt_ends_thickness", NUMBER),
    _entry("armour_belt_ends_length", NUMBER),
    _entry("armour_belt_ends_height", NUMBER),
    _entry("armour_belt_upper_thickness", NUMBER),
    _entry("armour_belt_upper_length", NUMBER),
    _entry("armour_belt_upper_height", NUMBER),
    _entry("armour_bulkhead_thickness", NUMBER),
    _entry("armour_bulkhead_length", NUMBER),
    _entry("armour_bulkhead_height", NUMBER),
    _entry("gun1_turret_face_armour", NUMBER),
    _entry("gun1_turret_rear_armour", NUMBER),
    _entry("gun1_turret_bottom_armour", NUMBER),
    _entry("gun2_turret_face_armour", NUMBER),
    _entry("gun2_turret_rear_armour", NUMBER),
    _entry("gun2_turret_bottom_armour", NUMBER),
    _entry("gun3_turret_face_armour", NUMBER),
    _entry("gun3_turret_rear_armour", NUMBER),
    _entry("gun3_turret_bottom_armour", NUMBER),
    _entry("gun4_turret_face_armour", NUMBER),
    _entry("gun4_turret_rear_armour", NUMBER),
    _entry("gun4_turret_bottom_armour", NUMBER),
    _entry("gun5_turret_face_armour", NUMBER),
    _entry("gun5_turret_rear_armour", NUMBER),
    _entry("gun5_turret_bottom_armour", NUMBER),
    _entry("armour_deck_thickness", NUMBER),
    _entry("armour_conning_forward_thickness", NUMBER),
    # 109..126 speeds, range, machinery, fuel, engine, drive and trim.
    _entry("speed_max_kn", NUMBER),
    _entry("speed_cruise_kn", NUMBER),
    _entry("range_nm", NUMBER),
    _entry("shafts", NUMBER),
    _entry("coal_percentage", NUMBER),
    _entry("fuel_coal", BOOLEAN),
    _entry("fuel_oil", BOOLEAN),
    _entry("fuel_diesel", BOOLEAN),
    _entry("fuel_petrol", BOOLEAN),
    _entry("fuel_batteries", BOOLEAN),
    _entry("engine_simple", BOOLEAN),
    _entry("engine_compound", BOOLEAN),
    _entry("engine_turbine", BOOLEAN),
    _entry("drive_direct", BOOLEAN),
    _entry("drive_geared", BOOLEAN),
    _entry("drive_electric", BOOLEAN),
    _entry("drive_hydraulic", BOOLEAN),
    _entry("trim", TEXT),
    # 127..148 bulged beam, dates, bow, barrel lengths and magazines.
    _entry("beam_at_bulges", NUMBER),
    _entry("engine_year", INTEGER),
    _entry("gun1_year", INTEGER),
    _entry("gun2_year", INTEGER),
    _entry("gun3_year", INTEGER),
    _entry("gun4_year", INTEGER),
    _entry("gun5_year", INTEGER),
    _entry("bow", ENUM),
    _entry("freeboard_ram_length", NUMBER),
    _entry("torpedo2_scale", SELECTOR),
    _entry("mine1_scale", SELECTOR),
    _entry("deck_gun1_scale", SELECTOR),
    _entry("deck_gun2_scale", SELECTOR),
    _entry("gun1_barrel_length_calibres", NUMBER),
    _entry("gun2_barrel_length_calibres", NUMBER),
    _entry("gun3_barrel_length_calibres", NUMBER),
    _entry("gun4_barrel_length_calibres", NUMBER),
    _entry("gun5_barrel_length_calibres", NUMBER),
    _entry("gun2_magazine_rounds", NUMBER),
    _entry("gun3_magazine_rounds", NUMBER),
    _entry("gun4_magazine_rounds", NUMBER),
    _entry("gun5_magazine_rounds", NUMBER),
    # 149..178 the second layout selector, the early group-2 mount counts that
    # 221..235 override, and the two turret-above/submarine checkboxes.
    _entry("gun1_layout_group2", ENUM),
    _entry("gun2_layout_group2", ENUM),
    _entry("gun3_layout_group2", ENUM),
    _entry("gun4_layout_group2", ENUM),
    _entry("gun5_layout_group2", ENUM),
    _entry("gun1_super_mounts_group2_early", NUMBER),
    _entry("gun2_super_mounts_group2_early", NUMBER),
    _entry("gun3_super_mounts_group2_early", NUMBER),
    _entry("gun4_super_mounts_group2_early", NUMBER),
    _entry("gun5_super_mounts_group2_early", NUMBER),
    _entry("gun1_superstructure_above", BOOLEAN),
    _entry("gun2_superstructure_above", BOOLEAN),
    _entry("gun3_superstructure_above", BOOLEAN),
    _entry("gun4_superstructure_above", BOOLEAN),
    _entry("gun5_superstructure_above", BOOLEAN),
    _entry("gun1_deck_mounts_group2_early", NUMBER),
    _entry("gun2_deck_mounts_group2_early", NUMBER),
    _entry("gun3_deck_mounts_group2_early", NUMBER),
    _entry("gun4_deck_mounts_group2_early", NUMBER),
    _entry("gun5_deck_mounts_group2_early", NUMBER),
    _entry("gun1_sub_mounts_group2_early", NUMBER),
    _entry("gun2_sub_mounts_group2_early", NUMBER),
    _entry("gun3_sub_mounts_group2_early", NUMBER),
    _entry("gun4_sub_mounts_group2_early", NUMBER),
    _entry("gun5_sub_mounts_group2_early", NUMBER),
    _entry("gun1_submarine_mount", BOOLEAN),
    _entry("gun2_submarine_mount", BOOLEAN),
    _entry("gun3_submarine_mount", BOOLEAN),
    _entry("gun4_submarine_mount", BOOLEAN),
    _entry("gun5_submarine_mount", BOOLEAN),
    # 179..200 torpedoes, mines, deck guns, remaining misc weights.
    _entry("torpedo1_rounds", NUMBER),
    _entry("torpedo2_rounds", NUMBER),
    _entry("torpedo2_size", NUMBER),
    _entry("torpedo1_length", NUMBER),
    _entry("torpedo2_length", NUMBER),
    _entry("torpedo1_location", ENUM),
    _entry("torpedo2_location", ENUM),
    _entry("mine1_count", NUMBER),
    _entry("mine1_rounds", NUMBER),
    _entry("mine1_size", NUMBER),
    _entry("mine1_location", ENUM),
    _entry("deck_gun1_count", NUMBER),
    _entry("deck_gun2_count", NUMBER),
    _entry("deck_gun1_rounds", NUMBER),
    _entry("deck_gun2_rounds", NUMBER),
    _entry("deck_gun1_size", NUMBER),
    _entry("deck_gun2_size", NUMBER),
    _entry("deck_gun1_location", ENUM),
    _entry("deck_gun2_location", ENUM),
    _entry("misc_weight_hull", NUMBER),
    _entry("misc_weight_deck", NUMBER),
    _entry("misc_weight_above", NUMBER),
    # 201..210 armour inclination, bulge, bulkhead and deck coverage.
    _entry("armour_belt_main_inclination", NUMBER),
    _entry("armour_bulge_thickness", NUMBER),
    _entry("armour_bulge_length", NUMBER),
    _entry("armour_bulge_height", NUMBER),
    _entry("armour_bulkhead_type", ENUM),
    _entry("armour_bulkhead_beam", NUMBER),
    _entry("armour_deck_forecastle_thickness", NUMBER),
    _entry("armour_deck_quarterdeck_thickness", NUMBER),
    _entry("armour_deck_coverage", ENUM),
    _entry("armour_conning_aft_thickness", NUMBER),
    # 211..245 the authoritative group-1/group-2 mount blocks and per-mount tables.
    _entry("gun1_super_mounts_group1", NUMBER),
    _entry("gun2_super_mounts_group1", NUMBER),
    _entry("gun3_super_mounts_group1", NUMBER),
    _entry("gun4_super_mounts_group1", NUMBER),
    _entry("gun5_super_mounts_group1", NUMBER),
    _entry("gun1_sub_mounts_group1", NUMBER),
    _entry("gun2_sub_mounts_group1", NUMBER),
    _entry("gun3_sub_mounts_group1", NUMBER),
    _entry("gun4_sub_mounts_group1", NUMBER),
    _entry("gun5_sub_mounts_group1", NUMBER),
    _entry("gun1_super_mounts_group2", NUMBER),
    _entry("gun2_super_mounts_group2", NUMBER),
    _entry("gun3_super_mounts_group2", NUMBER),
    _entry("gun4_super_mounts_group2", NUMBER),
    _entry("gun5_super_mounts_group2", NUMBER),
    _entry("gun1_deck_mounts_group2", NUMBER),
    _entry("gun2_deck_mounts_group2", NUMBER),
    _entry("gun3_deck_mounts_group2", NUMBER),
    _entry("gun4_deck_mounts_group2", NUMBER),
    _entry("gun5_deck_mounts_group2", NUMBER),
    _entry("gun1_sub_mounts_group2", NUMBER),
    _entry("gun2_sub_mounts_group2", NUMBER),
    _entry("gun3_sub_mounts_group2", NUMBER),
    _entry("gun4_sub_mounts_group2", NUMBER),
    _entry("gun5_sub_mounts_group2", NUMBER),
    _entry("gun1_barrels_per_mount_group1", ENUM),
    _entry("gun2_barrels_per_mount_group1", ENUM),
    _entry("gun3_barrels_per_mount_group1", ENUM),
    _entry("gun4_barrels_per_mount_group1", ENUM),
    _entry("gun5_barrels_per_mount_group1", ENUM),
    _entry("gun1_barrels_per_mount_group2", ENUM),
    _entry("gun2_barrels_per_mount_group2", ENUM),
    _entry("gun3_barrels_per_mount_group2", ENUM),
    _entry("gun4_barrels_per_mount_group2", ENUM),
    _entry("gun5_barrels_per_mount_group2", ENUM),
    # 246..279 the void misc weight and the ignored writer padding.
    _entry("misc_weight_void", NUMBER),
) + tuple(_entry(f"reserved_padding_{index}", TEXT) for index in range(PADDING_FIRST, FIELD_COUNT))

assert len(_REGISTRY) == FIELD_COUNT, len(_REGISTRY)

NAMES = tuple(name for name, _kind in _REGISTRY)
KINDS = tuple(kind for _name, kind in _REGISTRY)
RESERVED_INDEXES = frozenset(range(PADDING_FIRST, FIELD_COUNT))


def name_of(index):
    """Return the registry name of one source position."""
    return NAMES[index]


def kind_of(index):
    """Return the registry value kind of one source position."""
    return KINDS[index]