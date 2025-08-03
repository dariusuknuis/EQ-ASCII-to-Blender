import bpy
from .tools.outdoor_bsp_split import run_outdoor_bsp_split
from .tools.radial_visibility import run_radial_visibility
from .tools.format_world import run_format_world

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
    
class OBJECT_OT_generate_radial_visibility(bpy.types.Operator):
    """Run a radial visibility pass on all R###### empties"""
    bl_idname = "object.generate_radial_visibility"
    bl_label = "Generate Radial Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    search_radius: bpy.props.FloatProperty(
        name="Search Radius",
        description="Radius within which to search for neighboring regions",
        default=2000.0,
        min=0.0,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            run_radial_visibility(self.search_radius)
        except Exception as e:
            self.report({'ERROR'}, f"Radial visibility failed: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}
    
class OBJECT_OT_format_world(bpy.types.Operator):
    bl_idname = "object.format_world"
    bl_label = "Format World"
    bl_description = "Align UVs of region meshes and join into a single terrain mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        result = run_format_world()
        if result == {'FINISHED'}:
            self.report({'INFO'}, "World formatted successfully")
        else:
            self.report({'WARNING'}, "World formatting was cancelled or failed")
        return result

class VIEW3D_PT_EQ_world_tools(bpy.types.Panel):
    bl_label = "EverQuest World Tools"
    bl_idname = "VIEW3D_PT_EQ_world_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        layout.operator(
            "object.generate_outdoor_world",
            text="Generate Outdoor World",
            icon='VIEW3D'
        )
        layout.operator(
            "object.generate_radial_visibility",
            text="Generate Radial Visibility",
            icon='ONIONSKIN_ON'
        )
        layout.operator(
            "object.format_world",
            text="Format World",
            icon='OBJECT_DATA'
        )


classes = (
    OBJECT_OT_generate_outdoor_world,
    OBJECT_OT_generate_radial_visibility,
    OBJECT_OT_format_world,
    VIEW3D_PT_EQ_world_tools,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
