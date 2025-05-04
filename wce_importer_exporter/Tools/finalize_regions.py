import bpy, bmesh, math
from mathutils import Vector, kdtree
from mathutils.kdtree import KDTree

def angle_between_normals(n1, n2):
    """Compute angle between two vectors in degrees."""
    return math.degrees(n1.angle(n2))

def object_world_aabb(obj):
    """Return min/max world-space AABB of a mesh object."""
    mat = obj.matrix_world
    verts = [mat @ v.co for v in obj.data.vertices]
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

def split_edges_to_snap_verts(objs, threshold=1e-4):
    """For each pair A,B in objs, split edges of B where a vertex of A projects onto it."""
    world_verts = {ob: [ob.matrix_world @ v.co for v in ob.data.vertices] for ob in objs}

    for ob_B in objs:
        me = ob_B.data
        me.calc_normals_split()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        minB, maxB = object_world_aabb(ob_B)
        changed = False
        normal_map = {}

        for ob_A in objs:
            if ob_A == ob_B:
                continue

            minA, maxA = object_world_aabb(ob_A)
            if not aabb_intersects(minA, maxA, minB, maxB):
                continue

            verts_A = world_verts[ob_A]

            for edge in list(bm.edges):
                v1 = edge.verts[0]
                v2 = edge.verts[1]
                v1_ws = ob_B.matrix_world @ v1.co
                v2_ws = ob_B.matrix_world @ v2.co
                seg = v2_ws - v1_ws
                seg_len2 = seg.length_squared
                if seg_len2 == 0.0:
                    continue

                for p_ws in verts_A:
                    t = (p_ws - v1_ws).dot(seg) / seg_len2
                    if 0.0 < t < 1.0:
                        proj = v1_ws + seg * t
                        if (proj - p_ws).length <= threshold:
                            # ⛏️ Cache the interpolated normal BEFORE subdivision
                            interp_normal = (v1.normal * (1 - t) + v2.normal * t).normalized()

                            result = bmesh.ops.subdivide_edges(
                                bm,
                                edges=[edge],
                                cuts=1,
                                edge_percents={edge: t}
                            )
                            new_verts = [e for e in result["geom_split"] if isinstance(e, bmesh.types.BMVert)]
                            if new_verts:
                                nv = new_verts[0]
                                normal_map[nv.index] = interp_normal
                            changed = True
                            break

        if changed:
            bm.to_mesh(me)
            me.use_auto_smooth = True

            loop_normals = []
            for loop in me.loops:
                vi = loop.vertex_index
                normal = normal_map.get(vi, me.vertices[vi].normal)
                loop_normals.append(normal)

            me.normals_split_custom_set(loop_normals)

        bm.free()

    print("✅ split_edges_to_snap_verts: edges split and normals interpolated.")

def _material_uv_normal_match(v1, v2, uv_layer, normal_angle_limit=45):
    """Check if v1 and v2 share the same materials, UVs, and all loop normals are within angle limit."""
    def loop_data(v):
        uv_set = set()
        mat_set = set()
        normals = []
        for loop in v.link_loops:
            if loop.face:
                mat_set.add(loop.face.material_index)
                if uv_layer:
                    uv_set.add(tuple(loop[uv_layer].uv))
                normals.append(loop.calc_normal())
        return mat_set, uv_set, normals

    mats1, uvs1, normals1 = loop_data(v1)
    mats2, uvs2, normals2 = loop_data(v2)

    if mats1 != mats2:
        return False
    if uv_layer and uvs1 != uvs2:
        return False

    for n1 in normals1:
        for n2 in normals2:
            angle = angle_between_normals(n1, n2)
            if angle > normal_angle_limit:
                return False

    return True

def merge_by_distance(obj, dist=0.001, normal_angle_limit=45):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active  # Can be None

    visited = set()

    for v in list(bm.verts):
        if v in visited or not v.is_valid:
            continue

        group = [v]
        visited.add(v)

        # Build fresh KDTree per vertex due to possible mesh mutation
        kd = KDTree(len(bm.verts))
        for i, vtest in enumerate(bm.verts):
            if vtest.is_valid:
                kd.insert(vtest.co, i)
        kd.balance()

        for (_, idx, _) in kd.find_range(v.co, dist):
            try:
                v2 = bm.verts[idx]
            except IndexError:
                continue
            if v2 in visited or not v2.is_valid:
                continue
            if _material_uv_normal_match(v, v2, uv_layer, normal_angle_limit):
                group.append(v2)
                visited.add(v2)

        if len(group) > 1:
            bmesh.ops.remove_doubles(bm, verts=group, dist=dist)
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()

    bm.to_mesh(me)
    bm.free()
    print(f"✅ Merged with normal check (angle < {normal_angle_limit}°)")

def triangulate_meshes(objs):
    """Triangulate faces and preserve/reconstruct custom split normals."""

    for ob in objs:
        me = ob.data
        me.use_auto_smooth = True
        me.calc_normals_split()
        
        # Cache existing loop normals and loop-to-face/vertex mappings
        old_loop_normals = [loop.normal.copy() for loop in me.loops]
        old_loop_to_vert = [loop.vertex_index for loop in me.loops]

        # Build face-to-loop mapping (pre-triangulation)
        face_to_loop_indices = {}
        for face in me.polygons:
            face_to_loop_indices[face.index] = list(face.loop_indices)

        # Triangulate using BMesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()

        me.calc_normals_split()

        # Rebuild mapping of new loops (post-triangulation)
        new_loop_normals = []
        for loop_idx, loop in enumerate(me.loops):
            vi = loop.vertex_index
            face = next((f for f in me.polygons if loop_idx in f.loop_indices), None)
            replacement = None

            if face:
                # Try to find a previous loop on this face with same vertex
                original_loops = face_to_loop_indices.get(face.index, [])
                for old_li in original_loops:
                    if old_li < len(old_loop_normals) and old_loop_to_vert[old_li] == vi:
                        replacement = old_loop_normals[old_li]
                        break

                # Otherwise, use the first valid loop on that face
                if not replacement:
                    for old_li in original_loops:
                        if old_li < len(old_loop_normals):
                            replacement = old_loop_normals[old_li]
                            break

            # If still nothing, fallback to vertex normal
            if not replacement:
                replacement = me.vertices[vi].normal

            new_loop_normals.append(replacement)

        # Apply the rebuilt loop normals
        me.normals_split_custom_set(new_loop_normals)

        print(f"✅ {ob.name}: triangulated and normals preserved/repaired.")

def collapse_vertices_across_objects(objs, threshold=0.05):
    """
    Cluster all world-space verts across objs within threshold,
    snap each cluster to its centroid, then round that centroid
    to the grid implied by each obj.FPSCALE.
    """
    # gather world-space coords + mapping
    coords, mapping = [], []
    for ob in objs:
        wm = ob.matrix_world
        fscale = ob.get("FPSCALE", 0)
        factor = 2 ** fscale
        for vi, v in enumerate(ob.data.vertices):
            coords.append(wm @ v.co)
            mapping.append((ob, vi, factor))
    N = len(coords)
    if N == 0:
        print("⚠️ no vertices to collapse.")
        return

    # build KD-tree
    kd = KDTree(N)
    for i, co in enumerate(coords):
        kd.insert(co, i)
    kd.balance()

    visited = set()
    for i, co in enumerate(coords):
        if i in visited:
            continue
        # find cluster
        neighbors = [idx for (_, idx, _) in kd.find_range(co, threshold)]
        visited.update(neighbors)
        centroid = Vector((0,0,0))
        for j in neighbors:
            centroid += coords[j]
        centroid /= len(neighbors)
        # write back + grid-round
        for j in neighbors:
            ob, vi, factor = mapping[j]
            local = ob.matrix_world.inverted() @ centroid
            if factor != 0:
                local.x = round(local.x * factor) / factor
                local.y = round(local.y * factor) / factor
                local.z = round(local.z * factor) / factor
            ob.data.vertices[vi].co = local

    # update meshes
    for ob in objs:
        ob.data.update()

    #print(f"✅ collapse_vertices_across_objects (th={threshold}) done.")

def is_invalid_normal(v):
    """Check if a normal is zero-length or contains NaNs."""
    return v.length == 0.0 or math.isnan(v.x) or math.isnan(v.y) or math.isnan(v.z)

def fix_invalid_split_normals(region_objs):
    """Fix zero-length or NaN split normals in region meshes."""
    for obj in region_objs:
        me = obj.data
        me.calc_normals_split()
        me.use_auto_smooth = True

        loop_normals = [loop.normal.copy() for loop in me.loops]

        # Build loop-to-face mapping since MeshLoop has no .face
        loop_to_face = {}
        for face in me.polygons:
            for li in face.loop_indices:
                loop_to_face[li] = face

        invalid_loops = [i for i, n in enumerate(loop_normals) if is_invalid_normal(n)]

        for li in invalid_loops:
            replacement = None
            vert_index = me.loops[li].vertex_index
            face = loop_to_face.get(li)

            # Try other loops in the same face
            for alt_li in face.loop_indices:
                if alt_li == li:
                    continue
                n = loop_normals[alt_li]
                if not is_invalid_normal(n):
                    replacement = n
                    break

            # If that fails, try other loops that use the same vertex
            if not replacement:
                for alt_li, loop in enumerate(me.loops):
                    if loop.vertex_index == vert_index and alt_li != li:
                        n = loop_normals[alt_li]
                        if not is_invalid_normal(n):
                            replacement = n
                            break

            if replacement:
                loop_normals[li] = replacement
                print(f"✅ Fixed invalid normal at loop {li} (vertex {vert_index}) in {obj.name}")
            else:
                print(f"⚠️ Could not fix invalid normal at loop {li} (vertex {vert_index}) in {obj.name}")

        me.normals_split_custom_set(loop_normals)
        print(f"🔧 Completed normal fix for {obj.name}")

def merge_near_zero_edges(region_objs, threshold=1e-6, max_iterations=10):
    print(f"🔧 Merging near-zero-length edges (≤ {threshold}) across {len(region_objs)} region meshes...")

    for obj in region_objs:
        if obj.type != 'MESH':
            continue

        me = obj.data
        merged_total = 0
        iterations = 0

        while iterations < max_iterations:
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            edges_to_merge = []
            for edge in bm.edges:
                v1, v2 = edge.verts
                if (v1.co - v2.co).length_squared <= threshold ** 2:
                    edges_to_merge.append((v1, v2))

            if not edges_to_merge:
                bm.free()
                break

            collapse_count = 0
            for v1, v2 in edges_to_merge:
                if v1.is_valid and v2.is_valid:
                    midpoint = (v1.co + v2.co) / 2.0
                    bmesh.ops.pointmerge(bm, verts=[v1, v2], merge_co=midpoint)
                    collapse_count += 1

            bm.to_mesh(me)
            me.update()
            bm.free()

            merged_total += collapse_count
            iterations += 1

        print(f"✅ {obj.name}: {merged_total} edge(s) collapsed in {iterations} iteration(s)")

def average_vertex_colors_globally(region_objs, threshold=0.001):
    print(f"🎨 Globally averaging vertex colors between {len(region_objs)} region meshes...")

    vertex_data = []
    tree = KDTree(sum(len(obj.data.vertices) for obj in region_objs))

    index = 0
    for obj in region_objs:
        src = obj.data
        if not src.color_attributes:
            continue

        wm = obj.matrix_world
        for i, v in enumerate(src.vertices):
            co = wm @ v.co
            tree.insert(co, index)
            vertex_data.append((obj, i, co))
            index += 1

    tree.balance()

    clusters = []
    visited = set()

    for i, (_, _, co) in enumerate(vertex_data):
        if i in visited:
            continue
        group = [i]
        visited.add(i)
        for (_, idx, _) in tree.find_range(co, threshold):
            if idx not in visited:
                group.append(idx)
                visited.add(idx)
        if len(group) > 1:
            clusters.append(group)

    # Collect all color attributes
    attr_names = set()
    for obj in region_objs:
        for attr in obj.data.color_attributes:
            if attr.domain == 'POINT':
                attr_names.add(attr.name)

    for attr_name in attr_names:
        for cluster in clusters:
            accum = Vector((0.0, 0.0, 0.0, 0.0))
            count = 0
            for idx in cluster:
                obj, vi, _ = vertex_data[idx]
                attr = obj.data.color_attributes.get(attr_name)
                if attr:
                    accum += Vector(attr.data[vi].color)
                    count += 1
            if count > 0:
                avg = accum / count
                for idx in cluster:
                    obj, vi, _ = vertex_data[idx]
                    attr = obj.data.color_attributes.get(attr_name)
                    if attr:
                        attr.data[vi].color = avg

    print(f"✅ Averaged colors globally across {len(clusters)} vertex clusters.")

def delete_loose_and_degenerate(region_objs, area_threshold=1e-10):
    print("🧹 Deleting loose and degenerate geometry in region meshes...")

    for obj in region_objs:
        if obj.type != 'MESH':
            continue

        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        loose_verts = [v for v in bm.verts if not v.link_edges]
        loose_edges = [e for e in bm.edges if not e.link_faces]
        degenerate_faces = [f for f in bm.faces if f.calc_area() < area_threshold]

        geom_to_delete = loose_verts + loose_edges + degenerate_faces

        if geom_to_delete:
            # Choose best context
            if loose_edges or (loose_verts and degenerate_faces):
                context = 'EDGES'
            elif degenerate_faces:
                context = 'FACES'
            else:
                context = 'VERTS'

            bmesh.ops.delete(bm, geom=geom_to_delete, context=context)
            bm.to_mesh(mesh)
            mesh.update()

            print(f"✅ Cleaned {obj.name}: {len(loose_verts)} loose verts, {len(loose_edges)} loose edges, {len(degenerate_faces)} degenerate faces")
        else:
            print(f"✅ No loose/degenerate geometry in: {obj.name}")

        bm.free()


def fix_split_normal_counts(region_objs):
    """
    Ensure each mesh in region_objs has exactly one custom‐split‐normal
    per loop. Pads with the vertex normal or trims extras as needed.
    """
    for obj in region_objs:
        if obj.type != 'MESH':
            continue
        me = obj.data
        # make sure Blender has up‑to‑date split normals
        me.calc_normals_split()
        loop_count = len(me.loops)
        # read whatever normals exist (custom or auto)
        current = [loop.normal.copy() for loop in me.loops]

        if len(current) != loop_count:
            print(f"[FixNormals] {obj.name}: {len(current)} normals vs {loop_count} loops – repairing…")
            fixed = []
            for i in range(loop_count):
                if i < len(current):
                    fixed.append(current[i])
                else:
                    # pad missing with the corresponding vertex normal
                    vi = me.loops[i].vertex_index
                    fixed.append(me.vertices[vi].normal.copy())
            # apply exactly the right number of normals
            me.use_auto_smooth = True
            me.normals_split_custom_set(fixed[:loop_count])
            print(f" → now {len(fixed[:loop_count])} normals")
        else:
            print(f"[FixNormals] {obj.name}: OK ({loop_count} loops)")

def finalize_regions(
        edge_snap_threshold=0.03,
        merge_dist=0.001,
        collapse_thresh=0.05):
    # pick up all of your region meshes by naming convention
    region_objs = [
        o for o in bpy.context.scene.objects
        if o.type == 'MESH' and o.name.startswith('R') and o.name.endswith('_DMSPRITEDEF')
    ]
    if not region_objs:
        print("⚠️ No region meshes found (Rxxxxx_DMSPRITEDEF).")
        return

    print(f"🔧 Finalizing {len(region_objs)} region meshes:")
    for obj in region_objs:
        print(f"   • {obj.name}")

    merge_near_zero_edges(region_objs)
    delete_loose_and_degenerate(region_objs)
    collapse_vertices_across_objects(region_objs, threshold=collapse_thresh)
    fix_invalid_split_normals(region_objs)
    merge_near_zero_edges(region_objs)
    delete_loose_and_degenerate(region_objs)
    split_edges_to_snap_verts(region_objs, threshold=edge_snap_threshold)
    collapse_vertices_across_objects(region_objs, threshold=collapse_thresh)
    merge_near_zero_edges(region_objs)
    for obj in region_objs:
        merge_by_distance(obj, dist=merge_dist)
    delete_loose_and_degenerate(region_objs)
    triangulate_meshes(region_objs)
    average_vertex_colors_globally(region_objs, threshold=0.1)
    delete_loose_and_degenerate(region_objs)
    fix_split_normal_counts(region_objs)

    print("🎉 All region meshes finalized.")