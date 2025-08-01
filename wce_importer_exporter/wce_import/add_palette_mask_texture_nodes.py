import bpy
import os

def add_palette_mask_texture_nodes(material, texture_info, node_group_cache, base_path=None):
    """
    Adds palette mask texture nodes to a material.

    :param material: The material to modify.
    :param texture_info: A dictionary containing texture information, including palette mask frames.
    :param node_group_cache: A cache to store and retrieve existing node groups.
    :param base_path: The base path where texture files are located.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Create or get the Blur node group
    blur_node_group_name = "Blur"
    if blur_node_group_name not in bpy.data.node_groups:
        blur_node_group = bpy.data.node_groups.new(name=blur_node_group_name, type='ShaderNodeTree')
        create_blur_node_group(blur_node_group)
    else:
        blur_node_group = bpy.data.node_groups[blur_node_group_name]

    blur_node = nodes.new(type='ShaderNodeGroup')
    blur_node.node_tree = blur_node_group
    blur_node.location = (-1600, -1200)

    # Process palette mask frames
    if 'frames' in texture_info and texture_info['frames']:
        first_frame = texture_info['frames'][0]
        assets_folder = "assets"
        for file_entry in first_frame.get('frame_files', []):
            if file_entry.get('type', '').lower() == 'palette_mask':
                frame_file = file_entry['file']

                # Construct full path to the file
                full_path = os.path.join(base_path, assets_folder, frame_file) if base_path else os.path.join(assets_folder, frame_file)
                texture_path = bpy.path.abspath(full_path)

                # Check if the file exists before loading
                if not os.path.isfile(texture_path):
                    print(f"Warning: Palette mask texture file not found: {texture_path}")
                    continue

                try:
                    # Add Image Texture node for the palette mask
                    palette_mask_texture_node = nodes.new(type='ShaderNodeTexImage')
                    palette_mask_texture_node.location = (-1400, -1200)
                    palette_mask_texture_node.interpolation = 'Closest'
                    palette_mask_texture_node.image = bpy.data.images.load(texture_path)
                    palette_mask_texture_node.image.colorspace_settings.name = 'Non-Color'
                    palette_mask_texture_node.name = f"{os.path.basename(texture_path)}"
                    palette_mask_texture_node.label = f"{os.path.basename(texture_path)}"

                    # Connect the Blur node group to the palette mask texture
                    links.new(blur_node.outputs[0], palette_mask_texture_node.inputs['Vector'])

                except RuntimeError as e:
                    print(f"Error loading palette mask texture file: {texture_path}: {e}")
                    continue

                # Store the palette mask node for future use in tiled textures
                texture_info['palette_mask_node'] = palette_mask_texture_node
    #            print(f"Added palette mask texture node to material: {material.name}")

def create_blur_node_group(blur_node_group):
    """
    Creates the Blur node group used for palette mask textures.

    :param blur_node_group: The node group to be populated.
    """
    nodes = blur_node_group.nodes
    links = blur_node_group.links

    # Add nodes inside the Blur node group
    group_output = nodes.new('NodeGroupOutput')
    group_output.location = (400, 0)
    blur_node_group.outputs.new('NodeSocketVector', 'Vector')

    tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
    tex_coord_node.location = (-600, 0)

    add_vector_node = nodes.new(type='ShaderNodeVectorMath')
    add_vector_node.operation = 'ADD'
    add_vector_node.location = (0, 0)

    noise_texture_node = nodes.new(type='ShaderNodeTexWhiteNoise')
    noise_texture_node.location = (-400, -100)

    map_range_node = nodes.new(type='ShaderNodeMapRange')
    map_range_node.data_type = 'FLOAT_VECTOR'  # Updated data type to 'FLOAT_VECTOR'
    map_range_node.location = (-200, -100)

    value_node = nodes.new(type='ShaderNodeValue')
    value_node.location = (-800, -500)
    value_node.outputs[0].default_value = 0.005

    multiply_node = nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'
    multiply_node.location = (-600, -300)
    multiply_node.inputs[1].default_value = -1

    # Create links within the Blur node group

    # Connect TexCoord and Noise Texture
    links.new(tex_coord_node.outputs['UV'], add_vector_node.inputs[0])
    links.new(tex_coord_node.outputs['UV'], noise_texture_node.inputs['Vector'])
    links.new(noise_texture_node.outputs['Color'], map_range_node.inputs['Vector'])  

    # Correctly get the 'From Max' and 'From Min' sockets for the vector type
    to_max_vector_input = next(s for s in map_range_node.inputs if s.name == 'To Max' and s.type == 'VECTOR')
    to_min_vector_input = next(s for s in map_range_node.inputs if s.name == 'To Min' and s.type == 'VECTOR')

    # Link Value node and Multiply node to Map Range node using the correct vector inputs
    links.new(value_node.outputs[0], to_max_vector_input)
    links.new(value_node.outputs[0], multiply_node.inputs[0])
    links.new(multiply_node.outputs[0], to_min_vector_input)

    # Continue with the rest of the connections
    links.new(map_range_node.outputs['Vector'], add_vector_node.inputs[1])  
    links.new(add_vector_node.outputs['Vector'], group_output.inputs['Vector'])

#    print("Created Blur node group")