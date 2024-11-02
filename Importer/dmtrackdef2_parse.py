import shlex

def dmtrackdef2_parse(r, parse_property, current_line):
    vertex_animation = {}

    # Parse DMTRACKDEF2 from the data
    records = shlex.split(current_line)
    if records[0] != "DMTRACKDEF2":
        raise Exception(f"Expected DMTRACKDEF2, got {records[0]}")
    vertex_animation['name'] = records[1]

    # Parse SLEEP
    records = parse_property(r, "SLEEP", 1)
    vertex_animation['sleep'] = int(records[1])

    # Parse PARAM2, FPSCALE, SIZE6
    records = parse_property(r, "PARAM2", 1)
    vertex_animation['param2'] = int(records[1])
    records = parse_property(r, "FPSCALE", 1)
    vertex_animation['fpscale'] = int(records[1])
    records = parse_property(r, "SIZE6", 1)
    vertex_animation['size6'] = int(records[1])

    # Parse NUMFRAMES and each frame's vertices
    records = parse_property(r, "NUMFRAMES", 1)
    num_frames = int(records[1])
    frames = []
    for frame_index in range(num_frames):
        records = parse_property(r, "NUMVERTICES", 1)
        num_vertices = int(records[1])
        vertices = []
        for _ in range(num_vertices):
            records = parse_property(r, "XYZ", 3)
            vertices.append(tuple(map(float, records[1:])))
        frames.append(vertices)
    vertex_animation['frames'] = frames

    return vertex_animation
