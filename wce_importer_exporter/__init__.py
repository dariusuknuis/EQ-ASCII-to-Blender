# __init__.py
bl_info = {
    "name": "WCE Importer and Exporter",
    "description": "A tool to import EQ WCE files and export model data.",
    "author": "Darius",
    "version": (2, 4, 0),
    "Quail": "dev",
    "blender": (3, 6, 2),
    "location": "View3D > Tool Shelf > WCE Importer/Exporter",
    "category": "Import-Export",
}

import bpy
import os
import re
import sys

script_dir = os.path.dirname(os.path.realpath(__file__))
import_folder = os.path.join(script_dir, "wce_import")
export_folder = os.path.join(script_dir, "wce_export")

if import_folder not in sys.path:
    sys.path.append(import_folder)
if export_folder not in sys.path:
    sys.path.append(export_folder)

from .wce_import import import_wce_file
from .wce_export import master_export  # Assuming 'master_export.py' is in the export folder
from .passable_flag_editor import register_passable_editor, unregister_passable_editor
from .ui_world_tools import register as register_world_tools, unregister as unregister_world_tools

from .update_handler import update_animated_texture_nodes

bpy.types.Scene.export_folder_path = bpy.props.StringProperty(name="Export Folder", default="")

# Importer Preferences
class WCEImporterPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        blender_version = ".".join(map(str, bl_info["blender"]))
        col.label(text=f"Blender Version: {blender_version}")
        quail_version = ".".join(map(str, bl_info["Quail"]))
        col.label(text=f"Compatible Quail Version: {quail_version}")

# Property Group for Model Items
class ModelItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Model Name")
    selected: bpy.props.BoolProperty(name="Select", default=False)
    include_line: bpy.props.StringProperty(name="Include Line")

# Load models from file
def load_models_from_file(filepath):
    models = []
    try:
        with open(filepath, "r") as file:
            for line in file:
                if line.strip().startswith("INCLUDE"):
                    full_include_line = line.split('"')[1].strip()
                    model_name = re.sub(r'[\'" /]', "", line.split()[1])
                    model_name = model_name.replace("_ROOT.WCE", "").replace(".WCE", "")
                    models.append((model_name, full_include_line))  # Save both model name and full include line
    except Exception as e:
        print(f"Failed to load models from file: {e}")
    return models

# Import Dialog Operator
class WCEImportDialogOperator(bpy.types.Operator):
    bl_idname = "import_wce.select_models"
    bl_label = "Asset Importer"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        models = load_models_from_file(self.filepath)
        context.scene.wce_model_list.clear()

        for model_name, include_line in models:
            item = context.scene.wce_model_list.add()
            item.name = model_name
            item.selected = False
            item.include_line = include_line  # Store the full INCLUDE line

        num_items = len(context.scene.wce_model_list)

        # Dynamically adjust width and column count
        base_width = 600  # Minimum width
        max_width = 1000  # Maximum width
        base_columns = 10  # Minimum columns
        max_columns = 25  # Maximum columns

        # Scale width and columns dynamically based on the number of items
        dialog_width = min(max_width, base_width + num_items * 1.5)  # Scale but limit to max_width
        column_count = min(max_columns, max(base_columns, int(num_items / 12)))  # Adjust columns proportionally

        # Store column_count in class so we can use it in draw()
        self.column_count = column_count

        return context.window_manager.invoke_props_dialog(self, width=int(dialog_width))

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select assets to import:")

        row = layout.row()
        col = None  # Initialize column variable

        for i, item in enumerate(context.scene.wce_model_list):
            if i % self.column_count == 0:  # Create a new column every N items
                col = row.column()
            col.prop(item, "selected", text=item.name)

    def execute(self, context):
        selected_models = [item.include_line for item in context.scene.wce_model_list if item.selected]
        for include_line in selected_models:
            import_wce_file.process_include_file(include_line, os.path.dirname(self.filepath), self.filepath, {})
        self.report({'INFO'}, f"Imported models: {', '.join(selected_models)}")
        return {'FINISHED'}

# Operator to Open File Selection for Importing
class ImportWCEFileOperator(bpy.types.Operator):
    bl_idname = "import_wce.file"
    bl_label = "Import WCE File"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        bpy.ops.import_wce.select_models('INVOKE_DEFAULT', filepath=self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# Panel to Display Import Button
class ImportWCEPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_import_wce"
    bl_label = "Import WCE Files"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'WCE Importer/Exporter'

    def draw(self, context):
        layout = self.layout
        layout.operator("import_wce.file")

class SelectExportFolderOperator(bpy.types.Operator):
    bl_idname = "export_wce.select_export_folder"
    bl_label = "Select Export Folder"
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        # Open the file selector for selecting a directory
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # Store the selected directory in the global export folder path
        context.scene.export_folder_path = self.directory
        self.report({'INFO'}, f"Export folder set to: {self.directory}")
        
        # Automatically re-open the WCEExporterDialogOperator
        bpy.ops.export_wce.select_models('INVOKE_DEFAULT')
        return {'FINISHED'}

class WCEExporterDialogOperator(bpy.types.Operator):
    bl_idname = "export_wce.select_models"
    bl_label = "Asset Exporter"

    def invoke(self, context, event):
        print("Invoke called on WCEExporterDialogOperator")
        
        # If export folder isn't set, prompt the user to select it first
        if not context.scene.export_folder_path:
            self.report({'WARNING'}, "Please select an export folder.")
            bpy.ops.export_wce.select_export_folder('INVOKE_DEFAULT')
            return {'FINISHED'}

        context.scene.wce_export_list.clear()

        # Compile the regex to match empties with names like R000001, R000002, etc.
        region_pat = re.compile(r"^R\d{6}$")

        for obj in bpy.data.objects:
            # only empties, not region empties, and not *_BR empties
            if (
                obj.type == 'EMPTY'
                and not region_pat.match(obj.name)
                and not obj.name.endswith("_BR")
            ):
                item = context.scene.wce_export_list.add()
                item.name = obj.name
                item.selected = False

        return context.window_manager.invoke_props_dialog(self, width=800)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select assets to export:")
        column_count = 20
        row = layout.row()
        for i, item in enumerate(context.scene.wce_export_list):
            if i % column_count == 0:
                col = row.column()
            col.prop(item, "selected", text=item.name)

        layout.prop(context.scene, "export_folder_path", text="Export Folder")

    def execute(self, context):
        self.report({'INFO'}, "Starting export process")
        selected_models = [item.name for item in context.scene.wce_export_list if item.selected]
        export_path = context.scene.export_folder_path

        if not export_path:
            self.report({'WARNING'}, "Please select an export folder.")
            return {'CANCELLED'}

        if not selected_models:
            self.report({'WARNING'}, "No models selected for export.")
            return {'CANCELLED'}

        for obj_name in selected_models:
            obj = bpy.data.objects.get(obj_name)
            if obj is None:
                self.report({'WARNING'}, f"Object '{obj_name}' not found.")
                continue

            try:
                # Export the object using the export logic
                print(f"Exporting {obj_name} to {export_path}")
                master_export.export_model(obj_name, export_path)
                print(f"Successfully exported {obj_name}")
            except Exception as e:
                print(f"Failed to export {obj_name}: {str(e)}")
                self.report({'ERROR'}, f"Failed to export {obj_name}: {str(e)}")

        self.report({'INFO'}, f"Exported models: {', '.join(selected_models)}")
        return {'FINISHED'}

# Panel to Display Export Button
class ExportWCEPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_export_wce"
    bl_label = "Export WCE Models"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'WCE Importer/Exporter'

    def draw(self, context):
        layout = self.layout
        layout.operator("export_wce.select_models", text="Export Selected Models")

# Property Group for Export Models
class ModelExportItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Model Name")
    selected: bpy.props.BoolProperty(name="Select", default=False)

# Register and Unregister
def register():
    bpy.utils.register_class(WCEImporterPreferences)
    bpy.utils.register_class(ModelItem)
    bpy.utils.register_class(ModelExportItem)
    bpy.types.Scene.wce_model_list = bpy.props.CollectionProperty(type=ModelItem)
    bpy.types.Scene.wce_export_list = bpy.props.CollectionProperty(type=ModelExportItem)
    bpy.utils.register_class(ImportWCEFileOperator)
    bpy.utils.register_class(WCEImportDialogOperator)
    bpy.utils.register_class(ImportWCEPanel)
    bpy.utils.register_class(SelectExportFolderOperator)
    bpy.utils.register_class(WCEExporterDialogOperator)
    bpy.utils.register_class(ExportWCEPanel)
    register_passable_editor()  # Register the Passable Flag Editor
    register_world_tools()

    if update_animated_texture_nodes not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(update_animated_texture_nodes)

def unregister():
    bpy.utils.unregister_class(WCEImporterPreferences)
    bpy.utils.unregister_class(ModelItem)
    bpy.utils.unregister_class(ModelExportItem)
    del bpy.types.Scene.wce_model_list
    del bpy.types.Scene.wce_export_list
    bpy.utils.unregister_class(ImportWCEFileOperator)
    bpy.utils.unregister_class(WCEImportDialogOperator)
    bpy.utils.unregister_class(ImportWCEPanel)
    bpy.utils.unregister_class(SelectExportFolderOperator)
    bpy.utils.unregister_class(WCEExporterDialogOperator)
    bpy.utils.unregister_class(ExportWCEPanel)
    unregister_passable_editor()  # Unregister the Passable Flag Editor
    unregister_world_tools()

    if update_animated_texture_nodes in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(update_animated_texture_nodes)

if __name__ == "__main__":
    register()


