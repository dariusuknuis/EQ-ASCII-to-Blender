import bpy
import re
import os
import shutil
from dds_checker import check_and_fix_dds

def add_animated_texture_nodes(material, texture_info, base_path=None):
    """
    Adds animated texture nodes to a material and checks for DDS files to fix headers.
    
    :param material: The material to modify.
    :param texture_info: A dictionary containing texture information, including animation details.
    :param base_path: The base path where texture files are located.
    """
    import re

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Retrieve the main image texture node (assuming it's named "Image Texture")
    image_texture_node = None
    for node in nodes:
        if node.type == 'TEX_IMAGE':
            image_texture_node = node
            break

    if not image_texture_node:
        print(f"No image texture node found in material: {material.name}")
        return

    # Set the image texture node to use an image sequence
    image_texture_node.image.source = 'SEQUENCE'
    image_texture_node.image_user.use_auto_refresh = True  # Enable auto refresh for animated textures

    # Set the number of frames and start frame based on texture_info
    number_frames = texture_info.get('number_frames', 1)
    image_texture_node.image_user.frame_duration = number_frames
    image_texture_node.image_user.frame_start = -(number_frames - 2)

    # Process all files in the animation frames
    frame_files = texture_info.get('frame_files', [])
    frames_info = texture_info.get('frames', [])
    
    for frame_data in frames_info:
        frame_file = frame_data['file']
        animation_frame = frame_data['animation_frame']

        # Construct the full path to the file
        if base_path:
            full_path = os.path.join(base_path, frame_file)
        else:
#            print(f"Warning: base_path is not provided. Using frame file as is: {frame_file}")
            full_path = frame_file

        texture_path = bpy.path.abspath(full_path)  # Convert to absolute path

        print(f"Processing file: {texture_path}")  # Debugging output

        if not os.path.isfile(texture_path):
            print(f"File not found: {texture_path}")
            continue

        # Extract the number from the original frame file name
        match = re.search(r'(\d+)(?=\.\w+$)', frame_file)
        if match:
            actual_frame_number = int(match.group(1))
        else:
            print(f"No numeric frame number found in file name: {frame_file}")
            continue

        # Check if the actual frame number matches the expected animation frame number
        if actual_frame_number != animation_frame:
            # Copy and rename the file to match the correct frame number
            base_name, ext = os.path.splitext(frame_file)
            new_file_name = re.sub(r'\d+$', f"{animation_frame}", base_name) + ext
            new_full_path = os.path.join(base_path, new_file_name)

            try:
                shutil.copy(texture_path, new_full_path)
#                print(f"Copied and renamed {texture_path} to {new_full_path}")
                frame_file = new_file_name  # Update frame file to the newly created file
            except Exception as e:
                print(f"Error copying and renaming file {texture_path} to {new_full_path}: {e}")
                continue

        # Update the frame_file path after copying and renaming
        full_path = os.path.join(base_path, frame_file) if base_path else frame_file
        texture_path = bpy.path.abspath(full_path)

        # Pass the absolute file path to the check_and_fix_dds function
        try:
            check_and_fix_dds(texture_path)  # Ensure DDS headers are correct
            print(f"Processed file: {texture_path}")
        except Exception as e:
            print(f"Failed to process file {texture_path}: {e}")

    # Set up the driver for the offset
    offset_driver = image_texture_node.image_user.driver_add("frame_offset").driver
    offset_driver.type = 'SCRIPTED'
    offset_driver.expression = "int((frame / (fps * (sleep / 1000))) % num_frames) - (num_frames - 1)"

    # Add input variables for the driver
    var_frame = offset_driver.variables.new()
    var_frame.name = 'frame'
    var_frame.targets[0].id_type = 'SCENE'
    var_frame.targets[0].id = bpy.context.scene
    var_frame.targets[0].data_path = 'frame_current'

    var_fps = offset_driver.variables.new()
    var_fps.name = 'fps'
    var_fps.targets[0].id_type = 'SCENE'
    var_fps.targets[0].id = bpy.context.scene
    var_fps.targets[0].data_path = 'render.fps'

    var_sleep = offset_driver.variables.new()
    var_sleep.name = 'sleep'
    var_sleep.targets[0].id_type = 'MATERIAL'
    var_sleep.targets[0].id = material
    var_sleep.targets[0].data_path = '["sleep"]'

    var_num_frames = offset_driver.variables.new()
    var_num_frames.name = 'num_frames'
    var_num_frames.targets[0].id_type = 'MATERIAL'
    var_num_frames.targets[0].id = material
    var_num_frames.targets[0].data_path = '["number_frames"]'

    # Set custom properties for the material
    sleep_value = texture_info.get('sleep', 'NULL')
    number_frames = texture_info.get('number_frames', 1)

    material["sleep"] = sleep_value if sleep_value != 'NULL' else 'NULL'
    material["number_frames"] = number_frames

    # Set custom properties with zero-padded frame names
    for idx, frame_file in enumerate(frame_files):
        frame_name = f"Frame name {idx + 1:03}"  # Zero-padded frame number
        material[frame_name] = frame_file

#    print(f"Added animated texture nodes to material: {material.name}")
