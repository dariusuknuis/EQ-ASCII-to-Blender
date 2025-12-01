import bpy
import bmesh

# ---------------- checkbox backing property ----------------

def _bm_get_layer(me: bpy.types.Mesh):
    """Return (bm, layer) for the PASSABLE face int layer in EDIT mode; create layer if missing."""
    bm = bmesh.from_edit_mesh(me)
    layer = bm.faces.layers.int.get("PASSABLE")
    if layer is None:
        layer = bm.faces.layers.int.new("PASSABLE")
    return bm, layer

def _obj_get_passable_selected(obj):
    """Checkbox is ON only if ALL selected faces have PASSABLE == 1 (in Edit Mode, face-select)."""
    me = getattr(obj, "data", None)
    if not me or obj.type != 'MESH' or obj.mode != 'EDIT':
        return False

    # Must be in face select mode
    sel_mode = bpy.context.tool_settings.mesh_select_mode
    if not sel_mode[2]:
        return False

    bm, layer = _bm_get_layer(me)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return False
    return all(int(f[layer]) == 1 for f in faces)

def _obj_set_passable_selected(obj, value):
    """Set PASSABLE to 1/0 on all selected faces (no mode switching)."""
    me = getattr(obj, "data", None)
    if not me or obj.type != 'MESH' or obj.mode != 'EDIT':
        return

    # Must be in face select mode
    sel_mode = bpy.context.tool_settings.mesh_select_mode
    if not sel_mode[2]:
        return

    bm, layer = _bm_get_layer(me)
    v = 1 if value else 0
    any_selected = False
    for f in bm.faces:
        if f.select:
            f[layer] = v
            any_selected = True

    if any_selected:
        # Write bmesh back to the Mesh datablock so the Mesh attribute stays in sync
        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

def _register_object_prop():
    if not hasattr(bpy.types.Object, "passable_selected"):
        bpy.types.Object.passable_selected = bpy.props.BoolProperty(
            name="Passable (Selected Faces)",
            description="Checked if all selected faces have PASSABLE=1; toggling sets all selected faces to 1/0",
            get=_obj_get_passable_selected,
            set=_obj_set_passable_selected
        )

def _unregister_object_prop():
    if hasattr(bpy.types.Object, "passable_selected"):
        del bpy.types.Object.passable_selected

def _register_scene_flag():
    """Register a single typed checkbox on Scene; no ID-prop mirroring."""
    if not hasattr(bpy.types.Scene, "passable_display_enabled"):
        bpy.types.Scene.passable_display_enabled = bpy.props.BoolProperty(
            name="Passable Display",
            description="Global toggle used by shaders to show passable faces highlighting",
            default=False,
        )

def _unregister_scene_flag():
    if hasattr(bpy.types.Scene, "passable_display_enabled"):
        del bpy.types.Scene.passable_display_enabled
    # (We leave any ID prop on the Scene so user settings persist)


class MESH_OT_toggle_passable_viewport(bpy.types.Operator):
    """Toggle the scene passable display flag (used by materials/shaders)"""
    bl_idname = "mesh.toggle_passable_viewport"
    bl_label = "Toggle Passable Display"

    def execute(self, context):
        scene = context.scene
        # Ensure the typed prop exists
        if not hasattr(bpy.types.Scene, "passable_display_enabled"):
            _register_scene_flag()
        # Flip it
        scene.passable_display_enabled = not scene.passable_display_enabled
        state = "ON" if scene.passable_display_enabled else "OFF"
        self.report({'INFO'}, f"Passable display: {state}")
        return {'FINISHED'}


# --- NEW: Tool-tab panel that shows in Object *and* Edit modes ---
class MESH_PT_passable_flag(bpy.types.Panel):
    """Tool N-panel: global Passable Display toggle (always), and per-face checkbox in Edit/Face mode."""
    bl_label = "Passable Flag Editor"
    bl_idname = "MESH_PT_passable_flag"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    # NOTE: no bl_context here → panel shows in Object and Edit modes

    @classmethod
    def poll(cls, context):
        # Show the panel whenever we're in the 3D View; no mesh required for the global toggle
        return context.area and context.area.type == 'VIEW_3D'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object

        # --- Always available (Object or Edit mode): global toggle + button ---
        row = layout.row(align=True)
        row.prop(scene, "passable_display_enabled", text="Passable Display")
        row.operator("mesh.toggle_passable_viewport", text="", icon='RESTRICT_VIEW_OFF')

        # --- Per-face tools only in Edit Face mode ---
        if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
            sel_mode = context.tool_settings.mesh_select_mode
            if sel_mode[2]:  # face mode
                if "PASSABLE" not in obj.data.attributes:
                    layout.operator("mesh.ensure_passable_attribute", icon='ADD')
                else:
                    layout.prop(obj, "passable_selected", text="Passable (Selected Faces)")


class SCENE_PT_passable_display(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_label = "Passable Display"

    def draw(self, context):
        layout = self.layout
        sc = context.scene

        # Main checkbox drives the typed property
        layout.prop(sc, "passable_display_enabled", text="Passable Display")

        # (Optional) Show/seed ID custom property for convenience if you want to wire it manually
        if "PassableDisplay" not in sc:
            try:
                sc["PassableDisplay"] = bool(sc.passable_display_enabled)
            except Exception:
                pass
        if "PassableDisplay" in sc:
            layout.prop(sc, '["PassableDisplay"]', text="(ID) PassableDisplay")


class VIEW3D_PT_item_passable(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"
    bl_label = "Passable"
    bl_context = "mesh_edit"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not (obj and obj.type == 'MESH'):
            return False
        if obj.mode != 'EDIT':
            return False
        sel_mode = context.tool_settings.mesh_select_mode
        return bool(sel_mode[2])  # Face mode only

    def draw(self, context):
        layout = self.layout
        obj = context.object
        me = obj.data

        # Button to create attribute if missing
        if "PASSABLE" not in me.attributes:
            layout.operator("mesh.ensure_passable_attribute", icon='ADD')
            return

        # Simple checkbox only
        layout.prop(obj, "passable_selected", text="Passable")


# ---------------- registration -------------------------

_classes = (
    MESH_PT_passable_flag,       # new tool-tab panel
    SCENE_PT_passable_display,
    MESH_OT_toggle_passable_viewport,
    VIEW3D_PT_item_passable,
)

def register_passable_editor():
    for c in _classes:
        if not hasattr(bpy.types, c.__name__):
            bpy.utils.register_class(c)
    _register_object_prop()
    _register_scene_flag()

def unregister_passable_editor():
    for c in reversed(_classes):
        if hasattr(bpy.types, c.__name__):
            bpy.utils.unregister_class(c)
    _unregister_object_prop()
    _unregister_scene_flag()

if __name__ == "__main__":
    register_passable_editor()
