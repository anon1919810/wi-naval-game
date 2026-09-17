"""Verify a real FBX import into a clean Blender scene, including articulation.

The FBX is the shipped artefact, so this checks that everything the manifest
promises survives the round trip: semantic modules, the hierarchy, world bounds,
the turret pivot chain and the fact that decoration stayed merged.

run: blender --background --factory-startup --python verify_fbx.py
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
import queen_mary as qm  # noqa: E402  导出偏转角度的唯一来源

# manifest 记录的是 Blender 内部坐标（舰艏 +Y），而**出货的 FBX**在导出时被
# 绕竖直轴偏转了 EXPORT_YAW_DEG（为了让 Unity 的 forward 指向舰艏）。
# 所以拿 manifest 当期望值时必须先施加同一个偏转，否则这一整段会全体对不上。
FLIP = Matrix.Rotation(math.radians(qm.EXPORT_YAW_DEG), 4, 'Z')


def expected_origin(row):
    return FLIP @ Vector(row['origin_world_m'])


def expected_bounds(row):
    lo = Vector(row['bounds_world_m']['min'])
    hi = Vector(row['bounds_world_m']['max'])
    corners = [FLIP @ Vector((x, y, z))
               for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    return {'min': [min(c[i] for c in corners) for i in range(3)],
            'max': [max(c[i] for c in corners) for i in range(3)]}


expected = json.loads((OUT / 'object_manifest.json').read_text(encoding='utf-8'))
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.import_scene.fbx(filepath=str(OUT / 'HMS_Queen_Mary_1913_Refined_v3.fbx'))
bpy.context.view_layer.update()
checks = []


def check(name, condition, evidence=None):
    entry = {'check': name, 'passed': bool(condition)}
    if evidence is not None:
        entry['evidence'] = evidence
    checks.append(entry)


objects = bpy.data.objects
check('Every exported semantic object survives the FBX round trip',
      all(row['name'] in objects for row in expected['objects']),
      {'missing': [row['name'] for row in expected['objects'] if row['name'] not in objects]})
check('No preview cameras or lights exported',
      not any(o.type in ('CAMERA', 'LIGHT') for o in objects))
check('No extra objects in the FBX', len(objects) == expected['object_count'],
      {'imported': len(objects), 'manifest': expected['object_count']})
check('Parent-child hierarchy preserved', all(
      (objects[row['name']].parent.name if objects[row['name']].parent else None) == row['parent']
      for row in expected['objects']))

max_error = 0
for row in expected['objects']:
    obj = objects[row['name']]
    max_error = max(max_error, (obj.matrix_world.translation - expected_origin(row)).length)
    if obj.type == 'MESH':
        coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
        actual = {'min': [min(v[i] for v in coords) for i in range(3)],
                  'max': [max(v[i] for v in coords) for i in range(3)]}
        want = expected_bounds(row)
        max_error = max(max_error, max(abs(actual[k][i] - want[k][i])
                                       for k in ('min', 'max') for i in range(3)))
check('All world origins and mesh bounds preserved within 0.1 mm', max_error < .0001,
      {'max_error_m': max_error, 'export_yaw_deg': qm.EXPORT_YAW_DEG})
check('Hull remains 27.2 x 213.4 x 15 metres',
      all(abs(a - b) < .0001 for a, b in zip(objects['Hull'].dimensions, (27.2, 213.4, 15.0))),
      {'dimensions': [round(v, 6) for v in objects['Hull'].dimensions]})

# 有符号体积：法线朝外时为正值。它能抓住"导入后翻转"这类错误——
# 那种错误在尺寸检查里完全看不出来，但船会整艘里外翻过来渲染。
hull = objects['Hull']
hull_verts = [hull.matrix_world @ v.co for v in hull.data.vertices]
hull_volume = 0.0
for poly in hull.data.polygons:
    idx = list(poly.vertices)
    for i in range(1, len(idx) - 1):
        a, b, c = hull_verts[idx[0]], hull_verts[idx[i]], hull_verts[idx[i + 1]]
        hull_volume += a.dot(b.cross(c)) / 6.0
check('Hull volume is positive, so the normals still face outwards',
      hull_volume > 0, {'signed_volume_m3': round(hull_volume, 1)})

# 出货朝向：Blender 的 +Y 映射到 Unity 的 -Z，所以要让 Unity 里的舰艏朝向 +Z，
# FBX 里的舰艏就必须指向 -Y。这条是"Unity 里 forward 指向舰艏"的源头保证。
bow_dir = (objects['Barbette_A'].matrix_world.translation
           - objects['Barbette_X'].matrix_world.translation).normalized()
check('Shipped FBX faces the way Unity expects (bow maps to +Z)',
      bow_dir.y < -0.99,
      {'bow_direction_in_fbx': [round(v, 4) for v in bow_dir],
       'export_yaw_deg': qm.EXPORT_YAW_DEG,
       'note': 'Blender +Y maps to Unity -Z, so the bow has to point -Y in the file'})

modules = ['Turret_' + k for k in 'ABQX'] + ['Elevation_' + k for k in 'ABQX'] \
    + ['Barbette_' + k for k in 'ABQX'] \
    + ['Barrel_{}_{}'.format(k, s) for k in 'ABQX' for s in ('Port', 'Starboard')] \
    + ['Casemate_{}_{}'.format(s, i) for s in ('Port', 'Starboard') for i in range(1, 9)] \
    + ['Funnel_{}'.format(i) for i in (1, 2, 3)] \
    + ['Funnel_{}_Uptake'.format(i) for i in (1, 2, 3)] \
    + ['Mast_Fore', 'Mast_Main', 'Forecastle', 'Quarterdeck', 'Sternwalk',
       'Propeller_Shafts', 'Rudder', 'Rangefinder_CT', 'Steering_Gear', 'Damage_Modules',
       'Armour_Belt_229mm', 'Armour_Upper_Belt_152mm', 'Armour_Deck_64mm', 'Armour_Deck_25mm']
check('All {} combat and structure modules survive'.format(len(modules)),
      all(name in objects for name in modules),
      {'missing': [name for name in modules if name not in objects]})

loose = [o.name for o in objects if o.name.startswith(
    ('Net_Bundle_', 'Net_Boom_', 'Sternwalk_Rail_', 'Muzzle_', 'Casemate_Recess_'))]
check('Decoration is still merged after export', not loose, {'loose': loose})

for key in 'ABQX':
    turret = objects['Turret_' + key]
    pitch = objects['Elevation_' + key]
    gun = objects['Barrel_{}_Port'.format(key)]
    check('{}: pivot chain intact (turret -> elevation -> barrel)'.format(key),
          pitch.parent is turret and gun.parent is pitch)
    barrel_before = gun.matrix_world @ Vector((0, 10, 0))
    pivot_before = turret.matrix_world.translation.copy()
    rest_yaw = turret.rotation_euler.copy()
    rest_pitch = pitch.rotation_euler.copy()
    turret.rotation_euler.z += .5
    pitch.rotation_euler.x += .2
    bpy.context.view_layer.update()
    check('{}: FBX yaw and pitch move the barrel and preserve the turret origin'.format(key),
          ((gun.matrix_world @ Vector((0, 10, 0))) - barrel_before).length > 1
          and (turret.matrix_world.translation - pivot_before).length < .0001)
    turret.rotation_euler = rest_yaw
    pitch.rotation_euler = rest_pitch
    bpy.context.view_layer.update()

report = {'status': 'passed' if all(c['passed'] for c in checks) else 'failed',
          'max_position_or_bounds_error_m': max_error,
          'hull_signed_volume_m3': round(hull_volume, 1),
          'object_count': len(objects),
          'mesh_count': sum(o.type == 'MESH' for o in objects),
          'checks': checks}
(OUT / 'fbx_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
if report['status'] != 'passed':
    print('FAILED CHECKS:', [c for c in checks if not c['passed']])
    raise AssertionError(report)
print('FBX verification passed:', len(checks), 'checks')
