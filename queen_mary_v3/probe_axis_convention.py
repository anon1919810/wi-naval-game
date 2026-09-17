"""Probe the Blender -> Unity axis mapping with deliberately asymmetric markers.

Why this exists: the hull is bilaterally symmetric, so no check on the ship itself
can tell you which side is starboard after an engine import. Reasoning about the
export flags is not good enough either - the measured result (bow at -Z in Unity)
contradicted what the flag names suggest. So we drop in markers that are *not*
symmetric, export them with the exact same settings as the ship, and let Unity
report where each one landed.

run: blender --background --python probe_axis_convention.py -- --out <dir>
     <dir> must be inside the Unity project, e.g.
     D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval/Assets/_AxisProbe

The matching reader is unity_integration/Assets/Editor/AxisProbe.cs.
"""

import json
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent

# name -> Blender position (x right/starboard, y bow, z up)
MARKERS = {
    'MARK_BOW': (0.0, 90.0, 5.0),
    'MARK_STERN': (0.0, -90.0, 5.0),
    'MARK_STARBOARD': (12.0, 40.0, 5.0),
    'MARK_PORT': (-12.0, 40.0, 5.0),
    'MARK_TOP': (0.0, 40.0, 14.0),
}


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = Path(args[args.index('--out') + 1]) if '--out' in args else HERE / '_axis_probe'
    blend = HERE / 'HMS_Queen_Mary_1913_Greybox.blend'
    out.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=str(blend))
    bpy.ops.object.select_all(action='DESELECT')

    for name, (x, y, z) in MARKERS.items():
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, z))
        marker = bpy.context.object
        marker.name = name
        marker.data.name = name

    bpy.ops.object.select_all(action='DESELECT')
    for name in MARKERS:
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects['MARK_BOW']

    # 与 export_fbx() 用完全相同的轴向参数，否则测出来的映射不是这条管道的映射。
    bpy.ops.export_scene.fbx(filepath=str(out / 'AxisProbeModel.fbx'),
        use_selection=True, object_types={'MESH'}, global_scale=1.0,
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='Z', axis_up='Y', use_space_transform=True,
        bake_space_transform=False, use_mesh_modifiers=True, mesh_smooth_type='FACE',
        add_leaf_bones=False, bake_anim=False, path_mode='AUTO', use_custom_props=True)

    (HERE / '_axis_probe_blender.json').write_text(
        json.dumps(MARKERS, indent=2), encoding='utf-8')
    print('Axis probe exported to', out / 'AxisProbeModel.fbx')
    print('Blender frame:', json.dumps(MARKERS))


if __name__ == '__main__':
    main()
