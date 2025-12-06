#"Standard": {
    #"draw_style": "Solid",
    #"lighting": "Ambient",
    #"shading": "Gouraud1",
    #"texture_style": "None"

import bpy
from .material_utils import _add_group_socket, _get_group_io_sockets
from .material_utils import _attach_scene_flag_driver_to_group_input
from .passable_nodegroup import create_node_group_passable

# Function to create the node group SOLIDFILLAMBIENTGOURAUD1
def create_node_group_sfag1():
    node_group = bpy.data.node_groups.new(name="SOLIDFILLAMBIENTGOURAUD1", type='ShaderNodeTree')

    # Create Group Input and Output nodes
    group_input = node_group.nodes.new('NodeGroupInput')
    group_input.location = (-400, 0)

    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (400, 0)

    # Add an output socket of type Shader (instead of the default)
    _add_group_socket(node_group, 'PassableDisplay',    'NodeSocketFloat', is_input=True)
    _add_group_socket(node_group, 'Shader',             'NodeSocketShader', is_input=False)

    for item in node_group.interface.items_tree:
        if item.name == "PassableDisplay":
            item.hide_value = True

    # Create Emission and Diffuse BSDF nodes
    emission = node_group.nodes.new('ShaderNodeEmission')
    emission.location = (0, -100)

    diffuse = node_group.nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.location = (0, -300)
    diffuse.inputs['Roughness'].default_value = 0.0  # Set roughness to 0 as per the image

    # Attribute node for vertex_normals
    attr_node = node_group.nodes.new("ShaderNodeAttribute")
    attr_node.location = (-200, -480)
    attr_node.attribute_name = "vertex_normals"

    if hasattr(attr_node, "attribute_type"):
        try:
            attr_node.attribute_type = 'GEOMETRY'
        except:
            pass

    # Create Mix Shader node
    mix_shader1 = node_group.nodes.new('ShaderNodeMixShader')
    mix_shader1.location = (200, 0)

    # Add inputs to the group
    _add_group_socket(node_group, 'ScaledAmbient', 'NodeSocketFloat', is_input=True)
    _add_group_socket(node_group, 'Brightness', 'NodeSocketFloat', is_input=True)
    _add_group_socket(node_group, 'Color', 'NodeSocketColor', is_input=True)

    passable_group_tree = create_node_group_passable()
    passable = node_group.nodes.new('ShaderNodeGroup')
    passable.node_tree = passable_group_tree
    passable.location = (-220, 80)

    mix_shader2 = node_group.nodes.new('ShaderNodeMixShader'); mix_shader2.location = (240, 110)

    # Link the nodes within the group
    in_sock, out_sock = _get_group_io_sockets(node_group)
    group_links = node_group.links

    group_links.new(in_sock['ScaledAmbient'], mix_shader1.inputs['Fac'])
    group_links.new(in_sock['Brightness'], emission.inputs['Strength'])
    group_links.new(in_sock['Color'], passable.inputs['Texture'])
    group_links.new(in_sock['PassableDisplay'], passable.inputs['PassableDisplay'])

    group_links.new(passable.outputs['Result'], emission.inputs['Color'])
    group_links.new(passable.outputs['Result'], diffuse.inputs['Color'])
    group_links.new(passable.outputs['Value'],  mix_shader2.inputs['Fac'])
    group_links.new(passable.outputs['BSDF'],   mix_shader2.inputs[2])

    group_links.new(emission.outputs['Emission'], mix_shader1.inputs[1])  # Link Emission to Mix Shader
    
    group_links.new(diffuse.outputs['BSDF'], mix_shader1.inputs[2])  # Link Diffuse to Mix Shader

    group_links.new(mix_shader1.outputs['Shader'], mix_shader2.inputs[1])

    # Set default values
    in_sock['ScaledAmbient'].default_value = 0.0
    in_sock['Brightness'].default_value = 0.0

    group_links.new(attr_node.outputs['Vector'], diffuse.inputs['Normal'])
    group_links.new(mix_shader2.outputs['Shader'], out_sock['Shader'])  # Connect to output

    return node_group


# Function to create a material and apply the SOLIDFILLAMBIENTGOURAUD1 node group
def create_material_with_node_group_sfag1(material_name, material_data, node_group):
    # Create a new material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    material.use_transparency_overlap = False
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear default nodes
    for node in nodes:
        nodes.remove(node)

    # Add the SOLIDFILLAMBIENTGOURAUD1 node group
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