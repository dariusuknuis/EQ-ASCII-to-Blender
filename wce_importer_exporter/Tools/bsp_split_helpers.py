import bmesh
from math import radians
from mathutils import Vector, Matrix

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