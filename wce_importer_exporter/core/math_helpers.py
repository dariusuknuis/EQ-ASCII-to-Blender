import bpy
from mathutils import Vector

def object_world_aabb(obj):
    """
    Return the world‐space axis‐aligned bounding box of a mesh object.
    Returns (min_corner, max_corner) as two Vectors.
    If `obj` isn’t a mesh or has no vertices, returns (0,0,0),(0,0,0).
    """
    # 1) Validate input
    if not isinstance(obj, bpy.types.Object) or obj.type != 'MESH':
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    verts = obj.data.vertices
    if not verts:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    
    # 2) Grab the world‐matrix once
    mat = obj.matrix_world
    
    # 3) Initialize min/max to the first transformed vertex
    wco = mat @ verts[0].co
    minb = Vector(wco)
    maxb = Vector(wco)
    
    # 4) One‐pass update of all remaining verts
    for v in verts[1:]:
        wco = mat @ v.co
        if wco.x < minb.x: minb.x = wco.x
        if wco.y < minb.y: minb.y = wco.y
        if wco.z < minb.z: minb.z = wco.z
        if wco.x > maxb.x: maxb.x = wco.x
        if wco.y > maxb.y: maxb.y = wco.y
        if wco.z > maxb.z: maxb.z = wco.z
    
    return minb, maxb

def aabb_intersects(minA, maxA, minB, maxB, epsilon=0.000):
    """Return True if two padded AABBs intersect."""
    return not (
        maxA.x + epsilon < minB.x - epsilon or minA.x - epsilon > maxB.x + epsilon or
        maxA.y + epsilon < minB.y - epsilon or minA.y - epsilon > maxB.y + epsilon or
        maxA.z + epsilon < minB.z - epsilon or minA.z - epsilon > maxB.z + epsilon
    )