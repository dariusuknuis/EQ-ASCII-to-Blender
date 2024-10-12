import bpy
import mathutils

def export_animation_data(armature_obj, file, frame_rate=30):
    # Get the armature object and its associated animation data
    actions = bpy.data.actions

    for action in actions:
        if action.users == 0:
            continue  # Skip if action is not assigned to any object
        
        # Ensure the armature object has animation data
        if armature_obj.animation_data is None:
            armature_obj.animation_data_create()
        
        # Write TRACKDEFINITION and TRACKINSTANCE for each bone in the armature
        for bone in armature_obj.pose.bones:
            bone_name = bone.name

            # Strip off any .001, .002 suffixes and remove _DAG or _ANIDAG
            stripped_bone_name = bone_name.replace('_DAG', '').replace('_ANIDAG', '').split('.')[0]

            # Filter the fcurves for the current action and this bone
            location_fcurves = [fcurve for fcurve in action.fcurves if f'pose.bones["{bone_name}"].location' in fcurve.data_path]
            rotation_fcurves = [fcurve for fcurve in action.fcurves if f'pose.bones["{bone_name}"].rotation_quaternion' in fcurve.data_path]
            
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

            # Add newlines before TRACKDEFINITION and TRACKINSTANCE
            file.write(f'\nTRACKDEFINITION "{track_def_name}"\n')

            # Write action custom properties if they exist
            tag_index = action.get("TAGINDEX", 0)
            sprite = action.get("SPRITE", "")
            definition_index = action.get("DEFINITIONINDEX", 0)
            interpolate = 1 if action.get("INTERPOLATE", True) else 0
            reverse = 1 if action.get("REVERSE", False) else 0

            file.write(f'\tTAGINDEX {tag_index}\n')
            file.write(f'\tSPRITE "{sprite}"\n')
            file.write(f'\tNUMFRAMES {num_frames}\n')

            # Extract keyframe data for the bone
            for frame_idx in range(num_frames):
                scale_factor = 256
                rotation_factor = 16384
                
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
                file.write(f'\t\tFRAME {scale_factor} {translation[0]} {translation[1]} {translation[2]} {rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]}\n')

            # Write NUMLEGACYFRAMES (default to 0)
            file.write(f'\tNUMLEGACYFRAMES 0\n')

            # Write TRACKINSTANCE for this bone
            file.write(f'\nTRACKINSTANCE "{track_instance_name}"\n')
            file.write(f'\tTAGINDEX {tag_index}\n')
            file.write(f'\tSPRITE "{sprite}"\n')
            file.write(f'\tDEFINITION "{track_def_name}"\n')
            file.write(f'\tDEFINITIONINDEX {definition_index}\n')
            file.write(f'\tINTERPOLATE {interpolate}\n')
            file.write(f'\tREVERSE {reverse}\n')

            # Calculate SLEEP time between keyframes
            if num_frames > 1:
                sleep_time = round((action.frame_range[1] - 1) / (num_frames - 1) * 1000 / frame_rate)  # milliseconds
            else:
                sleep_time = "NULL"
            file.write(f'\tSLEEP? {sleep_time}\n')

    print("Animation export complete")


# Example call to export animation data
output_file = r"C:\Users\dariu\Documents\Quail\Exporter\fro_ani.export.wce"
armature = bpy.context.object  # Assume the armature is the active object

with open(output_file, 'w') as file:
    export_animation_data(armature, file, frame_rate=bpy.context.scene.render.fps)

print(f"Animation data exported to {output_file}")
