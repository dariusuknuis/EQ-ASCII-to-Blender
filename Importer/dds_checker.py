import bpy
import struct

DDS_HEADER_SIZE = 128  # Size of DDS header
DDS_MAGIC = b'DDS '  # The first 4 bytes of a DDS file should be "DDS "
DDS_OFFSET_MIPMAPCOUNT = 28  # Offset for mip map count
DDS_OFFSET_FLAGS = 8  # Offset for dwFlags
DDSD_MIPMAPCOUNT = 0x20000  # The flag that indicates mip maps are present
DDS_OFFSET_COMPRESSION = 84  # Offset for compression type
DXT1_COMPRESSION = b'DXT1'  # DXT1 compression identifier
DXT5_COMPRESSION = b'DXT5'  # DXT5 compression identifier

def check_and_fix_dds(texture_path):
    try:
        with open(texture_path, 'rb+') as f:
            header = f.read(DDS_HEADER_SIZE)
            if len(header) < DDS_HEADER_SIZE or header[:4] != DDS_MAGIC:
                return
            
            # Read the mip map count at offset 28
            mip_map_count = struct.unpack_from('<I', header, DDS_OFFSET_MIPMAPCOUNT)[0]
            
            # Read the dwFlags DWORD at offset 8
            flags = struct.unpack_from('<I', header, DDS_OFFSET_FLAGS)[0]
            
            # Read the compression type at offset 84
            compression = header[DDS_OFFSET_COMPRESSION:DDS_OFFSET_COMPRESSION + 4]
            
            if mip_map_count == 0 and (flags & DDSD_MIPMAPCOUNT) and (compression == DXT1_COMPRESSION or compression == DXT5_COMPRESSION):
                # If mip map count is 0, the mip map flag is set, and the compression is DXT1 or DXT5, turn off the mip map flag
#                print(f"Modifying {texture_path}: Turning off mip map flag for {compression.decode('ascii')}.")
                flags &= ~DDSD_MIPMAPCOUNT
                
                # Write the modified flags back to the file
                f.seek(DDS_OFFSET_FLAGS)
                f.write(struct.pack('<I', flags))
            else:
                print(f"No changes needed for {texture_path}.")
    except IOError as e:
        print(f"Failed to process {texture_path}: {e}")

def scan_and_fix_dds_in_materials():
    for material in bpy.data.materials:
        if material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    texture_path = bpy.path.abspath(node.image.filepath)
                    # Check the file header regardless of the extension
                    check_and_fix_dds(texture_path)
