"""Diagnostic: are the internal modules actually hidden inside the hull shell?

For each internal module, cast a ray from just outside the module toward the
port and starboard sides and report which object the ray hits first.
If the Hull is hit first, the module is hidden from a side view.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
import queen_mary as qm  # noqa: E402

qm.load_offsets()
depsgraph = bpy.context.evaluated_depsgraph_get()
objects = bpy.data.objects

internal_roles = ('magazine', 'boiler_room', 'engine_room', 'steering_gear',
                  'armour_belt', 'armour_deck', 'armour_bulkhead')
report = []
for obj in sorted(objects, key=lambda o: o.name):
    if obj.type != 'MESH' or obj.get('component_role') not in internal_roles:
        continue
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    centre = sum(coords, Vector()) / len(coords)
    line = [obj.name, obj.get('component_role'),
            [round(v, 2) for v in centre]]
    for label, direction in (('stbd', Vector((1, 0, 0))), ('port', Vector((-1, 0, 0)))):
        start = centre.copy()
        hit_name = None
        origin = start
        for _ in range(6):
            hit = bpy.context.scene.ray_cast(depsgraph, origin, direction)
            if not hit[0]:
                break
            if hit[4] is not obj:
                hit_name = hit[4].name
                break
            origin = hit[1] + direction * 0.002
        line.append('{}:{}'.format(label, hit_name))
    report.append(line)

lines = []
for row in report:
    lines.append('{:<32} {:<16} centre={:<22} {} | {}'.format(
        row[0], row[1], str(row[2]), row[3], row[4]))

hull = objects['Hull']
coords = [hull.matrix_world @ v.co for v in hull.data.vertices]
lines.append('hull verts {}  halfbeam_at(33,-7)={}'.format(
    len(coords), round(qm.halfbeam_at(33.0, -7.0), 3)))
(OUT / '_diag_report.txt').write_text('\n'.join(lines), encoding='utf-8')
print('\n'.join(lines))
