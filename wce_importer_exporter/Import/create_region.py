import bpy

def create_region(region_data):
    name = region_data['name']
    sphere = region_data['sphere']  # [x, y, z, radius]

    # Create the empty
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = 'CUBE'  # Use 'CUBE' to show bounding volume
    empty.empty_display_size = sphere[3]  # Diameter as visual scale (optional)

    # Position the empty at the center of the sphere
    empty.location = (sphere[0], sphere[1], sphere[2])

    # Optionally store the sphere radius in a custom property
    # empty["region_radius"] = sphere[3]

    # Link to the current collection
    bpy.context.collection.objects.link(empty)

    return empty
