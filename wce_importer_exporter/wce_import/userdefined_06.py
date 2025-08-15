#Transparent50

import bpy
import os
from .material_utils import add_texture_coordinate_and_mapping_nodes

def create_node_group_ud06():
    # Create the node group
    node_group = bpy.data.node_groups.new(name="USERDEFINED_6", type='ShaderNodeTree')
    
    # Add Group Input and Output nodes to the node group
    group_input = node_group.nodes.new('NodeGroupInput')
    group_input.location = (0, 0)
    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (600, 0)
    node_group.inputs.new('NodeSocketColor', 'sRGB Texture')
    node_group.outputs.new('NodeSocketShader', 'Shader')
    
    # Create a Principled BSDF node inside the node group
    principled_node = node_group.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_node.location = (300, 0)
    principled_node.inputs['Specular'].default_value = 0.0
    principled_node.inputs['Alpha'].default_value = 0.50

    # Create links within the node group
    group_links = node_group.links
    group_links.new(group_input.outputs['sRGB Texture'], principled_node.inputs['Base Color'])
    group_links.new(principled_node.outputs['BSDF'], group_output.inputs['Shader'])

    return node_group

def create_material_with_node_group_ud06(material_name, texture_path, node_group):
    # Create a new material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    material.blend_method = 'BLEND'  # Set blend mode to Alpha Blend
    material.use_backface_culling = True  # Enable backface culling

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear default nodes
    for node in nodes:
        nodes.remove(node)

    # Add the node group to the material
    group_node = nodes.new(type='ShaderNodeGroup')
    group_node.node_tree = node_group
    group_node.location = (0, 0)

    # Add an Image Texture node
    image_texture_node = nodes.new(type='ShaderNodeTexImage')
    image_texture_node.location = (-300, 0)
    image_texture_node.image = bpy.data.images.load(texture_path)
    image_texture_node.interpolation = 'Linear'
    image_texture_node.image.colorspace_settings.name = 'sRGB'
    image_texture_node.name = f"{os.path.basename(texture_path)}"
    image_texture_node.label = f"{os.path.basename(texture_path)}"

   # Add nodes to flip dds files
    add_texture_coordinate_and_mapping_nodes(nodes, links, image_texture_node, texture_path)

    # Create the necessary links
    links.new(image_texture_node.outputs['Color'], group_node.inputs['sRGB Texture'])

    # Add a Material Output node
    material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
    material_output_node.location = (300, 0)

    # Create the final link
    links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])

    return material
