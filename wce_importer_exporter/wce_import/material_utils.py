import bpy

DDS_HEADER_SIZE = 128  # Size of DDS header
DDS_MAGIC = b'DDS '  # The first 4 bytes of a DDS file should be "DDS "

def has_dds_header(texture_path):
    try:
        with open(texture_path, 'rb') as f:
            header = f.read(DDS_HEADER_SIZE)
            return len(header) >= DDS_HEADER_SIZE and header[:4] == DDS_MAGIC
    except IOError:
        return False

def is_dxt5_dds(texture_path):
    # Check if the texture is a DDS with DXT5 compression
    try:
        with open(texture_path, 'rb') as f:
            header = f.read(DDS_HEADER_SIZE)
            if len(header) < DDS_HEADER_SIZE:
                return False
            
            # The 'fourCC' for DXT5 starts at byte offset 84 in the header
            dxt5_indicator = header[84:88]
            return dxt5_indicator == b'DXT5'
    except IOError:
        return False

def add_texture_coordinate_and_mapping_nodes(nodes, links, image_texture_node, texture_path):
    """
    Adds a Texture Coordinate and Mapping node to the node tree, connects them to the image texture node,
    and flips the texture vertically if it is a DDS.

    :param nodes: Node tree of the material.
    :param links: Links of the node tree.
    :param image_texture_node: The image texture node to connect.
    :param texture_path: The path to the texture file.
    :return: Tuple of (tex_coord_node, mapping_node)
    """

    # Calculate positions relative to the Image Texture node
    tex_coord_location = (image_texture_node.location.x - 600, image_texture_node.location.y)
    mapping_location = (image_texture_node.location.x - 300, image_texture_node.location.y)

    # Create a new Texture Coordinate node
    tex_coord_node = nodes.new(type='ShaderNodeTexCoord')
    tex_coord_node.location = tex_coord_location

    # Create a new Mapping node
    mapping_node = nodes.new(type='ShaderNodeMapping')
    mapping_node.location = mapping_location

    # Flip the texture vertically if it has a DDS header
    if has_dds_header(texture_path):
        mapping_node.inputs['Scale'].default_value[1] = -1  # Flip vertically

    # Connect nodes
    links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
    links.new(mapping_node.outputs['Vector'], image_texture_node.inputs['Vector'])

    # Return the created nodes
    return tex_coord_node, mapping_node
    
def apply_detail_mapping(mapping_node, detail_value, has_dds_header):
    """
    Applies detail mapping scale to a mapping node.

    :param mapping_node: The mapping node to adjust.
    :param detail_value: The scale value to apply for detail mapping.
    :param has_dds_header: Boolean indicating if the texture has a DDS header.
    """
    # Apply the detail_value to X scale
    mapping_node.inputs['Scale'].default_value[0] = detail_value

    # Apply the detail_value to Y scale, negate if texture has a DDS header
    mapping_node.inputs['Scale'].default_value[1] = -detail_value if has_dds_header else detail_value

    print(f"Applied detail mapping: X scale = {detail_value}, Y scale = {'-' if has_dds_header else ''}{detail_value}")
    
def apply_tiled_mapping(mapping_node, scale_value, has_dds_header):
    """
    Applies tiled texture scaling to a mapping node.

    :param mapping_node: The mapping node to adjust.
    :param scale_value: The scale value to apply for tiled textures.
    :param has_dds_header: Boolean indicating if the texture has a DDS header.
    """
    # Apply the scale_value to X scale
    mapping_node.inputs['Scale'].default_value[0] = scale_value

    # Apply the scale_value to Y scale, negate if texture has a DDS header
    mapping_node.inputs['Scale'].default_value[1] = -scale_value if has_dds_header else scale_value

    print(f"Applied tiled mapping: X scale = {scale_value}, Y scale = {'-' if has_dds_header else ''}{scale_value}")

def _add_group_socket(nt: bpy.types.NodeTree, name: str, socket_type: str, is_input: bool):
    """
    Create a group interface socket in a way that works on both 3.6 and 4/5.
    Returns the created interface item (4/5) or the socket (3.6).
    """
    # Blender 4/5 API: use node_group.interface
    if hasattr(nt, "interface"):
        return nt.interface.new_socket(
            name=name,
            in_out='INPUT' if is_input else 'OUTPUT',
            socket_type=socket_type,
        )
    # Blender 3.6 fallback
    return (nt.inputs if is_input else nt.outputs).new(socket_type, name)

def _get_group_io_sockets(node_group):
    """
    Blender 5.0 compatible:
    Return two dicts mapping socket name -> NodeSocket
    for the Group Input (outputs) and Group Output (inputs) nodes.

    Usage:
        gi, go = _get_group_io_sockets(my_group)
        links.new(gi["Color"], some_node.inputs["Base Color"])
        links.new(some_node.outputs["BSDF"], go["Shader"])
    """
    gi_node = None
    go_node = None
    for n in node_group.nodes:
        # bl_idname is stable across versions
        if n.bl_idname == 'NodeGroupInput':
            gi_node = n
        elif n.bl_idname == 'NodeGroupOutput':
            go_node = n

    # Create them if they don't exist yet (fresh group)
    if gi_node is None:
        gi_node = node_group.nodes.new('NodeGroupInput')
        gi_node.location = (-400, 0)
    if go_node is None:
        go_node = node_group.nodes.new('NodeGroupOutput')
        go_node.location = (400, 0)

    # Build name->socket maps from the real, linkable sockets
    gi = {sock.name: sock for sock in gi_node.outputs}  # inputs of the group appear as outputs on Group Input
    go = {sock.name: sock for sock in go_node.inputs}   # outputs of the group appear as inputs on Group Output
    return gi, go

def _attach_scene_flag_driver_to_group_input(group_node, input_name='PassableDisplay',
                                             use_id_prop=False, scene=None):
    """
    Adds a driver to group_node.inputs[input_name].default_value so it follows the scene flag.
    If use_id_prop is True, uses Scene['PassableDisplay']; otherwise uses Scene.passable_display_enabled.
    """
    if scene is None:
        scene = bpy.context.scene

    sock = group_node.inputs.get(input_name)
    if not sock:
        return

    # Drivers are added to the default_value of the socket
    fcu = sock.driver_add("default_value")
    drv = fcu.driver
    drv.type = 'SCRIPTED'

    var = drv.variables.new()
    var.name = "s"
    tgt = var.targets[0]
    tgt.id_type = 'SCENE'
    tgt.id = scene
    tgt.data_path = '["PassableDisplay"]' if use_id_prop else 'passable_display_enabled'

    drv.expression = "s"
