import bpy
import bmesh
from bpy.props import FloatVectorProperty

LAYER_NAME = "vertex_normals"

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

# ---------- properties ----------

def _update_vec(self, context):
    # On change in UI, push to active vertex if possible
    if not _in_edit_vertex_mode(context):
        return
    _write_active_vert_value(context, tuple(context.scene.vertex_normals_edit_vec))

def register_props():
    bpy.types.Scene.vertex_normals_edit_vec = FloatVectorProperty(
        name="vertex_normals",
        description=f"Edit value for '{LAYER_NAME}' on the active vertex",
        size=3,
        subtype='DIRECTION',
        default=(0.0, 0.0, 1.0),
        update=_update_vec,
    )

def unregister_props():
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
        if layer:
            row.label(text=f"Layer: '{LAYER_NAME}' ✓")
        else:
            row.label(text=f"Layer: '{LAYER_NAME}' ✗")

        col = layout.column(align=True)
        col.prop(context.scene, "vertex_normals_edit_vec", text="Value")

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