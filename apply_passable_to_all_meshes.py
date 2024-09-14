import bpy

# Function to ensure we are in object mode
def ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

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
    
    # Add the Named Attribute and Equal nodes
    named_attribute = node_group.nodes.new('GeometryNodeInputNamedAttribute')
    named_attribute.data_type = 'INT'
    named_attribute.inputs[0].default_value = "PASSABLE"
    named_attribute.location = (-100, -100)
    
    equal_node = node_group.nodes.new('FunctionNodeCompare')
    equal_node.data_type = 'INT'
    equal_node.operation = 'EQUAL'
    equal_node.inputs[3].default_value = 1
    equal_node.location = (100, -100)
    
    # Add the Set Material node
    set_material = node_group.nodes.new('GeometryNodeSetMaterial')
    set_material.location = (300, 0)
    
    # Create the links between nodes
    node_group.links.new(group_input.outputs['Geometry'], set_material.inputs['Geometry'])
    node_group.links.new(named_attribute.outputs['Attribute'], equal_node.inputs[1])  # Correct output name: 'Attribute'
    node_group.links.new(equal_node.outputs['Result'], set_material.inputs['Selection'])
    
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
    ensure_object_mode()

    bpy.context.view_layer.objects.active = mesh_obj

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

# Function to recursively process all objects in the hierarchy
def process_object_hierarchy(obj, geo_node_group, passable_mat):
    if obj.type == 'MESH':
        print(f"Processing mesh: {obj.name}")
        apply_passable_to_mesh(obj, geo_node_group, passable_mat)
    else:
        print(f"Skipping non-mesh object: {obj.name}")
    
    for child in obj.children:
        process_object_hierarchy(child, geo_node_group, passable_mat)

# Apply passable to all objects in the scene
def apply_passable_to_all_meshes():
    geo_node_group = create_passable_geometry_node_group()
    passable_mat = create_passable_material()

    for obj in bpy.context.view_layer.objects:
        print(f"Object: {obj.name}, Type: {obj.type}")
        process_object_hierarchy(obj, geo_node_group, passable_mat)

apply_passable_to_all_meshes()