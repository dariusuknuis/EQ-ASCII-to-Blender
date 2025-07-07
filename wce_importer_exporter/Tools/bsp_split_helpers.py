import bmesh, math, itertools
from collections import defaultdict
from math import radians
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

def mark_color_seams(bm, color_layer_name="Color", threshold=0.04):
    """
    On the given mesh object (in Object Mode), mark as UV seams all edges
    whose endpoint vertex-colors differ by more than `threshold`.

    • color_layer_name: the name of a per-vertex Float Color layer (rgba).
    • threshold: Euclidean distance in color-space above which an edge is marked seam.
    """

    # look up your per-vertex color layer
    vcol = bm.verts.layers.float_color.get(color_layer_name)
    if vcol is None:
        # fall back on 3-channel color layer, if you happened to create one
        vcol = bm.verts.layers.color.get(color_layer_name)
    if vcol is None:
        bm.free()
        raise RuntimeError(f"Vertex color layer '{color_layer_name}' not found on verts")

    # ensure our tables are valid
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # for every edge: compare its two verts’ color values
    for e in bm.edges:
        c1 = Vector(e.verts[0][vcol])
        c2 = Vector(e.verts[1][vcol])
        if (c1 - c2).length > threshold:
            e.seam = True
        else:
            e.seam = False

def dissolve_colinear_geo(bm, angle_limit=0.01):
    """
    1) Dissolve edges touching vertices where:
         - all incident edges lie in one plane (within sin(angle_limit)), and
         - at least one pair of those edges is within angle_limit of 180°.
       Seams are preserved.
    2) Dissolve degree-2 vertices whose two edges are within angle_limit of 180°.
       Seams are preserved.
    3) Triangulate all faces (BEAUTY quads, EAR_CLIP ngons).
    """
    # precompute thresholds
    planarity_tol = math.sin(angle_limit)
    cos_eps       = math.cos(angle_limit)
    thresh        = 1.0 - cos_eps   # |dot + 1| < thresh ⇒ within angle_limit of straight

    # ——— 1) Edge pass —————————————————————————————————————
    seam_verts = {v for v in bm.verts if any(e.seam for e in v.link_edges)}
    edges_to_dissolve = set()

    for v in bm.verts:
        if v in seam_verts:
            continue

        # gather normalized directions of all incident edges
        dirs = []
        for e in v.link_edges:
            vec = e.other_vert(v).co - v.co
            if vec.length_squared > 1e-8:
                dirs.append(vec.normalized())
        if len(dirs) < 2:
            continue

        # check coplanarity
        plane_n = None
        for d1, d2 in itertools.combinations(dirs, 2):
            cr = d1.cross(d2)
            if cr.length_squared > 1e-8:
                plane_n = cr.normalized()
                break
        if plane_n and any(abs(plane_n.dot(d)) > planarity_tol for d in dirs):
            continue

        # check at least one pair is colinear
        if not any(abs(d1.dot(d2) + 1.0) < thresh
                   for d1, d2 in itertools.combinations(dirs, 2)):
            continue

        # mark all edges at this vertex
        edges_to_dissolve.update(v.link_edges)

    # filter out any real seam edges or edges touching seam-verts
    edges_to_dissolve = {
        e for e in edges_to_dissolve
        if not e.seam and e.verts[0] not in seam_verts and e.verts[1] not in seam_verts
    }

    if edges_to_dissolve:
        bmesh.ops.dissolve_edges(bm,
                                 edges=list(edges_to_dissolve),
                                 use_face_split=False)
        print(f"Dissolved {len(edges_to_dissolve)} planar-colinear edges.")
    else:
        print("No planar-colinear edges found.")

    # ——— 2) Degree-2 vertex pass —————————————————————————————
    to_dissolve_verts = []
    for v in bm.verts:
        if any(e.seam for e in v.link_edges):
            continue
        if len(v.link_edges) != 2:
            continue

        e1, e2 = v.link_edges
        d1 = (e1.other_vert(v).co - v.co).normalized()
        d2 = (e2.other_vert(v).co - v.co).normalized()

        if abs(d1.dot(d2) + 1.0) < thresh:
            to_dissolve_verts.append(v)

    if to_dissolve_verts:
        bmesh.ops.dissolve_verts(bm,
                                 verts=to_dissolve_verts,
                                 use_face_split=False)
        print(f"Dissolved {len(to_dissolve_verts)} degree-2 colinear verts.")
    else:
        print("No degree-2 colinear verts found.")

    # ——— 3) Final triangulation —————————————————————————————————
    faces = [f for f in bm.faces]
    if faces:
        bmesh.ops.triangulate(
            bm,
            faces        = faces,
            quad_method  = 'BEAUTY',
            ngon_method  = 'EAR_CLIP',
        )
        print(f"Triangulated {len(faces)} faces.")

    return bm

def mesh_cleanup(bm, angle_limit=0.01, delimit={'SEAM','SHARP','MATERIAL','NORMAL'}):
    """
    1) Copy the input BMesh (orig_bm), so we have a pristine version to compare against.
    2) On the *live* `bm`, run bmesh.ops.dissolve_limit **only** on edges/verts that
       are not themselves seams and don't support any other seam.
    3) Build a BVHTree on that dissolved `bm`.
    4) For each face in orig_bm, shoot its centroid into the BVH → get new_face_index.
    5) Collect all dissolved faces in `bm` that are ngons (>4 verts) and have at least one concave corner.
    6) For each concave face:
         • Gather the set of original triangles that mapped to it.
         • Try each possible loop-0 rotation:
             – Build a tiny temp BMesh with that rotated ngon,
             – Triangulate it with EAR_CLIP / BEAUTY,
             – Score = #tris matching the original triangle-sets.
         • Pick the rotation with the highest score,
           then *rebuild* the face in `bm` with that rotated loop order and reapply UVs.
    """

    # ——— 1) make a pristine copy ——————————————————————————————
    orig_bm = bm.copy()
    orig_bm.faces.ensure_lookup_table()
    orig_bm.verts.ensure_lookup_table()

    # pre-compute centroids & vert-sets of every original face
    orig_centroids = {
        f.index: sum((v.co for v in f.verts), Vector()) / len(f.verts)
        for f in orig_bm.faces
    }
    orig_face_verts = {
        f.index: frozenset(v.index for v in f.verts)
        for f in orig_bm.faces
    }

    # ——— 2) filter out seam-related edges & verts ——————————————————
    # a) edges: skip any that are marked seam, or sit on a face
    #    which has another seam on one of its other edges.
    dissolvable_edges = []
    for e in bm.edges:
        if e.seam:
            continue
        # skip if any face using this edge has a different seam on another edge
        skip = False
        for f in e.link_faces:
            for ed in f.edges:
                if ed is not e and ed.seam:
                    skip = True
                    break
            if skip:
                break
        if not skip:
            dissolvable_edges.append(e)

    # b) verts: skip any that have an incident seam edge,
    #    or that are on a face which already has a seam on a different edge.
    dissolvable_verts = []
    for v in bm.verts:
        # if vertex sits on any seam edge, skip
        if any(e.seam for e in v.link_edges):
            continue
        # if any face using this vert has another seam on a different edge, skip
        skip = False
        for f in v.link_faces:
            for ed in f.edges:
                if ed.seam:
                    skip = True
                    break
            if skip:
                break
        if not skip:
            dissolvable_verts.append(v)

    # ——— 3) dissolve on the *live* bm ———————————————————————————
    bmesh.ops.dissolve_limit(
        bm,
        edges                   = dissolvable_edges,
        verts                   = dissolvable_verts,
        angle_limit             = angle_limit,
        use_dissolve_boundaries = False,
        delimit                 = delimit,
    )

    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # ——— 4) build BVH on the dissolved bm ————————————————————————
    bvh = BVHTree.FromBMesh(bm, epsilon=0.0)

    # map each original face → new face index
    orig_to_new = {}
    for fi, cen in orig_centroids.items():
        hit = bvh.find_nearest(cen)
        orig_to_new[fi] = hit[2] if hit else None

    # invert: new_face_idx → list of original face indices
    new_to_orig = {}
    for orig_i, new_i in orig_to_new.items():
        new_to_orig.setdefault(new_i, []).append(orig_i)

    # ——— 5) find all concave ngons in the dissolved mesh —————————————
    uv_layer = bm.loops.layers.uv.active
    concave_ngons = []
    for f in bm.faces:
        if len(f.verts) <= 4:
            continue
        # CCW loop order ⇒ dot>0 means concave corner
        concave_flags = [
            ((l.link_loop_prev.vert.co - l.vert.co)
             .cross(l.link_loop_next.vert.co - l.vert.co)
             .dot(f.normal) > 0)
            for l in f.loops
        ]
        if any(concave_flags):
            concave_ngons.append((f, concave_flags))

    # ——— 6) for each concave ngon, brute-force the best loop-0 ——————————
    for face, concave_flags in concave_ngons:
        loops_idx = [l.vert.index for l in face.loops]
        N = len(loops_idx)

        # which original tris fell into this face?
        orig_tris = {
            orig_face_verts[i] for i in new_to_orig.get(face.index, [])
        }

        best_k, best_score = 0, -1
        for k in range(N):
            rot = loops_idx[k:] + loops_idx[:k]

            # tiny test bmesh
            tb = bmesh.new()
            inv = {}
            for vid in rot:
                tv = tb.verts.new(bm.verts[vid].co)
                inv[tv] = vid
            tb.faces.new([next(tv for tv,vv in inv.items() if vv==vid) for vid in rot])
            tb.faces.ensure_lookup_table()
            tb.normal_update()

            # ear-clip triangulate
            res = bmesh.ops.triangulate(
                tb,
                faces       = tb.faces[:],
                quad_method = 'BEAUTY',
                ngon_method = 'EAR_CLIP',
            )

            out_tris = {
                frozenset(inv[v] for v in tri.verts)
                for tri in res['faces']
            }

            score = len(out_tris & orig_tris)
            if score > best_score:
                best_score, best_k = score, k

            tb.free()

        # ——— 7) rebuild the real face with the winning rotation ————————
        # orig_loops = list(face.loops)
        # orig_verts = [l.vert for l in orig_loops]
        # orig_uvs   = [l[uv_layer].uv.copy() for l in orig_loops] if uv_layer else None
        # mat, sm    = face.material_index, face.smooth

        # rv = orig_verts[best_k:] + orig_verts[:best_k]
        # ru = (orig_uvs[best_k:] + orig_uvs[:best_k]) if orig_uvs else None

        # bm.faces.remove(face)
        # newf = bm.faces.new(rv)
        # newf.material_index = mat
        # newf.smooth         = sm

        # if ru:
        #     for loop, uv in zip(newf.loops, ru):
        #         loop[uv_layer].uv = uv

        fn_layer = bm.loops.layers.float_vector.get("orig_normals")

        # inside the loop where you rebuild each ngon:
        orig_loops = list(face.loops)
        orig_verts = [l.vert for l in orig_loops]
        orig_uvs   = [l[uv_layer].uv.copy() for l in orig_loops] if uv_layer else None
        orig_nrs   = [l[fn_layer].copy() for l in orig_loops] if fn_layer else None
        mat, sm    = face.material_index, face.smooth

        # rotated lists…
        rv = orig_verts[best_k:] + orig_verts[:best_k]
        ru = (orig_uvs[best_k:] + orig_uvs[:best_k]) if orig_uvs else None
        rn = (orig_nrs[best_k:] + orig_nrs[:best_k]) if orig_nrs else None

        bm.faces.remove(face)
        newf = bm.faces.new(rv)
        newf.material_index = mat
        newf.smooth         = sm

        if uv_layer and ru:
            for loop, uv in zip(newf.loops, ru):
                loop[uv_layer].uv = uv

        if fn_layer and rn:
            for loop, nr in zip(newf.loops, rn):
                loop[fn_layer] = nr

    # clean up the pristine copy
    orig_bm.free()

    return bm