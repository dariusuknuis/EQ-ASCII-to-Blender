import bpy
import json
import numpy as np
import mathutils

EPSILON = 1e-6

# ─── OVERLAY NODE‑GROUP BUILDERS ────────────────────────────────────────────

def ensure_pvp_node_group():
    name = "PVP_ZONE"
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    ng, nodes, links = bpy.data.node_groups.new(name, 'ShaderNodeTree'), None, None
    ng = bpy.data.node_groups[name]
    nodes, links = ng.nodes, ng.links

    # Group I/O
    inp = nodes.new('NodeGroupInput');  inp.location=(-700,225)
    out = nodes.new('NodeGroupOutput'); out.location=( 800,330)
    ng.inputs .new('NodeSocketShader',"Shader")
    ng.outputs.new('NodeSocketShader',"Shader")

    # Wave→Ramp→Mix #1
    w1 = nodes.new('ShaderNodeTexWave');     w1.location=(-335,590)
    w1.wave_type='BANDS'; w1.bands_direction='DIAGONAL'; w1.wave_profile='SIN'
    for k,v in (("Scale",5.0),("Distortion",12.0),("Detail",2.0),
                ("Detail Scale",1.0),("Detail Roughness",0.75)):
        w1.inputs[k].default_value = v

    r1 = nodes.new('ShaderNodeValToRGB');  r1.location=(-125,440)
    r1.color_ramp.interpolation = 'CONSTANT'
    r1.color_ramp.elements[0].position = 0.0
    r1.color_ramp.elements[0].color    = (1,1,1,1)
    r1.color_ramp.elements[1].position = 0.2
    r1.color_ramp.elements[1].color    = (0,0,0,1)

    m1 = nodes.new('ShaderNodeMixShader');  m1.location=(270,300)

    # Wave→Ramp→Mix #2
    w2 = nodes.new('ShaderNodeTexWave');     w2.location=(-35,800)
    w2.wave_type='BANDS'; w2.bands_direction='DIAGONAL'; w2.wave_profile='SIN'
    for attr in ("Scale","Distortion","Detail","Detail Scale","Detail Roughness"):
        w2.inputs[attr].default_value = w1.inputs[attr].default_value

    r2 = nodes.new('ShaderNodeValToRGB');  r2.location=(210,550)
    r2.color_ramp.interpolation = 'CONSTANT'
    r2.color_ramp.elements[0].position = 0.0
    r2.color_ramp.elements[0].color    = (1,1,1,1)
    r2.color_ramp.elements[1].position = 0.1
    r2.color_ramp.elements[1].color    = (0,0,0,1)

    m2 = nodes.new('ShaderNodeMixShader');  m2.location=(520,355)

    # Two colored Principled BSDFs
    p1 = nodes.new('ShaderNodeBsdfPrincipled'); p1.location=(-125,110)
    p1.inputs["Base Color"].default_value = (0x26/255,0x07/255,0x51/255,1)
    p1.inputs["Alpha"].default_value      = 1.0

    p2 = nodes.new('ShaderNodeBsdfPrincipled'); p2.location=(200,110)
    p2.inputs["Base Color"].default_value = (0x6D/255,0x03/255,0x0F/255,1)
    p2.inputs["Alpha"].default_value      = 1.0

    # internal links
    links.new(w1.outputs["Fac"], r1.inputs["Fac"])
    links.new(r1.outputs["Color"], m1.inputs["Fac"])

    links.new(w2.outputs["Fac"], r2.inputs["Fac"])
    links.new(r2.outputs["Color"], m2.inputs["Fac"])

    links.new(inp.outputs["Shader"], m1.inputs[1])
    links.new(p1.outputs["BSDF"],   m1.inputs[2])

    links.new(m1.outputs["Shader"], m2.inputs[1])
    links.new(p2.outputs["BSDF"],   m2.inputs[2])

    links.new(m2.outputs["Shader"], out.inputs["Shader"])
    return ng

def ensure_tp_node_group():
    name = "TELEPORT_ZONE"
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    nodes, links = ng.nodes, ng.links

    # Group I/O
    inp = nodes.new('NodeGroupInput');  inp.location=(-700,225)
    out = nodes.new('NodeGroupOutput'); out.location=( 800,330)
    ng.inputs .new('NodeSocketShader',"Shader")
    ng.outputs.new('NodeSocketShader',"Shader")

    # Voronoi→Ramp→Mix #1
    v1 = nodes.new('ShaderNodeTexVoronoi')
    v1.location = (-335,590)
    # remove v1.dimension
    v1.feature = 'DISTANCE_TO_EDGE'
    v1.inputs["Scale"].default_value      = 3.0
    v1.inputs["Randomness"].default_value = 0.75

    r1 = nodes.new('ShaderNodeValToRGB');  r1.location = (-125,440)
    r1.color_ramp.interpolation = 'CONSTANT'
    r1.color_ramp.elements[0].position = 0.0
    r1.color_ramp.elements[0].color    = (1,1,1,1)
    r1.color_ramp.elements[1].position   = 0.03
    r1.color_ramp.elements[1].color    = (0,0,0,1)

    m1 = nodes.new('ShaderNodeMixShader');  m1.location = (270,300)

    # Voronoi→Ramp→Mix #2
    v2 = nodes.new('ShaderNodeTexVoronoi')
    v2.location = (-35,800)
    v2.feature = 'DISTANCE_TO_EDGE'
    v2.inputs["Scale"].default_value      = 3.0
    v2.inputs["Randomness"].default_value = 0.75

    r2 = nodes.new('ShaderNodeValToRGB');  r2.location = (210,550)
    r2.color_ramp.interpolation = 'LINEAR'
    r2.color_ramp.elements[0].position = 0.0
    r2.color_ramp.elements[0].color    = (1,1,1,1)
    r2.color_ramp.elements[1].position   = 0.03
    r2.color_ramp.elements[1].color    = (0,0,0,1)

    m2 = nodes.new('ShaderNodeMixShader');  m2.location = (520,355)

    # colored BSDFs
    p1 = nodes.new('ShaderNodeBsdfPrincipled'); p1.location=(-125,110)
    p1.inputs["Base Color"].default_value=(0xBD/255,0xCB/255,0xCE/255,1); p1.inputs["Alpha"].default_value=1
    p2 = nodes.new('ShaderNodeBsdfPrincipled'); p2.location=(200,110)
    p2.inputs["Base Color"].default_value=(0x83/255,0x94/255,0x8F/255,1); p2.inputs["Alpha"].default_value=1

    # links
    links.new(v1.outputs["Distance"], r1.inputs["Fac"])
    links.new(r1.outputs["Color"],   m1.inputs["Fac"])

    links.new(v2.outputs["Distance"],r2.inputs["Fac"])
    links.new(r2.outputs["Color"],   m2.inputs["Fac"])

    links.new(inp.outputs["Shader"], m1.inputs[1])
    links.new(p1.outputs["BSDF"],    m1.inputs[2])
    
    links.new(m1.outputs["Shader"], m2.inputs[1])
    links.new(p2.outputs["BSDF"],    m2.inputs[2])

    links.new(m2.outputs["Shader"], out.inputs["Shader"])
    return ng

def ensure_slippery_node_group():
    name = "SLIPPERY_ZONE"
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    ng, nodes, links = bpy.data.node_groups.new(name,'ShaderNodeTree'),None,None
    ng = bpy.data.node_groups[name]; nodes, links = ng.nodes, ng.links

    # Group I/O
    inp = nodes.new('NodeGroupInput');  inp.location=(-700,225)
    out = nodes.new('NodeGroupOutput'); out.location=( 800,330)
    ng.inputs .new('NodeSocketShader',"Shader")
    ng.outputs.new('NodeSocketShader',"Shader")

    # Noise→Ramp→Mix #1
    n1 = nodes.new('ShaderNodeTexNoise'); n1.location=(-335,590)
    n1.inputs["Scale"].default_value      = 12.0
    n1.inputs["Detail"].default_value     = 2.0
    n1.inputs["Roughness"].default_value  = 0.5
    n1.inputs["Distortion"].default_value = 1.4

    r1 = nodes.new('ShaderNodeValToRGB');  r1.location=(-125,440)
    r1.color_ramp.interpolation = 'CONSTANT'
    r1.color_ramp.elements[0].position = 0.0
    r1.color_ramp.elements[0].color    = (1,1,1,1)
    r1.color_ramp.elements[1].position = 0.45
    r1.color_ramp.elements[1].color    = (0,0,0,1)

    m1 = nodes.new('ShaderNodeMixShader');  m1.location=(270,300)

    # Noise→Ramp→Mix #2
    n2 = nodes.new('ShaderNodeTexNoise'); n2.location=(-35,800)
    for attr in ("Scale","Detail","Roughness","Distortion"):
        n2.inputs[attr].default_value = n1.inputs[attr].default_value

    r2 = nodes.new('ShaderNodeValToRGB');  r2.location=(210,550)
    r2.color_ramp.interpolation = 'LINEAR'
    r2.color_ramp.elements[0].position = 0.0
    r2.color_ramp.elements[0].color    = (1,1,1,1)
    r2.color_ramp.elements[1].position = 0.45
    r2.color_ramp.elements[1].color    = (0,0,0,1)

    m2 = nodes.new('ShaderNodeMixShader');  m2.location=(520,355)

    # colored BSDFs
    p1 = nodes.new('ShaderNodeBsdfPrincipled'); p1.location=(-125,110)
    p1.inputs["Base Color"].default_value=(0x64/255,0x76/255,0x94/255,1); p1.inputs["Alpha"].default_value=1
    p2 = nodes.new('ShaderNodeBsdfPrincipled'); p2.location=(200,110)
    p2.inputs["Base Color"].default_value=(0xA4/255,0xC1/255,0xD0/255,1); p2.inputs["Alpha"].default_value=1

    # links
    links.new(n1.outputs["Fac"],    r1.inputs["Fac"])
    links.new(r1.outputs["Color"],  m1.inputs["Fac"])

    links.new(n2.outputs["Fac"],    r2.inputs["Fac"])
    links.new(r2.outputs["Color"],  m2.inputs["Fac"])

    links.new(inp.outputs["Shader"],m1.inputs[1])
    links.new(p1.outputs["BSDF"],   m1.inputs[2])

    links.new(m1.outputs["Shader"],m2.inputs[1])
    links.new(p2.outputs["BSDF"],   m2.inputs[2])

    links.new(m2.outputs["Shader"], out.inputs["Shader"])
    return ng

# ─── CHAINED OVERLAY UTILITY ────────────────────────────────────────────────

def apply_overlays(mat, base_bsdf, overlays):
    """overlays: list of (node_group, label) in order they should apply."""
    tree = mat.node_tree
    out  = tree.nodes.get("Material Output")

    # remove existing BSDF → output links
    for link in list(out.inputs['Surface'].links):
        tree.links.remove(link)

    # create a group‑node for each overlay and connect base_bsdf → each
    grp_nodes = []
    for i,(ng,name) in enumerate(overlays):
        g = tree.nodes.new('ShaderNodeGroup')
        g.node_tree = ng
        # stagger them horizontally
        g.location = base_bsdf.location + mathutils.Vector((300*(i+1), 0))
        tree.links.new(base_bsdf.outputs['BSDF'], g.inputs['Shader'])
        grp_nodes.append((g,name))

    # chain them via MixShader
    if not grp_nodes:
        # no overlays at all: direct BSDF→output
        tree.links.new(base_bsdf.outputs['BSDF'], out.inputs['Surface'])
        return

    # if only one overlay: its output → surface
    if len(grp_nodes)==1:
        tree.links.new(grp_nodes[0][0].outputs['Shader'], out.inputs['Surface'])
    else:
        prev_out = None
        # mix pairwise
        for idx,(g,name) in enumerate(grp_nodes):
            if idx==0:
                prev_out = g.outputs['Shader']
                continue
            mix = tree.nodes.new('ShaderNodeMixShader')
            mix.location = base_bsdf.location + mathutils.Vector((300*idx, -200))
            mix.inputs['Fac'].default_value = 0.5
            # mix prev_out with this group's output
            tree.links.new(prev_out, mix.inputs[1])
            tree.links.new(g.outputs['Shader'], mix.inputs[2])
            prev_out = mix.outputs['Shader']
        tree.links.new(prev_out, out.inputs['Surface'])

# ─── ZONE CREATION ───────────────────────────────────────────────────────────

def create_zone(zone):
    name     = zone['name']
    regions  = zone['region_list']
    userdata = zone.get('userdata', "")

    # 1) gather meshes named R<idx+1>_DMSPRITEDEF
    mesh_objs = []
    for r in regions:
        nm = f"R{r+1}_DMSPRITEDEF"
        o  = bpy.data.objects.get(nm)
        if o and o.type=='MESH':
            mesh_objs.append(o)
        else:
            print(f"[create_zone] warning: '{nm}' not found")

    if not mesh_objs:
        print(f"[create_zone] no meshes for {name}")
        return None

    # 2) collect verts
    verts = []
    for o in mesh_objs:
        M = o.matrix_world
        for v in o.data.vertices:
            co = M @ v.co
            verts.append((co.x,co.y,co.z))
    verts   = np.array(verts)
    aabb_min= verts.min(axis=0)
    aabb_max= verts.max(axis=0)
    dims    = aabb_max - aabb_min
    center  = (aabb_min + aabb_max)/2.0
    center_xy = center[:2]

    # 3) candidates…
    cands = []
    # cube
    vol = dims.prod()
    cands.append({'type':'cube','dims':dims,'min':aabb_min,'max':aabb_max,'volume':vol})
    # sphere
    d = np.linalg.norm(verts - center,axis=1).max()
    cands.append({'type':'sphere','center':center,'radius':d,'volume':4/3*np.pi*d**3})
    # cylinder
    h = dims[2]
    r_ = max(np.linalg.norm(v[:2]-center_xy) for v in verts)
    cands.append({'type':'cylinder','radius':r_,'height':h,
                  'z_min':aabb_min[2],'z_max':aabb_max[2],
                  'center_xy':center_xy,'volume':np.pi*r_**2*h})
    # cone
    h2 = max(h, EPSILON)
    rr = 0.0
    for v in verts:
        dz = aabb_max[2]-v[2]
        if dz< EPSILON: continue
        rr = max(rr, np.linalg.norm(v[:2]-center_xy)*h2/dz)
    cands.append({'type':'cone','base_radius':rr,'height':h2,
                  'apex_z':aabb_max[2],'base_z':aabb_min[2],
                  'center_xy':center_xy,'volume':1/3*np.pi*rr**2*h2})

    # 4) filter + pick
    valid = []
    for c in cands:
        ok = True
        t = c['type']
        if t=='sphere':
            ok = all(np.linalg.norm(v-c['center']) <= c['radius']+EPSILON for v in verts)
        elif t=='cylinder':
            ok = all(c['z_min']-EPSILON <= v[2] <= c['z_max']+EPSILON and
                     np.linalg.norm(v[:2]-c['center_xy']) <= c['radius']+EPSILON
                     for v in verts)
        elif t=='cone':
            ok = all(c['base_z']-EPSILON <= v[2] <= c['apex_z']+EPSILON and
                     np.linalg.norm(v[:2]-c['center_xy']) <=
                     c['base_radius']*((c['apex_z']-v[2])/c['height'])+EPSILON
                     for v in verts)
        if ok or t=='cube':
            valid.append(c)

    best = min(valid, key=lambda x: x['volume'])

    # 5) add primitive
    if best['type']=='cube':
        bpy.ops.mesh.primitive_cube_add(size=2, location=center.tolist())
        obj = bpy.context.active_object
        obj.scale = best['dims']/2.0

    elif best['type']=='sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=best['center'].tolist())
        obj = bpy.context.active_object
        obj.scale = (best['radius'],)*3

    elif best['type']=='cylinder':
        cx,cy = best['center_xy']
        zc = (best['z_min']+best['z_max'])/2.0
        bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=(cx,cy,zc))
        obj = bpy.context.active_object
        obj.scale = (best['radius'],best['radius'],best['height']/2.0)

    else:  # cone
        cx,cy = best['center_xy']
        h    = best['height']
        zc   = best['base_z']+h/2.0
        bpy.ops.mesh.primitive_cone_add(radius1=best['base_radius'],
                                        radius2=0, depth=h,
                                        location=(cx,cy,zc))
        obj = bpy.context.active_object

    obj.name = name

    # 6) custom props
    obj["REGIONLIST"] = json.dumps(regions)
    obj["USERDATA"]   = userdata

    # 7) pick zone material
    prefix = name[:2]
    if prefix not in {"DR","WT","LA","SL","VW","W2","W3"}:
        prefix = userdata[:2]

    mat_map = {
      "DR":("DRY_ZONE",     0xFFFFFF,0.00),
      "WT":("WATER_ZONE",   0x0F2417,0.75),
      "LA":("LAVA_ZONE",    0x570101,0.75),
      "SL":("SLIME_ZONE",   0x2A2A01,0.75),
      "VW":("V_WATER_ZONE", 0x01012D,0.75),
      "W2":("WATER2_ZONE",  0x1E2026,0.75),
      "W3":("WATER3_ZONE",  0xFFFFFF,0.10),
    }
    mat_name, hexcol, alpha = mat_map.get(prefix, (None,None,None))
    if mat_name:
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes    = True
            mat.blend_method = 'BLEND'
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            r = ((hexcol>>16)&0xFF)/255
            g = ((hexcol>>8)&0xFF)/255
            b = ( hexcol    &0xFF)/255
            bsdf.inputs["Base Color"].default_value = (r,g,b,1)
            bsdf.inputs["Alpha"].default_value      = alpha
            mat.use_backface_culling = True

        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        bsdf_node = None
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                bsdf_node = n
                break
        if not bsdf_node:
            print(f"[create_zone] no Principled BSDF in material {mat.name}")
        else:
            # 2) detect which overlays apply
            name3  = (len(name)  >= 3 and name[2]  == 'P') or (len(userdata)>=3 and userdata[2]=='P')
            name45 = (len(name)  >= 5 and name[3:5]=='TP') or (len(userdata)>=5 and userdata[3:5]=='TP')
            s_flag = "_S_" in name or "_S_" in userdata

            overlays = []
            if name3:
                overlays.append((ensure_pvp_node_group(),     "PVP"))
            if name45:
                overlays.append((ensure_tp_node_group(),      "TP"))
            if s_flag:
                overlays.append((ensure_slippery_node_group(),"SLP"))

            # 3) apply them
            apply_overlays(mat, bsdf_node, overlays)

            # 4) rename the material
            base   = mat.name.rsplit("_ZONE", 1)[0]
            suffix = "".join(f"_{lbl}" for (_,lbl) in overlays)
            mat.name = f"{base}{suffix}_ZONE"

    return obj
