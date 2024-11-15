import shlex

def material_palette_parse(r, parse_property, current_line):
    palette = {
        'name': '',
        'num_materials': 0,
        'materials': []
    }
    
    # Parse MATERIALPALETTE from the current line
    records = shlex.split(current_line)
    if records[0] != "MATERIALPALETTE":
        raise Exception(f"Expected MATERIALPALETTE, got {records[0]}")
    palette['name'] = records[1]
    
    # Parse NUMMATERIALS
    records = parse_property(r, "NUMMATERIALS", 1)
    palette['num_materials'] = int(records[1])

    # Parse MATERIAL for each material entry
    for i in range(palette['num_materials']):
        records = parse_property(r, "MATERIAL", 1)
        palette['materials'].append(records[1])

    return palette
