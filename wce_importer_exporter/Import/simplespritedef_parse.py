import shlex

def simplespritedef_parse(r, parse_property, current_line):
    texture = {}
    
    # Parse SIMPLESPRITEDEF from the current line
    records = shlex.split(current_line)
    if records[0] != "SIMPLESPRITEDEF":
        raise Exception(f"Expected SIMPLESPRITEDEF, got {records[0]}")
    texture['name'] = records[1]

    records = parse_property(r, "TAGINDEX", 1)
    texture['tag_index'] = int(records[1])
    
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

    frames = []

    # Process each frame.
    for _ in range(num_frames):
        # Parse the FRAME line.
        records = parse_property(r, "FRAME", 1)
        frame_tag = records[1].strip('"')
        frame = {
            'tag': frame_tag,
            'frame_files': []  # List of file entries for this frame.
        }
        
        # Parse the NUMFILES line for this frame.
        records = parse_property(r, "NUMFILES", 1)
        num_files = int(records[1])
        
        # Process each FILE line in this frame.
        for file_index in range(num_files):
            records = parse_property(r, "FILE", 1)
            file_name = records[1].strip('"')
            file_entry = {'file': file_name}
            
            # If there are more than 2 files, assume a fixed order:
            #   File 0: base file
            #   File 1: palette mask
            #   Files 2+: tiled files (with comma-separated parameters)
            if num_files > 2:
                if file_index == 1:
                    file_entry['type'] = 'palette_mask'
                elif file_index >= 2:
                    file_entry['type'] = 'tiled'
                    parts = file_name.split(", ")
                    if len(parts) >= 4:
                        try:
                            file_entry['color_index'] = int(parts[0]) - 1
                            file_entry['scale'] = int(parts[1]) * 10
                            file_entry['blend'] = int(parts[2])
                            # Use the fourth part as the actual file name.
                            file_entry['file'] = parts[3].strip()
                        except Exception:
                            # If parsing fails, leave the file_entry as is.
                            pass
            else:
                # For textures with one or two files, check for detail or layer markers.
                if "_LAYER" in file_name:
                    file_entry['type'] = 'layer'
                    file_entry['file'] = file_name.replace("_LAYER", "").strip()
                elif "_DETAIL" in file_name:
                    file_entry['type'] = 'detail'
                    parts = file_name.split("_DETAIL_")
                    if len(parts) > 1:
                        try:
                            file_entry['detail_value'] = float(parts[1])
                            file_entry['file'] = parts[0].strip()
                        except Exception as e:
                            print(f"Failed to extract detail_value from {file_name}: {e}")
            
            frame['frame_files'].append(file_entry)
        
        frames.append(frame)
    
    texture['frames'] = frames

    # For a single-frame texture that uses filed textures,
    # set the num_filed_textures property as num_files - 2.
    if num_frames == 1:
        single_frame_files = frames[0]['frame_files']
        if len(single_frame_files) > 2:
            texture['num_tiled_textures'] = len(single_frame_files) - 2
        else:
            texture['num_tiled_textures'] = 0
    else:
        texture['num_tiled_textures'] = 0

    return texture
