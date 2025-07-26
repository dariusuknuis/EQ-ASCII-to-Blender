import bpy, bmesh, math, re, math
from math import pi
from mathutils import Vector, kdtree
from mathutils.kdtree import KDTree
import time
from .bmesh_with_split_norms import bmesh_with_split_norms, mesh_from_bmesh_with_split_norms
from .format_helpers import merge_verts_by_attrs
from .bsp_split_helpers import mesh_cleanup

def angle_between_normals(n1, n2):
    """Compute angle between two vectors in degrees."""
    return math.degrees(n1.angle(n2))

def object_world_aabb(obj):
    """Return min/max world-space AABB of a mesh object."""
    mat = obj.matrix_world
    verts = [mat @ v.co for v in obj.data.vertices]
    if not verts:
        return Vector((0,0,0)), Vector((0,0,0))
    minb = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    maxb = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    return minb, maxb

def aabb_intersects(minA, maxA, minB, maxB, epsilon=0.001):
    """Return True if two padded AABBs intersect."""
    return not (
        maxA.x + epsilon < minB.x - epsilon or minA.x - epsilon > maxB.x + epsilon or
        maxA.y + epsilon < minB.y - epsilon or minA.y - epsilon > maxB.y + epsilon or
        maxA.z + epsilon < minB.z - epsilon or minA.z - epsilon > maxB.z + epsilon
    )

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

def split_edges_to_snap_verts(objs, threshold=1e-4):
    """
    For each pair A,B in objs, split B's edges wherever any A-vertex projects onto them.
    Preserves *all* splits and interpolates normals.
    """
    # 1) cache all world‐space vertex positions for quick lookup
    world_verts = {
        ob: [ob.matrix_world @ v.co for v in ob.data.vertices]
        for ob in objs
    }

    for ob_B in objs:
        me = ob_B.data
        me.calc_normals_split()
        me.use_auto_smooth = True

        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        ln_layer = bm.loops.layers.float_vector.new("orig_normals")
        loops = (l for f in bm.faces for l in f.loops)
        for loop in loops:
            loop[ln_layer] = me.loops[loop.index].normal

        minB, maxB = object_world_aabb(ob_B)
        # collect all hits per edge: {edge: [(t, interp_normal), ...]}
        edge_hits = {}

        for ob_A in objs:
            if ob_A is ob_B:
                continue
            minA, maxA = object_world_aabb(ob_A)
            if not aabb_intersects(minA, maxA, minB, maxB):
                continue

            for edge in bm.edges:
                v1, v2 = edge.verts
                w1 = ob_B.matrix_world @ v1.co
                w2 = ob_B.matrix_world @ v2.co
                seg = w2 - w1
                seg_len2 = seg.length_squared
                if seg_len2 == 0.0:
                    continue

                for p in world_verts[ob_A]:
                    t = (p - w1).dot(seg) / seg_len2
                    if 0.0 < t < 1.0:
                        proj = w1 + seg * t
                        if (proj - p).length <= threshold:
                            interp_n = (v1.normal * (1 - t) + v2.normal * t).normalized()
                            edge_hits.setdefault(edge, []).append((t, interp_n))

        if not edge_hits:
            bm.free()
            continue

        # 2) For each edge, sort its hits and subdivide *sequentially*
        for edge, hits in edge_hits.items():
            # skip degenerate
            if not edge.is_valid:
                continue

            # sort along the original edge
            hits.sort(key=lambda x: x[0])
            v1, v2 = edge.verts
            orig_v2 = v2  # we'll always split towards v2
            current_edge = edge
            offset = 0.0

            for t, interp_n in hits:
                # adjust t to the remaining segment
                local_t = (t - offset) / (1.0 - offset)
                # cut it once at local_t
                result = bmesh.ops.subdivide_edges(
                    bm,
                    edges=[current_edge],
                    cuts=1,
                    edge_percents={current_edge: local_t},
                )
                # grab the newly made vertex
                new_vert = next(
                    (g for g in result["geom_split"] if isinstance(g, bmesh.types.BMVert)),
                    None
                )
                if new_vert:

                    # find the segment from new_vert to the original v2
                    # so next subdivision happens on that piece
                    for e_next in new_vert.link_edges:
                        if orig_v2 in e_next.verts:
                            current_edge = e_next
                            break

                offset = t

        merge_verts_by_attrs(bm)
        mesh_from_bmesh_with_split_norms(bm, ob_B)

    #print("✅ split_edges_to_snap_verts: done, all splits & normals preserved.")

def triangulate_meshes(objs):
    """Triangulate faces and very quickly preserve custom split normals."""
    for ob in objs:
        me = ob.data
        
        # 2) Triangulate via BMesh
        bm = bmesh.new()
        bm.from_mesh(me)

        me.calc_normals_split()
        me.use_auto_smooth = True

        ln_layer = bm.loops.layers.float_vector.new("orig_normals")
        loops = (l for f in bm.faces for l in f.loops)
        for loop in loops:
            loop[ln_layer] = me.loops[loop.index].normal
        
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')
        cleanup_mesh_geometry(bm)
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')
        
        mesh_from_bmesh_with_split_norms(bm, ob)

        # print(f"✅ {ob.name}: triangulated and normals preserved.")

def collapse_vertices_across_objects(objs, threshold=0.5):
    eps = 1e-6

    # 1) Build BMesh per object, collect coords+mapping
    coords, mapping, bm_by_obj = [], [], {}
    for ob in objs:
        if ob.type != 'MESH': continue

        bm = bmesh_with_split_norms(ob)
        bm.verts.ensure_lookup_table()
        bm_by_obj[ob] = bm

        wm = ob.matrix_world
        factor = 2 ** ob.get("FPSCALE", 0)

        for v in bm.verts:
            coords.append(wm @ v.co)
            mapping.append((ob, v, factor))

    if not coords:
        return

    # 2) KD‑tree cluster in world‑space
    kd = KDTree(len(coords))
    for i, co in enumerate(coords):
        kd.insert(co, i)
    kd.balance()

    visited = set()

    # 3) Snap & (optionally) merge edge‑neighbors during cluster loop
    for i, co in enumerate(coords):
        if i in visited:
            continue
        nbrs = [j for (_, j, _) in kd.find_range(co, threshold)]
        visited.update(nbrs)
        if len(nbrs) < 2:
            continue

        centroid = sum((coords[j] for j in nbrs), Vector()) / len(nbrs)

        for j in nbrs:
            ob, v, factor = mapping[j]
            bm = bm_by_obj[ob]

            # grid‑snap the local target
            lt = ob.matrix_world.inverted() @ centroid
            if factor != 1:
                lt.x = round(lt.x * factor) / factor
                lt.y = round(lt.y * factor) / factor
                lt.z = round(lt.z * factor) / factor

            # merge if an edge‑neighbor already sits at that spot
            merged = False
            for e in v.link_edges:
                ov = e.other_vert(v)
                if (ov.co - lt).length < eps:
                    bmesh.ops.pointmerge(bm, verts=[v, ov], merge_co=ov.co)
                    merged = True
                    break

            if not merged:
                v.co = lt

            coords[j] = ob.matrix_world @ v.co

    # 4) NEW: merge any remaining zero‑length edges **only** where verts share an edge
    for ob, bm in bm_by_obj.items():
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        # collect offending edges
        to_merge = []
        for e in bm.edges:
            v1, v2 = e.verts
            if (v1.co - v2.co).length < eps:
                to_merge.append((v1, v2))
        # perform merges
        for v1, v2 in to_merge:
            if v1.is_valid and v2.is_valid:
                bmesh.ops.pointmerge(bm, verts=[v1, v2], merge_co=v1.co)

    # 5) Write back and reapply normals
    for ob, bm in bm_by_obj.items():
        mesh_boundary_cleanup(bm)
        mesh_cleanup(bm)
        cleanup_mesh_geometry(bm)
        mesh_boundary_cleanup(bm)
        mesh_from_bmesh_with_split_norms(bm, ob)

def average_vertex_colors_globally(region_objs, threshold=0.001):
    print(f"🎨 Reapplying vertex colors to {len(region_objs)} region meshes...")

    def linear_to_srgb(c: float) -> float:
        """
        Convert a linear-light value to sRGB‑encoded.
        """
        if c <= 0.0031308:
            return c * 12.92
        else:
            return 1.055 * (c ** (1/2.4)) - 0.055
        
    # ─── 0) Convert any per‑loop (corner) "_loop" attrs back to point‑domain ─────────────────────
    for obj in region_objs:
        me = obj.data

        # find all corner‑domain attrs whose names end with "_loop"
        loop_attrs = [
            attr for attr in me.color_attributes
            if attr.domain == 'CORNER' and attr.name.endswith('_loop')
        ]
        if not loop_attrs:
            continue

        for loop_attr in loop_attrs:
            point_name = loop_attr.name[:-5]  # strip "_loop"
            dst = me.color_attributes.get(point_name)
            if not dst:
                dst = me.color_attributes.new(
                    name=point_name,
                    type='FLOAT_COLOR',
                    domain='POINT'
                )

            # accumulate loop colors per vertex
            accum  = [Vector((0.0, 0.0, 0.0, 0.0)) for _ in me.vertices]
            counts = [0] * len(me.vertices)

            for li, loop in enumerate(me.loops):
                vi  = loop.vertex_index
                col = Vector(loop_attr.data[li].color)
                accum[vi]  += col
                counts[vi] += 1

            # write averaged (with gamma correction) back into the point‑domain attr
            for vi in range(len(me.vertices)):
                if counts[vi] > 0:
                    avg = accum[vi] / counts[vi]
                    lin = Vector((
                        linear_to_srgb(avg.x),
                        linear_to_srgb(avg.y),
                        linear_to_srgb(avg.z),
                        avg[3]  # leave alpha unchanged
                    ))
                    dst.data[vi].color = lin

            # remove the corner‑domain layer when done
            me.color_attributes.remove(loop_attr)

    # # ─── 1) Build KD‑tree on world‑space vertex positions ───────────────────────────────────
    # vertex_data = []
    # tree = KDTree(sum(len(obj.data.vertices) for obj in region_objs))
    # index = 0

    # for obj in region_objs:
    #     src = obj.data
    #     if not src.color_attributes:
    #         continue

    #     wm = obj.matrix_world

    #     for i, v in enumerate(src.vertices):
    #         co = wm @ v.co
    #         tree.insert(co, index)
    #         vertex_data.append((obj, i, co))
    #         index += 1

    # tree.balance()

    # # ─── 2) Cluster nearby verts ───────────────────────────────────────────────────────────
    # clusters = []
    # visited = set()
    # for i, (_, _, co) in enumerate(vertex_data):
    #     if i in visited:
    #         continue
    #     group = [i]
    #     visited.add(i)
    #     for (_, idx, _) in tree.find_range(co, threshold):
    #         if idx not in visited:
    #             group.append(idx)
    #             visited.add(idx)
    #     if len(group) > 1:
    #         clusters.append(group)

    # # ─── 3) Find all point‑domain attrs to average ─────────────────────────────────────────
    # attr_names = set()
    # for obj in region_objs:
    #     for attr in obj.data.color_attributes:
    #         if attr.domain == 'POINT':
    #             attr_names.add(attr.name)

    # # ─── 4) Average each attr over each cluster ────────────────────────────────────────────
    # for attr_name in attr_names:
    #     for cluster in clusters:
    #         accum = Vector((0.0, 0.0, 0.0, 0.0))
    #         count = 0
    #         for idx in cluster:
    #             obj, vi, _ = vertex_data[idx]
    #             attr = obj.data.color_attributes.get(attr_name)
    #             if attr:
    #                 accum += Vector(attr.data[vi].color)
    #                 count += 1
    #         if count > 0:
    #             avg = accum / count
    #             for idx in cluster:
    #                 obj, vi, _ = vertex_data[idx]
    #                 attr = obj.data.color_attributes.get(attr_name)
    #                 if attr:
    #                     attr.data[vi].color = avg

    # print(f"✅ Averaged colors globally across {len(clusters)} vertex clusters.")
        
def delete_empty_region_meshes_and_clear_sprite(region_objs):
    """
    Remove region mesh objects that have no vertices, delete any *_BR empties
    parented to them, and clear the SPRITE property on the corresponding region empty.
    """
    for obj in list(region_objs):
        if obj.type != 'MESH':
            continue
        # if no verts, we want to nuke it
        if len(obj.data.vertices) == 0:
            # 1) clear the SPRITE field on R###### empty
            m = re.match(r"R(\d+)_DMSPRITEDEF", obj.name)
            if m:
                idx = int(m.group(1))
                region_empty_name = f"R{idx:06d}"
                region_empty = bpy.data.objects.get(region_empty_name)
                if region_empty and "SPRITE" in region_empty:
                    region_empty["SPRITE"] = ""

            # 2) delete any direct children named "<mesh_name>_BR"
            for child in list(obj.children):
                if (child.type == 'EMPTY' 
                    and child.name == obj.name + "_BR"):
                    bpy.data.objects.remove(child, do_unlink=True)

            # 3) delete the mesh itself
            bpy.data.objects.remove(obj, do_unlink=True)
            region_objs.remove(obj)

def finalize_region_meshes(
        edge_snap_threshold=0.03,
        merge_dist=0.001,
        collapse_thresh=0.05):
    start = time.perf_counter()
    # pick up all of your region meshes by naming convention
    region_objs = [
        o for o in bpy.context.scene.objects
        if o.type == 'MESH' and o.name.startswith('R') and o.name.endswith('_DMSPRITEDEF')
    ]
    if not region_objs:
        print("⚠️ No region meshes found (Rxxxxx_DMSPRITEDEF).")
        return

    print(f"🔧 Finalizing {len(region_objs)} region meshes:")
    # for obj in region_objs:
        # print(f"   • {obj.name}")

    collapse_vertices_across_objects(region_objs, threshold=collapse_thresh)
    split_edges_to_snap_verts(region_objs, threshold=edge_snap_threshold)
    triangulate_meshes(region_objs)
    # average_vertex_colors_globally(region_objs, threshold=0.1)
    delete_empty_region_meshes_and_clear_sprite(region_objs)
    
    elapsed = time.perf_counter() - start

    print(f"🎉 All region meshes finalized in {elapsed:.2f} seconds.")