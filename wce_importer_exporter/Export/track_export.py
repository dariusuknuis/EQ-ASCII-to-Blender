import bpy

def export_animation_data(armature_obj, file, include_pos=False):
    # Debug: Print armature object being used
    # print(f"Exporting animations for armature: {armature_obj.name}")

    if not armature_obj.animation_data or not armature_obj.animation_data.nla_tracks:
        print(f"No NLA tracks found for armature {armature_obj.name}.")
        return

    for nla_track in armature_obj.animation_data.nla_tracks:
        # print(f"Processing NLA track: {nla_track.name}")
        
        for strip in nla_track.strips:
            action = strip.action
            if action is None:
                continue  # Skip if action is None
        
        # Debug: Print the action being processed
        # print(f"Processing action: {action.name}")

        # Filter actions based on POS inclusion
        if include_pos and not action.name.startswith("POS"):
            continue
        elif not include_pos and action.name.startswith("POS"):
            continue

        # Debug: Print which actions are being processed
        # print(f"Writing animation: {action.name} (POS included: {include_pos})")

        # Write TRACKDEFINITION and TRACKINSTANCE for each bone in the armature
        for bone in armature_obj.pose.bones:
            bone_name = bone.name
            # print(f"Processing bone: {bone_name}")

            # Strip off any .001, .002 suffixes and remove _DAG or _ANIDAG
            stripped_bone_name = bone_name.replace('_DAG', '').replace('_ANIDAG', '').split('.')[0]

            # Filter the fcurves for the current action and this bone
            location_fcurves = [fcurve for fcurve in action.fcurves if f'pose.bones["{bone_name}"].location' in fcurve.data_path]
            rotation_fcurves = [fcurve for fcurve in action.fcurves if f'pose.bones["{bone_name}"].rotation_quaternion' in fcurve.data_path]
            scale_fcurves = [fcurve for fcurve in action.fcurves if f'pose.bones["{bone_name}"].scale' in fcurve.data_path]

            if not location_fcurves and not rotation_fcurves:
                continue  # Skip if no animation data exists for this bone

            # Get the number of frames from the keyframe points
            num_frames = len(location_fcurves[0].keyframe_points) if location_fcurves else 1

            # Exclude "POS" prefix in the track names
            if action.name.startswith("POS"):
                action_prefix = ""
            else:
                action_prefix = action.name.split('_')[0]

            # Write the TRACKDEFINITION for this bone
            track_def_name = f"{action_prefix}{stripped_bone_name}_TRACKDEF"
            track_instance_name = f"{action_prefix}{stripped_bone_name}_TRACK"

            # Debug: Print track definition being written
            # print(f"Writing TRACKDEFINITION: {track_def_name}")

            file.write(f'\nTRACKDEFINITION "{track_def_name}"\n')

            # Write action custom properties if they exist
            tag_index = action.get("TAGINDEX", 0)
            definition_index = action.get("SPRITEINDEX", 0)
            interpolate = 1 if action.get("INTERPOLATE", True) else 0
            reverse = 1 if action.get("REVERSE", False) else 0

            file.write(f'\tTAGINDEX {tag_index}\n')
            file.write(f'\tNUMFRAMES {num_frames}\n')

            # Extract keyframe data for the bone
            for frame_idx in range(num_frames):
                scale_factor = 256
                rotation_factor = 16384

                # --- Extract scale data and compute average ---
                if scale_fcurves:
                    scale_values = [
                        scale_fcurves[i].keyframe_points[frame_idx].co[1] for i in range(3)  # X, Y, Z scales
                    ]
                    average_scale = sum(scale_values) / 3.0
                    calculated_scale = round(average_scale * scale_factor)
                else:
                    calculated_scale = scale_factor  # Fallback if no scale fcurves

                # Extract translation (location) data
                translation = [0, 0, 0]
                if location_fcurves:
                    translation = [
                        round(location_fcurves[i].keyframe_points[frame_idx].co[1] * scale_factor) 
                        for i in range(3)  # X, Y, Z translation
                    ]

                # Extract rotation (quaternion) data
                rotation = [16384, 0, 0, 0]  # Default identity quaternion
                if rotation_fcurves:
                    rotation = [
                        round(rotation_fcurves[i].keyframe_points[frame_idx].co[1] * rotation_factor) 
                        for i in range(4)  # W, X, Y, Z quaternion components
                    ]

                # Write the frame data
                file.write(f'\t\tFRAME {calculated_scale} {translation[0]} {translation[1]} {translation[2]} {rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]}\n')

            # Write NUMLEGACYFRAMES (default to 0)
            file.write(f'\tNUMLEGACYFRAMES 0\n')

            # Write TRACKINSTANCE for this bone
            file.write(f'\nTRACKINSTANCE "{track_instance_name}"\n')
            file.write(f'\tTAGINDEX {tag_index}\n')
            file.write(f'\tSPRITE "{track_def_name}"\n')
            file.write(f'\tSPRITEINDEX {definition_index}\n')
            file.write(f'\tINTERPOLATE {interpolate}\n')
            file.write(f'\tREVERSE {reverse}\n')

            # Calculate SLEEP time between keyframes
            if num_frames > 1:
                sleep_time = round((action.frame_range[1] - 1) / (num_frames - 1) * 1000 / bpy.context.scene.render.fps)  # milliseconds
            else:
                sleep_time = "NULL"
            file.write(f'\tSLEEP? {sleep_time}\n')

    # print("Animation export complete")
