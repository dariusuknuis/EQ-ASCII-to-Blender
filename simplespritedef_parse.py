import re

def simplespritedef_parse(r, parse_property):
    texture = {}

    # Parse SIMPLESPRITEDEF
    records = parse_property(r, "SIMPLESPRITEDEF", 1)
    texture['name'] = records[1]
    
    # Parse VARIATION
    records = parse_property(r, "VARIATION", 1)
    texture['variation'] = int(records[1])
    
    # Parse SKIPFRAMES? (nullable)
    records = parse_property(r, "SKIPFRAMES?", 1)
    if records[1] != "NULL":
        texture['skipframes'] = int(records[1])

    # Parse ANIMATED? (nullable)
    records = parse_property(r, "ANIMATED?", 1)
    if records[1] != "NULL":
        texture['animated_flag'] = int(records[1])
    
    # Parse SLEEP?
    records = parse_property(r, "SLEEP?", 1)
    if records[1] == "NULL":
        texture['sleep'] = None
        texture['animated'] = False
    else:
        sleep_value = int(records[1])
        texture['sleep'] = sleep_value
        texture['animated'] = sleep_value > 0

    # Parse CURRENTFRAME? (nullable)
    records = parse_property(r, "CURRENTFRAME?", 1)
    if records[1] != "NULL":
        texture['current_frame'] = int(records[1])

    # Parse NUMFRAMES
    records = parse_property(r, "NUMFRAMES", 1)
    num_frames = int(records[1])
    texture['num_frames'] = num_frames

    # Initialize variables to hold frame details
    frame_files = []
    frames = []
    animated_frame_count = 0
    tiled_frame_count = 0
    animated_frame_regex = re.compile(r'.*\d(?=\.[a-zA-Z]+$)')

    # Parse FRAME lines for the given number of frames
    for i in range(num_frames):
        records = parse_property(r, "FRAME", 2)
        frame_file = records[1].strip()
        frame_data = {'file': frame_file}

        # Determine the frame type based on the file name
        if "_LAYER" in frame_file:
            frame_data['type'] = 'layer'
            frame_data['file'] = frame_file.replace("_LAYER", "").strip()
        elif "_DETAIL" in frame_file:
            detail_value = frame_file.split('_DETAIL_')[1]
            frame_data['type'] = 'detail'
            frame_data['detail_value'] = float(detail_value)
            frame_data['file'] = frame_file.split('_DETAIL_')[0].strip()
        elif "PAL.BMP" in frame_file:
            previous_file = frames[-1]['file'] if frames else ''
            if previous_file.split('.')[0] == frame_file.replace("PAL.BMP", "").strip():
                frame_data['type'] = 'palette_mask'
                frame_data['file'] = frame_file
                texture['palette_mask_file'] = frame_file  # Store palette mask file separately
        elif "," in frame_file:
            # Handle tiled frames
            num_values, file_name = frame_file.split(", ", 3)[-1], frame_file.split(", ", 3)[-1]
            numbers = frame_file.split(", ")[:3]
            frame_data['type'] = 'tiled'
            frame_data['color_index'] = int(numbers[0]) - 1
            frame_data['scale'] = int(numbers[1]) * 10
            frame_data['blend'] = int(numbers[2])
            frame_data['file'] = file_name.strip()
            tiled_frame_count += 1
        else:
            # Check if this is an animated frame
            if texture['animated'] and animated_frame_regex.match(frame_file):
                animated_frame_count += 1
                frame_data['animation_frame'] = animated_frame_count

        # Save frame data and file names
        frames.append(frame_data)
        frame_files.append(frame_data['file'])

    # Store the frames and frame file names in the texture
    texture['frames'] = frames
    texture['frame_files'] = frame_files
    texture['number_frames'] = animated_frame_count  # Calculated from animated frames
    texture['num_tiled_frames'] = tiled_frame_count  # Calculated from tiled frames

    return texture
