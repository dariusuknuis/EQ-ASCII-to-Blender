import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix, kdtree
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from create_bounding_sphere import create_bounding_sphere
from modify_regions_and_worldtree import modify_regions_and_worldtree, create_bounding_volume_for_region_empties
from create_worldtree import create_worldtree
from .finalize_region_meshes import finalize_region_meshes
import math
from math import pi
import re

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

def duplicate_faces_by_tag(bm, tag_value):
    """
    Duplicate all bm.faces with face.tag==tag_value into a new BMesh,
    copying across:
      - all UV (loop) layers
      - all loop‐color layers
      - all loop float_vector layers
      - all vertex int layers
      - all vertex color layers
      - all vertex float_vector layers
      - all face int layers
    """
    new_bm = bmesh.new()
    v_map  = {}

    # ─── gather all source layers ────────────────────────────────────────
    uv_srcs        = {lay.name: lay for lay in bm.loops.layers.uv}
    loop_col_srcs  = {lay.name: lay for lay in bm.loops.layers.color}
    loop_fvec_srcs = {lay.name: lay for lay in bm.loops.layers.float_vector}

    vert_int_srcs  = {lay.name: lay for lay in bm.verts.layers.int}
    vert_col_srcs  = {lay.name: lay for lay in bm.verts.layers.color}
    vert_fvec_srcs = {lay.name: lay for lay in bm.verts.layers.float_vector}

    face_int_srcs  = {lay.name: lay for lay in bm.faces.layers.int}

    # ─── create matching layers in new_bm ───────────────────────────────
    uv_dsts        = {name: new_bm.loops.layers.uv.new(name)          for name in uv_srcs}
    loop_col_dsts  = {name: new_bm.loops.layers.color.new(name)       for name in loop_col_srcs}
    loop_fvec_dsts = {name: new_bm.loops.layers.float_vector.new(name) for name in loop_fvec_srcs}

    vert_int_dsts  = {name: new_bm.verts.layers.int.new(name)           for name in vert_int_srcs}
    vert_col_dsts  = {name: new_bm.verts.layers.color.new(name)         for name in vert_col_srcs}
    vert_fvec_dsts = {name: new_bm.verts.layers.float_vector.new(name)  for name in vert_fvec_srcs}

    face_int_dsts  = {name: new_bm.faces.layers.int.new(name)           for name in face_int_srcs}

    # ─── duplicate only tagged faces ────────────────────────────────────
    for face in bm.faces:
        if not face.tag:
            continue

        # copy verts & their attributes
        new_verts = []
        for v in face.verts:
            if v not in v_map:
                v_new = new_bm.verts.new(v.co)
                v_map[v] = v_new
                # copy vertex-domain layers
                for name, src in vert_int_srcs.items():
                    v_new[vert_int_dsts[name]] = v[src]
                for name, src in vert_col_srcs.items():
                    v_new[vert_col_dsts[name]] = v[src]
                for name, src in vert_fvec_srcs.items():
                    v_new[vert_fvec_dsts[name]] = v[src]
            new_verts.append(v_map[v])

        try:
            f_new = new_bm.faces.new(new_verts)
        except ValueError:
            continue  # degenerate face

        # copy material index
        f_new.material_index = face.material_index

        # copy face int layers
        for name, src in face_int_srcs.items():
            f_new[face_int_dsts[name]] = face[src]

        # copy per-loop data: UVs, loop-colors, loop-float_vectors
        for loop_old, loop_new in zip(face.loops, f_new.loops):
            for name, src in uv_srcs.items():
                loop_new[uv_dsts[name]].uv = loop_old[src].uv
            for name, src in loop_col_srcs.items():
                loop_new[loop_col_dsts[name]] = loop_old[src]
            for name, src in loop_fvec_srcs.items():
                loop_new[loop_fvec_dsts[name]] = loop_old[src]

    return new_bm

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
    # --- build the mesh & object ---
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()

    # rename first UV layer if present
    if me.uv_layers:
        me.uv_layers[0].name = f"{name}_uv"

    for poly in me.polygons:
            poly.use_smooth = True

    for e in me.edges:
        e.use_edge_sharp = False

    me.use_auto_smooth = True
    me.auto_smooth_angle = math.pi

    ln_attr = me.attributes.get("orig_normals")
    if ln_attr:
        # build flat list of normals in loop order
        custom_nors = [ Vector(cd.vector) for cd in ln_attr.data ]
        me.normals_split_custom_set(custom_nors)
        me.attributes.remove(me.attributes.get("orig_normals"))

    # clear any sharp‑edge flags
    for e in me.edges:
        e.use_edge_sharp = False

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

def build_zone_planes(zone_obj):
    """
    Returns a list of (world_normal, world_d) where
        normal·X + d = 0
    defines each face,
    with normals pointing outward.
    """
    wm3 = zone_obj.matrix_world.to_3x3()
    wm4 = zone_obj.matrix_world

    raw = []
    for poly in zone_obj.data.polygons:
        n_world = (wm3 @ poly.normal).normalized()
        p_world = wm4 @ poly.center
        d_world = -n_world.dot(p_world)
        raw.append([n_world, d_world])

    # interior test point: mesh centroid in world‐space
    verts_ws = [wm4 @ v.co for v in zone_obj.data.vertices]
    centroid = sum(verts_ws, Vector()) / len(verts_ws)

    # flip any plane whose half‐space does _not_ contain the centroid
    for i, (n, d) in enumerate(raw):
        if n.dot(centroid) + d > 0:
            raw[i][0] = -n
            raw[i][1] = -d

    return raw

def point_inside_convex_zone(pt, planes):
    """
    True if pt satisfies normal·pt + d <= PLANE_EPS for every plane.
    """
    for n, d in planes:
        if n.dot(pt) + d > PLANE_EPS:
            return False
    return True

# ------------------------------------------------------------
# --- Attempt Zone-Based Split
# ------------------------------------------------------------

def zone_bsp_split(bm, zone_obj, source_obj, region_min, region_max, tol=1e-4, min_diag=0.1):
    """
    Attempt to split bm along one of zone_obj’s face planes, but only if the region
    (given by region_min, region_max in source_obj's object space) actually overlaps
    the zone's bounding box in world space.

    Returns (bm_inside, bm_outside) or None if no valid candidate produces a meaningful split.
    """
    if not bm.faces:
        return None

    # Compute the world-space AABB for the zone.
    zmin, zmax = object_world_aabb(zone_obj)
    # Compute the region’s world AABB from region_min, region_max.
    mat = source_obj.matrix_world
    corners = []
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                x = region_min.x if dx == 0 else region_max.x
                y = region_min.y if dy == 0 else region_max.y
                z = region_min.z if dz == 0 else region_max.z
                corners.append(mat @ Vector((x, y, z)))
    rmin = Vector((float('inf'), float('inf'), float('inf')))
    rmax = Vector((-float('inf'), -float('inf'), -float('inf')))
    for c in corners:
        rmin.x = min(rmin.x, c.x); rmax.x = max(rmax.x, c.x)
        rmin.y = min(rmin.y, c.y); rmax.y = max(rmax.y, c.y)
        rmin.z = min(rmin.z, c.z); rmax.z = max(rmax.z, c.z)

    if not aabb_intersects(rmin, rmax, zmin, zmax):
        return None  # No overlap between zone and region.

    # Make a copy of bm to try candidate splits.
    bm_copy = bm.copy()

    # Try each polygon of zone_obj as a potential splitting plane.
    for poly in zone_obj.data.polygons:
        plane_co = zone_obj.matrix_world @ poly.center
        plane_no = (zone_obj.matrix_world.to_3x3() @ poly.normal).normalized()

        inside_count = 0
        outside_count = 0
        # Classify each face by its center (converted to world space).
        for f in bm_copy.faces:
            world_center = source_obj.matrix_world @ f.calc_center_median()
            d = (world_center - plane_co).dot(plane_no)
            if d < -tol:
                inside_count += 1
            elif d > tol:
                outside_count += 1

        if inside_count > 0 and outside_count > 0:
            d = -plane_no.dot(plane_co)
            # Bisect bm_copy along this candidate plane.
            bmesh.ops.bisect_plane(
                bm_copy,
                geom=list(bm_copy.faces) + list(bm_copy.edges) + list(bm_copy.verts),
                plane_co=plane_co,
                plane_no=plane_no,
                use_snap_center=False,
                clear_inner=False,
                clear_outer=False,
                dist=tol
            )
            # Classify resulting faces.
            inside_faces = []
            outside_faces = []
            for f in bm_copy.faces:
                wc = source_obj.matrix_world @ f.calc_center_median()
                dd = (wc - plane_co).dot(plane_no)
                if dd < -tol:
                    inside_faces.append(f)
                elif dd > tol:
                    outside_faces.append(f)
                else:
                    inside_faces.append(f)  # On the plane → treat as inside.
            if not inside_faces or not outside_faces:
                bm_copy.free()
                bm_copy = bm.copy()
                continue

            for f in bm_copy.faces:
                f.tag = False
            for f in inside_faces:
                f.tag = True
            bm_inside = duplicate_faces_by_tag(bm_copy, True)
            for f in bm_copy.faces:
                f.tag = False
            for f in outside_faces:
                f.tag = True
            bm_outside = duplicate_faces_by_tag(bm_copy, True)

            # Check if one side is too tiny.
            bmin_i, bmax_i = calculate_bounds_for_bmesh(bm_inside)
            diag_i = (bmax_i - bmin_i).length
            bmin_o, bmax_o = calculate_bounds_for_bmesh(bm_outside)
            diag_o = (bmax_o - bmin_o).length
            if diag_i < min_diag or diag_o < min_diag:
                bm_copy.free()
                bm_copy = bm.copy()
                continue

            bm_copy.free()
            return (bm_inside, bm_outside, plane_no.copy(), d)

    bm_copy.free()
    return None

# ------------------------------------------------------------
# --- Primary Recursive BSP Split (with Zone Splitting)
# ------------------------------------------------------------

def recursive_bsp_split(bm, vol_min, vol_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth=0):
    """
    Recursively subdivide the normalized volume using axis–aligned splits.
    When a region is small enough, attempt to further split it using zone-based splits.
    """
    size = vol_max - vol_min
    #print(f"\nRecursive call at depth {depth}: volume from {vol_min} to {vol_max} (size {size})")
    
    node_data = {
    "worldnode": worldnode_idx[0],
    "depth": depth,
    "normal": [0.0, 0.0, 0.0, 0.0],
    "front_tree": 0,
    "back_tree": None,
    "region_tag": ""
    }
    world_nodes.append(node_data)
    worldnode_idx[0] += 1

    # Base case: region is small enough.
    if all(size[i] <= target_size + 1e-6 for i in range(3)):
        # If zone splits apply for any zone, attempt them:
        for zone_obj in zone_volumes:
            split_result = zone_bsp_split(bm, zone_obj, source_obj, vol_min, vol_max, tol=1e-4, min_diag=0.1)
            if split_result is not None:
                bm_inside, bm_outside, plane_no, d = split_result
                node_data["normal"] = [-plane_no.x, -plane_no.y, -plane_no.z, -float(d)]
                node_data["front_tree"] = worldnode_idx[0]
                #print(f"Zone-based split succeeded with zone '{zone_obj.name}'.")
                # Compute bounding boxes from the resulting sub-BMeshes.
                bmin_i, bmax_i = calculate_bounds_for_bmesh(bm_inside)
                bmin_o, bmax_o = calculate_bounds_for_bmesh(bm_outside)
                recursive_bsp_split(bm_inside, bmin_i, bmax_i, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth+1)
                recursive_bsp_split(bm_outside, bmin_o, bmax_o, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth+1)
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
        if bm.faces:
            for f in bm.faces:
                f.tag = True
            new_bm = duplicate_faces_by_tag(bm, True)
            if new_bm.faces:
                empty_obj["SPRITE"] = f"R{region_index}_DMSPRITEDEF"
                create_mesh_object_from_bmesh(new_bm, f"R{region_index}_DMSPRITEDEF", source_obj, pending_objects)
        return

    # If bm has no faces, subdivide the volume anyway.
    if not bm.faces:
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
        split_pos = vol_min[axis] + target_size * math.floor((length/target_size)*0.5)
        plane_co = Vector((0, 0, 0))
        plane_no = Vector((0, 0, 0))
        plane_co[axis] = split_pos
        plane_no[axis] = 1.0
        d_value = -plane_no.dot(plane_co)
        
        node_data["normal"] = [-plane_no.x, -plane_no.y, -plane_no.z, -float(d_value)]
        node_data["front_tree"] = worldnode_idx[0]
        
        vol_lower_max = vol_max.copy(); vol_lower_max[axis] = split_pos
        vol_upper_min = vol_min.copy(); vol_upper_min[axis] = split_pos
        recursive_bsp_split(bmesh.new(), vol_min, vol_lower_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth+1)
        recursive_bsp_split(bmesh.new(), vol_upper_min, vol_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth+1)
        return

    # Otherwise, perform an axis-aligned split.
    valid_axes = [(i, size[i]) for i in range(3) if size[i] > target_size + 1e-6]
    if not valid_axes:
        region_index = region_counter[0]
        region_counter[0] += 1
        center = (vol_min + vol_max)*0.5
        print(f"Finalizing leaf region {region_index} (by grid split).")
        sphere_radius = (size).length / 2.0
        empty_obj = create_region_empty(center, sphere_radius, region_index, pending_objects)
        node_data["region_tag"] = empty_obj.name
        node_data["back_tree"] = 0
        for f in bm.faces:
            f.tag = True
        new_bm = duplicate_faces_by_tag(bm, True)
        if new_bm.faces:
            empty_obj["SPRITE"] = f"R{region_index}_DMSPRITEDEF"
            create_mesh_object_from_bmesh(new_bm, f"R{region_index}_DMSPRITEDEF", source_obj, pending_objects)
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
    
    bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.faces)+list(bm.edges)+list(bm.verts),
        plane_co=plane_co,
        plane_no=plane_no,
        use_snap_center=False,
        clear_inner=False,
        clear_outer=False
    )
    bm.faces.ensure_lookup_table()
    lower_faces = [f for f in bm.faces if f.calc_center_median()[axis] <= split_pos + 1e-6]
    upper_faces = [f for f in bm.faces if f.calc_center_median()[axis] > split_pos + 1e-6]
    for f in bm.faces:
        f.tag = False
    for f in lower_faces:
        f.tag = True
    bm_lower = duplicate_faces_by_tag(bm, True)
    for f in bm.faces:
        f.tag = False
    for f in upper_faces:
        f.tag = True
    bm_upper = duplicate_faces_by_tag(bm, True)
    vol_lower_max = vol_max.copy()
    vol_lower_max[axis] = split_pos
    vol_upper_min = vol_min.copy()
    vol_upper_min[axis] = split_pos
    #print(f"Axis–aligned split at axis {axis} at position {split_pos}")
    recursive_bsp_split(bm_lower, vol_min, vol_lower_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth+1)
    recursive_bsp_split(bm_upper, vol_upper_min, vol_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, pending_objects, depth+1)

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

        vcol_attr = next((a for a in src.data.color_attributes if a.domain == 'POINT'), None)
        if vcol_attr:
            # use slicing to copy the array into a tuple
            vertex_colors = [c.color[:] for c in vcol_attr.data]
        else:
            vertex_colors = None

        bm = bmesh.new(); bm.from_mesh(src.data)

        # --- Collect custom split normals from source mesh ---
        src.data.calc_normals_split()
        src.data.use_auto_smooth = True

        # --- Create generic loop float BMesh layer for split normals
        ln_layer = bm.loops.layers.float_vector.new("orig_normals")
        loops = (l for f in bm.faces for l in f.loops)
        for loop in loops:
            loop[ln_layer] = src.data.loops[loop.index].normal

        if vertex_colors:
            # make a fresh corner‑domain layer in the BMesh
            loop_col = bm.loops.layers.color.new(vcol_attr.name + "_loop")
            # copy per‑vertex → per‑loop
            loops = (l for f in bm.faces for l in f.loops)
            for loop in loops:
                loop[loop_col] = vertex_colors[loop.vert.index]

        region_counter = [1]; world_nodes = []; worldnode_idx = [1]
        recursive_bsp_split(bm, vol_min, vol_max, target_size,
                            region_counter, src, zone_volumes,
                            world_nodes, worldnode_idx, pending_objects, depth=0)
        assign_back_trees(world_nodes)
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
            zone: build_zone_planes(zone)
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