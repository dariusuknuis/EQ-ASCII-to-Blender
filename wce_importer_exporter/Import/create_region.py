import bpy
import json

def create_region(region_data):
    name = region_data['name']
    sphere = region_data['sphere']  # [x, y, z, radius]

    # Create the empty
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'SPHERE'  # Use 'CUBE' to show bounding volume
    empty.empty_display_size = sphere[3]  # Diameter as visual scale (optional)

    # Position the empty at the center of the sphere
    empty.location = (sphere[0], sphere[1], sphere[2])
    

    # Add custom properties
    empty["VISLISTBYTES"] = bool(region_data.get("vislistbytes", 1))

    # Dump each visible list to a numbered property
    visible_lists = region_data.get("visible_lists", [])
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

    # Link to the current collection
    bpy.context.collection.objects.link(empty)

    return empty
