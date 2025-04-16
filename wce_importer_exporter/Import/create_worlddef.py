import bpy

def create_worlddef(worlddef_data, folder_name):
    name = folder_name.split('.')[0].upper() + "_WORLDDEF"

    empty = bpy.data.objects.new(name, None)
    empty["NEWWORLD"] = bool(worlddef_data.get("new_world", 0))
    empty["ZONE"] = bool(worlddef_data.get("zone", 1))
    empty["EQGVERSION?"] = worlddef_data.get("eqg_version", "")
    bpy.context.collection.objects.link(empty)

    return empty
