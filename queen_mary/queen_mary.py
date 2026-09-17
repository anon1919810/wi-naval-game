"""Generate the user-specified HMS Queen Mary greybox in Blender 3.x/4.x. Asset v2.

Run: blender --background --python queen_mary.py -- --out OUTPUT_DIRECTORY
Or open this text in Blender's Text Editor and Run Script (clears the scene).
No third-party Python packages, textures, downloads, or external model files.
All lengths are metres. +Y bow, +X starboard, +Z up, Z=0 waterline.

asset_v2 changes against the v1 greybox (v1 is kept in _v1_backup/):
  * The hull is driven by a station offsets table (OFFSETS) instead of one scaled
    section. A real lines plan can be dropped in as hull_offsets.json without
    editing this script.
  * Cruiser stern: the deck keeps breadth aft, so attachments can be derived from
    the hull surface instead of hand-written absolute coordinates.
  * Attachments use halfbeam_at()/deck_halfbeam(), so nothing can silently leave
    the hull envelope again.
  * Forecastle and quarterdeck carry sheer and are separate modules.
  * Damage modules are real volumes with documented provenance, not empty anchors.
  * Only decoration is merged (nets, sternwalk rails, casemate openings, barrel
    parts). Every combat-relevant module stays separately addressable.
Specified principal dimensions are exact; component geometry is an estimate.
"""

import argparse
import csv
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix


# --- provenance -------------------------------------------------------------
# Every non-obvious number is tagged with where it came from. "estimate" means it
# is a greybox guess and must never be quoted as history.
SOURCES = {
    'wiki': 'Wikipedia: HMS Queen Mary (1912) - general characteristics, armament, armour',
    'mq': 'MaritimeQuest: HMS Queen Mary data page - dimensions, armament as built',
    'ww1': 'worldwar1.co.uk: Queen Mary class battlecruiser - funnel and mast notes',
    'navalenc': 'naval-encyclopedia.com: Lion class battlecruisers (1910) - modification notes',
    'rmg': 'Royal Museums Greenwich collection index for Queen Mary (1912)',
    'user': 'User greybox specification for this asset (not historical certification)',
    'estimate': 'Asset author estimate for this greybox; no source yet',
}

SHIP = {
    'ship_id': 'HMS_Queen_Mary_1913',
    'asset_version': 'v2',
    'length_m': 213.4, 'beam_m': 27.2, 'draft_m': 9.9,
    'main_deck_z_m': 5.1, 'forecastle_z_m': 7.5, 'quarterdeck_z_m': 5.72,
    'displacement_normal_t': 27200, 'displacement_full_t': 32160,
    'speed_knots': 28.0, 'speed_trials_knots': 28.35,
    'shp_design': 75000, 'shp_trials': 83350,
    'boilers': 42, 'boiler_rooms': 7, 'shafts': 4,
    'main_gun_calibre_mm': 343, 'main_gun_barrels': 8, 'main_turrets': 'A/B/Q/X',
    'secondary_gun_calibre_mm': 102, 'secondary_guns': 16,
    'torpedo_tubes': 2, 'torpedo_tube_inches': 21,
    'max_elevation_director_deg': 15.35, 'max_elevation_mount_deg': 20.0,
    'min_elevation_mount_deg': -3.0,
    'main_rounds_per_gun': 110, 'main_rounds_total': 880,
    'shell_weight_lb': 1400, 'muzzle_velocity_mps': 760,
    'max_range_main_m': 21708, 'max_range_secondary_m': 10400, 'secondary_rpm': '6-8',
    'configuration': 'user_spec_greybox_v2',
    'historically_certified': False,
}

# --- hull offsets: single source of truth for the whole ship -----------------
# (y, deck half-beam, waterline half-beam, keel z, flat-of-keel half-beam), metres.
# The three principal dimensions are specified; the shape between them is an
# estimate. Replace it by dropping hull_offsets.json next to this script:
#   {"sources": "...", "stations": [[y, deck_hb, wl_hb, keel_z, flat_hb], ...]}
OFFSETS = [
    (-106.7,  2.20, 0.55, -1.00, 0.15),
    (-105.5,  3.30, 1.25, -1.75, 0.22),
    (-103.0,  4.80, 2.45, -2.70, 0.30),
    (-100.0,  6.20, 3.80, -3.70, 0.42),
    ( -95.0,  7.80, 5.90, -5.60, 0.70),
    ( -88.0,  9.40, 7.80, -7.60, 1.20),
    ( -78.0, 10.60, 9.20, -9.10, 1.90),
    ( -65.0, 11.90, 10.90, -9.80, 2.60),
    ( -50.0, 13.10, 12.30, -9.90, 3.20),
    ( -30.0, 13.60, 13.10, -9.90, 3.40),
    ( -18.0, 13.60, 13.18, -9.90, 3.40),
    ( -10.0, 13.60, 13.30, -9.90, 3.40),
    (  10.0, 13.60, 13.40, -9.90, 3.40),
    (  30.0, 13.55, 13.35, -9.90, 3.40),
    (  50.0, 13.20, 13.00, -9.85, 3.20),
    (  65.0, 12.40, 12.10, -9.60, 2.80),
    (  78.0, 11.00, 10.55, -9.00, 2.20),
    (  88.0,  9.00,  8.35, -8.10, 1.60),
    (  95.0,  6.60,  5.60, -6.60, 1.00),
    ( 100.0,  4.30,  3.30, -4.80, 0.50),
    ( 102.5,  3.05,  2.20, -3.80, 0.30),
    ( 106.7,  0.12,  0.06, -0.60, 0.02),
]
DECK_Z = 5.10
FORE_AFT_END = -18.0          # forecastle deck after end
SUPERFIRING_DECK_Z = 11.0     # B turret deckhouse top (user spec, unchanged from v1)
FUNNEL_TOP_Z = 22.0           # all three funnel tops level (ww1: raised to one height)
FUNNEL_UPTAKE_H = 2.45
BARREL_END_M = 12.4           # muzzle plane, local +Y from the trunnion
TRUNNION_Y_M = 4.0            # pitch pivot, local +Y inside the turret
TURRET_HEIGHT_M = 3.1
BRIDGE_Y = 32.0
BRIDGE_HEIGHT = 6.2
BRIDGE_UPPER_HEIGHT = 2.8
AFT_Y = -41.0
AFT_DECKHOUSE_HEIGHT = 4.0
CT_Y = 37.0

TURRETS = {  # key: (y, deck source, barbette height, resting yaw deg)
    'A': ( 60.0, 'forecastle', 1.00,   0.0),
    'B': ( 46.0, 'superfiring', 1.00,   0.0),
    'Q': ( -6.0, 'forecastle', 1.00, 180.0),
    'X': (-68.0, 'quarterdeck', 1.20, 180.0),
}
FUNNELS = {  # index: (y, transverse radius, longitudinal radius)  estimate
    1: ( 23.0, 2.45, 3.80),
    2: (  7.0, 3.50, 3.50),
    3: (-27.0, 2.45, 3.80),
}
# 8 per side on one deck, from forward to aft. Which deck (and therefore the
# axis height) is not settled by the sources, so it is a switch, not a decision.
CASEMATE_YS = [54, 48, 42, 36, 30, 24, 18, 12]
CASEMATE_PLACEMENT = 'between_decks'   # or 'on_forecastle'
CASEMATE_BULWARK_H = 1.40

# Damage modules: real volumes so the combat layer has something to hit.
# Sizes are requested footprints; every box is then clamped inside the hull
# section, so a corner can never poke through the shell.
# (name, y centre, z centre, requested size xyz, role, provenance)
DAMAGE_VOLUMES = [
    ('Magazine_A',      60.0, -4.60, ( 9.0,  7.0, 6.0), 'magazine', 'wiki'),
    ('Magazine_B',      46.0, -4.60, ( 9.0,  7.0, 6.0), 'magazine', 'wiki'),
    ('Magazine_Q',      -6.0, -4.60, ( 9.0,  7.0, 6.0), 'magazine', 'wiki'),
    ('Magazine_X',     -71.0, -4.40, ( 9.0,  9.0, 6.0), 'magazine', 'wiki'),
    ('Boiler_Room_1',   33.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Boiler_Room_2',   23.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Boiler_Room_3',   13.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Boiler_Room_4',    3.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Boiler_Room_5',  -15.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Boiler_Room_6',  -25.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Boiler_Room_7',  -35.0, -4.00, (14.0,  9.0, 6.0), 'boiler_room', 'wiki'),
    ('Engine_Room_1',  -47.0, -4.00, (14.0, 14.0, 6.0), 'engine_room', 'wiki'),
    ('Engine_Room_2',  -60.5, -4.00, (14.0,  9.0, 6.0), 'engine_room', 'wiki'),
    ('Steering_Gear',  -96.0, -2.50, ( 7.0,  6.0, 2.5), 'steering_gear', 'estimate'),
]

# Armour: thicknesses are published, extents are estimates.
BELT_YS = (-68.0, 46.0)            # 9 in KC belt between the B and X turrets (wiki)
UPPER_BELT_Z = (1.60, 4.00)
MAIN_BELT_Z = (-1.40, 1.60)
TAPER_Z = (-1.40, 1.40)
ARMOUR_DECKS = [
    ('Armour_Deck_64mm', 0.064, -1.60, 'main deck over magazines, 2.5 in', 'wiki'),
    ('Armour_Deck_25mm', 0.025, -4.60, 'lower armour deck, 1 in', 'wiki'),
]
ARMOUR_BULKHEAD_MM = 102.0         # 4 in transverse bulkheads closing the citadel
INSET = 0.02                       # internal plates sit just inside the shell, never coplanar

FX_ANCHOR_YS = {'FX_Standard_Aft': -90.0}

# --- damage model tables ----------------------------------------------------
# Semantic hit zones: what a penetration model and a damage report need, instead
# of "internal/external".
HIT_ZONE_BY_ROLE = {
    'magazine': 'magazine',
    'boiler_room': 'machinery_space',
    'engine_room': 'machinery_space',
    'steering_gear': 'steering_gear',
    'armour_belt': 'side_armour',
    'armour_deck': 'deck_armour',
    'armour_bulkhead': 'bulkhead_armour',
    'barbette': 'barbette',
    'main_turret': 'turret_body',
    'main_gun_barrel': 'gun_barrel',
    'secondary_gun': 'casemate_battery',
    'casemate_opening': 'casemate_battery',
    'funnel': 'uptake',
    'funnel_uptake': 'uptake',
    'tripod_mast': 'mast',
    'bridge': 'control',
    'conning_tower': 'control',
    'structure': 'superstructure',
    'fire_control': 'fire_control',
    'rudder': 'steering_gear',
    'propulsion_underwater': 'shafting',
    'hull': 'hull_envelope',
    'forecastle_deck': 'hull_envelope',
    'quarterdeck': 'hull_envelope',
    'sternwalk': 'hull_envelope',
    'sternwalk_rail': 'hull_envelope',
    'stowed_net_mesh': 'hull_envelope',
}
PERMEABILITY = {'magazine': 0.95, 'boiler_room': 0.80, 'engine_room': 0.80,
                'steering_gear': 0.85}
# (source, relation, target, status, note). Published facts vs pairings that are
# estimates - the existence of the systems is sourced, the exact pairing is not.
SYSTEM_LINKS = [
    ('Magazine_A', 'feeds_feed_hoist_of', 'Turret_A', 'published', 'turret letter matches its magazine'),
    ('Magazine_B', 'feeds_feed_hoist_of', 'Turret_B', 'published', ''),
    ('Magazine_Q', 'feeds_feed_hoist_of', 'Turret_Q', 'published', ''),
    ('Magazine_X', 'feeds_feed_hoist_of', 'Turret_X', 'published', ''),
    ('Boiler_Room_1', 'supplies_steam_to', 'Engine_Room_1', 'estimate', 'grouping is estimated'),
    ('Boiler_Room_2', 'supplies_steam_to', 'Engine_Room_1', 'estimate', 'grouping is estimated'),
    ('Boiler_Room_3', 'supplies_steam_to', 'Engine_Room_1', 'estimate', 'grouping is estimated'),
    ('Boiler_Room_4', 'supplies_steam_to', 'Engine_Room_2', 'estimate', 'grouping is estimated'),
    ('Boiler_Room_5', 'supplies_steam_to', 'Engine_Room_2', 'estimate', 'grouping is estimated'),
    ('Boiler_Room_6', 'supplies_steam_to', 'Engine_Room_2', 'estimate', 'grouping is estimated'),
    ('Boiler_Room_7', 'supplies_steam_to', 'Engine_Room_2', 'estimate', 'grouping is estimated'),
    ('Engine_Room_1', 'turns', 'Propeller_Shafts', 'published', '4 shafts in 2 engine rooms'),
    ('Engine_Room_2', 'turns', 'Propeller_Shafts', 'published', '4 shafts in 2 engine rooms'),
    ('Steering_Gear', 'actuates', 'Rudder', 'published', 'rudder aft, steering gear below the quarterdeck'),
    ('Funnel_1', 'exhausts', 'Boiler_Room_1', 'estimate', 'smoke source pairing is estimated'),
    ('Funnel_1', 'exhausts', 'Boiler_Room_2', 'estimate', 'smoke source pairing is estimated'),
    ('Funnel_2', 'exhausts', 'Boiler_Room_3', 'estimate', 'smoke source pairing is estimated'),
    ('Funnel_2', 'exhausts', 'Boiler_Room_4', 'estimate', 'smoke source pairing is estimated'),
    ('Funnel_3', 'exhausts', 'Boiler_Room_5', 'estimate', 'smoke source pairing is estimated'),
    ('Funnel_3', 'exhausts', 'Boiler_Room_6', 'estimate', 'smoke source pairing is estimated'),
    ('Funnel_3', 'exhausts', 'Boiler_Room_7', 'estimate', 'smoke source pairing is estimated'),
]
SYSTEM_LINKS += [('Rangefinder_CT', 'provides_fire_control_to', 'Turret_' + key, 'published',
                  'director on the conning tower, 15 deg 21 min limit in 1913') for key in 'ABQX']

ASSET_COLLECTION = None
PREVIEW_COLLECTION = None
MATERIALS = {}
OFFSETS_SOURCE = 'builtin_estimate'
OFFSETS_TABLE = OFFSETS


# --- offsets maths ----------------------------------------------------------
def load_offsets():
    """Allow a real lines plan to replace the estimate without touching code."""
    global OFFSETS_SOURCE, OFFSETS_TABLE
    script = Path(globals().get('__file__', 'queen_mary.py')).resolve().parent
    candidate = script / 'hull_offsets.json'
    if candidate.is_file():
        payload = json.loads(candidate.read_text(encoding='utf-8'))
        rows = payload['stations'] if isinstance(payload, dict) else payload
        table = [tuple(float(v) for v in row) for row in rows]
        if len(table) < 5 or any(len(row) != 5 for row in table):
            raise ValueError('hull_offsets.json must hold 5 numbers per station')
        OFFSETS_TABLE = sorted(table, key=lambda row: row[0])
        note = str(payload.get('sources', '')) if isinstance(payload, dict) else ''
        OFFSETS_SOURCE = candidate.name + ((' | ' + note) if note else '')
    return OFFSETS_TABLE


def station_params(y):
    table = OFFSETS_TABLE
    if y <= table[0][0]:
        return table[0][1:]
    if y >= table[-1][0]:
        return table[-1][1:]
    for row_a, row_b in zip(table, table[1:]):
        if row_a[0] <= y <= row_b[0]:
            span = row_b[0] - row_a[0]
            t = 0.0 if span == 0 else (y - row_a[0]) / span
            return tuple(a + (b - a) * t for a, b in zip(row_a[1:], row_b[1:]))
    raise ValueError('y outside the offsets table: ' + str(y))


def section_profile(deck_hb, wl_hb, keel_z, flat_hb):
    """One section as (z, half-beam) pairs, deck edge down to keel. Fixed length."""
    pts = [(DECK_Z, deck_hb)]
    for z in (3.80, 2.00, 0.60):
        t = (DECK_Z - z) / DECK_Z
        pts.append((z, deck_hb + (wl_hb - deck_hb) * (t ** 0.85)))
    pts.append((0.0, wl_hb))
    for f in (0.14, 0.30, 0.48, 0.66, 0.82, 0.93):
        pts.append((keel_z * f, flat_hb + (wl_hb - flat_hb) * math.cos(math.pi * 0.5 * (f ** 0.92))))
    pts.append((keel_z, flat_hb))
    return pts


def section_loop(y, scale=1.0):
    """Closed section ring: port side deck->keel, then starboard keel->deck."""
    prof = section_profile(*station_params(y))
    ring = [(-hb * scale, y, z) for z, hb in prof]
    ring += [(hb * scale, y, z) for z, hb in reversed(prof[:-1])]
    return ring


def halfbeam_at(y, z):
    prof = section_profile(*station_params(y))
    if z >= prof[0][0]:
        return prof[0][1]
    for (z1, h1), (z2, h2) in zip(prof, prof[1:]):
        if z2 <= z <= z1:
            t = 0.0 if z1 == z2 else (z1 - z) / (z1 - z2)
            return h1 + (h2 - h1) * t
    return prof[-1][1]


def deck_halfbeam(y):
    return station_params(y)[0]


def keel_at(y):
    return station_params(y)[2]


def station_ys():
    return [row[0] for row in OFFSETS_TABLE]


def forecastle_z(y):
    if y < FORE_AFT_END:
        raise ValueError('forecastle does not extend aft of ' + str(FORE_AFT_END))
    s = (y - FORE_AFT_END) / (station_ys()[-1] - FORE_AFT_END)
    return 6.85 + 0.65 * (s ** 0.72)


def quarterdeck_z(y):
    if y > FORE_AFT_END:
        raise ValueError('quarterdeck does not extend forward of ' + str(FORE_AFT_END))
    s = (FORE_AFT_END - y) / (FORE_AFT_END - station_ys()[0])
    return DECK_Z + 0.62 * (s ** 0.85)


def deck_at(y):
    return forecastle_z(y) if y >= FORE_AFT_END else quarterdeck_z(y)


def bridge_base_z():
    return forecastle_z(BRIDGE_Y)


def bridge_top_z():
    return bridge_base_z() + BRIDGE_HEIGHT


def bridge_upper_top_z():
    return bridge_top_z() + BRIDGE_UPPER_HEIGHT


def conning_tower_base_z():
    return forecastle_z(CT_Y)


def conning_tower_top_z():
    return bridge_top_z() + 2.2


def aft_deckhouse_base_z():
    return quarterdeck_z(AFT_Y)


def aft_deckhouse_top_z():
    return aft_deckhouse_base_z() + AFT_DECKHOUSE_HEIGHT


def casemate_axis_z(y):
    if CASEMATE_PLACEMENT == 'on_forecastle':
        return forecastle_z(y) + 1.15
    return DECK_Z + 1.15


# --- mesh primitives --------------------------------------------------------
def loft_rings_mesh(rings, cap_start=True, cap_end=True):
    n = len(rings[0])
    verts = []
    faces = []
    for ring in rings:
        if len(ring) != n:
            raise ValueError('loft rings must have equal length')
        verts.extend(tuple(v) for v in ring)
    for i in range(len(rings) - 1):
        for j in range(n):
            faces.append((i * n + j, i * n + (j + 1) % n,
                          (i + 1) * n + (j + 1) % n, (i + 1) * n + j))
    if cap_start:
        faces.append(tuple(reversed(range(n))))
    if cap_end:
        base = (len(rings) - 1) * n
        faces.append(tuple(range(base, base + n)))
    return verts, faces


def box_mesh(center, size):
    cx, cy, cz = center
    hx, hy, hz = (s / 2.0 for s in size)
    verts = [(cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
             (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
             (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
             (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return verts, faces


def lathe_mesh(profile, vertices=12, axis='Y'):
    """Solid of revolution about the local axis; profile is [(position, radius), ...]."""
    rings = []
    for pos, radius in profile:
        ring = []
        for i in range(vertices):
            ang = 2.0 * math.pi * i / vertices
            a, b = radius * math.cos(ang), radius * math.sin(ang)
            ring.append((a, pos, b) if axis == 'Y' else (a, b, pos))
        rings.append(ring)
    return loft_rings_mesh(rings)


def rod_mesh(start, end, radius, vertices=10):
    a, b = Vector(start), Vector(end)
    delta = b - a
    if delta.length < 1e-9:
        raise ValueError('rod endpoints coincide')
    rotation = delta.to_track_quat('Z', 'Y').to_matrix()
    rings = []
    for z in (0.0, delta.length):
        ring = []
        for i in range(vertices):
            ang = 2.0 * math.pi * i / vertices
            ring.append(tuple(a + rotation @ Vector((radius * math.cos(ang),
                                                     radius * math.sin(ang), z))))
        rings.append(ring)
    return loft_rings_mesh(rings)


def frustum_mesh(outline_low, outline_high, z0, z1):
    return loft_rings_mesh([[(x, y, z0) for x, y in outline_low],
                            [(x, y, z1) for x, y in outline_high]])


def prism_mesh(outline, z0, z1):
    n = len(outline)
    verts = [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return verts, faces


class MeshBuilder:
    """Merge many small primitives into one object, one material per part."""

    def __init__(self, base=(0.0, 0.0, 0.0)):
        self.verts = []
        self.faces = []
        self.mats = []
        self.base = Vector(base)

    def add(self, geometry, material='StructureGrey', offset=(0.0, 0.0, 0.0)):
        verts, faces = geometry
        shift = self.base + Vector(offset)
        start = len(self.verts)
        self.verts.extend(tuple(Vector(v) + shift) for v in verts)
        index = self.mats.index(material) if material in self.mats else None
        if index is None:
            self.mats.append(material)
            index = len(self.mats) - 1
        self.faces.extend((tuple(i + start for i in face), index) for face in faces)
        return self

    def to_object(self, name, parent, role, materials, location=(0.0, 0.0, 0.0)):
        mesh = bpy.data.meshes.new(name + '_Mesh')
        mesh.from_pydata(self.verts, [], [face for face, _ in self.faces])
        mesh.update()
        if len(mesh.polygons) == len(self.faces):
            for polygon, (_, index) in zip(mesh.polygons, self.faces):
                polygon.material_index = index
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        obj = configure_object(bpy.data.objects.new(name, mesh), name, location, parent, role)
        for material in (self.mats or ['StructureGrey']):
            obj.data.materials.append(materials[material])
        return obj


# --- scene plumbing ---------------------------------------------------------
def reset_scene():
    """Remove all scene objects and unused geometry; keep active script texts."""
    global ASSET_COLLECTION, PREVIEW_COLLECTION
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for data in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras,
                 bpy.data.lights, bpy.data.materials):
        for item in list(data):
            if item.users == 0:
                data.remove(item)
    ASSET_COLLECTION = bpy.data.collections.new('01_Ship_Export')
    PREVIEW_COLLECTION = bpy.data.collections.new('90_Preview_Only')
    bpy.context.scene.collection.children.link(ASSET_COLLECTION)
    bpy.context.scene.collection.children.link(PREVIEW_COLLECTION)
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Queen_Mary_World')
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    scene['coordinate_system'] = 'X starboard / Y bow / Z up / waterline Z=0'
    scene['geometry_status'] = 'Greybox approximation; no hull lines or armour certification'
    scene['asset_version'] = 'v2'


#: 材质规格：名字 → 线性灰度。**这是灰度的唯一来源** —— Blender 用它建材质，
#: 契约把同一张表交给 Unity 侧建 URP 材质。两边各写一份必然漂。
MATERIAL_SPECS = [('HullGrey', .34), ('DeckGrey', .47), ('StructureGrey', .56),
                  ('DarkGrey', .20), ('Black', .065), ('UnderwaterGrey', .245)]
MATERIAL_ROUGHNESS = .85


def make_materials():
    for name, grey in MATERIAL_SPECS:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = (grey, grey, grey, 1)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (grey, grey, grey, 1)
        bsdf.inputs['Roughness'].default_value = MATERIAL_ROUGHNESS
        MATERIALS[name] = mat


def configure_object(obj, name, position, parent, role, material=None):
    obj.name = name
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    ASSET_COLLECTION.objects.link(obj)
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = position
    obj['component_role'] = role
    obj['component_id'] = name
    obj['export_asset'] = True
    obj['dimensions_status'] = 'estimated_greybox'
    if material:
        obj.data.materials.append(MATERIALS[material])
    return obj


def empty(name, position=(0, 0, 0), parent=None, role='group'):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = 1.5
    return configure_object(obj, name, position, parent, role)


def mesh_object(name, verts, faces, parent, material, role, position=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return configure_object(bpy.data.objects.new(name, mesh), name, position, parent, role, material)


def box(name, position, size, parent, material='StructureGrey', role='structure'):
    return mesh_object(name, *box_mesh((0, 0, 0), size), parent, material, role, position)


def cylinder(name, position, radius, depth, parent, material='StructureGrey',
             role='structure', ellipse=(1, 1), vertices=24):
    verts, faces = lathe_mesh([(0.0, radius), (depth, radius)], vertices=vertices, axis='Z')
    verts = [(x * ellipse[0], y * ellipse[1], z - depth / 2.0) for x, y, z in verts]
    return mesh_object(name, verts, faces, parent, material, role, position)


# --- modules ----------------------------------------------------------------
def make_hull(root):
    rings = [section_loop(y) for y in station_ys()]
    hull = mesh_object('Hull', *loft_rings_mesh(rings), root, 'HullGrey', 'hull')
    hull['dimensions_status'] = 'specified_overall_dimensions_estimated_sections'
    hull['offsets_source'] = OFFSETS_SOURCE
    hull['sections_status'] = ('estimated until a lines plan is supplied; drop '
                               'hull_offsets.json next to queen_mary.py to replace')
    hull.data.materials.append(MATERIALS['UnderwaterGrey'])
    hull.data.materials.append(MATERIALS['DeckGrey'])
    for face in hull.data.polygons:
        z = sum(hull.data.vertices[i].co.z for i in face.vertices) / len(face.vertices)
        face.material_index = 1 if z < 0 else 2 if z > 5 else 0
    return hull


def deck_slab(name, ys, z_bottom, z_top, parent, material, role):
    rings = []
    for y in ys:
        hb = deck_halfbeam(y)
        top = z_top(y) if callable(z_top) else z_top
        rings.append([(-hb, y, z_bottom), (-hb, y, top), (hb, y, top), (hb, y, z_bottom)])
    return mesh_object(name, *loft_rings_mesh(rings), parent, material, role)


def hull_plate(name, ys, z_lo, z_hi, thickness, parent, role,
               material='DarkGrey', offset=0.0, sides=(1, -1)):
    """Thin plate following the hull side; one loft per side so nothing bridges across."""
    builder = MeshBuilder()
    for side in sides:
        rings = []
        for y in ys:
            outer_lo = halfbeam_at(y, z_lo) - offset
            outer_hi = halfbeam_at(y, z_hi) - offset
            rings.append([(side * outer_lo, y, z_lo), (side * outer_hi, y, z_hi),
                          (side * (outer_hi - thickness), y, z_hi),
                          (side * (outer_lo - thickness), y, z_lo)])
        builder.add(loft_rings_mesh(rings), material)
    return builder.to_object(name, parent, role, MATERIALS)


def make_decks(root):
    ys = station_ys()
    fore_ys = [y for y in ys if y >= FORE_AFT_END]
    aft_ys = [y for y in ys if y <= FORE_AFT_END]
    forecastle = deck_slab('Forecastle', fore_ys, DECK_Z - 0.05, forecastle_z,
                           root, 'DeckGrey', 'forecastle_deck')
    forecastle['sheer'] = 'rises from {:.2f} m at Y={:.0f} to {:.2f} m at the stem (estimate)'.format(
        forecastle_z(FORE_AFT_END), FORE_AFT_END, forecastle_z(ys[-1]))
    quarterdeck = deck_slab('Quarterdeck', aft_ys, DECK_Z - 0.05, quarterdeck_z,
                            root, 'DeckGrey', 'quarterdeck')
    quarterdeck['sheer'] = 'rises from {:.2f} m at Y={:.0f} to {:.2f} m at the stern (estimate)'.format(
        quarterdeck_z(FORE_AFT_END), FORE_AFT_END, quarterdeck_z(ys[0]))
    if CASEMATE_PLACEMENT == 'on_forecastle':
        bulwark_ys = [y for y in fore_ys if y >= min(CASEMATE_YS) - 6]
        builder = MeshBuilder()
        for side in (1, -1):
            rings = []
            for y in bulwark_ys:
                hb = deck_halfbeam(y)
                z_lo = forecastle_z(y) + 0.02
                z_hi = z_lo + CASEMATE_BULWARK_H
                rings.append([(side * hb, y, z_lo), (side * hb, y, z_hi),
                              (side * (hb - 0.07), y, z_hi), (side * (hb - 0.07), y, z_lo)])
            builder.add(loft_rings_mesh(rings), 'HullGrey')
        bulwark = builder.to_object('Forecastle_Bulwark', root, 'bulwark', MATERIALS)
        bulwark['note'] = 'only built in the on_forecastle casemate arrangement'
    return forecastle, quarterdeck


def make_superstructure(root):
    sup = empty('Superstructure', parent=root)
    b_deck = forecastle_z(TURRETS['B'][0])
    box('B_Superfiring_Deckhouse', (0, TURRETS['B'][0], (b_deck + SUPERFIRING_DECK_Z) / 2),
        (11.8, 14, SUPERFIRING_DECK_Z - b_deck), sup)
    bridge = box('Bridge', (0, BRIDGE_Y, bridge_base_z() + BRIDGE_HEIGHT / 2),
                 (12.4, 12, BRIDGE_HEIGHT), sup, role='bridge')
    box('Bridge_Upper', (0, BRIDGE_Y - 1.0, bridge_top_z() + BRIDGE_UPPER_HEIGHT / 2),
        (8.6, 7, BRIDGE_UPPER_HEIGHT), sup)
    box('Bridge_Wings', (0, BRIDGE_Y - 0.5, bridge_top_z() + 0.06), (17.0, 5.0, 0.55), sup, 'DeckGrey')
    box('Bridge_Visor', (0, BRIDGE_Y - 1.0, bridge_upper_top_z() + 0.175), (10.2, 8, .35), sup, 'DarkGrey')
    ct_base = conning_tower_base_z()
    ct_top = conning_tower_top_z()
    cylinder('Conning_Tower', (0, CT_Y, (ct_base + ct_top) / 2), 3.0, ct_top - ct_base,
             sup, 'DarkGrey', 'conning_tower')
    uptakes = MeshBuilder()
    for index, (y, rx, ry) in FUNNELS.items():
        base = deck_at(y) + FUNNEL_UPTAKE_H
        box('Funnel_{}_Uptake'.format(index), (0, y, (deck_at(y) + base) / 2),
            (rx * 2.4, ry * 2.6, base - deck_at(y)), sup, 'HullGrey', role='funnel_uptake')
    box('Aft_Deckhouse', (0, AFT_Y, (aft_deckhouse_base_z() + aft_deckhouse_top_z()) / 2),
        (12.4, 23, AFT_DECKHOUSE_HEIGHT), sup)
    box('Aft_Platform', (0, AFT_Y - 1.0, aft_deckhouse_top_z() + 0.18), (15, 24, .35), sup, 'DeckGrey')
    return sup


def make_turret(key, root):
    y, deck_source, barbette, yaw = TURRETS[key]
    deck = SUPERFIRING_DECK_Z if deck_source == 'superfiring' else deck_at(y)
    base = deck + barbette
    barbette_obj = cylinder('Barbette_' + key, (0, y, (deck + base + INSET) / 2), 4.9,
                            max(base + INSET - deck, 0.2), root, 'DarkGrey', 'barbette', vertices=32)
    barbette_obj['armour_mm_above_deck'] = 229
    barbette_obj['armour_mm_below_deck'] = 203
    barbette_obj['source'] = SOURCES['wiki']

    low = [(-4.5, -4.3), (4.5, -4.3), (4.9, -2.8), (4.9, 2.8),
           (3.6, 4.8), (-3.6, 4.8), (-4.9, 2.8), (-4.9, -2.8)]
    high = [(-4.15, -4.05), (4.15, -4.05), (4.5, -2.6), (4.5, 2.5),
            (3.3, 4.3), (-3.3, 4.3), (-4.5, 2.5), (-4.5, -2.6)]
    builder = MeshBuilder()
    builder.add(frustum_mesh(low, high, 0.0, TURRET_HEIGHT_M), 'StructureGrey')
    for sight_x in (-2.6, 2.6):
        builder.add(box_mesh((sight_x, -3.4, TURRET_HEIGHT_M + 0.35), (1.5, 1.8, 0.7)), 'DarkGrey')
    turret = builder.to_object('Turret_' + key, root, 'main_turret', MATERIALS, (0, y, base))
    turret.rotation_euler.z = math.radians(yaw)
    turret['yaw_axis_local'] = '+Z'
    turret['rest_forward_local'] = '+Y'
    turret['calibre_mm'] = 343
    turret['barrels'] = 2
    turret['mount_base_z_m'] = base
    turret['deck_source'] = deck_source
    turret['armour_face_mm'] = 229
    turret['armour_roof_mm'] = '64-83'
    turret['rangefinder'] = '9 ft rangefinder in each turret (wiki)'

    pitch = empty('Elevation_' + key, (0, TRUNNION_Y_M, 1.5), turret, 'gun_elevation')
    pitch['pitch_axis_local'] = '+X'
    pitch['positive_rotation'] = 'raises barrels'
    pitch['max_elevation_mount_deg'] = SHIP['max_elevation_mount_deg']
    pitch['min_elevation_mount_deg'] = SHIP['min_elevation_mount_deg']
    pitch['max_elevation_director_deg'] = SHIP['max_elevation_director_deg']
    for side, x in [('Port', -1.25), ('Starboard', 1.25)]:
        profile = [(-0.15, 0.55), (0.40, 0.50), (2.60, 0.49), (2.62, 0.36),
                   (11.95, 0.33), (11.97, 0.42), (BARREL_END_M, 0.42)]
        verts, faces = lathe_mesh(profile, vertices=16, axis='Y')
        verts = [(vx + x, vy, vz) for vx, vy, vz in verts]
        barrel = mesh_object('Barrel_{}_{}'.format(key, side), verts, faces, pitch,
                             'DarkGrey', 'main_gun_barrel')
        barrel['calibre_mm'] = 343
        barrel['barrel_end_local_y_m'] = BARREL_END_M
        barrel['trunnion_local_y_m'] = 0.0
        barrel['data_status'] = 'chase length estimated; origin is the barrel trunnion'
    return turret


def make_casemates(root):
    for side, sign in [('Port', -1), ('Starboard', 1)]:
        openings = MeshBuilder()
        for index, y in enumerate(CASEMATE_YS, 1):
            axis = casemate_axis_z(y)
            surface = deck_halfbeam(y) if CASEMATE_PLACEMENT == 'on_forecastle' \
                else halfbeam_at(y, axis)
            openings.add(box_mesh((sign * (surface + 0.03), y, axis), (0.16, 2.45, 1.30)), 'Black')
            gun = mesh_object('Casemate_{}_{}'.format(side, index),
                              *lathe_mesh([(-0.40, 0.14), (2.45, 0.14)], vertices=12, axis='Y'),
                              parent=root, material='DarkGrey', role='secondary_gun',
                              position=(sign * surface, y, axis))
            gun.rotation_euler.z = math.radians(90.0 if side == 'Port' else -90.0)
            gun['side'] = side
            gun['calibre_mm'] = 102
            gun['axis_z_m'] = round(axis, 4)
            gun['deck_mode'] = CASEMATE_PLACEMENT
            gun['train_axis_local'] = '+Z'
            gun['rest_forward_local'] = '+Y (outboard)'
            gun['max_train_deg'] = 35.0
            gun['layout_status'] = 'user_spec_8_per_side_on_one_deck; axis height unverified'
            gun['layout_source'] = SOURCES['wiki']
        obj = openings.to_object('Casemate_Openings_' + side, root, 'casemate_opening', MATERIALS)
        obj['openings'] = len(CASEMATE_YS)
        obj['placement'] = CASEMATE_PLACEMENT


def make_funnels(root):
    for index, (y, rx, ry) in FUNNELS.items():
        base = deck_at(y) + FUNNEL_UPTAKE_H
        depth = FUNNEL_TOP_Z - base
        builder = MeshBuilder()
        builder.add(lathe_mesh([(-INSET, 1.0), (depth, 1.0)], vertices=32, axis='Z'), 'HullGrey')
        builder.add(lathe_mesh([(depth - 1.0, 1.04), (depth, 1.04)], vertices=32, axis='Z'), 'Black')
        funnel = builder.to_object('Funnel_{}'.format(index), root, 'funnel', MATERIALS, (0, y, base))
        funnel.data.transform(Matrix.Diagonal(Vector((rx, ry, 1.0, 1.0))))
        funnel['section'] = 'circular' if abs(rx - ry) < 1e-6 else 'elliptical'
        funnel['casing_axis_radius_m'] = [rx, ry]
        funnel['top_z_m'] = FUNNEL_TOP_Z
        funnel['section_source'] = SOURCES['ww1']
        funnel['uptake_armour_mm'] = 38
        funnel['internal_uptakes'] = False


def make_mast(name, y, base, height, root, spread):
    builder = MeshBuilder()
    meeting = (0.0, 0.0, height * 0.68)
    for start in [(0, spread, 0), (-spread, -spread * .65, 0), (spread, -spread * .65, 0)]:
        builder.add(rod_mesh(start, meeting, .30 if name == 'Mast_Fore' else .22, 12), 'DarkGrey')
    builder.add(rod_mesh(meeting, (0, 0, height), .16, 10), 'DarkGrey')
    for fraction in (.76, .90):
        width = 5.0 if name == 'Mast_Fore' else 3.4
        builder.add(rod_mesh((-width, 0, height * fraction), (width, 0, height * fraction),
                             .085, 8), 'DarkGrey')
    platform_r = 2.1 if name == 'Mast_Fore' else 1.35
    builder.add(lathe_mesh([(0.0, platform_r), (.75, platform_r)], 12, axis='Z'),
                'StructureGrey', offset=(0, 0, height * 0.68))
    mast = builder.to_object(name, root, 'tripod_mast', MATERIALS, (0, y, base))
    mast['spread_m'] = spread
    mast['legs'] = 3
    mast['height_m'] = height
    mast['historical_status'] = ('two tripod masts are a user requirement; ww1 says she '
                                 'was originally fitted with a pole mast and altered to a '
                                 'tripod later - needs a dated photo')
    mast['source'] = SOURCES['ww1']
    return mast


def make_sternwalk(root):
    """U-shaped gallery derived from the hull surface, so it can never float."""
    half_width = 1.30
    ys = [-98.0, -100.0, -102.0, -104.0, -105.5, -106.5]
    z0 = quarterdeck_z(-102.0) - 2.45

    def edge(y, extra):
        return halfbeam_at(y, z0) + extra

    outer = [(edge(y, half_width), y) for y in ys] + \
            [(-edge(y, half_width), y) for y in reversed(ys)]
    inner = [(edge(y, 0.0), y) for y in ys] + [(-edge(y, 0.0), y) for y in reversed(ys)]
    outline = outer + list(reversed(inner))
    walk = mesh_object('Sternwalk', *prism_mesh(outline, z0 - 0.18, z0 + 0.18),
                       root, 'DeckGrey', 'sternwalk')
    walk['projection_m'] = half_width
    walk['derived_from'] = 'halfbeam_at(y, z) - never hand-placed'
    walk['note'] = 'first British battlecruiser with a sternwalk (wiki)'
    rails = MeshBuilder()
    for y in ys:
        for sign in (1, -1):
            rails.add(rod_mesh((sign * edge(y, half_width), y, z0 + 0.18),
                               (sign * edge(y, half_width), y, z0 + 1.15), .065, 8), 'DarkGrey')
    for y_a, y_b in zip(ys, ys[1:]):
        for sign in (1, -1):
            rails.add(rod_mesh((sign * edge(y_a, half_width), y_a, z0 + 1.15),
                               (sign * edge(y_b, half_width), y_b, z0 + 1.15), .065, 8), 'DarkGrey')
    rails.to_object('Sternwalk_Rails', walk, 'sternwalk_rail', MATERIALS)
    return walk


def make_nets(root):
    for side, sign in [('Port', -1), ('Starboard', 1)]:
        group = empty('Torpedo_Net_{}_Stowed'.format(side), parent=root, role='stowed_net')
        builder = MeshBuilder()
        z_net = 4.40
        segments = [-80, -65, -40, -18, 15, 40, 60, 76]
        for y_a, y_b in zip(segments, segments[1:]):
            builder.add(rod_mesh((sign * (halfbeam_at(y_a, z_net) + .32), y_a, z_net),
                                 (sign * (halfbeam_at(y_b, z_net) + .32), y_b, z_net), .24, 8),
                        'DarkGrey')
        for y in range(-76, 73, 12):
            builder.add(rod_mesh((sign * (halfbeam_at(y, 1.7) + .38), y, 1.7),
                                 (sign * (halfbeam_at(y + 5, 4.7) + .43), y + 5, 4.7), .13, 8),
                        'DarkGrey')
        obj = builder.to_object('Torpedo_Net_{}_Mesh'.format(side), group,
                                'stowed_net_mesh', MATERIALS)
        obj['rendered_as'] = 'merged bundles and booms (decoration only)'
        obj['stowed'] = True


def make_underwater_gear(root):
    builder = MeshBuilder()
    for sign in (1, -1):
        for offset in (3.6, 8.2):
            hub = (sign * offset, -101.4, -5.2)
            builder.add(rod_mesh((sign * offset, -45.0, -6.4), hub, 0.32, 10), 'DarkGrey')
            builder.add(rod_mesh((hub[0], hub[1] - 0.5, hub[2]), (hub[0], hub[1] + 0.4, hub[2]),
                                 0.55, 10), 'DarkGrey')
            for blade in range(4):
                angle = math.radians(45 + 90 * blade)
                tip = (hub[0] + 2.3 * math.cos(angle), hub[1], hub[2] + 2.3 * math.sin(angle))
                builder.add(rod_mesh(hub, tip, 0.30, 8), 'DarkGrey')
    shafts = builder.to_object('Propeller_Shafts', root, 'propulsion_underwater', MATERIALS)
    shafts['note'] = 'four shafts and propellers, merged as scenery; not a damage module'
    rudder = mesh_object('Rudder', *box_mesh((0, -103.6, -4.6), (0.42, 5.6, 6.8)),
                         root, 'DarkGrey', 'rudder')
    rudder['note'] = 'steering gear damage module sits inboard at Y=-96'
    return shafts, rudder


def make_armour(root):
    ys = station_ys()
    belt_lo, belt_hi = BELT_YS
    belt_ys = [y for y in ys if belt_lo <= y <= belt_hi]
    entries = [
        ('Armour_Belt_229mm', belt_ys, 0.229, MAIN_BELT_Z, 'main waterline belt, 9 in KC'),
        ('Armour_Upper_Belt_152mm', belt_ys, 0.152, UPPER_BELT_Z, 'upper belt, 6 in'),
        ('Armour_Belt_Taper_102mm_Fwd',
         [y for y in ys if y > belt_hi and halfbeam_at(y, TAPER_Z[0]) > 0.8], 0.102, TAPER_Z,
         'belt taper to the bow, 4 in (stops short of the stem where there is no breadth)'),
        ('Armour_Belt_Taper_102mm_Aft',
         [y for y in ys if y < belt_lo and halfbeam_at(y, TAPER_Z[0]) > 0.8], 0.102, TAPER_Z,
         'belt taper to the stern, 4 in (stops short of the counter tip)'),
    ]
    for name, plate_ys, thickness, (z_lo, z_hi), note in entries:
        obj = hull_plate(name, plate_ys, z_lo, z_hi, thickness, root, 'armour_belt',
                         offset=INSET)
        obj['armour_mm'] = thickness * 1000.0
        obj['note'] = note
        obj['extent_status'] = 'estimated'
        obj['source'] = SOURCES['wiki']
    for name, thickness, z_lo, note, source in ARMOUR_DECKS:
        deck_ys = [y for y in ys if keel_at(y) <= z_lo - 0.4]
        rings = []
        for y in deck_ys:
            lo = halfbeam_at(y, z_lo) - INSET
            hi = halfbeam_at(y, z_lo + 0.02) - INSET
            rings.append([(-lo, y, z_lo), (-hi, y, z_lo + thickness),
                          (hi, y, z_lo + thickness), (lo, y, z_lo)])
        obj = mesh_object(name, *loft_rings_mesh(rings), root, 'DarkGrey', 'armour_deck')
        obj['armour_mm'] = thickness * 1000.0
        obj['note'] = note
        obj['source'] = SOURCES[source]
    for tag, y in (('Fwd', belt_hi), ('Aft', belt_lo)):
        bulk = mesh_object('Armour_Bulkhead_' + tag,
                           *loft_rings_mesh([section_loop(y - 0.05, 0.94),
                                             section_loop(y + 0.05, 0.94)]),
                           root, 'DarkGrey', 'armour_bulkhead')
        bulk['armour_mm'] = ARMOUR_BULKHEAD_MM
        bulk['note'] = '4 in transverse bulkhead closing the citadel'
        bulk['source'] = SOURCES['wiki']


def fit_module(y, z_centre, size):
    """Clamp a requested box inside the hull section so no corner leaves the shell."""
    sx, sy, sz = size
    keel = keel_at(y)
    z_lo = max(z_centre - sz / 2.0, keel + 0.35)
    z_hi = min(z_centre + sz / 2.0, DECK_Z - 0.35)
    if z_hi - z_lo < 0.5:
        z_lo = keel + 0.35
        z_hi = min(keel + 1.5, DECK_Z - 0.35)
    allowed = min(halfbeam_at(y, z_lo + (z_hi - z_lo) * i / 4.0) for i in range(5)) - 0.45
    fitted_x = min(sx, max(2.0 * allowed, 1.0))
    fitted = (fitted_x, sy, z_hi - z_lo)
    clamped = abs(fitted_x - sx) > 1e-6 or abs((z_hi - z_lo) - sz) > 1e-6
    return fitted, (z_lo + z_hi) / 2.0, clamped


def make_damage_modules(root):
    modules = empty('Damage_Modules', parent=root, role='module_group')
    for name, y, z, size, role_name, source in DAMAGE_VOLUMES:
        fitted, z_centre, clamped = fit_module(y, z, size)
        obj = box(name, (0, y, z_centre), fitted, modules, 'DarkGrey', role_name)
        obj['placeholder_only'] = False
        obj['volume_defined'] = True
        obj['hit_zone'] = 'internal'
        obj['extent_status'] = 'estimated'
        obj['size_m'] = [round(v, 3) for v in fitted]
        obj['requested_size_m'] = [round(v, 3) for v in size]
        obj['clamped_to_hull'] = clamped
        obj['source'] = SOURCES[source]
        if role_name == 'magazine':
            obj['shell_rooms'] = True
            obj['protection_mm'] = '2.5 in high tensile over the magazine (wiki)'
        if role_name == 'boiler_room':
            obj['boilers'] = 6
            obj['fuel'] = 'coal fired with oil spray'
    return modules


def make_fire_control(root, sup):
    builder = MeshBuilder()
    z = conning_tower_top_z() + 0.9
    builder.add(box_mesh((0, 0, 0), (3.6, 3.0, 1.8)), 'StructureGrey')
    builder.add(lathe_mesh([(-1.37, 0.16), (1.37, 0.16)], 12, axis='Y'), 'DarkGrey')
    obj = builder.to_object('Rangefinder_CT', sup, 'fire_control', MATERIALS, (0, CT_Y, z))
    obj['type'] = '9 ft rangefinder and director on the conning tower top (2.74 m baseline)'
    obj['support'] = 'sits on Conning_Tower top at {:.3f} m'.format(conning_tower_top_z())
    obj['fire_control_system'] = 'Pollen Argo Clock Mk IV (wiki)'
    obj['source'] = SOURCES['wiki']
    obj['placeholder_only'] = False
    return obj


def make_fx_anchors(root):
    group = empty('FX_Anchors', parent=root, role='fx_group')
    anchors = [('FX_Funnel_{}_Smoke'.format(index), (0, y, FUNNEL_TOP_Z), 'smoke')
               for index, (y, _, _) in FUNNELS.items()]
    anchors.append(('FX_Mast_Fore_Top', (0, BRIDGE_Y, bridge_upper_top_z() + 24.0), 'anchor'))
    anchors.append(('FX_Mast_Main_Top', (0, -38.0, aft_deckhouse_top_z() + 23.0), 'anchor'))
    anchors.append(('FX_Standard_Aft', (0, FX_ANCHOR_YS['FX_Standard_Aft'],
                                        quarterdeck_z(FX_ANCHOR_YS['FX_Standard_Aft']) + 0.35),
                    'anchor'))
    for name, position, kind in anchors:
        obj = empty(name, position, group, 'fx_anchor')
        obj['fx_type'] = kind
    return group


def build_ship():
    load_offsets()
    reset_scene()
    make_materials()
    root = empty('Queen_Mary', role='ship_root')
    for key, value in SHIP.items():
        root[key] = value
    root['offsets_source'] = OFFSETS_SOURCE
    root['casemate_placement'] = CASEMATE_PLACEMENT
    make_hull(root)
    make_decks(root)
    sup = make_superstructure(root)
    for key in TURRETS:
        make_turret(key, root)
    make_casemates(root)
    make_funnels(root)
    make_mast('Mast_Fore', BRIDGE_Y, bridge_upper_top_z(), 24.0, root, 2.5)
    make_mast('Mast_Main', -38.0, aft_deckhouse_top_z(), 23.0, root, 2.3)
    make_sternwalk(root)
    make_nets(root)
    make_underwater_gear(root)
    make_armour(root)
    make_damage_modules(root)
    make_fire_control(root, sup)
    make_fx_anchors(root)
    apply_system_links(root)
    bpy.context.view_layer.update()
    return root


# --- damage model, hydrostatics and game contract ---------------------------
def turret_deck_and_base(key):
    y, deck_source, barbette, _ = TURRETS[key]
    deck = SUPERFIRING_DECK_Z if deck_source == 'superfiring' else deck_at(y)
    return deck, deck + barbette


def section_immersed_area(y):
    """Moulded area below the design waterline at this station, in m2."""
    prof = section_profile(*station_params(y))
    area = 0.0
    for (z1, h1), (z2, h2) in zip(prof, prof[1:]):
        z_hi, z_lo = min(z1, 0.0), min(z2, 0.0)
        if z_hi <= z_lo:
            continue
        span = z1 - z2
        b_hi = h1 if span == 0 else h1 + (h2 - h1) * (z1 - z_hi) / span
        b_lo = h1 if span == 0 else h1 + (h2 - h1) * (z1 - z_lo) / span
        area += (b_hi + b_lo) * (z_hi - z_lo)
    return area


def section_immersed_moment_z(y):
    """First moment about z=0 of the immersed section, in m3 per metre."""
    prof = section_profile(*station_params(y))
    moment = 0.0
    for (z1, h1), (z2, h2) in zip(prof, prof[1:]):
        z_hi, z_lo = min(z1, 0.0), min(z2, 0.0)
        if z_hi <= z_lo:
            continue
        span = z1 - z2
        b_hi = h1 if span == 0 else h1 + (h2 - h1) * (z1 - z_hi) / span
        b_lo = h1 if span == 0 else h1 + (h2 - h1) * (z1 - z_lo) / span
        moment += (z_hi * (2.0 * b_hi + b_lo) + z_lo * (b_hi + 2.0 * b_lo)) / 3.0 * (z_hi - z_lo)
    return moment


def hull_hydrostatics(subdivisions=4):
    """Integrate the offsets table: volume, waterplane, centres of buoyancy.

    This is an independent check on the estimated sections: the immersed volume at
    the deep-load waterline must be consistent with the published displacement.
    """
    ys = station_ys()
    grid = []
    for y_a, y_b in zip(ys, ys[1:]):
        grid.extend(y_a + (y_b - y_a) * i / float(subdivisions) for i in range(subdivisions))
    grid.append(ys[-1])
    volume = moment_y = moment_z = waterplane = 0.0
    for y_a, y_b in zip(grid, grid[1:]):
        areas = [section_immersed_area(y) for y in (y_a, (y_a + y_b) / 2.0, y_b)]
        moments = [section_immersed_moment_z(y) for y in (y_a, (y_a + y_b) / 2.0, y_b)]
        seg = (y_b - y_a) / 6.0
        volume += seg * (areas[0] + 4.0 * areas[1] + areas[2])
        moment_z += seg * (moments[0] + 4.0 * moments[1] + moments[2])
        moment_y += seg * (areas[0] * y_a + 4.0 * areas[1] * (y_a + y_b) / 2.0 + areas[2] * y_b)
        waterplane += seg * (2.0 * halfbeam_at(y_a, 0.0) + 4.0 * halfbeam_at((y_a + y_b) / 2.0, 0.0)
                             + 2.0 * halfbeam_at(y_b, 0.0))
    return {
        'method': 'moulded sections integrated over the offsets table (Simpson in y)',
        'design_waterline_z_m': 0.0,
        'keel_z_m': round(min(keel_at(y) for y in ys), 3),
        'immersed_volume_m3': round(volume, 1),
        'waterplane_area_m2': round(waterplane, 1),
        'lcb_y_m': round(moment_y / volume, 3) if volume else None,
        'vcb_z_m': round(moment_z / volume, 3) if volume else None,
        'displacement_t_at_1_025': round(volume * 1.025, 1),
        'published_displacement_t': {'normal': SHIP['displacement_normal_t'],
                                     'deep_load': SHIP['displacement_full_t']},
        'displacement_delta_pct': round(
            100.0 * (volume * 1.025 - SHIP['displacement_full_t']) / SHIP['displacement_full_t'], 2),
        'note': ('moulded volume; excludes shell plating, appendages and openings. '
                 'Compare with the deep-load displacement because the keel sits at the '
                 'deep-load draught. A large gap means the estimated sections are too '
                 'full or too fine.'),
        'source': SOURCES['estimate'] + ' | ' + SOURCES['wiki'],
    }


def apply_system_links(root):
    """Record the system graph on the objects so the model carries it, not only the JSON."""
    for source, relation, target, status, note in SYSTEM_LINKS:
        if source not in bpy.data.objects or target not in bpy.data.objects:
            raise ValueError('system link references a missing object: {} -> {}'.format(source, target))
        obj = bpy.data.objects[source]
        existing = list(obj.get('system_links') or [])
        obj['system_links'] = existing + ['{}:{}:{}'.format(relation, target, status)]
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or not obj.get('component_role'):
            continue
        zone = HIT_ZONE_BY_ROLE.get(obj['component_role'])
        if zone:
            obj['hit_zone'] = zone
        obj['exposure'] = ('internal' if obj['component_role'] in
                           ('magazine', 'boiler_room', 'engine_room', 'steering_gear',
                            'armour_belt', 'armour_deck', 'armour_bulkhead') else 'external')


def nominal_side_protection_mm(y):
    return 229 if BELT_YS[0] <= y <= BELT_YS[1] else 102


def build_damage_model(rows):
    zones = {}
    for row in rows:
        zone = HIT_ZONE_BY_ROLE.get(row.get('role'))
        if zone:
            zones.setdefault(zone, []).append(row['name'])
    systems = {'gunnery': [], 'propulsion': [], 'steering': [], 'fire_control': []}
    relations = {'feeds_feed_hoist_of': 'gunnery', 'supplies_steam_to': 'propulsion',
                 'turns': 'propulsion', 'exhausts': 'propulsion', 'actuates': 'steering',
                 'provides_fire_control_to': 'fire_control'}
    for source, relation, target, status, note in SYSTEM_LINKS:
        systems[relations[relation]].append({'source': source, 'relation': relation,
                                             'target': target, 'status': status, 'note': note})
    by_name = {row['name']: row for row in rows}
    protected = []
    for name, y, _, _, role_name, source in DAMAGE_VOLUMES:
        row = by_name.get(name)
        if not row:
            continue
        protected.append({
            'module': name, 'role': role_name, 'hit_zone': HIT_ZONE_BY_ROLE.get(role_name),
            'side_protection_mm': nominal_side_protection_mm(y),
            'deck_protection_mm': 64 if role_name == 'magazine' else 25,
            'bulkhead_protection_mm': ARMOUR_BULKHEAD_MM,
            'extent_status': 'estimated', 'source': SOURCES[source],
        })
    return {
        'method': 'semantic hit zones, armour coverage and system graph derived from module data',
        'accuracy': 'hit zones are exact for this asset; armour extents and system pairings are estimates',
        'hit_zones': {zone: sorted(names) for zone, names in sorted(zones.items())},
        'armoured_modules': protected,
        'systems': systems,
        'catastrophic_risk': [
            'Magazine_A/B/Q/X: penetration to the magazine is what destroyed the ship at Jutland '
            '(wiki: shells from Derfflinger, magazines exploded)',
            'Steering_Gear: single steering gear, no redundancy',
        ],
        'notes': [
            'Damage volumes are collision-only: keep them off the render layer.',
            'Q turret has a restricted arc and sits between the boiler room groups - '
            'a hit there can take out machinery as well as gunnery.',
            'Engine room and boiler room grouping is estimated, not sourced.',
        ],
    }


def build_buoyancy(rows):
    compartments = []
    total_volume = total_floodable = 0.0
    for row in rows:
        role = row.get('role')
        if role not in PERMEABILITY:
            continue
        mn, mx = row['bounds_world_m']['min'], row['bounds_world_m']['max']
        size = [mx[i] - mn[i] for i in range(3)]
        volume = size[0] * size[1] * size[2]
        below_height = max(0.0, min(mx[2], 0.0) - mn[2])
        below = size[0] * size[1] * below_height
        permeability = PERMEABILITY[role]
        floodable = below * permeability
        total_volume += volume
        total_floodable += floodable
        compartments.append({
            'module': row['name'], 'role': role,
            'volume_m3': round(volume, 1),
            'centroid_world_m': [round((mn[i] + mx[i]) / 2.0, 3) for i in range(3)],
            'below_waterline_volume_m3': round(below, 1),
            'above_waterline_volume_m3': round(volume - below, 1),
            'permeability': permeability,
            'floodable_volume_m3': round(floodable, 1),
            'flooding_effect': ('reserve buoyancy loss' if below else 'no direct buoyancy effect'),
        })
    return {
        'method': 'compartment boxes from the damage volumes, axis aligned',
        'accuracy': 'volumes are estimates; extent_status on each module applies',
        'design_waterline_z_m': 0.0,
        'compartment_volume_total_m3': round(total_volume, 1),
        'floodable_volume_total_m3': round(total_floodable, 1),
        'floodable_share_of_immersed_volume_pct': None,   # filled in by the caller
        'compartments': compartments,
        'notes': [
            'A compartment fully flooded removes its waterplane area and its buoyancy; '
            'the total here is a starting point for a flooding model, not a stability calculation.',
            'Watertight subdivision between these volumes is not modelled yet.',
        ],
    }


def build_ship_contract(rows):
    """Flat, JsonUtility-friendly contract for the Unity side. No hand copying."""
    by_role = {}
    for row in rows:
        if row.get('role'):
            by_role.setdefault(row['role'], []).append(row['name'])
    turrets = []
    for key in TURRETS:
        _, base = turret_deck_and_base(key)
        turrets.append({
            'key': key, 'turret': 'Turret_' + key, 'pivot': 'Elevation_' + key,
            'barbette': 'Barbette_' + key,
            'barrels': sorted(name for name in by_role.get('main_gun_barrel', [])
                              if name.startswith('Barrel_' + key + '_')),
            'base_z_m': round(base, 3),
            'rest_yaw_deg': float(TURRETS[key][3]),
            'trunnion_local_y_m': TRUNNION_Y_M,
            'barrel_end_local_y_m': BARREL_END_M,
            'turret_height_m': TURRET_HEIGHT_M,
            'min_elevation_deg': SHIP['min_elevation_mount_deg'],
            'max_elevation_deg': SHIP['max_elevation_mount_deg'],
            'director_elevation_limit_deg': SHIP['max_elevation_director_deg'],
        })
    secondary = []
    for name in by_role.get('secondary_gun', []):
        row = next(r for r in rows if r['name'] == name)
        secondary.append({'name': name, 'side': name.split('_')[1],
                          'axis_z_m': row['origin_world_m'][2]})
    return {
        'ship_id': SHIP['ship_id'], 'asset_version': SHIP['asset_version'],
        'configuration': SHIP['configuration'], 'historically_certified': SHIP['historically_certified'],
        'length_m': SHIP['length_m'], 'beam_m': SHIP['beam_m'], 'draft_m': SHIP['draft_m'],
        'main_deck_z_m': SHIP['main_deck_z_m'], 'forecastle_z_m': SHIP['forecastle_z_m'],
        'main_gun_calibre_mm': SHIP['main_gun_calibre_mm'],
        'secondary_gun_calibre_mm': SHIP['secondary_gun_calibre_mm'],
        'speed_knots': SHIP['speed_knots'],
        'boilers': SHIP['boilers'], 'boiler_rooms': SHIP['boiler_rooms'], 'shafts': SHIP['shafts'],
        'torpedo_tubes': SHIP['torpedo_tubes'],
        'object_count': len(rows),
        'mesh_count': sum(1 for row in rows if row['type'] == 'MESH'),
        'offsets_source': OFFSETS_SOURCE,
        'casemate_placement': CASEMATE_PLACEMENT,
        'turrets': turrets, 'secondary_guns': secondary,
        'materials': [{'name': name, 'base_color': [grey, grey, grey],
                       'roughness': MATERIAL_ROUGHNESS, 'metallic': 0.0}
                      for name, grey in MATERIAL_SPECS],
        'module_names_by_role': {role: sorted(names) for role, names in sorted(by_role.items())},
        'files': {'manifest': 'object_manifest.json', 'damage_model': 'damage_model.json',
                  'hydrostatics': 'hydrostatics.json', 'firing_arcs': 'firing_arcs.json',
                  'fbx': 'HMS_Queen_Mary_1913_Greybox.fbx'},
        'notes': ['Generated by queen_mary.py together with the asset. Do not hand edit.',
                  'firing_arcs.json is regenerated by verify_blender.py after each build.'],
    }


def flatten_contract_for_unity(contract):
    """JsonUtility-friendly view of the contract.

    Unity's JsonUtility cannot deserialise dictionaries or top level arrays, so the
    two dictionaries become arrays of {key, value} pairs. Everything else is already
    flat. Same build, same data - the two files cannot drift apart.
    """
    flat = dict(contract)
    flat['module_roles'] = [{'role': role, 'names': names}
                            for role, names in contract['module_names_by_role'].items()]
    flat['file_refs'] = [{'key': key, 'path': value}
                         for key, value in contract['files'].items()]
    flat.pop('module_names_by_role', None)
    flat.pop('files', None)
    flat['unity_note'] = ('Read this file with JsonUtility. The nested dictionaries of '
                          'ship_contract.json are exposed as module_roles and file_refs.')
    return flat


# --- manifest and export ----------------------------------------------------
def asset_manifest():
    rows = []
    for obj in sorted(ASSET_COLLECTION.objects, key=lambda ob: ob.name):
        row = {'name': obj.name, 'type': obj.type,
               'parent': obj.parent.name if obj.parent else None,
               'role': obj.get('component_role'),
               'location_local_m': [round(v, 6) for v in obj.location],
               'origin_world_m': [round(v, 6) for v in obj.matrix_world.translation],
               'dimensions_local_axes_m': [round(v, 6) for v in obj.dimensions],
               'scale': [round(v, 6) for v in obj.scale],
               'rotation_local_deg': [round(math.degrees(v), 6) for v in obj.rotation_euler]}
        if obj.type == 'MESH':
            coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
            row['bounds_world_m'] = {'min': [round(min(v[i] for v in coords), 6) for i in range(3)],
                                     'max': [round(max(v[i] for v in coords), 6) for i in range(3)]}
            row['vertices'] = len(obj.data.vertices)
            row['triangles'] = sum(len(p.vertices) - 2 for p in obj.data.polygons)
        rows.append(row)
    return rows


def geometry_signature():
    data = []
    for obj in sorted(ASSET_COLLECTION.objects, key=lambda o: o.name):
        entry = [obj.name, obj.parent.name if obj.parent else None,
                 [round(v, 6) for row in obj.matrix_local for v in row]]
        if obj.type == 'MESH':
            entry += [[[round(c, 6) for c in v.co] for v in obj.data.vertices],
                      [list(p.vertices) for p in obj.data.polygons]]
        data.append(entry)
    return hashlib.sha256(json.dumps(data, separators=(',', ':')).encode()).hexdigest()


def module_summary(rows):
    roles = {}
    for row in rows:
        roles.setdefault(row['role'] or 'unknown', []).append(row['name'])
    decoration_roles = ('stowed_net_mesh', 'casemate_opening', 'sternwalk_rail')
    movable_roles = ('main_turret', 'gun_elevation', 'main_gun_barrel')
    return {
        'object_count': len(rows),
        'mesh_count': sum(row['type'] == 'MESH' for row in rows),
        'triangles': sum(row.get('triangles', 0) for row in rows),
        'role_counts': {role: len(names) for role, names in sorted(roles.items())},
        'movable_modules': sorted(name for role, names in roles.items()
                                  if role in movable_roles for name in names),
        'decoration_objects': sorted(name for role, names in roles.items()
                                     if role in decoration_roles for name in names),
        'combat_modules': sorted(name for role, names in roles.items()
                                 if role in ('magazine', 'boiler_room', 'engine_room',
                                             'steering_gear', 'rudder', 'fire_control',
                                             'armour_belt', 'armour_deck', 'armour_bulkhead',
                                             'secondary_gun', 'barbette', 'funnel')
                                 for name in names),
        'module_contract': ('Hull, decks, superstructure parts, barbettes, turrets, '
                            'elevation pivots, barrels, funnels, masts, secondary guns, '
                            'nets, sternwalk, armour, damage volumes and fire control are '
                            'separately addressable objects. Only decoration is merged.'),
    }


def preview_setup():
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.studiolight_rotate_z = .5
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.curvature_ridge_factor = 1.25
    scene.display.shading.curvature_valley_factor = 1.0
    scene.display.shading.show_specular_highlight = False
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.055, .055, .055)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast' if bpy.app.version < (4, 0, 0) else 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.display.render_aa = '32'
    cameras = [
        ('Overview', (210, 170, 145), (0, 0, 6), 245, (1800, 1100)),
        ('Starboard', (350, 0, 10), (0, 0, 10), 235, (1800, 560)),
        ('Top', (0, 0, 350), (0, 0, 0), 235, (1800, 430)),
        ('Bow', (0, 350, 13), (0, 0, 13), 65, (900, 900)),
        ('Stern_Detail', (55, -143, 44), (0, -84, 4), 76, (1200, 850)),
        ('Stern_Aft', (0, -300, 18), (0, -70, 5), 95, (1400, 700)),
    ]
    for name, position, target, scale, resolution in cameras:
        data = bpy.data.cameras.new('Camera_' + name)
        cam = bpy.data.objects.new('Camera_' + name, data)
        PREVIEW_COLLECTION.objects.link(cam)
        cam.location = position
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        if name == 'Top':
            cam.rotation_euler = (0, 0, math.pi / 2)
        data.type = 'ORTHO'
        data.ortho_scale = scale
        data.clip_end = 2000
        cam['render_width'] = resolution[0]
        cam['render_height'] = resolution[1]
        cam['preview_only'] = True
    scene.camera = bpy.data.objects['Camera_Overview']
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1100
    scene.render.resolution_percentage = 100
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.clip_end = 3000
                area.spaces.active.region_3d.view_distance = 260
                area.spaces.active.region_3d.view_location = (0, 0, 5)
                area.spaces.active.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
                area.spaces.active.shading.color_type = 'MATERIAL'


#: 导出时绕竖直轴额外偏转的角度。**这是实测出来的，不是猜的。**
#: 用不对称标记件探针（probe_axis_convention.py + AxisProbe.cs）测出的映射是
#:     Unity = (-x, z, -y)
#: 即 Blender 的 +X(右舷) 落到 Unity 的 -X、+Y(舰艏) 落到 Unity 的 -Z。
#: 这是一次反射，所以船本身没有镜像；但它等价于"整船绕竖轴转了 180°"——
#: 结果就是 transform.forward 指着舰艉、每座炮塔的静置偏航都差 180°。
#: 补一个 180° 偏转，就同时得到 forward=舰艏、right=右舷。
#: 改这个值必须同步改 verify_fbx.py 的期望坐标（它读的就是这个常量）。
EXPORT_YAW_DEG = 180.0


def export_fbx(out):
    """导出成 Unity 要的约定：舰艏 → +Z，向上 → +Y，右舷 → +X。

    注意 axis_forward / axis_up 这两个开关**在 Unity 侧没有效果**——试过把
    axis_forward 从 '-Z' 改成 'Z'，FBX 哈希变了而 Unity 里的朝向一字不差，
    因为 Unity 的导入器忽略文件头声明的 front 轴。所以朝向只能在几何上拧过来。
    """
    bpy.ops.object.select_all(action='DESELECT')
    for obj in ASSET_COLLECTION.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects['Hull']

    # 所有 98 个对象都挂在 Queen_Mary 下，而它在原点，所以绕它转就是绕全船转。
    root = bpy.data.objects['Queen_Mary']
    rest = root.matrix_world.copy()
    root.matrix_world = Matrix.Rotation(math.radians(EXPORT_YAW_DEG), 4, 'Z') @ rest
    bpy.context.view_layer.update()
    try:
        bpy.ops.export_scene.fbx(filepath=str(out / 'HMS_Queen_Mary_1913_Greybox.fbx'),
            use_selection=True, object_types={'MESH', 'EMPTY'}, global_scale=1.0,
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            axis_forward='-Z', axis_up='Y', use_space_transform=True,
            bake_space_transform=False, use_mesh_modifiers=True, mesh_smooth_type='FACE',
            add_leaf_bones=False, bake_anim=False, path_mode='AUTO', use_custom_props=True)
    finally:
        root.matrix_world = rest
        bpy.context.view_layer.update()


def main():
    global CASEMATE_PLACEMENT
    script_path = Path(globals().get('__file__', 'queen_mary.py')).resolve()
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=script_path.parent)
    parser.add_argument('--skip-render', action='store_true')
    parser.add_argument('--check-repeat', action='store_true')
    parser.add_argument('--casemate-placement', default=CASEMATE_PLACEMENT)
    config = parser.parse_args(args)
    CASEMATE_PLACEMENT = config.casemate_placement
    out = config.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    (out / 'build_started.json').write_text(json.dumps({'started_utc': stamp}), encoding='utf-8')
    try:
        build_ship()
        signature = geometry_signature()
        repeat = None
        if config.check_repeat:
            build_ship()
            repeat = geometry_signature() == signature
            if not repeat:
                raise AssertionError('Re-running in the same scene changed geometry or names')
        preview_setup()
        if script_path.is_file():
            text = bpy.data.texts.get('queen_mary.py') or bpy.data.texts.new('queen_mary.py')
            text.clear()
            text.write(script_path.read_text(encoding='utf-8'))
            text.filepath = str(script_path)
        rows = asset_manifest()
        hydro = hull_hydrostatics()
        damage = build_damage_model(rows)
        buoyancy = build_buoyancy(rows)
        if hydro['immersed_volume_m3']:
            buoyancy['floodable_share_of_immersed_volume_pct'] = round(
                100.0 * buoyancy['floodable_volume_total_m3'] / hydro['immersed_volume_m3'], 2)
        contract = build_ship_contract(rows)
        (out / 'hydrostatics.json').write_text(json.dumps(hydro, indent=2), encoding='utf-8')
        (out / 'damage_model.json').write_text(json.dumps(damage, indent=2), encoding='utf-8')
        (out / 'buoyancy_compartments.json').write_text(json.dumps(buoyancy, indent=2), encoding='utf-8')
        (out / 'ship_contract.json').write_text(json.dumps(contract, indent=2), encoding='utf-8')
        (out / 'ship_contract.unity.json').write_text(
            json.dumps(flatten_contract_for_unity(contract), indent=2), encoding='utf-8')
        manifest = {'ship': SHIP, 'references': SOURCES,
                    'offsets_source': OFFSETS_SOURCE,
                    'casemate_placement': CASEMATE_PLACEMENT,
                    'blender': bpy.app.version_string, 'started_utc': stamp,
                    'geometry_sha256': signature, 'repeat_generation_passed': repeat,
                    'object_count': len(rows),
                    'mesh_count': sum(r['type'] == 'MESH' for r in rows),
                    'triangles': sum(r.get('triangles', 0) for r in rows),
                    'modules': module_summary(rows),
                    'derived_files': ['damage_model.json', 'hydrostatics.json',
                                      'buoyancy_compartments.json', 'ship_contract.json',
                                      'ship_contract.unity.json'],
                    'hydrostatics_summary': {key: hydro[key] for key in
                                             ('immersed_volume_m3', 'waterplane_area_m2',
                                              'lcb_y_m', 'vcb_z_m', 'displacement_t_at_1_025',
                                              'displacement_delta_pct')},
                    'objects': rows,
                    'estimation_notes': [
                        'Hull sections come from the OFFSETS table and stay estimates until a lines plan is supplied.',
                        'A cruiser stern keeps deck breadth aft so attachments derive from the hull.',
                        'Two tripods and all 16 forecastle casemates follow the user specification.',
                        'Casemate axis height is a switch because the sources do not settle it.',
                        'Armour thicknesses are published; armour extents and internal volumes are estimates.',
                        '1916-labelled reference used for arrangement only.',
                    ]}
        (out / 'object_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        with (out / 'objects.csv').open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['Name', 'Type', 'Parent', 'Role', 'X_m', 'Y_m', 'Z_m', 'DX_m', 'DY_m', 'DZ_m'])
            for row in rows:
                writer.writerow([row['name'], row['type'], row['parent'], row['role'],
                                 *row['origin_world_m'], *row['dimensions_local_axes_m']])
        lines = ["{:34} {:6} dimensions(m)={}".format(r['name'], r['type'],
                                                      r['dimensions_local_axes_m']) for r in rows]
        for obj in PREVIEW_COLLECTION.objects:
            lines.append('{:34} {:6} dimensions(m)={}'.format(obj.name, obj.type, list(obj.dimensions)))
        for line in lines:
            print(line)
        (out / 'created_objects.txt').write_text('\n'.join(lines), encoding='utf-8')
        export_fbx(out)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects['Hull'].select_set(True)
        bpy.context.view_layer.objects.active = bpy.data.objects['Hull']
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'HMS_Queen_Mary_1913_Greybox.blend'))
        if not config.skip_render:
            for camera in list(PREVIEW_COLLECTION.objects):
                bpy.context.scene.camera = camera
                bpy.context.scene.render.resolution_x = camera['render_width']
                bpy.context.scene.render.resolution_y = camera['render_height']
                bpy.context.scene.render.filepath = str(out / (camera.name[7:] + '.png'))
                bpy.ops.render.render(write_still=True)
            bpy.context.scene.camera = bpy.data.objects['Camera_Overview']
            bpy.context.scene.render.resolution_x = 1800
            bpy.context.scene.render.resolution_y = 1100
            bpy.ops.wm.save_as_mainfile(filepath=str(out / 'HMS_Queen_Mary_1913_Greybox.blend'))
        report = {'status': 'complete', 'started_utc': stamp,
                  'completed_utc': datetime.now(timezone.utc).isoformat(),
                  'blender': bpy.app.version_string, 'geometry_sha256': signature,
                  'repeat_generation_passed': repeat}
        (out / 'build_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    except Exception:
        (out / 'build_result.json').write_text(json.dumps({'status': 'failed',
            'started_utc': stamp, 'traceback': traceback.format_exc()}, indent=2), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
