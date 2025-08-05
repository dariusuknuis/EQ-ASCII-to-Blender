import bpy, bmesh
from mathutils import Vector

def _compute_aabb(coords, world_mat=None):
    """
    coords: an iterable of Vector
    world_mat: a 4×4 Matrix or None
    Returns (min_vec, max_vec).  If coords is empty, returns (0,0,0),(0,0,0).
    """
    it = iter(coords)
    try:
        first = next(it)
    except StopIteration:
        return Vector(), Vector()
    if world_mat:
        first = world_mat @ first
    minb = Vector(first)
    maxb = Vector(first)
    for c in it:
        w = world_mat @ c if world_mat else c
        minb.x = min(minb.x, w.x)
        minb.y = min(minb.y, w.y)
        minb.z = min(minb.z, w.z)
        maxb.x = max(maxb.x, w.x)
        maxb.y = max(maxb.y, w.y)
        maxb.z = max(maxb.z, w.z)
    return minb, maxb

def aabb_mesh_local(obj: bpy.types.Object):
    """Object-space AABB of a Mesh object."""
    return _compute_aabb((v.co for v in obj.data.vertices))

def aabb_mesh_world(obj: bpy.types.Object):
    """World-space AABB of a Mesh object."""
    return _compute_aabb((v.co for v in obj.data.vertices), obj.matrix_world)

def aabb_bmesh_local(bm: bmesh.types.BMesh):
    """Object-space AABB of a BMesh."""
    return _compute_aabb((v.co for v in bm.verts))

def aabb_bmesh_world(bm: bmesh.types.BMesh, obj: bpy.types.Object):
    """
    World-space AABB of a BMesh.  
    `obj` is only used to supply matrix_world.
    """
    return _compute_aabb((v.co for v in bm.verts), obj.matrix_world)

def aabb_intersects(minA, maxA, minB, maxB, epsilon=0.000):
    """Return True if two padded AABBs intersect."""
    return not (
        maxA.x + epsilon < minB.x - epsilon or minA.x - epsilon > maxB.x + epsilon or
        maxA.y + epsilon < minB.y - epsilon or minA.y - epsilon > maxB.y + epsilon or
        maxA.z + epsilon < minB.z - epsilon or minA.z - epsilon > maxB.z + epsilon
    )

def compute_bmesh_volume_centroid(bm: bmesh.types.BMesh):
    """
    Compute the center of volume (centroid) of a *closed* BMesh.
    Returns (centroid, volume).  If the mesh is not closed or has
    near-zero volume, returns (None, 0.0).
    """
    bm.faces.ensure_lookup_table()

    total_vol = 0.0
    weighted_centroid = Vector((0.0, 0.0, 0.0))
    # We’ll tetrahedralize each face-triangle against the global origin:
    origin = Vector((0.0, 0.0, 0.0))

    for f in bm.faces:
        # skip degenerate or non-manifold faces
        if len(f.verts) < 3:
            continue

        # fan-triangulate n-gon
        v0 = f.verts[0].co
        for i in range(1, len(f.verts) - 1):
            v1 = f.verts[i].co
            v2 = f.verts[i + 1].co

            # signed tetra volume = (1/6) * dot(v0 × v1, v2)
            vol = v0.cross(v1).dot(v2) / 6.0
            if abs(vol) < 1e-12:
                continue

            # centroid of tetra (v0, v1, v2, origin) is average of its 4 points
            tet_centroid = (v0 + v1 + v2 + origin) / 4.0

            total_vol += vol
            weighted_centroid += tet_centroid * vol

    if abs(total_vol) < 1e-8:
        # zero or non-closed mesh
        return None, 0.0

    # divide by total (signed) volume
    center_of_volume = weighted_centroid / total_vol
    return center_of_volume

def point_inside_convex(pt, planes, tol=1e-9):
    """
    True if pt satisfies normal·pt + d <= PLANE_EPS for every plane.
    """
    for n, d in planes:
        if n.dot(pt) + d > tol:
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