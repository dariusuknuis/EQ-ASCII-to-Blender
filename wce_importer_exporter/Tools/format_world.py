# Tools/format_world.py
import bpy, bmesh, re
from mathutils import Matrix, Vector
from ..core.bmesh_utils import bmesh_with_split_norms, mesh_from_bmesh_with_split_norms, rearrange_uvs, merge_verts_by_attrs

def run_format_world():
    """
    Align UVs of region meshes under a WORLDDEF empty, join into one terrain mesh,
    rename mesh, data, and UV layers, zero out its object location by
    applying the location transform into the mesh data, and clean up scene objects.
    """
    context = bpy.context
    empty = context.active_object
    # Validate active object
    if not empty or empty.type != 'EMPTY' or "_WORLDDEF" not in empty.name:
        print("[Format World] Active object must be an Empty with '_WORLDDEF' in its name")
        return {'CANCELLED'}

    # Collect all region meshes under the empty by recursion
    meshes = []
    def recurse(obj):
        for child in obj.children:
            if child.type == 'MESH' and re.match(r"^R\d+_DMSPRITEDEF$", child.name):
                meshes.append(child)
            recurse(child)
    recurse(empty)

    if not meshes:
        print(f"[Format World] No region meshes found under '{empty.name}'")
        return {'CANCELLED'}
    
    for mesh in meshes:
        bm = bmesh_with_split_norms(mesh)
        rearrange_uvs(bm)
        merge_verts_by_attrs(bm)
        mesh_from_bmesh_with_split_norms(bm, mesh)
        for e in mesh.data.edges:
            e.use_edge_sharp = False

    # Deselect all, then select region meshes and set first as active
    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes:
        m.select_set(True)
    context.view_layer.objects.active = meshes[0]

    # Join selected meshes into one
    bpy.ops.object.join()
    joined = context.view_layer.objects.active

    # Compute new names
    base = empty.name.split("WORLDDEF")[0]
    new_name = base + "TERRAIN"

    # Rename object and mesh data
    joined.name = new_name
    joined.data.name = new_name

    # Zero out object location by applying that translation into the mesh data
    translation = joined.location.copy()
    if translation.length_squared != 0.0:
        joined.data.transform(Matrix.Translation(translation))
        joined.location = Vector((0.0, 0.0, 0.0))

    bm = bmesh.new(); bm.from_mesh(joined.data)
    joined.data.calc_normals_split()
    joined.data.use_auto_smooth = True

    ln_layer = bm.loops.layers.float_vector.new("orig_normals")
    loops = (l for f in bm.faces for l in f.loops)
    for loop in loops:
        loop[ln_layer] = joined.data.loops[loop.index].normal

    rearrange_uvs(bm)
    merge_verts_by_attrs(bm)

    bm.to_mesh(joined.data)
    joined.data.update()
    bm.free()

    mesh = joined.data
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.use_auto_smooth = True

    ln_attr = mesh.attributes.get("orig_normals")
    if ln_attr:
        custom_nors = [ Vector(cd.vector) for cd in ln_attr.data ]
        mesh.normals_split_custom_set(custom_nors)
        mesh.attributes.remove(ln_attr)

    # Clean up unwanted objects
    # Delete empty named WORLD_BOUNDS
    wb = bpy.data.objects.get("WORLD_BOUNDS")
    if wb and wb.type == 'EMPTY':
        bpy.data.objects.remove(wb, do_unlink=True)

    # Delete any empty ending with DMSPRITEDEF_BR
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY' and o.name.endswith("DMSPRITEDEF_BR"):
            bpy.data.objects.remove(o, do_unlink=True)

    # Helper to find direct child by name
    def find_child(parent, name):
        for c in parent.children:
            if c.name == name:
                return c
        return None

    # REGION and all its children
    region = find_child(empty, "REGION")
    if region and region.type == 'EMPTY':
        for child in list(region.children):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(region, do_unlink=True)

    # WorldTree_Root and all its children
    wroot = find_child(empty, "WorldTree_Root")
    if wroot and wroot.type == 'EMPTY':
        for child in list(wroot.children):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(wroot, do_unlink=True)

    # REGION_MESHES (but not its children)
    rmeshes = find_child(empty, "REGION_MESHES")
    if rmeshes and rmeshes.type == 'EMPTY':
        bpy.data.objects.remove(rmeshes, do_unlink=True)

    # Finally delete the selected WORLDDEF empty itself
    bpy.data.objects.remove(empty, do_unlink=True)

    print(f"[Format World] Formatted and cleaned scene; created '{new_name}' at origin")
    return {'FINISHED'}