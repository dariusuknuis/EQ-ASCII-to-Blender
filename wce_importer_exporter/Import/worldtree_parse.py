import shlex

def worldtree_parse(r, parse_property, current_line):
    """
    Parses the WORLDTREE and its nodes into a structured dictionary format.
    """
    records = shlex.split(current_line)
    if records[0] != "WORLDTREE":
        raise Exception(f"Expected WORLDTREE, got {records[0]}")

    worldtree = {
        "nodes": [],
        "total_nodes": 0,
    }

    # Parse NUMWORLDNODES
    records = parse_property(r, "NUMWORLDNODES", 1)
    worldtree["total_nodes"] = int(records[1])

    for i in range(worldtree["total_nodes"]):
        records = parse_property(r, "WORLDNODE", 0)
        records = parse_property(r, "NORMALABCD", 4)
        normal = list(map(float, records[1:]))

        records = parse_property(r, "WORLDREGIONTAG", 1)
        region_tag = records[1].strip('"')

        records = parse_property(r, "FRONTTREE", 1)
        front_tree = int(records[1])

        records = parse_property(r, "BACKTREE", 1)
        back_tree = int(records[1])

        node = {
            "worldnode": i + 1,  # Add worldnode property with index
            "normal": normal,
            "region_tag": region_tag,
            "front_tree": front_tree,
            "back_tree": back_tree,
        }
        worldtree["nodes"].append(node)

    return worldtree
