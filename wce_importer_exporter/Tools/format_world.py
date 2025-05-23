# Tools/format_world.py
import bpy
import re
from mathutils import Matrix, Vector
from .align_uv_maps import run_align_uv_maps

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

    # Deselect all, then select region meshes and set first as active
    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes:
        m.select_set(True)
    context.view_layer.objects.active = meshes[0]

    # Align UVs using existing function
    result = run_align_uv_maps()
    if result != {'FINISHED'}:
        print("[Format World] UV alignment failed or was cancelled")
        return result

    # Join selected meshes into one
    bpy.ops.object.join()
    joined = context.view_layer.objects.active

    # Compute new names
    base = empty.name.split("WORLDDEF")[0]
    new_name = base + "TERRAIN"

    # Rename object and mesh data
    joined.name = new_name
    joined.data.name = new_name

    # Rename UV map layers
    for uv in joined.data.uv_layers:
        uv.name = new_name + "_uv"

    # Zero out object location by applying that translation into the mesh data
    translation = joined.location.copy()
    if translation.length_squared != 0.0:
        joined.data.transform(Matrix.Translation(translation))
        joined.location = Vector((0.0, 0.0, 0.0))

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