import bpy
import os
from material_utils import has_dds_header, add_texture_coordinate_and_mapping_nodes

def add_layered_texture_nodes(material, texture_info, node_group_cache, base_path=None):
    """ 
    Adds layered texture nodes to a material.

    :param material: The material to modify.
    :param texture_info: A dictionary containing texture information, including layering details.
    :param node_group_cache: A cache to store and retrieve existing node groups.
    :param base_path: The base path where texture files are located.
    """
#    print(f"add_layered_texture_nodes called for material: {material.name}")
#    print(f"Texture info: {texture_info}")

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Retrieve the main rendermethod node group (assuming it's named according to the rendermethod)
    main_node_group = None
    for node in nodes:
        if node.type == 'GROUP' and node.node_tree.name in node_group_cache:
            main_node_group = node
            break

    if not main_node_group:
        print(f"No main node group found in material: {material.name}")
        return

    # Calculate positions relative to existing nodes
    x_position = main_node_group.location.x
    y_position = main_node_group.location.y

    # Adjust positions for the Material Output node
    material_output_node = material.node_tree.nodes.get('Material Output')
    if material_output_node:
        material_output_node.location.x += 300  # Move to the right
        material_output_x = (main_node_group.location.x + material_output_node.location.x) / 2
    else:
        print(f"No material output node found for material: {material.name}")
        return

    # Process layered frames
    if 'frames' in texture_info and texture_info['frames']:
        first_frame = texture_info['frames'][0]
        assets_folder = "assets"
        for file_entry in first_frame.get('frame_files', []):
            if file_entry.get('type', '').lower() == 'layer':
                frame_file = file_entry['file']
                layer_file_name = os.path.basename(frame_file)
                layer_name = f"{layer_file_name}_LAYER"

                # Construct full path to the file
                full_path = os.path.join(base_path, assets_folder, frame_file) if base_path else os.path.join(assets_folder, frame_file)
                texture_path = bpy.path.abspath(full_path)

                try:
                    # Attempt to load the image
                    image = bpy.data.images.load(texture_path)
                except Exception as e:
                    print(f"Error loading image file: {texture_path}: {e}")
                    continue

                # Add Image Texture node for the layer
                image_texture_node = nodes.new(type='ShaderNodeTexImage')
                image_texture_node.location = (x_position - 300, y_position - 400)
                image_texture_node.image = image
                image_texture_node.name = layer_name
                image_texture_node.label = layer_name

                # Add Texture Coordinate and Mapping nodes for the new image texture
                tex_coord_node, mapping_node = add_texture_coordinate_and_mapping_nodes(nodes, links, image_texture_node, texture_path)

                # Position the Texture Coordinate and Mapping nodes to align with the Image Texture node
                tex_coord_node.location = (image_texture_node.location.x - 600, image_texture_node.location.y)
                mapping_node.location = (image_texture_node.location.x - 300, image_texture_node.location.y)

                # Ensure the Y axis is flipped for DDS textures
                if has_dds_header(texture_path):
                    mapping_node.inputs['Scale'].default_value[1] = -1

                # Create another rendermethod node group for the layer
                layer_node_group = nodes.new(type='ShaderNodeGroup')
                layer_node_group.node_tree = main_node_group.node_tree
                layer_node_group.location = (image_texture_node.location.x + 300, image_texture_node.location.y)

                # Connect the color output of the Image Texture node to the input of the layer's rendermethod node group
                links.new(image_texture_node.outputs['Color'], layer_node_group.inputs[0])

                # Add a Mix Shader node to blend the main texture and the layer
                mix_shader_node = nodes.new(type='ShaderNodeMixShader')
                mix_shader_node.location = (material_output_x, y_position - 150)

                # Connect main texture node group to the first shader input of Mix Shader
                links.new(main_node_group.outputs[0], mix_shader_node.inputs[1])

                # Connect the layer's node group output to the second shader input of Mix Shader
                links.new(layer_node_group.outputs[0], mix_shader_node.inputs[2])

                # Connect the alpha output of the layer's Image Texture node to the "Fac" input of the Mix Shader
                links.new(image_texture_node.outputs['Alpha'], mix_shader_node.inputs['Fac'])

                # Update the output connection to go through the Mix Shader
                links.new(mix_shader_node.outputs[0], material_output_node.inputs['Surface'])
    #            print(f"Connected mix shader output to material output for {material.name}")

#    print(f"Added layered texture nodes to material: {material.name}")