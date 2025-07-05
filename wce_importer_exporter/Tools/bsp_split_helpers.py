import bmesh
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
        orig_loops = list(face.loops)
        orig_verts = [l.vert for l in orig_loops]
        orig_uvs   = [l[uv_layer].uv.copy() for l in orig_loops] if uv_layer else None
        mat, sm    = face.material_index, face.smooth

        rv = orig_verts[best_k:] + orig_verts[:best_k]
        ru = (orig_uvs[best_k:] + orig_uvs[:best_k]) if orig_uvs else None

        bm.faces.remove(face)
        newf = bm.faces.new(rv)
        newf.material_index = mat
        newf.smooth         = sm

        if ru:
            for loop, uv in zip(newf.loops, ru):
                loop[uv_layer].uv = uv

    # clean up the pristine copy
    orig_bm.free()

    return bm

def rotate_face_loops(bm):
    uv_layer = bm.loops.layers.uv.active  # may be None

    # Copy the original face list so we can rebuild safely
    original_faces = list(bm.faces)

    for face in original_faces:
        if not face.is_valid:
            continue
        """Rebuild `face`, rotating its loops so the pivot falls after the flattest convex cluster."""
        loops = list(face.loops)
        N     = len(loops)
        if N < 4:
            continue  # nothing to do for tris

        # Classify concave corners
        concave = [False] * N
        for i, l in enumerate(loops):
            v_prev = l.link_loop_prev.vert.co
            v_curr = l.vert.co
            v_next = l.link_loop_next.vert.co

            e1 = v_prev - v_curr
            e2 = v_next - v_curr
            turn = e1.cross(e2).dot(face.normal)
            concave[i] = (turn < 0)

        # Find convex indices
        convex_idx = [i for i in range(N) if not concave[i]]
        if not convex_idx:
            continue  # fully concave? leave it

        # Build clusters between convex corners
        clusters = []
        for j in range(len(convex_idx)):
            start = convex_idx[j]
            end   = convex_idx[(j + 1) % len(convex_idx)]
            seg = []
            k = (start + 1) % N
            while k != end:
                seg.append(k)
                k = (k + 1) % N
            clusters.append((start, end, seg))

        # Pick the cluster with the fewest concave verts
        best = min(clusters, key=lambda ce: sum(concave[i] for i in ce[2]))
        _, anchor_idx, _ = best

        # New loop 0 is the one after the anchor
        new0 = (anchor_idx) % N

        # Snapshot geometry & UVs
        orig_verts = [l.vert for l in loops]
        orig_uvs   = [l[uv_layer].uv.copy() for l in loops] if uv_layer else None
        mat_idx    = face.material_index
        smooth     = face.smooth

        # Rotate
        rot_verts = orig_verts[new0:] + orig_verts[:new0]
        rot_uvs   = (orig_uvs[new0:] + orig_uvs[:new0]) if orig_uvs else None

        # Rebuild face
        bm.faces.remove(face)
        new_face = bm.faces.new(rot_verts)
        new_face.material_index = mat_idx
        new_face.smooth = smooth

        # Reapply UVs
        if uv_layer and rot_uvs:
            for loop, uv in zip(new_face.loops, rot_uvs):
                loop[uv_layer].uv = uv

    return bm
            
def is_uv_affine_ngon(verts, uv_layer, uv_tol=15e-3):

    n = len(verts)
    if n < 3:
        return False
    normal = None
    for v in verts:
        if v.link_faces:
            normal = v.link_faces[0].normal.copy()
            break
    if not normal or normal.length == 0:
        return False
    axis = normal.normalized()
    helper = Vector((1,0,0))
    if abs(axis.dot(helper)) > 0.9:
        helper = Vector((0,1,0))
    t = axis.cross(helper).normalized()
    b = t.cross(axis)
    to2d = Matrix((t, b, axis)).transposed()
    P2 = [(to2d @ v.co).to_2d() for v in verts]
    U  = [next(l[uv_layer].uv.copy() for l in v.link_loops) for v in verts]
    p0,p1,p2 = P2[0], P2[1], P2[2]
    u0,u1,u2 = U [0], U [1], U [2]
    M = Matrix(((p1.x-p0.x, p2.x-p0.x),
                (p1.y-p0.y, p2.y-p0.y)))
    if abs(M.determinant()) < 1e-8:
        return False
    Minv = M.inverted()
    Umat = Matrix(((u1.x-u0.x, u2.x-u0.x),
                   (u1.y-u0.y, u2.y-u0.y)))
    A = Umat @ Minv
    t_vec = u0 - A @ p0
    for pi, ui in zip(P2[3:], U[3:]):
        if (A @ pi + t_vec - ui).length > uv_tol:
            return False
    return True

def dissolve_uv_affine_edges(bm, angle_deg=1.0, uv_tol=15e-3):
    """
    Dissolve _all_ manifold edges with dihedral < angle_deg AND
    perfectly affine UVs, but never touch any edge marked as a seam
    or any edge that would share a face with an existing seam.
    """

    uv_layer = bm.loops.layers.uv.get("UVMap")
    if not uv_layer:
        raise RuntimeError("No UVMap on this BMesh!")
    angle_tol = radians(angle_deg)

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # make sure our normals are up to date
    bm.normal_update()

    to_dissolve = []
    for e in bm.edges:
        # 1) never dissolve a known seam
        if e.seam:
            continue

        # 2) only pure 2-face manifold edges
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces

        # 3) never dissolve an edge that sits on any seam-bearing face
        #    (so we don't accidentally collapse away the seam)
        skip = False
        for f in (f1, f2):
            for ed in f.edges:
                if ed is not e and ed.seam:
                    skip = True
                    break
            if skip:
                break
        if skip:
            continue

        # 4) angle test
        if f1.normal.angle(f2.normal) > angle_tol:
            continue

        # 5) build the ordered two‐face patch verts
        patch_verts = []
        seen = set()
        for f in (f1, f2):
            for v in f.verts:
                if v not in seen:
                    seen.add(v)
                    patch_verts.append(v)

        # 6) UV‐affine test
        if is_uv_affine_ngon(patch_verts, uv_layer, uv_tol):
            to_dissolve.append(e)

    if to_dissolve:
        bmesh.ops.dissolve_edges(
            bm,
            edges=to_dissolve,
            use_verts=False,
            use_face_split=False,
        )

    for e in bm.edges:
        e.seam = False