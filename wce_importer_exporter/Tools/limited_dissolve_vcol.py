import bpy
import bmesh
from mathutils import Vector
from math import radians

def limited_dissolve_vcol(
    obj,
    color_layer_name="Color",
    minimum_gap=0.1,
    long_edge_factor=0.9,
    angle_degrees=5.0
):
    """
    Mark edges as “sharp” wherever the color‐difference logic dictates,
    run a bmesh.ops.dissolve_limit (respecting sharp edges), then restore
    all edges to smooth=True and write back to the original mesh.

    Parameters:
    - obj:            a bpy.types.Object of type 'MESH' (in Object Mode).
    - color_layer_name:  the name of the per‐vertex Float Color layer to use.
    - minimum_gap:    how much smaller (in color‐space) the “smallest edge”
                       must be than the next‐smallest edge on that same triangle
                       before we mark it sharp.
    - long_edge_factor:  any candidate edge with length ≥ (long_edge_factor × bbox_diagonal)
                       will be skipped entirely.
    - angle_degrees:  the “Max Angle” (in degrees) to pass into dissolve_limit.
    """

    # 1) Validate the incoming object
    if not obj or obj.type != 'MESH':
        raise RuntimeError("limited_dissolve_by_vertex_color: Please pass a mesh object.")
   
    me = obj.data
    me.calc_normals_split()
    me.use_auto_smooth = True

    # 2) Build a fresh BMesh from that Mesh
    bm = bmesh.new()
    bm.from_mesh(me)
    ln_layer = bm.loops.layers.float_vector.new("orig_normals")
    loops = (l for f in bm.faces for l in f.loops)
    for loop in loops:
        loop[ln_layer] = me.loops[loop.index].normal

    # 3) Ensure lookup tables
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 4) Find the per‐vertex float_color layer
    vcol_layer = bm.verts.layers.float_color.get(color_layer_name)
    if vcol_layer is None:
        bm.free()
        raise RuntimeError(
            f"limited_dissolve_by_vertex_color: Vertex float_color layer '{color_layer_name}' not found."
        )

    # 5) Compute bounding‐box diagonal length (local coords)
    all_co = [v.co for v in bm.verts]
    if not all_co:
        bm.free()
        raise RuntimeError("limited_dissolve_by_vertex_color: Mesh has no vertices! Aborting.")

    min_x = min(v.x for v in all_co)
    max_x = max(v.x for v in all_co)
    min_y = min(v.y for v in all_co)
    max_y = max(v.y for v in all_co)
    min_z = min(v.z for v in all_co)
    max_z = max(v.z for v in all_co)

    bbox_min = Vector((min_x, min_y, min_z))
    bbox_max = Vector((max_x, max_y, max_z))
    bbox_diag = (bbox_max - bbox_min).length

    # 6) We will collect “sharp” edges into a set instead of using selection
    sharp_edges = set()

    # 7) Helper: find the BMEdge shared by two BMVerts
    def find_edge_between(v_a, v_b):
        for e in v_a.link_edges:
            if v_b in e.verts:
                return e
        return None

    # 8) First pass: record each triangle’s “smallest‐edge” info
    face_smallest = {}  # map BMFace → (BMEdge, is_boundary, passes_gap_length)

    for face in bm.faces:
        if len(face.verts) != 3:
            continue

        v0, v1, v2 = face.verts
        c0 = Vector(v0[vcol_layer])
        c1 = Vector(v1[vcol_layer])
        c2 = Vector(v2[vcol_layer])

        # compute color‐distances
        d01 = (c0 - c1).length
        d12 = (c1 - c2).length
        d20 = (c2 - c0).length

        e01 = find_edge_between(v0, v1)
        e12 = find_edge_between(v1, v2)
        e20 = find_edge_between(v2, v0)

        triplet = [(e01, d01), (e12, d12), (e20, d20)]
        triplet_sorted = sorted(triplet, key=lambda x: x[1])
        smallest_edge, smallest_dist = triplet_sorted[0]
        _, second_dist = triplet_sorted[1]

        # check gap
        passes_gap = (second_dist - smallest_dist) > minimum_gap

        # check length
        edge_vec = smallest_edge.verts[0].co - smallest_edge.verts[1].co
        edge_len = edge_vec.length
        passes_length = (edge_len < (long_edge_factor * bbox_diag))

        # is “smallest_edge” a boundary edge?
        is_boundary = (len(smallest_edge.link_faces) == 1)

        face_smallest[face] = (smallest_edge, is_boundary, (passes_gap and passes_length))

        # if not boundary AND passes both criteria, mark it as sharp
        if (not is_boundary) and (passes_gap and passes_length):
            sharp_edges.add(smallest_edge)

    # 9) Second pass: find edges shared by two faces whose smallest‐edge was boundary & passed tests
    candidate_edges = set()

    for edge in bm.edges:
        # only consider truly-manifold edges (2 faces exactly)
        if len(edge.link_faces) != 2:
            continue
        f1, f2 = edge.link_faces

        se1, boundary1, ok1 = face_smallest.get(f1, (None, False, False))
        se2, boundary2, ok2 = face_smallest.get(f2, (None, False, False))

        if se1 and se2 and boundary1 and ok1 and boundary2 and ok2:
            candidate_edges.add(edge)

    # 10) Prune candidate_edges so that for any shared vertex, only the longest edge survives
    # First, group candidates by vertex
    vert_to_cands = {v: [] for v in bm.verts}
    for e in candidate_edges:
        for v in e.verts:
            vert_to_cands[v].append(e)

    # For each vertex, keep only the longest incident candidate
    for v, edge_list in vert_to_cands.items():
        if len(edge_list) <= 1:
            continue
        best = max(
            edge_list,
            key=lambda ee: (ee.verts[0].co - ee.verts[1].co).length
        )
        for ee in edge_list:
            if ee is not best:
                candidate_edges.discard(ee)

    # Add the surviving candidates to sharp_edges
    sharp_edges.update(candidate_edges)

    # 11) Mark each edge in sharp_edges as “sharp” (i.e. smooth=False)
    for e in sharp_edges:
        e.smooth = False

    # mark_uv_break_seams(bm)

    # 12) Perform limited dissolve, respecting SHARP edges as a delimiter
    angle_limit = radians(angle_degrees)
    while True:
        found = False

        for e in bm.edges:
            # only dissolve non-sharp, manifold, small-angle edges
            if not e.smooth: 
                continue
            if len(e.link_faces) != 2:
                continue
            if e.calc_face_angle() > angle_limit:
                continue

            f1, f2 = e.link_faces

            # if merging f1+f2 would give >4 verts, skip
            if (len(f1.verts) + len(f2.verts) - 2) > 4:
                continue

            # this edge is safe to dissolve _now_
            bmesh.ops.dissolve_edges(
                bm,
                edges=[e],
                use_verts=False,
                use_face_split=False
            )
            found = True
            break

        if not found:
            break

    # After dissolving, restore all edges back to smooth=True
    for e in bm.edges:
        e.smooth = True
        e.seam = False

    # 13) Write BMesh back into the Mesh, free BMesh, update normals
    bm.to_mesh(me)
    bm.free()

    for poly in me.polygons:
            poly.use_smooth = True

    me.use_auto_smooth = True

    ln_attr = me.attributes.get("orig_normals")
    if ln_attr:
        # build flat list of normals in loop order
        custom_nors = [ Vector(cd.vector) for cd in ln_attr.data ]
        me.normals_split_custom_set(custom_nors)
        me.attributes.remove(me.attributes.get("orig_normals"))

