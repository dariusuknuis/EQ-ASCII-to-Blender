import bpy
import math
import mathutils

DEFAULT_SIZE = 10000.0  # Default plane side length

def create_bsp_plane_mesh(name="BSPPlaneMesh", size=DEFAULT_SIZE):
    """
    Create a plane mesh that is oriented in its local space so that its face lies in the XZ plane.
    That means its vertices are defined so that the plane’s normal is (0, 1, 0) (local +Y).
    We create a square of side length 'size'.
    """
    half = size / 2.0
    # Create a default plane in the XY plane (face normal = (0,0,1))
    verts = [
        (-half, -half, 0),
        ( half, -half, 0),
        ( half,  half, 0),
        (-half,  half, 0)
    ]
    faces = [(0, 1, 2, 3)]
    # Rotate the mesh by -90° about the X axis to put the face into the XZ plane.
    rot = mathutils.Euler((-math.pi/2, 0, 0), 'XYZ').to_matrix().to_4x4()
    verts_rot = [rot @ mathutils.Vector(v) for v in verts]
    
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts_rot, [], faces)
    mesh.update()
    return mesh

def create_leaf_mesh(name="LeafMesh"):
    """
    Create a minimal mesh for leaf nodes.
    We'll create a mesh with a single vertex at the origin.
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0)], [], [])
    mesh.update()
    return mesh

def rotation_from_normal(normal):
    """
    Compute an Euler rotation that rotates the object's local +Y axis (which is the normal of our base plane)
    to align with the given target normal.
    """
    default_dir = mathutils.Vector((0, 1, 0))
    target_dir = mathutils.Vector(normal).normalized()
    quat = default_dir.rotation_difference(target_dir)
    return quat.to_euler()

def calculate_point_on_plane(normal, d, max_distance=10000.0):
    """
    Calculate the point on the plane (n · p + d = 0) that is closest to the origin.
    n must be normalized. That point is p = -d * n.
    
    If the distance of that point exceeds max_distance, return the point on the ray (origin to p)
    clamped to max_distance.
    """
    n = mathutils.Vector(normal).normalized()
    p = -d * n  # The unique closest point on the plane.
    if p.length > max_distance:
        p = p.normalized() * max_distance
    return p

def compute_scale_from_location(location, default_size=DEFAULT_SIZE):
    """
    Compute a uniform scale factor for the plane based on the node's location.
    Increase the plane's size by the absolute value of the highest coordinate.
    """
    offset = max(abs(location.x), abs(location.y), abs(location.z))
    final_size = default_size + offset
    scale_factor = final_size / default_size
    return scale_factor

def create_worldtree(worldtree_data, pending_objects=None):
    """
    Creates a WorldTree from the provided data.
    Each non-leaf node is represented by a plane mesh (with a translucent yellow material and a Solidify modifier)
    oriented so that its local +Y (the plane's normal) matches the node's plane normal.
    For leaf nodes (no front_tree or back_tree), a minimal mesh (with one vertex) is created and its rotation is set to zero.
    The plane's size is increased by the absolute maximum coordinate of its location.
    Parent-child relationships are set up, but we preserve each object's world transform.
    """
    if not worldtree_data or "nodes" not in worldtree_data:
        print("No WorldTree data to process.")
        return None

    # Create a root empty for organization.
    root_obj = bpy.data.objects.new("WorldTree_Root", None)
    pending_objects.append(root_obj)

    # Create a base plane mesh for non-leaf nodes.
    base_mesh = create_bsp_plane_mesh(size=DEFAULT_SIZE)
    
    # Create a translucent yellow material.
    mat = bpy.data.materials.get("WorldTreePlaneMaterial")
    if not mat:
        mat = bpy.data.materials.new("WorldTreePlaneMaterial")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 0.0, 0.25)  # yellow, alpha 0.25
            bsdf.inputs["Alpha"].default_value = 0.25
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'NONE'
        mat.use_backface_culling = False

    node_objects = {}

    # Create an object for each node.
    for node in worldtree_data["nodes"]:
        node_name = f"WorldNode_{node['worldnode']}"
        normal = node["normal"][:3]  # e.g., [0, -1, 0]
        d = node["normal"][3]        # e.g., 261.188873

        # Calculate the location of the plane.
        position = calculate_point_on_plane(normal, d)
        # Determine if the node is a leaf node.
        is_leaf = (node["front_tree"] == 0 and node["back_tree"] == 0)
        
        if is_leaf:
            # For leaf nodes, create a minimal mesh (1 vertex at the origin).
            mesh_data = create_leaf_mesh(name=f"LeafMesh_{node['worldnode']}")
            rotation = mathutils.Euler((0, 0, 0))  # zero rotation
            obj_scale = (1, 1, 1)
        else:
            # Non-leaf nodes use the base plane mesh.
            mesh_data = base_mesh
            # Compute rotation so that the plane's local +Y (the face normal) aligns with the node's normal.
            rotation = rotation_from_normal(normal)
            # Compute scale factor based on the maximum offset.
            scale_factor = compute_scale_from_location(position, default_size=DEFAULT_SIZE)
            obj_scale = (scale_factor, scale_factor, scale_factor)
        
        node_obj = bpy.data.objects.new(node_name, mesh_data)
        node_obj.location = position
        node_obj.rotation_euler = rotation
        node_obj.scale = obj_scale
        node_obj.parent = root_obj

        # For non-leaf nodes, assign material and add a Solidify modifier.
        if not is_leaf:
            if len(node_obj.data.materials) == 0:
                node_obj.data.materials.append(mat)
            else:
                node_obj.data.materials[0] = mat
            solidify = node_obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            solidify.thickness = 3.0
            solidify.offset = 0.0
            
            

        pending_objects.append(node_obj)

        # Save custom properties.
        node_obj["worldnode"] = node["worldnode"]
        node_obj["normal"] = normal
        node_obj["d"] = d
        node_obj["region_tag"] = node["region_tag"]
        node_obj["front_tree"] = node["front_tree"]
        node_obj["back_tree"] = node["back_tree"]

        node_objects[node["worldnode"]] = node_obj

    # bpy.context.view_layer.update()

    # # Re-parent child nodes while preserving their world transforms.
    # for node in worldtree_data["nodes"]:
    #     parent_obj = node_objects[node["worldnode"]]
    #     if node["front_tree"] > 0:
    #         front_child = node_objects.get(node["front_tree"])
    #         if front_child:
    #             wm = front_child.matrix_world.copy()
    #             front_child.parent = parent_obj
    #             front_child.matrix_parent_inverse = parent_obj.matrix_world.inverted()
    #             front_child.matrix_world = wm
    #             parent_obj.hide_set(True)
    #     if node["back_tree"] > 0:
    #         back_child = node_objects.get(node["back_tree"])
    #         if back_child:
    #             wm = back_child.matrix_world.copy()
    #             back_child.parent = parent_obj
    #             back_child.matrix_parent_inverse = parent_obj.matrix_world.inverted()
    #             back_child.matrix_world = wm
    #             parent_obj.hide_set(True)

    # for node_obj in node_objects.values():
    #     if not node_obj.parent:
    #         wm = node_obj.matrix_world.copy()
    #         node_obj.parent = root_obj
    #         node_obj.matrix_parent_inverse = root_obj.matrix_world.inverted()
    #         node_obj.matrix_world = wm

    print(f"Created WorldTree with {len(worldtree_data['nodes'])} nodes as meshes (leaf nodes have zero rotation).")
    return root_obj
