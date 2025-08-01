import shlex

def parse_world_def(r, parse_property, current_line):
    """
    Parses the WORLDDEF and its properties.
    """
    records = shlex.split(current_line)
    if records[0] != "WORLDDEF":
        raise Exception(f"Expected WORLDDEF, got {records[0]}")

    worlddef = {}

    records = parse_property(r, "NEWWORLD", 1)
    worlddef["new_world"] = int(records[1])

    records = parse_property(r, "ZONE", 1)
    worlddef["zone"] = int(records[1])

    records = parse_property(r, "EQGVERSION?", 1)
    worlddef["eqg_version"] = records[1]

    return worlddef
