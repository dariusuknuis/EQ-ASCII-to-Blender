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
