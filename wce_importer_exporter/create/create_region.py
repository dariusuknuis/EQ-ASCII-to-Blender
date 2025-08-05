import bpy
import json

def create_region(region_data, pending_objects=None):
    name = region_data['name']
    sphere = region_data['sphere']  # [x, y, z, radius]

    # Create the region empty
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'SPHERE'
    empty.empty_display_size = sphere[3]
    empty.location = (sphere[0], sphere[1], sphere[2])
    empty["VISLISTBYTES"] = bool(region_data.get("vislistbytes", 1))
    empty["SPRITE"] = region_data['sprite']
    pending_objects.append(empty)

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
            json_data = {
                "num_ranges": vis[0],
                "range_bytes": vis[1]
            }

        # Assign JSON string as a custom property
        empty[key] = json.dumps(json_data)

    # Parent to REGION empty if it exists
    region_parent = bpy.data.objects.get("REGION")
    if region_parent:
        empty.parent = region_parent
    else:
        print("[WARN] REGION parent object not found.")

    return empty
