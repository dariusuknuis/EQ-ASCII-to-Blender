# TransparentMaskedPassable

import bpy
import struct
import os
from .material_utils import has_dds_header, add_texture_coordinate_and_mapping_nodes, _add_group_socket, _get_group_io_sockets
from .material_utils import _attach_scene_flag_driver_to_group_input
from .passable_nodegroup import create_node_group_passable

def read_bmp_palette_color(file_path):
    with open(file_path, 'rb') as f:
        f.seek(54)  # BMP header is 54 bytes
        palette_data = f.read(4)  # Read the first color in the palette (4 bytes: BGRX)
        blue, green, red, _ = struct.unpack('BBBB', palette_data)
        return red / 255.0, green / 255.0, blue / 255.0

def create_node_group_ud08(image_texture_file):
    """
    Creates a node group based on the texture type: DXT5 DDS or Indexed Color BMP.
    
    :param texture_path: Path to the texture file.
    :return: The node group created.
    """
    if has_dds_header(image_texture_file):
        node_group_name = "USERDEFINED_8(DXT5DDS)"
    else:
        node_group_name = "USERDEFINED_8(NDXCLRBMP)"
    
    # Check if the node group already exists
    if node_group_name in bpy.data.node_groups:
        print(f"Using existing node group: {node_group_name}")
        return bpy.data.node_groups[node_group_name]

    # Create the node group based on the texture type
    if has_dds_header(image_texture_file):
        # Create the node group for DXT5 DDS
        node_group = bpy.data.node_groups.new(name=node_group_name, type='ShaderNodeTree')

        # Add Group Input and Output nodes to the node group
        group_input = node_group.nodes.new('NodeGroupInput')
        group_input.location = (-400, 0)
        group_output = node_group.nodes.new('NodeGroupOutput')
        group_output.location = (400, 0)
        _add_group_socket(node_group, 'Color',              'NodeSocketColor', is_input=True)
        _add_group_socket(node_group, 'Alpha',              'NodeSocketFloat', is_input=True)
        _add_group_socket(node_group, 'PassableDisplay',    'NodeSocketFloat', is_input=True)
        _add_group_socket(node_group, 'Shader',             'NodeSocketShader', is_input=False)

        for item in node_group.interface.items_tree:
            if item.name == "PassableDisplay":
                item.hide_value = True

        # Create Principled BSDF node
        principled_bsdf_node = node_group.nodes.new(type='ShaderNodeBsdfPrincipled')
        principled_bsdf_node.location = (0, 0)
        principled_bsdf_node.inputs['Emission Strength'].default_value = 0
        principled_bsdf_node.inputs['Subsurface Scale'].default_value = 0
        principled_bsdf_node.inputs['Specular IOR Level'].default_value = 0
        principled_bsdf_node.inputs['Metallic'].default_value = 0
        principled_bsdf_node.inputs['Roughness'].default_value = 0
        principled_bsdf_node.inputs['Sheen Roughness'].default_value = 0
        principled_bsdf_node.inputs['Coat IOR'].default_value = 0

        # Attribute node for vertex_normals
        attr_node = node_group.nodes.new("ShaderNodeAttribute")
        attr_node.location = (0, -180)
        attr_node.attribute_name = "vertex_normals"

        if hasattr(attr_node, "attribute_type"):
            try:
                attr_node.attribute_type = 'GEOMETRY'
            except:
                pass

        passable_group_tree = create_node_group_passable()
        passable = node_group.nodes.new('ShaderNodeGroup')
        passable.node_tree = passable_group_tree
        passable.location = (-220, 80)

        mix_shader = node_group.nodes.new('ShaderNodeMixShader'); mix_shader.location = (240, 110)

        # Connect inputs to Principled BSDF
        in_sock, out_sock = _get_group_io_sockets(node_group)
        group_links = node_group.links
        group_links.new(in_sock['Color'], passable.inputs['Texture'])
        group_links.new(in_sock['Alpha'], principled_bsdf_node.inputs['Alpha'])
        group_links.new(in_sock['PassableDisplay'], passable.inputs['PassableDisplay'])
        group_links.new(passable.outputs['Result'], principled_bsdf_node.inputs['Base Color'])
        group_links.new(passable.outputs['Value'],  mix_shader.inputs['Fac'])
        group_links.new(passable.outputs['BSDF'],   mix_shader.inputs[2])
        group_links.new(attr_node.outputs['Vector'], principled_bsdf_node.inputs['Normal'])
        group_links.new(principled_bsdf_node.outputs['BSDF'], mix_shader.inputs[1])
        group_links.new(mix_shader.outputs['Shader'], out_sock['Shader'])
    
    else:
        # Create the node group for Indexed Color BMP
        node_group = bpy.data.node_groups.new(name=node_group_name, type='ShaderNodeTree')
        
        # Add Group Input and Output nodes to the node group
        group_input = node_group.nodes.new('NodeGroupInput')
        group_input.location = (-800, 0)
        group_output = node_group.nodes.new('NodeGroupOutput')
        group_output.location = (800, 0)
        _add_group_socket(node_group, 'Index 0 Color',      'NodeSocketColor', is_input=True)
        _add_group_socket(node_group, 'Non-Color Texture',  'NodeSocketColor', is_input=True)
        _add_group_socket(node_group, 'sRGB Texture',       'NodeSocketColor', is_input=True)
        _add_group_socket(node_group, 'PassableDisplay',    'NodeSocketFloat', is_input=True)
        _add_group_socket(node_group, 'Shader',             'NodeSocketShader', is_input=False)

        for item in node_group.interface.items_tree:
            if item.name == "PassableDisplay":
                item.hide_value = True

        # Create nodes in the node group
        math_node1 = node_group.nodes.new(type='ShaderNodeMath')
        math_node1.operation = 'SUBTRACT'
        math_node1.location = (-400, 400)

        math_node2 = node_group.nodes.new(type='ShaderNodeMath')
        math_node2.operation = 'SUBTRACT'
        math_node2.location = (-400, 200)

        math_node3 = node_group.nodes.new(type='ShaderNodeMath')
        math_node3.operation = 'SUBTRACT'
        math_node3.location = (-400, 0)

        separate_color_node1 = node_group.nodes.new(type='ShaderNodeSeparateColor')
        separate_color_node1.location = (-600, 300)
    
        separate_color_node2 = node_group.nodes.new(type='ShaderNodeSeparateColor')
        separate_color_node2.location = (-600, 100)

        transparent_bsdf_node = node_group.nodes.new(type='ShaderNodeBsdfTransparent')
        transparent_bsdf_node.location = (200, -200)

        abs_node1 = node_group.nodes.new(type='ShaderNodeMath')
        abs_node1.operation = 'ABSOLUTE'
        abs_node1.location = (-200, 400)

        abs_node2 = node_group.nodes.new(type='ShaderNodeMath')
        abs_node2.operation = 'ABSOLUTE'
        abs_node2.location = (-200, 200)

        abs_node3 = node_group.nodes.new(type='ShaderNodeMath')
        abs_node3.operation = 'ABSOLUTE'
        abs_node3.location = (-200, 0)

        diffuse_bsdf_node = node_group.nodes.new(type='ShaderNodeBsdfDiffuse')
        diffuse_bsdf_node.location = (-200, -200)

        # Attribute node for vertex_normals
        attr_node = node_group.nodes.new("ShaderNodeAttribute")
        attr_node.location = (-400, -380)
        attr_node.attribute_name = "vertex_normals"

        if hasattr(attr_node, "attribute_type"):
            try:
                attr_node.attribute_type = 'GEOMETRY'
            except:
                pass

        add_node1 = node_group.nodes.new(type='ShaderNodeMath')
        add_node1.operation = 'ADD'
        add_node1.location = (0, 400)

        add_node2 = node_group.nodes.new(type='ShaderNodeMath')
        add_node2.operation = 'ADD'
        add_node2.location = (200, 300)

        less_than_node = node_group.nodes.new(type='ShaderNodeMath')
        less_than_node.operation = 'LESS_THAN'
        less_than_node.location = (400, 200)
        less_than_node.inputs[1].default_value = 1.5e-05  # Threshold value

        mix_shader1 = node_group.nodes.new(type='ShaderNodeMixShader')
        mix_shader1.location = (600, 100)

        passable_group_tree = create_node_group_passable()
        passable = node_group.nodes.new('ShaderNodeGroup')
        passable.node_tree = passable_group_tree
        passable.location = (-220, 80)

        mix_shader2 = node_group.nodes.new('ShaderNodeMixShader'); mix_shader2.location = (240, 110)

        # Create links within the node group
        in_sock, out_sock = _get_group_io_sockets(node_group)
        group_links = node_group.links
        group_links.new(separate_color_node1.outputs['Red'], math_node1.inputs[1])
        group_links.new(separate_color_node1.outputs['Green'], math_node2.inputs[1])
        group_links.new(separate_color_node1.outputs['Blue'], math_node3.inputs[1])
        group_links.new(separate_color_node2.outputs['Red'], math_node1.inputs[0])
        group_links.new(separate_color_node2.outputs['Green'], math_node2.inputs[0])
        group_links.new(separate_color_node2.outputs['Blue'], math_node3.inputs[0])
        group_links.new(in_sock['Non-Color Texture'], separate_color_node2.inputs['Color'])
        group_links.new(in_sock['sRGB Texture'], passable.inputs['Texture'])
        group_links.new(in_sock['Index 0 Color'], separate_color_node1.inputs['Color'])
        group_links.new(in_sock['PassableDisplay'], passable.inputs['PassableDisplay'])

        group_links.new(passable.outputs['Result'], diffuse_bsdf_node.inputs['Color'])
        group_links.new(passable.outputs['Value'],  mix_shader2.inputs['Fac'])
        group_links.new(passable.outputs['BSDF'],   mix_shader2.inputs[2])

        group_links.new(math_node1.outputs['Value'], abs_node1.inputs[0])
        group_links.new(math_node2.outputs['Value'], abs_node2.inputs[0])
        group_links.new(math_node3.outputs['Value'], abs_node3.inputs[0])
        group_links.new(abs_node1.outputs['Value'], add_node1.inputs[0])
        group_links.new(abs_node2.outputs['Value'], add_node1.inputs[1])
        group_links.new(abs_node3.outputs['Value'], add_node2.inputs[1])
        group_links.new(add_node1.outputs['Value'], add_node2.inputs[0])
        group_links.new(add_node2.outputs['Value'], less_than_node.inputs[0])
        group_links.new(less_than_node.outputs['Value'], mix_shader1.inputs['Fac'])
        group_links.new(diffuse_bsdf_node.outputs['BSDF'], mix_shader1.inputs[1])
        group_links.new(transparent_bsdf_node.outputs['BSDF'], mix_shader1.inputs[2])
        group_links.new(attr_node.outputs['Vector'],  diffuse_bsdf_node.inputs['Normal'])
        group_links.new(mix_shader1.outputs['Shader'], mix_shader2.inputs[1])
        group_links.new(mix_shader2.outputs['Shader'], out_sock['Shader'])

    return node_group

def create_material_with_node_group_ud08(material_name, image_texture_file, node_group):
    # Determine the texture type
    if has_dds_header(image_texture_file):
        # Create a new material for DXT5 DDS
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
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
            image_texture_node.image = bpy.data.images.load(image_texture_file)
        except RuntimeError:
            image_texture_node.image = None
        image_texture_node.interpolation = 'Linear'
        image_texture_node.name = f"{os.path.basename(image_texture_file)}"
        image_texture_node.label = f"{os.path.basename(image_texture_file)}"
        
        # Connect Image Texture outputs to Group inputs
        links.new(image_texture_node.outputs['Color'], group_node.inputs['Color'])
        links.new(image_texture_node.outputs['Alpha'], group_node.inputs['Alpha'])
        
        # Add nodes to flip dds files
        add_texture_coordinate_and_mapping_nodes(nodes, links, image_texture_node, image_texture_file)
        
        # Add a Material Output node
        material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
        material_output_node.location = (300, 0)
        
        # Connect the Group output to the Material Output
        links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])
    
    else:
        # Create a new material for Indexed Color BMP
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        material.blend_method = 'CLIP'  # Set blend mode to Alpha Clip
        material.use_transparency_overlap = False
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Clear default nodes
        for node in nodes:
            nodes.remove(node)
        
        # Read the first color from the BMP palette
        first_palette_color = read_bmp_palette_color(image_texture_file)
        red_value = float(first_palette_color[0])
        green_value = float(first_palette_color[1])
        blue_value = float(first_palette_color[2])

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

        # Add other nodes outside the group

        image_texture_node1 = nodes.new(type='ShaderNodeTexImage')
        image_texture_node1.location = (-300, -400)
        try:
            image_texture_node1.image = bpy.data.images.load(image_texture_file)
        except RuntimeError:
            image_texture_node1.image = None
        image_texture_node1.name = f"{os.path.basename(image_texture_file)}"
        image_texture_node1.label = f"{os.path.basename(image_texture_file)}"

        image_texture_node2 = nodes.new(type='ShaderNodeTexImage')
        image_texture_node2.location = (-300, -50)
        try:
            image_texture_node2.image = bpy.data.images.load(image_texture_file)
        except RuntimeError:
            image_texture_node2.image = None
        image_texture_node2.interpolation = 'Closest'
        if image_texture_node2.image:
            try:
                image_texture_node2.image.colorspace_settings.name = 'Non-Color'
            except Exception:
                pass
        image_texture_node2.name = f"{os.path.basename(image_texture_file)}_NC"
        image_texture_node2.label = f"{os.path.basename(image_texture_file)}_NC"

        rgb_node = nodes.new(type='ShaderNodeRGB')
        rgb_node.location = (-300, 200)
        rgb_node.outputs[0].default_value = (red_value, green_value, blue_value, 1.0)

        # Add nodes to flip dds files
        add_texture_coordinate_and_mapping_nodes(nodes, links, image_texture_node1, image_texture_file)
        add_texture_coordinate_and_mapping_nodes(nodes, links, image_texture_node2, image_texture_file)

        material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
        material_output_node.location = (300, 0)

        # Create links outside the group
        links.new(image_texture_node2.outputs['Color'], group_node.inputs['Non-Color Texture'])
        links.new(image_texture_node1.outputs['Color'], group_node.inputs['sRGB Texture'])
        links.new(rgb_node.outputs[0], group_node.inputs['Index 0 Color'])
        links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])

    return material
