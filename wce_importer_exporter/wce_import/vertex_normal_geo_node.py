import bpy
import bmesh
from math import pi
from .material_utils import _add_group_socket, _get_group_io_sockets

# Default names (change if you like)
GROUP_NAME    = "GN_VertexNormals_Visualizer"
MATERIAL_NAME = "EQ_VERTEX_NORMALS"

# ------------------------------------------------------------
# Material
# ------------------------------------------------------------

def ensure_eq_vertex_normals_material(name="EQ_VERTEX_NORMALS"):
    """Create (or reuse) a simple Principled BSDF material for the GN output."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True

        nt = mat.node_tree
        nt.nodes.clear()

        out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
        principled = nt.nodes.new("ShaderNodeBsdfPrincipled"); principled.location = (0, 0)

        # Magenta-ish color like your screenshot
        principled.inputs["Base Color"].default_value = (1.0, 0.0, 1.0, 1.0)
        principled.inputs["Alpha"].default_value = 1.0

        nt.links.new(principled.outputs["BSDF"], out.inputs["Surface"])

        # Viewport behavior (tweak as you like)
        mat.blend_method = 'OPAQUE'
        # If you want to keep around even when unused:
        mat.use_fake_user = True

    return mat

# ------------------------------------------------------------
# Geometry Nodes group (the node graph from your screenshot)
# ------------------------------------------------------------

def create_gn_vertex_normals_group(
    group_name="GN_VertexNormals_Visualizer",
    material_name="EQ_VERTEX_NORMALS"
):
    """Build a GN group that:
       - converts vertices -> points
       - instances a 1m straight line (as a curve) on each vertex
       - orients the line by per-vertex vector attribute 'vertex_normals'
       - gives each line a round profile (Curve Circle, r=0.003, res=4)
       - converts to mesh, assigns a material, joins with original geometry.
    """
    # Idempotent: reuse node group if present
    if group_name in bpy.data.node_groups:
        ng = bpy.data.node_groups[group_name]
        # Make sure the material exists and is set on the Set Material node
        mat = ensure_eq_vertex_normals_material(material_name)
        for n in ng.nodes:
            if n.bl_idname == "GeometryNodeSetMaterial":
                n.inputs["Material"].default_value = mat
        return ng

    # Make sure material exists
    mat = ensure_eq_vertex_normals_material(material_name)

    ng = bpy.data.node_groups.new(group_name, 'GeometryNodeTree')
    nodes = ng.nodes
    links = ng.links

    # I/O
    n_in  = nodes.new("NodeGroupInput");  n_in.location  = (-1200, 0)
    n_out = nodes.new("NodeGroupOutput"); n_out.location = (  500, 0)
    _add_group_socket(ng, 'Geometry', 'NodeSocketGeometry', is_input=True)
    _add_group_socket(ng, 'Geometry', 'NodeSocketGeometry', is_input=False)

    # Mesh to Points (Vertices)
    n_mesh2pts = nodes.new("GeometryNodeMeshToPoints")
    n_mesh2pts.location = (-950, 120)
    n_mesh2pts.mode = 'VERTICES'   # Points from vertices
    # Optional: sphere radius around each point (matches screenshot readout)
    n_mesh2pts.inputs["Radius"].default_value = 0.05

    # Named Attribute: vertex_normals (FLOAT_VECTOR)
    n_attr = nodes.new("GeometryNodeInputNamedAttribute")
    n_attr.location = (-950, -200)
    n_attr.data_type = 'FLOAT_VECTOR'
    n_attr.inputs["Name"].default_value = "vertex_normals"

    # Align Rotation to Vector (Rotation socket)
    n_align = nodes.new("FunctionNodeAlignRotationToVector")
    n_align.location = (-700, -70)
    n_align.axis = 'Z'         # align the Z axis to the vector
    n_align.pivot_axis = 'AUTO'
    links.new(n_attr.outputs["Attribute"], n_align.inputs["Vector"])

    # Extra 90° Z offset (Combine Euler -> Euler Math Add)
    n_rot_offset = nodes.new("FunctionNodeInputRotation")
    n_rot_offset.location = (-700, -250)
    n_rot_offset.rotation_euler[2] = 1.57079632679  # 90° in radians

    n_vec_add = nodes.new("ShaderNodeVectorMath")
    n_vec_add.location = (-480, -130)
    n_vec_add.operation = 'ADD'
    links.new(n_align.outputs["Rotation"], n_vec_add.inputs[0])
    links.new(n_rot_offset.outputs["Rotation"], n_vec_add.inputs[1])

    # Straight 1m line (Curve Line in Points mode: 0,0,0 -> 0,0,1)
    n_line = nodes.new("GeometryNodeCurvePrimitiveLine")
    n_line.location = (-700, 280)
    n_line.mode = 'POINTS'
    # Defaults are fine: Start (0,0,0), End (0,0,1)

    # Instance on Points (put the line on each vertex point)
    n_inst = nodes.new("GeometryNodeInstanceOnPoints")
    n_inst.location = (-260, 160)
    # Instance
    links.new(n_line.outputs["Curve"],      n_inst.inputs["Instance"])
    # Points from Mesh to Points
    links.new(n_mesh2pts.outputs["Points"], n_inst.inputs["Points"])
    # Rotation from Euler math
    links.new(n_vec_add.outputs["Vector"], n_inst.inputs["Rotation"])
    # Scale (vector): 0.25, 0.25, 0.25 like your screenshot
    n_inst.inputs["Scale"].default_value = (0.25, 0.25, 0.25)

    # Round profile for the line (Curve Circle: res 4, radius 0.003)
    n_circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
    n_circle.location = (-260, -20)
    n_circle.inputs["Resolution"].default_value = 4
    n_circle.inputs["Radius"].default_value = 0.003

    # Curve to Mesh (with Fill Caps)
    n_curve2mesh = nodes.new("GeometryNodeCurveToMesh")
    n_curve2mesh.location = (-30, 110)
    n_curve2mesh.inputs[3].default_value = True
    links.new(n_inst.outputs["Instances"],      n_curve2mesh.inputs["Curve"])
    links.new(n_circle.outputs["Curve"],        n_curve2mesh.inputs["Profile Curve"])

    # Set Material
    n_setmat = nodes.new("GeometryNodeSetMaterial")
    n_setmat.location = (170, 120)
    n_setmat.inputs["Material"].default_value = mat
    links.new(n_curve2mesh.outputs["Mesh"], n_setmat.inputs["Geometry"])

    # Join original geometry back
    n_join = nodes.new("GeometryNodeJoinGeometry")
    n_join.location = (350, 60)

    in_sock, out_sock = _get_group_io_sockets(ng)
    links.new(n_setmat.outputs["Geometry"], n_join.inputs["Geometry"])
    links.new(in_sock["Geometry"],     n_join.inputs["Geometry"])

    # Wire input and output
    links.new(in_sock["Geometry"],  n_mesh2pts.inputs["Mesh"])
    links.new(n_join.outputs["Geometry"], out_sock["Geometry"])

    return ng

# ------------------------------------------------------------
# Public API you import and call from import_wce_file.py
# ------------------------------------------------------------
def apply_vertex_normal_geo_node(
    obj_or_iter,
    group_name=GROUP_NAME,
    material_name=MATERIAL_NAME,
    modifier_name=GROUP_NAME
):
    """Ensure the GN group + material exist, then apply the modifier to:
       - a single Mesh object, or
       - any iterable of Mesh objects.
       Returns a list of (object, modifier) pairs that were ensured/applied.
    """
    # Normalize to iterable
    if isinstance(obj_or_iter, (list, tuple, set)):
        objs = list(obj_or_iter)
    else:
        objs = [obj_or_iter]

    # Ensure shared resources
    ng  = create_gn_vertex_normals_group(group_name, material_name)

    applied = []
    for obj in objs:
        if not obj or obj.type != 'MESH':
            continue

        # Reuse existing modifier if present; otherwise create
        mod = obj.modifiers.get(modifier_name)
        if mod is None:
            mod = obj.modifiers.new(modifier_name, 'NODES')

        # Assign the group every time (idempotent)
        mod.node_group = ng

        # Optional: ensure the vertex attribute exists (creates empty layer if missing)
        _ensure_float_vector_layer(obj.data, "vertex_normals")

        applied.append((obj, mod))

    return applied


# ------------------------------------------------------------
# Small helper: make sure the float_vector layer exists
# ------------------------------------------------------------
def _ensure_float_vector_layer(mesh: bpy.types.Mesh, layer_name: str):
    """Ensure a per-vertex float_vector custom-data layer exists (Edit mode safe)."""
    # Handle both Object and Edit mode
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        if bm.verts.layers.float_vector.get(layer_name) is None:
            bm.verts.layers.float_vector.new(layer_name)
            bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        if bm.verts.layers.float_vector.get(layer_name) is None:
            bm.verts.layers.float_vector.new(layer_name)
            bm.to_mesh(mesh)
        bm.free()
