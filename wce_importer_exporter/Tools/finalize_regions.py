import bpy, bmesh
from mathutils import Vector, kdtree
from mathutils.kdtree import KDTree

def split_edges_to_snap_verts(objs, threshold=1e-4):
    """For each pair A,B in objs, split edges of B wherever a vert of A projects onto it."""
    # build per-object list of world-space vert coords
    world_verts = {}
    for ob in objs:
        wm = ob.matrix_world
        world_verts[ob] = [wm @ v.co for v in ob.data.vertices]

    for ob_B in objs:
        me = ob_B.data
        bm = bmesh.new(); bm.from_mesh(me)
        invB = ob_B.matrix_world.inverted()
        # for each other object A
        for ob_A, ws_verts in world_verts.items():
            if ob_A is ob_B: continue
            # test every edge
            for edge in list(bm.edges):
                v1_ws = ob_B.matrix_world @ edge.verts[0].co
                v2_ws = ob_B.matrix_world @ edge.verts[1].co
                seg = v2_ws - v1_ws
                seg_len2 = seg.length_squared
                if seg_len2 == 0.0:
                    continue
                for p_ws in ws_verts:
                    t = (p_ws - v1_ws).dot(seg) / seg_len2
                    if 0.0 < t < 1.0:
                        proj = v1_ws + seg * t
                        if (proj - p_ws).length <= threshold:
                            bmesh.ops.subdivide_edges(
                                bm,
                                edges=[edge],
                                cuts=1,
                                edge_percents={edge: t}
                            )
                            break
        bm.to_mesh(me)
        bm.free()
    #print("✅ split_edges_to_snap_verts done.")

def merge_by_distance(objs, dist=0.001):
    """On each mesh in objs, merge any vertices within dist by entering Edit Mode."""
    for ob in objs:
        # make this object active
        bpy.context.view_layer.objects.active = ob
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        # run Blender's built-in Remove Doubles (Merge by Distance)
        bpy.ops.mesh.remove_doubles(threshold=dist)
        bpy.ops.object.mode_set(mode='OBJECT')
        #print(f"[merge_by_distance] {ob.name}: ran remove_doubles(threshold={dist})")
    #print(f"✅ merge_by_distance ({dist}) done.")

def triangulate_meshes(objs):
    """Convert every face of every mesh in objs into triangles."""
    for ob in objs:
        me = ob.data
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
    #print("✅ triangulate_meshes done.")

def collapse_vertices_across_objects(objs, threshold=0.05):
    """
    Cluster all world-space verts across objs within threshold,
    snap each cluster to its centroid, then round that centroid
    to the grid implied by each obj.FPSCALE.
    """
    # gather world-space coords + mapping
    coords, mapping = [], []
    for ob in objs:
        wm = ob.matrix_world
        fscale = ob.get("FPSCALE", 0)
        factor = 2 ** fscale
        for vi, v in enumerate(ob.data.vertices):
            coords.append(wm @ v.co)
            mapping.append((ob, vi, factor))
    N = len(coords)
    if N == 0:
        print("⚠️ no vertices to collapse.")
        return

    # build KD-tree
    kd = KDTree(N)
    for i, co in enumerate(coords):
        kd.insert(co, i)
    kd.balance()

    visited = set()
    for i, co in enumerate(coords):
        if i in visited:
            continue
        # find cluster
        neighbors = [idx for (_, idx, _) in kd.find_range(co, threshold)]
        visited.update(neighbors)
        centroid = Vector((0,0,0))
        for j in neighbors:
            centroid += coords[j]
        centroid /= len(neighbors)
        # write back + grid-round
        for j in neighbors:
            ob, vi, factor = mapping[j]
            local = ob.matrix_world.inverted() @ centroid
            if factor != 0:
                local.x = round(local.x * factor) / factor
                local.y = round(local.y * factor) / factor
                local.z = round(local.z * factor) / factor
            ob.data.vertices[vi].co = local

    # update meshes
    for ob in objs:
        ob.data.update()

    #print(f"✅ collapse_vertices_across_objects (th={threshold}) done.")

def finalize_regions(
        edge_snap_threshold=0.001,
        merge_dist=0.001,
        collapse_thresh=0.05):
    # pick up all of your region meshes by naming convention
    region_objs = [
        o for o in bpy.context.scene.objects
        if o.type=='MESH' and o.name.startswith('R') and o.name.endswith('_DMSPRITEDEF')
    ]
    if not region_objs:
        print("⚠️ No region meshes found (Rxxxxx_DMSPRITEDEF).")
        return

    split_edges_to_snap_verts(region_objs, threshold=edge_snap_threshold)
    merge_by_distance(region_objs, dist=merge_dist)
    triangulate_meshes(region_objs)
    collapse_vertices_across_objects(region_objs, threshold=collapse_thresh)
    merge_by_distance(region_objs, dist=merge_dist)
    print("🎉 All region meshes finalized.")