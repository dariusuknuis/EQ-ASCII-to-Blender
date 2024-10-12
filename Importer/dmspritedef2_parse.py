import bpy
import bmesh
import mathutils
import shlex

def dmspritedef2_parse(r, parse_property, current_line):
    mesh = {}

    # Parse DMSPRITEDEF2 from the current line
    records = shlex.split(current_line)
    if records[0] != "DMSPRITEDEF2":
        raise Exception(f"Expected DMSPRITEDEF2, got {records[0]}")
    mesh['name'] = records[1]

    # Parse the CENTEROFFSET property
    records = parse_property(r, "CENTEROFFSET", 3)
    mesh['center_offset'] = tuple(map(float, records[1:]))

    # Parse NUMVERTICES and the XYZ coordinates of each vertex
    records = parse_property(r, "NUMVERTICES", 1)
    num_vertices = int(records[1])
    vertices = []
    for i in range(num_vertices):
        records = parse_property(r, "XYZ", 3)
        vertices.append(tuple(map(float, records[1:])))
    mesh['vertices'] = vertices

    # Parse NUMUVS and the UV coordinates
    records = parse_property(r, "NUMUVS", 1)
    num_uvs = int(records[1])
    uvs = []
    for i in range(num_uvs):
        records = parse_property(r, "UV", 2)
        uvs.append(tuple(map(float, records[1:])))
    mesh['uvs'] = uvs

    # Parse NUMVERTEXNORMALS and the XYZ normals
    records = parse_property(r, "NUMVERTEXNORMALS", 1)
    num_normals = int(records[1])
    normals = []
    for i in range(num_normals):
        records = parse_property(r, "XYZ", 3)
        normals.append(tuple(map(float, records[1:])))
    mesh['normals'] = normals

    # Parse NUMVERTEXCOLORS and the RGBA values
    records = parse_property(r, "NUMVERTEXCOLORS", 1)
    num_colors = int(records[1])
    colors = []
    for i in range(num_colors):
        records = parse_property(r, "RGBA", 4)
#        r = int(records[1]) / 255
#        g = int(records[2]) / 255
#        b = int(records[3]) / 255
#        a = int(records[4]) / 255
#        colors.append((r, g, b, a))
        colors.append(tuple(map(float, records[1:])))
    mesh['colors'] = colors

    # Parse SKINASSIGNMENTGROUPS
    records = parse_property(r, "SKINASSIGNMENTGROUPS", -1)
    parts = records[1:]
    num_groups = int(parts[0])
    vertex_groups = []
    vertex_start = 0
    for i in range(num_groups):
        num_vertices = int(parts[i * 2 + 1])
        bone_index = int(parts[i * 2 + 2])
        vertex_end = vertex_start + num_vertices
        vertex_groups.append((vertex_start, vertex_end, bone_index))
        vertex_start = vertex_end
    mesh['vertex_groups'] = vertex_groups

    # Parse MATERIALPALETTE
    records = parse_property(r, "MATERIALPALETTE", 1)
    mesh["material_palette"] = records[1]

    # Parse POLYHEDRON and its DEFINITION
    records = parse_property(r, "POLYHEDRON", 0)
    records = parse_property(r, "DEFINITION", 1)
    polyhedron_data = records[1]
    mesh['polyhedron'] = polyhedron_data

    # Parse NUMFACE2S and the TRIANGLE indices
    records = parse_property(r, "NUMFACE2S", 1)
    num_faces = int(records[1])
    faces = []
    for i in range(num_faces):
        records = parse_property(r, "DMFACE2", 0)
        records = parse_property(r, "PASSABLE", 1)
        passable = int(records[1])  # Passable flag
        records = parse_property(r, "TRIANGLE", 3)
        face = (int(records[3]), int(records[2]), int(records[1]), passable)  # Reverse order and include passable
        faces.append(face)
    mesh['faces'] = faces

    # Parse MESHOPS
    records = parse_property(r, "NUMMESHOPS", 1)
    num_meshops = int(records[1])
    meshops = []
    for i in range(num_meshops):
        records = parse_property(r, "MESHOP", 5)
        meshop = (int(records[1]), int(records[2]), float(records[3]), int(records[4]), int(records[5]))
        meshops.append(meshop)
    mesh['meshops'] = meshops

    # Parse FACEMATERIALGROUPS
    records = parse_property(r, "FACEMATERIALGROUPS", -1)
    parts = records[1:]
    num_groups = int(parts[0])
    face_material_groups = []
    face_start = 0
    for i in range(num_groups):
        num_faces = int(parts[i * 2 + 1])
        material_index = int(parts[i * 2 + 2])
        face_end = face_start + num_faces
        face_material_groups.append((face_start, face_end, material_index))
        face_start = face_end
    mesh['face_materials'] = face_material_groups

    # Parse VERTEXMATERIALGROUPS
    records = parse_property(r, "VERTEXMATERIALGROUPS", -1)
    parts = records[1:]
    num_groups = int(parts[0])
    vertex_material_groups = []
    vertex_start = 0
    for i in range(num_groups):
        num_vertices = int(parts[i * 2 + 1])
        material_index = int(parts[i * 2 + 2])
        vertex_end = vertex_start + num_vertices
        vertex_material_groups.append((vertex_start, vertex_end, material_index))
        vertex_start = vertex_end
    mesh['vertex_materials'] = vertex_material_groups

    # Parse DMTRACK and its DEFINITION
    # records = parse_property(r, "DMTRACK", 0)
    # records = parse_property(r, "DEFINITION", 1)
    # dmtrack_data = records[1]
    # mesh['dmtrack'] = dmtrack_data

    # Parse BOUNDINGBOX
    bounding_box_data = []
    records = parse_property(r, "BOUNDINGBOXMIN", 3)
    bounding_box_data.append(tuple(map(float, records[1:])))
    records = parse_property(r, "BOUNDINGBOXMAX", 3)
    bounding_box_data.append(tuple(map(float, records[1:])))
    mesh['bounding_box'] = bounding_box_data

    # Parse BOUNDINGRADIUS
    records = parse_property(r, "BOUNDINGRADIUS", 1)
    mesh["bounding_radius"] = float(records[1])

    # Parse FPSCALE
    records = parse_property(r, "FPSCALE", 1)
    mesh["fpscale"] = int(records[1])

    # Parse FLAGS
    records = parse_property(r, "HEXONEFLAG", 1)
    mesh["hexoneflag"] = int(records[1])

    records = parse_property(r, "HEXTWOFLAG", 1)
    mesh["hextwoflag"] = int(records[1])

    records = parse_property(r, "HEXFOURTHOUSANDFLAG", 1)
    mesh["hexfourthousandflag"] = int(records[1])

    records = parse_property(r, "HEXEIGHTTHOUSANDFLAG", 1)
    mesh["hexeightthousandflag"] = int(records[1])

    records = parse_property(r, "HEXTENTHOUSANDFLAG", 1)
    mesh["hextenthousandflag"] = int(records[1])

    records = parse_property(r, "HEXTWENTYTHOUSANDFLAG", 1)
    mesh["hextwentythousandflag"] = int(records[1])

    return mesh
