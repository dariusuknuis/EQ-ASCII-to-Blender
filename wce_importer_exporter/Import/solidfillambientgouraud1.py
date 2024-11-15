#"Standard": {
    #"draw_style": "Solid",
    #"lighting": "Ambient",
    #"shading": "Gouraud1",
    #"texture_style": "None"

import bpy

# Function to create the node group SOLIDFILLAMBIENTGOURAUD1
def create_node_group_sfag1():
    node_group = bpy.data.node_groups.new(name="SOLIDFILLAMBIENTGOURAUD1", type='ShaderNodeTree')

    # Create Group Input and Output nodes
    group_input = node_group.nodes.new('NodeGroupInput')
    group_input.location = (-400, 0)

    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (400, 0)

    # Add an output socket of type Shader (instead of the default)
    node_group.outputs.new('NodeSocketShader', 'Shader')

    # Create Emission and Diffuse BSDF nodes
    emission = node_group.nodes.new('ShaderNodeEmission')
    emission.location = (0, -100)

    diffuse = node_group.nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.location = (0, -300)
    diffuse.inputs['Roughness'].default_value = 0.0  # Set roughness to 0 as per the image

    # Create Mix Shader node
    mix_shader = node_group.nodes.new('ShaderNodeMixShader')
    mix_shader.location = (200, 0)

    # Add inputs to the group
    node_group.inputs.new('NodeSocketFloat', 'ScaledAmbient')
    node_group.inputs.new('NodeSocketFloat', 'Brightness')
    node_group.inputs.new('NodeSocketColor', 'Color')

    # Set default values
    group_input.outputs['ScaledAmbient'].default_value = 0.0
    group_input.outputs['Brightness'].default_value = 0.0

    # Link the nodes within the group
    node_group.links.new(group_input.outputs['ScaledAmbient'], mix_shader.inputs['Fac'])
    node_group.links.new(group_input.outputs['Brightness'], emission.inputs['Strength'])
    node_group.links.new(group_input.outputs['Color'], emission.inputs['Color'])
    node_group.links.new(group_input.outputs['Color'], diffuse.inputs['Color'])

    node_group.links.new(emission.outputs['Emission'], mix_shader.inputs[1])  # Link Emission to Mix Shader
    node_group.links.new(diffuse.outputs['BSDF'], mix_shader.inputs[2])  # Link Diffuse to Mix Shader

    node_group.links.new(mix_shader.outputs['Shader'], group_output.inputs['Shader'])  # Connect to output

    return node_group


# Function to create a material and apply the SOLIDFILLAMBIENTGOURAUD1 node group
def create_material_with_node_group_sfag1(material_name, material_data, node_group):
    # Create a new material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear default nodes
    for node in nodes:
        nodes.remove(node)

    # Add the SOLIDFILLAMBIENTGOURAUD1 node group
    group_node = nodes.new(type='ShaderNodeGroup')
    group_node.node_tree = node_group
    group_node.location = (0, 0)

    # Add RGBPen input, Brightness, and ScaledAmbient nodes
    rgb_pen_node = nodes.new(type='ShaderNodeRGB')
    rgb_pen_node.name = "RGBPEN"
    rgb_pen_node.location = (-400, -200)
    rgb_pen_node.outputs['Color'].default_value = material_data['rgbpen']  # Use RGBPEN from material data

    brightness_node = nodes.new(type='ShaderNodeValue')
    brightness_node.label = "BRIGHTNESS"
    brightness_node.location = (-400, -100)
    brightness_node.outputs['Value'].default_value = material_data['brightness']  # Use BRIGHTNESS from material data

    scaled_ambient_node = nodes.new(type='ShaderNodeValue')
    scaled_ambient_node.label = "SCALEDAMBIENT"
    scaled_ambient_node.location = (-400, 0)
    scaled_ambient_node.outputs['Value'].default_value = material_data['scaledambient']  # Use SCALEDAMBIENT from material data

    # Add Material Output node
    material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
    material_output_node.location = (300, 0)

    # Create the links
    links.new(rgb_pen_node.outputs['Color'], group_node.inputs['Color'])
    links.new(brightness_node.outputs['Value'], group_node.inputs['Brightness'])
    links.new(scaled_ambient_node.outputs['Value'], group_node.inputs['ScaledAmbient'])

    links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])

    return material