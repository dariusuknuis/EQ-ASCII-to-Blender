import bpy

def write_dm_track_def_2(mesh, file):
    # Ensure the mesh has shape keys and KeyAction
    if not mesh.data.shape_keys or len(mesh.data.shape_keys.key_blocks) <= 1:
        print(f"No vertex animation shape keys found for {mesh.name}")
        return
    
    # Access the KeyAction linked to shape keys and use its name
    if not mesh.data.shape_keys.animation_data or not mesh.data.shape_keys.animation_data.action:
        print(f"No KeyAction linked to shape keys for {mesh.name}")
        return
    
    key_action = mesh.data.shape_keys.animation_data.action
    dmtrack_name = key_action.name

    # Get the frame range from the KeyAction
    frame_start, frame_end = key_action.frame_range
    scene_fps = bpy.context.scene.render.fps
    # Calculate NUMFRAMES based on the number of shape keys excluding "Basis"
    shape_keys = [key for key in mesh.data.shape_keys.key_blocks if key.name != "Basis"]
    num_frames = len(shape_keys)
    sleep_time = round((frame_end - 1) / (num_frames - 1) * 1000 / scene_fps)

    # Get custom properties for PARAM2, FPSCALE, and SIZE6
    param2 = mesh.get("PARAM2", 0)
    fpscale = mesh.get("FPSCALE", 1)
    size6 = mesh.get("SIZE6", 0)

    # Write the DMTRACKDEF2 header information
    file.write(f'DMTRACKDEF2 "{dmtrack_name}"\n')
    file.write(f'\tSLEEP {sleep_time}\n')
    file.write(f'\tPARAM2 {param2}\n')
    file.write(f'\tFPSCALE {fpscale}\n')
    file.write(f'\tSIZE6 {size6}\n')
    file.write(f'\tNUMFRAMES {num_frames}\n')

    # Write vertex data for each frame based on key blocks
    for frame_index, shape_key in enumerate(shape_keys):
        bpy.context.scene.frame_set(int(frame_start + frame_index))
        num_vertices = len(mesh.data.vertices)
        file.write(f'\t\tNUMVERTICES {num_vertices}\n')
        
        for vertex_index, vertex in enumerate(mesh.data.vertices):
            # Get vertex coordinates from the current shape key
            vertex_coords = shape_key.data[vertex_index].co
            file.write(f'\t\t\tXYZ {vertex_coords.x:.8e} {vertex_coords.y:.8e} {vertex_coords.z:.8e}\n')

    print(f'DMTRACKDEF2 data for "{dmtrack_name}" exported.')
