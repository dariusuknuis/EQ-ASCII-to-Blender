import mathutils

def polyhedrondefinition_parse(r, parse_property):
    polyhedron = {
        'name': '',
        'bounding_radius': 0.0,
        'scale_factor': 1.0,
        'vertices': [],
        'faces': [],
        'hexoneflag': 0
    }

    # Parse the TAG property
    records = parse_property(r, "POLYHEDRONDEFINITION", 1)
    polyhedron['name'] = records[1]
    
    # Parse BOUNDINGRADIUS
    records = parse_property(r, "BOUNDINGRADIUS", 1)
    polyhedron['bounding_radius'] = float(records[1])

    # Parse SCALEFACTOR
    records = parse_property(r, "SCALEFACTOR", 1)
    polyhedron['scale_factor'] = float(records[1])

    # Parse NUMVERTICES and then the XYZ coordinates of each vertex
    records = parse_property(r, "NUMVERTICES", 1)
    num_vertices = int(records[1])
    for i in range(num_vertices):
        records = parse_property(r, "XYZ", 3)
        vertex = list(map(float, records[1:]))
        polyhedron['vertices'].append(vertex)

    # Parse NUMFACES and the VERTEXLIST of each face
    records = parse_property(r, "NUMFACES", 1)
    num_faces = int(records[1])
    for i in range(num_faces):
        records = parse_property(r, "VERTEXLIST", -1)
        parts = list(map(int, records[1:]))
        num_vertices_in_face = parts[0]
        vertex_list = parts[1:num_vertices_in_face + 1]  # Extract vertex indices
        face = {
            'num_vertices': num_vertices_in_face,
            'vertex_list': vertex_list
        }
        polyhedron['faces'].append(face)

    # Parse HEXONEFLAG
    records = parse_property(r, "HEXONEFLAG", 1)
    polyhedron['hexoneflag'] = int(records[1])

    return polyhedron

    polyhedron = polyhedrondefinition_parse(lines, parse_property)
    print("POLYHEDRONDEFINITION Sections:")
    print(polyhedron)
