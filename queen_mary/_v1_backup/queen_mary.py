"""Generate the user-specified HMS Queen Mary greybox in Blender 3.x/4.x.

Run: blender --background --python queen_mary.py -- --out OUTPUT_DIRECTORY
Or open this text in Blender's Text Editor and Run Script (clears the scene).
No third-party Python packages, textures, downloads, or external model files.
All lengths are metres. +Y bow, +X starboard, +Z up, Z=0 waterline.
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


SHIP = {
    'ship_id': 'HMS_Queen_Mary_1913', 'length_m': 213.4, 'beam_m': 27.2,
    'draft_m': 9.9, 'main_deck_z_m': 5.1, 'forecastle_z_m': 7.5,
    'displacement_normal_t': 27200, 'displacement_full_t': 32158,
    'speed_knots': 28.0, 'main_gun_calibre_mm': 343,
    'secondary_gun_calibre_mm': 102, 'configuration': 'user_spec_greybox_v1',
    'historically_certified': False,
}
# Longitudinal position, half beam, fraction of maximum depth. Estimated hull form.
STATIONS = [
    (-106.7,.08,.15), (-102,2.8,.3), (-94,6.0,.6), (-82,9.0,.85),
    (-65,11.6,1), (-40,13.0,1), (-18,13.6,1), (15,13.6,1),
    (40,12.9,1), (60,11.4,1), (78,8.1,.9), (92,4.4,.7),
    (101,1.75,.35), (106.7,.02,.05),
]
# y, fixed deck height, rotating turret base z, initial yaw degrees.
TURRETS = {'A': (60,7.5,8.5,0), 'B': (46,11.0,12.0,0),
           'Q': (-6,7.5,8.5,180), 'X': (-68,5.1,6.3,180)}
# y, transverse radius, longitudinal radius, base z, height.
FUNNELS = {1:(23,2.45,3.8,9.2,12.8), 2:(7.0,3.5,3.5,9.0,13.0),
           3:(-27,2.45,3.8,7.6,14.4)}
CASEMATE_YS = [54,48,42,36,30,24,18,12]
MAIN_MAST_TRIPOD = True  # Explicit user requirement; not historical certification.
ASSET_COLLECTION = None
PREVIEW_COLLECTION = None
MATERIALS = {}


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


def make_materials():
    for name,grey in [('HullGrey',.34), ('DeckGrey',.47), ('StructureGrey',.56),
                      ('DarkGrey',.20), ('Black',.065), ('UnderwaterGrey',.245)]:
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = (grey,grey,grey,1)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (grey,grey,grey,1)
        bsdf.inputs['Roughness'].default_value = .85
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


def empty(name, position=(0,0,0), parent=None, role='group'):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = 1.5
    return configure_object(obj,name,position,parent,role)


def box(name, position, size, parent, material='StructureGrey', role='structure'):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    # Mesh-space dimensions leave the object at scale (1,1,1).
    obj.data.transform(Matrix.Diagonal(Vector((*size,1))))
    return configure_object(obj,name,position,parent,role,material)


def cylinder(name, position, radius, depth, parent, material='StructureGrey',
             role='structure', ellipse=(1,1), vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth)
    obj = bpy.context.object
    obj.data.transform(Matrix.Diagonal(Vector((ellipse[0],ellipse[1],1,1))))
    return configure_object(obj,name,position,parent,role,material)


def rod(name, start, end, radius, parent, material='DarkGrey', role='structure', vertices=10):
    delta = Vector(end)-Vector(start)
    obj = cylinder(name,start,radius,delta.length,parent,material,role,vertices=vertices)
    rotation = delta.to_track_quat('Z','Y').to_matrix().to_4x4()
    # Origin at the first endpoint, geometry extends toward the second endpoint.
    obj.data.transform(rotation @ Matrix.Translation((0,0,delta.length/2)))
    return obj


def mesh_object(name, vertices, faces, parent, material, role, position=(0,0,0)):
    mesh = bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return configure_object(bpy.data.objects.new(name,mesh),name,position,parent,role,material)


def prism(name, outline, z0, z1, parent, material, role, position=(0,0,0)):
    n = len(outline)
    vertices = [(x,y,z) for z in (z0,z1) for x,y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh_object(name,vertices,faces,parent,material,role,position)


def half_beam(y):
    for (ya,wa,_),(yb,wb,_) in zip(STATIONS,STATIONS[1:]):
        if ya <= y <= yb:
            return wa+(wb-wa)*(y-ya)/(yb-ya)
    raise ValueError('Position is outside hull stations: '+str(y))


def make_hull(root):
    verts = []
    for y,w,depth in STATIONS:
        keel = -SHIP['draft_m']*depth
        verts.extend([(x,y,z) for x,z in [(-w,5.1),(-w*.985,0),
            (-w*.93,keel*.55),(-w*.60,keel),(w*.60,keel),
            (w*.93,keel*.55),(w*.985,0),(w,5.1)]])
    faces = []
    for i in range(len(STATIONS)-1):
        for j in range(8):
            faces.append((i*8+j,i*8+(j+1)%8,(i+1)*8+(j+1)%8,(i+1)*8+j))
    faces += [tuple(reversed(range(8))),tuple(range(len(verts)-8,len(verts)))]
    hull = mesh_object('Hull',verts,faces,root,'HullGrey','hull')
    hull['dimensions_status'] = 'specified_overall_dimensions_estimated_sections'
    hull.data.materials.append(MATERIALS['UnderwaterGrey'])
    hull.data.materials.append(MATERIALS['DeckGrey'])
    for face in hull.data.polygons:
        z = sum(hull.data.vertices[i].co.z for i in face.vertices)/len(face.vertices)
        face.material_index = 1 if z<0 else 2 if z>5 else 0
    forecastle = [(y,w) for y,w,_ in STATIONS if y>=-18]
    outline = [(w,y) for y,w in forecastle]+[(-w,y) for y,w in reversed(forecastle)]
    prism('Forecastle',outline,5.1,7.5,root,'DeckGrey','deck')
    return hull


def make_superstructure(root):
    sup = empty('Superstructure',parent=root)
    box('B_Superfiring_Deckhouse',(0,46,9.25),(11.8,14,3.5),sup)
    bridge = box('Bridge',(0,32,10.6),(12.4,12,6.2),sup,role='bridge')
    box('Bridge_Upper',(0,31,15.1),(8.6,7,2.8),bridge.parent)
    box('Bridge_Wings',(0,31.5,14.0),(17.0,5.0,.55),sup,'DeckGrey')
    box('Bridge_Visor',(0,31,16.6),(10.2,8,.35),sup,'DarkGrey')
    cylinder('Conning_Tower',(0,37,13.4),3.0,5.0,sup,'DarkGrey','conning_tower')
    box('Funnel_1_Uptake',(0,23,8.35),(8.8,9.5,1.7),sup,'HullGrey')
    box('Funnel_2_Uptake',(0,7,8.25),(9.8,10,1.5),sup,'HullGrey')
    box('Aft_Deckhouse',(0,-41,7.1),(12.4,23,4.0),sup)
    box('Funnel_3_Uptake',(0,-27,6.35),(8.8,9.4,2.5),sup,'HullGrey')
    box('Aft_Platform',(0,-42,9.25),(15,24,.35),sup,'DeckGrey')
    return sup


def make_turret(key, spec, root):
    y,deck,base,yaw = spec
    barbette = cylinder('Barbette_'+key,(0,y,(deck+base)/2),4.9,base-deck,
                        root,'DarkGrey','barbette',vertices=32)
    barbette['module_id'] = 'Magazine_'+key
    outline = [(-4.5,-4.3),(4.5,-4.3),(4.9,-2.8),(4.9,2.8),
               (3.6,4.8),(-3.6,4.8),(-4.9,2.8),(-4.9,-2.8)]
    turret = prism('Turret_'+key,outline,0,3.1,root,'StructureGrey','main_turret',
                   position=(0,y,base))
    turret.rotation_euler.z = math.radians(yaw)
    turret['yaw_axis_local'] = '+Z'
    turret['rest_forward_local'] = '+Y'
    turret['calibre_mm'] = 343
    turret['barrels'] = 2
    turret['mount_base_z_m'] = base
    pitch = empty('Elevation_'+key,(0,4.0,1.5),turret,'gun_elevation')
    pitch['pitch_axis_local'] = '+X'
    pitch['positive_rotation'] = 'raises barrels'
    for side,x in [('Port',-1.25),('Starboard',1.25)]:
        barrel = rod(f'Barrel_{key}_{side}',(x,0,0),(x,12.4,0),.34,pitch,
                     'DarkGrey','main_gun_barrel',vertices=16)
        barrel['calibre_mm'] = 343
        barrel['external_radius_m'] = .34
        # Origin is the individual barrel trunnion, not its mesh midpoint.
        rod(f'Gun_Sleeve_{key}_{side}',(x,-.15,0),(x,2.6,0),.49,pitch,
            'HullGrey',vertices=16)
        rod(f'Muzzle_{key}_{side}',(x,12.401,0),(x,12.421,0),.1715,pitch,
            'Black','muzzle',vertices=16)


def make_casemates(root):
    for side,sign in [('Port',-1),('Starboard',1)]:
        for i,y in enumerate(CASEMATE_YS,1):
            width = half_beam(y)
            box(f'Casemate_Recess_{side}_{i}',(sign*(width+.035),y,6.3),
                (.12,2.45,1.2),root,'Black','casemate_recess_proxy')
            gun = rod(f'Casemate_{side}_{i}',(sign*(width-.3),y,6.3),
                      (sign*(width+2.45),y,6.3),.14,root,'DarkGrey','secondary_gun',12)
            gun['side'] = side
            gun['calibre_mm'] = 102
            gun['layout_status'] = 'user_spec_8_per_side_schematic'


def make_funnels(root):
    for i,(y,rx,ry,z,h) in FUNNELS.items():
        funnel = cylinder(f'Funnel_{i}',(0,y,z+h/2),1,h,root,'HullGrey','funnel',
                          ellipse=(rx,ry),vertices=32)
        funnel['section'] = 'circular' if i==2 else 'elliptical'
        cylinder(f'Funnel_{i}_Cap',(0,0,h/2-.5),1,1.0,funnel,'Black',
                 ellipse=(rx*1.04,ry*1.04),vertices=32)


def make_mast(name,y,base,height,root,spread):
    mast = empty(name,(0,y,base),root,'tripod_mast')
    mast['historical_status'] = 'two_tripods_requested; exact period rig not certified'
    meeting = (0,0,height*.68)
    for i,start in enumerate([(0,spread,0),(-spread,-spread*.65,0),
                              (spread,-spread*.65,0)],1):
        rod(name+f'_Leg_{i}',start,meeting,.30 if name=='Mast_Fore' else .22,
            mast,'DarkGrey','mast_leg',12)
    rod(name+'_Topmast',meeting,(0,0,height),.16,mast,'DarkGrey',vertices=10)
    cylinder(name+'_Top',(0,0,height*.68),2.1 if name=='Mast_Fore' else 1.35,
             .75,mast,'StructureGrey','mast_platform',vertices=12)
    for i,fraction in enumerate((.76,.9),1):
        width = 5 if name=='Mast_Fore' else 3.4
        rod(name+f'_Yard_{i}',(-width,0,height*fraction),(width,0,height*fraction),
            .085,mast,'DarkGrey','yard',8)
    return mast


def make_sternwalk(root):
    # U-shaped platform wraps the stern rather than extending the ship's length.
    outer = [(-5.9,-98.0),(-4.4,-103.2),(-2.0,-106.7),(2.0,-106.7),
             (4.4,-103.2),(5.9,-98.0)]
    inner = [(-4.4,-98.0),(-2.8,-102.0),(-.65,-105.1),(.65,-105.1),
             (2.8,-102.0),(4.4,-98.0)]
    outline = outer + list(reversed(inner))
    center = Vector((0,-102,2.55))
    local_outline = [(x,y-center.y) for x,y in outline]
    walk = prism('Sternwalk',local_outline,-.18,.18,root,'DeckGrey','sternwalk',tuple(center))
    for i,((x1,y1),(x2,y2)) in enumerate(zip(outer,outer[1:]),1):
        rod(f'Sternwalk_Rail_{i}',(x1,y1-center.y,1.18),(x2,y2-center.y,1.18),
            .065,walk,'DarkGrey','sternwalk_rail',8)
    for i,(x,y) in enumerate(outer,1):
        rod(f'Sternwalk_Post_{i}',(x,y-center.y,.18),(x,y-center.y,1.18),
            .065,walk,'DarkGrey','sternwalk_rail',8)


def make_nets(root):
    for side,sign in [('Port',-1),('Starboard',1)]:
        group = empty(f'Torpedo_Net_{side}_Stowed',parent=root,role='stowed_net')
        segments = [-80,-65,-40,-18,15,40,60,76]
        for i,(ya,yb) in enumerate(zip(segments,segments[1:]),1):
            rod(f'Net_Bundle_{side}_{i}',(sign*(half_beam(ya)+.32),ya,4.4),
                (sign*(half_beam(yb)+.32),yb,4.4),.24,group,'DarkGrey','net_bundle',8)
        for i,y in enumerate(range(-76,73,12),1):
            rod(f'Net_Boom_{side}_{i}',(sign*(half_beam(y)+.38),y,1.7),
                (sign*(half_beam(y+5)+.43),y+5,4.7),.13,group,
                'DarkGrey','stowed_net_boom',8)


def make_modules(root, sup):
    modules = empty('Damage_Module_Anchors',parent=root,role='module_group')
    for key,(y,_,_,_) in TURRETS.items():
        obj = empty('Magazine_'+key,(0,y,-4.5),modules,'magazine_anchor')
        obj['placeholder_only'] = True
        obj['volume_defined'] = False
    for name,pos in [('Engine_Room_1',(0,-43,-4)),('Boiler_Room_1',(0,16,-4)),
                     ('Rudder',(0,-98,-5)),('Fire_Control',(0,32,17.5))]:
        obj = empty(name,pos,modules,'future_module_anchor')
        obj['placeholder_only'] = True
        obj['volume_defined'] = False
    rf = rod('Rangefinder',(-3.1,32,17.1),(3.1,32,17.1),.26,sup,
             'DarkGrey','rangefinder_proxy',12)
    rf['placeholder_only'] = True


def build_ship():
    reset_scene()
    make_materials()
    root = empty('Queen_Mary',role='ship_root')
    for key,value in SHIP.items():
        root[key] = value
    make_hull(root)
    sup = make_superstructure(root)
    for key,spec in TURRETS.items():
        make_turret(key,spec,root)
    make_casemates(root)
    make_funnels(root)
    make_mast('Mast_Fore',32,16.8,24,root,2.5)
    make_mast('Mast_Main',-38,9.45,23,root,2.3)
    make_sternwalk(root)
    make_nets(root)
    make_modules(root,sup)
    bpy.context.view_layer.update()
    return root


def asset_manifest():
    rows = []
    for obj in sorted(ASSET_COLLECTION.objects,key=lambda ob:ob.name):
        row = {'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,
               'role':obj.get('component_role'),
               'location_local_m':[round(v,6) for v in obj.location],
               'origin_world_m':[round(v,6) for v in obj.matrix_world.translation],
               'dimensions_local_axes_m':[round(v,6) for v in obj.dimensions],
               'scale':[round(v,6) for v in obj.scale],
               'rotation_local_deg':[round(math.degrees(v),6) for v in obj.rotation_euler]}
        if obj.type=='MESH':
            coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
            row['bounds_world_m'] = {'min':[round(min(v[i] for v in coords),6) for i in range(3)],
                                     'max':[round(max(v[i] for v in coords),6) for i in range(3)]}
            row['vertices'] = len(obj.data.vertices)
            row['triangles'] = sum(len(p.vertices)-2 for p in obj.data.polygons)
        rows.append(row)
    return rows


def geometry_signature():
    data = []
    for obj in sorted(ASSET_COLLECTION.objects,key=lambda o:o.name):
        entry = [obj.name,obj.parent.name if obj.parent else None,
                 [round(v,6) for row in obj.matrix_local for v in row]]
        if obj.type=='MESH':
            entry += [[[round(c,6) for c in v.co] for v in obj.data.vertices],
                      [list(p.vertices) for p in obj.data.polygons]]
        data.append(entry)
    return hashlib.sha256(json.dumps(data,separators=(',',':')).encode()).hexdigest()


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
    scene.world.color = (.055,.055,.055)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast' if bpy.app.version<(4,0,0) else 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.display.render_aa = '32'
    cameras = [
        ('Overview',(210,170,145),(0,0,6),245,(1800,1100)),
        ('Starboard',(350,0,10),(0,0,10),235,(1800,560)),
        ('Top',(0,0,350),(0,0,0),235,(1800,430)),
        ('Bow',(0,350,13),(0,0,13),65,(900,900)),
        ('Stern_Detail',(55,-143,44),(0,-84,4),76,(1200,850)),
    ]
    for name,position,target,scale,resolution in cameras:
        data = bpy.data.cameras.new('Camera_'+name)
        cam = bpy.data.objects.new('Camera_'+name,data)
        PREVIEW_COLLECTION.objects.link(cam)
        cam.location = position
        cam.rotation_euler = (Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
        if name=='Top':
            cam.rotation_euler = (0,0,math.pi/2)
        data.type = 'ORTHO'
        data.ortho_scale = scale
        data.clip_end = 2000
        cam['render_width'] = resolution[0]
        cam['render_height'] = resolution[1]
        cam['preview_only'] = True
    scene.camera = bpy.data.objects['Camera_Overview']
    scene.render.resolution_x,scene.render.resolution_y = 1800,1100
    scene.render.resolution_percentage = 100
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.clip_end = 3000
                area.spaces.active.region_3d.view_distance = 260
                area.spaces.active.region_3d.view_location = (0,0,5)
                area.spaces.active.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
                area.spaces.active.shading.color_type = 'MATERIAL'


def export_fbx(out):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in ASSET_COLLECTION.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects['Hull']
    bpy.ops.export_scene.fbx(filepath=str(out/'HMS_Queen_Mary_1913_Greybox.fbx'),
        use_selection=True,object_types={'MESH','EMPTY'},global_scale=1.0,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Z',axis_up='Y',use_space_transform=True,
        bake_space_transform=False,use_mesh_modifiers=True,mesh_smooth_type='FACE',
        add_leaf_bones=False,bake_anim=False,path_mode='AUTO',use_custom_props=True)


def main():
    script_path = Path(globals().get('__file__','queen_mary.py')).resolve()
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=script_path.parent)
    parser.add_argument('--skip-render',action='store_true')
    parser.add_argument('--check-repeat',action='store_true')
    config = parser.parse_args(args)
    out = config.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    (out/'build_started.json').write_text(json.dumps({'started_utc':stamp}),encoding='utf-8')
    try:
        build_ship()
        signature = geometry_signature()
        repeat = None
        if config.check_repeat:
            build_ship()
            repeat = geometry_signature()==signature
            if not repeat:
                raise AssertionError('Re-running in the same scene changed geometry or names')
        preview_setup()
        if script_path.is_file():
            text = bpy.data.texts.get('queen_mary.py') or bpy.data.texts.new('queen_mary.py')
            text.clear()
            text.write(script_path.read_text(encoding='utf-8'))
            text.filepath = str(script_path)
        rows = asset_manifest()
        manifest = {'ship':SHIP,'blender':bpy.app.version_string,'started_utc':stamp,
                    'geometry_sha256':signature,'repeat_generation_passed':repeat,
                    'object_count':len(rows),'mesh_count':sum(r['type']=='MESH' for r in rows),
                    'triangles':sum(r.get('triangles',0) for r in rows),'objects':rows,
                    'estimation_notes':['Hull sections and component dimensions are schematic.',
                        'Two tripods and all 16 forecastle casemates follow the user specification.',
                        '1916-labelled reference used for arrangement only.',
                        'Internal anchors have no volume, armour or damage simulation.']}
        (out/'object_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        with (out/'objects.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['Name','Type','Parent','Role','X_m','Y_m','Z_m','DX_m','DY_m','DZ_m'])
            for row in rows:
                writer.writerow([row['name'],row['type'],row['parent'],row['role'],
                                 *row['origin_world_m'],*row['dimensions_local_axes_m']])
        lines = [f"{r['name']:<34} {r['type']:<6} dimensions(m)={r['dimensions_local_axes_m']}"
                 for r in rows]
        for obj in PREVIEW_COLLECTION.objects:
            lines.append(f'{obj.name:<34} {obj.type:<6} dimensions(m)={list(obj.dimensions)}')
        for line in lines:
            print(line)
        (out/'created_objects.txt').write_text('\n'.join(lines),encoding='utf-8')
        export_fbx(out)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects['Hull'].select_set(True)
        bpy.context.view_layer.objects.active = bpy.data.objects['Hull']
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'HMS_Queen_Mary_1913_Greybox.blend'))
        if not config.skip_render:
            for camera in list(PREVIEW_COLLECTION.objects):
                bpy.context.scene.camera = camera
                bpy.context.scene.render.resolution_x = camera['render_width']
                bpy.context.scene.render.resolution_y = camera['render_height']
                bpy.context.scene.render.filepath = str(out/(camera.name[7:]+'.png'))
                bpy.ops.render.render(write_still=True)
            bpy.context.scene.camera = bpy.data.objects['Camera_Overview']
            bpy.context.scene.render.resolution_x = 1800
            bpy.context.scene.render.resolution_y = 1100
            bpy.ops.wm.save_as_mainfile(filepath=str(out/'HMS_Queen_Mary_1913_Greybox.blend'))
        report = {'status':'complete','started_utc':stamp,
                  'completed_utc':datetime.now(timezone.utc).isoformat(),
                  'blender':bpy.app.version_string,'geometry_sha256':signature,
                  'repeat_generation_passed':repeat}
        (out/'build_result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    except Exception:
        (out/'build_result.json').write_text(json.dumps({'status':'failed',
            'started_utc':stamp,'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
        raise


if __name__=='__main__':
    main()
