import bpy
import re
import mathutils

def create_bounding_volume_for_region_empties():
    # Define a regex to match region empty names, e.g., R000007
    pattern = re.compile(r"^R\d{6}$")
    
    # Collect all objects matching the pattern
    region_empties = [obj for obj in bpy.data.objects if pattern.match(obj.name)]
    if not region_empties:
        print("No region empties found.")
        return None
    
    # For each region empty, include its sphere radius (empty_display_size) in the bounds:
    min_x = min(obj.location.x - obj.empty_display_size for obj in region_empties)
    max_x = max(obj.location.x + obj.empty_display_size for obj in region_empties)
    min_y = min(obj.location.y - obj.empty_display_size for obj in region_empties)
    max_y = max(obj.location.y + obj.empty_display_size for obj in region_empties)
    min_z = min(obj.location.z - obj.empty_display_size for obj in region_empties)
    max_z = max(obj.location.z + obj.empty_display_size for obj in region_empties)
    
    # Compute the full extents along each axis
    extent_x = (max_x - min_x) / 2
    extent_y = (max_y - min_y) / 2
    extent_z = (max_z - min_z) / 2

    # Calculate the center of the bounding volume so that its limits align with the computed extents
    center = mathutils.Vector((
        (min_x + max_x) / 2,
        (min_y + max_y) / 2,
        (min_z + max_z) / 2
    ))
    
    # Create an empty object with a cube display type
    bounding_empty = bpy.data.objects.new("ZONE_BOUNDS", None)
    bounding_empty.empty_display_type = 'CUBE'
    bounding_empty.location = center
    # Set the empty's display size to 1 so that its base geometry remains unit sized
    bounding_empty.empty_display_size = 1.0
    # Adjust the transform scale so that the empty spans the full extents.
    # The empty is a unit cube (from -0.5 to 0.5 in local space), so scaling it
    # by (extent_x, extent_y, extent_z) makes its boundaries match the computed extents.
    bounding_empty.scale = (extent_x, extent_y, extent_z)
    
    bpy.context.collection.objects.link(bounding_empty)
    
    #print(f"Created bounding empty '{bounding_empty.name}' at {bounding_empty.location} with scale {bounding_empty.scale}")
    return bounding_empty

def modify_regions_and_worldtree():
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
            region_tag = obj.name
            if region_tag in world_nodes:
                obj.hide_set(True)
            else:
                print(f"No worldtree node found for region '{obj.name}'")

    # -----------------------------------------------------------------------
    #  Create or retrieve the "ZoneBoundsIntersect" geometry node group
    # -----------------------------------------------------------------------
    gn_tree = create_zone_bounds_intersect_geometry_node()

    # -----------------------------------------------------------------------
    #  Add the Geometry Nodes modifier to non-leaf worldnode meshes
    # -----------------------------------------------------------------------
    # Define your own logic to identify "non-leaf" nodes. Here, we just add
    # the modifier to every worldnode that is a mesh. Adjust as needed.
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.name.startswith("WorldNode_"):
            mod = obj.modifiers.new("ZoneBoundsIntersect", 'NODES')
            mod.node_group = gn_tree
            obj.hide_set(True)
            #print(f"Added 'ZoneBoundsIntersect' modifier to {obj.name}")

def create_zone_bounds_intersect_geometry_node():
    # If a node group named "ZoneBoundsIntersect" already exists, reuse it:
    if "ZoneBoundsIntersect" in bpy.data.node_groups:
        return bpy.data.node_groups["ZoneBoundsIntersect"]
    
    # Otherwise, create a new Geometry Node tree
    gn_tree = bpy.data.node_groups.new("ZoneBoundsIntersect", 'GeometryNodeTree')
    gn_tree.name = "ZoneBoundsIntersect"
    
    # Create the group input node
    group_input = gn_tree.nodes.new("NodeGroupInput")
    group_input.location = (-600, 0)
    gn_tree.inputs.new("NodeSocketGeometry", "Geometry")
    
    # Create the group output node
    group_output = gn_tree.nodes.new("NodeGroupOutput")
    group_output.location = (200, 0)
    gn_tree.outputs.new("NodeSocketGeometry", "Geometry")
    
    # Create the Object Info node (points to the ZONE_BOUNDS empty)
    zone_bounds_obj = bpy.data.objects.get("ZONE_BOUNDS")
    object_info_node = gn_tree.nodes.new("GeometryNodeObjectInfo")
    object_info_node.location = (-600, -200)
    if object_info_node and "Object" in object_info_node.inputs:
            object_info_node.inputs["Object"].default_value = zone_bounds_obj
    else:
        print("Could not set the Object Info node to reference 'ZONE_BOUNDS'.")
    object_info_node.transform_space = 'RELATIVE'
    
    # Create the Mesh Cube node (2 m in each dimension)
    cube_node = gn_tree.nodes.new("GeometryNodeMeshCube")
    cube_node.location = (-400, -200)
    cube_node.inputs["Size"].default_value = (2.0, 2.0, 2.0)
    
    # Create the Transform node
    transform_node = gn_tree.nodes.new("GeometryNodeTransform")
    transform_node.location = (-200, -200)
    
    # Create the Mesh Boolean node, set to Intersect
    boolean_node = gn_tree.nodes.new("GeometryNodeMeshBoolean")
    boolean_node.operation = 'INTERSECT'
    boolean_node.location = (0, 0)
    
    # Link everything
    links = gn_tree.links
    # 1) Group Input -> Boolean (Mesh 2)
    links.new(group_input.outputs["Geometry"], boolean_node.inputs["Mesh 2"])
    # 2) Cube -> Transform
    links.new(cube_node.outputs["Mesh"], transform_node.inputs["Geometry"])
    # 3) Object Info -> Transform (Translation/Rotation/Scale)
    links.new(object_info_node.outputs["Location"],  transform_node.inputs["Translation"])
    links.new(object_info_node.outputs["Rotation"],  transform_node.inputs["Rotation"])
    links.new(object_info_node.outputs["Scale"],     transform_node.inputs["Scale"])
    # 4) Transform -> Boolean (Mesh 1)
    links.new(transform_node.outputs["Geometry"], boolean_node.inputs["Mesh 2"])
    # 5) Boolean -> Group Output
    links.new(boolean_node.outputs["Mesh"], group_output.inputs["Geometry"])
    
    return gn_tree

