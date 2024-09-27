import bpy
import mathutils

# Function to create bounding material if it doesn't exist
def get_bounding_material():
    mat_name = "BoundingSphereMaterial"
    if mat_name not in bpy.data.materials:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        mat.blend_method = 'BLEND'  # Set blend method to Alpha Blend

        # Get the Principled BSDF node
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Set light blue color with 25% alpha (0.25)
            bsdf.inputs["Base Color"].default_value = (0.5, 0.8, 1.0, 0.25)  # RGBA with Alpha 0.25
            bsdf.inputs["Alpha"].default_value = 0.25  # Set transparency
        return mat
    else:
        return bpy.data.materials[mat_name]

# Function to create bounding sphere
def create_bounding_sphere(mesh_obj, bounding_radius):
    # Create a UV Sphere with the bounding radius
    bpy.ops.mesh.primitive_uv_sphere_add(radius=bounding_radius)
    sphere = bpy.context.object
    sphere.name = f"{mesh_obj.name}_BR"  # Append "_BR" to the mesh name

    # Get the bounding material
    mat = get_bounding_material()
    
    # Assign the material to the sphere
    sphere.data.materials.append(mat)

    # Parent the sphere to the mesh
    sphere.parent = mesh_obj

    # Add a "Copy Location" constraint to the bounding sphere
    if mesh_obj.vertex_groups:
        # Get the first vertex group name
        first_vgroup_name = mesh_obj.vertex_groups[0].name

        # Create the "Copy Location" constraint
        copy_loc_constraint = sphere.constraints.new(type='COPY_LOCATION')

        # Set the target to be the mesh
        copy_loc_constraint.target = mesh_obj
        
        # Set the vertex group name as the subtarget (for bones, vertex groups, etc.)
        copy_loc_constraint.subtarget = first_vgroup_name

    return sphere

# Function to create bounding box if not all values are 0
def create_bounding_box(mesh_obj, bounding_box_data):
    # Check if not all values in the bounding box data are zero
    if any(v != 0 for pair in bounding_box_data for v in pair):
        # Create an empty mesh object to represent the bounding box
        min_x, min_y, min_z = bounding_box_data[0]
        max_x, max_y, max_z = bounding_box_data[1]

        # Define the 8 corners of the bounding box
        vertices = [
            (min_x, min_y, min_z), (max_x, min_y, min_z), (max_x, max_y, min_z), (min_x, max_y, min_z),
            (min_x, min_y, max_z), (max_x, min_y, max_z), (max_x, max_y, max_z), (min_x, max_y, max_z)
        ]

        # Define the faces of the bounding box (connect the vertices)
        faces = [
            (0, 1, 2, 3),  # Bottom face
            (4, 5, 6, 7),  # Top face
            (0, 1, 5, 4),  # Side face
            (1, 2, 6, 5),  # Side face
            (2, 3, 7, 6),  # Side face
            (3, 0, 4, 7)   # Side face
        ]

        # Create the bounding box mesh and object
        bbox_mesh = bpy.data.meshes.new(f"{mesh_obj.name}_BB_Mesh")
        bbox_mesh.from_pydata(vertices, [], faces)
        bbox_obj = bpy.data.objects.new(f"{mesh_obj.name}_BB", bbox_mesh)

        # Get the bounding material
        mat = get_bounding_material()

        # Assign the material to the bounding box
        bbox_obj.data.materials.append(mat)

        # Link the bounding box to the scene and parent it to the mesh
        bpy.context.collection.objects.link(bbox_obj)
        bbox_obj.parent = mesh_obj

        return bbox_obj
    return None