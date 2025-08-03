import shlex

def parse_ambient_light(r, parse_property, current_line):
    """
    Parses the AMBIENTLIGHT and its properties.
    """

    ambient_light = {}

    records = shlex.split(current_line)
    if records[0] != "AMBIENTLIGHT":
        raise Exception(f"Expected AMBIENTLIGHT, got {records[0]}")
    ambient_light['name'] = records[1]

    records = parse_property(r, "LIGHT", 1)
    ambient_light["light"] = records[1]

    records = parse_property(r, "REGIONLIST", -1)
    parts = records[1:]
    ambient_light['num_regions'] = int(parts[0])
    region_list = [int(x) for x in parts[1:]]
    ambient_light['region_list'] = region_list

    return ambient_light
