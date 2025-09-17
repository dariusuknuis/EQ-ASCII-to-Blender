import shlex

def parse_hierarchical_sprite_def(r, parse_property, current_line):
    armature_data = {
        'name': '',
        'bones': [],
        'relationships': [],
        'attached_skins': [],
        'center_offset': None,
        'bounding_radius': None,
    }
    
    existing_bone_names = set()
    track_suffix_map = {}
    
    # Parse HIERARCHICALSPRITEDEF from the current line
    records = shlex.split(current_line)
    if records[0] != "HIERARCHICALSPRITEDEF":
        raise Exception(f"Expected HIERARCHICALSPRITEDEF, got {records[0]}")
    armature_data['name'] = records[1]

    # Parse NUMDAGS
    records = parse_property(r, "NUMDAGS", 1)
    num_dags = int(records[1])
    bone_index = 0

    # Parse each DAG section
    for i in range(num_dags):
        records = parse_property(r, "DAG", 0)
        bone_data = {
            'name': '',
            'track': None,
            'track_index': 0,
            'num_subdags': 0,
            'subdag_list': [],
            'sprite': None
        }

        # Parse TAG
        records = parse_property(r, "TAG", 1)
        base_name = records[1]
        if base_name in existing_bone_names:
            suffix = 1
            new_name = f"{base_name}.{suffix:03d}"
            while new_name in existing_bone_names:
                suffix += 1
                new_name = f"{base_name}.{suffix:03d}"
            bone_data['name'] = new_name
            track_suffix_map[base_name] = suffix
        else:
            bone_data['name'] = base_name
            track_suffix_map[base_name] = 0
        existing_bone_names.add(bone_data['name'])

        # Parse SPRITE
        records = parse_property(r, "SPRITETAG", 1)
        sprite_value = records[1]
        bone_data['sprite'] = sprite_value if sprite_value else None

        records = parse_property(r, "SPRITEINDEX", 1)
        bone_data['sprite_index'] = int(records[1])

        # Parse TRACK
        records = parse_property(r, "TRACK", 1)
        base_track = records[1]
        if bone_data['name'] != base_name:
            suffix = track_suffix_map[base_name]
            new_track = f"{base_track}.{suffix:03d}"
            bone_data['track'] = new_track
        else:
            bone_data['track'] = base_track

        # Parse TRACKINDEX
        records = parse_property(r, "TRACKINDEX", 1)
        bone_data['track_index'] = int(records[1])

        # Parse SUBDAGLIST
        records = parse_property(r, "SUBDAGLIST", -1)
        parts = records[1:]
        bone_data['num_subdags'] = int(parts[0])  # The first value is the number of child bones
        subdag_list = [int(x) for x in parts[1:]]  # The remaining values are the child bone index values
        bone_data['subdag_list'] = subdag_list
        armature_data['relationships'].append((bone_index, subdag_list))

        # Store the bone data
        armature_data['bones'].append(bone_data)
        bone_index += 1

    # Parse NUMATTACHEDSKINS
    records = parse_property(r, "NUMATTACHEDSKINS", 1)
    num_attached_skins = int(records[1])

    # Parse attached skins if any
    for i in range(num_attached_skins):
        attached_skin = {}
        records = parse_property(r, "ATTACHEDSKIN", 0)
        records = parse_property(r, "DMSPRITE", 1)
        attached_skin['sprite'] = records[1]

        records = parse_property(r, "DMSPRITEINDEX", 1)
        attached_skin['sprite_index'] = records[1]

        records = parse_property(r, "LINKSKINUPDATESTODAGINDEX", 1)
        attached_skin['link_skin_updates_to_dag_index'] = int(records[1])

        armature_data['attached_skins'].append(attached_skin)

    # Parse POLYHEDRON
    records = parse_property(r, "POLYHEDRON", 0)
    records = parse_property(r, "SPRITE", 1)
    polyhedron_definition = records[1]
    armature_data['polyhedron'] = polyhedron_definition

    # Parse CENTEROFFSET?
    records = parse_property(r, "CENTEROFFSET?", 3)
    offset_values = records[1:]
    if offset_values and all(value != "NULL" for value in offset_values):
        armature_data['center_offset'] = list(map(float, offset_values))

    # Parse BOUNDINGRADIUS?
    records = parse_property(r, "BOUNDINGRADIUS?", 1)
    bounding_radius_value = records[1]
    if bounding_radius_value and bounding_radius_value != "NULL":
        armature_data['bounding_radius'] = float(bounding_radius_value)

    # Parse FLAGS
    records = parse_property(r, "HAVEATTACHEDSKINS", 1)
    armature_data["have_attached_skins"] = int(records[1])

    records = parse_property(r, "DAGCOLLISIONS", 1)
    armature_data["dag_collisions"] = int(records[1])

    return armature_data
