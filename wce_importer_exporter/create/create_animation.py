import bpy
import mathutils
from mathutils import Quaternion
from .create_default_pose import _ensure_anim_and_action

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

def _ensure_curve(action, owner, data_path: str, index: int, group_name: str):
    """Get or create an F-Curve for `owner` (the armature object) on `action` in Blender 5+."""
    # Blender 5+ convenience: creates layer/strip/slot as needed and returns the F-Curve
    return action.fcurve_ensure_for_datablock(
        datablock=owner,
        data_path=data_path,
        index=index,
        group_name=group_name,
    )

def create_animation(armature_obj, track_definitions, armature_data, model_prefix):
    frame_rate  = bpy.context.scene.render.fps
    start_frame = 1

    # Group tracks by action key (animation_key + model_name)
    animations_by_key = {}
    for animation_name, animation_data in track_definitions['animations'].items():
        animation_key = animation_data.get('animation_prefix', animation_name[:3]).strip()
        model_name    = animation_data.get('model_name', model_prefix.strip())
        action_name   = f"{animation_key}_{model_name}"
        animations_by_key.setdefault(action_name, []).append(animation_data)

    # Process each action bucket
    for action_name, tracks in animations_by_key.items():
        anim, action = _ensure_anim_and_action(armature_obj, action_name)

        # Build an NLA strip that references this action (optional)
        nla_track = anim.nla_tracks.new()
        nla_track.name = action_name
        nla_strip = nla_track.strips.new(action_name, start_frame, action)
        nla_strip.name = action_name

        # Cache to avoid re-ensuring curves per bone
        ensured_curves = {}

        # Helper to get bone curves once
        def get_bone_curves(bone_name: str):
            if bone_name in ensured_curves:
                return ensured_curves[bone_name]
            loc = [_ensure_curve(action, armature_obj, f'pose.bones["{bone_name}"].location',            i, bone_name) for i in range(3)]
            rot = [_ensure_curve(action, armature_obj, f'pose.bones["{bone_name}"].rotation_quaternion', i, bone_name) for i in range(4)]
            scl = [_ensure_curve(action, armature_obj, f'pose.bones["{bone_name}"].scale',               i, bone_name) for i in range(3)]
            ensured_curves[bone_name] = (loc, rot, scl)
            return ensured_curves[bone_name]

        # We’ll attach metadata to the action using the first track’s instance if available
        first_instance_for_props = None

        for track_index, track_data in enumerate(tracks):
            track          = track_data['definition']
            track_instance = track_data['instance']
            track_inst_name = track_instance['name']
            if first_instance_for_props is None:
                first_instance_for_props = track_instance

            # Timing
            sleep = track_instance.get('sleep', None)
            frames_per_sleep = (sleep / 1000) * frame_rate if sleep else 1.0
            current_frame = 1

            # Determine animation_key used to strip from instance name
            animation_key = track_data.get('animation_prefix', track_inst_name[:3]).strip()

            # Derive bone/token names (matches your legacy logic)
            stripped_track_instance_name = track_inst_name[len(animation_key):].replace('_TRACK', '')

            if model_prefix not in stripped_track_instance_name:
                fallback = fallback_names.get(model_prefix)
                if fallback and fallback in stripped_track_instance_name:
                    modified_track_instance_name = stripped_track_instance_name.replace(fallback, model_prefix)
                else:
                    model_name = track_data.get('model_name', model_prefix)
                    modified_track_instance_name = model_name + stripped_track_instance_name
            else:
                modified_track_instance_name = stripped_track_instance_name

            if track_data.get('model_name', model_prefix) == "WOE":
                modified_track_instance_name = stripped_track_instance_name.replace("WOE", "WEL")

            # Resolve bone
            bone_name = None
            if track_index == 0 and len(armature_obj.pose.bones) > 0:
                bone_name = armature_obj.pose.bones[0].name
            else:
                for pb in armature_obj.pose.bones:
                    base = pb.name.replace('_DAG', '')
                    if base == stripped_track_instance_name:
                        bone_name = pb.name
                        break
                    if base == modified_track_instance_name:
                        bone_name = pb.name
                        stripped_track_instance_name = modified_track_instance_name
                        break
                    if pb.name.replace('_ANIDAG', '') == stripped_track_instance_name:
                        bone_name = pb.name
                        break

            # If not found and not first track, create an _ANIDAG child under parent
            if not bone_name and track_index != 0:
                bpy.ops.object.mode_set(mode='EDIT')
                parent_bone_name = stripped_track_instance_name[:-1] + '_DAG'
                parent_bone = armature_obj.data.edit_bones.get(parent_bone_name)
                if parent_bone:
                    anim_bone_name = f"{stripped_track_instance_name}_ANIDAG"
                    anim_bone = armature_obj.data.edit_bones.new(anim_bone_name)
                    anim_bone.head   = parent_bone.tail
                    anim_bone.tail   = anim_bone.head + mathutils.Vector((0, 0.1, 0))
                    anim_bone.parent = parent_bone
                bpy.ops.object.mode_set(mode='OBJECT')
                # retry match
                for pb in armature_obj.pose.bones:
                    if pb.name.replace('_ANIDAG', '') == stripped_track_instance_name:
                        bone_name = pb.name
                        break

            if not bone_name:
                # Couldn’t resolve a bone for this track; skip it
                continue

            loc_curves, rot_curves, scl_curves = get_bone_curves(bone_name)

            # Per-frame keys
            xyz_scale    = track.get('xyz_scale', 256)
            scale_factor = xyz_scale / 256.0

            for frame in track['frames']:
                # Frame data → transform
                arm_loc = frame.get('translation', [0, 0, 0])
                arm_rot = Quaternion(frame.get('rotation', [1, 0, 0, 0]))

                S = mathutils.Matrix.Scale(scale_factor, 4)
                R = arm_rot.to_matrix().to_4x4()
                T = mathutils.Matrix.Translation(arm_loc)
                bone_m = T @ R @ S

                translation = bone_m.to_translation()
                rotation    = bone_m.to_quaternion()
                scale_vec   = (scale_factor, scale_factor, scale_factor)

                # Insert keys
                for i, v in enumerate(translation):
                    kf = loc_curves[i].keyframe_points.insert(current_frame, float(v))
                    kf.interpolation = 'LINEAR'
                for i, v in enumerate(rotation):
                    kf = rot_curves[i].keyframe_points.insert(current_frame, float(v))
                    kf.interpolation = 'LINEAR'
                for i, v in enumerate(scale_vec):
                    kf = scl_curves[i].keyframe_points.insert(current_frame, float(v))
                    kf.interpolation = 'LINEAR'

                current_frame += frames_per_sleep

        # Action metadata (use the first instance in this action bucket if available)
        if first_instance_for_props:
            action["TAGINDEX"]    = first_instance_for_props.get('tag_index', 0)
            action["SPRITEINDEX"] = first_instance_for_props.get('definition_index', 0)
            action["INTERPOLATE"] = first_instance_for_props.get('interpolate', False)
            action["REVERSE"]     = first_instance_for_props.get('reverse', False)

        # Optional: detach active action if you only want NLA to drive playback
        try:
            if hasattr(anim, "action") and hasattr(anim.action, "action"):
                anim.action.action = None
            else:
                anim.action = None
        except Exception:
            pass