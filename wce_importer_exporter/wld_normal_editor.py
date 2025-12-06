import bpy
import bmesh
from bpy.props import FloatVectorProperty
from mathutils import Vector

LAYER_NAME = "vertex_normals"
_UPDATING = False

# ---------- helpers ----------

def _in_edit_vertex_mode(context):
    ob = context.active_object
    if not (ob and ob.type == 'MESH' and ob.mode == 'EDIT'):
        return False
    sel_mode = context.tool_settings.mesh_select_mode
    return bool(sel_mode[0])  # vertex-select on

def _get_bm_and_layer(mesh):
    bm = bmesh.from_edit_mesh(mesh)
    layer = bm.verts.layers.float_vector.get(LAYER_NAME)
    return bm, layer

def _get_active_bmvert(bm):
    hist = bm.select_history.active
    if hist and isinstance(hist, bmesh.types.BMVert):
        return hist
    # Fallback: first selected vert
    for v in bm.verts:
        if v.select:
            return v
    return None

def _ensure_layer(mesh):
    bm = bmesh.from_edit_mesh(mesh)
    layer = bm.verts.layers.float_vector.get(LAYER_NAME)
    if layer is None:
        layer = bm.verts.layers.float_vector.new(LAYER_NAME)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    return layer

def _read_active_vert_value(context):
    ob = context.active_object
    me = ob.data
    bm, layer = _get_bm_and_layer(me)
    if layer is None:
        return None
    v = _get_active_bmvert(bm)
    if v is None:
        return None
    # v[layer] is a mathutils.Vector of length 3
    return tuple(v[layer])

def _write_active_vert_value(context, vec3):
    ob = context.active_object
    me = ob.data
    bm = bmesh.from_edit_mesh(me)
    layer = bm.verts.layers.float_vector.get(LAYER_NAME)
    if layer is None:
        layer = bm.verts.layers.float_vector.new(LAYER_NAME)
    v = _get_active_bmvert(bm)
    if v is None:
        return False
    v[layer] = vec3
    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)
    return True

def _sync_ui_from_vec(context, vec: Vector):
    """Update both UI fields from a vector (widget gets normalized preview)."""
    global _UPDATING
    try:
        _UPDATING = True
        # Raw numeric boxes reflect exact stored value
        context.scene.vertex_normals_vec_xyz = vec[:]
        # Direction widget shows normalized (if non-zero), else fallback +Z
        if vec.length_squared > 0.0:
            context.scene.vertex_normals_edit_vec = vec.normalized()
        else:
            context.scene.vertex_normals_edit_vec = (0.0, 0.0, 1.0)
    finally:
        _UPDATING = False

# ---------- properties (two synced fields: widget + raw xyz) ----------

def _update_vec_widget(self, context):
    """Dragged the sphere: write normalized direction; sync raw boxes."""
    global _UPDATING
    if _UPDATING or not _in_edit_vertex_mode(context):
        return
    w = Vector(context.scene.vertex_normals_edit_vec)
    if w.length_squared == 0.0:
        # Avoid writing zero from the widget; keep previous
        return
    w.normalize()
    _write_active_vert_value(context, w[:])
    _sync_ui_from_vec(context, w)

def _update_vec_xyz(self, context):
    """Edited raw XYZ boxes: write exact values; widget shows normalized preview."""
    global _UPDATING
    if _UPDATING or not _in_edit_vertex_mode(context):
        return
    v = Vector(context.scene.vertex_normals_vec_xyz)
    _write_active_vert_value(context, v[:])
    _sync_ui_from_vec(context, v)

def register_props():
    s = bpy.types.Scene
    # Direction widget (unit preview)
    s.vertex_normals_edit_vec = FloatVectorProperty(
        name="Direction",
        description=f"Normalized direction preview for '{LAYER_NAME}' (drag to rotate)",
        size=3,
        subtype='DIRECTION',
        default=(0.0, 0.0, 1.0),
        update=_update_vec_widget,
    )
    # Raw XYZ numeric boxes (exact stored values; no normalization)
    s.vertex_normals_vec_xyz = FloatVectorProperty(
        name="Vector XYZ",
        description=f"Raw values stored in '{LAYER_NAME}' (no normalization applied)",
        size=3,
        subtype='XYZ',
        default=(0.0, 0.0, 1.0),
        update=_update_vec_xyz,
    )

def unregister_props():
    del bpy.types.Scene.vertex_normals_vec_xyz
    del bpy.types.Scene.vertex_normals_edit_vec

# ---------- operators ----------

class VERTNORMALS_OT_create_layer(bpy.types.Operator):
    bl_idname = "mesh.vn_create_layer"
    bl_label = "Create Layer"
    bl_description = f"Create per-vertex float vector layer '{LAYER_NAME}'"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _in_edit_vertex_mode(context)

    def execute(self, context):
        _ensure_layer(context.active_object.data)
        self.report({'INFO'}, f"Layer '{LAYER_NAME}' ensured")
        return {'FINISHED'}


class VERTNORMALS_OT_load_from_active(bpy.types.Operator):
    bl_idname = "mesh.vn_load_from_active"
    bl_label = "Load From Active Vertex"
    bl_description = f"Read '{LAYER_NAME}' from active vertex into the editor field"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _in_edit_vertex_mode(context)

    def execute(self, context):
        vec = _read_active_vert_value(context)
        if vec is None:
            self.report({'WARNING'}, f"No active vertex or layer '{LAYER_NAME}' missing")
            return {'CANCELLED'}
        context.scene.vertex_normals_edit_vec = vec
        self.report({'INFO'}, f"Loaded value {tuple(round(c, 6) for c in vec)}")
        return {'FINISHED'}


class VERTNORMALS_OT_write_to_active(bpy.types.Operator):
    bl_idname = "mesh.vn_write_to_active"
    bl_label = "Apply To Active Vertex"
    bl_description = f"Write editor field into '{LAYER_NAME}' on active vertex"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _in_edit_vertex_mode(context)

    def execute(self, context):
        vec = tuple(context.scene.vertex_normals_edit_vec)
        ok = _write_active_vert_value(context, vec)
        if not ok:
            self.report({'WARNING'}, "No active vertex to write to")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Wrote value {tuple(round(c, 6) for c in vec)}")
        return {'FINISHED'}

# ---------- panel ----------

class VIEW3D_PT_vertex_layer_normals(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"              # Item tab
    bl_label = "Vertex Normals (Layer)"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return _in_edit_vertex_mode(context)

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        me = ob.data

        bm, layer = _get_bm_and_layer(me)
        row = layout.row()
        row.label(text=f"Layer: '{LAYER_NAME}' " + ("✓" if layer else "✗"))

        col = layout.column(align=True)
        # 1) direction widget (normalized preview)
        col.prop(context.scene, "vertex_normals_edit_vec", text="Direction")
        # 2) raw numeric vector fields (exact)
        col.prop(context.scene, "vertex_normals_vec_xyz", text="Vector XYZ")

        row = layout.row(align=True)
        row.operator("mesh.vn_load_from_active", icon='EYEDROPPER')
        row.operator("mesh.vn_write_to_active", icon='CHECKMARK')

        if not layer:
            layout.operator("mesh.vn_create_layer", icon='ADD')

# ---------- register ----------

classes = (
    VERTNORMALS_OT_create_layer,
    VERTNORMALS_OT_load_from_active,
    VERTNORMALS_OT_write_to_active,
    VIEW3D_PT_vertex_layer_normals,
)

def register_wld_normal_editor():
    for c in classes:
        bpy.utils.register_class(c)
    register_props()

def unregister_wld_normal_editor():
    unregister_props()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register_wld_normal_editor()