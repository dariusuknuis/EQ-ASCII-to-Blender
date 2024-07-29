import bpy

def create_node_group_ud12():
    # Create the node group
    node_group = bpy.data.node_groups.new(name="USERDEFINED 12", type='ShaderNodeTree')
    
    # Add Group Input and Output nodes to the node group
    group_input = node_group.nodes.new('NodeGroupInput')
    group_input.location = (0, 0)
    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (800, 0)
    node_group.inputs.new('NodeSocketColor', 'sRGB Texture')
    node_group.outputs.new('NodeSocketShader', 'Shader')

    # Create the internal nodes
    emission_node = node_group.nodes.new(type='ShaderNodeEmission')
    emission_node.location = (200, 0)
    emission_node.inputs['Strength'].default_value = 0.75
    
    transparent_node = node_group.nodes.new(type='ShaderNodeBsdfTransparent')
    transparent_node.location = (200, 200)
    
    add_shader_node1 = node_group.nodes.new(type='ShaderNodeAddShader')
    add_shader_node1.location = (400, 100)
    
    add_shader_node2 = node_group.nodes.new(type='ShaderNodeAddShader')
    add_shader_node2.location = (600, 0)

    # Create links within the node group
    group_links = node_group.links
    group_links.new(group_input.outputs['sRGB Texture'], emission_node.inputs['Color'])
    group_links.new(emission_node.outputs['Emission'], add_shader_node1.inputs[1])
    group_links.new(transparent_node.outputs['BSDF'], add_shader_node1.inputs[0])
    group_links.new(add_shader_node1.outputs['Shader'], add_shader_node2.inputs[0])
    group_links.new(emission_node.outputs['Emission'], add_shader_node2.inputs[1])
    group_links.new(add_shader_node2.outputs['Shader'], group_output.inputs['Shader'])

    return node_group

def create_material_with_node_group_ud12(material_name, texture_path, node_group):
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

    # Add a Material Output node
    material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
    material_output_node.location = (300, 0)

    # Create links outside the group
    links.new(image_texture_node.outputs['Color'], group_node.inputs['sRGB Texture'])
    links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])

    return material