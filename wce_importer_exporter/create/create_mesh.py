import bpy
import bmesh
import mathutils
import re
from create_vertex_animation import create_vertex_animation

def create_mesh(mesh_data, parent_obj, armature_obj=None, armature_data=None, material_palettes=None, created_materials=None, vertex_animations=None, pending_objects=None):
    mesh = bpy.data.meshes.new(mesh_data['name'])
    obj = bpy.data.objects.new(mesh_data['name'], mesh)
    pending_objects.append(obj)
    region_mesh_pattern = re.compile(r"^R\d+_DMSPRITEDEF$")
    if region_mesh_pattern.match(obj.name):
        # Try to get the REGION_MESHES empty
        region_meshes_empty = bpy.data.objects.get("REGION_MESHES")

        # If REGION_MESHES doesn't exist yet, create and link it
        if region_meshes_empty is None:
            region_meshes_empty = bpy.data.objects.new("REGION_MESHES", None)
            bpy.context.collection.objects.link(region_meshes_empty)

        # Parent the mesh under REGION_MESHES
        obj.parent = region_meshes_empty
    else:
        obj.parent = parent_obj

    # Adjust origin by the center_offset value
    center_offset = mathutils.Vector(mesh_data.get('center_offset', [0.0, 0.0, 0.0]))
    obj.location = center_offset

    # Extract only the first three vertices for each face (without passable value)
    faces_for_creation = [face[:3] for face in mesh_data['faces']]
    mesh.from_pydata(mesh_data['vertices'], [], faces_for_creation)
    mesh.update()

    for poly in mesh.polygons:
        poly.use_smooth = True

    # == UV mapping ==
    if 'uvs' in mesh_data and mesh_data['uvs']:  # Check if UV data is present
        uvlayer = mesh.uv_layers.new(name="UVMap")
        for i, triangle in enumerate(mesh.polygons):
            vertices = list(triangle.vertices)
            for j, vertex in enumerate(vertices):
                uvlayer.data[triangle.loop_indices[j]].uv = (mesh_data['uvs'][vertex][0], mesh_data['uvs'][vertex][1] - 1)

    # == Apply Custom Normals ==
    if 'normals' in mesh_data and len(mesh_data['normals']) == len(mesh_data['vertices']):
        loop_normals = []
        for loop in mesh.loops:
            v_index = loop.vertex_index
            normal = mathutils.Vector(mesh_data['normals'][v_index])
            loop_normals.append(normal.normalized())
        mesh.normals_split_custom_set(loop_normals)
        mesh.use_auto_smooth = True

    # == Color Attribute (Vertex Colors per Vertex) ==
    if 'colors' in mesh_data and len(mesh_data['colors']) == len(mesh_data['vertices']):
        # Remove existing color attributes, if any
        color_attribute_name = "Color"  # Set the name for the color attribute
        if color_attribute_name in mesh.color_attributes:
            mesh.color_attributes.remove(mesh.color_attributes[color_attribute_name])

        # Create a new color attribute in the 'POINT' domain (per vertex)
        color_attribute = mesh.color_attributes.new(name=color_attribute_name, domain='POINT', type='FLOAT_COLOR')

        # Write vertex color data per vertex
        for v_index, vertex_color in enumerate(mesh_data['colors']):
            r, g, b, a = vertex_color  # Extract RGBA values
            color_attribute.data[v_index].color = (r / 255.0, g / 255.0, b / 255.0, a / 255.0)

    # == Vertex Material Indices as Custom Attribute ==
    if 'vertex_materials' in mesh_data:
        # Create a custom integer attribute for vertex materials in the 'POINT' domain
        vertex_material_attribute = mesh.attributes.new(name="Vertex_Material_Index", type='INT', domain='POINT')

        # Iterate over vertex_material_groups and assign material indices to vertices
        for vertex_start, vertex_end, material_index in mesh_data['vertex_materials']:
            for v_index in range(vertex_start, vertex_end):
                vertex_material_attribute.data[v_index].value = material_index

    # == Save custom properties ==
    material_palette = mesh_data.get('material_palette', "")
    obj["TAGINDEX"] = mesh_data.get("tag_index", 0)
    obj["MATERIALPALETTE"] = material_palette
    obj["FPSCALE"] = mesh_data.get("fpscale", 1)
    obj["HEXONEFLAG"] = bool(mesh_data.get("hexoneflag", 0))
    obj["HEXTWOFLAG"] = bool(mesh_data.get("hextwoflag", 0))
    obj["HEXFOURTHOUSANDFLAG"] = bool(mesh_data.get("hexfourthousandflag", 0))
    obj["HEXEIGHTTHOUSANDFLAG"] = bool(mesh_data.get("hexeightthousandflag", 0))
    obj["HEXTENTHOUSANDFLAG"] = bool(mesh_data.get("hextenthousandflag", 0))
    obj["HEXTWENTYTHOUSANDFLAG"] = bool(mesh_data.get("hextwentythousandflag", 0))

    # Add the "POLYHEDRON" custom property
    polyhedron_value = mesh_data.get("polyhedron", "")
    obj["POLYHEDRON"] = polyhedron_value  # Store as blank if polyhedron_value is ""

    # Create vertex groups if armature data is available
    if armature_obj and 'vertex_groups' in mesh_data and mesh_data['vertex_groups']:
        for vg_start, vg_end, bone_index in mesh_data['vertex_groups']:
            bone_name = armature_data['bones'][bone_index]['name']
            group = obj.vertex_groups.new(name=bone_name)
            group.add(range(vg_start, vg_end), 1.0, 'ADD')

    # Create materials only if face materials exist
    if 'face_materials' in mesh_data and mesh_data['face_materials']:
        palette_name = mesh_data.get('material_palette', None)
        if palette_name:
            if palette_name not in material_palettes:
                print(f"Error: Material palette '{palette_name}' not found for mesh '{mesh_data['name']}'")
                return None

            materials = material_palettes[palette_name]
            for mat_name in materials:
                if mat_name in created_materials:
                    obj.data.materials.append(created_materials[mat_name])
                else:
                    print(f"Warning: Material '{mat_name}' not found in created materials")
        else:
            print(f"Warning: No material palette found for mesh '{mesh_data['name']}'")
            materials = []

        # Assign materials to faces
        face_index = 0
        for face_data in mesh_data['face_materials']:
            start_face, end_face, material_index = face_data[:3]
            num_faces = end_face - start_face

            if material_index < len(materials):
                material_name = materials[material_index]
                material_list_index = obj.data.materials.find(material_name)
                if material_list_index == -1:
                    material_list_index = len(obj.data.materials) - 1

                for i in range(num_faces):
                    if face_index < len(obj.data.polygons):
                        obj.data.polygons[face_index].material_index = material_list_index
                        face_index += 1

    # == Apply the "PASSABLE" attribute as a custom face property ==
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Create a custom layer for the "PASSABLE" value
    passable_layer = bm.faces.layers.int.new("PASSABLE")

    # Assign the "PASSABLE" value to each face based on the parsed data
    for i, face in enumerate(bm.faces):
        passable_value = mesh_data['faces'][i][3]  # The fourth element in the face tuple is the PASSABLE flag
        face[passable_layer] = passable_value

    # Write the bmesh data back to the original mesh
    bm.to_mesh(mesh)
    bm.free()

    # == Store MESHOPS as a text block ==
    if 'meshops' in mesh_data and len(mesh_data['meshops']) > 0:  # Only proceed if meshops exists and is not empty
        text_block_name = f"{mesh_data['name']}_MESHOPS"
    
        if text_block_name in bpy.data.texts:
            text_block = bpy.data.texts[text_block_name]
        else:
            text_block = bpy.data.texts.new(text_block_name)

        text_block.clear()
        #text_block.write(f"MESHOPS for {mesh_data['name']}:\n")

        # Write each MESHOP entry
        for meshop in mesh_data['meshops']:
            text_block.write(f"MESHOP {meshop[0]} {meshop[1]} {meshop[2]:.8f} {meshop[3]} {meshop[4]}\n")

        # Link the text block to the mesh (optional if you want to reference it later)
        obj["MESHOPS_TEXT"] = text_block_name

    if 'dmtrack' in mesh_data and mesh_data['dmtrack']:
        dmtrack_name = mesh_data['dmtrack']
        create_vertex_animation(obj, dmtrack_name, vertex_animations)

    return obj