import bpy
import os
import math

# Function to write mesh data to ASCII format
def write_dmspritedef(mesh, file):
    # Automatically switch to Object Mode if currently in Edit Mode
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
        
    print(f"Writing data for mesh: {mesh.name}")
    
    # Get the object location (CENTEROFFSET)
    center_offset = mesh.location
    file.write(f'DMSPRITEDEF2 "{mesh.name}"\n')
    file.write(f'\tCENTEROFFSET {center_offset.x:.8e} {center_offset.y:.8e} {center_offset.z:.8e}\n\n')

    # Write vertices (NUMVERTICES, XYZ)
    verts = mesh.data.vertices
    file.write(f'\tNUMVERTICES {len(verts)}\n')
    for v in verts:
        file.write(f'\tXYZ {v.co.x:.8e} {v.co.y:.8e} {v.co.z:.8e}\n')

    # Write UV coordinates (NUMUVS, UV)
    uv_layer = mesh.data.uv_layers.active
    if uv_layer:
        uv_data = uv_layer.data
        uv_per_vertex = {}

        # Initialize UVs per vertex to default value (0.0, 0.0) to ensure we handle every vertex
        for vertex in mesh.data.vertices:
            uv_per_vertex[vertex.index] = (0.0, 0.0)

        # Gather UVs for each vertex from loops, taking the last UV per vertex if multiple loops are found
        for loop in mesh.data.loops:
            vertex_index = loop.vertex_index
            uv = uv_data[loop.index].uv
            # Add 1 to the V-coordinate to reverse the applied transformation
            uv_per_vertex[vertex_index] = (uv.x, uv.y + 1)

        file.write(f'\n\tNUMUVS {len(verts)}\n')  # Use the number of vertices for NUMUVS

        # Write UV data per vertex in the order of vertex index
        for vertex_index in range(len(verts)):
            uv = uv_per_vertex[vertex_index]
            file.write(f'\tUV {uv[0]:.8e} {uv[1]:.8e}\n')
    else:
        # If there is no UV layer, write NUMUVS 0
        file.write(f'\n\tNUMUVS 0\n')

    # Write vertex normals (NUMVERTEXNORMALS, XYZ)
    if mesh.data.has_custom_normals:  # Check if the mesh has custom normals
        mesh.data.calc_normals_split()  # Calculate split normals for loops
        file.write(f'\n\tNUMVERTEXNORMALS {len(verts)}\n')

        # Create a dictionary to store the averaged normal per vertex
        normal_per_vertex = {v.index: [0.0, 0.0, 0.0] for v in mesh.data.vertices}
        count_per_vertex = {v.index: 0 for v in mesh.data.vertices}

        # Go through loops and sum the normals for each vertex
        for loop in mesh.data.loops:
            vertex_index = loop.vertex_index
            normal = loop.normal

            normal_per_vertex[vertex_index][0] += normal.x
            normal_per_vertex[vertex_index][1] += normal.y
            normal_per_vertex[vertex_index][2] += normal.z
            count_per_vertex[vertex_index] += 1

        # Average the normals for each vertex and write them out
        for vertex_index in range(len(verts)):
            if count_per_vertex[vertex_index] > 0:
                normal = normal_per_vertex[vertex_index]
                avg_normal = [n / count_per_vertex[vertex_index] for n in normal]
                file.write(f'\tXYZ {avg_normal[0]:.8e} {avg_normal[1]:.8e} {avg_normal[2]:.8e}\n')
            else:
                file.write(f'\tXYZ 0.00000000e+00 0.00000000e+00 0.00000000e+00\n')  # Handle missing normals
    else:
        file.write(f'\tNUMVERTEXNORMALS 0\n')

    # Write vertex colors (NUMVERTEXCOLORS, RGBA)
    color_layer = mesh.data.color_attributes.get("Color")  # Assuming 'Color' is the name of the vertex color layer
    if color_layer:
        # Count the number of vertices (since we're using per-vertex colors)
        file.write(f'\n\tNUMVERTEXCOLORS {len(mesh.data.vertices)}\n')
        
        # Iterate through the vertex colors and write them
        for v_index, vert in enumerate(mesh.data.vertices):
            # The color attribute is stored per vertex (POINT domain)
            color = color_layer.data[v_index].color
            r = round(color[0] * 255)
            g = round(color[1] * 255)
            b = round(color[2] * 255)
            a = round(color[3] * 255)
            file.write(f'\tRGBA {r} {g} {b} {a}\n')
    else:
        file.write('\n\tNUMVERTEXCOLORS 0\n')

    # Write SKINASSIGNMENTGROUPS
    armature = find_armature_for_mesh(mesh)
    if armature and mesh.vertex_groups:

        # Create a bone index mapping, excluding bones that end in "_ANIDAG"
        bone_name_to_index = {}
        adjusted_bone_index = 0  # Start adjusted bone index

        for bone in armature.data.bones:
            if not bone.name.endswith("_ANIDAG"):
                bone_name_to_index[bone.name] = adjusted_bone_index
                adjusted_bone_index += 1  # Increment only if it's not "_ANIDAG"

        # Create a list to store the groups (as vertex count and bone index pairs)
        skin_assignment_groups = []

        # Track the current number of vertices assigned per vertex group
        vertex_group_data = {}

        # Initialize the number of groups
        num_groups = len(mesh.vertex_groups)

        # Go through all the vertices and their groups
        for v in mesh.data.vertices:
            for group in v.groups:
                group_index = group.group
                vertex_group = mesh.vertex_groups[group_index]
                bone_index = bone_name_to_index.get(vertex_group.name, -1)  # Get adjusted bone index

                if bone_index == -1:
                    continue  # Skip if the vertex group is not linked to a bone

                if bone_index not in vertex_group_data:
                    vertex_group_data[bone_index] = []
                vertex_group_data[bone_index].append(v.index)

        # Sort by vertex index and create groups based on consecutive indices
        for bone_index, vertex_indices in vertex_group_data.items():
            vertex_indices.sort()  # Sort vertex indices

            start_index = vertex_indices[0]
            last_index = start_index
            count = 1

            for i in range(1, len(vertex_indices)):
                if vertex_indices[i] == last_index + 1:
                    last_index += 1
                    count += 1
                else:
                    # Store the previous group's data (number of vertices and bone index)
                    skin_assignment_groups.append((count, bone_index))
                    count = 1
                    last_index = vertex_indices[i]

            # Store the last group of consecutive vertices
            skin_assignment_groups.append((count, bone_index))

        # Write the SKINASSIGNMENTGROUPS data
        file.write(f'\n\n\tSKINASSIGNMENTGROUPS {num_groups}')
        for count, bone_index in skin_assignment_groups:
            file.write(f' {count} {bone_index}')
        file.write('\n')

    else:
        file.write('\n\n\tSKINASSIGNMENTGROUPS 0\n')

    # Write material palette (MATERIALPALETTE)
    if "MATERIALPALETTE" in mesh.keys():
        file.write(f'\tMATERIALPALETTE "{mesh["MATERIALPALETTE"]}"\n')

    # Check for shape keys for vertex animation
    if mesh.data.shape_keys and len(mesh.data.shape_keys.key_blocks) > 1:  # Ensure there is a shape key other than Basis
        # Get the name of the first shape key after "Basis"
        first_shape_key_name = mesh.data.shape_keys.key_blocks[1].name
        # Remove any trailing numerical suffix from the shape key name
        dmtrack_name = first_shape_key_name.rsplit('_', 1)[0]
        file.write(f'\tDMTRACKINST "{dmtrack_name}"\n')
    else:
        # No shape keys other than "Basis," so print empty DMTRACKINST
        file.write('\tDMTRACKINST ""\n')
        
    # Write POLYHEDRON
    polyhedron_mesh = find_child_mesh(mesh, '_POLYHDEF')
    if polyhedron_mesh:
        file.write(f'\n\tPOLYHEDRON\n\t\tDEFINITION "{polyhedron_mesh.name}"\n')
    else:
        file.write(f'\n\tPOLYHEDRON\n\t\tDEFINITION ""\n')

    # Write face and material data
    faces = mesh.data.polygons

    # Get the custom data layer for the "PASSABLE" flag
    passable_layer = mesh.data.polygon_layers_int.get("PASSABLE")

    file.write(f'\tNUMFACE2S {len(faces)}\n\n')
    for i, face in enumerate(faces):
        # Get the "PASSABLE" value from the custom layer, default to 0 if the layer doesn't exist
        if passable_layer:
            passable = passable_layer.data[i].value
        else:
            passable = 0  # Default to 0 if the layer doesn't exist

        verts = list(face.vertices)
        verts[0], verts[2] = verts[2], verts[0]  # Reverse winding order
        file.write(f'\t\tDMFACE2 //{i}\n')
        file.write(f'\t\t\tPASSABLE {passable}\n')
        file.write(f'\t\t\tTRIANGLE {verts[0]} {verts[1]} {verts[2]}\n')
        
    # Check for MESHOPS data
    meshops_name = f"{mesh.name}_MESHOPS"
    if meshops_name in bpy.data.texts:
        meshops_text = bpy.data.texts[meshops_name]
        # Filter out the first line and any blank lines
        meshops_lines = [line.body for line in meshops_text.lines[1:] if line.body.strip()]
        
        file.write(f'\n\tNUMMESHOPS {len(meshops_lines)}\n')
        for line in meshops_lines:
            file.write(f'\t{line}\n')
    else:
        file.write(f'\n\tNUMMESHOPS 0\n')
        
    # Write FACEMATERIALGROUPS
    materials = [mat for mat in mesh.data.materials if mat and mat.name.endswith("_MDF")]
    if materials:
        material_groups = []
        current_material = faces[0].material_index
        face_count = 0
        face_groups = []

        for face in faces:
            mat_index = face.material_index

            # If the material changes, append the previous group and start a new one
            if mat_index != current_material:
                face_groups.append((face_count, current_material))
                current_material = mat_index
                face_count = 1  # Start counting the new group
            else:
                face_count += 1

        # Don't forget to append the last group
        face_groups.append((face_count, current_material))

        # Write the FACEMATERIALGROUPS to the file
        file.write(f'\n\tFACEMATERIALGROUPS {len(face_groups)}')
        for count, mat_index in face_groups:
            file.write(f' {count} {mat_index}')
        file.write('\n')
    else:
        file.write(f'\n\tFACEMATERIALGROUPS 0\n')

    # Write VERTEXMATERIALGROUPS
    if "Vertex_Material_Index" in mesh.data.attributes:
        vertex_material_index = mesh.data.attributes["Vertex_Material_Index"].data
        
        # Check if the attribute contains any data
        if len(vertex_material_index) > 0:
            vertex_groups = []
            
            # Start tracking the first vertex and its material index
            current_mat_index = vertex_material_index[0].value
            vertex_count = 1
            
            for i in range(1, len(vertex_material_index)):
                mat_index = vertex_material_index[i].value
                if mat_index == current_mat_index:
                    vertex_count += 1
                else:
                    # Store the count and material index of the previous group
                    vertex_groups.append((vertex_count, current_mat_index))
                    # Reset for the next group
                    current_mat_index = mat_index
                    vertex_count = 1

            # Don't forget to store the last group
            vertex_groups.append((vertex_count, current_mat_index))

            # Write the VERTEXMATERIALGROUPS to the file
            file.write(f'\tVERTEXMATERIALGROUPS {len(vertex_groups)}')
            for vertex_count, mat_index in vertex_groups:
                file.write(f' {vertex_count} {mat_index}')
            file.write('\n')
        else:
            file.write(f'\tVERTEXMATERIALGROUPS 0\n')
    else:
        file.write(f'\tVERTEXMATERIALGROUPS 0\n')

    # Write bounding box and bounding radius
    bounding_box_mesh = find_child_mesh(mesh, '_BB')
    if bounding_box_mesh:
        min_bb = bounding_box_mesh.bound_box[0]
        max_bb = bounding_box_mesh.bound_box[6]
        file.write(f'\tBOUNDINGBOXMIN {min_bb[0]:.8e} {min_bb[1]:.8e} {min_bb[2]:.8e}\n')
        file.write(f'\tBOUNDINGBOXMAX {max_bb[0]:.8e} {max_bb[1]:.8e} {max_bb[2]:.8e}\n')
    else:
        file.write(f'\tBOUNDINGBOXMIN 0.00000000e+00 0.00000000e+00 0.00000000e+00\n')
        file.write(f'\tBOUNDINGBOXMAX 0.00000000e+00 0.00000000e+00 0.00000000e+00\n')

    bounding_radius_mesh = find_child_mesh(mesh, '_BR')
    if bounding_radius_mesh:
        # Get the X, Y, Z dimensions of the bounding box
        dimensions = bounding_radius_mesh.dimensions
        # Calculate the bounding radius as the largest dimension divided by 2
        bounding_radius = max(dimensions.x, dimensions.y, dimensions.z) / 2
        file.write(f'\tBOUNDINGRADIUS {bounding_radius:.8e}\n')
    else:
        file.write(f'\tBOUNDINGRADIUS 0.00000000e+00\n')

    # Write custom properties
    file.write(f'\n\tFPSCALE {mesh.get("FPSCALE", 0)}\n')
    file.write(f'\tHEXONEFLAG {mesh.get("HEXONEFLAG", 0)}\n')
    file.write(f'\tHEXTWOFLAG {mesh.get("HEXTWOFLAG", 0)}\n')
    file.write(f'\tHEXFOURTHOUSANDFLAG {mesh.get("HEXFOURTHOUSANDFLAG", 0)}\n')
    file.write(f'\tHEXEIGHTTHOUSANDFLAG {mesh.get("HEXEIGHTTHOUSANDFLAG", 0)}\n')
    file.write(f'\tHEXTENTHOUSANDFLAG {mesh.get("HEXTENTHOUSANDFLAG", 0)}\n')
    file.write(f'\tHEXTWENTYTHOUSANDFLAG {mesh.get("HEXTWENTYTHOUSANDFLAG", 0)}\n\n')

# Helper function to find the armature associated with a mesh
def find_armature_for_mesh(mesh):
    for modifier in mesh.modifiers:
        if modifier.type == 'ARMATURE' and modifier.object:
            return modifier.object
    if mesh.parent and mesh.parent.type == 'ARMATURE':
        return mesh.parent
    return None

# Function to find child meshes by suffix
def find_child_mesh(parent_obj, suffix):
    for child in parent_obj.children:
        if child.type == 'MESH' and child.name.endswith(suffix):
            return child
    return None

# Function to recursively search for meshes
def find_all_child_meshes(parent_obj):
    meshes = []
    for child in parent_obj.children:
        if child.type == 'MESH' and child.name.endswith("_DMSPRITEDEF"):
            meshes.append(child)
        # Recursively find meshes in the child objects
        meshes.extend(find_all_child_meshes(child))
    return meshes

# Main script execution
#output_file = r"C:\Users\dariu\Documents\Quail\Exporter\haf.export.wce"  # Replace with desired path
#with open(output_file, 'w') as file:
#    empty_obj = bpy.data.objects.get('haf')  # Replace with your empty object name
#    if not empty_obj:
#        print("Empty object not found!")
#        file.write("Empty object not found!\n")
#    else:
#        print(f"Empty object found: {empty_obj.name}")
#        meshes = find_all_child_meshes(empty_obj)
#        if not meshes:
#            file.write("No meshes found!\n")
#        else:
#            for mesh in meshes:
#                print(f"Processing mesh: {mesh.name}")
#                write_dmspritedef(mesh, file)

#print(f"ASCII data exported to {output_file}")
