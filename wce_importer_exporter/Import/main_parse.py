def main_parse(filepath):
    def strip_comments(line):
        return line.split('//')[0].strip()
    
    with open(filepath, 'r') as file:
        lines = file.readlines()
        
    includes = []
    sections = {}
    current_section = None
    main_keywords = {
        "MATERIALPALETTE": "ENDMATERIALPALETTE",
        "DMSPRITEDEF2": "ENDDMSPRITEDEF2",
        "TRACKDEFINITION": "ENDTRACKDEFINITION",
        "TRACKINSTANCE": "ENDTRACKINSTANCE",
        "HIERARCHICALSPRITEDEF": "ENDHIERARCHICALSPRITEDEF",
        "POLYHEDRONDEFINITION": "ENDPOLYHEDRONDEFINITION",
        "SIMPLESPRITEDEF": "ENDSIMPLESPRITEDEF",
        "MATERIALDEFINITION": "ENDMATERIALDEFINITION"  # Add MATERIALDEFINITION section
    }

    for line in lines:
        line = strip_comments(line)
        if not line:
            continue
        
        if line.startswith("INCLUDE"):
            include = line.split('"')[1]
            includes.append(include)
        elif line.startswith("MATERIALPALETTE") and '"' not in line:
            if current_section == "DMSPRITEDEF2":
                current_section = "DMSPRITEDEF2_MATERIALPALETTE"
            else:
                current_section = "MATERIALPALETTE"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("DMSPRITEDEF2"):
            current_section = "DMSPRITEDEF2"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("TRACKDEFINITION"):
            current_section = "TRACKDEFINITION"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("TRACKINSTANCE"):
            current_section = "TRACKINSTANCE"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("HIERARCHICALSPRITEDEF"):
            current_section = "HIERARCHICALSPRITEDEF"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("POLYHEDRONDEFINITION"):
            current_section = "POLYHEDRONDEFINITION"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("SIMPLESPRITEDEF"):
            current_section = "SIMPLESPRITEDEF"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif line.startswith("MATERIALDEFINITION"):  # Handle MATERIALDEFINITION
            current_section = "MATERIALDEFINITION"
            if current_section not in sections:
                sections[current_section] = []
            sections[current_section].append([])
        elif current_section and line.startswith(main_keywords.get(current_section.split('_')[0], '')):
            current_section = None
        elif current_section:
            sections[current_section][-1].append(line)
        
    return sections, includes
