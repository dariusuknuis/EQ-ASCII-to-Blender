import mathutils
import shlex

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

def format_tag_index(tag_index):
    """Format the tag index as .xxx where xxx = tag_index / 1000."""
    return f".{tag_index:03d}"

def generate_unique_name(model_prefix, existing_names):
    """Generate a unique name by adding a numerical suffix if needed."""
    if model_prefix not in existing_names:
        return model_prefix
    
    suffix = 1
    while True:
        new_name = f"{model_prefix}.{suffix:03d}"
        if new_name not in existing_names:
            return new_name
        suffix += 1

def track_parse(r, parse_property, model_prefix, current_line):
    track_definitions = {}
    animations = {}
    armature_tracks = {}

    # Parse TRACKDEFINITION from the current line
    records = shlex.split(current_line)
    if records[0] != "TRACKDEFINITION":
        raise Exception(f"Expected TRACKDEFINITION, got {records[0]}")
        
    track_def = {
        'name': records[1],
        'num_frames': 0,
        'frames': [],
        'legacy_frames': [],
        'xyz_scale': 256
    }

    # Parse TAGINDEX
    records = parse_property(r, "TAGINDEX", 1)
    tag_index = int(records[1])
    track_def['tag_index'] = tag_index

    # Append .xxx to track_def name if TAGINDEX > 0
    if tag_index > 0:
        track_def['name'] += format_tag_index(tag_index)

    # Parse NUMFRAMES
    records = parse_property(r, "NUMFRAMES", 1)
    track_def['num_frames'] = int(records[1])

    # Parse FRAME lines if NUMFRAMES > 0
    frames = []
    if track_def['num_frames'] > 0:
        for _ in range(track_def['num_frames']):
            # Parse each FRAME line with 8 values
            records = parse_property(r, "FRAME", 8)

            # Create a quaternion for the rotation
            rot_scale = float(records[5])
            rx = float(records[6])
            ry = float(records[7])
            rz = float(records[8])
            rotation = mathutils.Quaternion((rot_scale, rx, ry, rz))
            rotation.normalize()  # Normalize the quaternion

            # Parse and process the translation values (XYZ) divided by 256
            translation = (
                float(records[2]) / 256,
                float(records[3]) / 256,
                float(records[4]) / 256
            )

            # Store the translation and rotation in the frame_data
            frame_data = {
                'translation': translation,
                'rotation': rotation  # Store the quaternion rotation
            }

            frames.append(frame_data)

        # Store frames under track_def
        track_def['frames'] = frames

    # Store xyz_scale separately
    track_def['xyz_scale'] = int(records[1])

    # Parse NUMLEGACYFRAMES
    records = parse_property(r, "NUMLEGACYFRAMES", 1)
    track_def['num_legacy_frames'] = int(records[1])

    # Parse LEGACYFRAME lines if NUMLEGACYFRAMES > 0
    legacy_frames = []
    if track_def['num_legacy_frames'] > 0:
        for _ in range(track_def['num_legacy_frames']):
            records = parse_property(r, "LEGACYFRAME", 8)

            # Create a quaternion for the rotation
            rot_scale = float(records[5])
            rx = float(records[6])
            ry = float(records[7])
            rz = float(records[8])
            rotation = mathutils.Quaternion((rot_scale, rx, ry, rz))
            rotation.normalize()  # Normalize the quaternion

            # Parse and process the translation values (XYZ) divided by 256
            legacy_frame_data = {
                'xyz_scale': int(records[1]),
                'tx': int(records[2]) / 256,
                'ty': int(records[3]) / 256,
                'tz': int(records[4]) / 256,
                'rotation': rotation
            }
            legacy_frames.append(legacy_frame_data)
        track_def['legacy_frames'] = legacy_frames

    # Store the track definition
    track_definitions[track_def['name']] = track_def

    # Parse TRACKINSTANCE
    records = parse_property(r, "TRACKINSTANCE", 1)
    track_instance = {
        'name': records[1],
        'definition': '',
        'interpolate': False,
        'sleep': 0
    }

    # Parse TAGINDEX (inside TRACKINSTANCE)
    records = parse_property(r, "TAGINDEX", 1)
    instance_tag_index = int(records[1])
    track_instance['tag_index'] = instance_tag_index
    if instance_tag_index > 0:
        track_instance['name'] += format_tag_index(instance_tag_index)

    # Parse DEFINITION (inside TRACKINSTANCE)
    records = parse_property(r, "DEFINITION", 1)
    track_instance['definition'] = records[1]
    if instance_tag_index > 0:
        track_instance['definition'] += format_tag_index(instance_tag_index)

    # Parse DEFINITIONINDEX
    records = parse_property(r, "DEFINITIONINDEX", 1)
    track_instance['definition_index'] = int(records[1])

    # Parse INTERPOLATE
    records = parse_property(r, "INTERPOLATE", 1)
    track_instance['interpolate'] = bool(int(records[1]))

    # Parse REVERSE
    records = parse_property(r, "REVERSE", 1)
    track_instance['reverse'] = bool(int(records[1]))

    # Parse SLEEP?
    records = parse_property(r, "SLEEP?", 1)
    track_instance['sleep'] = int(records[1]) if records[1] != "NULL" else None

    # Determine whether the track is an animation or an armature track
    track_instance_name = track_instance['name']
    prefix = track_instance['name'].split(model_prefix)[0]

    if any(prefix.startswith(anim_prefix) for anim_prefix in animation_prefixes):
        animations[track_instance_name] = {
            'instance': track_instance,
            'definition': track_def,
            'animation_prefix': prefix  # Store the animation prefix
        }
        #print(f"Stored animation prefix '{prefix}' for track '{track_instance['name']}'")
    else:
        armature_tracks[track_instance['name']] = {
            'instance': track_instance,
            'definition': track_def
        }

    return {'animations': animations, 'armature_tracks': armature_tracks}