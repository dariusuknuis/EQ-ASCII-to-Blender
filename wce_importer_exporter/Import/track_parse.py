import mathutils
import shlex
import re

# Regex patterns for detecting animation prefixes and item models
regexAniPrefix = re.compile(r"^[CDLOPST](0[1-9]|[1-9][0-9])")
regexItemModel = re.compile(r"IT\d+")

# Store state variables between function calls
currentAniCode = ""
currentAniModelCode = ""
previousAnimations = {}

# Dummy strings from Go code for tag matching
dummy_strings = [
    "10404P0", "2HNSWORD", "BARDING", "BELT", "BODY", "BONE",
    "BOW", "BOX", "DUMMY", "HUMEYE", "MESH", "POINT", "POLYSURF",
    "RIDER", "SHOULDER"
]

# Regex patterns for item models (IT)
item_patterns = [
    r"^[CDLOPST](0[1-9]|[1-9][0-9])IT\d+_TRACK$",
    r"^[CDLOPST](0[1-9]|[1-9][0-9])_IT\d+_TRACK$",
    r"^([CDLOPST](0[1-9]|[1-9][0-9])){2}_IT\d+_TRACK$"
]

# Character model suffix matching rules (from Go)
character_suffixes = {
    "SED": ["FDD"],
    "FMP": ["PE", "CH", "NE", "HE", "BI", "FO", "TH", "CA", "BO"],
    "SKE": ["BI", "BO", "CA", "CH", "FA", "FI", "FO", "HA", "HE", "L_POINT",
            "NE", "PE", "R_POINT", "SH", "TH", "TO", "TU"]
}

# Special suffix rules for item models (non-character)
item_suffixes = {
    "IT157": ["SNA"],
    "IT61": ["WIP"]
}

# Animation parsing patterns
animation_patterns = [
    r"^[CDLOPST](0[1-9]|[1-9][0-9])[A-Z]{3}_TRACK$",
    r"^([CDLOPST](0[1-9]|[1-9][0-9])){2}[A-Z]{3}_TRACK$",
    r"^([CDLOPST](0[1-9]|[1-9][0-9])){2}_[A-Z]{3}_TRACK$",
    r"^[CDLOPST](0[1-9]|[1-9][0-9])[A-Z]{3}[CDLOPST](0[1-9]|[1-9][0-9])[A-Z]{3}_TRACK$",
    r"^[CDLOPST](0[1-9]|[1-9][0-9])[A-Z]{3}[CDLOPST](0[1-9]|[1-9][0-9])_[A-Z]{3}_TRACK$",
    r"^[CDLOPST](0[1-9]|[1-9][0-9])[A,B,G][A-Z]{3}[CDLOPST](0[1-9]|[1-9][0-9])[A,B,G]_[A-Z]{3}_TRACK$",
    r"^[CDLOPST](0[1-9]|[1-9][0-9])[A,B,G][CDLOPST](0[1-9]|[1-9][0-9])_[A-Z]{3}_TRACK$"
]


def track_animation_parse(tag, model_prefix):
    """Parses the track name and extracts the animation and model codes."""
    global currentAniCode, currentAniModelCode, previousAnimations

    # Determine if it's a character model (not an item model)
    is_character = not bool(regexItemModel.match(model_prefix))
    
    # Check if the tag starts with currentAniCode + currentAniModelCode
    combined_code = currentAniCode + currentAniModelCode
    if currentAniCode and currentAniModelCode and tag.startswith(combined_code):
        return currentAniCode, currentAniModelCode

    # Check against previousAnimations
    for previous in previousAnimations.keys():
        if tag.startswith(previous):
            parts = previous.split(":")
            if len(parts) == 2:
                currentAniCode, currentAniModelCode = parts[0], parts[1]
                return currentAniCode, currentAniModelCode
            
    # Check if tag starts with currentAniCode and contains a dummy string
    if currentAniCode:
        for dummy in dummy_strings:
            if tag.startswith(currentAniCode) and dummy in tag:
                return currentAniCode, currentAniModelCode

    # Handle special cases for character models
    if is_character:
        if tag.startswith(currentAniCode):
            if currentAniModelCode in character_suffixes:
                suffix_start_index = len(currentAniCode)
                for suffix in character_suffixes[currentAniModelCode]:
                    if tag[suffix_start_index:].startswith(suffix):
                        return currentAniCode, currentAniModelCode

        # Attempt regex pattern matching
        for i, pattern in enumerate(animation_patterns):
            if re.match(pattern, tag):
                if i == 0:
                    currentAniCode, currentAniModelCode = tag[:3], tag[3:6]
                elif i == 1:
                    currentAniCode, currentAniModelCode = tag[:3], tag[6:9]
                elif i == 2:
                    currentAniCode, currentAniModelCode = tag[:3], tag[7:10]
                elif i in [3, 4]:
                    currentAniCode, currentAniModelCode = tag[:3], tag[3:6]
                elif i == 5:
                    currentAniCode, currentAniModelCode = tag[:4], tag[4:7]
                elif i == 6:
                    currentAniCode, currentAniModelCode = tag[:4], tag[8:11]
                return currentAniCode, currentAniModelCode

        # Fallback for character models
        if len(tag) >= 6:
            currentAniCode, currentAniModelCode = tag[:3], tag[3:6]
            return currentAniCode, currentAniModelCode

    # Handle special cases for item models (isChr == false)
    if not is_character:
        if tag.startswith(currentAniCode):
            if currentAniModelCode in item_suffixes:
                if any(tag[3:].startswith(suffix) for suffix in item_suffixes[currentAniModelCode]):
                    return currentAniCode, currentAniModelCode

        # Check known item patterns
        for pattern in item_patterns:
            if re.match(pattern, tag):
                ani_code = tag[:3]
                model_match = re.search(r"IT\d+", tag)
                model_code = model_match.group(0) if model_match else None
                currentAniCode, currentAniModelCode = ani_code, model_code
                return currentAniCode, currentAniModelCode

    # Default fallback
    return "", ""


def format_tag_index(tag_index):
    """Format the tag index as .xxx where xxx = tag_index / 1000."""
    return f".{tag_index:03d}"

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
    records = parse_property(r, "SPRITE", 1)
    track_instance['definition'] = records[1]
    if instance_tag_index > 0:
        track_instance['definition'] += format_tag_index(instance_tag_index)

    # Parse DEFINITIONINDEX
    records = parse_property(r, "SPRITEINDEX", 1)
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
    is_animation = regexAniPrefix.match(track_instance_name)

    if is_animation:
        ani_prefix, model_name = track_animation_parse(track_instance_name, model_prefix)

        animations[track_instance_name] = {
            'instance': track_instance,
            'definition': track_def,
            'animation_prefix': ani_prefix,
            'model_name': model_name
        }
    else:
        armature_tracks[track_instance['name']] = {
            'instance': track_instance,
            'definition': track_def
        }

    return {'animations': animations, 'armature_tracks': armature_tracks}