#TransparentAdditive

import bpy
import os
from .material_utils import add_texture_coordinate_and_mapping_nodes, _add_group_socket, _get_group_io_sockets
from .material_utils import _attach_scene_flag_driver_to_group_input
from .passable_nodegroup import create_node_group_passable

def create_node_group_ud24():
    # Create the node group
    node_group = bpy.data.node_groups.new(name="USERDEFINED_24", type='ShaderNodeTree')
    
    # Add Group Input and Output nodes to the node group
    group_input = node_group.nodes.new('NodeGroupInput')
    group_input.location = (0, 0)
    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (800, 0)
    _add_group_socket(node_group, 'sRGB Texture',       'NodeSocketColor', is_input=True)
    _add_group_socket(node_group, 'PassableDisplay',    'NodeSocketFloat', is_input=True)
    _add_group_socket(node_group, 'Shader',             'NodeSocketShader', is_input=False)

    for item in node_group.interface.items_tree:
        if item.name == "PassableDisplay":
            item.hide_value = True
    
    # Use Principled, but ONLY its Emission channel.
    principled = node_group.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (200, 0)
    principled.inputs['Base Color'].default_value = (0, 0, 0, 1)  # no diffuse
    principled.inputs['Metallic'].default_value = 0.0
    principled.inputs['Specular IOR Level'].default_value = 0.0
    principled.inputs['Roughness'].default_value = 1.0
    principled.inputs['Transmission Weight'].default_value = 0.0
    # drive emission
    principled.inputs['Emission Strength'].default_value = 0.75

    # Attribute node for vertex_normals
    attr_node = node_group.nodes.new("ShaderNodeAttribute")
    attr_node.location = (0, -180)
    attr_node.attribute_name = "vertex_normals"

    if hasattr(attr_node, "attribute_type"):
        try:
            attr_node.attribute_type = 'GEOMETRY'
        except:
            pass
    
    transparent_node = node_group.nodes.new(type='ShaderNodeBsdfTransparent')
    transparent_node.location = (200, 200)
    
    add_shader_node1 = node_group.nodes.new(type='ShaderNodeAddShader')
    add_shader_node1.location = (400, 100)
    
    add_shader_node2 = node_group.nodes.new(type='ShaderNodeAddShader')
    add_shader_node2.location = (600, 0)

    passable_group_tree = create_node_group_passable()
    passable = node_group.nodes.new('ShaderNodeGroup')
    passable.node_tree = passable_group_tree
    passable.location = (-220, 80)

    # Create Mix Shader node
    mix_shader = node_group.nodes.new('ShaderNodeMixShader')
    mix_shader.location = (200, 0)

    # Create links within the node group
    in_sock, out_sock = _get_group_io_sockets(node_group)
    group_links = node_group.links
    group_links.new(in_sock['sRGB Texture'], passable.inputs['Texture'])
    group_links.new(in_sock['PassableDisplay'], passable.inputs['PassableDisplay'])
    group_links.new(passable.outputs['Result'], principled.inputs['Base Color'])
    group_links.new(passable.outputs['Value'],  mix_shader.inputs['Fac'])
    group_links.new(passable.outputs['BSDF'],   mix_shader.inputs[2])
    group_links.new(principled.outputs['BSDF'], add_shader_node1.inputs[1])
    group_links.new(transparent_node.outputs['BSDF'], add_shader_node1.inputs[0])
    group_links.new(add_shader_node1.outputs['Shader'], add_shader_node2.inputs[0])
    group_links.new(principled.outputs['BSDF'], add_shader_node2.inputs[1])
    group_links.new(attr_node.outputs['Vector'], principled.inputs['Normal'])
    group_links.new(add_shader_node2.outputs['Shader'], mix_shader.inputs[1])
    group_links.new(mix_shader.outputs['Shader'], out_sock['Shader'])

    return node_group

def create_material_with_node_group_ud24(material_name, texture_path, node_group):
    # Create a new material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    material.use_backface_culling = True  # Enable backface culling
    material.use_transparency_overlap = False

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear default nodes
    for node in nodes:
        nodes.remove(node)

    # Add the node group to the material
    group_node = nodes.new(type='ShaderNodeGroup')
    group_node.node_tree = node_group
    group_node.location = (0, 0)

    # Attach driver so this material instance reads the scene flag
    _attach_scene_flag_driver_to_group_input(
        group_node,
        input_name='PassableDisplay',
        # choose which you prefer to drive:
        use_id_prop=False  # False → Scene.passable_display_enabled, True → Scene["PassableDisplay"]
    )

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
