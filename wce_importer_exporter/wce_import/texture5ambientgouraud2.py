#"Standard": {
    #"draw_style": "Solid",
    #"lighting": "Ambient",
    #"shading": "Gouraud2",
    #"texture_style": "Texture5"

import bpy
import os
from .material_utils import add_texture_coordinate_and_mapping_nodes, _add_group_socket, _get_group_io_sockets

def create_node_group_t5ag2():
    # Create the node group
    node_group = bpy.data.node_groups.new(name="TEXTURE5AMBIENTGOURAUD2", type='ShaderNodeTree')
    
    # Add Group Input and Output nodes to the node group
    group_input = node_group.nodes.new('NodeGroupInput')
    group_input.location = (0, 0)
    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (400, 0)
    _add_group_socket(node_group, 'sRGB Texture', 'NodeSocketColor', is_input=True)
    _add_group_socket(node_group, 'Shader',       'NodeSocketShader', is_input=False)

    # Create a Diffuse BSDF node inside the node group
    diffuse_node = node_group.nodes.new(type='ShaderNodeBsdfDiffuse')
    diffuse_node.location = (200, 0)

    # Attribute node for vertex_normals
    attr_node = node_group.nodes.new("ShaderNodeAttribute")
    attr_node.location = (0, -180)
    attr_node.attribute_name = "vertex_normals"

    if hasattr(attr_node, "attribute_type"):
        try:
            attr_node.attribute_type = 'GEOMETRY'
        except:
            pass

    # Create links within the node group
    in_sock, out_sock = _get_group_io_sockets(node_group)
    group_links = node_group.links
    group_links.new(in_sock['sRGB Texture'], diffuse_node.inputs['Color'])
    group_links.new(attr_node.outputs['Vector'], diffuse_node.inputs['Normal'])
    group_links.new(diffuse_node.outputs['BSDF'], out_sock['Shader'])

    return node_group

def create_material_with_node_group_t5ag2(material_name, texture_path, node_group):
    # Create a new material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
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
    try:
        image_texture_node.image = bpy.data.images.load(texture_path)
    except RuntimeError:
        image_texture_node.image = None
    image_texture_node.interpolation = 'Linear'
    if image_texture_node.image:
        try:
            image_texture_node.image.colorspace_settings.name = 'sRGB'
        except Exception:
            pass
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