import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix, kdtree, bvhtree
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from create_bounding_sphere import create_bounding_sphere
from modify_regions_and_worldtree import modify_regions_and_worldtree, create_bounding_volume_for_region_empties
from create_worldtree import create_worldtree
from .finalize_region_meshes import finalize_region_meshes
from .bsp_split_helpers import mark_color_seams, mesh_cleanup, dissolve_colinear_geo
from .format_helpers import merge_verts_by_attrs
from .bmesh_with_split_norms import bmesh_with_split_norms, mesh_from_bmesh_with_split_norms
import math
from math import pi
import re
import numpy as np

# ------------------------------------------------------------
# --- Helper: AABB Intersection
# ------------------------------------------------------------

def aabb_intersects(minA, maxA, minB, maxB):
    """Return True if two axis-aligned bounding boxes intersect, False otherwise."""
    if (maxA.x < minB.x or minA.x > maxB.x): return False
    if (maxA.y < minB.y or minA.y > maxB.y): return False
    if (maxA.z < minB.z or minA.z > maxB.z): return False
    return True

def object_world_aabb(obj):
    """
    Compute the world-space axis-aligned bounding box of an object
    by transforming its vertex positions.
    """
    if not obj or obj.type != 'MESH' or not obj.data.vertices:
        return Vector((0,0,0)), Vector((0,0,0))
    mat = obj.matrix_world
    local_coords = [v.co for v in obj.data.vertices]
    minb = Vector((float('inf'), float('inf'), float('inf')))
    maxb = Vector((float('-inf'), float('-inf'), float('-inf')))
    for co in local_coords:
        wco = mat @ co
        minb.x = min(minb.x, wco.x)
        minb.y = min(minb.y, wco.y)
        minb.z = min(minb.z, wco.z)
        maxb.x = max(maxb.x, wco.x)
        maxb.y = max(maxb.y, wco.y)
        maxb.z = max(maxb.z, wco.z)
    return minb, maxb

# ------------------------------------------------------------
# --- Standard Helper Functions
# ------------------------------------------------------------

def calculate_bounds(obj):
    """Compute object-space bounding box of obj.data."""
    local_coords = [v.co for v in obj.data.vertices]
    min_bound = Vector((float('inf'), float('inf'), float('inf')))
    max_bound = Vector((float('-inf'), float('-inf'), float('-inf')))
    for co in local_coords:
        min_bound.x = min(min_bound.x, co.x)
        min_bound.y = min(min_bound.y, co.y)
        min_bound.z = min(min_bound.z, co.z)
        max_bound.x = max(max_bound.x, co.x)
        max_bound.y = max(max_bound.y, co.y)
        max_bound.z = max(max_bound.z, co.z)
    return min_bound, max_bound

def calculate_bounds_for_bmesh(bm):
    """Compute the bounding box of the bmesh geometry (object-space)."""
    minb = Vector((float('inf'), float('inf'), float('inf')))
    maxb = Vector((float('-inf'), float('-inf'), float('-inf')))
    for v in bm.verts:
        minb.x = min(minb.x, v.co.x)
        minb.y = min(minb.y, v.co.y)
        minb.z = min(minb.z, v.co.z)
        maxb.x = max(maxb.x, v.co.x)
        maxb.y = max(maxb.y, v.co.y)
        maxb.z = max(maxb.z, v.co.z)
    return minb, maxb

def normalize_bounds(min_bound, max_bound, target_size):
    """Expand the bounds so that each side is an integer multiple of target_size."""
    center = (min_bound + max_bound) * 0.5
    extents = max_bound - min_bound
    adjusted_size = Vector((
        math.ceil(extents.x / target_size) * target_size,
        math.ceil(extents.y / target_size) * target_size,
        math.ceil(extents.z / target_size) * target_size
    ))
    new_min = center - adjusted_size * 0.5
    new_max = center + adjusted_size * 0.5
    return new_min, new_max

def create_world_volume(vol_min, vol_max):
    """
    Create a new mesh object named `name` whose geometry is 
    the rectangular prism spanning vol_min→vol_max.
    Returns the new Object (already linked to the active collection).
    """

    bm = bmesh.new()

    # 8 corners
    v0 = Vector((vol_min.x, vol_min.y, vol_min.z))
    v1 = Vector((vol_max.x, vol_min.y, vol_min.z))
    v2 = Vector((vol_max.x, vol_max.y, vol_min.z))
    v3 = Vector((vol_min.x, vol_max.y, vol_min.z))
    v4 = Vector((vol_min.x, vol_min.y, vol_max.z))
    v5 = Vector((vol_max.x, vol_min.y, vol_max.z))
    v6 = Vector((vol_max.x, vol_max.y, vol_max.z))
    v7 = Vector((vol_min.x, vol_max.y, vol_max.z))

    bm_verts = [
        bm.verts.new(v0),
        bm.verts.new(v1),
        bm.verts.new(v2),
        bm.verts.new(v3),
        bm.verts.new(v4),
        bm.verts.new(v5),
        bm.verts.new(v6),
        bm.verts.new(v7),
    ]
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()

    # each face as a quad of those verts
    faces = [
        (0, 1, 2, 3),  # bottom
        (4, 5, 6, 7),  # top
        (0, 4, 5, 1),  # front
        (1, 5, 6, 2),  # right
        (2, 6, 7, 3),  # back
        (3, 7, 4, 0),  # left
    ]

    for idx_tuple in faces:
        vA, vB, vC, vD = (bm_verts[i] for i in idx_tuple)
        try:
            bm.faces.new((vA, vB, vC, vD))
        except ValueError:
            # face might already exist if you run this twice; ignore
            pass

    # 4) Finalize: ensure lookup tables and normals are valid
    bm.faces.index_update()
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()

    return bm

def fix_concave_ngons(bm_half, bm_orig, tol):
    FMAP = "orig_face"
    VMAP = "orig_vert"

    # ensure up‐to‐date tables & normals
    bm_half.verts.ensure_lookup_table()
    bm_half.faces.ensure_lookup_table()
    bm_half.normal_update()
    bm_orig.verts.ensure_lookup_table()
    bm_orig.faces.ensure_lookup_table()
    bm_orig.normal_update()

    fmap_h = bm_half.faces.layers.face_map[FMAP]
    fmap_o = bm_orig.faces.layers.face_map[FMAP]
    vmap_h = bm_half.verts.layers.int[VMAP]
    vmap_o = bm_orig.verts.layers.int[VMAP]

    uv_layer = bm_half.loops.layers.uv.active
    fn_layer = bm_half.loops.layers.float_vector.get("orig_normals")

    # build EAR_CLIP triangulation of one original face → set of frozenset(orig_vert indices)
    def build_orig_tris(orig_f):
        tb = bmesh.new()
        inv = {}
        for loop in orig_f.loops:
            ov = loop.vert
            tv = tb.verts.new(ov.co)
            inv[tv] = ov[vmap_o]
        tb.faces.new(list(inv.keys()))
        tb.verts.ensure_lookup_table()
        tb.faces.ensure_lookup_table()
        tb.normal_update()
        out = bmesh.ops.triangulate(
            tb,
            faces=tb.faces[:],
            quad_method='BEAUTY',
            ngon_method='EAR_CLIP',
        )['faces']
        tris = {frozenset(inv[v] for v in tri.verts) for tri in out}
        tb.free()
        return tris

    orig_tris_cache = {}

    # find concave ngons in this half
    concaves = []
    for f in bm_half.faces:
        if len(f.verts) <= 4:
            continue
        for l in f.loops:
            p, c, n = l.link_loop_prev.vert.co, l.vert.co, l.link_loop_next.vert.co
            if (p - c).cross(n - c).dot(f.normal) > 0:
                concaves.append(f)
                break

    to_tris = []
    for f in concaves:
        ofi = f[fmap_h]
        print(f"\n[debug] Concave ngon in half: face={f.index} → original_face={ofi}")
        orig_f = bm_orig.faces[ofi]
        if ofi not in orig_tris_cache:
            orig_tris_cache[ofi] = build_orig_tris(orig_f)
        target_tris = orig_tris_cache[ofi]
        print(f"[debug]   original EAR_CLIP tris (by orig_vert): {target_tris}")

        loops_idx = [l.vert.index for l in f.loops]
        N = len(loops_idx)
        best_k, best_score, best_method = 0, -1, 'EAR_CLIP'

        for method in ('EAR_CLIP', 'BEAUTY'):
            for k in range(N):
                rot = loops_idx[k:] + loops_idx[:k]
                tb = bmesh.new()
                inv = {}
                for vid in rot:
                    tv = tb.verts.new(bm_half.verts[vid].co)
                    inv[tv] = bm_half.verts[vid][vmap_h]
                tb.faces.new(list(inv.keys()))
                tb.verts.ensure_lookup_table()
                tb.faces.ensure_lookup_table()
                tb.normal_update()
                out = bmesh.ops.triangulate(
                    tb,
                    faces=tb.faces[:],
                    quad_method='BEAUTY',
                    ngon_method=method,
                )['faces']
                test_tris = {frozenset(inv[v] for v in tri.verts) for tri in out}
                tb.free()
                score = len(test_tris & target_tris)
                print(f"[debug]     test method={method:<9} k={k:>2} → score={score}")
                if score > best_score:
                    best_score, best_k, best_method = score, k, method

        print(f"[debug]   → best: method={best_method}, k={best_k}, score={best_score}")

        # rebuild face f with best rotation
        orig_loops = list(f.loops)
        verts = [l.vert for l in orig_loops]
        uvs   = [l[uv_layer].uv.copy() for l in orig_loops] if uv_layer else None
        nrs   = [l[fn_layer].copy()     for l in orig_loops] if fn_layer else None
        mat, sm = f.material_index, f.smooth

        rv = verts[best_k:] + verts[:best_k]
        ru = (uvs[best_k:] + uvs[:best_k]) if uvs else None
        rn = (nrs[best_k:] + nrs[:best_k]) if nrs else None

        bm_half.faces.remove(f)
        newf = bm_half.faces.new(rv)
        newf.material_index = mat
        newf.smooth         = sm
        newf[fmap_h]        = ofi

        if uv_layer and ru:
            for loop, uvv in zip(newf.loops, ru):
                loop[uv_layer].uv = uvv
        if fn_layer and rn:
            for loop, nr in zip(newf.loops, rn):
                loop[fn_layer] = nr

        if best_method == 'BEAUTY':
            to_tris.append(newf)

    bm_half.normal_update()
    if to_tris:
        res = bmesh.ops.triangulate(
            bm_half,
            faces=to_tris,
            quad_method='BEAUTY',
            ngon_method='BEAUTY',
        )
        # carry face_map into each new tri
        for tri in res['faces']:
            tri[fmap_h] = tri.verts[0].link_loops[0].face[fmap_h]

    
    bm_orig.normal_update()

    # ——— CLEANUP: remove our two custom layers ——————————————
    fmap_h = bm_half.faces.layers.face_map.get(FMAP)
    if fmap_h:
        bm_half.faces.layers.face_map.remove(fmap_h)
    vmap_h = bm_half.verts.layers.int.get(VMAP)
    if vmap_h:
        bm_half.verts.layers.int.remove(vmap_h)

def terrain_cleanup(bm, angle_limit=math.radians(1.0), delimit={'SEAM','SHARP','MATERIAL','NORMAL'}):
    uv_layer = bm.loops.layers.uv.active
    fn_layer = bm.loops.layers.float_vector.get("orig_normals")

    # ——— 1) pristine copy ——————————————————————————————————————————————
    orig_bm = bm.copy()
    orig_bm.faces.ensure_lookup_table()
    orig_bm.verts.ensure_lookup_table()

    orig_centroids = {
        f.index: sum((v.co for v in f.verts), Vector()) / len(f.verts)
        for f in orig_bm.faces
    }
    orig_face_verts = {
        f.index: frozenset(v.index for v in f.verts)
        for f in orig_bm.faces
    }
    print(f"▶ Pristine: {len(orig_bm.faces)} faces, {len(orig_bm.verts)} verts")

    # ——— 2) limited dissolve on the *live* bm ————————————————————————
    all_edges = [e for e in bm.edges]
    all_verts = list({v for e in all_edges for v in e.verts})
    bmesh.ops.dissolve_limit(
        bm,
        edges                   = all_edges,
        verts                   = all_verts,
        angle_limit             = angle_limit,
        use_dissolve_boundaries = False,
        delimit                 = delimit,
    )
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    print(f"▶ After dissolve: {len(bm.faces)} faces, {len(bm.verts)} verts")

    # ——— 3) build BVH to map original faces → new faces ————————————————————
    bvh = BVHTree.FromBMesh(bm, epsilon=0.0)
    orig_to_new = {
        fi: (bvh.find_nearest(cen) or (None, None, None, None))[2]
        for fi, cen in orig_centroids.items()
    }
    new_to_orig = {}
    for o, n in orig_to_new.items():
        new_to_orig.setdefault(n, []).append(o)

    # ——— 4) find all concave ngons in dissolved mesh ————————————————————
    concave_ngons = []
    for f in bm.faces:
        if len(f.verts) <= 4:
            continue
        flags = [
            ((l.link_loop_prev.vert.co - l.vert.co)
             .cross(l.link_loop_next.vert.co - l.vert.co)
             .dot(f.normal) > 0)
            for l in f.loops
        ]
        if any(flags):
            concave_ngons.append((f, flags))
    print(f"▶ Found {len(concave_ngons)} concave ngons to re-anchor")

    # we'll collect here the BEAUTY-triangulate candidates:
    beauty_tris = []

    # ——— 5) for each concave ngon, brute-force best rotation + BEAUTY check ————
    for face, concave_flags in concave_ngons:
        loops_idx = [l.vert.index for l in face.loops]
        N = len(loops_idx)

        # per-face KDTree to remap originals → this face’s new verts
        kd = KDTree(N)
        for i, vi in enumerate(loops_idx):
            kd.insert(bm.verts[vi].co, vi)
        kd.balance()

        # gather the original triangle‐sets (in this face’s vert-space)
        orig_tris = set()
        for orig_fi in new_to_orig.get(face.index, []):
            old_vs = orig_face_verts[orig_fi]
            mapped = [kd.find(orig_bm.verts[old_vi].co)[1] for old_vi in old_vs]
            orig_tris.add(frozenset(mapped))

        print(f"\n--- Face {face.index}: loops {loops_idx}")
        print(f"    orig_tris = {orig_tris}")

        # 1) Ear-clip search
        best_k, best_score = 0, -1
        for k in range(N):
            rot = loops_idx[k:] + loops_idx[:k]
            tb = bmesh.new(); inv = {}
            for vi in rot:
                tv = tb.verts.new(bm.verts[vi].co); inv[tv] = vi
            tb.faces.new([next(tv for tv,vv in inv.items() if vv==vi) for vi in rot])
            tb.faces.ensure_lookup_table()
            tb.normal_update()
            res = bmesh.ops.triangulate(
                tb,
                faces       = tb.faces[:],
                quad_method = 'BEAUTY',
                ngon_method = 'EAR_CLIP',
            )
            out = {frozenset(inv[v] for v in tri.verts) for tri in res['faces']}
            score = len(out & orig_tris)
            print(f"    [EAR] rot k={k} start={rot[0]} → out={out}, score={score}")
            if score > best_score:
                best_score, best_k = score, k
            tb.free()
        ear_best, ear_score = best_k, best_score

        # 2) BEAUTY-only search
        beauty_best, beauty_score = 0, -1
        for k in range(N):
            rot = loops_idx[k:] + loops_idx[:k]
            tb = bmesh.new(); inv = {}
            for vi in rot:
                tv = tb.verts.new(bm.verts[vi].co); inv[tv] = vi
            tb.faces.new([next(tv for tv,vv in inv.items() if vv==vi) for vi in rot])
            tb.faces.ensure_lookup_table()
            tb.normal_update()
            res = bmesh.ops.triangulate(
                tb,
                faces       = tb.faces[:],
                quad_method = 'BEAUTY',
                ngon_method = 'BEAUTY',
            )
            out = {frozenset(inv[v] for v in tri.verts) for tri in res['faces']}
            score = len(out & orig_tris)
            print(f"    [BEA] rot k={k} start={rot[0]} → out={out}, score={score}")
            if score > beauty_score:
                beauty_score, beauty_best = score, k
            tb.free()
        print(f"  → EAR best k={ear_best}, score={ear_score}")
        print(f"  → BEA best k={beauty_best}, score={beauty_score}")

        # Decide which rotation to rebuild with:
        rebuild_k = ear_best
        want_beauty = (beauty_score > ear_score)

        # snapshot loops
        orig_loops = list(face.loops)
        verts      = [l.vert for l in orig_loops]
        uvs        = [l[uv_layer].uv.copy() for l in orig_loops] if uv_layer else None
        nrs        = [l[fn_layer].copy()     for l in orig_loops] if fn_layer else None
        mat, sm    = face.material_index, face.smooth

        # rotate verts & attrs
        rv = verts[rebuild_k:] + verts[:rebuild_k]
        ru = (uvs[rebuild_k:] + uvs[:rebuild_k]) if uvs else None
        rn = (nrs[rebuild_k:] + nrs[:rebuild_k]) if nrs else None

        # remove & rebuild as ngon
        bm.faces.remove(face)
        newf = bm.faces.new(rv)
        newf.material_index = mat
        newf.smooth         = sm
        if uv_layer and ru:
            for loop, uvv in zip(newf.loops, ru):
                loop[uv_layer].uv = uvv
        if fn_layer and rn:
            for loop, nr in zip(newf.loops, rn):
                loop[fn_layer] = nr

        # if BEAUTY strictly wins, mark this face for later triangulation
        if want_beauty:
            beauty_tris.append(newf)

    # ——— 6) do one batch BEAUTY triangulation on all marked faces —————————
    bm.normal_update()
    if beauty_tris:
        print(f"▶ triangulating {len(beauty_tris)} faces with BEAUTY at the end")
        bmesh.ops.triangulate(
            bm,
            faces        = beauty_tris,
            quad_method  = 'BEAUTY',
            ngon_method  = 'BEAUTY',
        )

    orig_bm.free()
    print("✅ mesh_cleanup_and_reanchor complete.")
    return bm

def create_region_empty(center, sphere_radius, index, pending_objects):
    """
    Create an empty (for labeling/visualization) at the given center.
    The empty is set up as a sphere with display size equal to the computed sphere radius.
    """
    empty = bpy.data.objects.new(f"R{index:06d}", None)
    empty.location = center
    empty.empty_display_type = 'SPHERE'
    empty.empty_display_size = sphere_radius
    
    empty["VISLISTBYTES"] = True
    empty["VISLIST_01"] = ""
    empty["SPRITE"] = ""

    region_empty = bpy.data.objects.get("REGION")
    if region_empty:
        empty.parent = region_empty

    pending_objects.append(empty)
    
    return empty

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

def terrain_split(bm_geo, plane_co, plane_no, tol=1e-6):
    """
    Splits the convex BMesh `bm_vgeo` by the plane (plane_co, plane_no) into
    two capped halves, and returns (bm_lower, bm_upper).

      - the “lower” half keeps the inside side (n·X + d <= 0)
      - the “upper” half keeps the outside side (n·X + d >= 0)
    """

    # tag original BMesh faces & verts
    fmap = bm_geo.faces.layers.face_map.new("orig_face")
    for f in bm_geo.faces:
        f[fmap] = f.index

    vmap = bm_geo.verts.layers.int.new("orig_vert")
    for v in bm_geo.verts:
        v[vmap] = v.index

    # copy for lower half
    bm_lower = bm_geo.copy()
    geom_l   = list(bm_lower.verts) + list(bm_lower.edges) + list(bm_lower.faces)
    bmesh.ops.bisect_plane(
        bm_lower,
        geom       = geom_l,
        plane_co   = plane_co,
        plane_no   = plane_no,
        dist       = tol,
        use_snap_center=False,
        clear_inner=False,   # keep the “inside” half
        clear_outer=True     # discard the outside
    )

    cleanup_mesh_geometry(bm_lower)
    fix_concave_ngons(bm_lower, bm_geo, tol)
    bmesh.ops.triangulate(bm_lower, faces = bm_lower.faces[:], quad_method = 'BEAUTY', ngon_method = 'EAR_CLIP',)
    terrain_cleanup(bm_lower, angle_limit=math.radians(1.0))
   
    # copy for upper half
    bm_upper = bm_geo.copy()
    geom_u   = list(bm_upper.verts) + list(bm_upper.edges) + list(bm_upper.faces)
    bmesh.ops.bisect_plane(
        bm_upper,
        geom       = geom_u,
        plane_co   = plane_co,
        plane_no   = plane_no,
        dist       = tol,
        use_snap_center=False,
        clear_inner=True,    # discard the inside
        clear_outer=False    # keep the outside half
    )
    
    cleanup_mesh_geometry(bm_upper)
    fix_concave_ngons(bm_upper, bm_geo, tol)
    bmesh.ops.triangulate(bm_upper, faces = bm_upper.faces[:], quad_method = 'BEAUTY', ngon_method = 'EAR_CLIP',)
    terrain_cleanup(bm_upper, angle_limit=math.radians(1.0))

    fmap_o = bm_geo.faces.layers.face_map.get("orig_face")
    if fmap_o:
        bm_geo.faces.layers.face_map.remove(fmap_o)
    vmap_o = bm_geo.verts.layers.int.get("orig_vert")
    if vmap_o:
        bm_geo.verts.layers.int.remove(vmap_o)

    return bm_lower, bm_upper

def volume_split(bm_vol, plane_co, plane_no, tol=1e-6):
    """
    Splits the convex BMesh `bm_vol` by the plane (plane_co, plane_no) into
    two capped halves, and returns (bm_lower, bm_upper).

      - the “lower” half keeps the inside side (n·X + d <= 0)
      - the “upper” half keeps the outside side (n·X + d >= 0)

    Both outputs are new BMesh instances with their open boundaries filled.
    """
    # copy for lower half
    bm_lower = bm_vol.copy()
    geom_l   = list(bm_lower.verts) + list(bm_lower.edges) + list(bm_lower.faces)
    bmesh.ops.bisect_plane(
        bm_lower,
        geom       = geom_l,
        plane_co   = plane_co,
        plane_no   = plane_no,
        dist       = tol,
        clear_inner=False,   # keep the “inside” half
        clear_outer=True     # discard the outside
    )
    # cap the cut
    boundary = [e for e in bm_lower.edges if len(e.link_faces)==1]
    if boundary:
        bmesh.ops.holes_fill(bm_lower, edges=boundary, sides=0)
    # fix normals
    bmesh.ops.recalc_face_normals(bm_lower, faces=bm_lower.faces)
    bm_lower.normal_update()

    # copy for upper half
    bm_upper = bm_vol.copy()
    geom_u   = list(bm_upper.verts) + list(bm_upper.edges) + list(bm_upper.faces)
    bmesh.ops.bisect_plane(
        bm_upper,
        geom       = geom_u,
        plane_co   = plane_co,
        plane_no   = plane_no,
        dist       = tol,
        clear_inner=True,    # discard the inside
        clear_outer=False    # keep the outside half
    )
    boundary = [e for e in bm_upper.edges if len(e.link_faces)==1]
    if boundary:
        bmesh.ops.holes_fill(bm_upper, edges=boundary, sides=0)
    bmesh.ops.recalc_face_normals(bm_upper, faces=bm_upper.faces)
    bm_upper.normal_update()

    return bm_lower, bm_upper

def create_mesh_object_from_bmesh(bm, name, original_obj, pending_objects):
    """
    Create a new mesh object from bm:
     1) copy original materials & custom props
     2) apply world transform into the mesh data
     3) compute world-space AABB → center & radius
     4) recenter geometry so that AABB-center is at origin
     5) set object.matrix_world to put it back at that center
     6) call create_bounding_sphere() with the computed radius
    """

    cleanup_mesh_geometry(bm)

    # --- build the mesh & object ---
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)

    # access split normal data from float vector layer
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

    # --- Set vertex color layer as active (or it doesn't display automatically) ---
    col_attr = me.color_attributes.get("Color")
    if col_attr:
        me.color_attributes.active_color = col_attr
        
    me.use_auto_smooth = True
    me.normals_split_custom_set(loop_normals)

    ln_attr = me.attributes.get("orig_normals")
    if ln_attr:
        me.attributes.remove(me.attributes.get("orig_normals"))

    # create the object
    new_obj = bpy.data.objects.new(name, me)
    pending_objects.append(new_obj)

    # copy materials
    for mat in original_obj.data.materials:
        new_obj.data.materials.append(mat)

    # copy custom props
    for key in original_obj.keys():
        if key != "_RNA_UI":
            new_obj[key] = original_obj[key]

    # add PASSABLE geo‑node modifier if available
    if "PASSABLE" in bpy.data.node_groups:
        gn_mod = new_obj.modifiers.new(name="PASSABLE", type='NODES')
        gn_mod.node_group = bpy.data.node_groups["PASSABLE"]
        gn_mod.show_viewport = False

    # --- bake original_obj's world matrix into the mesh data ---
    me.transform(original_obj.matrix_world)

    # --- compute world-space AABB of the baked vertices ---
    verts = [v.co for v in me.vertices]
    if verts:
        minv = Vector((min(v.x for v in verts),
                       min(v.y for v in verts),
                       min(v.z for v in verts)))
        maxv = Vector((max(v.x for v in verts),
                       max(v.y for v in verts),
                       max(v.z for v in verts)))
    else:
        minv = maxv = Vector((0,0,0))

    # center of that box in world-space
    center_world = (minv + maxv) * 0.5

    # round to nearest integer
    center_int = Vector((
        round(center_world.x),
        round(center_world.y),
        round(center_world.z),
    ))

    # half the diagonal is the sphere radius
    radius = ((maxv - minv).length) * 0.5

    # --- recenter the mesh geometry so box-center moves to origin ---
    me.transform(Matrix.Translation(-center_int))

    # place the new object back at the box-center
    new_obj.matrix_world = Matrix.Translation(center_int)

    # --- finally, add the bounding sphere ---
    bounding_sphere = create_bounding_sphere(new_obj, radius)
    bounding_sphere.hide_set(True)

    region_meshes_empty = bpy.data.objects.get("REGION_MESHES")
    if region_meshes_empty:
        new_obj.parent = region_meshes_empty

    return new_obj

def mesh_world_matrix(mesh_obj):
    """Return a copy of the object's world matrix."""
    return mesh_obj.matrix_world.copy()

def assign_back_trees(world_nodes):
    """
    Iterates over world_nodes in reverse order (i.e. from last to first) and for every
    node with depth > 0, finds the first candidate (earlier in the list) with depth equal
    to current depth - 1 that has no back_tree assigned and sets that candidate's back_tree
    to the current node's worldnode index.
    """
    for current_node in world_nodes:
        for candidate in world_nodes:
            # Skip candidates that already have their front_tree set to the current node's worldnode.
            if candidate["front_tree"] == current_node["worldnode"]:
                break
            if (candidate["depth"] == current_node["depth"] - 1 and
                candidate["back_tree"] is None):
                candidate["back_tree"] = current_node["worldnode"]
                break


# ------------------------------------------------------------
# --- Zone BVH and Point–in–Mesh Test (Using closest_point_on_mesh)
# ------------------------------------------------------------

AABB_EPS  = 1e-6
PLANE_EPS = 1e-9

def build_volume_planes(source, source_obj=None):
    """
    Given either:
      - a bmesh.types.BMesh (optionally with source_obj to reproject it),
      - a bpy.types.Object (type=='MESH'),
      - or a bpy.types.Mesh (must pass source_obj),
    returns a list of (world_normal, world_d) for each face of the convex mesh,
    with normals flipped so that n·X + d <= 0 is the “inside” half-space.
    
    If `source` is a BMesh and `source_obj` is None, it is assumed already in world space.
    """
    # — determine the BMesh we’ll work on —
    temp_bm = False
    if isinstance(source, bmesh.types.BMesh):
        bm = source
        # now optional: if no source_obj, we assume bm verts are already world‐space
    elif isinstance(source, bpy.types.Object) and source.type == 'MESH':
        source_obj = source
        bm = bmesh.new()
        bm.from_mesh(source.data)
        temp_bm = True
    elif isinstance(source, bpy.types.Mesh):
        if source_obj is None:
            raise ValueError("When passing a Mesh you must also pass source_obj for its transform")
        bm = bmesh.new()
        bm.from_mesh(source)
        temp_bm = True
    else:
        raise TypeError("`source` must be a BMesh, a MESH Object, or a Mesh datablock")

    # — grab transforms (or identity if none) —
    if source_obj is not None:
        wm3 = source_obj.matrix_world.to_3x3()
        wm4 = source_obj.matrix_world
    else:
        wm3 = Matrix.Identity(3)
        wm4 = Matrix.Identity(4)

    # — build raw planes —
    planes = []
    for f in bm.faces:
        n_world = (wm3 @ f.normal).normalized()
        p_world = wm4 @ f.calc_center_median()
        planes.append((n_world, -n_world.dot(p_world)))

    # — flip any plane whose outside‐half contains the mesh centroid —
    verts_ws = [wm4 @ v.co for v in bm.verts]
    if verts_ws:
        centroid = sum(verts_ws, Vector()) / len(verts_ws)
        for i, (n, d) in enumerate(planes):
            if n.dot(centroid) + d > 0:
                planes[i] = (-n, -d)

    # — clean up if we made a temporary BMesh —
    if temp_bm:
        bm.free()

    return planes

def point_inside_convex_zone(pt, planes):
    """
    True if pt satisfies normal·pt + d <= PLANE_EPS for every plane.
    """
    for n, d in planes:
        if n.dot(pt) + d > PLANE_EPS:
            return False
    return True

# ——— Helper routines ——————————————————————————————
def point_in_convex(pt, planes, tol=1e-4):
    for n, d in planes:
        if n.dot(pt) + d >= -tol:
            return False
    return True

def point_in_poly_2d(x, y, poly2d):
    inside = False
    n = len(poly2d)
    for i in range(n):
        xi, yi = poly2d[i]
        xj, yj = poly2d[(i-1) % n]
        if (yi > y) != (yj > y):
            t = (y - yi) / (yj - yi)
            if xi + t*(xj - xi) > x:
                inside = not inside
    return inside

def point_in_face_polygon(pt, ws_verts, normal):
    origin = ws_verts[0]
    u      = (ws_verts[1] - origin).normalized()
    v      = normal.cross(u).normalized()
    poly2d = [(((vv - origin).dot(u)),
                ((vv - origin).dot(v)))
                for vv in ws_verts]
    x, y   = ((pt - origin).dot(u), (pt - origin).dot(v))
    return point_in_poly_2d(x, y, poly2d)

def volume_intersection_tests(zone_face, region_planes, bvh_vol, region_edges, zone_wm3, zone_wm4):
    """
    Returns True if this DRP_ZONE face truly intersects the region volume.
    Prints only the initial region_planes and the Step 1 vertex‐inside results.
    """
    # face_idx = zone_face.index
    # if face_idx == 23:
    #     print(f"Face {face_idx}")

    # compute world‐space verts of this face
    ws_verts = [zone_wm4 @ v.co for v in zone_face.verts]

    # — Step 1: any vertex inside? —
    for i, v in enumerate(ws_verts):
        inside = point_in_convex(v, region_planes)
        # print(f"[DEBUG]   Step 1: vert {i} at {v} inside region? {inside}")
        if inside:
            return True

    # — Step 2 & 3: perform intersection tests silently —

    # Step 2: edge ray‐casts
    for i in range(len(ws_verts)):
        p0, p1 = ws_verts[i], ws_verts[(i+1) % len(ws_verts)]
        seg = p1 - p0
        L   = seg.length

        # skip degenerate edges
        if L < 1e-6:
            continue

        dir = seg.normalized()
        ε   = 1e-5
        if L < 2*ε:
            continue
        
        # cast from p0+ε toward p1−ε
        start_pt = p0 + dir * ε
        max_d    = L - 2*ε
        
        _, hit_nrm, tri, _ = bvh_vol.ray_cast(start_pt, dir, max_d)
        if tri is None:
            continue

        # now reject if this is almost a tangent (hit_nrm·dir ≈ 0)        
        if abs(hit_nrm.dot(dir)) < 0.2:
            # too shallow, assume it's just grazing
            continue

        return True

    # Step 3: region‐edge puncture test
    n_ws  = (zone_wm3 @ zone_face.normal).normalized()
    p_ctr = zone_wm4 @ zone_face.calc_center_median()
    d_ws  = -n_ws.dot(p_ctr)
    for ce0, ce1 in region_edges:
        seg = ce1 - ce0
        denom = n_ws.dot(seg)
        if abs(denom) < 1e-8:
            continue
        t = -(n_ws.dot(ce0) + d_ws) / denom
        eps = 1e-2
        if eps < t < (1.0 - eps):
            P = ce0 + seg * t
            if point_in_face_polygon(P, ws_verts, n_ws):
                return True

    return False

# ------------------------------------------------------------
# --- Attempt Zone-Based Split
# ------------------------------------------------------------

def zone_bsp_split(bm_geo, zone_obj, current_node, bm_vol, tol=1e-4, min_diag=0.1, used_planes=None):
    """
    Attempt to split bm_geo and bm_vol by the first zone‐face that truly
    penetrates the region volume.  Returns

        (geo_in, geo_out, vol_in, vol_out, world_normal, world_d, face_index)

    or None on failure.
    """

    # 1) AABB cull
    # --------------------------------
    vol_verts = list(bm_vol.verts)
    vol_ws    = [v.co for v in vol_verts]
    if not vol_ws:
        return None

    rmin = Vector((min(v.x for v in vol_ws),
                   min(v.y for v in vol_ws),
                   min(v.z for v in vol_ws)))
    rmax = Vector((max(v.x for v in vol_ws),
                   max(v.y for v in vol_ws),
                   max(v.z for v in vol_ws)))
    zmin, zmax = object_world_aabb(zone_obj)
    if not aabb_intersects(rmin, rmax, zmin, zmax):
        return None

    # 2) Build BVH on the region‐volume triangles, plus collect its edges
    # --------------------------------------------------------------------
    bvh_vol = BVHTree.FromBMesh(bm_vol, epsilon=0.0)

    region_edges = [
        (e.verts[0].co, e.verts[1].co)
        for e in bm_vol.edges
    ]
    

    # 3) Build half‐spaces for the convex region‐volume
    # -------------------------------------------------
    region_planes = build_volume_planes(bm_vol)

    # zone BMesh once
    bm_zon = bmesh.new(); bm_zon.from_mesh(zone_obj.data)
    bm_zon.faces.ensure_lookup_table()
    zone_wm3 = zone_obj.matrix_world.to_3x3()
    zone_wm4 = zone_obj.matrix_world


    # 4) Scan each zone‐face until we find one that really penetrates
    # ---------------------------------------------------------------
    splitter = None
    already_used = used_planes.get(current_node, [])
    for face in bm_zon.faces:
        if not volume_intersection_tests(face, region_planes, bvh_vol, region_edges, zone_wm3, zone_wm4):
            continue

        # build world‐space plane
        n_ws = (zone_wm3 @ face.normal).normalized()
        p_ws = zone_wm4 @ face.calc_center_median()
        d_ws = -n_ws.dot(p_ws)

        # **dedupe against used_planes**:
        too_similar = False
        for (n0, d0) in already_used:
            if n0.dot(n_ws) > 1.0 - 1e-4 and abs(d0 - d_ws) < tol:
                too_similar = True
                break
        if too_similar:
            continue

        splitter = face
        break

    if not splitter:
        bm_zon.free()
        return None

    # 5) Build the split plane in both world and local space
    # ------------------------------------------------------
    plane_co_ws = zone_wm4 @ face.calc_center_median()
    plane_no_ws = (zone_wm3 @ face.normal).normalized()
    plane_d     = -plane_no_ws.dot(plane_co_ws)

    plane_co_l  = plane_co_ws.copy()
    plane_no_l  = plane_no_ws.copy()

    bm_zon.free()

    geo_in, geo_out = terrain_split(bm_geo, plane_co_l, plane_no_l)
    vol_in, vol_out = volume_split(bm_vol, plane_co_l, plane_no_l, tol)

    # 8) Sanity‐check
    # ---------------
    bi_min, bi_max = calculate_bounds_for_bmesh(geo_in)
    bo_min, bo_max = calculate_bounds_for_bmesh(geo_out)
    if (bi_max - bi_min).length < min_diag or (bo_max - bo_min).length < min_diag:
        return None

    # 9) Return exactly what recursive_bsp_split expects
    # -------------------------------------------------
    used_planes.setdefault(current_node, []).append((plane_no_ws.copy(), plane_d))
    return geo_in, geo_out, vol_in, vol_out, plane_no_ws.copy(), plane_d

# ------------------------------------------------------------
# --- Primary Recursive BSP Split (with Zone Splitting)
# ------------------------------------------------------------

def recursive_bsp_split(bm_geo, bm_vol, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=None, depth=0, depth_counters=None, backtree=False):
    """
    Recursively subdivide the normalized volume using axis–aligned splits.
    When a region is small enough, attempt to further split it using zone-based splits.
    """

    if used_planes is None:
        used_planes = {}
    if depth_counters is None:
        depth_counters = {}

    for d in list(depth_counters.keys()):
        if d <= depth:
            depth_counters[d] += 1
    if depth not in depth_counters:
        depth_counters[depth] = 1

    print(f"At depth={depth}, worldnode={worldnode_idx[0]} → depth_counters = {depth_counters}")

    if backtree == True:
        parent_index = worldnode_idx[0] - depth_counters[depth]
        print(f"{worldnode_idx[0]} is backtree to {parent_index}")
        for node_data in world_nodes:
            if node_data["worldnode"] == parent_index:
                node_data["back_tree"] = worldnode_idx[0]
                break
        for d in list(depth_counters.keys()):
            if d >= depth:
                depth_counters[d] = 0

    vol_min, vol_max = calculate_bounds_for_bmesh(bm_vol)

    fpscale = source_obj.get("FPSCALE", None)
    if isinstance(fpscale, int):
        grid_step = 1.0 / (2 ** fpscale)
    else:
        grid_step = None

    size = vol_max - vol_min
    
    node_data = {
    "worldnode": worldnode_idx[0],
    "depth": depth,
    "normal": [0.0, 0.0, 0.0, 0.0],
    "front_tree": 0,
    "back_tree": None,
    "region_tag": ""
    }
    world_nodes.append(node_data)
    current_node = worldnode_idx[0]
    worldnode_idx[0] += 1
    
    # Base case: region is small enough.
    if all(size[i] <= target_size + 1e-4 for i in range(3)):
        parent_idx = None
        for nd in world_nodes:
            if nd["front_tree"] == current_node or nd["back_tree"] == current_node:
                parent_idx = nd["worldnode"]
                break
        if parent_idx is None:
            used_planes[current_node] = []
        else:
            used_planes[current_node] = used_planes.get(parent_idx, []).copy()
        # If zone splits apply for any zone, attempt them:
        for zone_obj in zone_volumes:
            split_result = zone_bsp_split(bm_geo, zone_obj, current_node, bm_vol, tol=1e-4, min_diag=0.1, used_planes=used_planes)
            if split_result is not None:
                bm_geo_in, bm_geo_out, bm_vol_in, bm_vol_out, plane_no, d = split_result
                node_data["normal"] = [-plane_no.x, -plane_no.y, -plane_no.z, -float(d)]
                node_data["front_tree"] = worldnode_idx[0]
                #print(f"Zone-based split succeeded with zone '{zone_obj.name}'.")
                recursive_bsp_split(bm_geo_in, bm_vol_in, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=used_planes, depth=depth+1, depth_counters=depth_counters, backtree=False)
                recursive_bsp_split(bm_geo_out, bm_vol_out, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=used_planes, depth=depth+1, depth_counters=depth_counters, backtree=True)
                return  # Stop after a successful zone split.
        # No zone candidate split succeeded → finalize this leaf region.
        region_index = region_counter[0]
        region_counter[0] += 1
        center = (vol_min + vol_max) * 0.5
        # Compute the world-space bounding box of the region.
        # Create world-space corners from region min/max:
        mat = source_obj.matrix_world
        ws_corners = [mat @ Vector((x, y, z)) for x in (vol_min.x, vol_max.x)
                                         for y in (vol_min.y, vol_max.y)
                                         for z in (vol_min.z, vol_max.z)]
        ws_min = Vector((min(c.x for c in ws_corners),
                         min(c.y for c in ws_corners),
                         min(c.z for c in ws_corners)))
        ws_max = Vector((max(c.x for c in ws_corners),
                         max(c.y for c in ws_corners),
                         max(c.z for c in ws_corners)))
        # Compute the sphere radius that encloses this region.
        sphere_radius = (ws_max - ws_min).length / 2.0
        #print(f"Finalizing leaf region {region_index} with sphere radius {sphere_radius:.4f} (world-space).")
        empty_obj = create_region_empty(center, sphere_radius, region_index, pending_objects)
        node_data["region_tag"] = empty_obj.name
        node_data["back_tree"] = 0
        if bm_geo.faces:
            empty_obj["SPRITE"] = f"R{region_index}_DMSPRITEDEF"
            create_mesh_object_from_bmesh(bm_geo, f"R{region_index}_DMSPRITEDEF", source_obj, pending_objects)
        return

    # If bm has no faces, subdivide the volume anyway.
    if not bm_geo.faces:
        axis, length = max(enumerate(size), key=lambda x: x[1])
        if length <= target_size:
            region_index = region_counter[0]
            region_counter[0] += 1
            center = (vol_min + vol_max)*0.5
            #print(f"Empty region at depth {depth}; finalizing as leaf region {region_index}.")
            # Compute sphere radius from volume dimensions.
            sphere_radius = (size).length / 2.0
            empty_obj = create_region_empty(center, sphere_radius, region_index, pending_objects)
            node_data["region_tag"] = empty_obj.name
            node_data["back_tree"] = 0
            return
        if grid_step:
            # Snap to nearest grid step aligned with FPSCALE
            mid = vol_min[axis] + (length * 0.5)
            split_pos = round(mid / grid_step) * grid_step
        else:
            # Default behavior
            split_pos = vol_min[axis] + target_size * math.floor((length/target_size)*0.5)
            if split_pos <= vol_min[axis] + 1e-6 or split_pos >= vol_max[axis] - 1e-6:
                split_pos = vol_min[axis] + (length * 0.5)
        # split_pos = vol_min[axis] + target_size * math.floor((length/target_size)*0.5)
        plane_co = Vector((0, 0, 0))
        plane_no = Vector((0, 0, 0))
        plane_co[axis] = split_pos
        plane_no[axis] = 1.0
        d_value = -plane_no.dot(plane_co)
        
        node_data["normal"] = [-plane_no.x, -plane_no.y, -plane_no.z, -float(d_value)]
        node_data["front_tree"] = worldnode_idx[0]
        
        bm_vol_lower, bm_vol_upper = volume_split(bm_vol, plane_co, plane_no, tol=0.0)

        recursive_bsp_split(bm_geo, bm_vol_lower, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=None, depth=depth+1, depth_counters=depth_counters, backtree=False)
        recursive_bsp_split(bm_geo, bm_vol_upper, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=None, depth=depth+1, depth_counters=depth_counters, backtree=True)
        return

    # Otherwise, perform an axis-aligned split.
    valid_axes = [(i, size[i]) for i in range(3) if size[i] > target_size + 1e-4]
    if not valid_axes:
        region_index = region_counter[0]
        region_counter[0] += 1
        center = (vol_min + vol_max)*0.5
        print(f"Finalizing leaf region {region_index} (by grid split).")
        sphere_radius = (size).length / 2.0
        empty_obj = create_region_empty(center, sphere_radius, region_index, pending_objects)
        node_data["region_tag"] = empty_obj.name
        node_data["back_tree"] = 0
        if bm_geo.faces:
            empty_obj["SPRITE"] = f"R{region_index}_DMSPRITEDEF"
            create_mesh_object_from_bmesh(bm_geo, f"R{region_index}_DMSPRITEDEF", source_obj, pending_objects)
        return

    axis, _ = max(valid_axes, key=lambda x: x[1])
    length = size[axis]
    split_pos = vol_min[axis] + target_size * math.floor((length/target_size)*0.5)
    if split_pos <= vol_min[axis] + 1e-6 or split_pos >= vol_max[axis] - 1e-6:
        split_pos = vol_min[axis] + (length*0.5)
    plane_co = Vector((0,0,0))
    plane_no = Vector((0,0,0))
    plane_co[axis] = split_pos
    plane_no[axis] = 1.0
    
    d_value = -plane_no.dot(plane_co)
    # Update our worldnode dictionary (node_data) for this non‐leaf node:
    node_data["normal"] = [-plane_no.x, -plane_no.y, -plane_no.z, -float(d_value)]
    node_data["front_tree"] = worldnode_idx[0]
    
    bm_geo_lower, bm_geo_upper = terrain_split(bm_geo, plane_co, plane_no)

    bm_vol_lower, bm_vol_upper = volume_split(bm_vol, plane_co, plane_no, tol=0.0)

    #print(f"Axis–aligned split at axis {axis} at position {split_pos}")
    recursive_bsp_split(bm_geo_lower, bm_vol_lower, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=None, depth=depth+1, depth_counters=depth_counters, backtree=False)
    recursive_bsp_split(bm_geo_upper, bm_vol_upper, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, used_planes=None, depth=depth+1, depth_counters=depth_counters, backtree=True)
    

# ------------------------------------------------------------
# --- Main Runner
# ------------------------------------------------------------

def run_outdoor_bsp_split(target_size=282.0):
    bpy.context.preferences.view.show_splash = False
    bpy.context.scene.render.use_lock_interface = True
    bpy.context.view_layer.depsgraph.update()  # make sure scene is up-to-date
    bpy.context.window_manager.progress_begin(0, 100)

    selected_objs = [obj for obj in bpy.context.selected_objects 
                     if obj.type == 'MESH' and not "_ZONE" in obj.name]
    if not selected_objs:
        print("No valid mesh selected. Please select a mesh object (not a _ZONE).")
        return
    
    region_empty = bpy.data.objects.new("REGION", None)
    bpy.context.collection.objects.link(region_empty)

    region_meshes_empty = bpy.data.objects.new("REGION_MESHES", None)
    bpy.context.collection.objects.link(region_meshes_empty)
    
    pending_objects = []

    zone_volumes = [obj for obj in bpy.data.objects 
                    if obj.type == 'MESH' and "_ZONE" in obj.name]
    print(f"Detected {len(zone_volumes)} zone volumes.")

    for src in selected_objs:
        # --- 1) Container empty ---
        base = src.name.split("_")[0]
        container_name = f"{base}_WORLDDEF"
        container = bpy.data.objects.new(container_name, None)
        bpy.context.collection.objects.link(container)
        container.empty_display_type = 'PLAIN_AXES'
        container["EQGVERSION?"] = "NULL"    # string
        container["NEWWORLD"]   = False # bool
        container["ZONE"]       = True  # bool

        # --- 2) Your existing split & worldtree build ---
        bounds_min, bounds_max = calculate_bounds(src)
        vol_min, vol_max = normalize_bounds(bounds_min, bounds_max, target_size)

        bm = bmesh.new(); bm.from_mesh(src.data)
        bm_vol = create_world_volume(vol_min, vol_max)

        # --- Collect custom split normals from source mesh ---
        src.data.calc_normals_split()
        src.data.use_auto_smooth = True

        # --- Create generic loop float BMesh layer for split normals
        ln_layer = bm.loops.layers.float_vector.new("orig_normals")
        loops = (l for f in bm.faces for l in f.loops)
        for loop in loops:
            loop[ln_layer] = src.data.loops[loop.index].normal

        # color_map = vertex_color_map(bm)
        terrain_cleanup(bm)

        region_counter = [1]; world_nodes = []; worldnode_idx = [1]
        recursive_bsp_split(bm, bm_vol, target_size,
                            region_counter, src, zone_volumes,
                            world_nodes, worldnode_idx, pending_objects, depth=0, depth_counters=None, backtree=False)
        # assign_back_trees(world_nodes)
        worldtree = {"nodes": world_nodes, "total_nodes": len(world_nodes)}

        # --- 3) Create & parent the WorldTree root ---
        root_obj = create_worldtree(worldtree, pending_objects)
        root_obj.parent = container

        for obj in pending_objects:
            bpy.context.collection.objects.link(obj)
        
        zone_boxes = {
            zone: object_world_aabb(zone)
            for zone in zone_volumes
        }

        # 2) Precompute each zone’s face‐plane list once (convex test):
        zone_planes = {
            zone: build_volume_planes(zone)
            for zone in zone_volumes
        }

        for zone, planes in zone_planes.items():
            print(f"=== {zone.name}: {len(planes)} planes ===")
            for i, (n, d) in enumerate(planes):
                print(f"  Plane {i:03d}: normal = ({n.x:.3f}, {n.y:.3f}, {n.z:.3f}),  d = {d:.3f}")

        # 3) Gather your region empties once:
        region_empties = [o for o in bpy.data.objects if re.fullmatch(r"R\d{6}", o.name)]

        # 4) Now do the combined test:
        for zone in zone_volumes:
            minb, maxb = zone_boxes[zone]
            planes     = zone_planes[zone]
            region_idxs = []

            for empty in region_empties:
                # grab true world‐space location in case of parenting
                pt = empty.location.copy()

                # —— A) Cheap AABB cull ——
                if (pt.x < minb.x - AABB_EPS or pt.x > maxb.x + AABB_EPS or
                    pt.y < minb.y - AABB_EPS or pt.y > maxb.y + AABB_EPS or
                    pt.z < minb.z - AABB_EPS or pt.z > maxb.z + AABB_EPS):
                    continue

                # —— B) Convex half‐space test ——
                if point_inside_convex_zone(pt, planes):
                    region_idxs.append(int(empty.name[1:]) - 1)

            zone["REGIONLIST"] = "[" + ", ".join(map(str, region_idxs)) + "]"
            print(f"{zone.name}.REGIONLIST = {zone['REGIONLIST']}")

        # --- 4) Parent any existing _ZONE meshes ---
        for zone in zone_volumes:
            zone.parent = container

        region_empty.parent = container
        region_meshes_empty.parent = container

        create_bounding_volume_for_region_empties()

        modify_regions_and_worldtree()

        finalize_region_meshes()
    
    bpy.context.scene.render.use_lock_interface = False
    bpy.context.window_manager.progress_end()
    bpy.context.view_layer.update()  # Force final update

    print("BSP splitting complete.")