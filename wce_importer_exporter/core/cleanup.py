import bmesh
from math import pi

def cleanup_mesh_geometry(bm, area_threshold=1e-10, dissolve_dist=1e-4, max_passes=8):
    """
    Iteratively deletes loose verts/edges, degenerate faces,
    and performs dissolve_degenerate until no more geometry can be removed.
    Operates in-place on the given mesh.
    """
    for _ in range(max_passes):
        changed = False

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # 1. Delete loose verts/edges and degenerate faces
        loose_verts = [v for v in bm.verts if not v.link_edges]
        loose_edges = [e for e in bm.edges if not e.link_faces]
        degenerate_faces = [f for f in bm.faces if f.calc_area() < area_threshold]

        geom_to_delete = loose_verts + loose_edges + degenerate_faces

        if geom_to_delete:
            if loose_edges or (loose_verts and degenerate_faces):
                context = 'EDGES'
            elif degenerate_faces:
                context = 'FACES'
            else:
                context = 'VERTS'
            bmesh.ops.delete(bm, geom=geom_to_delete, context=context)
            changed = True

        # 2. Dissolve degenerate geometry
        res = bmesh.ops.dissolve_degenerate(bm, dist=dissolve_dist, edges=list(bm.edges))
        if res and any(res.get(k) for k in ('edges', 'verts', 'faces')):
            changed = True

        if not changed:
            break

def mesh_boundary_cleanup(bm, thin_thresh=0.001, angle_tol=1e-3):
    """
    In-place on `bm`:
      1) Dissolve vertices on any face whose thinness ratio ≤ thin_thresh,
         but only those vertices that have exactly 2 incident edges.
      2) Rebuild normals & lookup tables.
      3) Dissolve any boundary-vert with exactly 2 boundary edges that are nearly colinear
         (dot(d1,d2) ≈ -1 within angle_tol).
    Returns the modified bm.
    """
    # ——— Pass 1: thin-face vertices ———
    bm.faces.ensure_lookup_table()
    thin_verts = set()
    for f in bm.faces:
        # area & perimeter
        area = f.calc_area()
        peri = 0.0
        verts = f.verts
        n = len(verts)
        for i in range(n):
            peri += (verts[i].co - verts[(i+1)%n].co).length
        tr = (4.0*pi*area)/(peri*peri) if peri > 0 else 0.0
        if tr <= thin_thresh:
            for v in verts:
                if len(v.link_edges) == 2:
                    thin_verts.add(v)

    if thin_verts:
        bmesh.ops.dissolve_verts(bm,
                                 verts=list(thin_verts),
                                 use_face_split=False)

    # ——— Refresh normals & tables ———
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # ——— Pass 2: colinear boundary vertices ———
    col_verts = []
    eps = angle_tol
    for v in bm.verts:
        if len(v.link_edges) != 2:
            continue
        # pick out the two boundary edges
        b_edges = [e for e in v.link_edges if len(e.link_faces) == 1]
        if len(b_edges) != 2:
            continue

        v1 = b_edges[0].other_vert(v)
        v2 = b_edges[1].other_vert(v)
        d1 = (v1.co - v.co)
        d2 = (v2.co - v.co)
        if d1.length == 0 or d2.length == 0:
            continue
        if abs(d1.normalized().dot(d2.normalized()) + 1.0) < eps:
            col_verts.append(v)

    if col_verts:
        bmesh.ops.dissolve_verts(bm,
                                 verts=col_verts,
                                 use_face_split=False)

    return bm