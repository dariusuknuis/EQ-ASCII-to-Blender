import json

def write_actordef(empty_obj, file):
    # Ensure that we’re only exporting for objects with "_ACTORDEF" suffix
    if not empty_obj.name.endswith("_ACTORDEF"):
        print(f"Object '{empty_obj.name}' does not have '_ACTORDEF' suffix.")
        return
    
    # Write the ACTORDEF header with the object's name
    actordef_name = empty_obj.name
    file.write(f'\nACTORDEF "{actordef_name}"\n')

    # Export custom properties
    callback = empty_obj.get("CALLBACK", "SPRITECALLBACK")
    bounds_ref = empty_obj.get("BOUNDSREF", 0)
    current_action = empty_obj.get("CURRENTACTION", "NULL")
    location = empty_obj.get("LOCATION", ["NULL"] * 6)
    active_geometry = empty_obj.get("ACTIVEGEOMETRY", "NULL")
    userdata = empty_obj.get("USERDATA", "")
    use_model_collider = 1 if empty_obj.get("USEMODELCOLLIDER", False) else 0

    # Write the core properties to the file
    file.write(f'\tCALLBACK "{callback}"\n')
    file.write(f'\tBOUNDSREF {bounds_ref}\n')
    file.write(f'\tCURRENTACTION? {current_action}\n')

    # Handle LOCATION parsing and formatting
    if isinstance(location, str):
        try:
            location = json.loads(location)  # Attempt to parse JSON if location is a string
        except json.JSONDecodeError:
            location = ["NULL"] * 6  # Default if parsing fails

    location_str = " ".join(map(str, location))
    file.write(f'\tLOCATION? {location_str}\n')

    file.write(f'\tACTIVEGEOMETRY? {active_geometry}\n')

    # Count NUMACTIONS by detecting "ACTION_x" custom properties
    action_props = [key for key in empty_obj.keys() if key.startswith("ACTION_")]
    num_actions = len(action_props)
    file.write(f'\tNUMACTIONS {num_actions}\n')
    
    for action_key in action_props:
        # Parse the JSON data from each ACTION_x property
        action_data = json.loads(empty_obj[action_key])
        unk1 = action_data.get("unk1", 0)
        num_lod = action_data.get("numlevelsofdetail", 1)
        levels_of_detail = action_data.get("levelsofdetail", [])

        # Write the ACTION block
        file.write(f'\t\tACTION\n')
        file.write(f'\t\t\tUNK1 {unk1}\n')
        file.write(f'\t\t\tNUMLEVELSOFDETAILS {num_lod}\n')
        
        # Write each level of detail within the ACTION block
        for lod in levels_of_detail:
            sprite = lod.get("sprite", "")
            sprite_index = lod.get("spriteindex", 0)
            min_distance = lod.get("mindistance", 1.00000002e+30)
            file.write(f'\t\t\t\tLEVELOFDETAIL\n')
            file.write(f'\t\t\t\t\tSPRITE "{sprite}"\n')
            file.write(f'\t\t\t\t\tSPRITEINDEX {sprite_index}\n')
            file.write(f'\t\t\t\t\tMINDISTANCE {min_distance:.8e}\n')

    # Write remaining properties USEMODELCOLLIDER and USERDATA
    file.write(f'\tUSEMODELCOLLIDER {use_model_collider}\n')
    file.write(f'\tUSERDATA "{userdata}"\n')

    print(f'ACTORDEF data for "{actordef_name}" exported.')
