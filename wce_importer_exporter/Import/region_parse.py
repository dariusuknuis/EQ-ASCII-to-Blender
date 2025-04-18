import shlex

def process_vislist(vislistbytes, ranges):
    """
    Decode a WCE‐style visibility RANGE byte stream into a flat list of region indices.
    `vislistbytes` is the VISLISTBYTES flag from your region.
    `ranges` is a list of ints (0–255).
    """
    regions = []
    current = 1

    if vislistbytes == 1:
        # RLE‐encoded
        i = 0
        while i < len(ranges):
            b = ranges[i]
            if   b <= 0x3E:
                current += b
            elif b == 0x3F:
                # next two bytes are a 16‑bit count, little‑endian
                count = (ranges[i+2] << 8) | ranges[i+1]
                current += count
                i += 2
            elif 0x40 <= b <= 0x7F:
                skip = (b & 0b0011_1000) >> 3
                take = b & 0b0000_0111
                current += skip
                for _ in range(take):
                    regions.append(current)
                    current += 1
            elif 0x80 <= b <= 0xBF:
                take = (b & 0b0011_1000) >> 3
                for _ in range(take):
                    regions.append(current)
                    current += 1
                current += (b & 0b0000_0111)
            elif 0xC0 <= b <= 0xFE:
                take = b - 0xC0
                for _ in range(take):
                    regions.append(current)
                    current += 1
            elif b == 0xFF:
                count = (ranges[i+2] << 8) | ranges[i+1]
                for _ in range(count):
                    regions.append(current)
                    current += 1
                i += 2
            i += 1
    else:
        # direct uint16 reads, little‑endian pairs
        for i in range(0, len(ranges), 2):
            idx = (ranges[i+1] << 8) | ranges[i]
            regions.append(idx + 1)

    return regions

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

    records = parse_property(r, "NUMREGIONVERTEXS", 1)
    region["num_region_vertex"] = int(records[1])

    records = parse_property(r, "NUMRENDERVERTICES", 1)
    region["num_render_vertices"] = int(records[1])

    records = parse_property(r, "NUMWALLS", 1)
    region["num_walls"] = int(records[1])

    records = parse_property(r, "NUMOBSTACLES", 1)
    region["num_obstacles"] = int(records[1])

    records = parse_property(r, "NUMCUTTINGOBSTACLES", 1)
    region["num_cutting_obstacles"] = int(records[1])

    records = parse_property(r, "VISTREE", 0)
    records = parse_property(r, "NUMVISNODES", 1)
    num_visnodes = int(records[1])
    visnodes = []
    for i in range(num_visnodes):
        records = parse_property(r, "VISNODE", 0)
        records = parse_property(r, "VNORMALABCD", 4)
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

    records = parse_property(r, "NUMVISIBLELISTS", 1)
    num_vislists = int(records[1])
    vislists = []
    for i in range(num_vislists):
        records = parse_property(r, "VISLIST", 0)
        records = parse_property(r, "RANGE", -1)
        parts = records[1:]
        num_ranges = int(parts[0])
        range_bytes = parts[1:]
        vislist = (num_ranges, range_bytes)
        vislists.append(vislist)

    region['vislists'] = vislists

    records = parse_property(r, "SPHERE", 4)
    region['sphere'] = list(map(float, records[1:]))

    records = parse_property(r, "USERDATA", 1)
    region['userdata'] = records[1]

    records = parse_property(r, "SPRITE", 1)
    region['sprite'] = records[1]
        
    return region
