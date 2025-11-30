import bpy
import mathutils
from mathutils import Quaternion

def _ensure_anim_and_action(armature_obj, action_name: str):
    """Return (anim, action) correctly wired for Blender 5 slotted actions, with 3.6 fallback."""
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    anim = armature_obj.animation_data

    # Create action
    action = bpy.data.actions.new(action_name)

    # Blender 5: add an OBJECT slot so Blender knows what this action targets
    # (Pose-bone paths still live on the OBJECT owner.)
    if hasattr(action, "slots"):
        if not any(s.target_id_type == 'OBJECT' for s in action.slots):
            action.slots.new(id_type='OBJECT', name=armature_obj.name)

    # Assign to anim; in 5.0 this does NOT always auto-pick a slot, so set it.
    anim.action = action
    try:
        # Prefer a suitable slot (guaranteed compatible)
        if hasattr(anim, "action_suitable_slots") and anim.action_suitable_slots:
            anim.action_slot = anim.action_suitable_slots[0]
        elif hasattr(action, "slots") and action.slots:
            anim.action_slot = action.slots[0]
    except Exception:
        # If the build auto-assigned, this may be unnecessary.
        pass

    return anim, action

def create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices, prefix):
    frame_rate  = bpy.context.scene.render.fps
    start_frame = 1

    # Set up action & slot correctly
    action_name = f"POS_{prefix}"
    anim, action = _ensure_anim_and_action(armature_obj, action_name)

    # Pose bones animate in quaternion space here
    for pb in armature_obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'

    # Build curves per bone using the **new** API
    def ensure_curve(dp: str, idx: int, group: str):
        """
        Blender 5: use fcurve_ensure_for_datablock (creates layer/strip/slot if needed).
        Blender 3.6: legacy method exists too; signature is slightly different but
        the keyword-only form works in 5.0: (datablock, data_path, *, index=..., group_name=...)
        """
        return action.fcurve_ensure_for_datablock(
            datablock=armature_obj,
            data_path=dp,
            index=idx,
            group_name=group,
        )

    # Iterate only bones with tracks
    for bone_name, pb in armature_obj.pose.bones.items():
        track_name = pb.get('track', None)
        if not (track_name and track_name in track_definitions['armature_tracks']):
            continue

        track_def  = track_definitions['armature_tracks'][track_name]['definition']
        track_inst = track_definitions['armature_tracks'][track_name]['instance']

        sleep_ms        = track_inst.get('sleep', None)
        frames_per_step = (sleep_ms / 1000) * frame_rate if sleep_ms else 1
        current_frame   = start_frame

        # Ensure curves once per bone
        loc_curves = [ensure_curve(f'pose.bones["{bone_name}"].location',            i, bone_name) for i in range(3)]
        rot_curves = [ensure_curve(f'pose.bones["{bone_name}"].rotation_quaternion', i, bone_name) for i in range(4)]
        scl_curves = [ensure_curve(f'pose.bones["{bone_name}"].scale',               i, bone_name) for i in range(3)]

        xyz_scale    = track_def.get('xyz_scale', 256)
        scale_factor = xyz_scale / 256.0

        for frame_data in track_def['frames']:
            arm_translation = frame_data.get('translation', [0, 0, 0])
            arm_rotation    = frame_data.get('rotation', Quaternion((1, 0, 0, 0)))

            # Compose transform in your space
            S = mathutils.Matrix.Scale(scale_factor, 4)
            R = arm_rotation.to_matrix().to_4x4()
            T = mathutils.Matrix.Translation(arm_translation)
            bone_m = T @ R @ S @ cumulative_matrices.get(bone_name, mathutils.Matrix.Identity(4))

            translation = bone_m.to_translation()
            rotation    = bone_m.to_quaternion()
            scale_vec   = (scale_factor, scale_factor, scale_factor)

            # Insert keyframes on the F-Curves we ensured
            for i, v in enumerate(translation):
                kf = loc_curves[i].keyframe_points.insert(current_frame, float(v))
                kf.interpolation = 'LINEAR'
            for i, v in enumerate(rotation):
                kf = rot_curves[i].keyframe_points.insert(current_frame, float(v))
                kf.interpolation = 'LINEAR'
            for i, v in enumerate(scale_vec):
                kf = scl_curves[i].keyframe_points.insert(current_frame, float(v))
                kf.interpolation = 'LINEAR'

            current_frame += frames_per_step

        # Optional metadata on the Action (works fine with slots)
        action["TAGINDEX"]    = track_inst.get('tag_index', 0)
        action["SPRITEINDEX"] = track_inst.get('definition_index', 0)
        action["INTERPOLATE"] = track_inst.get('interpolate', False)
        action["REVERSE"]     = track_inst.get('reverse', False)

    # (Optional) Also add an NLA strip that references the same action
    nla_track = anim.nla_tracks.new()
    nla_track.name = action.name
    strip = nla_track.strips.new(action.name, start_frame, action)
    strip.name = action.name

    # If you prefer NLA-only control, you can detach the active action here.
    try:
        # Blender 5 may expose an ActionSlot at anim.action; detach safely:
        if hasattr(anim, "action") and hasattr(anim.action, "action"):
            anim.action.action = None
        else:
            anim.action = None
    except Exception:
        pass
