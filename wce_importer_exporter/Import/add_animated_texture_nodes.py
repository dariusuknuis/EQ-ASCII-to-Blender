import bpy
import os
import re
import shutil
from dds_checker import check_and_fix_dds

def add_animated_texture_nodes(material, texture_info, base_path=None):
    """
    Modifies image texture nodes in a material so that they use image sequences.
    The base image texture node (one whose name does not end with "LAYER" or "DETAIL")
    will use the first file in each frame, and any image texture node whose name ends
    in "LAYER" or "DETAIL" will use the second file in each frame.
    
    It sets each node’s image source to 'SEQUENCE', enables auto refresh,
    and creates a driver for the frame offset.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Identify base and overlay (layer/detail) image texture nodes
    base_node = None
    overlay_nodes = []
    for node in nodes:
        if node.type == 'TEX_IMAGE':
            # Use the node name to decide if it's an overlay node
            node_name_upper = node.name.upper()
            if node_name_upper.endswith("LAYER") or node_name_upper.endswith("DETAIL"):
                overlay_nodes.append(node)
            else:
                if base_node is None:
                    base_node = node

    if not base_node:
        print(f"[add_animated_texture_nodes] No base image texture node found in material: {material.name}")
        return

    # Get the total number of frames (assumed stored in texture_info)
    number_frames = texture_info.get('num_frames', 1)

    # Set up the base node for sequence animation
    base_node.image.source = 'SEQUENCE'
    base_node.image_user.use_auto_refresh = True
    base_node.image_user.frame_duration = number_frames
    base_node.image_user.frame_start = -(number_frames - 2)

    # Build two lists from the texture_info frames:
    # - base_frame_files: the first file in each frame (for the base node)
    # - overlay_frame_files: the second file in each frame (for overlay nodes)
    base_frame_files = []
    overlay_frame_files = []
    for frame in texture_info.get('frames', []):
        files = frame.get('frame_files', [])
        # Use first file as base (or empty string if missing)
        base_frame_files.append(files[0].get('file', '') if len(files) > 0 else '')
        # Use second file as overlay (or empty string if not present)
        overlay_frame_files.append(files[1].get('file', '') if len(files) > 1 else '')

    # Process base image sequence files
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
        # Extract numeric frame number from the filename
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
            # Instead, load the image and duplicate its data block
            try:
                # Load the original image if not already loaded:
                original_image = bpy.data.images.get(os.path.basename(texture_path))
                if not original_image:
                    original_image = bpy.data.images.load(texture_path)
                # Duplicate the image data block
                new_image = original_image.copy()
                new_image.name = new_file_name  # new name for sequence consistency
                # Optionally, update the filepath if needed (for display purposes only)
                new_image.filepath = new_full_path
                # Pack the image so it’s stored in the blend file
                new_image.pack()
                # Now update your frame reference to point to the new image's name
                frame_file = new_file_name
            except Exception as e:
                print(f"Error duplicating image for sequence: {e}")


    # Process overlay nodes (if any)
    for overlay_node in overlay_nodes:
        overlay_node.image.source = 'SEQUENCE'
        overlay_node.image_user.use_auto_refresh = True
        overlay_node.image_user.frame_duration = number_frames
        overlay_node.image_user.frame_start = -(number_frames - 2)
        # Process the overlay sequence files using the second file from each frame
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
                    # Get the original image data block by its basename. If it's not already loaded, load it.
                    original_image = bpy.data.images.get(os.path.basename(texture_path))
                    if not original_image:
                        original_image = bpy.data.images.load(texture_path)
                    # Duplicate the image data block
                    new_image = original_image.copy()
                    new_image.name = new_file_name  # assign the new name to maintain the sequence
                    new_image.filepath = new_full_path  # update the filepath for display/reference
                    new_image.pack()  # optionally pack the image into the blend file
                    overlay_frame_files[idx] = new_file_name
                except Exception as e:
                    print(f"[add_animated_texture_nodes] Error duplicating overlay image from {texture_path} to {new_full_path}: {e}")
                    continue

        # Add a driver for the overlay node’s frame offset
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

    # Add a driver for the base node’s frame offset
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

    # (Optionally) store the base frame filenames as custom properties on the material
    for idx, frame_file in enumerate(base_frame_files):
        frame_name = f"FRAME {idx + 1:03}"
        material[frame_name] = frame_file
