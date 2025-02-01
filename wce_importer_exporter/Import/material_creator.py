import bpy
import os
from solidfillambientgouraud1 import create_node_group_sfag1, create_material_with_node_group_sfag1
from texture5ambientgouraud1 import create_node_group_t5ag1, create_material_with_node_group_t5ag1
from transparent import create_node_group_transparent, create_material_with_node_group_transparent
from userdefined_02 import create_node_group_ud02, create_material_with_node_group_ud02
from userdefined_06 import create_node_group_ud06, create_material_with_node_group_ud06
from userdefined_08 import create_node_group_ud08, create_material_with_node_group_ud08
from userdefined_10 import create_node_group_ud10, create_material_with_node_group_ud10
from userdefined_12 import create_node_group_ud12, create_material_with_node_group_ud12
from userdefined_20 import create_node_group_ud20, create_material_with_node_group_ud20
from userdefined_21 import create_node_group_ud21, create_material_with_node_group_ud21
from userdefined_22 import create_node_group_ud22, create_material_with_node_group_ud22
from userdefined_24 import create_node_group_ud24, create_material_with_node_group_ud24
from add_animated_texture_nodes import add_animated_texture_nodes
from add_layered_texture_nodes import add_layered_texture_nodes
from add_detail_texture_nodes import add_detail_texture_nodes
from add_palette_mask_texture_nodes import add_palette_mask_texture_nodes
from add_tiled_texture_nodes import add_tiled_texture_nodes
from dds_checker import scan_and_fix_dds_in_materials


def get_or_create_node_group(group_name, create_function, node_group_cache, texture_path=None):
    """
    Retrieves an existing node group or creates a new one if it doesn't exist.
    """
    if group_name in node_group_cache:
        return node_group_cache[group_name]
    
    if group_name in bpy.data.node_groups:
        node_group = bpy.data.node_groups[group_name]
    else:
        if texture_path is not None:
            node_group = create_function(texture_path)
        else:
            # If the function doesn't require texture_path, you can call it without arguments
            node_group = create_function()  
    
    node_group_cache[group_name] = node_group
    return node_group


def create_materials(materials, textures, file_path, node_group_cache):
    """
    Creates or retrieves materials based on the provided material data.
    """
    created_materials = {}
    base_path = file_path

    for mat_data in materials:
        mat_name = mat_data['name']
        if mat_name in bpy.data.materials:
            created_materials[mat_name] = bpy.data.materials[mat_name]
            continue

        texture_name = mat_data.get('texture_tag', '')
        texture_info = textures.get(texture_name, {})
        if isinstance(texture_info, dict) and texture_info.get('frames'):
            first_frame = texture_info['frames'][0]
            if first_frame.get('frame_files') and len(first_frame['frame_files']) > 0:
                texture_file = first_frame['frame_files'][0].get('file', '')
            else:
                texture_file = ''
        else:
            texture_file = ''
        texture_full_path = os.path.join(base_path, texture_file)

        rendermethod = mat_data['rendermethod']
        if rendermethod == 'SOLIDFILLAMBIENTGOURAUD1':
            node_group = get_or_create_node_group('SOLIDFILLAMBIENTGOURAUD1', create_node_group_sfag1, node_group_cache)
            mat = create_material_with_node_group_sfag1(mat_name, mat_data, node_group)
        elif rendermethod == 'TEXTURE5AMBIENTGOURAUD1':
            node_group = get_or_create_node_group('TEXTURE5AMBIENTGOURAUD1', create_node_group_t5ag1, node_group_cache)
            mat = create_material_with_node_group_t5ag1(mat_name, texture_full_path, node_group)
        elif rendermethod == 'TRANSPARENT':
            node_group = get_or_create_node_group('TRANSPARENT', create_node_group_transparent, node_group_cache)
            mat = create_material_with_node_group_transparent(mat_name, node_group)
        elif rendermethod == 'USERDEFINED_2':
            node_group = get_or_create_node_group('USERDEFINED_2', create_node_group_ud02, node_group_cache)
            mat = create_material_with_node_group_ud02(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_6':
            node_group = get_or_create_node_group('USERDEFINED_6', create_node_group_ud06, node_group_cache)
            mat = create_material_with_node_group_ud06(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_8':
            node_group = get_or_create_node_group('USERDEFINED_8', create_node_group_ud08, node_group_cache, texture_full_path)
            mat = create_material_with_node_group_ud08(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_10':
            node_group = get_or_create_node_group('USERDEFINED_10', create_node_group_ud10, node_group_cache)
            mat = create_material_with_node_group_ud10(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_12':
            node_group = get_or_create_node_group('USERDEFINED_12', create_node_group_ud12, node_group_cache)
            mat = create_material_with_node_group_ud12(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_20':
            node_group = get_or_create_node_group('USERDEFINED_20', create_node_group_ud20, node_group_cache, texture_full_path)
            mat = create_material_with_node_group_ud20(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_21':
            node_group = get_or_create_node_group('USERDEFINED_21', create_node_group_ud21, node_group_cache)
            mat = create_material_with_node_group_ud21(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_22':
            node_group = get_or_create_node_group('USERDEFINED_22', create_node_group_ud22, node_group_cache)
            mat = create_material_with_node_group_ud22(mat_name, texture_full_path, node_group)
        elif rendermethod == 'USERDEFINED_24':
            node_group = get_or_create_node_group('USERDEFINED_24', create_node_group_ud24, node_group_cache)
            mat = create_material_with_node_group_ud24(mat_name, texture_full_path, node_group)
        else:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get('Principled BSDF')
            if bsdf:
                bsdf.inputs['Base Color'].default_value = (0.698, 0.698, 0.698, 0.0)

        mat.use_fake_user = True  # Assign a fake user to the material        

        # Set Backface Culling based on DOUBLESIDED
        mat.use_backface_culling = not bool(mat_data.get('doublesided', 0))

        # Add custom properties from materialdefinition_parse
        mat["TAGINDEX"] = mat_data.get('tag_index', 0)
        mat["VARIATION"] = mat_data.get('variation', 0)
        mat["RGBPEN"] = mat_data.get('rgbpen', (0.698, 0.698, 0.698, 0.0))
        mat["BRIGHTNESS"] = mat_data.get('brightness', 0.0)
        mat["SCALEDAMBIENT"] = mat_data.get('scaledambient', 0.75)
        mat["HEXFIFTYFLAG"] = bool(mat_data.get('hexfiftyflag', 0))
        mat["PAIRS"] = mat_data.get('pairs', (0.0, 0.0))

        # Add custom properties from simplespritedef_parse
        mat["SKIPFRAMES"] = bool(texture_info.get('skipframes', 0))
        mat["ANIMATED"] = bool(texture_info.get('animated_flag', 0))
        mat["CURRENTFRAME"] = texture_info.get('current_frame', 0)

        # Handle animated textures, layered textures, and special frame types
        if texture_info.get('animated', False):
            add_animated_texture_nodes(mat, texture_info, file_path)
        if 'frames' in texture_info and texture_info['frames']:
            for file_entry in texture_info['frames'][0].get('frame_files', []):
                file_type = file_entry.get('type', '').lower()
                if file_type == 'layer':
                    add_layered_texture_nodes(mat, texture_info, node_group_cache, file_path)
                elif file_type == 'detail':
                    add_detail_texture_nodes(mat, texture_info, node_group_cache, file_path)
                elif file_type == 'palette_mask':
                    add_palette_mask_texture_nodes(mat, texture_info, node_group_cache, file_path)
                elif file_type == 'tiled':
                    add_tiled_texture_nodes(mat, file_entry, texture_info, node_group_cache, file_path)

        created_materials[mat_name] = mat

    scan_and_fix_dds_in_materials()

    return created_materials
