import bpy
import mathutils
from mathutils import Quaternion

def create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices, prefix):
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

    # Set a start frame for the NLA strip (default pose should typically start at frame 1)
    start_frame = 1  # Set this as appropriate for your needs
    nla_strip = nla_track.strips.new(action_name, start=start_frame, action=action)
    nla_strip.action = action
    nla_strip.name = action_name

    fcurves = {}  # Initialize the fcurves dictionary

    # Loop through the bones in the armature and create default pose keyframes
    for bone_name, bone in armature_obj.pose.bones.items():
        stripped_bone_name = bone_name.replace('_DAG', '')
        corresponding_bone = next((b for b in armature_data['bones'] if b['name'] == bone_name), None)

        if corresponding_bone:
            track_name = corresponding_bone['track']
            track_def = track_definitions['armature_tracks'][track_name]['definition']
            initial_transform = track_def['frames'][0]

            armature_translation = initial_transform.get('translation', [0, 0, 0])
            armature_rotation = initial_transform.get('rotation', Quaternion((1, 0, 0, 0)))
            xyz_scale = track_def.get('xyz_scale', 256)
            scale_factor = xyz_scale / 256.0

            # Create a matrix that applies the cumulative matrix, translation, rotation, and scale
            scale_matrix = mathutils.Matrix.Scale(scale_factor, 4)
            rotation_matrix = armature_rotation.to_matrix().to_4x4()
            translation_matrix = mathutils.Matrix.Translation(armature_translation)

            # Combine the matrices in the correct order: Translation * Rotation * Scale * Cumulative Matrix
            bone_matrix = translation_matrix @ rotation_matrix @ scale_matrix @ cumulative_matrices.get(bone_name, mathutils.Matrix.Identity(4))

            # Initialize fcurves for location, rotation, and scale
            if bone_name not in fcurves:
                fcurves[bone_name] = {
                    'location': [],
                    'rotation_quaternion': [],
                    'scale': []
                }

                # Create fcurves for location, rotation, and scale
                for i in range(3):  # Location and Scale have 3 components: X, Y, Z
                    fcurves[bone_name]['location'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].location', index=i))
                    fcurves[bone_name]['scale'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].scale', index=i))

                for i in range(4):  # Rotation quaternion has 4 components: W, X, Y, Z
                    fcurves[bone_name]['rotation_quaternion'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].rotation_quaternion', index=i))

            # Extract translation, rotation, and scale from the bone matrix
            translation = bone_matrix.to_translation()
            rotation = bone_matrix.to_quaternion()
            scale = [scale_factor] * 3  # Apply the scaling factor uniformly on all axes

            # Insert location keyframes
            for i, value in enumerate(translation):
                fcurve = fcurves[bone_name]['location'][i]
                kf = fcurve.keyframe_points.insert(1, value)
                kf.interpolation = 'LINEAR'

            # Insert rotation keyframes
            for i, value in enumerate(rotation):
                fcurve = fcurves[bone_name]['rotation_quaternion'][i]
                kf = fcurve.keyframe_points.insert(1, value)
                kf.interpolation = 'LINEAR'

            # Insert scale keyframes
            for i, value in enumerate(scale):
                fcurve = fcurves[bone_name]['scale'][i]
                kf = fcurve.keyframe_points.insert(1, value)
                kf.interpolation = 'LINEAR'

    print(f"Created default pose action '{action_name}'")