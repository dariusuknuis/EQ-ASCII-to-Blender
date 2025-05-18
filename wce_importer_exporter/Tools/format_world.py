# Tools/format_world.py
import bpy
import re
from .align_uv_maps import run_align_uv_maps

def run_format_world():
    """
    Align UVs of region meshes under a WORLDDEF empty, join into one terrain mesh,
    and rename mesh, data, and UV layers appropriately.
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

    print(f"[Format World] Formatted world mesh: '{new_name}'")
    return {'FINISHED'}