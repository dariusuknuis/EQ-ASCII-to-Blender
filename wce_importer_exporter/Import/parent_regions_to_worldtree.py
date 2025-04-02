import bpy
import re
import mathutils

def create_bounding_cube_for_region_empties():
    # Define the regex pattern for region empties, e.g., R000007
    pattern = re.compile(r"^R\d{6}$")
    
    # Collect all objects that match this naming pattern
    region_empties = [obj for obj in bpy.data.objects if pattern.match(obj.name)]
    
    if not region_empties:
        print("No region empties found.")
        return None
    
    # Compute the minimum and maximum coordinates among all region empties
    min_x = min(obj.location.x for obj in region_empties)
    min_y = min(obj.location.y for obj in region_empties)
    min_z = min(obj.location.z for obj in region_empties)
    
    max_x = max(obj.location.x for obj in region_empties)
    max_y = max(obj.location.y for obj in region_empties)
    max_z = max(obj.location.z for obj in region_empties)
    
    # Calculate the center of the bounding cube
    center = mathutils.Vector((
        (min_x + max_x) / 2,
        (min_y + max_y) / 2,
        (min_z + max_z) / 2
    ))
    
    # Compute the extents in each axis and then choose the maximum extent
    extent_x = max_x - min_x
    extent_y = max_y - min_y
    extent_z = max_z - min_z
    max_extent = max(extent_x, extent_y, extent_z)
    
    # Create a new empty object with display type 'CUBE'
    bounding_empty = bpy.data.objects.new("RegionBoundingCube", None)
    bounding_empty.empty_display_type = 'CUBE'
    # Set the display size; note that empties use a uniform size,
    # so we use the maximum extent. You can add a margin if desired.
    bounding_empty.empty_display_size = max_extent
    bounding_empty.location = center
    bpy.context.collection.objects.link(bounding_empty)
    
    print(f"Created bounding cube '{bounding_empty.name}' at {bounding_empty.location} with size {max_extent}")
    return bounding_empty

def parent_regions_to_worldtree():
    # Build a dictionary of worldtree nodes by region tag.
    # (Assumes that objects created by create_worldtree have a custom property "region_tag")
    world_nodes = {}
    for obj in bpy.data.objects:
        if "region_tag" in obj:
            world_nodes[obj["region_tag"]] = obj

    # Loop over all empties that represent regions.
    # (Assumes region empties are type 'EMPTY' and are named with the region tag, e.g., "R000007")
    for obj in bpy.data.objects:
        if obj.type == 'EMPTY' and obj.name.startswith("R"):
            region_tag = obj.name  # Or, if you stored it in a property, you could use that.
            if region_tag in world_nodes:
                parent_obj = world_nodes[region_tag]
                # Parent obj to parent_obj without inheriting parent transforms:
                bpy.ops.object.select_all(action='DESELECT')
                parent_obj.select_set(True)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = parent_obj
                bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
                print(f"Parented region empty '{obj.name}' to worldtree node '{parent_obj.name}'")
            else:
                print(f"No worldtree node found for region '{obj.name}'")
