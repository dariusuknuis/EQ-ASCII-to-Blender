import bpy

class MESH_PT_passable_flag(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Passable Flag Editor"
    bl_idname = "MESH_PT_passable_flag"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    bl_context = "mesh_edit"

    def draw(self, context):
        layout = self.layout
        obj = context.object

        # Ensure the object is a mesh
        if obj and obj.type == 'MESH':
            layout.operator("mesh.set_passable_flag", text="Set Passable").flag_value = 1
            layout.operator("mesh.set_passable_flag", text="Remove Passable").flag_value = 0


class MESH_OT_set_passable_flag(bpy.types.Operator):
    """Set PASSABLE flag for selected faces"""
    bl_idname = "mesh.set_passable_flag"
    bl_label = "Set Passable"
    
    flag_value: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.object
        mesh = obj.data

        # Ensure the mesh is in edit mode and has the PASSABLE attribute
        if "PASSABLE" not in mesh.attributes:
            self.report({'ERROR'}, "PASSABLE attribute not found.")
            return {'CANCELLED'}

        # Switch to object mode to modify data
        bpy.ops.object.mode_set(mode='OBJECT')

        # Access the PASSABLE attribute
        passable_layer = mesh.attributes["PASSABLE"].data

        # Iterate over the selected polygons and modify the PASSABLE flag
        for poly in mesh.polygons:
            if poly.select:
                # Ensure the index is within bounds and update the flag
                try:
                    passable_layer[poly.index].value = int(self.flag_value)  # Explicitly cast to int
                except IndexError:
                    self.report({'ERROR'}, f"Index {poly.index} out of range for PASSABLE attribute.")
                    return {'CANCELLED'}
                except TypeError as e:
                    self.report({'ERROR'}, f"Type error: {str(e)}")
                    return {'CANCELLED'}

        # Switch back to edit mode
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

# Register the classes
def register_passable_editor():
    if not hasattr(bpy.types, "MESH_PT_passable_flag"):
        bpy.utils.register_class(MESH_PT_passable_flag)
    
    if not hasattr(bpy.types, "MESH_OT_set_passable_flag"):
        bpy.utils.register_class(MESH_OT_set_passable_flag)

def unregister_passable_editor():
    if hasattr(bpy.types, "MESH_PT_passable_flag"):
        bpy.utils.unregister_class(MESH_PT_passable_flag)
    
    if hasattr(bpy.types, "MESH_OT_set_passable_flag"):
        bpy.utils.unregister_class(MESH_OT_set_passable_flag)


if __name__ == "__main__":
    register_passable_editor()