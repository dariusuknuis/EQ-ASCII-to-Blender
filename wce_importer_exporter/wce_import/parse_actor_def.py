import shlex

def parse_actor_def(r, parse_property, current_line):
    actordef_data = {
        "name": "",
        "callback": "",
        "boundsref": 0,
        "currentaction": "NULL",
        "location": ["NULL"] * 6,
        "activegeometry": "NULL",
        "numactions": 0,
        "actions": [],
        "unk2": 0,
        "haseightyflag": False
    }

    # Parse ACTORDEF from the current line
    records = shlex.split(current_line)
    if records[0] != "ACTORDEF":
        raise Exception(f"Expected ACTORDEF, got {records[0]}")
    actordef_data["name"] = records[1]

    # Parse CALLBACK
    records = parse_property(r, "CALLBACK", 1)
    actordef_data["callback"] = records[1]

    # Parse BOUNDSREF
    records = parse_property(r, "BOUNDSREF", 1)
    actordef_data["boundsref"] = int(records[1])

    # Parse CURRENTACTION? (nullable)
    records = parse_property(r, "CURRENTACTION?", 1)
    actordef_data["currentaction"] = records[1]

    # Parse LOCATION? (nullable)
    records = parse_property(r, "LOCATION?", 6)
    actordef_data["location"] = [record if record != "NULL" else "NULL" for record in records[1:]]

    # Parse ACTIVEGEOMETRY? (nullable)
    records = parse_property(r, "ACTIVEGEOMETRY?", 1)
    actordef_data["activegeometry"] = records[1]

    # Parse NUMACTIONS
    records = parse_property(r, "NUMACTIONS", 1)
    actordef_data["numactions"] = int(records[1])

    # Parse ACTION blocks
    for action_index in range(actordef_data["numactions"]):
        action = {
            "unk1": 0,
            "numlevelsofdetail": 0,
            "levelsofdetail": []
        }

        # Parse ACTION
        parse_property(r, "ACTION", 0)

        # Parse UNK1
        records = parse_property(r, "UNK1", 1)
        action["unk1"] = int(records[1])

        # Parse NUMLEVELSOFDETAIL
        records = parse_property(r, "NUMLEVELSOFDETAILS", 1)
        action["numlevelsofdetail"] = int(records[1])

        # Parse LEVELOFDETAIL blocks
        for lod_index in range(action["numlevelsofdetail"]):
            lod = {
                "sprite": "",
                "spriteindex": 0,
                "mindistance": 0.0
            }

            # Parse LEVELOFDETAIL
            parse_property(r, "LEVELOFDETAIL", 0)

            # Parse SPRITE
            records = parse_property(r, "SPRITE", 1)
            lod["sprite"] = records[1]

            # Parse SPRITEINDEX
            records = parse_property(r, "SPRITEINDEX", 1)
            lod["spriteindex"] = int(records[1])

            # Parse MINDISTANCE
            records = parse_property(r, "MINDISTANCE", 1)
            lod["mindistance"] = float(records[1])

            # Append the level of detail to the action
            action["levelsofdetail"].append(lod)

        # Append the action to the actions list in actordef
        actordef_data["actions"].append(action)

    # Parse USEMODELCOLLIDER (SPRITEVOLUMEONLY)
    records = parse_property(r, "USEMODELCOLLIDER", 1)
    actordef_data["usemodelcollider"] = bool(int(records[1]))

    # Parse USERDATA
    records = parse_property(r, "USERDATA", 1)
    actordef_data["userdata"] = records[1]

    return actordef_data
