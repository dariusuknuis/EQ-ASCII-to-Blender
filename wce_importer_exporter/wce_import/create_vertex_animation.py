import bpy

def create_vertex_animation(mesh_obj, dmtrack_name, vertex_animations):
    vertex_animation_data = next((anim for anim in vertex_animations if anim.get('name') == dmtrack_name), None)
    
    # Ensure animation data was found
    if not vertex_animation_data:
        print(f"Warning: No vertex animation found for {dmtrack_name}")
        return
    
    sleep = vertex_animation_data.get("sleep", 1000)  # Assume sleep is in milliseconds if not given
    fps = bpy.context.scene.render.fps  # Get scene FPS
    frames_per_sleep = (sleep / 1000) * fps  # Calculate frames per sleep interval
    current_frame = 1  # Start animation at frame 1

    # Add custom properties from DMTRACKDEF2 data
    mesh_obj.data["FPSCALE"] = vertex_animation_data.get("fpscale", 1)
    mesh_obj.data["PARAM2"] = vertex_animation_data.get("param2", 0)
    mesh_obj.data["SIZE6"] = vertex_animation_data.get("size6", 0)

    # Add the basis shape key (initial position)
    if mesh_obj.data.shape_keys is None:
        mesh_obj.shape_key_add(name="Basis", from_mix=False)
    mesh_obj.data.shape_keys.use_relative = True  # Set to "Relative" mode

    # Create a new action for shape keys with the name of dmtrack_name
    action = bpy.data.actions.new(name=dmtrack_name)
    mesh_obj.data.shape_keys.animation_data_create().action = action

    # Create shape keys with frame-specific names and set up the frames
    shape_keys = []
    for frame_index, frame_data in enumerate(vertex_animation_data["frames"]):
        # Name each shape key based on dmtrack_name and frame number
        shape_key_name = f"{dmtrack_name}_{frame_index + 1}"
        shape_key = mesh_obj.shape_key_add(name=shape_key_name, from_mix=False)
        shape_keys.append(shape_key)
        for vertex, coords in zip(mesh_obj.data.shape_keys.key_blocks[shape_key_name].data, frame_data):
            vertex.co = coords

    # Set up keyframes for shape keys to create the animation sequence
    for shape_key in shape_keys:
        # Set all shape key values to 0 and keyframe them at this frame
        for sk in shape_keys:
            sk.value = 0.0
            sk.keyframe_insert(data_path="value", frame=current_frame)
        
        # Set only the active shape key's value to 1.0 and keyframe it
        shape_key.value = 1.0
        shape_key.keyframe_insert(data_path="value", frame=current_frame)
        
        # Advance to the next frame for the next shape key
        current_frame += frames_per_sleep

    # Ensure shape key animation is visible in playback
    mesh_obj.active_shape_key_index = 0
    bpy.context.view_layer.objects.active = mesh_obj
