import bpy
import os
import struct
from material_utils import has_dds_header, add_texture_coordinate_and_mapping_nodes, apply_tiled_mapping

def add_tiled_texture_nodes(material, frame_data, texture_info, node_group_cache, base_path=None):
    """
    Adds tiled texture nodes to a material for a specific frame.

    :param material: The material to modify.
    :param frame_data: A dictionary containing information about the current tiled frame.
    :param texture_info: A dictionary containing overall texture information, including the number of tiled frames.
    :param node_group_cache: A cache to store and retrieve existing node groups.
    :param base_path: The base path where texture files are located.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    transparent_bsdf_node = None
    previous_palette_mask_group_output = None
    palette_mask_texture_node = None

    # Use the palette_mask_file to identify the palette_mask_texture_node
    palette_mask_file = texture_info.get('palette_mask_file', '')

    if palette_mask_file:
        # Convert the palette mask file path to an absolute path
        palette_mask_file_path = os.path.abspath(os.path.join(base_path, palette_mask_file)) if base_path else palette_mask_file

        # Identify palette_mask_texture_node by matching the name with palette_mask_file
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image and node.image.filepath == bpy.path.abspath(palette_mask_file_path):
                palette_mask_texture_node = node
#                print(f"Identified palette_mask_texture_node: {palette_mask_texture_node.name}")
                break

    main_shader_node = None
    for node in nodes:
        if node.type == 'GROUP' and node.node_tree.name in node_group_cache:
            main_shader_node = node
            break

    # Create or get the PaletteMask node group definition
    palette_mask_node_group_name = "PaletteMask"
    if palette_mask_node_group_name not in bpy.data.node_groups:
        palette_mask_node_group = bpy.data.node_groups.new(name=palette_mask_node_group_name, type='ShaderNodeTree')
        create_palette_mask_node_group(palette_mask_node_group)
    else:
        palette_mask_node_group = bpy.data.node_groups[palette_mask_node_group_name]

    # Process the specific tiled frame
    if frame_data.get('type') == 'tiled':
        frame_file = frame_data['file']
        color_index = frame_data['color_index']  # Use color_index instead of frame_index
        scale = frame_data['scale']
        blend = frame_data['blend']
        num_tiled_frames = texture_info.get('num_tiled_frames', 0)  # Get num_tiled_frames from texture_info

        tiled_texture_name = f"{color_index + 1}, {int(scale / 10)}, {blend}, {os.path.basename(frame_file)}"

        # Construct full path to the file
        full_path = os.path.join(base_path, frame_file) if base_path else frame_file
        texture_path = bpy.path.abspath(full_path)

        # Check if the file exists before loading
        if not os.path.isfile(texture_path):
            print(f"Warning: Tiled texture file not found: {texture_path}")
            return

        try:
            # Create or reuse Image Texture node for the tiled texture
            tiled_texture_node = nodes.get(tiled_texture_name)
            if not tiled_texture_node:
                tiled_texture_node = nodes.new(type='ShaderNodeTexImage')
                tiled_texture_node.image = bpy.data.images.load(texture_path)
                tiled_texture_node.location = (-400, -200 - (color_index + 1) * 300)
                tiled_texture_node.name = tiled_texture_name
                tiled_texture_node.label = tiled_texture_name
        except RuntimeError as e:
            print(f"Error loading tiled texture file: {texture_path}: {e}")
            return

        # Read the palette color for the current color index
        if palette_mask_file:
            palette_mask_path = os.path.join(base_path, palette_mask_file) if base_path else palette_mask_file
            if os.path.isfile(palette_mask_path):
#                print(f"Palette mask texture file found: {palette_mask_path} for color index: {color_index}")
                palette_color = read_bmp_palette_color(palette_mask_path, color_index)
            else:
#                print(f"Warning: Palette mask texture file not found at path: {palette_mask_path} for color index: {color_index}")
                palette_color = (1.0, 0.0, 0.0)  # Default to red if palette mask not found
        else:
#            print(f"Warning: No palette mask texture file specified for color index: {color_index}")
            palette_color = (1.0, 0.0, 0.0)  # Default to red if palette mask not found

        # Add or create Index Color node with the proper name and color
        index_color_node_name = f"Index {color_index + 1} Color"
        index_color_node = nodes.new(type='ShaderNodeRGB')
        index_color_node.location = (-100, -150 - (color_index + 1) * 300)
        index_color_node.name = index_color_node_name
        index_color_node.outputs[0].default_value = (*palette_color, 1.0)  # Correctly set RGB + Alpha as 4 elements

        # Add or reuse Texture Coordinate and Mapping nodes
        tex_coord_node, mapping_node = add_texture_coordinate_and_mapping_nodes(nodes, links, tiled_texture_node, texture_path)

        # Apply the scale to the Mapping node
        apply_tiled_mapping(mapping_node, scale, has_dds_header(texture_path))

        # Create or reuse the PaletteMask node group
        palette_mask_group_node_name = f"PaletteMask"
        palette_mask_group_node = nodes.new(type='ShaderNodeGroup')
        palette_mask_group_node.node_tree = palette_mask_node_group
        palette_mask_group_node.location = (100, -300 - (color_index + 1) * 300)
        palette_mask_group_node.name = palette_mask_group_node_name

        # Connect nodes for palette masking
        links.new(index_color_node.outputs['Color'], palette_mask_group_node.inputs['NdxClr'])
        links.new(tiled_texture_node.outputs['Color'], palette_mask_group_node.inputs['Texture'])

        # If there's a previous palette mask node, connect its output to the Mix input of the current node
        if previous_palette_mask_group_output:
            links.new(previous_palette_mask_group_output, palette_mask_group_node.inputs['Mix'])

        # Update previous output node
        previous_palette_mask_group_output = palette_mask_group_node.outputs['Shader']

        last_palette_mask_node = palette_mask_group_node

        # If this is the last tiled frame, prepare to connect the final output
        if color_index + 1 == num_tiled_frames:
            # Create the final mix shader to blend the last tiled texture with the base material
            final_mix_shader = nodes.new(type='ShaderNodeMixShader')
            final_mix_shader.location = (600, -1500)

            # Add a Transparent BSDF if not already created
            if not transparent_bsdf_node:
                transparent_bsdf_node = nodes.new(type='ShaderNodeBsdfTransparent')
                transparent_bsdf_node.location = (400, -1500)

            # Connect the Transparent BSDF to the first input of the final mix shader
            links.new(transparent_bsdf_node.outputs['BSDF'], final_mix_shader.inputs[1])

            # Connect the last PaletteMask node group's Shader output to the second input of the final mix shader
            links.new(last_palette_mask_node.outputs['Shader'], final_mix_shader.inputs[2])

            # Create another mix shader for the base material blending
            base_mix_shader = nodes.new(type='ShaderNodeMixShader')
            base_mix_shader.location = (800, -1000)

            # Connect the final mix shader output to the second input of the base mix shader
            links.new(final_mix_shader.outputs['Shader'], base_mix_shader.inputs[2])

            # Connect the main material shader output to the first input of the base mix shader
            if main_shader_node:
                links.new(main_shader_node.outputs[0], base_mix_shader.inputs[1])

            # Connect the base mix shader to the material output
            material_output_node = nodes.get("Material Output")
            if material_output_node:
                links.new(base_mix_shader.outputs['Shader'], material_output_node.inputs['Surface'])

                # Adjust the position of the material output node
                material_output_node.location.x += 1000
                material_output_node.location.y -= 1000

        else:
            # Continue connecting the PaletteMask nodes if not the last tiled frame
            if previous_palette_mask_group_output:
                links.new(previous_palette_mask_group_output, palette_mask_group_node.inputs['Mix'])

#    print(f"Added tiled texture nodes to material: {material.name} for color index: {color_index}")

    # Scan through material nodes to link PaletteMask node groups
    palette_mask_nodes = [node for node in nodes if node.type == 'GROUP' and node.node_tree == palette_mask_node_group]

    # Link the PaletteMask node groups and palette_mask_texture_node if found
    for i in range(len(palette_mask_nodes)):
        current_node = palette_mask_nodes[i]

        # Connect the Color output of the palette_mask_texture_node to the ClrPalette input of each PaletteMask node group
        if palette_mask_texture_node:
#            print(f"Connecting {palette_mask_texture_node.name} Color output to {current_node.name} ClrPalette input")
            links.new(palette_mask_texture_node.outputs['Color'], current_node.inputs['ClrPalette'])

        # Connect the Shader output of the current node to the Mix input of the next node, if not already connected
        if i < len(palette_mask_nodes) - 1:
            next_node = palette_mask_nodes[i + 1]
            if not any(link.from_node == current_node and link.to_node == next_node for link in links):
                links.new(current_node.outputs['Shader'], next_node.inputs['Mix'])

#    print(f"Linked PaletteMask node groups and palette_mask_texture_node for material: {material.name}")

def read_bmp_palette_color(file_path, color_index):
    """
    Reads the color at the specified index from a BMP palette.

    :param file_path: The path to the BMP file.
    :param color_index: The index of the color in the BMP palette.
    :return: The RGB color as a tuple (red, green, blue).
    """
    with open(file_path, 'rb') as f:
        palette_offset = 54 + color_index * 4  # BMP header is 54 bytes + 4 bytes per color entry
        f.seek(palette_offset)
        palette_data = f.read(4)  # Read the color data (BGRX format)
        blue, green, red, _ = struct.unpack('BBBB', palette_data)
        return red / 255.0, green / 255.0, blue / 255.0

def create_palette_mask_node_group(palette_mask_node_group):
    """
    Creates the PaletteMask node group used for tiled textures.

    :param palette_mask_node_group: The node group to be populated.
    """
    nodes = palette_mask_node_group.nodes
    links = palette_mask_node_group.links

    # Create nodes inside the PaletteMask node group
    group_input = nodes.new('NodeGroupInput')
    group_input.location = (-800, 0)
    palette_mask_node_group.inputs.new('NodeSocketColor', 'ClrPalette')
    palette_mask_node_group.inputs.new('NodeSocketColor', 'NdxClr')
    palette_mask_node_group.inputs.new('NodeSocketShader', 'Mix')
    palette_mask_node_group.inputs.new('NodeSocketColor', 'Texture')

    group_output = nodes.new('NodeGroupOutput')
    group_output.location = (600, 0)
    palette_mask_node_group.outputs.new('NodeSocketShader', 'Shader')

    separate_clr_palette = nodes.new(type='ShaderNodeSeparateColor')
    separate_clr_palette.location = (-400, 300)

    separate_ndx_clr = nodes.new(type='ShaderNodeSeparateColor')
    separate_ndx_clr.location = (-400, 100)

    less_than_red = nodes.new(type='ShaderNodeMath')
    less_than_red.operation = 'LESS_THAN'
    less_than_red.location = (-200, 300)

    greater_than_red = nodes.new(type='ShaderNodeMath')
    greater_than_red.operation = 'GREATER_THAN'
    greater_than_red.location = (-200, 250)

    less_than_green = nodes.new(type='ShaderNodeMath')
    less_than_green.operation = 'LESS_THAN'
    less_than_green.location = (-200, 200)

    greater_than_green = nodes.new(type='ShaderNodeMath')
    greater_than_green.operation = 'GREATER_THAN'
    greater_than_green.location = (-200, 150)

    less_than_blue = nodes.new(type='ShaderNodeMath')
    less_than_blue.operation = 'LESS_THAN'
    less_than_blue.location = (-200, 100)

    greater_than_blue = nodes.new(type='ShaderNodeMath')
    greater_than_blue.operation = 'GREATER_THAN'
    greater_than_blue.location = (-200, 50)

    # Math nodes with updated default values for the second input
    add_red = nodes.new(type='ShaderNodeMath')
    add_red.operation = 'ADD'
    add_red.location = (-400, -100)
    add_red.inputs[1].default_value = 0.001  # Updated default value

    sub_red = nodes.new(type='ShaderNodeMath')
    sub_red.operation = 'SUBTRACT'
    sub_red.location = (-400, -150)
    sub_red.inputs[1].default_value = 0.001  # Updated default value

    add_green = nodes.new(type='ShaderNodeMath')
    add_green.operation = 'ADD'
    add_green.location = (-400, -200)
    add_green.inputs[1].default_value = 0.001  # Updated default value

    sub_green = nodes.new(type='ShaderNodeMath')
    sub_green.operation = 'SUBTRACT'
    sub_green.location = (-400, -250)
    sub_green.inputs[1].default_value = 0.001  # Updated default value

    add_blue = nodes.new(type='ShaderNodeMath')
    add_blue.operation = 'ADD'
    add_blue.location = (-400, -300)
    add_blue.inputs[1].default_value = 0.001  # Updated default value

    sub_blue = nodes.new(type='ShaderNodeMath')
    sub_blue.operation = 'SUBTRACT'
    sub_blue.location = (-400, -350)
    sub_blue.inputs[1].default_value = 0.001  # Updated default value

    multiply_red = nodes.new(type='ShaderNodeMath')
    multiply_red.operation = 'MULTIPLY'
    multiply_red.location = (0, 300)

    multiply_green = nodes.new(type='ShaderNodeMath')
    multiply_green.operation = 'MULTIPLY'
    multiply_green.location = (0, 200)

    multiply_blue = nodes.new(type='ShaderNodeMath')
    multiply_blue.operation = 'MULTIPLY'
    multiply_blue.location = (0, 100)

    final_multiply = nodes.new(type='ShaderNodeMath')
    final_multiply.operation = 'MULTIPLY'
    final_multiply.location = (200, 200)

    final_multiply_2 = nodes.new(type='ShaderNodeMath')
    final_multiply_2.operation = 'MULTIPLY'
    final_multiply_2.location = (400, 100)

    mix_shader = nodes.new(type='ShaderNodeMixShader')
    mix_shader.location = (500, 0)

    emission_shader = nodes.new(type='ShaderNodeEmission')
    emission_shader.inputs['Strength'].default_value = 5
    emission_shader.location = (200, -100)

    # Create links within the PaletteMask node group
    links.new(group_input.outputs['ClrPalette'], separate_clr_palette.inputs['Color'])
    links.new(group_input.outputs['NdxClr'], separate_ndx_clr.inputs['Color'])

    links.new(separate_clr_palette.outputs['Red'], less_than_red.inputs[0])  # Corrected output name
    links.new(separate_clr_palette.outputs['Red'], greater_than_red.inputs[0])  # Corrected output name
    links.new(separate_clr_palette.outputs['Green'], less_than_green.inputs[0])  # Corrected output name
    links.new(separate_clr_palette.outputs['Green'], greater_than_green.inputs[0])  # Corrected output name
    links.new(separate_clr_palette.outputs['Blue'], less_than_blue.inputs[0])  # Corrected output name
    links.new(separate_clr_palette.outputs['Blue'], greater_than_blue.inputs[0])  # Corrected output name

    links.new(separate_ndx_clr.outputs['Red'], add_red.inputs[0])  # Corrected output name
    links.new(separate_ndx_clr.outputs['Red'], sub_red.inputs[0])  # Corrected output name
    links.new(separate_ndx_clr.outputs['Green'], add_green.inputs[0])  # Corrected output name
    links.new(separate_ndx_clr.outputs['Green'], sub_green.inputs[0])  # Corrected output name
    links.new(separate_ndx_clr.outputs['Blue'], add_blue.inputs[0])  # Corrected output name
    links.new(separate_ndx_clr.outputs['Blue'], sub_blue.inputs[0])  # Corrected output name

    links.new(add_red.outputs['Value'], less_than_red.inputs[1])
    links.new(sub_red.outputs['Value'], greater_than_red.inputs[1])
    links.new(add_green.outputs['Value'], less_than_green.inputs[1])
    links.new(sub_green.outputs['Value'], greater_than_green.inputs[1])
    links.new(add_blue.outputs['Value'], less_than_blue.inputs[1])
    links.new(sub_blue.outputs['Value'], greater_than_blue.inputs[1])

    links.new(less_than_red.outputs['Value'], multiply_red.inputs[0])
    links.new(greater_than_red.outputs['Value'], multiply_red.inputs[1])
    links.new(less_than_green.outputs['Value'], multiply_green.inputs[0])
    links.new(greater_than_green.outputs['Value'], multiply_green.inputs[1])
    links.new(less_than_blue.outputs['Value'], multiply_blue.inputs[0])
    links.new(greater_than_blue.outputs['Value'], multiply_blue.inputs[1])

    links.new(multiply_red.outputs['Value'], final_multiply.inputs[0])
    links.new(multiply_green.outputs['Value'], final_multiply.inputs[1])
    links.new(final_multiply.outputs['Value'], final_multiply_2.inputs[0])
    links.new(multiply_blue.outputs['Value'], final_multiply_2.inputs[1])

    links.new(final_multiply_2.outputs['Value'], mix_shader.inputs['Fac'])
    links.new(group_input.outputs['Mix'], mix_shader.inputs[1])
    links.new(group_input.outputs['Texture'], emission_shader.inputs['Color'])
    links.new(emission_shader.outputs['Emission'], mix_shader.inputs[2])
    links.new(mix_shader.outputs['Shader'], group_output.inputs['Shader'])

#    print("Created PaletteMask node group")