import shlex

def parse_zone(r, parse_property, current_line):
    """
    Parses the ZONE and its properties.
    """
    zone = {}

    records = shlex.split(current_line)
    if records[0] != "ZONE":
        raise Exception(f"Expected ZONE, got {records[0]}")
    zone['name'] = records[1]

    records = parse_property(r, "REGIONLIST", -1)
    parts = records[1:]
    zone['num_regions'] = int(parts[0])
    region_list = [int(x) for x in parts[1:]]
    zone['region_list'] = region_list

    records = parse_property(r, "USERDATA", 1)
    zone["userdata"] = records[1]

    return zone
