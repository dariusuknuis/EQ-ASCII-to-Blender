import bpy
import re
import mathutils

# Define the list of animation prefixes
animation_prefixes = [
    "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "D01", "D02", "D03",
    "D04", "D05", "L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08", "L09", "O01", "O02", "O03",
    "P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08", "S01", "S02", "S03", "S04", "S05", "T01",
    "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "S06", "S07", "S08", "S09", "S10", "S11",
    "S12", "S13", "S14", "S15", "S16", "S17", "S18", "S19", "S20", "S21", "S22", "S23", "S24", "S25",
    "S26", "S27", "S28", "S29"
]

# Create a new list that includes the variants with "A" and "B"
animation_prefix_variants = animation_prefixes + [prefix + "A" for prefix in animation_prefixes] + [prefix + "B" for prefix in animation_prefixes]

def generate_unique_name(base_name, existing_names):
    if base_name not in existing_names:
        return base_name
    
    suffix = 1
    while True:
        new_name = f"{base_name}.{suffix:03d}"
        if new_name not in existing_names:
            return new_name
        suffix += 1

def process_track_definition(r, parse_property, existing_track_definitions):
    track_def = {
        'name': '',
        'num_frames': 0,
        'frame_transforms': [],
        'xyz_scale': 256
    }
    
    frame_transform = None

    # Parse TAG
    records = parse_property(r, "TRACKDEFINITION", 1)
    base_name = records[1]
    track_def['name'] = generate_unique_name(base_name, existing_track_definitions)
    existing_track_definitions.add(track_def['name'])

    # Parse TAGINDEX
    records = parse_property(r, "TAGINDEX ", 1)
    track_def['tagindex'] = int(records[1])

    # Parse SPRITE
    records = parse_property(r, "SPRITE", 1)
    track_def['sprite'] = records[1]

    # Parse NUMFRAMES
    records = parse_property(r, "NUMFRAMES", 1)
    track_def['num_frames'] = int(records[1])

    # Parse FRAMETRANSFORM
    for i in range(track_def['num_frames']):
        records = parse_property(r, "FRAME", 8)
        xyz_scale = float(records[1])
        tx = float(records[2]) / 256
        ty = float(records[3]) / 256
        tz = float(records[4]) / 256
        rot_scale = float(records[5])
        rx = float(records[6])
        ry = float(records[7])
        rz = float(records[8])

        frame_transform = {
            'translation': (tx, ty, tz),
            'rotation': mathutils.Quaternion((rot_scale, rx, ry, rz))
        }
        frame_transform['rotation'].normalize()
        track_def['frame_transforms'].append(frame_transform)

    # Parse NUMLEGACYFRAMES and LEGACYFRAMES (if they exist)
    records = parse_property(r, "NUMLEGACYFRAMES", 1)
    num_legacy_frames = int(records[1])
    if num_legacy_frames > 0:
        for i in range(num_legacy_frames):
            records = parse_property(r, "LEGACYFRAME", 4)
            frame_transform['legacy_frame'] = list(map(float, records[1:5]))
            track_def['frame_transforms'].append(frame_transform)

    return track_def

def process_track_instance(r, parse_property, existing_track_instances, track_def_suffixes):
    track_instance = {
        'name': '',
        'definition': '',
        'interpolate': False,
        'sleep': 0
    }
    
    # Parse TAG
    records = parse_property(r, "TRACKINSTANCE", 1)
    base_name = records[1]
    track_instance['name'] = generate_unique_name(base_name, existing_track_instances)
    existing_track_instances.add(track_instance['name'])

    # Parse TAGINDEX
    records = parse_property(r, "TAGINDEX ", 1)
    track_instance['tagindex'] = int(records[1])

    # Parse SPRITE
    records = parse_property(r, "SPRITE", 1)
    track_instance['sprite'] = records[1]

    # Parse DEFINITION
    records = parse_property(r, "DEFINITION", 1)
    base_name = records[1]
    if base_name in track_def_suffixes:
        suffix = track_def_suffixes[base_name]
        new_definition_name = f"{base_name}.{suffix:03d}"
        track_instance['definition'] = new_definition_name
        track_def_suffixes[base_name] += 1
    else:
        track_instance['definition'] = base_name
        track_def_suffixes[base_name] = 1

    # Parse DEFINITIONINDEX
    records = parse_property(r, "DEFINITIONINDEX ", 1)
    track_instance['definitonindex'] = int(records[1])

    # Parse INTERPOLATE
    records = parse_property(r, "INTERPOLATE", 1)
    track_instance['interpolate'] = bool(int(records[1]))

    # Parse REVERSE
    records = parse_property(r, "REVERSE", 1)
    track_instance['reverse'] = bool(int(records[1]))

    # Parse SLEEP?
    records = parse_property(r, "SLEEP?", 1)
    track_instance['sleep'] = int(records[1]) if records[1] != "NULL" else None

    return track_instance

def track_parse(sections, base_name, parse_property):
    track_definitions = {}
    animations = {}
    armature_tracks = {}

    existing_track_definitions = set()
    existing_track_instances = set()
    track_def_suffixes = {}

    # Process TRACKDEFINITION sections
    for instance in sections.get('TRACKDEFINITION', []):
        track_def = process_track_definition(instance, parse_property, existing_track_definitions)
        track_definitions[track_def['name']] = track_def

    # Process TRACKINSTANCE sections
    for instance in sections.get('TRACKINSTANCE', []):
        track_instance = process_track_instance(instance, parse_property, existing_track_instances, track_def_suffixes)
        definition_name = track_instance['definition']

        track_def = track_definitions.get(definition_name)

        if track_def:
            # Extract the part before the base_name for comparison
            if base_name in track_instance['name']:
                prefix_part = track_instance['name'].split(base_name)[0]

                # Perform an exact match with the animation prefix variants
                if prefix_part in animation_prefix_variants:
                    animations[track_instance['name']] = {
                        'instance': track_instance,
                        'definition': track_def,
                        'animation_prefix': prefix_part  # Store the animation prefix
                    }
                    # Debugging: Ensure the prefix is stored correctly
                    print(f"Stored animation prefix '{prefix_part}' for track '{track_instance['name']}'")
                else:
                    armature_tracks[track_instance['name']] = {
                        'instance': track_instance,
                        'definition': track_def
                    }

    return {'animations': animations, 'armature_tracks': armature_tracks}

def build_animation(armature_obj, animations, frame_rate=30):
    for anim_name, anim_data in animations.items():
        track_instance = anim_data['instance']
        track_definition = anim_data['definition']
        animation_prefix = anim_data.get('animation_prefix', 'Unknown')
        num_frames = track_definition['num_frames']

        # Debugging: Print the animation prefix
        print(f"Building animation '{anim_name}' with prefix '{animation_prefix}'")

        # Create a new action for the animation
        action = bpy.data.actions.new(name=anim_name)
        armature_obj.animation_data_create()
        armature_obj.animation_data.action = action

        # Build the animation
        current_frame = 0
        for i, frame_transform in enumerate(track_definition['frame_transforms']):
            current_frame += (track_instance['sleep'] or 100) / 1000.0 * frame_rate
            frame = round(current_frame)

            for bone_name, bone in armature_obj.pose.bones.items():
                if bone_name in track_instance['name']:
                    bone.location = frame_transform['translation']
                    bone.rotation_quaternion = frame_transform['rotation']
                    bone.keyframe_insert(data_path="location", frame=frame)
                    bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                    break

        print(f"Animation '{anim_name}' created with {num_frames} frames.")

# Example usage after parsing the sections:
# base_name = "FRO"  # Replace with the actual base name from your model
# track_data = track_parse(sections, base_name, parse_property)
# build_animation(armature_obj, track_data['animations'], frame_rate=30)
