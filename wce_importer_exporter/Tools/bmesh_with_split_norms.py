import bmesh
from mathutils import Vector

def bmesh_with_split_norms(obj):

    if not obj or obj.type != 'MESH':
            raise RuntimeError("limited_dissolve_by_vertex_color: Please pass a mesh object.")
    
    me = obj.data
    me.calc_normals_split()
    me.use_auto_smooth = True

    # 2) Build a fresh BMesh from that Mesh
    bm = bmesh.new()
    bm.from_mesh(me)
    ln_layer = bm.loops.layers.float_vector.new("orig_normals")
    loops = (l for f in bm.faces for l in f.loops)
    for loop in loops:
        loop[ln_layer] = me.loops[loop.index].normal

    return bm

def mesh_from_bmesh_with_split_norms(bm, mesh):
    me = mesh.data
    bm.to_mesh(me)
    me.update()
    ln_layer = bm.loops.layers.float_vector.get("orig_normals")
    if not ln_layer:
        raise RuntimeError("Loop layer 'orig_normals' not found")

    # 3) accumulate normals per vertex
    vert_accum = {v.index: Vector((0,0,0)) for v in bm.verts}
    vert_count = {v.index: 0               for v in bm.verts}
    for f in bm.faces:
        for l in f.loops:
            n = l[ln_layer]
            vert_accum[l.vert.index] += n
            vert_count[l.vert.index] += 1

    # 4) build an averaged, normalized normal per-vertex
    vert_normal = {}
    for vid, total in vert_accum.items():
        cnt = vert_count[vid]
        if cnt > 0:
            vert_normal[vid] = (total / cnt).normalized()
        else:
            vert_normal[vid] = total.normalized()

    # 5) now build your final loop_normals array
    loops = [l for f in bm.faces for l in f.loops]
    loop_normals = [vert_normal[l.vert.index] for l in loops]
    bm.free()

    me.use_auto_smooth = True
    me.normals_split_custom_set(loop_normals)

    ln_attr = me.attributes.get("orig_normals")
    if ln_attr:
        me.attributes.remove(me.attributes.get("orig_normals"))
    
    