"""Verify a real FBX import into a clean Blender scene, including articulation."""
import json
from pathlib import Path
import bpy
from mathutils import Vector

out = Path(__file__).resolve().parent
expected = json.loads((out/'object_manifest.json').read_text(encoding='utf-8'))
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.import_scene.fbx(filepath=str(out/'HMS_Queen_Mary_1913_Greybox.fbx'))
bpy.context.view_layer.update()
checks = []

def check(name, condition):
    checks.append({'check':name,'passed':bool(condition)})

objects = bpy.data.objects
check('Every exported semantic object survives FBX round trip',
      all(row['name'] in objects for row in expected['objects']))
check('No preview cameras or lights exported', not any(o.type in ('CAMERA','LIGHT') for o in objects))
check('No extra objects in FBX',len(objects)==expected['object_count'])
check('Parent-child hierarchy preserved',all(
      (objects[row['name']].parent.name if objects[row['name']].parent else None)==row['parent']
      for row in expected['objects']))
max_error = 0
for row in expected['objects']:
    obj = objects[row['name']]
    max_error = max(max_error,(obj.matrix_world.translation-Vector(row['origin_world_m'])).length)
    if obj.type=='MESH':
        coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
        actual = {'min':[min(v[i] for v in coords) for i in range(3)],
                  'max':[max(v[i] for v in coords) for i in range(3)]}
        max_error = max(max_error,max(abs(actual[k][i]-row['bounds_world_m'][k][i])
                                      for k in ('min','max') for i in range(3)))
check('All world origins and mesh bounds preserved within 0.1 mm',max_error<.0001)
check('Hull remains 27.2 x 213.4 x 15 metres',
      all(abs(a-b)<.0001 for a,b in zip(objects['Hull'].dimensions,(27.2,213.4,15))))
for key in 'ABQX':
    gun = objects[f'Barrel_{key}_Port']
    barrel_before = gun.matrix_world @ Vector((0,10,0))
    pivot_before = objects['Turret_'+key].matrix_world.translation.copy()
    objects['Turret_'+key].rotation_euler.z += .5
    objects['Elevation_'+key].rotation_euler.x += .2
    bpy.context.view_layer.update()
    check(f'{key}: FBX yaw/pitch hierarchy moves barrel and preserves turret origin',
          ((gun.matrix_world @ Vector((0,10,0)))-barrel_before).length > 1 and
          (objects['Turret_'+key].matrix_world.translation-pivot_before).length<.0001)
report = {'status':'passed' if all(c['passed'] for c in checks) else 'failed',
          'max_position_or_bounds_error_m':max_error,'checks':checks}
(out/'fbx_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if report['status']!='passed':
    raise AssertionError(report)
