import bpy
import mathutils

def calculate_point_on_plane(normal, d):
    """
    Calculate a point on the plane defined by Ax + By + Cz + D = 0.
    For simplicity, find an intersection point with one axis if possible.
    """
    a, b, c = normal  # Expect only (A, B, C) here
    if c != 0:  # Prefer Z-axis intersection
        return mathutils.Vector((0, 0, -d / c))
    elif b != 0:  # Prefer Y-axis intersection
        return mathutils.Vector((0, -d / b, 0))
    elif a != 0:  # Prefer X-axis intersection
        return mathutils.Vector((-d / a, 0, 0))
    return mathutils.Vector((0, 0, 0))  # Fallback to origin if all coefficients are zero

def create_worldtree(worldtree_data):
    """
    Creates a WorldTree in Blender from the parsed worldtree data.

    Args:
        worldtree_data (dict): A dictionary containing the WorldTree data with nodes.
    Returns:
        bpy.types.Object: The root object of the created WorldTree.
    """
    if not worldtree_data or "nodes" not in worldtree_data:
        print("No WorldTree data to process.")
        return None

    # Create a root object for the WorldTree
    root_obj = bpy.data.objects.new("WorldTree_Root", None)
    bpy.context.collection.objects.link(root_obj)

    # Create a dictionary to hold references to node objects
    node_objects = {}

    # Create Blender objects for each node
    for node in worldtree_data["nodes"]:
        node_name = f"WorldNode_{node['worldnode']}"
        
        # Extract the normal vector (A, B, C) and the D value
        normal = node["normal"][:3]  # First three values are (A, B, C)
        d = node["normal"][3]        # Fourth value is D

        # Calculate the position of the node based on the plane's normal and D value
        position = calculate_point_on_plane(normal, d)
        
        node_obj = bpy.data.objects.new(node_name, None)
        node_obj.empty_display_type = 'ARROWS'
        node_obj.empty_display_size = 500.0  # Set size for better visibility
        node_obj.location = position  # Set the node's location based on the plane
        
        bpy.context.collection.objects.link(node_obj)

        # Add custom properties to the node object
        node_obj["worldnode"] = node["worldnode"]
        node_obj["normal"] = normal  # Store the normal vector (A, B, C)
        node_obj["d"] = d            # Store the D value separately
        node_obj["region_tag"] = node["region_tag"]
        node_obj["front_tree"] = node["front_tree"]
        node_obj["back_tree"] = node["back_tree"]

        # Store the node object in the dictionary
        node_objects[node["worldnode"]] = node_obj

    # Set up parent-child relationships based on the tree structure
    for node in worldtree_data["nodes"]:
        node_obj = node_objects[node["worldnode"]]
        if node["front_tree"] > 0:  # Front tree child
            front_child = node_objects.get(node["front_tree"])
            if front_child:
                front_child.parent = node_obj
        if node["back_tree"] > 0:  # Back tree child
            back_child = node_objects.get(node["back_tree"])
            if back_child:
                back_child.parent = node_obj

    # Link all top-level nodes to the root object
    for node_obj in node_objects.values():
        if not node_obj.parent:
            node_obj.parent = root_obj

    print(f"Created WorldTree with {len(worldtree_data['nodes'])} nodes.")
    return root_obj
