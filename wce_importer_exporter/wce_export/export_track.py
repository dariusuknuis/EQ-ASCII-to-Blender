import bpy
from bpy_extras import anim_utils

def export_animation_data(armature_obj, file, action_filter=None):
    """Writes animation data for an armature to the specified file (Blender 5.0+)."""

    ad = armature_obj.animation_data
    if not ad or not ad.nla_tracks:
        print(f"No NLA tracks found for armature {armature_obj.name}.")
        return

    fps = bpy.context.scene.render.fps

    for nla_track in ad.nla_tracks:
        if getattr(nla_track, "mute", False):
            continue

        for strip in nla_track.strips:
            if getattr(strip, "type", "CLIP") != "CLIP":
                continue

            action = getattr(strip, "action", None)
            if action is None:
                continue

            if action_filter and not action.name.startswith(action_filter):
                continue

            # --- resolve slot for this strip/action ---
            slot = getattr(strip, "action_slot", None) or getattr(strip, "slot", None)
            if slot is None:
                # pick a suitable slot from the action
                slots = list(getattr(action, "slots", []))
                want_type = getattr(armature_obj, "id_type", None)
                slot = next((s for s in slots if getattr(s, "target_id_type", None) == want_type), None)
                if slot is None:
                    slot = next((s for s in slots if getattr(s, "target_id_type", None) in {"ARMATURE", "OBJECT"}), None)
                if slot is None and slots:
                    slot = slots[0]
            if slot is None:
                continue

            # --- get channelbag (Blender 5) using anim_utils ---
            cb = None
            try:
                cb = anim_utils.action_get_channelbag_for_slot(action, slot)
            except Exception:
                cb = None
            if cb is None:
                # last resort: ensure
                try:
                    cb = anim_utils.action_ensure_channelbag_for_slot(action, slot)
                except Exception:
                    cb = None
            if cb is None:
                continue

            cb_fcurves = getattr(cb, "fcurves", None)
            if cb_fcurves is None:
                continue

            # --- per-bone animation export (quat-only, with optional loc/scale) ---
            for bone in armature_obj.pose.bones:
                bone_name = bone.name
                stripped_bone_name = bone_name.replace('_DAG', '').replace('_ANIDAG', '').split('.')[0]

                # exact data paths
                loc_path  = bone.path_from_id("location")
                sca_path  = bone.path_from_id("scale")
                quat_path = bone.path_from_id("rotation_quaternion")

                # find fcurves in the channelbag
                location_fcurves  = [cb_fcurves.find(loc_path,  index=i) for i in range(3)]
                rotation_fcurves  = [cb_fcurves.find(quat_path, index=i) for i in range(4)]
                scale_fcurves     = [cb_fcurves.find(sca_path,  index=i) for i in range(3)]

                has_loc  = any(fc is not None for fc in location_fcurves)
                has_quat = any(fc is not None for fc in rotation_fcurves)
                if not has_loc and not has_quat:
                    continue

                # build a unified sorted frame list from all present channels
                frames_set = set()
                for arr in (location_fcurves, rotation_fcurves, scale_fcurves):
                    for fc in arr:
                        if fc is None:
                            continue
                        for kp in fc.keyframe_points:
                            frames_set.add(kp.co[0])
                frames = sorted(frames_set) if frames_set else [0.0]
                num_frames = len(frames)

                # track names & header
                action_prefix = "" if action.name.startswith("POS") else action.name.split('_')[0]
                track_def_name = f"{action_prefix}{stripped_bone_name}_TRACKDEF"
                track_instance_name = f"{action_prefix}{stripped_bone_name}_TRACK"

                file.write(f'\nTRACKDEFINITION "{track_def_name}"\n')

                tag_index = action.get("TAGINDEX", 0)
                definition_index = action.get("SPRITEINDEX", 0)
                interpolate = 1 if action.get("INTERPOLATE", True) else 0
                reverse = 1 if action.get("REVERSE", False) else 0

                file.write(f'\tTAGINDEX {tag_index}\n')
                file.write(f'\tNUMFRAMES {num_frames}\n')

                scale_factor = 256
                rotation_factor = 16384

                prev_quat = None

                for fr in frames:
                    # scale (avg xyz; default 1.0 each)
                    if any(fc is not None for fc in scale_fcurves):
                        sx = scale_fcurves[0].evaluate(fr) if scale_fcurves[0] else 1.0
                        sy = scale_fcurves[1].evaluate(fr) if scale_fcurves[1] else 1.0
                        sz = scale_fcurves[2].evaluate(fr) if scale_fcurves[2] else 1.0
                        average_scale = (sx + sy + sz) / 3.0
                    else:
                        average_scale = 1.0
                    calculated_scale = round(average_scale * scale_factor)

                    # translation (default 0s)
                    tx = location_fcurves[0].evaluate(fr) if location_fcurves[0] else 0.0
                    ty = location_fcurves[1].evaluate(fr) if location_fcurves[1] else 0.0
                    tz = location_fcurves[2].evaluate(fr) if location_fcurves[2] else 0.0
                    translation = [round(tx * scale_factor), round(ty * scale_factor), round(tz * scale_factor)]

                    # quaternion (default identity)
                    qw = rotation_fcurves[0].evaluate(fr) if rotation_fcurves[0] else 1.0
                    qx = rotation_fcurves[1].evaluate(fr) if rotation_fcurves[1] else 0.0
                    qy = rotation_fcurves[2].evaluate(fr) if rotation_fcurves[2] else 0.0
                    qz = rotation_fcurves[3].evaluate(fr) if rotation_fcurves[3] else 0.0

                    # normalize to be safe (Blender usually is, but this guarantees it)
                    length = (qw*qw + qx*qx + qy*qy + qz*qz) ** 0.5
                    if length != 0:
                        qw /= length
                        qx /= length
                        qy /= length
                        qz /= length

                    # Hemisphere continuity fix
                    if prev_quat is not None:
                        dot = (
                            prev_quat[0] * qw +
                            prev_quat[1] * qx +
                            prev_quat[2] * qy +
                            prev_quat[3] * qz
                        )

                        if dot < 0.0:
                            qw = -qw
                            qx = -qx
                            qy = -qy
                            qz = -qz

                    # Store for next iteration
                    prev_quat = (qw, qx, qy, qz)

                    rotation = [
                        round(qw * rotation_factor),
                        round(qx * rotation_factor),
                        round(qy * rotation_factor),
                        round(qz * rotation_factor),
                    ]

                    file.write(
                        f'\t\tFRAME {calculated_scale} '
                        f'{translation[0]} {translation[1]} {translation[2]} '
                        f'{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]}\n'
                    )

                file.write(f'\tNUMLEGACYFRAMES 0\n')

                # instance block
                file.write(f'\nTRACKINSTANCE "{track_instance_name}"\n')
                file.write(f'\tTAGINDEX {tag_index}\n')
                file.write(f'\tSPRITE "{track_def_name}"\n')
                file.write(f'\tSPRITEINDEX {definition_index}\n')
                file.write(f'\tINTERPOLATE {interpolate}\n')
                file.write(f'\tREVERSE {reverse}\n')

                if num_frames > 1:
                    sleep_time = round((action.frame_range[1] - 1) / (num_frames - 1) * 1000 / fps)
                else:
                    sleep_time = "NULL"
                file.write(f'\tSLEEP? {sleep_time}\n')
