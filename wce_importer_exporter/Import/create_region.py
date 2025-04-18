import bpy
import json

def create_region(region_data):
    name = region_data['name']
    sphere = region_data['sphere']  # [x, y, z, radius]

    # Create the region empty
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'SPHERE'
    empty.empty_display_size = sphere[3]
    empty.location = (sphere[0], sphere[1], sphere[2])
    empty["VISLISTBYTES"] = bool(region_data.get("vislistbytes", 1))
    bpy.context.collection.objects.link(empty)

    # Write VISLISTs as custom JSON properties
    visible_lists = region_data.get("vislists", [])
    for i, vis in enumerate(visible_lists):
        # Prepare key name like "VISLIST_01", "VISLIST_02", etc.
        key = f"VISLIST_{i+1:02d}"

        # Construct JSON content
        if isinstance(vis, dict):
            # If already in dict format (just in case)
            json_data = vis
        else:
            list_type = "REGIONS" if isinstance(vis[1], list) else "RANGE"
            json_data = {
                "type": list_type,
                "num": vis[0],
                "regions" if list_type == "REGIONS" else "ranges": vis[1]
            }

        # Assign JSON string as a custom property
        empty[key] = json.dumps(json_data)

        # Try to parent the corresponding mesh (sprite) to the region empty
    sprite_name = region_data.get("sprite", "").strip('"')  # sometimes it might come with quotes
    if sprite_name in bpy.data.objects:
        mesh_obj = bpy.data.objects[sprite_name]

        # Make sure we're in Object mode
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        # Deselect all, then select parent and child
        bpy.ops.object.select_all(action='DESELECT')
        empty.select_set(True)
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = empty  # parent must be active

        # Set parent and keep transform
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

    else:
        print(f"[WARN] Mesh object for sprite '{sprite_name}' not found for region '{name}'")

    return empty
