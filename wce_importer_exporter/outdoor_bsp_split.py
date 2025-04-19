import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix
from create_bounding_sphere import create_bounding_sphere 
import math
import re


# ------------------------------------------------------------
# --- WorldNode Mesh Creation
# ------------------------------------------------------------

DEFAULT_SIZE = 10000.0  # Default plane side length

def create_bsp_plane_mesh(name="BSPPlaneMesh", size=DEFAULT_SIZE):
    """
    Create a plane mesh that is oriented in its local space so that its face lies in the XZ plane.
    That means its vertices are defined so that the plane’s normal is (0, 1, 0) (local +Y).
    We create a square of side length 'size'.
    """
    half = size / 2.0
    # Create a default plane in the XY plane (face normal = (0,0,1))
    verts = [
        (-half, -half, 0),
        ( half, -half, 0),
        ( half,  half, 0),
        (-half,  half, 0)
    ]
    faces = [(0, 1, 2, 3)]
    # Rotate the mesh by -90° about the X axis to put the face into the XZ plane.
    rot = mathutils.Euler((-math.pi/2, 0, 0), 'XYZ').to_matrix().to_4x4()
    verts_rot = [rot @ mathutils.Vector(v) for v in verts]
    
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts_rot, [], faces)
    mesh.update()
    return mesh

def create_leaf_mesh(name="LeafMesh"):
    """
    Create a minimal mesh for leaf nodes.
    We'll create a mesh with a single vertex at the origin.
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0)], [], [])
    mesh.update()
    return mesh

def rotation_from_normal(normal):
    """
    Compute an Euler rotation that rotates the object's local +Y axis (which is the normal of our base plane)
    to align with the given target normal.
    """
    default_dir = mathutils.Vector((0, 1, 0))
    target_dir = mathutils.Vector(normal).normalized()
    quat = default_dir.rotation_difference(target_dir)
    return quat.to_euler()

def calculate_point_on_plane(normal, d, max_distance=10000.0):
    """
    Calculate the point on the plane (n · p + d = 0) that is closest to the origin.
    n must be normalized. That point is p = -d * n.
    
    If the distance of that point exceeds max_distance, return the point on the ray (origin to p)
    clamped to max_distance.
    """
    n = mathutils.Vector(normal).normalized()
    p = -d * n  # The unique closest point on the plane.
    if p.length > max_distance:
        p = p.normalized() * max_distance
    return p

def compute_scale_from_location(location, default_size=DEFAULT_SIZE):
    """
    Compute a uniform scale factor for the plane based on the node's location.
    Increase the plane's size by the absolute value of the highest coordinate.
    """
    offset = max(abs(location.x), abs(location.y), abs(location.z))
    final_size = default_size + offset
    scale_factor = final_size / default_size
    return scale_factor

def create_worldtree(worldtree_data):
    """
    Creates a WorldTree from the provided data.
    Each non-leaf node is represented by a plane mesh (with a translucent yellow material and a Solidify modifier)
    oriented so that its local +Y (the plane's normal) matches the node's plane normal.
    For leaf nodes (no front_tree or back_tree), a minimal mesh (with one vertex) is created and its rotation is set to zero.
    The plane's size is increased by the absolute maximum coordinate of its location.
    Parent-child relationships are set up, but we preserve each object's world transform.
    """
    if not worldtree_data or "nodes" not in worldtree_data:
        print("No WorldTree data to process.")
        return None

    # Create a root empty for organization.
    root_obj = bpy.data.objects.new("WorldTree_Root", None)
    bpy.context.collection.objects.link(root_obj)

    # Create a base plane mesh for non-leaf nodes.
    base_mesh = create_bsp_plane_mesh(size=DEFAULT_SIZE)
    
    # Create a translucent yellow material.
    mat = bpy.data.materials.get("WorldTreePlaneMaterial")
    if not mat:
        mat = bpy.data.materials.new("WorldTreePlaneMaterial")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 0.0, 0.25)  # yellow, alpha 0.25
            bsdf.inputs["Alpha"].default_value = 0.25
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'NONE'
        mat.use_backface_culling = False

    node_objects = {}

    # Create an object for each node.
    for node in worldtree_data["nodes"]:
        node_name = f"WorldNode_{node['worldnode']}"
        normal = node["normal"][:3]  # e.g., [0, -1, 0]
        d = node["normal"][3]        # e.g., 261.188873

        # Calculate the location of the plane.
        position = calculate_point_on_plane(normal, d)
        # Determine if the node is a leaf node.
        is_leaf = (node["front_tree"] == 0 and node["back_tree"] == 0)
        
        if is_leaf:
            # For leaf nodes, create a minimal mesh (1 vertex at the origin).
            mesh_data = create_leaf_mesh(name=f"LeafMesh_{node['worldnode']}")
            rotation = mathutils.Euler((0, 0, 0))  # zero rotation
            obj_scale = (1, 1, 1)
        else:
            # Non-leaf nodes use the base plane mesh.
            mesh_data = base_mesh
            # Compute rotation so that the plane's local +Y (the face normal) aligns with the node's normal.
            rotation = rotation_from_normal(normal)
            # Compute scale factor based on the maximum offset.
            scale_factor = compute_scale_from_location(position, default_size=DEFAULT_SIZE)
            obj_scale = (scale_factor, scale_factor, scale_factor)
        
        node_obj = bpy.data.objects.new(node_name, mesh_data)
        node_obj.location = position
        node_obj.rotation_euler = rotation
        node_obj.scale = obj_scale

        # For non-leaf nodes, assign material and add a Solidify modifier.
        if not is_leaf:
            if len(node_obj.data.materials) == 0:
                node_obj.data.materials.append(mat)
            else:
                node_obj.data.materials[0] = mat
            solidify = node_obj.modifiers.new(name="Solidify", type='SOLIDIFY')
            solidify.thickness = 3.0
            solidify.offset = 0.0
            
            

        bpy.context.collection.objects.link(node_obj)

        # Save custom properties.
        node_obj["worldnode"] = node["worldnode"]
        node_obj["normal"] = normal
        node_obj["d"] = d
        node_obj["region_tag"] = node["region_tag"]
        node_obj["front_tree"] = node["front_tree"]
        node_obj["back_tree"] = node["back_tree"]

        node_objects[node["worldnode"]] = node_obj

    bpy.context.view_layer.update()

    # Re-parent child nodes while preserving their world transforms.
    for node in worldtree_data["nodes"]:
        parent_obj = node_objects[node["worldnode"]]
        if node["front_tree"] > 0:
            front_child = node_objects.get(node["front_tree"])
            if front_child:
                wm = front_child.matrix_world.copy()
                front_child.parent = parent_obj
                front_child.matrix_parent_inverse = parent_obj.matrix_world.inverted()
                front_child.matrix_world = wm
                parent_obj.hide_set(True)
        if node["back_tree"] > 0:
            back_child = node_objects.get(node["back_tree"])
            if back_child:
                wm = back_child.matrix_world.copy()
                back_child.parent = parent_obj
                back_child.matrix_parent_inverse = parent_obj.matrix_world.inverted()
                back_child.matrix_world = wm
                parent_obj.hide_set(True)

    for node_obj in node_objects.values():
        if not node_obj.parent:
            wm = node_obj.matrix_world.copy()
            node_obj.parent = root_obj
            node_obj.matrix_parent_inverse = root_obj.matrix_world.inverted()
            node_obj.matrix_world = wm

    print(f"Created WorldTree with {len(worldtree_data['nodes'])} nodes as meshes (leaf nodes have zero rotation).")
    return root_obj

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

def create_region_empty(center, sphere_radius, index):
    """
    Create an empty (for labeling/visualization) at the given center.
    The empty is set up as a sphere with display size equal to the computed sphere radius.
    """
    bpy.ops.object.empty_add(type='SPHERE', location=center)
    empty = bpy.context.active_object
    empty.name = f"R{index:06d}"
    empty.empty_display_size = sphere_radius
    
    empty["VISLISTBYTES"] = True
    empty["VISLIST_01"] = ""
    
    return empty

def duplicate_faces_by_tag(bm, tag_value):
    """
    Duplicate all faces in bm that have face.tag == tag_value into a new bmesh.
    Preserves the active UV layer if present.
    """
    new_bm = bmesh.new()
    v_map = {}
    uv_layer_src = bm.loops.layers.uv.active
    uv_layer_dst = new_bm.loops.layers.uv.new() if uv_layer_src else None
    for face in bm.faces:
        if face.tag == tag_value:
            new_verts = []
            for v in face.verts:
                if v not in v_map:
                    v_map[v] = new_bm.verts.new(v.co)
                new_verts.append(v_map[v])
            try:
                new_face = new_bm.faces.new(new_verts)
            except ValueError:
                continue  # Skip degenerate faces
            new_face.material_index = face.material_index
            if uv_layer_src and uv_layer_dst:
                for l_old, l_new in zip(face.loops, new_face.loops):
                    l_new[uv_layer_dst].uv = l_old[uv_layer_src].uv
    new_bm.normal_update()
    return new_bm

import bpy
from mathutils import Vector, Matrix

def create_mesh_object_from_bmesh(bm, name, original_obj):
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

    # create the object
    new_obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(new_obj)

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
    # half the diagonal is the sphere radius
    radius = ((maxv - minv).length) * 0.5

    # --- recenter the mesh geometry so box-center moves to origin ---
    me.transform(Matrix.Translation(-center_world))

    # place the new object back at the box-center
    new_obj.matrix_world = Matrix.Translation(center_world)

    # --- finally, add the bounding sphere ---
    bounding_sphere = create_bounding_sphere(new_obj, radius)
    bounding_sphere.hide_set(True)

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

def world_point_inside_zone(point, zone_obj):
    """
    Determine if a world-space point is inside a _ZONE volume using the mesh's
    closest point routine. (Assumes zone normals point outwards.)
    """
    # Convert the point into the zone's local space.
    inv_mat = zone_obj.matrix_world.inverted()
    local_point = inv_mat @ point
    # Use the built-in method: closest_point_on_mesh returns (result, location, normal, index)
    result, location, normal, index = zone_obj.closest_point_on_mesh(local_point)
    if not result:
        return False
    # Transform the face center and normal back to world space.
    poly = zone_obj.data.polygons[index]
    poly_center = zone_obj.matrix_world @ poly.center
    poly_normal = (zone_obj.matrix_world.to_3x3() @ poly.normal).normalized()
    # A point is inside if (point - poly_center) dot (poly_normal) is negative.
    return (point - poly_center).dot(poly_normal) < 0

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

def recursive_bsp_split(bm, vol_min, vol_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth=0):
    """
    Recursively subdivide the normalized volume using axis–aligned splits.
    When a region is small enough, attempt to further split it using zone-based splits.
    """
    size = vol_max - vol_min
    print(f"\nRecursive call at depth {depth}: volume from {vol_min} to {vol_max} (size {size})")
    
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
                node_data["normal"] = [plane_no.x, plane_no.y, plane_no.z, float(d)]
                node_data["front_tree"] = worldnode_idx[0]
                print(f"Zone-based split succeeded with zone '{zone_obj.name}'.")
                # Compute bounding boxes from the resulting sub-BMeshes.
                bmin_i, bmax_i = calculate_bounds_for_bmesh(bm_inside)
                bmin_o, bmax_o = calculate_bounds_for_bmesh(bm_outside)
                recursive_bsp_split(bm_inside, bmin_i, bmax_i, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth+1)
                recursive_bsp_split(bm_outside, bmin_o, bmax_o, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth+1)
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
        print(f"Finalizing leaf region {region_index} with sphere radius {sphere_radius:.4f} (world-space).")
        empty_obj = create_region_empty(center, sphere_radius, region_index)
        node_data["region_tag"] = empty_obj.name
        node_data["back_tree"] = 0
        if bm.faces:
            for f in bm.faces:
                f.tag = True
            new_bm = duplicate_faces_by_tag(bm, True)
            if new_bm.faces:
                create_mesh_object_from_bmesh(new_bm, f"R{region_index}_DMSPRITEDEF", source_obj)
        return

    # If bm has no faces, subdivide the volume anyway.
    if not bm.faces:
        axis, length = max(enumerate(size), key=lambda x: x[1])
        if length <= target_size:
            region_index = region_counter[0]
            region_counter[0] += 1
            center = (vol_min + vol_max)*0.5
            print(f"Empty region at depth {depth}; finalizing as leaf region {region_index}.")
            # Compute sphere radius from volume dimensions.
            sphere_radius = (size).length / 2.0
            empty_obj = create_region_empty(center, sphere_radius, region_index)
            node_data["region_tag"] = empty_obj.name
            node_data["back_tree"] = 0
            return
        split_pos = vol_min[axis] + target_size * math.floor((length/target_size)*0.5)
        plane_co = Vector((0, 0, 0))
        plane_no = Vector((0, 0, 0))
        plane_co[axis] = split_pos
        plane_no[axis] = 1.0
        d_value = -plane_no.dot(plane_co)
        
        node_data["normal"] = [plane_no.x, plane_no.y, plane_no.z, float(d_value)]
        node_data["front_tree"] = worldnode_idx[0]
        
        vol_lower_max = vol_max.copy(); vol_lower_max[axis] = split_pos
        vol_upper_min = vol_min.copy(); vol_upper_min[axis] = split_pos
        recursive_bsp_split(bmesh.new(), vol_min, vol_lower_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth+1)
        recursive_bsp_split(bmesh.new(), vol_upper_min, vol_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth+1)
        return

    # Otherwise, perform an axis-aligned split.
    valid_axes = [(i, size[i]) for i in range(3) if size[i] > target_size + 1e-6]
    if not valid_axes:
        region_index = region_counter[0]
        region_counter[0] += 1
        center = (vol_min + vol_max)*0.5
        print(f"Finalizing leaf region {region_index} (by grid split).")
        sphere_radius = (size).length / 2.0
        empty_obj = create_region_empty(center, sphere_radius, region_index)
        node_data["region_tag"] = empty_obj.name
        node_data["back_tree"] = 0
        for f in bm.faces:
            f.tag = True
        new_bm = duplicate_faces_by_tag(bm, True)
        if new_bm.faces:
            create_mesh_object_from_bmesh(new_bm, f"R{region_index}_DMSPRITEDEF", source_obj)
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
    node_data["normal"] = [plane_no.x, plane_no.y, plane_no.z, float(d_value)]
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
    print(f"Axis–aligned split at axis {axis} at position {split_pos}")
    recursive_bsp_split(bm_lower, vol_min, vol_lower_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth+1)
    recursive_bsp_split(bm_upper, vol_upper_min, vol_max, target_size, region_counter, source_obj, zone_volumes, world_nodes, worldnode_idx, depth+1)

# ------------------------------------------------------------
# --- Main Runner
# ------------------------------------------------------------

def run_outdoor_bsp_split(target_size=282.0):
    selected_objs = [obj for obj in bpy.context.selected_objects 
                     if obj.type == 'MESH' and not obj.name.endswith('_ZONE')]
    if not selected_objs:
        print("No valid mesh selected. Please select a mesh object (not a _ZONE).")
        return

    zone_volumes = [obj for obj in bpy.data.objects 
                    if obj.type == 'MESH' and obj.name.endswith('_ZONE')]
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
        region_counter = [1]; world_nodes = []; worldnode_idx = [1]
        recursive_bsp_split(bm, vol_min, vol_max, target_size,
                            region_counter, src, zone_volumes,
                            world_nodes, worldnode_idx, depth=0)
        assign_back_trees(world_nodes)
        worldtree = {"nodes": world_nodes, "total_nodes": len(world_nodes)}

        # --- 3) Create & parent the WorldTree root ---
        root_obj = create_worldtree(worldtree)
        wm = root_obj.matrix_world.copy()
        root_obj.parent = container
        root_obj.matrix_parent_inverse = container.matrix_world.inverted()
        root_obj.matrix_world = wm
        
        for zone_obj in zone_volumes:
            region_idxs = []
            for empty in (o for o in bpy.data.objects if re.fullmatch(r"R\d{6}", o.name)):
                if world_point_inside_zone(empty.location, zone_obj):
                    region_idxs.append(int(empty.name[1:]) - 1)
            # format as a string "[n, n, n]"
            region_str = "[" + ", ".join(str(i) for i in region_idxs) + "]"
            zone_obj["REGIONLIST"] = region_str
            print(f"{zone_obj.name}.REGIONLIST = {region_str}")

        # --- 4) Parent any existing _ZONE meshes ---
        for zone in zone_volumes:
            wm = zone.matrix_world.copy()
            zone.parent = container
            zone.matrix_parent_inverse = container.matrix_world.inverted()
            zone.matrix_world = wm

        # --- 5) Parent all region empties (R######) ---
        for obj in bpy.data.objects:
            if (obj.type == 'EMPTY' and
                re.fullmatch(r"R\d{6}", obj.name)):
                wm = obj.matrix_world.copy()
                obj.parent = container
                obj.matrix_parent_inverse = container.matrix_world.inverted()
                obj.matrix_world = wm
        
        # 6) Parent all region meshes (R###_DMSPRITEDEF)
        for obj in bpy.data.objects:
            if re.fullmatch(r"R\d+_DMSPRITEDEF", obj.name):
                wm = obj.matrix_world.copy()
                obj.parent = container
                obj.matrix_parent_inverse = container.matrix_world.inverted()
                obj.matrix_world = wm

    print("BSP splitting complete.")

# ------------------------------------------------------------
# --- Run the Script
# ------------------------------------------------------------

#run_outdoor_bsp_split(target_size=282.0)