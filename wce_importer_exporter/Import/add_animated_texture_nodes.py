import bpy
import os
import re
import shutil
import json
from dds_checker import check_and_fix_dds

def add_animated_texture_nodes(material, texture_info, base_path=None):
    """
    Modifies image texture nodes in a material so that they use image sequences.
    The base image texture node (one whose name does not end with "LAYER" or "DETAIL")
    will use the first file in each frame, and any image texture node whose name ends
    in "LAYER" or "DETAIL" will use the second file in each frame.
    
    It sets each node’s image source to 'SEQUENCE', enables auto refresh,
    and creates a driver for the frame offset.
    
    This version uses a copy-and-rename approach on disk (via shutil.copy) if the file’s
    numeric suffix is not sequential.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Identify base and overlay (layer/detail) image texture nodes.
    # (For this example, we assume there is one base image texture node,
    # and any additional TEX_IMAGE nodes are overlays.)
    base_node = None
    overlay_nodes = []
    for node in nodes:
        if node.type == 'TEX_IMAGE':
            node_name_upper = node.name.upper()
            if node_name_upper.endswith("LAYER") or node_name_upper.endswith("DETAIL"):
                overlay_nodes.append(node)
            else:
                if base_node is None:
                    base_node = node

    if not base_node:
        print(f"[add_animated_texture_nodes] No base image texture node found in material: {material.name}")
        return

    # Set up the base node for sequence animation.
    base_node.image.source = 'SEQUENCE'
    base_node.image_user.use_auto_refresh = True
    number_frames = texture_info.get('num_frames', 1)
    base_node.image_user.frame_duration = number_frames
    base_node.image_user.frame_start = -(number_frames - 2)

    # Build lists from the texture_info frames.
    # Each frame in texture_info['frames'] is expected to be a dict that contains a
    # 'frame_files' list. For a non-animated (or tiled) texture with a single frame,
    # there will typically be one or two files:
    #   - Index 0: base image
    #   - Index 1: overlay (layer/detail) image (if any)
    base_frame_files = []
    overlay_frame_files = []
    for frame in texture_info.get('frames', []):
        files = frame.get('frame_files', [])
        # Use the first file as base (or empty string if missing)
        if len(files) > 0:
            base_frame_files.append(files[0].get('file', ''))
        else:
            base_frame_files.append('')
        # Use the second file as overlay (or empty string if not present)
        if len(files) > 1:
            overlay_frame_files.append(files[1].get('file', ''))
        else:
            overlay_frame_files.append('')

    # Process the base sequence files.
    for idx, frame_file in enumerate(base_frame_files):
        if not frame_file:
            continue
        full_path = os.path.join(base_path, frame_file) if base_path else frame_file
        texture_path = bpy.path.abspath(full_path)
        if not os.path.isfile(texture_path):
            print(f"[add_animated_texture_nodes] Base file not found: {texture_path}")
            continue
        try:
            check_and_fix_dds(texture_path)
        except Exception as e:
            print(f"[add_animated_texture_nodes] Failed to process base file {texture_path}: {e}")
        # Extract numeric frame number from the filename (e.g. "NEWWAT25.DDS" yields 25)
        match = re.search(r'(\d+)(?=\.\w+$)', frame_file)
        if match:
            actual_frame_number = int(match.group(1))
        else:
            print(f"[add_animated_texture_nodes] No numeric frame number found in base file name: {frame_file}")
            continue
        expected_frame = idx + 1
        if actual_frame_number != expected_frame:
            base_name, ext = os.path.splitext(frame_file)
            new_file_name = re.sub(r'\d+$', f"{expected_frame}", base_name) + ext
            new_full_path = os.path.join(base_path, new_file_name)
            try:
                shutil.copy(texture_path, new_full_path)
                print(f"Copied and renamed {texture_path} to {new_full_path}")
                base_frame_files[idx] = new_file_name  # Update the reference in our list.
            except Exception as e:
                print(f"Error copying and renaming file {texture_path} to {new_full_path}: {e}")
                continue
        # Update texture_path after potential renaming.
        full_path = os.path.join(base_path, base_frame_files[idx]) if base_path else base_frame_files[idx]
        texture_path = bpy.path.abspath(full_path)
        try:
            check_and_fix_dds(texture_path)
            print(f"Processed base file: {texture_path}")
        except Exception as e:
            print(f"Failed to process file {texture_path}: {e}")

    # Process overlay files (if any overlay nodes exist)
    for overlay_node in overlay_nodes:
        overlay_node.image.source = 'SEQUENCE'
        overlay_node.image_user.use_auto_refresh = True
        overlay_node.image_user.frame_duration = number_frames
        overlay_node.image_user.frame_start = -(number_frames - 2)
        # Process overlay sequence files using the second file from each frame.
        for idx, overlay_file in enumerate(overlay_frame_files):
            if not overlay_file:
                continue
            full_path = os.path.join(base_path, overlay_file) if base_path else overlay_file
            texture_path = bpy.path.abspath(full_path)
            if not os.path.isfile(texture_path):
                print(f"[add_animated_texture_nodes] Overlay file not found: {texture_path}")
                continue
            try:
                check_and_fix_dds(texture_path)
            except Exception as e:
                print(f"[add_animated_texture_nodes] Failed to process overlay file {texture_path}: {e}")
            match = re.search(r'(\d+)(?=\.\w+$)', overlay_file)
            if match:
                actual_frame_number = int(match.group(1))
            else:
                print(f"[add_animated_texture_nodes] No numeric frame number found in overlay file name: {overlay_file}")
                continue
            expected_frame = idx + 1
            if actual_frame_number != expected_frame:
                base_name, ext = os.path.splitext(overlay_file)
                new_file_name = re.sub(r'\d+$', f"{expected_frame}", base_name) + ext
                new_full_path = os.path.join(base_path, new_file_name)
                try:
                    original_image = bpy.data.images.get(os.path.basename(texture_path))
                    if not original_image:
                        original_image = bpy.data.images.load(texture_path)
                    # Duplicate the image by copying the file on disk.
                    shutil.copy(texture_path, new_full_path)
                    print(f"Copied and renamed overlay {texture_path} to {new_full_path}")
                    overlay_frame_files[idx] = new_file_name
                except Exception as e:
                    print(f"[add_animated_texture_nodes] Error duplicating overlay image from {texture_path} to {new_full_path}: {e}")
                    continue
        # Add a driver for the overlay node’s frame offset.
        od = overlay_node.image_user.driver_add("frame_offset").driver
        od.type = 'SCRIPTED'
        od.expression = "int((frame / (fps * (sleep / 1000))) % num_frames) - (num_frames - 1)"
        var_frame = od.variables.new()
        var_frame.name = 'frame'
        var_frame.targets[0].id_type = 'SCENE'
        var_frame.targets[0].id = bpy.context.scene
        var_frame.targets[0].data_path = 'frame_current'
        var_fps = od.variables.new()
        var_fps.name = 'fps'
        var_fps.targets[0].id_type = 'SCENE'
        var_fps.targets[0].id = bpy.context.scene
        var_fps.targets[0].data_path = 'render.fps'
        var_sleep = od.variables.new()
        var_sleep.name = 'sleep'
        var_sleep.targets[0].id_type = 'MATERIAL'
        var_sleep.targets[0].id = material
        var_sleep.targets[0].data_path = '["SLEEP"]'
        var_num_frames = od.variables.new()
        var_num_frames.name = 'num_frames'
        var_num_frames.targets[0].id_type = 'MATERIAL'
        var_num_frames.targets[0].id = material
        var_num_frames.targets[0].data_path = '["NUMFRAMES"]'

    # Add a driver for the base node’s frame offset.
    bd = base_node.image_user.driver_add("frame_offset").driver
    bd.type = 'SCRIPTED'
    bd.expression = "int((frame / (fps * (sleep / 1000))) % num_frames) - (num_frames - 1)"
    var_frame = bd.variables.new()
    var_frame.name = 'frame'
    var_frame.targets[0].id_type = 'SCENE'
    var_frame.targets[0].id = bpy.context.scene
    var_frame.targets[0].data_path = 'frame_current'
    var_fps = bd.variables.new()
    var_fps.name = 'fps'
    var_fps.targets[0].id_type = 'SCENE'
    var_fps.targets[0].id = bpy.context.scene
    var_fps.targets[0].data_path = 'render.fps'
    var_sleep = bd.variables.new()
    var_sleep.name = 'sleep'
    var_sleep.targets[0].id_type = 'MATERIAL'
    var_sleep.targets[0].id = material
    var_sleep.targets[0].data_path = '["SLEEP"]'
    var_num_frames = bd.variables.new()
    var_num_frames.name = 'num_frames'
    var_num_frames.targets[0].id_type = 'MATERIAL'
    var_num_frames.targets[0].id = material
    var_num_frames.targets[0].data_path = '["NUMFRAMES"]'

    # Set custom properties for the material.
    sleep_value = texture_info.get('sleep', 'NULL')
    #number_frames = texture_info.get('num_frames', 1)
    material["SLEEP"] = sleep_value if sleep_value != 'NULL' else 'NULL'
    material["NUMFRAMES"] = number_frames

    # Store the original (or corrected) base frame filenames as custom properties.
    # For each frame, create a custom property with a key like "FRAME 001"
    # and a value in the format: "<frame_tag>, <base texture file name>, <overlay texture file name (if exists)>"
    for idx, frame in enumerate(texture_info.get("frames", [])):
        frame_key = f"FRAME {idx + 1:03}"
        # Get the frame tag from the frame dictionary.
        tag = frame.get("tag", "")
        # Get the base file from the first file entry.
        base_file = ""
        overlay_file = ""
        frame_files = frame.get("frame_files", [])
        if len(frame_files) > 0:
            base_file = frame_files[0].get("file", "")
        if len(frame_files) > 1:
            overlay_file = frame_files[1].get("file", "")
        
        # Build the property value.
        if overlay_file:
            value = f"{tag}, {base_file}, {overlay_file}"
        else:
            value = f"{tag}, {base_file}"
        
        # Store the custom property on the material.
        material[frame_key] = value
        print(f"Set property {frame_key} = {value}")


    # At this point, the extra (copied/renamed) files remain on disk.
    # If you want to delete them afterward, you could loop over a list of such files.
    # (For this version, we are leaving them intact.)

