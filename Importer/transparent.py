import bpy

def create_node_group_transparent():
    # Create the node group
    node_group = bpy.data.node_groups.new(name="TRANSPARENT", type='ShaderNodeTree')
    
    # Add Group Output node to the node group
    group_output = node_group.nodes.new('NodeGroupOutput')
    group_output.location = (600, 0)
    node_group.outputs.new('NodeSocketShader', 'Shader')
    
    # Create nodes inside the node group
    # Add a Principled BSDF node
    principled_bsdf_node = node_group.nodes.new(type='ShaderNodeBsdfPrincipled')
    principled_bsdf_node.location = (300, 0)
    principled_bsdf_node.inputs['Specular'].default_value = 0.0
    principled_bsdf_node.inputs['Roughness'].default_value = 0.6  # Slight roughness for frosted effect
    principled_bsdf_node.inputs['Transmission'].default_value = 1.0  # Full transmission for glass effect
    principled_bsdf_node.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 0.05)  # Subtle white color with slight transparency
    principled_bsdf_node.inputs['Alpha'].default_value = 0.3  # Set alpha under Emission to 0.3

    # Create links within the node group
    group_links = node_group.links
    group_links.new(principled_bsdf_node.outputs['BSDF'], group_output.inputs['Shader'])

    return node_group

def create_material_with_node_group_transparent(material_name, node_group):
    # Create a new material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    material.blend_method = 'BLEND'  # Set blend mode to Alpha Blend
    
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Clear default nodes
    for node in nodes:
        nodes.remove(node)

    # Add the node group to the material
    group_node = nodes.new(type='ShaderNodeGroup')
    group_node.node_tree = node_group
    group_node.location = (0, 0)

    # Add a Material Output node
    material_output_node = nodes.new(type='ShaderNodeOutputMaterial')
    material_output_node.location = (600, 0)

    # Create links outside the group
    links.new(group_node.outputs['Shader'], material_output_node.inputs['Surface'])

    return material

# Example usage
node_group = create_node_group_transparent()

# Assuming you have a material name you want to create:
material_name = "TransparentMaterial"
mat = create_material_with_node_group_transparent(material_name, node_group)
