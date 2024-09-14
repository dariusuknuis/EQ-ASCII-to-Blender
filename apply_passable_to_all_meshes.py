import bpy

# Function to ensure we are in object mode
def ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

# Debug function to print socket info
def print_socket_info(node):
    print(f"Node: {node.name}, Type: {node.type}")
    print("Outputs:")
    for output in node.outputs:
        print(f"  {output.name} ({output.type})")
    print("Inputs:")
    for input in node.inputs:
        print(f"  {input.name} ({input.type})")

# Function to create the passable geometry node group
def create_passable_geometry_node_group():
    if "PASSABLE" in bpy.data.node_groups:
        print("Using existing 'PASSABLE' geometry node group.")
        return bpy.data.node_groups["PASSABLE"]
    
    print("Creating 'PASSABLE' geometry node group.")
    node_group = bpy.data.node_groups.new(name="PASSABLE", type="GeometryNodeTree")
    
    # Create the input and output nodes
    group_input = node_group.nodes.new(type='NodeGroupInput')
    group_output = node_group.nodes.new(type='NodeGroupOutput')
    
    node_group.inputs.new('NodeSocketGeometry', 'Geometry')
    node_group.outputs.new('NodeSocketGeometry', 'Geometry')
    
    group_input.location = (-300, 0)
    group_output.location = (300, 0)
    
    # Add the Named Attribute and Compare (Equal) nodes
    named_attribute = node_group.nodes.new('GeometryNodeInputNamedAttribute')
    named_attribute.data_type = 'INT'
    named_attribute.inputs[0].default_value = "PASSABLE"
    named_attribute.location = (-300, -100)
    
    equal_node = node_group.nodes.new('FunctionNodeCompare')
    equal_node.data_type = 'INT'  # Change the data type to FLOAT to avoid issues
    equal_node.operation = 'EQUAL'
    equal_node.inputs[3].default_value = 1
    equal_node.location = (-100, -100)
    
    # Add the Set Material node
    set_material = node_group.nodes.new('GeometryNodeSetMaterial')
    set_material.location = (100, 0)
    passable_material = bpy.data.materials.get("PASSABLE")
    set_material.inputs['Material'].default_value = passable_material
    
    # Create the links between nodes
    node_group.links.new(group_input.outputs['Geometry'], set_material.inputs['Geometry'])
    
    # Correctly get the 'Attribute' output from Named Attribute for the 'INT' type
    attribute_output = next(s for s in named_attribute.outputs if s.name == 'Attribute' and s.type == 'INT')
    
    # Correctly get the input for the Compare node based on the FLOAT type
    compare_value_input = next(s for s in equal_node.inputs if s.name == 'A' and s.type == 'INT')
    
    # Link the Named Attribute to the correct Compare node input
    node_group.links.new(attribute_output, compare_value_input)
    
    # Link the result of the Equal node to the Set Material selection input
    equal_output = equal_node.outputs.get('Result')
    set_material_input = set_material.inputs.get('Selection')
    node_group.links.new(equal_output, set_material_input)
    
    # Connect to output
    node_group.links.new(set_material.outputs['Geometry'], group_output.inputs['Geometry'])
    
    print("Created 'PASSABLE' geometry node group.")
    return node_group

# Function to create a passable material
def create_passable_material():
    passable_mat = bpy.data.materials.get('PASSABLE')
    if not passable_mat:
        print("Creating 'PASSABLE' material...")
        passable_mat = bpy.data.materials.new(name="PASSABLE")
        passable_mat.use_nodes = True
        passable_mat.blend_method = 'BLEND'
        passable_mat.show_transparent_back = True

        nodes = passable_mat.node_tree.nodes
        nodes.clear()

        transparent_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
        emission_shader = nodes.new(type='ShaderNodeEmission')
        mix_shader = nodes.new(type='ShaderNodeMixShader')
        material_output = nodes.new(type='ShaderNodeOutputMaterial')

        transparent_bsdf.location = (-400, 200)
        emission_shader.location = (-400, 0)
        mix_shader.location = (-200, 100)
        material_output.location = (0, 100)

        passable_mat.node_tree.links.new(transparent_bsdf.outputs['BSDF'], mix_shader.inputs[1])
        passable_mat.node_tree.links.new(emission_shader.outputs['Emission'], mix_shader.inputs[2])
        passable_mat.node_tree.links.new(mix_shader.outputs['Shader'], material_output.inputs['Surface'])

        emission_shader.inputs['Color'].default_value = (0.0, 1.0, 0.0, 1.0)  # Green color

        print("'PASSABLE' material created.")
    else:
        print("'PASSABLE' material already exists.")
    
    return passable_mat

# Function to apply the passable geometry node group and material to a mesh object
def apply_passable_to_mesh(mesh_obj, geo_node_group, passable_mat):
    if mesh_obj.type != 'MESH':
        print(f"Skipping non-mesh object: {mesh_obj.name}")
        return
    
    print(f"Applying PASSABLE geometry node to {mesh_obj.name}")
    
    modifier = mesh_obj.modifiers.get("PASSABLE")
    if not modifier:
        modifier = mesh_obj.modifiers.new(name="PASSABLE", type='NODES')
        modifier.node_group = geo_node_group
        modifier.show_viewport = False
        print(f"Geometry node modifier applied to {mesh_obj.name}")
    
    if passable_mat.name not in [mat.name for mat in mesh_obj.data.materials]:
        mesh_obj.data.materials.append(passable_mat)
        print(f"Added PASSABLE material to {mesh_obj.name}")

# Function to apply passable nodes to all meshes in the scene
def apply_passable_to_all_meshes():
    passable_mat = create_passable_material()
    geo_node_group = create_passable_geometry_node_group()

    # Iterate over all objects in the scene and apply to all mesh objects
    for obj in bpy.context.view_layer.objects:
        if obj.type == 'MESH':  # Ensure we are only applying to meshes
            print(f"Applying to mesh: {obj.name}")
            apply_passable_to_mesh(obj, geo_node_group, passable_mat)
        else:
            print(f"Skipping non-mesh object: {obj.name}")

apply_passable_to_all_meshes()