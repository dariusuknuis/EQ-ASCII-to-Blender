# align_uv_maps.py

import bpy

def remove_unused_meshes():
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

def run_align_uv_maps():
    """
    Rename UV maps of all selected meshes to match the active object.
    """
    remove_unused_meshes()
    context = bpy.context
    sel = [o for o in context.selected_objects if o.type == 'MESH']
    active = context.active_object

    if active not in sel or active.type != 'MESH':
        bpy.ops.ui.popup_operator('INVOKE_DEFAULT', 
            message="Select mesh objects and make one the active object.")
        return {'CANCELLED'}

    src_uvs = [uv.name for uv in active.data.uv_layers]

    for ob in sel:
        if ob is active:
            continue
        uvlayers = ob.data.uv_layers
        if len(uvlayers) != len(src_uvs):
            # skip if counts don’t match
            continue
        for uv, new_name in zip(uvlayers, src_uvs):
            uv.name = new_name

    return {'FINISHED'}
