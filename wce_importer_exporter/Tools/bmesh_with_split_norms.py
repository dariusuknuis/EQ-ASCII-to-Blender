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
    bm.free()

    ln_attr = me.attributes.get("orig_normals")
    if ln_attr:
        # build flat list of normals in loop order
        custom_nors = [ Vector(cd.vector) for cd in ln_attr.data ]
        me.normals_split_custom_set(custom_nors)
        # me.attributes.remove(me.attributes.get("orig_normals"))

    me.use_auto_smooth = True
    
    