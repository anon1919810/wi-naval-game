"""Validate Queen Mary v4 Blender assets and independent FBX round trips.

Run with Blender 4.x::

    blender --background --python verify_v4.py -- --asset-dir <directory>

The verifier opens files in memory and never saves or changes model assets.
It writes verification_v4_independent.json and exits nonzero on any failure.
FBX axis conventions are measured in Blender, not certified for Unity.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import traceback

import bpy
from mathutils import Vector


LAYERS = (
    '01_Exterior', '02_Interior_Visual', '03_Damage_Proxies',
    '04_Armour_Proxies', '05_Functional_Anchors',
)
MODULE_IDS = (
    'Magazine_A', 'Magazine_B', 'Magazine_Q', 'Magazine_X',
    *(f'Boiler_Room_{i}' for i in range(1, 8)),
    'Engine_Room_1', 'Engine_Room_2', 'Steering_Gear',
)
CHECKS = []
MEASUREMENTS = {}


def check(name, passed, evidence):
    CHECKS.append({'check': name, 'passed': bool(passed), 'evidence': evidence})
    print(f"{'PASS' if passed else 'FAIL'} {name}", flush=True)


def bounds(objects, evaluated=False):
    """Measure world-space bounds, including zero-origin equipment meshes."""
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    count = 0
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        if obj.type != 'MESH' or not obj.data.vertices:
            continue
        measured = obj.evaluated_get(depsgraph) if evaluated else obj
        for corner in measured.bound_box:
            point = measured.matrix_world @ Vector(corner)
            for axis in range(3):
                minimum[axis] = min(minimum[axis], point[axis])
                maximum[axis] = max(maximum[axis], point[axis])
            count += 1
    if not count:
        return None
    return {
        'min_m': minimum, 'max_m': maximum,
        'size_m': [maximum[i] - minimum[i] for i in range(3)],
    }


def parents(obj):
    chain = []
    while obj.parent:
        obj = obj.parent
        chain.append(obj.name)
    return chain


def validate_meshes(scope, meshes, materials=True):
    bad_geometry, bad_uv, bad_materials = [], [], []
    triangles = 0
    for obj in meshes:
        mesh = obj.data
        if (not mesh.vertices or not mesh.polygons
                or any(not math.isfinite(float(c)) for v in mesh.vertices for c in v.co)
                or any(not math.isfinite(float(c)) for row in obj.matrix_world for c in row)):
            bad_geometry.append(obj.name)
        triangles += sum(max(0, len(face.vertices) - 2) for face in mesh.polygons)
        uv = mesh.uv_layers.active
        if uv is None or len(uv.data) != len(mesh.loops):
            bad_uv.append({'object': obj.name, 'reason': 'missing UV or loop count mismatch'})
        else:
            invalid = sum(not all(math.isfinite(float(v)) for v in item.uv) for item in uv.data)
            collapsed = 0
            for face in mesh.polygons:
                if face.area <= 1e-9:
                    continue
                coords = [uv.data[index].uv for index in face.loop_indices]
                area = sum(a.x * b.y - b.x * a.y for a, b in zip(coords, coords[1:] + coords[:1]))
                if abs(area) <= 1e-12:
                    collapsed += 1
            if invalid or collapsed:
                bad_uv.append({'object': obj.name, 'nonfinite_loops': invalid,
                               'nonzero_geometry_faces_with_collapsed_uv': collapsed})
        if materials and (not mesh.materials or any(mat is None for mat in mesh.materials)
                          or any(face.material_index >= len(mesh.materials) for face in mesh.polygons)):
            bad_materials.append(obj.name)
    check(scope + '.finite_nonempty_meshes', not bad_geometry, bad_geometry)
    check(scope + '.valid_uvs', not bad_uv, bad_uv)
    if materials:
        check(scope + '.material_assignments', not bad_materials, bad_materials)
    MEASUREMENTS[scope] = {'mesh_count': len(meshes), 'triangles_base_mesh': triangles,
                           'bounds_blender_world': bounds(meshes, evaluated=True)}


def validate_guns(scope):
    problems = []
    names = bpy.data.objects
    for key in 'ABQX':
        turret_name = 'Turret_' + key
        turret = names.get(turret_name)
        if turret is None or turret.get('component_role') != 'main_turret':
            problems.append(turret_name + ': absent or incorrect role')
        for side in ('Port', 'Starboard'):
            barrel = names.get(f'Barrel_{key}_{side}')
            muzzle = names.get(f'Muzzle_{key}_{side}')
            expected_chain = [f'Barrel_{key}_{side}', f'Elevation_{key}', turret_name, 'Queen_Mary']
            if muzzle is None or barrel is None:
                problems.append(f'{key}/{side}: missing muzzle or barrel')
                continue
            if parents(muzzle) != expected_chain:
                problems.append({'muzzle': muzzle.name, 'chain': parents(muzzle)})
            if muzzle.get('component_role') != 'muzzle':
                problems.append(muzzle.name + ': missing muzzle role')
            # Custom data define a point in barrel mesh coordinates. Comparing
            # world positions also works after the FBX coordinate conversion.
            end = float(barrel.get('barrel_end_local_y_m', 12.4))
            expected = barrel.matrix_world @ Vector((0, end, 0))
            error = (muzzle.matrix_world.translation - expected).length
            if error > .005:
                problems.append({'muzzle': muzzle.name, 'tip_error_m': error})
    turrets = [o.name for o in names if o.get('component_role') == 'main_turret']
    muzzles = [o.name for o in names if o.get('component_role') == 'muzzle']
    check(scope + '.four_turrets_eight_muzzles', len(turrets) == 4 and len(muzzles) == 8,
          {'turrets': turrets, 'muzzles': muzzles})
    check(scope + '.muzzle_parent_chains_and_tips', not problems, problems)


def validate_interior(scope, require_proxies):
    problems = []
    modules = [o for o in bpy.data.objects if o.get('component_role') == 'interior_module']
    equipment = [o for o in bpy.data.objects if o.get('component_role') == 'interior_equipment']
    check(scope + '.fourteen_modules_and_equipment', len(modules) == len(equipment) == 14,
          {'modules': [o.name for o in modules], 'equipment': [o.name for o in equipment]})
    for module_id in MODULE_IDS:
        group = bpy.data.objects.get('Interior_' + module_id)
        obj = bpy.data.objects.get('Equipment_' + module_id)
        if group is None or obj is None:
            problems.append(module_id + ': missing module visual')
            continue
        if group.get('module_id') != module_id or obj.get('module_id') != module_id:
            problems.append(module_id + ': identity mismatch')
        if obj.parent != group or 'Interior_Visual' not in parents(group):
            problems.append(module_id + ': incorrect interior parentage')
        if not obj.get('not_collision_geometry'):
            problems.append(module_id + ': missing visual-only flag')
        if require_proxies:
            proxy = bpy.data.objects.get(module_id)
            if proxy is None or proxy.get('asset_layer') != '03_Damage_Proxies':
                problems.append(module_id + ': missing separate damage proxy')
            elif proxy == obj or proxy.parent == group:
                problems.append(module_id + ': functional and visible meshes not separated')
    check(scope + '.interior_identity_and_layer_links', not problems, problems)


def validate_images():
    missing, unassigned = [], []
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image is None:
                unassigned.append(material.name + '/' + node.name)
    for image in bpy.data.images:
        if image.type in ('RENDER_RESULT', 'COMPOSITING'):
            continue
        packed = bool(image.packed_file) or bool(image.packed_files)
        source_exists = bool(image.filepath) and Path(bpy.path.abspath(image.filepath)).is_file()
        if min(image.size) <= 0 or (image.source == 'FILE' and not (packed or source_exists)):
            missing.append({'image': image.name, 'size': list(image.size),
                            'packed': packed, 'source_exists': source_exists})
    check('full.texture_nodes_assigned', not unassigned, unassigned)
    check('full.images_available', not missing, missing)


def inspect_full(asset_dir):
    bpy.ops.wm.open_mainfile(filepath=str(asset_dir / 'QueenMary_v4_Full.blend'))
    bpy.context.view_layer.update()
    objects = [o for o in bpy.data.objects if o.get('export_asset')]
    meshes = [o for o in objects if o.type == 'MESH']
    check('full.metre_units', abs(bpy.context.scene.unit_settings.scale_length - 1) < 1e-8,
          bpy.context.scene.unit_settings.scale_length)
    hull = bpy.data.objects.get('Hull')
    measured = bounds([hull]) if hull else None
    check('full.hull_length_beam_draft', measured is not None
          and abs(measured['size_m'][0] - 27.2) < .02
          and abs(measured['size_m'][1] - 213.4) < .02
          and abs(measured['min_m'][2] + 9.9) < .02, measured)
    root = bpy.data.objects.get('Queen_Mary')
    check('full.draft_metadata', root is not None and abs(float(root.get('draft_m', 0)) - 9.9) < .001,
          root.get('draft_m') if root else None)
    duplicates = [o.name for o in bpy.data.objects if re.search(r'\.\d{3}$', o.name)]
    check('full.no_accidental_numbered_objects', not duplicates, duplicates)
    bad_layers = []
    for obj in objects:
        layer = obj.get('asset_layer')
        member = [c.name for c in obj.users_collection if c.name in LAYERS]
        if layer not in LAYERS or member != [layer]:
            bad_layers.append({'object': obj.name, 'tag': layer, 'collections': member})
    check('full.collections_match_layer_tags', not bad_layers, bad_layers)
    hidden = [o for o in objects if o.get('asset_layer') in LAYERS[1:4]]
    wrongly_visible = [o.name for o in hidden if not o.hide_render or not o.hide_get()]
    check('full.interior_and_proxies_hidden', not wrongly_visible, wrongly_visible)
    exterior = [o for o in meshes if o.get('asset_layer') == LAYERS[0]]
    interior = [o for o in meshes if o.get('asset_layer') == LAYERS[1]]
    check('full.exterior_mesh_budget', 0 < len(exterior) <= 65,
          {'all_exterior_meshes': len(exterior), 'render_enabled': sum(not o.hide_render for o in exterior)})
    check('full.interior_fifteen_meshes', len(interior) == 15, len(interior))
    validate_meshes('full', meshes)
    validate_guns('full')
    validate_interior('full', True)
    validate_images()
    reference = {}
    for label, selected in [('exterior', exterior), ('interior', interior)]:
        reference[label] = {
            obj.name: {'component_id': obj.get('component_id'),
                       'component_role': obj.get('component_role'),
                       'module_id': obj.get('module_id'),
                       'bounds': bounds([obj], evaluated=True)} for obj in selected
        }
    return reference


def inspect_fbx(asset_dir, label, reference):
    # A new empty file for each import prevents Blender name collisions from
    # masking identities and prevents one export from supplying missing nodes.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = asset_dir / f'QueenMary_v4_{label.title()}.fbx'
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_props=True)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    actual = {o.name for o in meshes}
    expected = set(reference)
    scope = 'fbx_' + label
    check(scope + '.mesh_names_and_count', actual == expected,
          {'mesh_count': len(meshes), 'expected_count': len(expected),
           'missing': sorted(expected - actual), 'unexpected': sorted(actual - expected)})
    bad_ids, bad_bounds, leaked = [], [], []
    for obj in meshes:
        if obj.name not in reference:
            continue
        source = reference[obj.name]
        for prop in ('component_id', 'component_role', 'module_id'):
            if obj.get(prop) != source[prop]:
                bad_ids.append({'object': obj.name, 'property': prop,
                                'expected': source[prop], 'actual': obj.get(prop)})
        measured = bounds([obj], evaluated=True)
        # Export includes a rest-heading rotation; compare extents, not heading.
        original_sizes = sorted(source['bounds']['size_m'])
        imported_sizes = sorted(measured['size_m']) if measured else []
        if not measured or any(abs(a - b) > max(.03, abs(a) * .002)
                               for a, b in zip(original_sizes, imported_sizes)):
            bad_bounds.append({'object': obj.name, 'source': source['bounds'], 'imported': measured})
        if obj.get('asset_layer') in LAYERS[2:4]:
            leaked.append(obj.name)
    check(scope + '.module_identity_preserved', not bad_ids, bad_ids)
    check(scope + '.metre_scale_dimensions_preserved', not bad_bounds, bad_bounds)
    check(scope + '.no_damage_or_armour_proxy_meshes', not leaked, leaked)
    validate_meshes(scope, meshes)
    if label == 'exterior':
        validate_guns(scope)
    else:
        validate_interior(scope, False)


def inspect_cutaway(asset_dir):
    bpy.ops.wm.open_mainfile(filepath=str(asset_dir / 'QueenMary_v4_Cutaway.blend'))
    bpy.context.view_layer.update()
    hull = bpy.data.objects.get('Hull')
    measured = bounds([hull]) if hull else None
    check('cutaway.half_hull', measured is not None
          and measured['max_m'][0] <= .02 and measured['min_m'][0] < -13.5, measured)
    equipment = [o for o in bpy.data.objects if o.get('component_role') == 'interior_equipment']
    check('cutaway.interior_equipment_visible', len(equipment) == 14
          and all(not o.hide_render and not o.hide_get() for o in equipment),
          {'count': len(equipment), 'hidden': [o.name for o in equipment if o.hide_render or o.hide_get()]})
    proxy_visible = [o.name for o in bpy.data.objects
                     if o.get('asset_layer') in LAYERS[2:4] and not o.hide_render]
    check('cutaway.functional_proxies_hidden', not proxy_visible, proxy_visible)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    asset_dir = args.asset_dir.resolve()
    report = {'started_utc': datetime.now(timezone.utc).isoformat(),
              'asset_dir': str(asset_dir), 'blender': bpy.app.version_string,
              'historically_certified': False, 'unity_runtime_tested': False,
              'notes': ['Bounds use Blender world coordinates; Unity orientation is not asserted.',
                        'The duplicate-object check detects naming pollution, not a second regeneration.'],
              'files': {}, 'checks': CHECKS, 'measurements': MEASUREMENTS}
    files = ['QueenMary_v4_Full.blend', 'QueenMary_v4_Cutaway.blend',
             'QueenMary_v4_Exterior.fbx', 'QueenMary_v4_Interior.fbx']
    try:
        for name in files:
            path = asset_dir / name
            exists = path.is_file() and path.stat().st_size > 1024
            check('file.' + name, exists, {'exists': path.is_file(), 'bytes': path.stat().st_size if path.is_file() else 0})
            if exists:
                report['files'][name] = {
                    'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                }
        if all(c['passed'] for c in CHECKS):
            reference = inspect_full(asset_dir)
            inspect_fbx(asset_dir, 'exterior', reference['exterior'])
            inspect_fbx(asset_dir, 'interior', reference['interior'])
            inspect_cutaway(asset_dir)
    except Exception:
        report['exception'] = traceback.format_exc()
        check('verifier.completed_without_exception', False, report['exception'])
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    report['status'] = 'passed' if CHECKS and all(c['passed'] for c in CHECKS) else 'failed'
    report['passed_checks'] = sum(c['passed'] for c in CHECKS)
    report['total_checks'] = len(CHECKS)
    output = asset_dir / 'verification_v4_independent.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': report['total_checks'],
                      'report': str(output)}, ensure_ascii=False), flush=True)
    if report['status'] != 'passed':
        # Blender can swallow Python exceptions without --python-exit-code.
        # All evidence has been flushed; no model files were saved or changed.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


if __name__ == '__main__':
    main()
