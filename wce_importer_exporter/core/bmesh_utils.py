import bmesh
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
      • a float_vector layer whose quantized indices differ by at most 1.

    `tol` controls the positional snapping tolerance for merging.
    """
    # — quantizers —
    def quantize_255(c):
        i = int(round(c * 255.0))
        return max(0, min(255, i))

    def quantize_127(c):
        i = int(round(c * 127.0))
        return max(-127, min(127, i))

    # — get layers —
    luv = bm.loops.layers.uv.active
    if not luv:
        return bm  # no UV → nothing to do

    # color: try per-vert then per-loop
    vcol_vert = (bm.verts.layers.color.get(vcol_name)
                 or bm.verts.layers.float_color.get(vcol_name)
                 if vcol_name else
                 next(iter(bm.verts.layers.color.values()), None)
                 or next(iter(bm.verts.layers.float_color.values()), None))
    if not vcol_vert:
        # fallback to loop‑color
        vcol_loop = (bm.loops.layers.color.get(vcol_name)
                     or bm.loops.layers.float_color.get(vcol_name)
                     if vcol_name else
                     bm.loops.layers.color.active
                     or bm.loops.layers.float_color.active)
        if not vcol_loop:
            raise RuntimeError("No vertex-color layer found")
    else:
        vcol_loop = None

    # float_vector (per-loop)
    vec_layer = (bm.loops.layers.float_vector.get(float_vec_name)
                 if float_vec_name else
                 next(iter(bm.loops.layers.float_vector.values()), None))
    if not vec_layer:
        raise RuntimeError("No float_vector layer found")

    # — helpers to pull per-vert / per-loop values —
    def pos_key(v):
        return (round(v.co.x,6), round(v.co.y,6), round(v.co.z,6))

    def loop_uv(l):
        return (round(l[luv].uv.x,6), round(l[luv].uv.y,6))

    def vert_color(v):
        col = v[vcol_vert]
        return tuple(quantize_255(c) for c in col)

    def loop_color(l):
        col = l[vcol_loop]
        return tuple(quantize_255(c) for c in col)

    def vert_vec_index(v):
        # average per-loop, then quantize to integer index
        idxs = []
        for l in v.link_loops:
            x,y,z = l[vec_layer]
            idxs.append((
                quantize_127(x),
                quantize_127(y),
                quantize_127(z),
            ))
        # if multiple loops, pick the most common triple
        from collections import Counter
        return Counter(idxs).most_common(1)[0][0]

    # — 1) bucket by everything except the float‑vector —
    buckets = {}
    for v in bm.verts:
        p    = pos_key(v)
        mats = {l.face.material_index for l in v.link_loops}
        uvs  = {loop_uv(l)    for l in v.link_loops}
        cols = ({vert_color(v)}
                if vcol_vert
                else {loop_color(l) for l in v.link_loops})

        if len(mats)!=1 or len(uvs)!=1 or len(cols)!=1:
            continue

        key = (p, mats.pop(), uvs.pop(), cols.pop())
        buckets.setdefault(key, []).append(v)

    # — 2) within each bucket, cluster by vec‐indices ±1 —
    for verts in buckets.values():
        if len(verts) <= 1:
            continue

        # gather (vert, its vec‐index triple)
        verts_idx = [(v, vert_vec_index(v)) for v in verts]

        # build adjacency: two verts connect if each component differs ≤1
        adj = {v: set() for v,_ in verts_idx}
        for i,(v1,idx1) in enumerate(verts_idx):
            for v2,idx2 in verts_idx[i+1:]:
                if all(abs(idx1[k] - idx2[k]) <= 1 for k in range(3)):
                    adj[v1].add(v2)
                    adj[v2].add(v1)

        # find connected‐components in this small graph
        seen = set()
        for v in adj:
            if v in seen:
                continue
            # BFS
            comp = {v}
            stack = [v]
            while stack:
                u = stack.pop()
                for w in adj[u]:
                    if w not in comp:
                        comp.add(w)
                        stack.append(w)
            seen |= comp
            if len(comp) > 1:
                # merge this component down to the first vertex
                target = next(iter(comp))
                co = target.co.copy()
                bmesh.ops.pointmerge(bm, verts=list(comp), merge_co=co)

    return bm

def bmesh_with_split_norms(obj):

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

    return bm

def mesh_from_bmesh_with_split_norms(bm, mesh):
    me = mesh.data
    bm.to_mesh(me)
    me.update()
    ln_layer = bm.loops.layers.float_vector.get("orig_normals")
    if not ln_layer:
        raise RuntimeError("Loop layer 'orig_normals' not found")

    # 3) accumulate normals per vertex
    vert_accum = {v.index: Vector((0,0,0)) for v in bm.verts}
    vert_count = {v.index: 0               for v in bm.verts}
    for f in bm.faces:
        for l in f.loops:
            n = l[ln_layer]
            vert_accum[l.vert.index] += n
            vert_count[l.vert.index] += 1

    # 4) build an averaged, normalized normal per-vertex
    vert_normal = {}
    for vid, total in vert_accum.items():
        cnt = vert_count[vid]
        if cnt > 0:
            vert_normal[vid] = (total / cnt).normalized()
        else:
            vert_normal[vid] = total.normalized()

    # 5) now build your final loop_normals array
    loops = [l for f in bm.faces for l in f.loops]
    loop_normals = [vert_normal[l.vert.index] for l in loops]
    bm.free()

    me.use_auto_smooth = True
    me.normals_split_custom_set(loop_normals)

    ln_attr = me.attributes.get("orig_normals")
    if ln_attr:
        me.attributes.remove(me.attributes.get("orig_normals"))
    
    