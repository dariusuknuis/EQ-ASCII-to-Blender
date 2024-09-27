import bpy

def create_bounding_sphere(mesh_obj, bounding_radius):
    # Create a UV Sphere with the bounding radius
    bpy.ops.mesh.primitive_uv_sphere_add(radius=bounding_radius)#, location=mesh_obj.location)
    sphere = bpy.context.object
    sphere.name = f"{mesh_obj.name}_BR"  # Append "_BR" to the mesh name

    # Create a light bluish transparent material with alpha blend
    mat = bpy.data.materials.new(name="BoundingSphereMaterial")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'  # Set blend method to Alpha Blend

    # Get the Principled BSDF node
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Set light blue color with 25% alpha (0.25)
        bsdf.inputs["Base Color"].default_value = (0.5, 0.8, 1.0, 0.25)  # RGBA with Alpha 0.25
        # Set alpha input to 0.25 for transparency
        bsdf.inputs["Alpha"].default_value = 0.25

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
