import bpy

def export_animation_data(armature_obj, file, action_filter=None):
    """Writes animation data for an armature to the specified file.
    
    - `filepath`: The file where animation data should be written.
    - `action_filter`: The specific action to export, or None to export all matching actions.
    """

    if not armature_obj.animation_data or not armature_obj.animation_data.nla_tracks:
        print(f"No NLA tracks found for armature {armature_obj.name}.")
        return

    for nla_track in armature_obj.animation_data.nla_tracks:
        for strip in nla_track.strips:
            action = strip.action
            
            if action is None:
                continue  # Skip if no action is assigned to the strip

            # Skip actions that don't match the filter (if provided)
            if action_filter and not action.name.startswith(action_filter):
                continue

            # Process each bone's animation data
            for bone in armature_obj.pose.bones:
                bone_name = bone.name
                stripped_bone_name = bone_name.replace('_DAG', '').replace('_ANIDAG', '').split('.')[0]

                # Get fcurves for location, rotation, and scale
                location_fcurves = [f for f in action.fcurves if f'pose.bones["{bone_name}"].location' in f.data_path]
                rotation_fcurves = [f for f in action.fcurves if f'pose.bones["{bone_name}"].rotation_quaternion' in f.data_path]
                scale_fcurves = [f for f in action.fcurves if f'pose.bones["{bone_name}"].scale' in f.data_path]

                if not location_fcurves and not rotation_fcurves:
                    continue  # Skip bones with no meaningful animation

                # Get the number of frames
                num_frames = len(location_fcurves[0].keyframe_points) if location_fcurves else 1

                # Set action prefix
                action_prefix = "" if action.name.startswith("POS") else action.name.split('_')[0]

                # Define track names
                track_def_name = f"{action_prefix}{stripped_bone_name}_TRACKDEF"
                track_instance_name = f"{action_prefix}{stripped_bone_name}_TRACK"

                file.write(f'\nTRACKDEFINITION "{track_def_name}"\n')

                # Write action properties if they exist
                tag_index = action.get("TAGINDEX", 0)
                definition_index = action.get("SPRITEINDEX", 0)
                interpolate = 1 if action.get("INTERPOLATE", True) else 0
                reverse = 1 if action.get("REVERSE", False) else 0

                file.write(f'\tTAGINDEX {tag_index}\n')
                file.write(f'\tNUMFRAMES {num_frames}\n')

                # Extract keyframe data
                for frame_idx in range(num_frames):
                    scale_factor = 256
                    rotation_factor = 16384

                    # Extract scale data
                    if scale_fcurves:
                        scale_values = [scale_fcurves[i].keyframe_points[frame_idx].co[1] for i in range(3)]
                        average_scale = sum(scale_values) / 3.0
                        calculated_scale = round(average_scale * scale_factor)
                    else:
                        calculated_scale = scale_factor  # Default scale

                    # Extract translation (location) data
                    translation = [0, 0, 0]
                    if location_fcurves:
                        translation = [round(location_fcurves[i].keyframe_points[frame_idx].co[1] * scale_factor) for i in range(3)]

                    # Extract rotation (quaternion) data
                    rotation = [16384, 0, 0, 0]  # Default identity quaternion
                    if rotation_fcurves:
                        rotation = [round(rotation_fcurves[i].keyframe_points[frame_idx].co[1] * rotation_factor) for i in range(4)]

                    # Write frame data
                    file.write(f'\t\tFRAME {calculated_scale} {translation[0]} {translation[1]} {translation[2]} {rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]}\n')

                file.write(f'\tNUMLEGACYFRAMES 0\n')

                # Write TRACKINSTANCE
                file.write(f'\nTRACKINSTANCE "{track_instance_name}"\n')
                file.write(f'\tTAGINDEX {tag_index}\n')
                file.write(f'\tSPRITE "{track_def_name}"\n')
                file.write(f'\tSPRITEINDEX {definition_index}\n')
                file.write(f'\tINTERPOLATE {interpolate}\n')
                file.write(f'\tREVERSE {reverse}\n')

                # Calculate SLEEP time
                if num_frames > 1:
                    sleep_time = round((action.frame_range[1] - 1) / (num_frames - 1) * 1000 / bpy.context.scene.render.fps)
                else:
                    sleep_time = "NULL"
                file.write(f'\tSLEEP? {sleep_time}\n')
