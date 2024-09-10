def material_palette_parse(r, parse_property):
    palette = {
        'name': '',
        'num_materials': 0,
        'materials': []
    }

    # Parse MATERIALPALETTE
    records = parse_property(r, "MATERIALPALETTE", 1)
    palette['name'] = records[1]
    
    # Parse NUMMATERIALS
    records = parse_property(r, "NUMMATERIALS", 1)
    palette['num_materials'] = int(records[1])

    # Parse MATERIAL for each material entry
    for i in range(palette['num_materials']):
        records = parse_property(r, "MATERIAL", 1)
        palette['materials'].append(records[1])

    return palette
