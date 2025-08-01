import shlex

def parse_material_definition(r, parse_property, current_line):
    material = {}
    
    # Parse MATERIALDEFINITION from the current line
    records = shlex.split(current_line)
    if records[0] != "MATERIALDEFINITION":
        raise Exception(f"Expected MATERIALDEFINITION, got {records[0]}")
    material['name'] = records[1]

    records = parse_property(r, "TAGINDEX", 1)
    material['tag_index'] = int(records[1])

    # Parse VARIATION
    records = parse_property(r, "VARIATION", 1)
    material['variation'] = int(records[1])

    # Parse RENDERMETHOD
    records = parse_property(r, "RENDERMETHOD", 1)
    material['rendermethod'] = records[1]

    # Parse RGBPEN
    records = parse_property(r, "RGBPEN", 4)
    material['rgbpen'] = (
        int(records[1]) / 255.0,
        int(records[2]) / 255.0,
        int(records[3]) / 255.0,
        int(records[4]) / 255.0
    )

    # Parse BRIGHTNESS
    records = parse_property(r, "BRIGHTNESS", 1)
    material['brightness'] = float(records[1])

    # Parse SCALEDAMBIENT
    records = parse_property(r, "SCALEDAMBIENT", 1)
    material['scaledambient'] = float(records[1])

    # Parse SIMPLESPRITEINST block
    records = parse_property(r, "SIMPLESPRITEINST", 0)

    # Parse TAG within SIMPLESPRITEINST
    records = parse_property(r, "SIMPLESPRITETAG", 1)
    material['texture_tag'] = records[1]

    records = parse_property(r, "SIMPLESPRITETAGINDEX", 1)
    material['simple_sprite_tag_index'] = int(records[1])

    # Parse HEXFIFTYFLAG
    records = parse_property(r, "SIMPLESPRITEHEXFIFTYFLAG", 1)
    material['hexfiftyflag'] = int(records[1])

    # Parse PAIRS? and handle NULL
    records = parse_property(r, "PAIRS?", 2)
    if records[1] != "NULL":
        material['pairs'] = (int(records[1]), float(records[2]))

    # Parse DOUBLESIDED
    records = parse_property(r, "DOUBLESIDED", 1)
    material['doublesided'] = int(records[1])

    return material
