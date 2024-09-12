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

def track_parse(r, parse_property, base_name):
    track_definitions = {}
    animations = {}
    armature_tracks = {}

    existing_track_definitions = set()
    existing_track_instances = set()
    track_def_suffixes = {}

    # Parse TRACKDEFINITION
    records = parse_property(r, "TRACKDEFINITION", 1)
    track_def = {
        'name': records[1],
        'num_frames': 0,
        'frames': [],
        'legacy_frames': [],
        'xyz_scale': 256
    }

    # Parse TAGINDEX
    records = parse_property(r, "TAGINDEX", 1)
    track_def['tag_index'] = int(records[1])

    # Parse SPRITE
    records = parse_property(r, "SPRITE", 1)
    track_def['sprite'] = records[1]

    # Parse NUMFRAMES
    records = parse_property(r, "NUMFRAMES", 1)
    track_def['num_frames'] = int(records[1])

    # Parse FRAME lines if NUMFRAMES > 0
    frames = []
    if track_def['num_frames'] > 0:
        for _ in range(track_def['num_frames']):
            records = parse_property(r, "FRAME", 8)
            frame_data = {
                'xyz_scale': int(records[1]),
                'tx': int(records[2]),
                'ty': int(records[3]),
                'tz': int(records[4]),
                'rot_scale': int(records[5]),
                'rx': int(records[6]),
                'ry': int(records[7]),
                'rz': int(records[8])
            }
            frames.append(frame_data)
        track_def['frames'] = frames

    # Parse NUMLEGACYFRAMES
    records = parse_property(r, "NUMLEGACYFRAMES", 1)
    track_def['num_legacy_frames'] = int(records[1])

    # Parse LEGACYFRAME lines if NUMLEGACYFRAMES > 0
    legacy_frames = []
    if track_def['num_legacy_frames'] > 0:
        for _ in range(track_def['num_legacy_frames']):
            records = parse_property(r, "LEGACYFRAME", 7)
            legacy_frame_data = {
                'xyz_scale': int(records[1]),
                'tx': int(records[2]),
                'ty': int(records[3]),
                'tz': int(records[4]),
                'rot_scale': float(records[5]),
                'rotation': (float(records[6]), float(records[7]), float(records[8]))
            }
            legacy_frames.append(legacy_frame_data)
        track_def['legacy_frames'] = legacy_frames

    # Add track definition to track_definitions
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
    track_instance['tag_index'] = int(records[1])

    # Parse SPRITE (inside TRACKINSTANCE)
    records = parse_property(r, "SPRITE", 1)
    track_instance['sprite'] = records[1]

    # Parse DEFINITION (inside TRACKINSTANCE)
    records = parse_property(r, "DEFINITION", 1)
    track_instance['definition'] = records[1]

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
    track_def = track_definitions.get(track_instance['definition'])

    if track_def:
        if base_name in track_instance['name']:
            prefix_part = track_instance['name'].split(base_name)[0]

            # Perform an exact match with the animation prefix variants
            if prefix_part in animation_prefix_variants:
                animations[track_instance['name']] = {
                    'instance': track_instance,
                    'definition': track_def,
                    'animation_prefix': prefix_part  # Store the animation prefix
                }
                print(f"Stored animation prefix '{prefix_part}' for track '{track_instance['name']}'")
            else:
                armature_tracks[track_instance['name']] = {
                    'instance': track_instance,
                    'definition': track_def
                }

    return {'animations': animations, 'armature_tracks': armature_tracks}
