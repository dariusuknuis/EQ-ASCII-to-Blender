import bpy, bmesh
import json
import numpy as np
import mathutils
from mathutils import Vector
from math import pi

EPSILON = 1e-1

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

# ─── CLEANUP ZONE MESH ───────────────────────────────────────────────────────────

def cleanup_bmesh(bm, 
                  deg_edge_dist=1e-6, 
                  coplanar_angle=1e-3, 
                  vert_colinear_tol=1e-6):
    """
    1) Dissolve any edge shorter than deg_edge_dist.
    2) Dissolve any edge between two faces whose normals differ by < coplanar_angle.
    3) Dissolve any vertex of valence==2 whose two incident edges are colinear 
       (i.e. it lies mid‑edge), within vert_colinear_tol.
    """

    # 1) dissolve truly tiny edges
    tiny_edges = [e for e in bm.edges
                  if (e.verts[0].co - e.verts[1].co).length < deg_edge_dist]
    if tiny_edges:
        bmesh.ops.dissolve_degenerate(bm,
                                      edges=tiny_edges,
                                      dist=deg_edge_dist)

    # 2) dissolve edges between nearly‑coplanar faces
    coplanar_edges = []
    for e in bm.edges:
        if len(e.link_faces) == 2:
            n1 = e.link_faces[0].normal
            n2 = e.link_faces[1].normal
            if n1.angle(n2) < coplanar_angle:
                coplanar_edges.append(e)
    if coplanar_edges:
        bmesh.ops.dissolve_edges(bm,
                                 edges=coplanar_edges,
                                 use_verts=False)

    bm.normal_update()

    # 3) dissolve any “mid‑edge” vertices (valence==2, perfectly colinear)
    mid_verts = []
    for v in bm.verts:
        # exactly two edges → candidate
        if len(v.link_edges) == 2:
            e0, e1 = v.link_edges
            # get direction vectors from v to the two other endpoints
            p0 = e0.other_vert(v).co - v.co
            p1 = e1.other_vert(v).co - v.co
            # if they’re colinear and opposite, dot ≈ -1
            if abs(p0.normalized().dot(p1.normalized()) + 1.0) < vert_colinear_tol:
                mid_verts.append(v)

    if mid_verts:
        bmesh.ops.dissolve_verts(bm,
                                 verts=mid_verts,
                                 use_face_split=False)

    bm.normal_update()

# ─── ZONE CREATION ───────────────────────────────────────────────────────────

def create_zone(zone):
    name     = zone['name']
    regions  = zone['region_list']
    userdata = zone.get('userdata', "")

    # 1) gather region empties named "R{index:06d}"
    empties = []
    for r in regions:
        nm = f"R{r+1:06d}"
        e  = bpy.data.objects.get(nm)
        if e and e.type=='EMPTY':
            empties.append(e)
        else:
            print(f"[create_zone] warning: empty '{nm}' not found")
    if not empties:
        print(f"[create_zone] no empties for {name!r}")
        return None

    # 2) compute AABB including each empty’s empty_display_size
    min_x = min(e.location.x - e.empty_display_size for e in empties)
    max_x = max(e.location.x + e.empty_display_size for e in empties)
    min_y = min(e.location.y - e.empty_display_size for e in empties)
    max_y = max(e.location.y + e.empty_display_size for e in empties)
    min_z = min(e.location.z - e.empty_display_size for e in empties)
    max_z = max(e.location.z + e.empty_display_size for e in empties)

    # center & full dims
    center = Vector((
        (min_x + max_x) * 0.5,
        (min_y + max_y) * 0.5,
        (min_z + max_z) * 0.5,
    ))
    dims = Vector((
        (max_x - min_x),
        (max_y - min_y),
        (max_z - min_z),
    ))

    # 3) build initial BMesh cube covering that box
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(    bm, vec=dims,   verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)

    # 4) collect splitting planes by BFS from each LeafMesh_* whose region_tag matches
    region_tags = { f"R{r+1:06d}" for r in regions }
    visited_ids = set()
    frontier    = []

    # seed with worldnode IDs from leaf meshes
    for o in bpy.data.objects:
        if o.type=='MESH' and o.data.name.startswith("LeafMesh_"):
            if o.get("region_tag") in region_tags:
                wid = o.get("worldnode")
                if wid is not None:
                    visited_ids.add(wid)
                    frontier.append(wid)

    # climb up to all BSPPlaneMesh parents
    planes = []
    while frontier:
        cur = frontier.pop(0)
        for o in bpy.data.objects:
            if o.type=='MESH' and o.data.name=="BSPPlaneMesh":
                ft, bt = o.get("front_tree"), o.get("back_tree")
                if ft==cur or bt==cur:
                    pid = o.get("worldnode")
                    if pid not in visited_ids:
                        visited_ids.add(pid)
                        frontier.append(pid)
                    n = Vector(o["normal"]).normalized()
                    d = -(float(o["d"]))
                    planes.append((n,d))

    # 5) dedupe planes by rounded (nx,ny,nz,d)
    uniq = []
    seen = set()
    for n,d in planes:
        key = (round(n.x,6), round(n.y,6), round(n.z,6), round(d,6))
        if key not in seen:
            seen.add(key)
            uniq.append((n,d))

    # precompute box corners
    corners   = [ Vector((x,y,z)) 
                  for x in (min_x,max_x)
                  for y in (min_y,max_y)
                  for z in (min_z,max_z) ]

    # --- 5b) filter out any plane that truly bisects one of the region meshes ---
    sprite_meshes = []
    for e in empties:
        sprite = e.get("SPRITE")
        o = bpy.data.objects.get(sprite)
        if o and o.type=='MESH':
            sprite_meshes.append(o)

    mesh_centers = []
    for o in sprite_meshes:
        # Blender gives you 8 box corners in object‑local space:
        bbox_corners = [o.matrix_world @ Vector(c) for c in o.bound_box]
        center = sum(bbox_corners, Vector()) / len(bbox_corners)
        mesh_centers.append(center)

    empty_pts = [e.matrix_world.to_translation() for e in empties]
    empty_pts.extend(mesh_centers)

    # cache world‐space coords
    mesh_verts = {
        o: [o.matrix_world @ v.co for v in o.data.vertices]
        for o in sprite_meshes
    }

    all_verts = []
    for verts in mesh_verts.values():
        all_verts.extend(verts)

    # parameters you can tweak:
    MESH_EPS       = 0.05    # how close to zero counts as “on the plane”
    MIN_SLICE_FRAC = 0.05    # must have at least 5% of verts on each side to reject

    empty_pts = [e.matrix_world.to_translation() for e in empties]
    empty_pts.extend(mesh_centers)
    empty_pts.extend(all_verts)

    good_planes = []
    for n, d in uniq:
        # (a) skip if it misses the zone-box
        ds = [c.dot(n) - d for c in corners]
        if max(ds) < -EPSILON or min(ds) > EPSILON:
            continue

        # (b) decide which side to keep
        es = [p.dot(n) - d for p in empty_pts]
        if   all(s >= -EPSILON for s in es):
            clear_outer, clear_inner = False, True
        elif all(s <=  EPSILON for s in es):
            clear_outer, clear_inner = True, False
        else:
            continue

        # (c) reject if it bisects the combined vertex cloud
        vals  = [n.dot(co) - d for co in all_verts]
        neg   = sum(1 for v in vals if v < -MESH_EPS)
        pos   = sum(1 for v in vals if v > +MESH_EPS)
        total = len(vals)
        if neg/total > MIN_SLICE_FRAC and pos/total > MIN_SLICE_FRAC:
            continue

        good_planes.append((n, d, clear_outer, clear_inner))

    # 2) Now do your bisects in one pass, using the precomputed flags
    geom_all = bm.faces[:] + bm.edges[:] + bm.verts[:]
    for n, d, clear_outer, clear_inner in good_planes:
        bmesh.ops.bisect_plane(
            bm,
            geom        = geom_all,
            plane_co    = n * d,
            plane_no    = n,
            clear_outer = clear_outer,
            clear_inner = clear_inner,
            use_snap_center=False,
        )

        boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
        if boundary_edges:
            bmesh.ops.holes_fill(bm, edges=boundary_edges)

        geom_all = bm.faces[:] + bm.edges[:] + bm.verts[:]
    
    # --- CLAMP ZONE VERTS TO ENCLOSE ALL SPRITE VERTICES  ---
    # 1) compute bmesh’s current AABB
    zone_min = Vector((
        min(v.co.x for v in bm.verts),
        min(v.co.y for v in bm.verts),
        min(v.co.z for v in bm.verts),
    ))
    zone_max = Vector((
        max(v.co.x for v in bm.verts),
        max(v.co.y for v in bm.verts),
        max(v.co.z for v in bm.verts),
    ))

    # 2) compute region‐cloud AABB
    region_min = Vector((
        min(co.x for co in all_verts),
        min(co.y for co in all_verts),
        min(co.z for co in all_verts),
    ))
    region_max = Vector((
        max(co.x for co in all_verts),
        max(co.y for co in all_verts),
        max(co.z for co in all_verts),
    ))

    # 3) decide new extents (never shrink)
    new_min = Vector((
        min(zone_min.x, region_min.x),
        min(zone_min.y, region_min.y),
        min(zone_min.z, region_min.z),
    ))
    new_max = Vector((
        max(zone_max.x, region_max.x),
        max(zone_max.y, region_max.y),
        max(zone_max.z, region_max.z),
    ))

    # 4) only move those verts that sit on the original box‐extents
    eps = 1e-3
    for v in bm.verts:
        # X axis
        if abs(v.co.x - zone_min.x) < eps:
            v.co.x = new_min.x
        elif abs(v.co.x - zone_max.x) < eps:
            v.co.x = new_max.x
        # Y axis
        if abs(v.co.y - zone_min.y) < eps:
            v.co.y = new_min.y
        elif abs(v.co.y - zone_max.y) < eps:
            v.co.y = new_max.y
        # Z axis
        if abs(v.co.z - zone_min.z) < eps:
            v.co.z = new_min.z
        elif abs(v.co.z - zone_max.z) < eps:
            v.co.z = new_max.z

    # 7) write mesh & link object
    cleanup_bmesh(bm)
    me  = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)

    # 5) custom props
    obj["REGIONLIST"] = json.dumps(regions)
    obj["USERDATA"]   = userdata

    # 6) pick zone material & overlays (unchanged)
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
    base_name, hexcol, alpha = mat_map.get(prefix, (None,None,None))
    if base_name:
        do_pvp = (len(name)>=3 and name[2]=="P") or (len(userdata)>=3 and userdata[2]=="P")
        do_tp  = (len(name)>=5 and name[3:5]=="TP") or (len(userdata)>=5 and userdata[3:5]=="TP")
        do_slp = "_S_" in name or "_S_" in userdata

        overlay_codes = []
        if do_pvp: overlay_codes.append("PVP")
        if do_tp:  overlay_codes.append("TP")
        if do_slp: overlay_codes.append("SLP")

        base_key = base_name[:-5]
        suffix   = "".join(f"_{c}" for c in overlay_codes)
        final_name = f"{base_key}{suffix}_ZONE"

        mat = bpy.data.materials.get(final_name)
        if not mat:
            if not overlay_codes:
                mat = bpy.data.materials.get(base_name) or bpy.data.materials.new(base_name)
                mat.use_nodes = True
            else:
                src = bpy.data.materials.get(base_name)
                mat = src.copy() if src else bpy.data.materials.new(base_name)
                mat.use_nodes = True
                mat.name = final_name
            mat.blend_method         = 'BLEND'
            mat.use_backface_culling = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                r = ((hexcol>>16)&0xFF)/255
                g = ((hexcol>>8 )&0xFF)/255
                b = ( hexcol     &0xFF)/255
                bsdf.inputs["Base Color"].default_value = (r,g,b,1)
                bsdf.inputs["Alpha"].default_value      = alpha

        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        bsdf_node = next((n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED"), None)
        if bsdf_node:
            overlays = []
            if do_pvp: overlays.append((ensure_pvp_node_group(),   "PVP"))
            if do_tp:  overlays.append((ensure_tp_node_group(),    "TP"))
            if do_slp: overlays.append((ensure_slippery_node_group(),"SLP"))
            apply_overlays(mat, bsdf_node, overlays)

    return obj
