import bpy
import mathutils
from mathutils import Quaternion

def create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices, prefix):
    # Get the scene's frame rate
    frame_rate = bpy.context.scene.render.fps

    # Create a default pose action
    action_name = f"POS_{prefix}"
    action = bpy.data.actions.new(name=action_name)

    # Ensure the armature has animation data and assign the action
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()

    # Create an NLA track for this action
    nla_tracks = armature_obj.animation_data.nla_tracks
    nla_track = nla_tracks.new()
    nla_track.name = action_name

    # Set a start frame for the NLA strip
    start_frame = 1  # Adjust as needed
    nla_strip = nla_track.strips.new(action_name, start=start_frame, action=action)
    nla_strip.action = action
    nla_strip.name = action_name

    fcurves = {}  # Initialize the fcurves dictionary

    #Iterate over the bones in the armature in order
    for bone_name, bone in armature_obj.pose.bones.items():
        # Check if the bone has a 'track' value
        track_name = bone.get('track', None)

        if track_name and track_name in track_definitions['armature_tracks']:
            # Retrieve the corresponding track definition and instance
            track_def = track_definitions['armature_tracks'][track_name]['definition']
            track_instance = track_definitions['armature_tracks'][track_name]['instance']

            # Get the sleep value for frame timing
            sleep = track_instance.get('sleep', None)
            frames_per_sleep = (sleep / 1000) * frame_rate if sleep else 1

            current_frame = start_frame

            # Iterate over all frames to create keyframes
            for frame_index, frame_data in enumerate(track_def['frames']):
                armature_translation = frame_data.get('translation', [0, 0, 0])
                armature_rotation = frame_data.get('rotation', Quaternion((1, 0, 0, 0)))
                xyz_scale = track_def.get('xyz_scale', 256)
                scale_factor = xyz_scale / 256.0

                # Create the transformation matrix
                scale_matrix = mathutils.Matrix.Scale(scale_factor, 4)
                rotation_matrix = armature_rotation.to_matrix().to_4x4()
                translation_matrix = mathutils.Matrix.Translation(armature_translation)

                bone_matrix = (
                    translation_matrix @ rotation_matrix @ scale_matrix @
                    cumulative_matrices.get(bone_name, mathutils.Matrix.Identity(4))
                )

                # Initialize fcurves for location, rotation, and scale
                if bone_name not in fcurves:
                    fcurves[bone_name] = {
                        'location': [],
                        'rotation_quaternion': [],
                        'scale': []
                    }

                    for i in range(3):  # Location and Scale
                        fcurves[bone_name]['location'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].location', index=i))
                        fcurves[bone_name]['scale'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].scale', index=i))

                    for i in range(4):  # Rotation quaternion
                        fcurves[bone_name]['rotation_quaternion'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].rotation_quaternion', index=i))

                # Extract translation, rotation, and scale
                translation = bone_matrix.to_translation()
                rotation = bone_matrix.to_quaternion()
                scale = [scale_factor] * 3

                # Insert keyframes for location, rotation, and scale
                for i, value in enumerate(translation):
                    fcurve = fcurves[bone_name]['location'][i]
                    kf = fcurve.keyframe_points.insert(current_frame, value)
                    kf.interpolation = 'LINEAR'

                for i, value in enumerate(rotation):
                    fcurve = fcurves[bone_name]['rotation_quaternion'][i]
                    kf = fcurve.keyframe_points.insert(current_frame, value)
                    kf.interpolation = 'LINEAR'

                for i, value in enumerate(scale):
                    fcurve = fcurves[bone_name]['scale'][i]
                    kf = fcurve.keyframe_points.insert(current_frame, value)
                    kf.interpolation = 'LINEAR'

                # Advance the current frame
                current_frame += frames_per_sleep

            # Add custom properties to the action
            action["TAGINDEX"] = track_instance.get('tag_index', 0)
            action["SPRITEINDEX"] = track_instance.get('definition_index', 0)
            action["INTERPOLATE"] = track_instance.get('interpolate', False)
            action["REVERSE"] = track_instance.get('reverse', False)

    #print(f"Created default pose action '{action_name}' with multiple keyframes")
