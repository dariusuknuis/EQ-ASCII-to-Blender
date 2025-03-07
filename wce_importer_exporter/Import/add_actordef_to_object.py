import json

def add_actordef_to_object(obj, actordef_data):
    # Set simple properties directly
    obj["CALLBACK"] = actordef_data["callback"]
    obj["BOUNDSREF"] = actordef_data["boundsref"]
    obj["CURRENTACTION"] = actordef_data["currentaction"]
    obj["LOCATION"] = json.dumps(actordef_data["location"])
    obj["ACTIVEGEOMETRY"] = actordef_data["activegeometry"]
    obj["USERDATA"] = actordef_data["userdata"]
    obj["USEMODELCOLLIDER"] = actordef_data["usemodelcollider"]

    # Add actions with sub-properties as JSON strings
    for i, action in enumerate(actordef_data["actions"], 1):
        action_key = f"ACTION_{i}"
        obj[action_key] = json.dumps(action)
