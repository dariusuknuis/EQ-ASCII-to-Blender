import bmesh, math
from collections import deque
from mathutils import Vector

def rearrange_uvs(bm, tol=1e-6):
    """
    Given a BMesh `bm`, flood‐fill vertex‐based UV chunks and integer‐tile‐align them.
    If no UV map is present, returns `bm` unmodified.
    """
    # 1) Grab active UV layer, bail early if none
    luv = bm.loops.layers.uv.active
    if not luv:
        print("No UV map found; skipping UV stitching.")
        return bm

    # 2) Helpers
    def loc_key(v):
        return (round(v.co.x,6), round(v.co.y,6), round(v.co.z,6))
    def raw_uv(v):
        l = next(iter(v.link_loops))
        u, vv = l[luv].uv
        return (round(u,3), round(vv,3))
    def frac_uv(raw):
        return (raw[0] % 1.0, raw[1] % 1.0)

    # 3) Precompute per-vertex lookups
    pos_groups = {}   # loc_key → [verts]
    vert_loc   = {}   # vert → loc_key
    vert_raw   = {}   # vert → raw_uv
    vert_mat   = {}   # vert → material_index
    for v in bm.verts:
        lk = loc_key(v)
        pos_groups.setdefault(lk, []).append(v)
        vert_loc[v] = lk
        vert_raw[v] = raw_uv(v)
        vert_mat[v] = v.link_loops[0].face.material_index

    # 4) Phase 1: vertex-seeded BFS chunks
    seen   = set()
    chunks = []
    for seed in bm.verts:
        if seed in seen:
            continue
        chunk_vs = {seed}
        queue    = deque([seed])
        while queue:
            v = queue.popleft()
            # face-adjacency
            for f in v.link_faces:
                for v2 in f.verts:
                    if v2 not in chunk_vs:
                        chunk_vs.add(v2)
                        queue.append(v2)
            # UV-adjacency at same loc + exact raw + same material
            u0, m0 = vert_raw[v], vert_mat[v]
            for v2 in pos_groups[vert_loc[v]]:
                if (v2 not in chunk_vs
                    and vert_mat[v2]==m0
                    and vert_raw[v2]==u0):
                    chunk_vs.add(v2)
                    queue.append(v2)
        # collect loops and loc maps for merging
        chunk_ls = {l for v in chunk_vs for l in v.link_loops}
        loc_map  = {vert_loc[v]: v for v in chunk_vs}
        locs     = set(loc_map)
        chunks.append({
            "verts":   chunk_vs,
            "loops":   chunk_ls,
            "loc_map": loc_map,
            "locs":    locs,
        })
        seen |= chunk_vs

    # 5) Phase 2: merge & integer-align pairwise
    i = 0
    while i < len(chunks):
        base = chunks[i]
        merged_any = True
        while merged_any:
            merged_any = False
            for j in range(i+1, len(chunks)):
                other = chunks[j]
                common = base["locs"] & other["locs"]
                if not common:
                    continue
                for loc in common:
                    vb = base["loc_map"][loc]
                    vo = other["loc_map"][loc]
                    if vert_mat[vb] != vert_mat[vo]:
                        continue
                    fa = frac_uv(vert_raw[vb])
                    fb = frac_uv(vert_raw[vo])
                    if abs(fa[0]-fb[0])>tol or abs(fa[1]-fb[1])>tol:
                        continue
                    # compute integer offset
                    ru, rv = vert_raw[vb], vert_raw[vo]
                    delta  = Vector((ru[0]-rv[0], ru[1]-rv[1]))
                    di     = Vector((round(delta.x), round(delta.y)))
                    if di.length_squared:
                        # shift other chunk UVs
                        for l in other["loops"]:
                            l[luv].uv += di
                        # update raw_uv
                        for v3 in other["verts"]:
                            u3, v3y = vert_raw[v3]
                            vert_raw[v3] = (u3 + di.x, v3y + di.y)
                    # merge other into base
                    base["verts"].update(other["verts"])
                    base["loops"].update(other["loops"])
                    base["loc_map"].update(other["loc_map"])
                    base["locs"].update(other["locs"])
                    del chunks[j]
                    merged_any = True
                    break
                if merged_any:
                    break
        i += 1

    return bm

def merge_verts_by_attrs(bm,
                         vcol_name=None,
                         float_vec_name=None,
                         tol=1e-6):
    """
    Merge co-located verts in `bm` that share:
      • the same material on all loops,
      • the same UV on all loops (active UV map),
      • the same vertex-color on all loops (per-vertex or per-loop),
      • the same custom vector attribute on all loops (float_vector layer).

    Now quantizes:
      – loop.float_vector to signed-byte (±128) steps of 1/128,
      – loop.color     to unsigned-byte (0–255) steps of 1/255.
    """
    # — quantizers —
    def quantize_255(c):
        i = int(round(c * 255.0))
        if i < 0:   i = 0
        if i > 255: i = 255
        return i / 255.0

    def quantize_128(c):
        i = int(round(c * 128.0))
        if i < -128: i = -128
        if i >  127: i =  127
        return i / 128.0

    # — UV layer (must exist) —
    luv = bm.loops.layers.uv.active
    if not luv:
        return bm  # nothing to do

    # — Vertex-color layer? prefer per-vert —
    vcol_vert = None
    if vcol_name:
        vcol_vert = (bm.verts.layers.color.get(vcol_name)
                     or bm.verts.layers.float_color.get(vcol_name))
    else:
        vcol_vert = next(iter(bm.verts.layers.color.values()), None) \
                 or next(iter(bm.verts.layers.float_color.values()), None)

    # — Fallback to per-loop color —
    vcol_loop = None
    if not vcol_vert:
        if vcol_name:
            vcol_loop = (bm.loops.layers.color.get(vcol_name)
                         or bm.loops.layers.float_color.get(vcol_name))
            if not vcol_loop:
                raise RuntimeError(f"Vertex-color layer '{vcol_name}' not found")
        else:
            vcol_loop = (bm.loops.layers.color.active
                         or bm.loops.layers.float_color.active)
        if not vcol_loop:
            raise RuntimeError("No vertex-color layer found")

    # — Float-vector layer (per-loop) —
    vec_layer = None
    if float_vec_name:
        vec_layer = bm.loops.layers.float_vector.get(float_vec_name)
        if not vec_layer:
            raise RuntimeError(f"Float-vector layer '{float_vec_name}' not found")
    else:
        vec_layer = next(iter(bm.loops.layers.float_vector.values()), None)
    if not vec_layer:
        raise RuntimeError("No float_vector layer found")

    # — Helpers to extract a *quantized* attribute signature —
    def pos_key(v):
        return (round(v.co.x,6), round(v.co.y,6), round(v.co.z,6))

    def loop_uv(l):
        # UV precision usually higher, keep 6 decimal places.
        return (round(l[luv].uv.x,6), round(l[luv].uv.y,6))

    def vert_color(v):
        # quantize per-vertex color to 0..255
        col = v[vcol_vert]
        return tuple(quantize_255(c) for c in col)

    def loop_color(l):
        # quantize per-loop color to 0..255
        col = l[vcol_loop]
        return tuple(quantize_255(c) for c in col)

    def loop_vec(l):
        # quantize float vector to signed byte steps of 1/128
        x,y,z = l[vec_layer]
        return (quantize_128(x),
                quantize_128(y),
                quantize_128(z))

    # — Build buckets by attribute-tuple —
    buckets = {}
    for v in bm.verts:
        p    = pos_key(v)
        mats = {l.face.material_index for l in v.link_loops}
        uvs  = {loop_uv(l)    for l in v.link_loops}
        cols = ({vert_color(v)}
                if vcol_vert
                else {loop_color(l) for l in v.link_loops})
        vecs = {loop_vec(l)   for l in v.link_loops}

        # require exactly one unique value per attribute
        if len(mats)!=1 or len(uvs)!=1 or len(cols)!=1 or len(vecs)!=1:
            continue

        key = (p,
               mats.pop(),
               uvs.pop(),
               cols.pop(),
               vecs.pop())
        buckets.setdefault(key, []).append(v)

    # — Merge each group of duplicates —
    for verts in buckets.values():
        if len(verts) <= 1:
            continue
        # merge into the first vert’s position
        co = verts[0].co.copy()
        bmesh.ops.pointmerge(bm, verts=verts, merge_co=co)

    return bm

def dissolve_mid_edge_verts(bm, angle_limit=0.01):
    """
    1) Dissolve any boundary vertex whose two boundary edges deviate
       from straight by <= angle_limit, but never if that vertex
       is part of a UV seam or would collapse away a seam.
    2) Triangulate with BEAUTY for quads and EAR_CLIP for ngons.
    """
    
    # precompute dot threshold for |angle - pi| <= angle_limit
    cos_eps = math.cos(angle_limit)
    thresh  = 1.0 - cos_eps  # so |dot + 1| < thresh → within angle_limit of straight

    to_dissolve = []
    for v in bm.verts:
        # --- protection: skip any vertex that is part of or supports a UV seam ---
        # a) if any incident edge is already a seam, skip
        if any(e.seam for e in v.link_edges):
            continue
        # b) if any face using this vertex has a different seam on another edge, skip
        skip = False
        for f in v.link_faces:
            for e in f.edges:
                if e is not None and e.seam:
                    skip = True
                    break
            if skip:
                break
        if skip:
            continue

        # --- boundary‐edge colinearity test ---
        b_eds = [e for e in v.link_edges if len(e.link_faces)==1]
        if len(b_eds) != 2:
            continue

        p = v.co
        a = b_eds[0].other_vert(v).co
        b = b_eds[1].other_vert(v).co

        d1 = (a - p).normalized()
        d2 = (b - p).normalized()
        dot = d1.dot(d2)

        # if |dot + 1| < thresh → nearly straight
        if abs(dot + 1.0) < thresh:
            to_dissolve.append(v)

    if to_dissolve:
        bmesh.ops.dissolve_verts(
            bm,
            verts          = to_dissolve,
            use_face_split = False
        )
        print(f"Dissolved {len(to_dissolve)} boundary verts within {angle_limit} rad, skipping seams.")
    else:
        print("No boundary verts qualified for dissolve (all protected by seams or not colinear).")

    # now triangulate everything
    faces = [f for f in bm.faces]
    bmesh.ops.triangulate(
        bm,
        faces        = faces,
        quad_method  = 'BEAUTY',
        ngon_method  = 'EAR_CLIP',
    )
    print(f"Triangulated {len(faces)} faces (BEAUTY quads, EAR_CLIP ngons).")

    return bm
