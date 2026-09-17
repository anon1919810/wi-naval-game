"""Run inside Blender after loading Queen Mary; writes persistent evidence.

Two layers, deliberately separated:

  geometry    blocking invariants. The asset must be internally consistent:
              dimensions, hierarchy, pivots, attachments inside the hull,
              nothing floating, module budget. A failure must stop the build.

  assumption  historical claims the asset encodes. These are reported with their
              source and never treated as certification. They document what the
              current configuration asserts, so a wrong assumption stays visible
              instead of hiding behind a green tick.

run: blender --background HMS_Queen_Mary_1913_Greybox.blend --python verify_blender.py
"""

import json
import math
import sys
import itertools
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
import queen_mary as qm  # noqa: E402  single source of truth for the offsets maths

qm.load_offsets()

CHECKS = []
WARNINGS = []


def check(label, passed, layer='geometry', evidence=None, source=None, status=None):
    entry = {'check': label, 'passed': bool(passed), 'layer': layer,
             'blocking': layer == 'geometry'}
    if evidence is not None:
        entry['evidence'] = evidence
    if source is not None:
        entry['source'] = source
    if status is not None:
        entry['status'] = status
    CHECKS.append(entry)
    return bool(passed)


def mesh_bounds(obj):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not coords:
        return None
    return (Vector((min(c[i] for c in coords) for i in range(3))),
            Vector((max(c[i] for c in coords) for i in range(3))))


def object_bounds(obj):
    if obj.type == 'MESH':
        return mesh_bounds(obj)
    if obj.type == 'EMPTY':
        t = obj.matrix_world.translation.copy()
        return t, t
    return None


def envelope_halfbeam(y, z):
    """Width the ship allows at this station and height (deck edge above the deck)."""
    if z <= qm.DECK_Z:
        return qm.halfbeam_at(y, z)
    return qm.deck_halfbeam(y)


def main():
    objects = bpy.data.objects
    exported = [obj for obj in objects if obj.get('export_asset')]

    # --- required modules ---------------------------------------------------
    required = ['Queen_Mary', 'Hull', 'Forecastle', 'Quarterdeck', 'Superstructure',
                'Bridge', 'Conning_Tower', 'Sternwalk', 'Mast_Fore', 'Mast_Main',
                'Rangefinder_CT', 'Damage_Modules', 'FX_Anchors', 'Propeller_Shafts',
                'Rudder', 'Steering_Gear',
                'Casemate_Openings_Port', 'Casemate_Openings_Starboard',
                'Torpedo_Net_Port_Stowed', 'Torpedo_Net_Starboard_Stowed']
    required += ['Turret_' + k for k in 'ABQX']
    required += ['Elevation_' + k for k in 'ABQX']
    required += ['Barbette_' + k for k in 'ABQX']
    required += ['Barrel_{}_{}'.format(k, s) for k in 'ABQX' for s in ('Port', 'Starboard')]
    required += ['Funnel_{}'.format(i) for i in (1, 2, 3)]
    required += ['Funnel_{}_Uptake'.format(i) for i in (1, 2, 3)]
    required += ['Casemate_{}_{}'.format(s, i) for s in ('Port', 'Starboard') for i in range(1, 9)]
    required += [name for name, _, _, _, _, _ in qm.DAMAGE_VOLUMES]
    required += ['Armour_Belt_229mm', 'Armour_Upper_Belt_152mm', 'Armour_Deck_64mm',
                 'Armour_Deck_25mm', 'Armour_Bulkhead_Fwd', 'Armour_Bulkhead_Aft']
    missing = [name for name in required if name not in objects]
    check('All required semantic module names exist', not missing,
          evidence={'missing': missing, 'required_count': len(required)})
    if missing:
        return CHECKS

    hull = objects['Hull']

    # --- dimensions and frame ----------------------------------------------
    check('Hull dimensions are 27.2 x 213.4 x 15.0 metres',
          all(abs(a - b) < 0.002 for a, b in zip(hull.dimensions, (27.2, 213.4, 15.0))),
          evidence={'dimensions': [round(v, 6) for v in hull.dimensions]})
    hb = mesh_bounds(hull)
    check('Hull envelope is Y -106.7..+106.7 and X +-13.6',
          abs(hb[0].y + 106.7) < 0.002 and abs(hb[1].y - 106.7) < 0.002
          and abs(hb[0].x + 13.6) < 0.002 and abs(hb[1].x - 13.6) < 0.002,
          evidence={'min': [round(v, 6) for v in hb[0]], 'max': [round(v, 6) for v in hb[1]]})
    check('Metres, waterline root, no object scale',
          bpy.context.scene.unit_settings.scale_length == 1
          and objects['Queen_Mary'].location.length < 1e-6
          and all(all(abs(s - 1) < 1e-5 for s in o.scale) for o in objects if o.type == 'MESH'))
    check('Hull keel -9.9 m and main deck +5.1 m',
          abs(hb[0].z + 9.9) < 0.002 and abs(hb[1].z - 5.1) < 0.002,
          evidence={'keel_z': round(hb[0].z, 6), 'deck_z': round(hb[1].z, 6)})

    # --- layout -------------------------------------------------------------
    order = ['Turret_A', 'Turret_B', 'Mast_Fore', 'Funnel_1', 'Funnel_2',
             'Turret_Q', 'Funnel_3', 'Mast_Main', 'Turret_X']
    ys = [objects[n].matrix_world.translation.y for n in order]
    check('Module order fore to aft is A B foremast F1 F2 Q F3 mainmast X',
          all(a > b for a, b in zip(ys, ys[1:])),
          evidence={n: round(v, 3) for n, v in zip(order, ys)})
    check('B turret superfires above A',
          objects['Turret_B'].matrix_world.translation.z
          > objects['Turret_A'].matrix_world.translation.z + 2.5,
          evidence={'B_z': round(objects['Turret_B'].matrix_world.translation.z, 3),
                    'A_z': round(objects['Turret_A'].matrix_world.translation.z, 3)})
    funnel_tops = [mesh_bounds(objects['Funnel_{}'.format(i)])[1].z for i in (1, 2, 3)]
    check('All three funnel tops level at {:.1f} m'.format(qm.FUNNEL_TOP_Z),
          max(abs(v - qm.FUNNEL_TOP_Z) for v in funnel_tops) < 0.05,
          evidence=[round(v, 4) for v in funnel_tops],
          source=qm.SOURCES['ww1'], layer='assumption',
          status='matches_source')

    # --- attachments stay inside the hull ----------------------------------
    allowance = {'sternwalk': 1.75, 'sternwalk_rail': 1.75, 'stowed_net_mesh': 0.85,
                 'casemate_opening': 0.20, 'secondary_gun': 2.65, 'bulwark': 0.20,
                 'armour_belt': 0.06, 'armour_deck': 0.06}
    worst = None
    violations = []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        role = obj.get('component_role')
        if role not in allowance:
            continue
        limit_extra = allowance[role]
        for vert in obj.data.vertices:
            world = obj.matrix_world @ vert.co
            limit = envelope_halfbeam(world.y, world.z) + limit_extra
            excess = abs(world.x) - limit
            if excess > 1e-6:
                entry = {'object': obj.name, 'role': role, 'excess_m': round(excess, 4),
                         'y_m': round(world.y, 3), 'z_m': round(world.z, 3),
                         'x_m': round(abs(world.x), 3),
                         'hull_halfbeam_m': round(envelope_halfbeam(world.y, world.z), 3),
                         'allowance_m': limit_extra}
                violations.append(entry)
                if worst is None or excess > worst['excess_m']:
                    worst = entry
    violations.sort(key=lambda item: -item['excess_m'])
    check('Every attachment stays inside the hull envelope plus its allowance',
          not violations,
          evidence=worst if not violations else {'count': len(violations),
                                                 'worst_five': violations[:5]})

    # --- nothing floats -----------------------------------------------------
    depsgraph = bpy.context.evaluated_depsgraph_get()
    supported_roles = ('forecastle_deck', 'quarterdeck', 'bridge', 'conning_tower',
                       'structure', 'funnel', 'tripod_mast', 'main_turret', 'barbette',
                       'fire_control')

    # Support surfaces: the two deck slabs use their sheer function (an AABB top
    # would be the highest point of the whole deck), everything else its top face.
    support_surfaces = []
    for candidate in objects:
        if candidate.type != 'MESH':
            continue
        role = candidate.get('component_role')
        bounds = mesh_bounds(candidate)
        if bounds is None:
            continue
        surface_z = bounds[1].z
        support_surfaces.append([candidate.name, role, surface_z, bounds[0], bounds[1]])

    def overlap(a_min, a_max, b_min, b_max):
        return min(a_max, b_max) - max(a_min, b_min)

    floating = []
    for obj in objects:
        if obj.type != 'MESH' or obj.get('component_role') not in supported_roles:
            continue
        bounds = mesh_bounds(obj)
        if bounds is None:
            continue
        mn, mx = bounds
        cy = (mn.y + mx.y) / 2.0
        reported = []
        supported = False
        for name, role, surface_z, c_min, c_max in support_surfaces:
            if name == obj.name:
                continue
            if role == 'forecastle_deck':
                surface_z = qm.forecastle_z(min(max(cy, qm.FORE_AFT_END), 106.7))
            elif role == 'quarterdeck':
                surface_z = qm.quarterdeck_z(min(max(cy, -106.7), qm.FORE_AFT_END))
            if overlap(mn.x, mx.x, c_min.x, c_max.x) < 0.4:
                continue
            if overlap(mn.y, mx.y, c_min.y, c_max.y) < 0.4:
                continue
            gap = mn.z - surface_z
            if -0.60 <= gap <= 0.02:
                supported = True
                break
            reported.append((name, round(gap, 3)))
        if not supported:
            floating.append({'object': obj.name, 'role': obj.get('component_role'),
                             'bottom_z_m': round(mn.z, 3),
                             'nearest_surfaces': sorted(reported, key=lambda item: abs(item[1]))[:3]})
    check('Every structure is supported by a deck or by the module below it',
          not floating, evidence=floating or 'all supported')

    # --- decks and casemates ------------------------------------------------
    deck_errors = []
    forecastle = objects['Forecastle']
    f_bounds = mesh_bounds(forecastle)
    if abs(f_bounds[0].z - (qm.DECK_Z - 0.05)) > 0.01:
        deck_errors.append({'object': 'Forecastle', 'bottom_z': round(f_bounds[0].z, 4)})
    for index, y in enumerate(qm.CASEMATE_YS, 1):
        for side, sign in (('Port', -1), ('Starboard', 1)):
            gun = objects['Casemate_{}_{}'.format(side, index)]
            axis = qm.casemate_axis_z(y)
            origin = gun.matrix_world.translation
            surface = qm.halfbeam_at(y, axis)
            if abs(origin.z - axis) > 0.01 or abs(abs(origin.x) - surface) > 0.02 \
                    or abs(origin.y - y) > 0.01:
                deck_errors.append({'object': gun.name, 'origin': [round(v, 4) for v in origin],
                                    'expected_z': round(axis, 4),
                                    'hull_surface_m': round(surface, 4)})
    check('Casemate guns sit on the hull surface at the configured axis height',
          not deck_errors, evidence=deck_errors or 'all on surface',
          source=qm.SOURCES['wiki'], status='axis height unverified')
    turret_errors = []
    for key in 'ABQX':
        y, deck_source, barbette_h, _ = qm.TURRETS[key]
        deck = qm.SUPERFIRING_DECK_Z if deck_source == 'superfiring' else qm.deck_at(y)
        base = objects['Turret_' + key].matrix_world.translation.z
        if abs(base - (deck + barbette_h)) > 0.005:
            turret_errors.append({'turret': key, 'base_z': round(base, 4),
                                  'expected': round(deck + barbette_h, 4), 'deck': deck_source})
        pitch_z = objects['Elevation_' + key].matrix_world.translation.z
        if abs(pitch_z - (base + 1.5)) > 0.005:
            turret_errors.append({'turret': key, 'trunnion_z': round(pitch_z, 4)})
    check('Turret bases sit on their deck and trunnions stay at the designed height',
          not turret_errors, evidence=turret_errors or 'all on deck')

    # --- internal volumes fit inside the hull ------------------------------
    volume_errors = []
    for name, y, _, size, role_name, _ in qm.DAMAGE_VOLUMES:
        bounds = mesh_bounds(objects[name])
        half = (bounds[1].x - bounds[0].x) / 2.0
        limit = qm.halfbeam_at(y, bounds[0].z) - 0.4
        if half > limit + 1e-6:
            volume_errors.append({'module': name, 'half_width_m': round(half, 3),
                                  'hull_allows_m': round(limit, 3)})
        if bounds[0].z < qm.keel_at(y) + 0.2:
            volume_errors.append({'module': name, 'bottom_z': round(bounds[0].z, 3),
                                  'keel_z': round(qm.keel_at(y), 3)})
        if bounds[1].z > qm.DECK_Z - 0.2:
            volume_errors.append({'module': name, 'top_z': round(bounds[1].z, 3)})
    check('Internal damage volumes fit inside the hull shell', not volume_errors,
          evidence=volume_errors or 'all inside')

    # --- turret integrity and motion ---------------------------------------
    integrity = []
    for key in 'ABQX':
        pitch = objects['Elevation_' + key]
        turret = objects['Turret_' + key]
        if pitch.parent is not turret:
            integrity.append({'turret': key, 'issue': 'elevation is not a child of the turret'})
        if objects['Barbette_' + key].parent is turret:
            integrity.append({'turret': key, 'issue': 'barbette is parented to the turret'})
        if abs(pitch.location.y - qm.TRUNNION_Y_M) > 1e-3:
            integrity.append({'turret': key, 'issue': 'trunnion not at the front',
                              'y': round(pitch.location.y, 4)})
        for side in ('Port', 'Starboard'):
            barrel = objects['Barrel_{}_{}'.format(key, side)]
            if barrel.parent is not pitch:
                integrity.append({'turret': key, 'barrel': side, 'issue': 'not on the pivot'})
            if abs(barrel.location.length) > 1e-6 and barrel.parent is pitch:
                if abs(barrel.location.y) > 1e-6:
                    integrity.append({'turret': key, 'barrel': side,
                                      'issue': 'barrel origin is not its own trunnion',
                                      'local': [round(v, 4) for v in barrel.location]})
    check('Turret module integrity: pivot chain, front trunnion, individual barrels',
          not integrity, evidence=integrity or 'all four turrets intact')

    motion_failures = []
    for key in 'ABQX':
        turret = objects['Turret_' + key]
        pitch = objects['Elevation_' + key]
        barrel = objects['Barrel_{}_Port'.format(key)]
        barbette = objects['Barbette_' + key]
        rest_yaw = turret.rotation_euler.copy()
        rest_pitch = pitch.rotation_euler.copy()
        barbette_before = barbette.matrix_world.copy()
        pivot_before = turret.matrix_world.translation.copy()
        point_before = barrel.matrix_world @ Vector((0, 6, 0))
        turret.rotation_euler.z += math.radians(35)
        pitch.rotation_euler.x += math.radians(15)
        bpy.context.view_layer.update()
        point_after = barrel.matrix_world @ Vector((0, 6, 0))
        ok = ((point_after - point_before).length > 1
              and (turret.matrix_world.translation - pivot_before).length < 1e-5
              and all(abs(barbette.matrix_world[r][c] - barbette_before[r][c]) < 1e-5
                      for r in range(4) for c in range(4)))
        if not ok:
            motion_failures.append({'turret': key})
        turret.rotation_euler = rest_yaw
        pitch.rotation_euler = rest_pitch
        bpy.context.view_layer.update()
    check('Yaw and elevation move the barrels and leave mount and barbette fixed',
          not motion_failures, evidence=motion_failures or 'all four turrets articulate')

    # --- secondary battery --------------------------------------------------
    for side, sign in (('Port', -1), ('Starboard', 1)):
        guns = [o for o in objects if o.get('component_role') == 'secondary_gun'
                and o.get('side') == side]
        check('{}: exactly 8 secondary guns on the correct side'.format(side),
              len(guns) == 8 and all(o.matrix_world.translation.x * sign > 0 for o in guns),
              evidence={'count': len(guns)},
              source=qm.SOURCES['wiki'], status='16 on one deck per source')

    # --- decoration merged, modules kept -----------------------------------
    decoration_roles = ('stowed_net_mesh', 'casemate_opening', 'sternwalk_rail')
    decoration = [o.name for o in objects if o.get('component_role') in decoration_roles]
    loose_patterns = ('Net_Bundle_', 'Net_Boom_', 'Sternwalk_Rail_', 'Muzzle_',
                      'Casemate_Recess_')
    loose = [o.name for o in objects if o.name.startswith(loose_patterns)]
    movable = [o.name for o in objects if o.get('component_role') in
               ('main_turret', 'gun_elevation', 'main_gun_barrel')]
    check('Decoration is merged and combat modules stay separate',
          len(decoration) <= 10 and not loose and len(movable) == 16,
          evidence={'decoration': sorted(decoration), 'loose_parts': loose,
                    'movable_modules': len(movable),
                    'module_contract': 'per-module objects, decoration merged'})
    internal_roles = ('magazine', 'boiler_room', 'engine_room', 'steering_gear',
                      'armour_belt', 'armour_deck', 'armour_bulkhead')
    render_meshes = [o.name for o in exported if o.type == 'MESH'
                     and o.get('component_role') not in internal_roles]
    internal_meshes = [o.name for o in exported if o.type == 'MESH'
                       and o.get('component_role') in internal_roles]
    check('Ship stays inside the object budget for 10-30 ships on screen',
          len(render_meshes) <= 65 and len(exported) <= 110,
          evidence={'render_meshes': len(render_meshes),
                    'internal_volume_meshes': len(internal_meshes),
                    'exported_objects_total': len(exported),
                    'preview_objects_excluded': len(objects) - len(exported),
                    'note': 'internal volumes and armour belong on a collision-only '
                            'layer in Unity, so they must not cost draw calls'})

    # --- damage and fire control data --------------------------------------
    data_gaps = []
    for name, _, _, _, role_name, _ in qm.DAMAGE_VOLUMES:
        obj = objects[name]
        if not obj.get('volume_defined') or obj.get('placeholder_only'):
            data_gaps.append({'module': name, 'issue': 'volume not defined'})
        if not obj.get('source'):
            data_gaps.append({'module': name, 'issue': 'no provenance'})
    if not objects['Rangefinder_CT'].get('fire_control_system'):
        data_gaps.append({'module': 'Rangefinder_CT', 'issue': 'no fire control system recorded'})
    boiler_rooms = [o for o in objects if o.get('component_role') == 'boiler_room']
    if len(boiler_rooms) != qm.SHIP['boiler_rooms']:
        data_gaps.append({'issue': 'boiler room count', 'found': len(boiler_rooms),
                          'expected': qm.SHIP['boiler_rooms']})
    check('Damage modules carry a volume and provenance; 7 boiler rooms exist',
          not data_gaps, evidence=data_gaps or 'complete')

    # --- resting clearance and firing arcs ---------------------------------
    obstruction_roles = ('funnel', 'funnel_uptake', 'bridge', 'conning_tower', 'structure',
                         'tripod_mast', 'fire_control', 'forecastle_deck', 'quarterdeck',
                         'hull', 'barbette', 'main_turret', 'main_gun_barrel', 'sternwalk')
    obstacles = []
    for obj in objects:
        if obj.type != 'MESH' or obj.get('component_role') not in obstruction_roles:
            continue
        bounds = mesh_bounds(obj)
        obstacles.append((obj.name, obj.get('component_role'), bounds[0], bounds[1]))

    def clearance(origin, direction, length, ignore):
        """Minimum distance from the barrel centre line to any obstacle box."""
        best = (1e9, None)
        for name, role, mn, mx in obstacles:
            if name in ignore:
                continue
            for step in range(0, 14):
                point = origin + direction * (length * step / 13.0)
                dx = max(mn.x - point.x, 0.0, point.x - mx.x)
                dy = max(mn.y - point.y, 0.0, point.y - mx.y)
                dz = max(mn.z - point.z, 0.0, point.z - mx.z)
                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                if dist < best[0]:
                    best = (dist, name)
        return best

    arcs = {}
    resting = []
    for key in 'ABQX':
        turret = objects['Turret_' + key]
        pitch = objects['Elevation_' + key]
        barrel = objects['Barrel_{}_Port'.format(key)]
        ignore = {turret.name, pitch.name, barrel.name, 'Barbette_' + key,
                  'Barrel_{}_Starboard'.format(key)}
        rest_yaw = turret.rotation_euler.z
        rest_pitch = pitch.rotation_euler.x
        per_elevation = {}
        for elevation in (0, 5, 10, 15, 20):
            pitch.rotation_euler.x = rest_pitch + math.radians(elevation)
            allowed = []
            for yaw in range(0, 360, 5):
                turret.rotation_euler.z = rest_yaw + math.radians(yaw)
                bpy.context.view_layer.update()
                origin = barrel.matrix_world.translation.copy()
                direction = (barrel.matrix_world @ Vector((0, 1, 0))) \
                    - (barrel.matrix_world @ Vector((0, 0, 0)))
                direction.normalize()
                dist, blocker = clearance(origin, direction, qm.BARREL_END_M - 0.3, ignore)
                if elevation == 0 and yaw == 0:
                    resting.append({'turret': key, 'clearance_m': round(dist, 3),
                                    'nearest': blocker})
                if dist >= 0.30:
                    allowed.append(yaw)
            intervals = []
            start = None
            previous = None
            for value in allowed:
                if start is None:
                    start = value
                elif value != previous + 5:
                    intervals.append([start, previous])
                    start = value
                previous = value
            if start is not None:
                intervals.append([start, previous])
            per_elevation[str(elevation)] = {
                'allowed_yaw_intervals_deg': intervals,
                'clear_fraction': round(len(allowed) / 72.0, 3)}
        turret.rotation_euler.z = rest_yaw
        pitch.rotation_euler.x = rest_pitch
        bpy.context.view_layer.update()
        arcs[key] = {'zero_bearing': 'forward +Y, as built' if turret.get('rest_forward_local')
                     else 'unknown',
                     'rest_yaw_deg': round(math.degrees(rest_yaw), 2),
                     'by_elevation': per_elevation}
    worst_rest = min(resting, key=lambda item: item['clearance_m'])
    check('Resting barrels clear funnels, masts and superstructure',
          worst_rest['clearance_m'] > 0.10,
          evidence={'worst': worst_rest, 'all': resting})
    (OUT / 'firing_arcs.json').write_text(json.dumps({
        'method': 'barrel centre line sampled against obstacle bounding boxes',
        'accuracy': 'conservative approximation; not a ballistics or blast model',
        'clearance_required_m': 0.30,
        'increment_deg': 5,
        'note': 'main_turret, barbette and main_gun_barrel boxes are excluded as obstacles',
        'turrets': arcs}, indent=2), encoding='utf-8')
    check('Firing arcs derived from geometry and written to firing_arcs.json',
          True, layer='assumption',
          evidence={'file': 'firing_arcs.json',
                    'clear_fraction_at_0deg': {k: v['by_elevation']['0']['clear_fraction']
                                               for k, v in arcs.items()}},
          status='derived, needs review against gunnery sources')

    # --- derived game data (damage model, hydrostatics, contract) -----------
    derived = {}
    for name in ('damage_model.json', 'hydrostatics.json',
                 'buoyancy_compartments.json', 'ship_contract.json',
                 'ship_contract.unity.json'):
        path = OUT / name
        derived[name] = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    missing_files = [name for name, payload in derived.items() if payload is None]
    check('Derived game data files were written next to the asset',
          not missing_files, evidence=missing_files or sorted(derived))
    if not missing_files:
        damage = derived['damage_model.json']
        hydro = derived['hydrostatics.json']
        buoyancy = derived['buoyancy_compartments.json']
        contract = derived['ship_contract.json']

        hoist = {link['source']: link['target'] for link in damage['systems']['gunnery']}
        director_links = damage['systems']['fire_control']
        check('Every turret is linked to its magazine and to the director',
              all(hoist.get('Magazine_' + key) == 'Turret_' + key for key in 'ABQX')
              and len(director_links) == 4,
              evidence={'feed_hoists': hoist, 'director_links': len(director_links)})

        steam = {link['source']: link['target'] for link in damage['systems']['propulsion']
                 if link['relation'] == 'supplies_steam_to'}
        smoke = {}
        for link in damage['systems']['propulsion']:
            if link['relation'] == 'exhausts':
                smoke.setdefault(link['source'], []).append(link['target'])
        check('Seven boiler rooms feed the engine rooms and every funnel has a smoke source',
              sorted(steam) == sorted('Boiler_Room_{}'.format(i) for i in range(1, 8))
              and all(len(smoke.get('Funnel_{}'.format(i), [])) >= 1 for i in (1, 2, 3)),
              evidence={'boiler_rooms_linked': len(steam), 'funnel_smoke_sources': smoke})

        compartments = []
        for obj in objects:
            if obj.type == 'MESH' and obj.get('component_role') in qm.PERMEABILITY:
                bounds = mesh_bounds(obj)
                compartments.append((obj.name, bounds[0], bounds[1]))
        overlaps = []
        for (name_a, min_a, max_a), (name_b, min_b, max_b) in itertools.combinations(compartments, 2):
            if all(min(max_a[i], max_b[i]) - max(min_a[i], min_b[i]) > 0.05 for i in range(3)):
                overlaps.append([name_a, name_b])
        check('Floodable compartments do not overlap each other',
              not overlaps and len(compartments) == len(qm.DAMAGE_VOLUMES),
              evidence={'compartments': len(compartments), 'overlaps': overlaps})

        check('Hydrostatics were integrated from the offsets table',
              hydro['immersed_volume_m3'] > 1000 and abs(hydro['lcb_y_m']) < 15
              and hydro['waterplane_area_m2'] > 1000,
              evidence={key: hydro[key] for key in
                        ('immersed_volume_m3', 'waterplane_area_m2', 'lcb_y_m', 'vcb_z_m',
                         'displacement_t_at_1_025', 'displacement_delta_pct')})
        check('Ship contract agrees with the manifest',
              contract['object_count'] == len(exported)
              and contract['turrets'][0]['turret'] == 'Turret_A'
              and all(entry['name'] in objects for entry in contract['secondary_guns']),
              evidence={'contract_objects': contract['object_count'],
                        'exported_objects': len(exported),
                        'turrets': len(contract['turrets']),
                        'secondary_guns': len(contract['secondary_guns'])})

        # 这两条是为 Unity 侧服务的：契约是那一侧唯一的字段来源，名字错一个就 fail fast，
        # 而 JsonUtility 读不了字典 —— 让问题在这里暴露，而不是等到 Unity 里才发现。
        flat = derived['ship_contract.unity.json'] or {}
        contract_names = set()
        for entry in contract['turrets']:
            contract_names |= {entry['turret'], entry['pivot'], entry['barbette']}
            contract_names |= set(entry['barrels'])
        contract_names |= {entry['name'] for entry in contract['secondary_guns']}
        contract_names |= {name for role in flat.get('module_roles', [])
                           for name in role['names']}
        unknown = sorted(name for name in contract_names if name not in objects)
        check('Every name in the contract resolves to a scene object',
              bool(contract_names) and not unknown,
              evidence=unknown[:12] or {'names_checked': len(contract_names)})

        unportable = []
        for key, value in flat.items():
            if isinstance(value, dict):
                unportable.append(key)
            elif isinstance(value, list) and any(
                    isinstance(item, dict) and any(isinstance(v, dict) for v in item.values())
                    for item in value):
                unportable.append(key)
        mesh_total = sum(1 for obj in exported if obj.type == 'MESH')
        check('Unity contract stays readable by JsonUtility',
              not unportable
              and flat.get('object_count') == len(exported)
              and flat.get('mesh_count') == mesh_total,
              evidence={'nested_dictionaries': unportable or 'none',
                        'object_count': flat.get('object_count'),
                        'mesh_count': flat.get('mesh_count'),
                        'scene': {'objects': len(exported), 'meshes': mesh_total},
                        'note': 'JsonUtility cannot deserialise dictionaries; '
                                'module_roles and file_refs carry that data as arrays'})

        check('Estimated sections are consistent with the published deep-load displacement',
              abs(hydro['displacement_delta_pct']) <= 15,
              layer='assumption', source=qm.SOURCES['wiki'],
              status='sections are still an estimate; this is an independent cross-check',
              evidence={'computed_t': hydro['displacement_t_at_1_025'],
                        'published_deep_load_t': qm.SHIP['displacement_full_t'],
                        'delta_pct': hydro['displacement_delta_pct'],
                        'floodable_share_pct': buoyancy.get('floodable_share_of_immersed_volume_pct')})

    # --- historical assumptions the asset encodes ---------------------------
    for name in ('Mast_Fore', 'Mast_Main'):
        check('{}: merged tripod module records three legs'.format(name),
              objects[name].get('legs') == 3,
              source=qm.SOURCES['user'] + ' | ' + qm.SOURCES['ww1'], layer='assumption',
              status='user_spec_only: ww1 reports a pole mast as built, altered to tripod later')
    check('Two tripod masts are a user requirement, not a certified fit',
          True, source=qm.SOURCES['user'], layer='assumption',
          status='conflicts_with_source: needs a dated photo')
    check('Funnel 2 circular, funnels 1 and 3 elliptical',
          abs(objects['Funnel_2'].dimensions.x - objects['Funnel_2'].dimensions.y) < 0.002
          and all(objects['Funnel_{}'.format(i)].dimensions.y
                  > objects['Funnel_{}'.format(i)].dimensions.x * 1.2 for i in (1, 3)),
          source=qm.SOURCES['ww1'], layer='assumption', status='matches_source')
    f_ys = [objects['Funnel_{}'.format(i)].matrix_world.translation.y for i in (1, 2, 3)]
    check('Funnel 1 and 2 are closer together than 2 and 3',
          f_ys[0] - f_ys[1] < f_ys[1] - f_ys[2], source=qm.SOURCES['user'],
          layer='assumption', status='user_spec_only',
          evidence={'spacing_m': [round(f_ys[0] - f_ys[1], 2), round(f_ys[1] - f_ys[2], 2)]})
    check('Sternwalk is present and derived from the hull surface',
          objects['Sternwalk'].get('derived_from') is not None,
          source=qm.SOURCES['wiki'], layer='assumption', status='matches_source')
    check('Torpedo nets are stowed as fitted in the target 1913 configuration',
          all('Torpedo_Net_{}_Stowed'.format(s) in objects for s in ('Port', 'Starboard')),
          source=qm.SOURCES['mq'], layer='assumption', status='as built, removed later in the war')
    check('Principal dimensions and displacement match the published figures',
          all(abs(a - b) < 0.05 for a, b in zip(
              (qm.SHIP['length_m'], qm.SHIP['beam_m'], qm.SHIP['draft_m']), (213.4, 27.2, 9.9))),
          source=qm.SOURCES['wiki'], layer='assumption', status='matches_source',
          evidence={'normal_t': qm.SHIP['displacement_normal_t'],
                    'deep_t': qm.SHIP['displacement_full_t'],
                    'speed_kn': qm.SHIP['speed_knots']})
    check('Director elevation limit 15 deg 21 min recorded for the 1913 fit',
          abs(qm.SHIP['max_elevation_director_deg'] - 15.35) < 0.02,
          source=qm.SOURCES['wiki'], layer='assumption', status='matches_source')
    check('No anti-aircraft armament in the 1913 configuration',
          not any('AA' in o.name.upper() or 'Anti_Aircraft' in o.name for o in objects),
          source=qm.SOURCES['wiki'], layer='assumption',
          status='matches_source: AA was fitted from October 1914')

    return CHECKS


if __name__ == '__main__':
    result = main()
    failing_blocking = [c for c in result if c['blocking'] and not c['passed']]
    failing_soft = [c for c in result if not c['blocking'] and not c['passed']]
    report = {
        'status': 'passed' if not failing_blocking else 'failed',
        'counts': {'total': len(result),
                   'geometry': sum(c['layer'] == 'geometry' for c in result),
                   'assumption': sum(c['layer'] == 'assumption' for c in result),
                   'failing_blocking': len(failing_blocking),
                   'failing_assumption': len(failing_soft)},
        'warnings': WARNINGS,
        'checks': result,
    }
    (OUT / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for entry in result:
        if not entry['passed']:
            print('FAIL [{}] {} {}'.format(entry['layer'], entry['check'],
                                           entry.get('evidence', '')))
    print('Queen Mary validation:', len(result), 'checks,',
          len(failing_blocking), 'blocking failures,',
          len(failing_soft), 'assumption gaps')
    if failing_blocking:
        raise AssertionError(failing_blocking)
