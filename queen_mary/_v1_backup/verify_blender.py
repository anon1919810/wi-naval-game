"""Run inside Blender after loading Queen Mary; writes persistent evidence."""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def verify_scene():
    checks = []

    def check(label, condition):
        checks.append({'check': label, 'passed': bool(condition)})

    objects = bpy.data.objects
    required = ['Queen_Mary', 'Hull', 'Superstructure', 'Bridge', 'Sternwalk',
                'Mast_Fore', 'Mast_Main', 'Rangefinder', 'Fire_Control',
                'Magazine_A', 'Engine_Room_1', 'Boiler_Room_1', 'Rudder']
    required += ['Turret_' + key for key in 'ABQX']
    required += ['Funnel_' + str(i) for i in range(1, 4)]
    required += [f'Casemate_{side}_{i}' for side in ('Port', 'Starboard')
                 for i in range(1, 9)]
    check('All required semantic names exist', all(n in objects for n in required))
    if not checks[-1]['passed']:
        return checks
    hull = objects['Hull']
    check('Hull dimensions: X=27.2 Y=213.4 Z=15.0 metres',
          all(abs(a-b) < 0.002 for a,b in zip(hull.dimensions, (27.2,213.4,15))))
    check('Metres and waterline root', bpy.context.scene.unit_settings.scale_length == 1
          and objects['Queen_Mary'].location.length < 1e-6)
    check('Hull keel -9.9 m; main deck +5.1 m',
          abs(min((hull.matrix_world @ v.co).z for v in hull.data.vertices)+9.9)<0.002
          and abs(max((hull.matrix_world @ v.co).z for v in hull.data.vertices)-5.1)<0.002)
    names = ['Turret_A','Turret_B','Mast_Fore','Funnel_1','Funnel_2',
             'Turret_Q','Funnel_3','Mast_Main','Turret_X']
    ys = [objects[n].matrix_world.translation.y for n in names]
    check('Fore-to-aft layout A B Foremast F1 F2 Q F3 Mainmast X',
          all(a>b for a,b in zip(ys,ys[1:])))
    check('B is superfiring above A', objects['Turret_B'].matrix_world.translation.z
          > objects['Turret_A'].matrix_world.translation.z + 2.5)
    check('F1/F2 closer than F2/F3', ys[3]-ys[4] < ys[4]-ys[6])
    dims = objects['Funnel_2'].dimensions
    check('Funnel 2 circular section', abs(dims.x-dims.y)<0.002)
    check('Funnels 1 and 3 elliptical', all(objects[f'Funnel_{i}'].dimensions.y >
          objects[f'Funnel_{i}'].dimensions.x*1.2 for i in (1,3)))
    for side,sign in [('Port',-1),('Starboard',1)]:
        casemates = [o for o in objects if o.get('component_role')=='secondary_gun'
                     and o.get('side')==side]
        check(f'{side}: exactly 8 secondary guns on correct side', len(casemates)==8
              and all(o.matrix_world.translation.x*sign > 0 for o in casemates))
    for name in ['Mast_Fore','Mast_Main']:
        check(f'{name}: three tripod legs', sum(o.name.startswith(name+'_Leg_')
              for o in objects)==3)
    check('Sternwalk is aft of X and inside full length envelope',
          objects['Sternwalk'].matrix_world.translation.y < ys[-1]
          and min((objects['Sternwalk'].matrix_world @ v.co).y
                  for v in objects['Sternwalk'].data.vertices) >= -106.701)
    for key in 'ABQX':
        turret = objects['Turret_'+key]
        pitch = objects['Elevation_'+key]
        barrel = objects[f'Barrel_{key}_Port']
        barbette = objects['Barbette_'+key]
        check(f'{key}: pitch and barrels inherit turret, barbette is fixed',
              pitch.parent==turret and barrel.parent==pitch and barbette.parent!=turret)
        check(f'{key}: front trunnion', abs(pitch.location.y-4.0)<0.001)
        original_yaw = turret.rotation_euler.copy()
        original_pitch = pitch.rotation_euler.copy()
        barbette_before = barbette.matrix_world.copy()
        pivot_before = turret.matrix_world.translation.copy()
        point_before = barrel.matrix_world @ Vector((0,6,0))
        turret.rotation_euler.z += math.radians(35)
        pitch.rotation_euler.x += math.radians(15)
        bpy.context.view_layer.update()
        point_after = barrel.matrix_world @ Vector((0,6,0))
        check(f'{key}: yaw/elevation move gun but preserve mount and barbette',
              (point_after-point_before).length > 1
              and (turret.matrix_world.translation-pivot_before).length < 1e-5
              and all(abs(barbette.matrix_world[r][c]-barbette_before[r][c])<1e-5
                      for r in range(4) for c in range(4)))
        turret.rotation_euler = original_yaw
        pitch.rotation_euler = original_pitch
        bpy.context.view_layer.update()
    meshes = [o for o in objects if o.type=='MESH' and o.get('export_asset')]
    check('All exported meshes have applied unit scale',
          all(all(abs(s-1)<1e-5 for s in o.scale) for o in meshes))
    check('No auto-generated .001 duplicate names',
          not any(o.name.endswith('.001') for o in objects))
    check('Stowed nets and support booms exist on both sides',
          all(f'Torpedo_Net_{side}_Stowed' in objects and
              any(o.name.startswith(f'Net_Boom_{side}_') for o in objects)
              for side in ('Port','Starboard')))
    targets = [objects[f'Funnel_{i}'] for i in range(1,4)]
    targets += [objects['Bridge'], objects['Bridge_Upper'],objects['Aft_Deckhouse']]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    collisions = []
    for key in 'ABQX':
        for side in ('Port','Starboard'):
            barrel = objects[f'Barrel_{key}_{side}']
            origin = barrel.matrix_world.translation
            end = barrel.matrix_world @ Vector((0,12.4,0))
            for target in targets:
                inv = target.matrix_world.inverted()
                local_start = inv @ origin
                delta = (inv @ end)-local_start
                tree = BVHTree.FromObject(target,depsgraph)
                hit = tree.ray_cast(local_start,delta.normalized(),delta.length)
                if hit[0] is not None:
                    collisions.append((barrel.name,target.name))
    check('Resting main-gun centre lines clear funnels and superstructures', not collisions)
    return checks


if __name__ == '__main__':
    out = Path(__file__).resolve().parent
    result = verify_scene()
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in result):
        raise AssertionError([c for c in result if not c['passed']])
    print('Queen Mary validation:', len(result), 'passed')
