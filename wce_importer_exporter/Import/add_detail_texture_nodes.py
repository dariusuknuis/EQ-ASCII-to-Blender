import bpy
import os
from material_utils import has_dds_header, add_texture_coordinate_and_mapping_nodes

def add_detail_texture_nodes(material, texture_info, node_group_cache, base_path=None):
    """
    Adds detail texture nodes to a material.
    
    :param material: The material to modify.
    :param texture_info: A dictionary containing texture information, including detail overlay files.
    :param node_group_cache: A cache to store and retrieve existing node groups.
    :param base_path: The base path where texture files are located.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Retrieve the main rendermethod node group (assumed to be stored in node_group_cache)
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

    # Adjust position for the Material Output node
    material_output_node = material.node_tree.nodes.get('Material Output')
    if material_output_node:
        material_output_node.location.x += 300  # Move to the right
        material_output_x = (main_node_group.location.x + material_output_node.location.x) / 2
    else:
        print(f"No material output node found for material: {material.name}")
        return

    # Process detail overlay nodes from the first frame's file entries.
    if 'frames' in texture_info and texture_info['frames']:
        first_frame = texture_info['frames'][0]
        for file_entry in first_frame.get('frame_files', []):
            if file_entry.get('type', '').lower() == 'detail':
                frame_file = file_entry['file']
                detail_value = file_entry.get('detail_value', 1.0)
                detail_file_name = os.path.basename(frame_file)
                detail_name = f"{detail_file_name}_DETAIL"

                # Construct full path to the file
                full_path = os.path.join(base_path, frame_file) if base_path else frame_file
                texture_path = bpy.path.abspath(full_path)

                # Check if the file exists before loading
                if not os.path.isfile(texture_path):
                    print(f"Warning: Detail texture file not found: {texture_path}")
                    continue

                try:
                    # Add Image Texture node for the detail
                    detail_texture_node = nodes.new(type='ShaderNodeTexImage')
                    detail_texture_node.location = (x_position - 300, y_position - 400)
                    detail_texture_node.image = bpy.data.images.load(texture_path)
                    detail_texture_node.name = detail_name
                    detail_texture_node.label = detail_name
                except RuntimeError as e:
                    print(f"Error loading detail texture file: {texture_path}: {e}")
                    continue

                # Add Texture Coordinate and Mapping nodes for the detail texture
                tex_coord_node, mapping_node = add_texture_coordinate_and_mapping_nodes(
                    nodes, links, detail_texture_node, texture_path
                )
                
                # Position the Texture Coordinate and Mapping nodes to align with the Image Texture node
                tex_coord_node.location = (detail_texture_node.location.x - 600, detail_texture_node.location.y)
                mapping_node.location = (detail_texture_node.location.x - 300, detail_texture_node.location.y)

                # Apply detail_value to the Mapping node's scale inputs
                mapping_node.inputs['Scale'].default_value[0] = detail_value  # X scale
                mapping_node.inputs['Scale'].default_value[1] = -detail_value if has_dds_header(texture_path) else detail_value  # Y scale

                # Create another rendermethod node group for the detail texture
                detail_node_group = nodes.new(type='ShaderNodeGroup')
                detail_node_group.node_tree = main_node_group.node_tree
                detail_node_group.location = (detail_texture_node.location.x + 300, detail_texture_node.location.y)

                # Connect the color output of the detail Image Texture node to the input of the detail rendermethod node group
                links.new(detail_texture_node.outputs['Color'], detail_node_group.inputs[0])

                # Add a Mix Shader node to blend the main texture and the detail texture
                mix_shader_node = nodes.new(type='ShaderNodeMixShader')
                mix_shader_node.location = (material_output_x, y_position - 150)
                mix_shader_node.inputs['Fac'].default_value = 0.25  # Set the blending factor to 0.25

                # Connect main texture node group to the first shader input of Mix Shader
                links.new(main_node_group.outputs[0], mix_shader_node.inputs[1])

                # Connect the detail texture's node group output to the second shader input of Mix Shader
                links.new(detail_node_group.outputs[0], mix_shader_node.inputs[2])

                # Update the output connection to go through the Mix Shader
                for link in links:
                    if link.to_node == material.node_tree.nodes.get('Material Output'):
                        links.new(mix_shader_node.outputs[0], link.to_socket)
                        break

#    print(f"Added detail texture nodes to material: {material.name}")