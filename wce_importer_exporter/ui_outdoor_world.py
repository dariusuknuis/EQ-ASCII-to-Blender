import bpy
from .outdoor_bsp_split import run_outdoor_bsp_split

class OBJECT_OT_generate_outdoor_world(bpy.types.Operator):
    """Split mesh into BSP regions & submeshes (Outdoor world)"""
    bl_idname = "object.generate_outdoor_world"
    bl_label = "Generate Outdoor World"
    bl_options = {'REGISTER', 'UNDO'}

    target_size: bpy.props.FloatProperty(
        name="Target Size",
        description="Maximum leaf size before zone splits",
        default=300.0,
        min=0.01,
    )

    def invoke(self, context, event):
        # show dialog to enter target_size
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            run_outdoor_bsp_split(self.target_size)
        except Exception as e:
            self.report({'ERROR'}, f"BSP split failed: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


class VIEW3D_PT_outdoor_world(bpy.types.Panel):
    bl_label = "Outdoor World"
    bl_idname = "VIEW3D_PT_outdoor_world"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_context = "objectmode"

    def draw(self, context):
        self.layout.operator(
            OBJECT_OT_generate_outdoor_world.bl_idname,
            text="Generate Outdoor World",
            icon='WORLD'
        )


classes = (
    OBJECT_OT_generate_outdoor_world,
    VIEW3D_PT_outdoor_world,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
