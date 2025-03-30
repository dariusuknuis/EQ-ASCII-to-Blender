import shlex

def region_parse(r, parse_property, current_line):
    region = {}

    records = shlex.split(current_line)
    if records[0] != "REGION":
        raise Exception(f"Expected REGION, got {records[0]}")
    region['name'] = records[1]

    # Parse NUMWORLDNODES
    records = parse_property(r, "REVERBVOLUME", 1)
    region["reverb_volume"] = float(records[1])

    records = parse_property(r, "REVERBOFFSET", 1)
    region["reverb_offset"] = int(records[1])

    records = parse_property(r, "REGIONFOG", 1)
    region["region_fog"] = int(records[1])

    records = parse_property(r, "GOURAND2", 1)
    region["gouraud2"] = int(records[1])

    records = parse_property(r, "ENCODEDVISIBILITY", 1)
    region["encoded_visibility"] = int(records[1])

    records = parse_property(r, "VISLISTBYTES", 1)
    region["vislistbytes"] = int(records[1])

    records = parse_property(r, "NUMREGIONVERTEX", 1)
    region["num_region_vertex"] = int(records[1])

    records = parse_property(r, "NUMRENDERVERTICES", 1)
    region["num_render_vertices"] = int(records[1])

    ecords = parse_property(r, "NUMWALLS", 1)
    region["num_walls"] = int(records[1])

    records = parse_property(r, "NUMOBSTACLES", 1)
    region["num_obstacles"] = int(records[1])

    records = parse_property(r, "NUMCUTTINGOBSTACLES", 1)
    region["num_cutting_obstacles"] = int(records[1])

    records = parse_property(r, "VISTREE", 0)
    records = parse_property(r, "NUMVISNODE", 1)
    num_visnodes = int(records[1])
    visnodes = []
    for i in range(num_visnodes):
        records = parse_property(r, "VISNODE", 0)
        records = parse_property(r, "NORMALABCD", 4)
        normal = list(map(float, records[1:]))
        records = parse_property(r, "VISLISTINDEX", 1)
        vislist_index = int(records[1])
        records = parse_property(r, "FRONTTREE", 1)
        front_tree = int(records[1])
        records = parse_property(r, "BACKTREE", 1)
        back_tree = int(records[1])
        visnode = (normal, vislist_index, front_tree, back_tree)
        visnodes.append(visnode)
    region['visnodes'] = visnodes

    records = parse_property(r, "NUMVISIBLELIST", 1)
    num_visible_lists = int(records[1])
    visible_lists = []
    for i in range(num_visible_lists):
        parse_property(r, "VISLIST", 0)
        # Peek at the next line to determine if it's RANGE or REGIONS
        line = next(r).strip()
        if "//" in line:
            line = line.split("//")[0].strip()
        if not line:
            continue  # skip empty lines

        keyword = shlex.split(line)[0].upper()
        if keyword == "REGIONS":
            records = shlex.split(line)
            num_regions = int(records[1])
            visible_regions = records[2:]
            visible_list = {
                "type": "REGIONS",
                "num": num_regions,
                "regions": visible_regions,
            }
        elif keyword == "RANGE":
            records = shlex.split(line)
            num_ranges = int(records[1])
            range_bytes = records[2:]
            visible_list = {
                "type": "RANGE",
                "num": num_ranges,
                "ranges": range_bytes,
            }
        else:
            raise Exception(f"Expected REGIONS or RANGE after VISLIST, got: {keyword}")

        visible_lists.append(visible_list)
    region['visible_lists'] = visible_lists

    records = parse_property(r, "SPHERE", 4)
    region['sphere'] = list(map(float, records[1:]))

    records = parse_property(r, "USERDATA", 1)
    region['userdata'] = records[1]

    records = parse_property(r, "SPRITE", 1)
    region['sprite'] = records[1]
        
    return region
