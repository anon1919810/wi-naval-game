"""Build HMS Queen Mary v4: modular exterior, PBR materials and inferred cutaway interior.

Standalone bpy generator for Blender 3.x/4.x; validated on Blender 4.5.3 LTS.
Run: blender --background --factory-startup --python queen_mary_v4.py -- --out OUTPUT
Clears the scene. 1 unit = 1 metre; +Y bow, +X starboard, +Z up; waterline Z=0.
Retains v3 module IDs and dimensional references; does not modify v3 gameplay assets.
Internal equipment, bulkheads, coatings and fittings are inferred, not historically certified.
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
    'early_photos': 'User supplied numbered early stern and broadside photographs; 18 is a reference image identifier, not a year; exact fit provisional',
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
    'asset_version': 'v4',
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
    'configuration': 'modular_presentation_with_inferred_interiors',
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
    # Funnel 2 is circular and slightly more massive: mid-range recognition cue vs Lion
    # (worldwar1.co.uk notes the centre funnel was rounder on Queen Mary).
    1: ( 23.0, 2.45, 3.80),
    2: (  7.0, 3.55, 3.55),
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
    'pole_mast': 'mast',
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

MATERIAL_SPECS = [('HullGrey', .34), ('DeckGrey', .47), ('StructureGrey', .56),
                  ('DarkGrey', .20), ('Black', .065), ('UnderwaterGrey', .245)]

MATERIAL_ROUGHNESS = .85

EXPORT_YAW_DEG = 180.0

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






def section_loop(y, scale=1.0):
    """Closed section ring: port side deck->keel, then starboard keel->deck."""
    prof = section_profile(*station_params(y))
    ring = [(-hb * scale, y, z) for z, hb in prof]
    ring += [(hb * scale, y, z) for z, hb in reversed(prof)]
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
    MATERIALS.clear()
    for image in list(bpy.data.images):
        if image.users == 0 and image.name != 'Render Result':
            bpy.data.images.remove(image)
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Queen_Mary_World')
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    scene['coordinate_system'] = 'X starboard / Y bow / Z up / waterline Z=0'
    scene['geometry_status'] = 'Greybox approximation; no hull lines or armour certification'
    scene['asset_version'] = 'v3'




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
    obj = mesh_object(name, verts, faces, parent, material, role, position)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return obj


def bevel_module(obj, width=.18):
    """Small applied bevel: portable geometry, no modifier dependency in Unity."""
    modifier = obj.modifiers.new('Edge_softening', 'BEVEL')
    modifier.width = width
    modifier.segments = 2
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)


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
        face.use_smooth = len(face.vertices) == 4 and z < DECK_Z - .01
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
    for name in ('Bridge', 'Bridge_Upper', 'B_Superfiring_Deckhouse', 'Aft_Deckhouse'):
        bevel_module(bpy.data.objects[name])
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
    builder.add(box_mesh((0,-1.7,TURRET_HEIGHT_M+.10),(1.4,1.6,.20)),'HullGrey')
    for x in (-1.25,1.25):
        builder.add(box_mesh((x,4.57,1.5),(1.14,.10,1.2)),'Black')
    turret = builder.to_object('Turret_' + key, root, 'main_turret', MATERIALS, (0, y, base))
    bevel_module(turret, .08)
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
        profile = [(-0.15,.54), (.8,.54), (1,.48), (2.6,.45), (2.8,.38),
                   (8.5,.29), (BARREL_END_M,.235), (BARREL_END_M,.1715), (11.6,.1715)]
        verts, faces = lathe_mesh(profile, vertices=16, axis='Y')
        barrel = mesh_object('Barrel_{}_{}'.format(key, side), verts, faces, pitch,
                             'DarkGrey', 'main_gun_barrel', position=(x,0,0))
        for polygon in barrel.data.polygons:
            polygon.use_smooth = len(polygon.vertices) == 4
        barrel['calibre_mm'] = 343
        barrel['barrel_end_local_y_m'] = BARREL_END_M
        barrel['trunnion_local_y_m'] = 0.0
        barrel['data_status'] = 'chase length estimated; origin is the barrel trunnion'
    return turret


def make_casemates(root):
    forecastle = bpy.data.objects['Forecastle']
    for side, sign in [('Port', -1), ('Starboard', 1)]:
        openings = MeshBuilder()
        for index, y in enumerate(CASEMATE_YS, 1):
            axis = casemate_axis_z(y)
            surface = deck_halfbeam(y) if CASEMATE_PLACEMENT == 'on_forecastle' else halfbeam_at(y, axis)
            if CASEMATE_PLACEMENT == 'between_decks':
                cutter = mesh_object('_Cut', *box_mesh((sign*(surface-.30), y, axis),
                                     (1.35, 2.45, 1.3)), root, 'Black', 'temporary')
                modifier = forecastle.modifiers.new('Casemate_recess', 'BOOLEAN')
                modifier.operation = 'DIFFERENCE'
                modifier.solver = 'EXACT'
                modifier.object = cutter
                bpy.context.view_layer.objects.active = forecastle
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                data = cutter.data
                bpy.data.objects.remove(cutter, do_unlink=True)
                bpy.data.meshes.remove(data)
                inset = .93
            else:
                inset = -.03
            openings.add(box_mesh((sign*(surface-inset), y, axis), (.06, 2.4, 1.24)), 'Black')
            openings.add(box_mesh((sign*(surface-.08), y, axis+.71), (.24, 2.65, .13)), 'HullGrey')
            gun = mesh_object('Casemate_{}_{}'.format(side, index),
                *lathe_mesh([(-.95,.19), (.1,.18), (2.45,.10), (2.45,.051), (2.20,.051)], 12),
                parent=root, material='DarkGrey', role='secondary_gun', position=(sign*surface, y, axis))
            gun.rotation_euler.z = math.radians(90 if side == 'Port' else -90)
            gun['side'] = side
            gun['calibre_mm'] = 102
            gun['axis_z_m'] = round(axis, 4)
            gun['deck_mode'] = CASEMATE_PLACEMENT
            gun['train_axis_local'] = '+Z'
            gun['rest_forward_local'] = '+Y (outboard)'
            gun['max_train_deg'] = 35.0
            gun['layout_status'] = 'user_spec_8_per_side; exact station and axis height unverified'
            gun['layout_source'] = SOURCES['user']
        obj = openings.to_object('Casemate_Openings_' + side, root, 'casemate_opening', MATERIALS)
        obj['openings'] = len(CASEMATE_YS)
        obj['placement'] = CASEMATE_PLACEMENT
    forecastle['cutout_count'] = 16 if CASEMATE_PLACEMENT == 'between_decks' else 0


def make_funnels(root):
    for index, (y, rx, ry) in FUNNELS.items():
        base = deck_at(y) + FUNNEL_UPTAKE_H
        depth = FUNNEL_TOP_Z - base
        builder = MeshBuilder()
        # Fold the profile down inside the mouth; the terminal cap is recessed.
        profile = [(-INSET, 1), (depth - 1, 1), (depth, 1.035),
                   (depth, .91), (depth - 1.6, .91)]
        verts, faces = lathe_mesh(profile, 40, axis='Z')
        verts = [(x * rx, v * ry, z) for x, v, z in verts]
        builder.add((verts, faces), 'HullGrey')
        for f in range(40, 160):
            # Upper rim and inner walls are dark; no artificial cover over the mouth.
            builder.faces[f] = (builder.faces[f][0], 1)
        builder.faces[-1] = (builder.faces[-1][0], 1)
        builder.mats.append('Black')
        for z in (depth * .27, depth * .58):
            ring = [(rx * 1.013 * math.cos(i * math.tau / 40),
                     ry * 1.013 * math.sin(i * math.tau / 40), z) for i in range(40)]
            for a, b in zip(ring, ring[1:] + ring[:1]):
                builder.add(rod_mesh(a, b, .045, 6), 'DarkGrey')
        if abs(rx - ry) < 1e-6:
            # Recognition collar baked into Funnel_2 mesh (decoration budget: do not spawn a new object).
            collar_z = depth * .42
            ring = [(rx * 1.022 * math.cos(i * math.tau / 40),
                     ry * 1.022 * math.sin(i * math.tau / 40), collar_z) for i in range(40)]
            for a, b in zip(ring, ring[1:] + ring[:1]):
                builder.add(rod_mesh(a, b, .065, 6), 'DarkGrey')
        # Thin spark-arrestor bars sit below the rim, preserving the overall height.
        for u in (-.55, 0, .55):
            extent = math.sqrt(.88**2 - u**2)
            builder.add(rod_mesh((rx*u, -ry*extent, depth-.22),
                                 (rx*u, ry*extent, depth-.22), .045, 6), 'DarkGrey')
        funnel = builder.to_object('Funnel_{}'.format(index), root, 'funnel', MATERIALS, (0, y, base))
        for p in funnel.data.polygons:
            p.use_smooth = len(p.vertices) == 4
        circular = abs(rx - ry) < 1e-6
        funnel['section'] = 'circular' if circular else 'elliptical'
        funnel['casing_axis_radius_m'] = [rx, ry]
        funnel['top_z_m'] = FUNNEL_TOP_Z
        funnel['section_source'] = SOURCES['ww1']
        funnel['uptake_armour_mm'] = 38
        funnel['internal_uptakes'] = False
        funnel['mouth_depth_m'] = 1.6
        if circular:
            funnel['recognition_feature'] = (
                'centre funnel rounder than Lion-class sisters; greybox mid-range cue')
            funnel['recognition_status'] = 'secondary_source_estimate'
            funnel['recognition_source'] = SOURCES['ww1']
            funnel['recognition_collar_z'] = depth * 0.42


def make_mast(name, y, base, height, root, spread):
    builder = MeshBuilder()
    fore = name == 'Mast_Fore'
    radius = .32 if fore else .24
    builder.add(lathe_mesh([(0, radius), (height*.65, radius*.70), (height, .075)],
                           16, axis='Z'), 'DarkGrey')
    for fraction, half_width in ((.63, 5.0 if fore else 2.8), (.88, 3.2 if fore else 1.8)):
        builder.add(rod_mesh((-half_width, 0, height*fraction),
                             (half_width, 0, height*fraction), .075, 8), 'DarkGrey')
    if fore:
        builder.add(lathe_mesh([(height*.40, 1.20), (height*.40+.24, 1.20)], 16, axis='Z'), 'DeckGrey')
        builder.add(lathe_mesh([(height*.40+.24, .70), (height*.40+1.0, .70)], 12, axis='Z'), 'StructureGrey')
    mast = builder.to_object(name, root, 'pole_mast', MATERIALS, (0, y, base))
    mast['legs'] = 1
    mast['height_m'] = height
    mast['historical_status'] = 'early pole-and-stay interpretation per latest user correction; exact dated fit unverified'
    mast['source'] = SOURCES['early_photos']
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
    for y in ys:
        for sign in (-1,1):
            rails.add(rod_mesh((sign*edge(y,half_width),y,z0+.18),
                               (sign*edge(y,half_width),y,z0+2.05),.045,6),'DarkGrey')
    rails.add(prism_mesh(outline,z0+2.05,z0+2.17),'StructureGrey')
    rails.to_object('Sternwalk_Rails', walk, 'sternwalk_rail', MATERIALS)
    walk['canopy_height_m'] = 2.17
    return walk



def add_rails(builder, points, height=1.0):
    for a, b in zip(points, points[1:]):
        a, b = Vector(a), Vector(b)
        for z in (height*.5, height):
            builder.add(rod_mesh(a+Vector((0,0,z)), b+Vector((0,0,z)), .035, 6), 'DarkGrey')
        count = max(1, math.ceil((b-a).length/2.2))
        for i in range(count):
            foot = a.lerp(b, i/count)
            builder.add(rod_mesh(foot, foot+Vector((0,0,height)), .04, 6), 'DarkGrey')


def make_refinement_details(root):
    details, fittings, rigging = MeshBuilder(), MeshBuilder(), MeshBuilder()
    # Bridge glazing, wing rails and aft deckhouse windows.
    z = bridge_top_z()+1.45
    for x in (-3.2,-1.6,0,1.6,3.2):
        details.add(box_mesh((x,BRIDGE_Y+2.51,z),(1.10,.025,.72)), 'Black')
    for sign in (-1,1):
        for y in (BRIDGE_Y-3.5,BRIDGE_Y-1.8,BRIDGE_Y,BRIDGE_Y+1.7):
            details.add(box_mesh((sign*4.311,y,z),(.025,1.1,.72)), 'Black')
        for y in (-49,-45,-41,-37):
            details.add(box_mesh((sign*6.212,y,aft_deckhouse_top_z()-1),(.025,1,.6)), 'Black')
        add_rails(details, [(sign*8.3,BRIDGE_Y-2.9,bridge_top_z()+.34),
                            (sign*8.3,BRIDGE_Y+1.9,bridge_top_z()+.34),
                            (sign*4.5,BRIDGE_Y+1.9,bridge_top_z()+.34)])
        # Rails follow deck sheer; separate at the forecastle break.
        for start,end in ((-104,-19),(-17,103)):
            ys = sorted(set([start,end]+[v for v in station_ys() if start < v < end]))
            add_rails(details, [(sign*(deck_halfbeam(y)-.22),y,deck_at(y)+.03) for y in ys])
        for y in range(-91,96,5):
            # Flat disks just outside the shell: portholes, not expensive booleans.
            x = sign*(halfbeam_at(y,3.25)+.025)
            details.add(rod_mesh((x,y,3.25),(x+sign*.022,y,3.25),.17,10), 'Black')
        # Four open launches on the aft platform; no new gameplay modules.
        for y,length in ((-36,7.2),(-46,7.2)):
            bx = sign*4.3
            bz = aft_deckhouse_top_z()+.42
            outline = [(0,length/2),(.82,length*.30),(.98,-length*.2),(.72,-length*.43),
                       (0,-length/2),(-.72,-length*.43),(-.98,-length*.2),(-.82,length*.30)]
            rings = [[(bx+x*k,y+v*k,bz+h) for x,v in outline] for k,h in ((.68,.05),(1,.80),(.84,.80),(.62,.23))]
            fittings.add(loft_rings_mesh(rings), 'StructureGrey')
            for dy in (-1.6,0,1.6):
                fittings.add(box_mesh((bx,y+dy,bz+.73),(1.5,.24,.12)), 'DeckGrey')
            for dy in (-1.8,1.8):
                fittings.add(box_mesh((bx,y+dy,bz),(2.2,.32,.40)), 'DarkGrey')
        # Foredeck capstans and simplified anchor chains.
        for y in (79,86):
            x = sign*(2.3 if y==79 else 3.3)
            dz = deck_at(y)
            fittings.add(lathe_mesh([(0,.5),(.65,.5),(.65,.66),(.82,.66)], 16, axis='Z'), 'DarkGrey', (x,y,dz))
            fittings.add(rod_mesh((x,y,dz+.18),(sign*5,94,deck_at(94)+.15),.10,8), 'Black')
        # Early pole-mast stays kept outside mast collision bounds.
        for name,y,base,height in (('Fore',BRIDGE_Y,bridge_upper_top_z(),24),
                                    ('Main',-38,aft_deckhouse_top_z(),19)):
            peak = (0,y,base+height*.84)
            for delta in (-9,9):
                anchor_y = y+delta
                anchor = (sign*min(10,deck_halfbeam(anchor_y)-1),anchor_y,deck_at(anchor_y)+.1)
                rigging.add(rod_mesh(peak,anchor,.027,5), 'DarkGrey')
    # Boat handling boom and signal stays, interpreted from the early photographs.
    # Mid-range massing belts on bridge/aft (merged into deck details; estimate, not fittings).
    details.add(box_mesh((0, BRIDGE_Y, bridge_base_z() + 0.35), (12.6, 12.2, 0.35)), 'DeckGrey')
    details.add(box_mesh((0, AFT_Y, aft_deckhouse_base_z() + 0.40), (12.6, 23.2, 0.35)), 'DeckGrey')
    rigging.add(rod_mesh((0,-38,aft_deckhouse_top_z()+3),(0,-50,aft_deckhouse_top_z()+1.3),.14,10), 'DarkGrey')
    rigging.add(rod_mesh((0,-38,aft_deckhouse_top_z()+16),(0,-50,aft_deckhouse_top_z()+1.3),.032,5), 'DarkGrey')
    rigging.add(rod_mesh((0,BRIDGE_Y,bridge_upper_top_z()+23),(0,-38,aft_deckhouse_top_z()+18),.024,5), 'DarkGrey')
    for builder,name,role in ((details,'Deck_Visual_Details','deck_detail'),
                              (fittings,'Deck_Fittings','deck_fitting'),
                              (rigging,'Rigging_Stays','rigging')):
        obj = builder.to_object(name,root,role,MATERIALS)
        obj['geometry_status'] = '50m visual approximation; not structural collision geometry'
        if name == 'Deck_Visual_Details':
            obj['midrange_massing'] = (
                'bridge/aft deck-grey belts merged here for 50-200m readability; estimate')


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
    anchors.append(('FX_Mast_Main_Top', (0, -38.0, aft_deckhouse_top_z() + 19.0), 'anchor'))
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
    make_mast('Mast_Main', -38.0, aft_deckhouse_top_z(), 19.0, root, 2.3)
    make_sternwalk(root)
    make_nets(root)
    make_underwater_gear(root)
    make_armour(root)
    make_damage_modules(root)
    make_fire_control(root, sup)
    make_fx_anchors(root)
    make_refinement_details(root)
    apply_system_links(root)
    bpy.context.view_layer.update()
    return root


# --- manifest and export ----------------------------------------------------
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
        waterplane += seg * (2.0 * halfbeam_at(y_a, 0.0) + 8.0 * halfbeam_at((y_a + y_b) / 2.0, 0.0)
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
                  'buoyancy_compartments': 'buoyancy_compartments.json',
                  'lod_profiles': 'lod_profiles.json',
                  'fbx': 'HMS_Queen_Mary_1913_Refined_v3.fbx'},
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
    decoration_roles = ('stowed_net_mesh', 'casemate_opening', 'sternwalk_rail', 'deck_detail', 'deck_fitting', 'rigging')
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










"""Functions integrated into the standalone v4 generator by assemble_v4.py."""

def create_pbr_material(name, color, metallic=0.0, roughness=0.65, texture_kind=None):
    """Create a portable material using generated tileable image textures."""
    import numpy as np
    mat = MATERIALS.get(name) or bpy.data.materials.new(name)
    MATERIALS[name] = mat
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    mat['unity_shader'] = 'Universal Render Pipeline/Lit'
    mat['metallic'] = metallic
    mat['smoothness'] = 1-roughness
    if texture_kind:
        n = 512
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
        if texture_kind == 'teak':
            plank = np.floor(xx*12)
            seam = (np.mod(xx*12, 1) < .033)
            endseam = np.mod(yy*2 + np.mod(plank, 3)/3, 1) < .007
            variation = .96 + .035*np.sin(plank*12.12) + .012*np.sin(yy*math.tau*47 + np.sin(xx*math.tau*6))
            variation = np.where(seam | endseam, .24, variation)
            height = np.where(seam | endseam, 0.0, .35) + .01*np.sin(yy*math.tau*65)
        else:
            variation = .99+.003*np.sin(xx*math.tau*59)*np.cos(yy*math.tau*83)
            height = .003*np.sin(xx*math.tau*27)*np.cos(yy*math.tau*23)
        rgba = np.ones((n,n,4), dtype=np.float32)
        rgba[:,:,:3] = np.clip(variation[:,:,None]*np.array(color), 0, 1)
        maps = {'BaseColor':rgba.copy()}
        rgba[:,:,:3] = metallic
        rgba[:,:,3] = 1-roughness
        maps['MetallicSmoothness'] = rgba.copy()
        nx = -(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*.7
        ny = -(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*.7
        rgba[:,:,0] = .5+nx
        rgba[:,:,1] = .5+ny
        rgba[:,:,2] = 1.0
        rgba[:,:,3] = 1.0
        maps['Normal'] = rgba.copy()
        for kind, pixels in maps.items():
            im = bpy.data.images.new(name+'_'+kind, width=n, height=n, alpha=True)
            im.colorspace_settings.name = 'sRGB' if kind == 'BaseColor' else 'Non-Color'
            im.pixels.foreach_set(pixels.ravel())
            im.filepath_raw = str(OUT/'textures'/(im.name+'.png'))
            im.file_format = 'PNG'
            im.save()
            im.pack()
            tex = nodes.new('ShaderNodeTexImage')
            tex.image = im
            if kind == 'BaseColor':
                mat.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
            elif kind == 'Normal':
                normal = nodes.new('ShaderNodeNormalMap')
                normal.inputs['Strength'].default_value = .25
                mat.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color'])
                mat.node_tree.links.new(normal.outputs['Normal'],shader.inputs['Normal'])
    return mat


def make_materials():
    palette = {
        'HullGrey': ((.29,.335,.35),.12,.68,'steel'),
        'StructureGrey': ((.38,.425,.43),.08,.63,'steel'),
        'UnderwaterGrey': ((.19,.045,.031),.03,.82,'steel'),
        'DeckGrey': ((.39,.29,.18),0,.74,'teak'),
        'DarkGrey': ((.105,.13,.14),.4,.55,'steel'),
        'Black': ((.016,.023,.025),.1,.74,None),
        'Brass': ((.48,.29,.10),.82,.35,None),
        'InteriorPaint': ((.62,.64,.57),.05,.76,None),
        'Machinery': ((.12,.19,.20),.5,.46,None),
        'ChargeCases': ((.29,.20,.115),.08,.76,None),
        'CutEdge': ((.60,.29,.075),.15,.64,None),
        'Glass': ((.055,.115,.14),.35,.2,None),
        'Canvas': ((.49,.46,.37),0,.9,None),
    }
    for name, args in palette.items():
        create_pbr_material(name,*args)


def station_params(y):
    """Interpolate estimated offsets monotonically without adding beam overshoot."""
    rows=OFFSETS_TABLE
    if y<=rows[0][0]:return rows[0][1:]
    if y>=rows[-1][0]:return rows[-1][1:]
    i=next(i for i in range(len(rows)-1) if rows[i][0]<=y<=rows[i+1][0])
    h=rows[i+1][0]-rows[i][0]; t=(y-rows[i][0])/h
    answer=[]
    for col in range(1,5):
        def slope(j):
            if j==0:return (rows[1][col]-rows[0][col])/(rows[1][0]-rows[0][0])
            if j==len(rows)-1:return (rows[-1][col]-rows[-2][col])/(rows[-1][0]-rows[-2][0])
            h0=rows[j][0]-rows[j-1][0]; h1=rows[j+1][0]-rows[j][0]
            a=(rows[j][col]-rows[j-1][col])/h0; b=(rows[j+1][col]-rows[j][col])/h1
            if a*b<=0:return 0.0
            w1=2*h1+h0;w2=h1+2*h0
            return (w1+w2)/(w1/a+w2/b)
        a,b=rows[i][col],rows[i+1][col]
        value=(2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*h*slope(i)+(-2*t**3+3*t*t)*b+(t**3-t*t)*h*slope(i+1)
        answer.append(max(min(a,b),min(max(a,b),value)))
    return tuple(answer)


def station_ys():
    ys={FORE_AFT_END,*BELT_YS}
    for a,b in zip(OFFSETS_TABLE,OFFSETS_TABLE[1:]):
        n=max(1,math.ceil((b[0]-a[0])/2))
        ys.update(a[0]+(b[0]-a[0])*j/n for j in range(n+1))
    return sorted(ys)


def section_profile(deck_hb,wl_hb,keel_z,flat_hb):
    pts=[]
    for i in range(9):
        t=i/8;z=DECK_Z*(1-t)
        pts.append((z,deck_hb+(wl_hb-deck_hb)*t**.85))
    for i in range(1,25):
        f=i/24
        pts.append((keel_z*f,flat_hb+(wl_hb-flat_hb)*math.cos(math.pi*.5*f**.92)))
    return pts


def append_geometry(obj, builder):
    """Append decoration to a module without changing its pivot or children."""
    temp = builder.to_object('_merge_detail',obj.parent,'temporary',MATERIALS)
    temp.matrix_world = obj.matrix_world.copy()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    temp.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()


def add_ring(builder, center, rx, ry, radius=.04, material='DarkGrey', count=32):
    x,y,z = center
    points = [(x+rx*math.cos(i*math.tau/count),y+ry*math.sin(i*math.tau/count),z) for i in range(count)]
    for a,b in zip(points,points[1:]+points[:1]):
        builder.add(rod_mesh(a,b,radius,6),material)


def make_underwater_gear(root):
    """Model four pitched propellers; dimensions and blade profiles are estimated."""
    builder=MeshBuilder()
    for side in (-1,1):
        for x,y,z in ((3,-101,-4.2),(6,-95,-5.5)):
            hx=side*x
            builder.add(rod_mesh((hx*.65,-68,-6.4),(hx,y,z),.22,16),'DarkGrey')
            builder.add(rod_mesh((hx*.6,y+5,-2.2),(hx,y+1,z),.19,12),'HullGrey')
            builder.add(lathe_mesh([(-.55,.2),(-.35,.43),(.6,.43),(.8,.2)],24,'Y'),'Brass',(hx,y,z))
            for blade in range(4):
                angle=blade*math.tau/4
                rings=[]
                for r,width,sweep in ((.38,.18,0),(.72,.44,.12),(1.15,.56,.3),(1.6,.46,.42),(1.88,.16,.4),(1.95,.02,.35)):
                    ring=[]
                    for u,v in ((-1,-1),(1,-1),(1,1),(-1,1)):
                        tangent=sweep+u*width
                        bx=r*math.cos(angle)-tangent*math.sin(angle)
                        bz=r*math.sin(angle)+tangent*math.cos(angle)
                        ring.append((hx+bx,y+u*width*.42*side+v*.035,z+bz))
                    rings.append(ring)
                builder.add(loft_rings_mesh(rings),'Brass')
    shafts=builder.to_object('Propeller_Shafts',root,'propulsion_underwater',MATERIALS)
    for p in shafts.data.polygons:p.use_smooth=True
    rudder=mesh_object('Rudder',*box_mesh((0,-103.6,-4.6),(.42,5.6,6.8)),root,'UnderwaterGrey','rudder')
    bevel_module(rudder,.18)
    return shafts,rudder


def make_presentation_refinement(root):
    """Refine all external modules while retaining their gameplay identities."""
    fittings = MeshBuilder()
    # Upper deck edge is painted steel; wood is limited to horizontal surfaces.
    for name in ('Forecastle','Quarterdeck'):
        ob = bpy.data.objects[name]
        ob.data.materials.append(MATERIALS['HullGrey'])
        for p in ob.data.polygons:
            p.material_index = 0 if p.normal.z > .7 else 1
    # Boot topping follows the actual hull section, leaving the principal hull unchanged.
    for side in (-1,1):
        for ya,yb in zip(station_ys(),station_ys()[1:]):
            verts = [(side*(halfbeam_at(y,z)+.012),y,z) for y,z in ((ya,-.32),(yb,-.32),(yb,.36),(ya,.36))]
            fittings.add((verts,[(0,1,2,3)]),'Black')
    # Bridge becomes an open, supported tier above a low deckhouse.
    bridge = bpy.data.objects['Bridge']
    low = [(-5.9,-5.8),(5.9,-5.8),(6.2,-4.8),(6.2,4.5),(4.6,6),(-4.6,6),(-6.2,4.5),(-6.2,-4.8)]
    old = bridge.data
    verts,faces = prism_mesh(low,0,2.9)
    mesh = bpy.data.meshes.new('Bridge_Tiered_Mesh')
    mesh.from_pydata(verts,[],faces)
    bridge.data = mesh
    bridge.location.z = bridge_base_z()
    mesh.materials.append(MATERIALS['StructureGrey'])
    bevel_module(bridge,.09)
    if old.users == 0: bpy.data.meshes.remove(old)
    for z in (bridge_base_z()+3.05,bridge_top_z()-.32):
        fittings.add(prism_mesh([(x,y+BRIDGE_Y) for x,y in low],z,z+.18),'StructureGrey')
        for side in (-1,1):
            add_rails(fittings,[(side*6.15,BRIDGE_Y-5.2,z+.18),(side*6.15,BRIDGE_Y+4.4,z+.18),(side*4.6,BRIDGE_Y+5.9,z+.18)],.9)
    for x in (-4.9,4.9):
        for y in (BRIDGE_Y-4.8,BRIDGE_Y+4):
            fittings.add(rod_mesh((x,y,bridge_base_z()+2.9),(x,y,bridge_top_z()),.14,10),'StructureGrey')
    # Bridge glazing, door frames and aft house vents.
    for side in (-1,1):
        for y in (28,30,32,34,36):
            fittings.add(box_mesh((side*6.22,y,bridge_base_z()+1.8),(.035,1.15,.7)),'Glass')
        for y in (-49,-45,-41,-37,-33):
            for dz in (-.2,0,.2):
                fittings.add(box_mesh((side*6.24,y,aft_deckhouse_top_z()-1.4+dz),(.04,1.2,.045)),'DarkGrey')
        # Cowl ventilators and skylights on clear deck margins.
        for y in (-82,-57,-20,2,18,40,71,85):
            x = side*min(8.4,deck_halfbeam(y)-2)
            z = deck_at(y)
            fittings.add(lathe_mesh([(0,.32),(.14,.44),(1.05,.32),(1.4,.50)],16,'Z'),'StructureGrey',(x,y,z))
            fittings.add(rod_mesh((x,y, z+1.35),(x,y+.45,z+1.35),.38,16),'StructureGrey')
            fittings.add(rod_mesh((x,y+.451,z+1.35),(x,y+.47,z+1.35),.29,16),'Black')
        for y in (78,90,-84):
            x=side*3.7
            z=deck_at(y)
            fittings.add(box_mesh((x,y,z+.3),(2.1,2.8,.6)),'StructureGrey')
            fittings.add(box_mesh((x,y,z+.61),(1.8,2.4,.035)),'Glass')
            for d in (-.6,0,.6):
                fittings.add(box_mesh((x+d,y,z+.65),(.065,2.4,.07)),'StructureGrey')
    # Bollards, fairleads and anchor chains; all static fittings share one mesh.
    for y in (-99,-90,82,94,100):
        z=deck_at(y)
        for side in (-1,1):
            x=side*(deck_halfbeam(y)-1.0)
            fittings.add(box_mesh((x,y,z+.14),(.9,1.6,.28)),'DarkGrey')
            for dy in (-.4,.4):
                fittings.add(lathe_mesh([(0,.17),(.6,.17),(.65,.25),(.74,.25)],12,'Z'),'DarkGrey',(x,y+dy,z+.28))
    for side in (-1,1):
        for i in range(35):
            y=83+i*.31
            x=side*(3.1+(y-83)*.105)
            add_ring(fittings,(x,y,deck_at(y)+.14),.12,.19,.028,'DarkGrey',10)
    # Weather doors and inclined ladders provide real silhouettes at close range.
    for x,y,z in ((6.32,-51,quarterdeck_z(-51)),(-6.32,-51,quarterdeck_z(-51)),(6.3,28,forecastle_z(28))):
        fittings.add(box_mesh((x,y,z+1.08),(.05,.9,2.05)),'DarkGrey')
        fittings.add(box_mesh((x+.04,y,z+1.08),(.055,.72,1.85)),'StructureGrey')
        for dy in (-.32,.32):
            fittings.add(rod_mesh((x+.12,y+dy,z+.3),(x+.12,y+dy,z+1.8),.025,6),'DarkGrey')
    for side in (-1,1):
        for y,z0,z1 in ((-19,deck_at(-19),deck_at(-17)),(43,deck_at(43),SUPERFIRING_DECK_Z)):
            x=side*(8.2 if y<0 else 6.5)
            a=Vector((x,y-2,z0+.1)); b=Vector((x,y,z1+.1))
            for dx in (-.42,.42):
                fittings.add(rod_mesh(a+Vector((dx,0,0)),b+Vector((dx,0,0)),.055,8),'StructureGrey')
            for i in range(12):
                p=a.lerp(b,i/11)
                fittings.add(box_mesh(p,(.8,.22,.06)),'DarkGrey')
    # Two open cutters beside the forward funnel, plus existing aft boat interiors.
    for side in (-1,1):
        bx=side*6.7;by=22;length=8.3;bz=deck_at(by)+.50
        outline=[(0,length/2),(.82,length*.34),(1.0,-length*.18),(.72,-length*.43),(0,-length/2),(-.72,-length*.43),(-1,-length*.18),(-.82,length*.34)]
        rings=[[(bx+x*k,by+y*k,bz+z) for x,y in outline] for k,z in ((.58,0),(1,.85),(.86,.85),(.52,.18))]
        fittings.add(loft_rings_mesh(rings),'StructureGrey')
        for dy in (-2.3,-1.1,.1,1.3,2.5):
            fittings.add(box_mesh((bx,by+dy,bz+.62),(1.65,.24,.10)),'DeckGrey')
        for dy in (-2.5,2.5):
            fittings.add(box_mesh((bx,by+dy,bz-.30),(2.2,.28,.58)),'DarkGrey')
            x=side*8.1
            fittings.add(rod_mesh((x,by+dy,deck_at(by)),(x,by+dy,bz+2.2),.09,10),'StructureGrey')
            fittings.add(rod_mesh((x,by+dy,bz+2.2),(bx,by+dy,bz+2.7),.09,10),'StructureGrey')
            fittings.add(rod_mesh((bx,by+dy,bz+2.7),(bx,by+dy,bz+.8),.025,6),'DarkGrey')
        for by in (-36,-46):
            for dy in (-2,-1,0,1,2):
                fittings.add(box_mesh((side*4.3,by+dy,aft_deckhouse_top_z()+1.01),(1.5,.20,.08)),'DeckGrey')
    extra=fittings.to_object('Presentation_Fittings',root,'decoration',MATERIALS)
    extra['historical_status']='photographic interpretation; individual fittings estimated'
    # Detail rotates with each turret; muzzle points remain children of the barrels.
    for key in TURRETS:
        ob=bpy.data.objects['Turret_'+key]
        d=MeshBuilder()
        for x in (-3.6,3.6):
            for y in (-2.8,-1.4,0,1.4,2.8):
                d.add(lathe_mesh([(0,.055),(.055,.055)],8,'Z'),'DarkGrey',(x,y,TURRET_HEIGHT_M+.025))
        for y in (-2.5,-.2,2.1):
            d.add(box_mesh((0,y,TURRET_HEIGHT_M+.035),(7.6,.028,.035)),'DarkGrey')
        for x in (-1.25,1.25):
            d.add(rod_mesh((x,3.75,1.5),(x,4.75,1.5),.65,24),'Canvas')
        for z in (.5,1,1.5,2,2.5):
            d.add(rod_mesh((-.45,-4.34,z),(.45,-4.34,z),.045,8),'DarkGrey')
        append_geometry(ob,d)
        for side in ('Port','Starboard'):
            barrel=bpy.data.objects[f'Barrel_{key}_{side}']
            muzzle=empty(f'Muzzle_{key}_{side}',(0,BARREL_END_M,0),barrel,'muzzle')
            muzzle['forward_local']='+Y'
            muzzle['unity_forward_note']='transform imported axis explicitly; Blender local +Y'
    # Funnel ladders and steam pipes, merged into each original funnel module.
    for index,(y,rx,ry) in FUNNELS.items():
        ob=bpy.data.objects[f'Funnel_{index}']; height=FUNNEL_TOP_Z-ob.location.z
        d=MeshBuilder()
        for x in (-.28,.28):
            d.add(rod_mesh((x,-ry-.10,.4),(x,-ry-.10,height-.5),.04,8),'DarkGrey')
        for i in range(int(height/.4)):
            z=.5+i*.4
            d.add(rod_mesh((-.28,-ry-.12,z),(.28,-ry-.12,z),.025,6),'DarkGrey')
        for side in (-1,1):
            d.add(rod_mesh((side*(rx+.35),0,0),(side*(rx+.35),0,height-1.2),.12,12),'StructureGrey')
        append_geometry(ob,d)


def make_internal_visuals(root):
    """Build a readable inferred engineering interior linked to existing modules."""
    interior=empty('Interior_Visual',parent=root,role='interior_group')
    interior['visibility_default']='hidden in exterior view; enable for section inspection'
    structural=MeshBuilder()
    # Two continuous deck levels with the hull shape, visible in the section derivative.
    for z in (-.8,2.1):
        ys=[y for y in station_ys() if keel_at(y)<z-.6 and -99<y<99]
        rings=[]
        for y in ys:
            hb=max(.2,halfbeam_at(y,z)-.3)
            rings.append([(-hb,y,z),(-hb,y,z+.12),(hb,y,z+.12),(hb,y,z)])
        structural.add(loft_rings_mesh(rings),'InteriorPaint')
    for key,(y,deck_source,h,yaw) in TURRETS.items():
        deck,top=turret_deck_and_base(key)
        rings=[]
        for z,r in ((-.65,4.8),(top,4.8),(top,4.57),(-.65,4.57),(-.65,4.8)):
            rings.append([(r*math.cos(i*math.tau/48),y+r*math.sin(i*math.tau/48),z) for i in range(48)])
        structural.add(loft_rings_mesh(rings,False,False),'InteriorPaint')
    for index,(y,rx,ry) in FUNNELS.items():
        ztop=deck_at(y)+FUNNEL_UPTAKE_H
        structural.add(box_mesh((0,y,(ztop-.6)/2),(rx*1.4,ry*1.6,ztop+.6)),'DarkGrey')
    for y in range(-90,85,6):
        prof=section_profile(*station_params(y))
        for side in (-1,1):
            points=[(side*max(.1,hb-.3),y,z+.16) for z,hb in prof]
            for a,b in zip(points,points[1:]):
                structural.add(rod_mesh(a,b,.075,6),'InteriorPaint')
    modules=[]
    for name,y,z,size,role,source in DAMAGE_VOLUMES:
        proxy=bpy.data.objects[name]
        sx,sy,sz=proxy.dimensions
        cz=proxy.location.z; floor=cz-sz/2+.15
        obgroup=empty('Interior_'+name,parent=interior,role='interior_module')
        obgroup['module_id']=name
        obgroup['historical_status']='inferred equipment and compartment arrangement; not certified'
        equipment=MeshBuilder()
        equipment.add(box_mesh((0,y,floor),(sx-.2,sy-.25,.14)),'DarkGrey')
        for edge in (-1,1):
            structural.add(box_mesh((0,y+edge*sy/2,floor+sz*.48),(sx,.12,sz*.96)),'InteriorPaint')
            # Exposed section-edge band makes compartment boundaries legible.
            structural.add(box_mesh((sx/2-.1,y+edge*sy/2,floor+sz*.48),(.08,.16,sz*.96)),'CutEdge')
            if role!='steering_gear':
                structural.add(box_mesh((0,y+edge*sy/2,1.0),(sx,.10,3.7)),'InteriorPaint')
        if role=='boiler_room':
            for side in (-1,1):
                x=side*min(3.7,sx*.27)
                for dy in (-sy*.30,0,sy*.30):
                    by=y+dy
                    equipment.add(box_mesh((x,by,floor+.7),(2.7,sy*.22,1.3)),'Machinery')
                    # Triangular tube banks are schematic water-tube boilers, not locomotive tanks.
                    for sign in (-1,1):
                        for k in range(9):
                            py=by-sy*.09+k*sy*.0225
                            equipment.add(rod_mesh((x+sign*1.13,py,floor+1.15),(x+sign*.25,py,floor+3.35),.055,8),'DarkGrey')
                    equipment.add(rod_mesh((x,by-sy*.12,floor+3.38),(x,by+sy*.12,floor+3.38),.30,16),'Machinery')
                    for door in (-.65,.65):
                        equipment.add(rod_mesh((x+door,by+sy*.111,floor+.65),(x+door,by+sy*.13,floor+.65),.28,16),'Black')
                    equipment.add(rod_mesh((x,by,floor+3.65),(0,by,floor+3.65),.09,10),'Brass')
            equipment.add(rod_mesh((0,y-sy*.44,floor+3.65),(0,y+sy*.44,floor+3.65),.13,12),'Brass')
        elif role=='magazine':
            for side in (-1,1):
                x=side*min(2.7,sx*.30)
                for row in (-.7,.7):
                    for k in range(6):
                        py=y-sy*.36+k*sy*.14
                        equipment.add(lathe_mesh([(0,.175),(.95,.175),(1.14,.12),(1.38,.012)],12,'Z'),'Machinery',(x+row,py,floor+.25))
                equipment.add(box_mesh((x,y,floor+.16),(2.4,sy*.86,.2)),'ChargeCases')
                for dy in (-sy*.28,0,sy*.28):
                    equipment.add(box_mesh((side*.95,y+dy,floor+.45),(.75,sy*.2,.72)),'ChargeCases')
            key=name[-1]; turret_y=TURRETS[key][0]; base=turret_deck_and_base(key)[1]
            equipment.add(lathe_mesh([(floor+.25,1.0),(base,1.0)],32,'Z'),'InteriorPaint',(0,turret_y,0))
            for h in (floor+1, -1.25, 2.3, base-.3):
                add_ring(equipment,(0,turret_y,h),1.04,1.04,.07,'DarkGrey',28)
            equipment.add(box_mesh((0,turret_y,floor+.2),(2.4,2.4,.22)),'DarkGrey')
        elif role=='engine_room':
            for side in (-1,1):
                x=side*min(sx*.28,3.8)
                length=sy*.75
                equipment.add(lathe_mesh([(-length/2,.6),(-length*.4,1.18),(length*.22,1.18),(length*.4,.85),(length/2,.45)],28,'Y'),'Machinery',(x,y,floor+1.65))
                for dy in [i*length/7-length*.43 for i in range(7)]:
                    equipment.add(lathe_mesh([(-.055,1.20),(.055,1.20)],24,'Y'),'DarkGrey',(x,y+dy,floor+1.65))
                equipment.add(box_mesh((x,y,floor+.28),(2.8,length,.4)),'DarkGrey')
                equipment.add(rod_mesh((x,y-sy*.48,floor+1.65),(x,y+sy*.48,floor+1.65),.18,16),'Brass')
                equipment.add(rod_mesh((x,y,floor+3),(0,y,floor+3),.17,12),'Brass')
            for dy in (-sy*.3,sy*.3):
                equipment.add(lathe_mesh([(0,.5),(1.4,.5)],16,'Z'),'Machinery',(0,y+dy,floor+.25))
        else:
            equipment.add(box_mesh((0,y,floor+.6),(3.5,2.4,1.0)),'Machinery')
            equipment.add(lathe_mesh([(0,.45),(1.9,.45)],24,'Z'),'DarkGrey',(0,y,floor+.2))
            for side in (-1,1):
                equipment.add(rod_mesh((0,y,floor+1.35),(side*2.6,y,floor+1.35),.2,16),'Brass')
        mesh=equipment.to_object('Equipment_'+name,obgroup,'interior_equipment',MATERIALS)
        mesh['module_id']=name
        mesh['confidence']='low: schematic equipment; medium: relationship to source module'
        mesh['not_collision_geometry']=True
        modules.append({'module_id':name,'visual_root':obgroup.name,'equipment_mesh':mesh.name,'role':role,'layout':'estimate'})
    frame=structural.to_object('Interior_Frames_Bulkheads',interior,'interior_structure',MATERIALS)
    frame['historical_status']='estimated frames and watertight boundaries, not a shipyard drawing'
    (OUT/'interior_modules.json').write_text(json.dumps({'historically_certified':False,'modules':modules},indent=2),encoding='utf-8')
    return interior


def assign_uvs_and_collections():
    """Keep shell, modules, interior and helper layers individually selectable."""
    categories={}
    for title in ('01_Exterior','02_Interior_Visual','03_Damage_Proxies','04_Armour_Proxies','05_Functional_Anchors'):
        c=bpy.data.collections.new(title)
        bpy.context.scene.collection.children.link(c)
        categories[title]=c
    for ob in list(ASSET_COLLECTION.objects):
        role=ob.get('component_role','')
        if role in ('magazine','boiler_room','engine_room','steering_gear'):
            cat='03_Damage_Proxies'; ob.hide_render=True; ob.display_type='WIRE'; ob.hide_set(True)
        elif role.startswith('armour_'):
            cat='04_Armour_Proxies'; ob.hide_render=True; ob.display_type='WIRE'; ob.hide_set(True)
        elif role.startswith('interior_'):
            cat='02_Interior_Visual'; ob.hide_render=True; ob.hide_set(True)
        elif ob.type=='EMPTY': cat='05_Functional_Anchors'
        else: cat='01_Exterior'
        categories[cat].objects.link(ob)
        ASSET_COLLECTION.objects.unlink(ob)
        ob['asset_layer']=cat
        ob['historically_certified']=False
        if ob.type!='MESH': continue
        uv=ob.data.uv_layers.new(name='UVMap') if not ob.data.uv_layers else ob.data.uv_layers[0]
        for face in ob.data.polygons:
            axis=max(range(3),key=lambda i:abs(face.normal[i]))
            mat=ob.data.materials[face.material_index] if ob.data.materials else None
            wood=mat and mat.name=='DeckGrey'
            for loop_index in face.loop_indices:
                v=ob.data.vertices[ob.data.loops[loop_index].vertex_index].co
                a,b=(v.x,v.y) if axis==2 else (v.y,v.z) if axis==0 else (v.x,v.z)
                uv.data[loop_index].uv=(a/(3.6 if wood else 5),b/(12 if wood else 5))
    return categories


def v4_validation():
    checks=[]
    def check(name,condition,evidence): checks.append({'check':name,'passed':bool(condition),'evidence':evidence})
    hull=bpy.data.objects['Hull']
    check('hull_length_213_4m',abs(hull.dimensions.y-213.4)<.01,list(hull.dimensions))
    check('hull_beam_27_2m',abs(hull.dimensions.x-27.2)<.02,list(hull.dimensions))
    check('draft_9_9m',abs(min(v.co.z for v in hull.data.vertices)+9.9)<.01,'keel z')
    check('four_independent_yaw_pivots',all(bpy.data.objects.get('Turret_'+k) is not None for k in TURRETS),list(TURRETS))
    check('eight_muzzles_at_barrel_tips',all(abs(bpy.data.objects[f'Muzzle_{k}_{s}'].location.y-BARREL_END_M)<.001 for k in TURRETS for s in ('Port','Starboard')),8)
    check('Q_between_funnels_2_3',FUNNELS[3][0]<TURRETS['Q'][0]<FUNNELS[2][0],TURRETS['Q'][0])
    check('round_middle_funnel',FUNNELS[2][1]==FUNNELS[2][2],FUNNELS[2])
    check('single_pole_masts',all(bpy.data.objects[n]['legs']==1 for n in ('Mast_Fore','Mast_Main')),2)
    check('sixteen_secondary_guns',all(bpy.data.objects.get(f'Casemate_{side}_{i}') for side in ('Port','Starboard') for i in range(1,9)),16)
    check('fourteen_interior_modules',len([o for o in bpy.data.objects if o.get('component_role')=='interior_module'])==14,14)
    check('sternwalk_present',bpy.data.objects.get('Sternwalk') is not None,'Sternwalk')
    bad=[]
    for ob in bpy.data.objects:
        if ob.type=='MESH' and ob.get('export_asset'):
            if any(not math.isfinite(c) for v in ob.data.vertices for c in v.co): bad.append(ob.name)
    check('finite_geometry',not bad,bad)
    ext=[o for o in bpy.data.objects if o.type=='MESH' and o.get('asset_layer')=='01_Exterior']
    check('exterior_mesh_budget',len(ext)<=65,len(ext))
    report={'status':'passed' if all(c['passed'] for c in checks) else 'failed','checks':checks,'historically_certified':False}
    (OUT/'verification_v4.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if report['status']!='passed': raise RuntimeError(json.dumps(report))
    return report


def write_v4_manifest():
    material_rows=[]
    for name,mat in MATERIALS.items():
        images={kind:f'textures/{name}_{kind}.png' for kind in ('BaseColor','Normal','MetallicSmoothness') if (OUT/'textures'/f'{name}_{kind}.png').is_file()}
        material_rows.append({'name':name,'shader':'Universal Render Pipeline/Lit','base_color':list(mat.diffuse_color),
            'metallic':mat.get('metallic',0),'smoothness':mat.get('smoothness',.35),'textures':images})
    (OUT/'material_manifest.json').write_text(json.dumps({'materials':material_rows,'normal_convention':'OpenGL tangent space','metallic_channel':'R','smoothness_channel':'A'},indent=2),encoding='utf-8')
    rows=[]
    for ob in sorted(bpy.data.objects,key=lambda o:o.name):
        if not ob.get('export_asset'): continue
        rows.append({'name':ob.name,'parent':ob.parent.name if ob.parent else None,'role':ob.get('component_role'),
            'layer':ob.get('asset_layer'),'module_id':ob.get('module_id'),'origin_m':list(ob.matrix_world.translation),
            'dimensions_m':list(ob.dimensions),'triangles':sum(len(p.vertices)-2 for p in ob.data.polygons) if ob.type=='MESH' else 0})
    (OUT/'object_manifest_v4.json').write_text(json.dumps({'asset':'Queen_Mary_v4','objects':rows,'total_triangles':sum(r['triangles'] for r in rows),'historically_certified':False},indent=2),encoding='utf-8')
    (OUT/'created_objects.txt').write_text('\n'.join(f"{r['name']:42} {r['dimensions_m']} | {r['role']}" for r in rows),encoding='utf-8')
    print((OUT/'created_objects.txt').read_text(encoding='utf-8'),flush=True)


def setup_studio():
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.cycles.device='CPU'
    scene.render.threads_mode='FIXED'; scene.render.threads=8
    scene.render.image_settings.file_format='PNG'
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.20,.24,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
    scene.view_settings.view_transform='AgX' if bpy.app.version>=(4,0,0) else 'Standard'
    for name,position,power,size,color in [('Key',(60,80,130),270000,100,(1,.89,.75)),('Fill',(-90,20,70),190000,90,(.65,.79,1)),('Rim',(0,-150,95),340000,90,(.8,.9,1))]:
        data=bpy.data.lights.new('Studio_'+name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size; data.color=color
        ob=bpy.data.objects.new(data.name,data); PREVIEW_COLLECTION.objects.link(ob); ob.location=position
        ob.rotation_euler=(Vector((0,0,0))-ob.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=2000,location=(0,0,-12))
    floor=bpy.context.object; floor.name='Studio_Backdrop'
    for c in list(floor.users_collection):c.objects.unlink(floor)
    PREVIEW_COLLECTION.objects.link(floor)
    mat=create_pbr_material('Studio_Backdrop_Mat',(.085,.105,.125),0,.9)
    floor.data.materials.append(mat)
    for name,pos,target,scale,res in [
        ('Exterior_Hero',(185,135,100),(0,0,7),233,(2000,1200)),
        ('Exterior_Profile',(300,0,17),(0,0,10),232,(2000,740)),
        ('A_B_Bridge_Detail',(57,90,38),(0,49,11),74,(1600,1100)),
        ('Stern_Detail',(45,-145,27),(0,-90,4),61,(1500,1000)),
        ('Cutaway_Overview',(200,115,65),(0,0,-1),229,(2000,1100)),
        ('Cutaway_Magazine_A',(36,88,15),(0,57,1),49,(1600,1200)),
        ('Cutaway_Machinery',(56,-27,13),(0,-10,-3),79,(1800,1100))]:
        data=bpy.data.cameras.new('Camera_'+name); ob=bpy.data.objects.new(data.name,data); PREVIEW_COLLECTION.objects.link(ob)
        ob.location=pos; ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
        data.type='ORTHO'; data.ortho_scale=scale; data.clip_end=3000
        ob['render_resolution']=res
    scene.camera=bpy.data.objects['Camera_Exterior_Hero']
    scene.render.resolution_x=2000; scene.render.resolution_y=1200; scene.render.resolution_percentage=100
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.clip_end=3000
                area.spaces.active.region_3d.view_distance=250
                area.spaces.active.region_3d.view_location=(0,0,5)
                area.spaces.active.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
                area.spaces.active.shading.color_type='MATERIAL'


def render_view(name):
    scene=bpy.context.scene; cam=bpy.data.objects['Camera_'+name]; scene.camera=cam
    scene.render.resolution_x,scene.render.resolution_y=cam['render_resolution']
    scene.render.filepath=str(OUT/'previews'/(name+'.png'))
    print('RENDER '+name,flush=True)
    bpy.ops.render.render(write_still=True)


def create_cutaway():
    """Bisect the presentation copy only; complete asset was already saved/exported."""
    for ob in list(bpy.data.objects):
        cat=ob.get('asset_layer','')
        if cat=='02_Interior_Visual':
            ob.hide_render=False; ob.hide_set(False)
        if ob.type!='MESH' or cat not in ('01_Exterior','02_Interior_Visual'):continue
        # Keep equipment intact for readability, cut the shell and structural partitions.
        if ob.get('component_role')=='interior_equipment':continue
        bm=bmesh.new(); bm.from_mesh(ob.data)
        transform=ob.matrix_world
        for v in bm.verts: v.co=transform@v.co
        geom=list(bm.verts)+list(bm.edges)+list(bm.faces)
        bmesh.ops.bisect_plane(bm,geom=geom,dist=.00001,plane_co=(0,0,0),plane_no=(1,0,0),clear_outer=True)
        inv=transform.inverted()
        for v in bm.verts:v.co=inv@v.co
        bm.to_mesh(ob.data);bm.free();ob.data.update()
    bpy.context.scene['presentation_mode']='starboard half removed for inspection; nonphysical section model'
    bpy.context.scene.camera=bpy.data.objects['Camera_Cutaway_Overview']


def export_v4_fbx(interior=False):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in bpy.data.objects:
        if not ob.get('export_asset'):continue
        cat=ob.get('asset_layer')
        allowed=cat in ('01_Exterior','05_Functional_Anchors') if not interior else cat in ('02_Interior_Visual','05_Functional_Anchors')
        if allowed:
            ob.hide_set(False);ob.select_set(True)
    root=bpy.data.objects['Queen_Mary'];bpy.context.view_layer.objects.active=root
    rest=root.matrix_world.copy();root.matrix_world=Matrix.Rotation(math.pi,4,'Z')@rest;bpy.context.view_layer.update()
    try:
        bpy.ops.export_scene.fbx(filepath=str(OUT/('QueenMary_v4_Interior.fbx' if interior else 'QueenMary_v4_Exterior.fbx')),
            use_selection=True,object_types={'MESH','EMPTY'},global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
            axis_forward='-Z',axis_up='Y',use_space_transform=True,bake_space_transform=False,use_mesh_modifiers=True,
            add_leaf_bones=False,bake_anim=False,path_mode='RELATIVE',embed_textures=False,use_custom_props=True)
    finally:root.matrix_world=rest;bpy.context.view_layer.update()


def main():
    global OUT
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description='Queen Mary v4 modular presentation asset')
    parser.add_argument('--out',type=Path,default=Path(globals().get('__file__',bpy.data.filepath or 'queen_mary_v4.py')).resolve().parent)
    parser.add_argument('--skip-render',action='store_true')
    parser.add_argument('--views',default='all')
    config=parser.parse_args(args); OUT=config.out.resolve();OUT.mkdir(parents=True,exist_ok=True)
    for directory in ('textures','previews'): (OUT/directory).mkdir(exist_ok=True)
    started=datetime.now(timezone.utc).isoformat()
    (OUT/'build_started.json').write_text(json.dumps({'started_utc':started}),encoding='utf-8')
    try:
        root=build_ship()
        make_presentation_refinement(root)
        make_internal_visuals(root)
        bpy.context.view_layer.update()
        assign_uvs_and_collections()
        bpy.context.view_layer.update()
        verification=v4_validation();write_v4_manifest()
        export_v4_fbx(False);export_v4_fbx(True)
        # Restore intended full-model visibility after selection/export.
        for ob in bpy.data.objects:
            if ob.get('asset_layer') in ('02_Interior_Visual','03_Damage_Proxies','04_Armour_Proxies'):
                ob.hide_set(True)
        setup_studio()
        bpy.context.preferences.filepaths.save_version=0
        for im in bpy.data.images:
            if im.name.endswith(('_BaseColor','_Normal','_MetallicSmoothness')):
                im.filepath='//textures/'+im.name+'.png'
        bpy.context.scene['asset_version']='v4_modular_presentation'
        bpy.context.scene['reference_note']='18 is image identifier per user, not a year; exact fit remains provisional'
        text=bpy.data.texts.new('README_FIRST')
        text.write('Queen Mary v4 | 1 Blender unit = 1 metre. +Y bow, Z up.\n'
          'Exterior, Interior_Visual, Damage_Proxies and Armour_Proxies are separate collections.\n'
          'Internal equipment arrangement is inferred, NOT a historically certified machinery plan.\n'
          'Cutaway file is a presentation derivative. Export full exterior/interior FBX files for integration.\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'QueenMary_v4_Full.blend'))
        requested=None if config.views=='all' else set(config.views.split(','))
        if not config.skip_render:
            for view in ('Exterior_Hero','Exterior_Profile','A_B_Bridge_Detail','Stern_Detail'):
                if requested is None or view in requested:render_view(view)
        create_cutaway()
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'QueenMary_v4_Cutaway.blend'))
        if not config.skip_render:
            for view in ('Cutaway_Overview','Cutaway_Magazine_A','Cutaway_Machinery'):
                if requested is None or view in requested:render_view(view)
        report={'status':'complete','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
                'blender':bpy.app.version_string,'historically_certified':False,'geometry_checks':len(verification['checks'])}
    except Exception:
        report={'status':'failed','started_utc':started,'traceback':traceback.format_exc()}
        (OUT/'build_result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        raise
    (OUT/'build_result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('BUILD COMPLETE',flush=True)


if __name__=='__main__':main()
