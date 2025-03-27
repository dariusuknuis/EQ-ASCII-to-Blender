import bpy
import math
import mathutils

def calculate_point_on_plane(normal, d):
    a, b, c = normal
    if abs(c) > 1e-6:
        return mathutils.Vector((0, 0, -d / c))
    elif abs(b) > 1e-6:
        return mathutils.Vector((0, -d / b, 0))
    elif abs(a) > 1e-6:
        return mathutils.Vector((-d / a, 0, 0))
    return mathutils.Vector((0, 0, 0))

def rotation_from_normal(normal):
    """
    Compute an Euler rotation that rotates the empty's local +Y axis to the given normal.
    This works for normals in any direction.
    """
    default_dir = mathutils.Vector((0, 1, 0))
    target_dir = mathutils.Vector(normal).normalized()
    quat = default_dir.rotation_difference(target_dir)
    return quat.to_euler()

def create_worldtree(worldtree_data):
    if not worldtree_data or "nodes" not in worldtree_data:
        print("No WorldTree data to process.")
        return None

    root_obj = bpy.data.objects.new("WorldTree_Root", None)
    bpy.context.collection.objects.link(root_obj)

    node_objects = {}

    # Create an empty for each node.
    for node in worldtree_data["nodes"]:
        node_name = f"WorldNode_{node['worldnode']}"
        normal = node["normal"][:3]
        d = node["normal"][3]
        position = calculate_point_on_plane(normal, d)
        rotation = rotation_from_normal(normal)
        
        node_obj = bpy.data.objects.new(node_name, None)
        node_obj.empty_display_type = 'CIRCLE'
        node_obj.empty_display_size = 1000.0
        node_obj.location = position
        node_obj.rotation_euler = rotation
        bpy.context.collection.objects.link(node_obj)

        node_obj["worldnode"] = node["worldnode"]
        node_obj["normal"] = normal
        node_obj["d"] = d
        node_obj["region_tag"] = node["region_tag"]
        node_obj["front_tree"] = node["front_tree"]
        node_obj["back_tree"] = node["back_tree"]

        node_objects[node["worldnode"]] = node_obj

    bpy.context.view_layer.update()

    # Re-parent child nodes while preserving their world transforms.
    for node in worldtree_data["nodes"]:
        node_obj = node_objects[node["worldnode"]]
        if node["front_tree"] > 0:
            front_child = node_objects.get(node["front_tree"])
            if front_child:
                wm = front_child.matrix_world.copy()
                front_child.parent = node_obj
                front_child.matrix_parent_inverse = node_obj.matrix_world.inverted()
                front_child.matrix_world = wm
        if node["back_tree"] > 0:
            back_child = node_objects.get(node["back_tree"])
            if back_child:
                wm = back_child.matrix_world.copy()
                back_child.parent = node_obj
                back_child.matrix_parent_inverse = node_obj.matrix_world.inverted()
                back_child.matrix_world = wm

    for node_obj in node_objects.values():
        if not node_obj.parent:
            wm = node_obj.matrix_world.copy()
            node_obj.parent = root_obj
            node_obj.matrix_parent_inverse = root_obj.matrix_world.inverted()
            node_obj.matrix_world = wm

    print(f"Created WorldTree with {len(worldtree_data['nodes'])} nodes as empties.")
    return root_obj
