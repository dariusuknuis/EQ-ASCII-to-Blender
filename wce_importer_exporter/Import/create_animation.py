import bpy
import mathutils
from mathutils import Quaternion

fallback_names = {
    "HUM": "ELM", "HUF": "ELF", "BAM": "ELM", "BAF": "ELF", "ERM": "ELM", "ERF": "ELF",
    "HIM": "ELM", "HIF": "ELF", "DAM": "ELM", "DAF": "ELF", "HAM": "ELM", "HAF": "ELF",
    "TRM": "OGF", "TRF": "OGF", "OGM": "OGF", "HOM": "DWM", "HOF": "DWF", "GNM": "DWM",
    "GNF": "DWF", "BRM": "ELM", "BRF": "ELF", "GOM": "GIA", "GOL": "GIA", "BET": "SPI",
    "CPF": "CPM", "FRG": "FRO", "GAM": "GAR", "GHU": "GOB", "FPM": "ELM", "IMP": "GAR",
    "GRI": "DRK", "KOB": "WER", "LIF": "LIM", "MIN": "GNN", "BGM": "ELM", "PIF": "FAF",
    "BGG": "KGO", "SKE": "ELM", "TIG": "LIM", "HHM": "ELM", "ZOM": "ELM", "ZOF": "ELF",
    "QCM": "ELM", "QCF": "ELF", "PUM": "LIM", "NGM": "ELM", "EGM": "ELM", "RIM": "DWM",
    "RIF": "DWF", "SKU": "RAT", "SPH": "DRK", "ARM": "RAT", "CLM": "DWM", "CLF": "DWF",
    "CL": "DWM", "HLM": "ELM", "HLF": "ELF", "GRM": "OGF", "GRF": "OGF", "OKM": "OGF",
    "OKF": "OGF", "KAM": "DWM", "KAF": "DWF", "KA": "DWM", "FEM": "ELM", "FEF": "ELF",
    "GFM": "ELM", "GFF": "ELF", "STC": "LIM", "IKF": "IKM", "ICM": "IKM", "ICF": "IKM",
    "ICN": "IKM", "ERO": "ELF", "TRI": "ELM", "BRI": "DWM", "FDF": "FDR", "SSK": "SRW",
    "VRF": "VRM", "WUR": "DRA", "IKS": "IKM", "IKH": "REA", "FMO": "DRK", "BTM": "RHI",
    "SDE": "DML", "TOT": "SCA", "SPC": "SPE", "ENA": "ELM", "YAK": "GNN", "COM": "DWM",
    "COF": "DWF", "COK": "DWM", "DR2": "TRK", "HAG": "ELF", "SIR": "ELF", "STG": "FSG",
    "CCD": "TRK", "ABH": "ELF", "BWD": "TRK", "GDR": "DRA", "PRI": "TRK", "FEL": "AEL",
    "SHN": "SHM", "SUN": "SNN", "FAN": "GNN", "CPM": "GNN", "SHF": "SHM", "MTC": "LIM" 
}

def create_animation(armature_obj, track_definitions, armature_data, model_prefix):
    # Get the scene's frame rate
    frame_rate = bpy.context.scene.render.fps

    # Group tracks by their animation key and model prefix
    animations_by_key = {}

    for animation_name, animation_data in track_definitions['animations'].items():
        animation_key = animation_data.get('animation_prefix', animation_name[:3]).strip()
        model_name = animation_data.get('model_name', model_prefix.strip())  # Use stored model_name, fallback to model_prefix

        action_name = f"{animation_key}_{model_name}"

        if action_name not in animations_by_key:
            animations_by_key[action_name] = []
        
        animations_by_key[action_name].append(animation_data)

    # Create actions for each animation key
    for action_name, tracks in animations_by_key.items():
        action = bpy.data.actions.new(name=action_name)
        
        # Assign the action to the armature to ensure it has a user
        if armature_obj.animation_data is None:
            armature_obj.animation_data_create()
        
        # Create an NLA track for this action
        nla_tracks = armature_obj.animation_data.nla_tracks
        nla_track = nla_tracks.new()
        nla_track.name = action_name
        
        # Set a start frame for the NLA strip (you can modify this value as needed)
        start_frame = 1  # Adjust this to your desired start frame
        nla_strip = nla_track.strips.new(action_name, start=start_frame, action=action)
        nla_strip.action = action
        nla_strip.name = action_name

        fcurves = {}

        # Go through each track in the animation data
        for track_index, track_data in enumerate(tracks):
            track = track_data['definition']
            track_instance = track_data['instance']
            track_instance_name = track_instance['name']
            sleep = track_instance.get('sleep', None)

            # Determine frames_per_sleep only if sleep is not None
            frames_per_sleep = 1
            if sleep is not None:
                frames_per_sleep = (sleep / 1000) * frame_rate

            current_frame = 1

            # Strip the animation prefix and '_TRACK' from the track instance name
            stripped_track_instance_name = track_instance_name[len(animation_key):].replace('_TRACK', '')

            # Check if the track contains the model name
            if model_prefix not in stripped_track_instance_name:
                fallback_name = fallback_names.get(model_prefix, None)
                
                if fallback_name and fallback_name in stripped_track_instance_name:
                    modified_track_instance_name = stripped_track_instance_name.replace(fallback_name, model_prefix)
                else:
                    modified_track_instance_name = model_name + stripped_track_instance_name
            else:
                modified_track_instance_name = stripped_track_instance_name
            
            if model_name == "WOE":
                modified_track_instance_name = stripped_track_instance_name.replace("WOE", "WEL")

            # Identify which bone this track belongs to
            bone_name = None

            # Force matching the first track to the first bone in the armature
            if track_index == 0:
                first_bone = armature_obj.pose.bones[0]
                bone_name = first_bone.name
            else:
                for bone in armature_obj.pose.bones:
                    stripped_bone_name = bone.name.replace('_DAG', '')

                    if stripped_bone_name == stripped_track_instance_name:
                        bone_name = bone.name
                        break
                    elif stripped_bone_name == modified_track_instance_name:
                        bone_name = bone.name
                        stripped_track_instance_name = modified_track_instance_name
                        break
                    elif bone.name.replace('_ANIDAG', '') == stripped_track_instance_name:
                        bone_name = bone.name
                        break

            if not bone_name and track_index != 0:  # Only create new bone if it's not the first track
                # Create new animation-only bone with "_ANIDAG"
                bpy.ops.object.mode_set(mode='EDIT')
                parent_bone_name = stripped_track_instance_name[:-1] + '_DAG'
                parent_bone = armature_obj.data.edit_bones.get(parent_bone_name)

                if parent_bone:
                    anim_bone_name = f"{stripped_track_instance_name}_ANIDAG"
                    anim_bone = armature_obj.data.edit_bones.new(anim_bone_name)
                    anim_bone.head = parent_bone.tail
                    anim_bone.tail = anim_bone.head + mathutils.Vector((0, 0.1, 0))
                    anim_bone.parent = parent_bone
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # After creating the animation bone, retry matching
                    for bone in armature_obj.pose.bones:
                        stripped_bone_name = bone.name.replace('_ANIDAG', '')
                        if stripped_bone_name == stripped_track_instance_name:
                            bone_name = bone.name
                            break

            if bone_name:
                if bone_name not in fcurves:
                    fcurves[bone_name] = {
                        'location': [],
                        'rotation_quaternion': [],
                        'scale': []
                    }

                    for i in range(3):
                        fcurves[bone_name]['location'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].location', index=i))
                        fcurves[bone_name]['scale'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].scale', index=i))

                    for i in range(4):
                        fcurves[bone_name]['rotation_quaternion'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].rotation_quaternion', index=i))

                for frame_index, frame in enumerate(track['frames']):
                    location = frame.get('translation', [0, 0, 0])
                    frame_rotation = mathutils.Quaternion(frame.get('rotation', [1, 0, 0, 0]))
                    xyz_scale = track.get('xyz_scale', 256)
                    scale_factor = xyz_scale / 256.0

                    scale_matrix = mathutils.Matrix.Scale(scale_factor, 4)
                    rotation_matrix = frame_rotation.to_matrix().to_4x4()
                    translation_matrix = mathutils.Matrix.Translation(location)

                    bone_matrix = translation_matrix @ rotation_matrix @ scale_matrix

                    translation = bone_matrix.to_translation()
                    rotation = bone_matrix.to_quaternion()
                    scale = [scale_factor] * 3

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

                    current_frame += frames_per_sleep

        # Add custom properties to the NLA strip
        action["TAGINDEX"] = track_instance.get('tag_index', 0)
        action["SPRITEINDEX"] = track_instance.get('definition_index', 0)
        action["INTERPOLATE"] = track_instance.get('interpolate', False)
        action["REVERSE"] = track_instance.get('reverse', False)

    #print("Animation creation complete")