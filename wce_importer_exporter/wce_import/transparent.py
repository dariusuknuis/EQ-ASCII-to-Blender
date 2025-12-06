import bpy
from .material_utils import _add_group_socket, _get_group_io_sockets
from .material_utils import _attach_scene_flag_driver_to_group_input
from .passable_nodegroup import create_node_group_passable

def create_node_group_transparent():
    # Check if the node group already exists, and return it if it does
    if "TRANSPARENT" in bpy.data.node_groups:
        return bpy.data.node_groups["TRANSPARENT"]
    
    # Create the node group if it doesn't already exist
    node_group = bpy.data.node_groups.new(name="TRANSPARENT", type='ShaderNodeTree')
    
    # Add Group Output node to the node group
    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (600, 0)
    _add_group_socket(node_group, 'PassableDisplay', 'NodeSocketFloat', is_input=True)
    _add_group_socket(node_group, 'Shader',          'NodeSocketShader', is_input=False)

    for item in node_group.interface.items_tree:
        if item.name == "PassableDisplay":
            item.hide_value = True

    # Create nodes inside the node group
    # Add a Principled BSDF node
    principled_bsdf_node = node_group.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_bsdf_node.location = (300, 0)
    principled_bsdf_node.inputs['Specular IOR Level'].default_value = 0.0
    principled_bsdf_node.inputs['Roughness'].default_value = 0.6  # Slight roughness for frosted effect
    principled_bsdf_node.inputs['Transmission Weight'].default_value = 1.0  # Full transmission for glass effect
    principled_bsdf_node.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 0.05)  # Subtle white color with slight transparency
    principled_bsdf_node.inputs['Alpha'].default_value = 0.3  # Set alpha under Emission to 0.3

    # Attribute node for vertex_normals
    attr_node = node_group.nodes.new("ShaderNodeAttribute")
    attr_node.location = (100, -180)
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

    # Create links within the node group
    in_sock, out_sock = _get_group_io_sockets(node_group)
    group_links = node_group.links
    group_links.new(in_sock['PassableDisplay'], passable.inputs['PassableDisplay'])
    group_links.new(passable.outputs['Result'], principled_bsdf_node.inputs['Base Color'])
    group_links.new(passable.outputs['Value'],  mix_shader.inputs['Fac'])
    group_links.new(passable.outputs['BSDF'],   mix_shader.inputs[2])
    group_links.new(attr_node.outputs['Vector'], principled_bsdf_node.inputs['Normal'])
    group_links.new(principled_bsdf_node.outputs['BSDF'], mix_shader.inputs[1])
    group_links.new(mix_shader.outputs['Shader'], out_sock['Shader'])

    return node_group

def create_material_with_node_group_transparent(material_name, node_group):
    # Check if the material already exists, and return it if it does
    if material_name in bpy.data.materials:
        return bpy.data.materials[material_name]
    
    # Ensure the node group is created or retrieved
    node_group = create_node_group_transparent()

    # Create a new material
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

    # Add a Material Output node
    material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
    material_output_node.location = (600, 0)

    # Create links outside the group
    links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])

    return material
