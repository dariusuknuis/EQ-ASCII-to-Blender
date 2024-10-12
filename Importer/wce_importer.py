bl_info = {
    "name": "WCE Importer",
    "description": "A tool to import WCE files.",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (2, 83, 0),
    "location": "View3D > Tool Shelf > WCE Importer",
    "category": "Import-Export",
}

import bpy
import os
import sys

# Manually set the directory containing your scripts
script_dir = r'C:\Users\dariu\Documents\Quail\Importer'  # Replace with the actual path
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Function that loads external modules only during execution
def load_modules():
    global eq_ascii_parse, create_materials, register_passable_editor, apply_passable_to_all_meshes
    global apply_passable_to_mesh, create_passable_geometry_node_group, create_passable_material
    global create_mesh, create_armature, assign_mesh_to_armature, create_animation
    global create_default_pose, create_polyhedron, create_bounding_sphere, create_bounding_box

    from eq_ascii_wld_parser import eq_ascii_parse
    from material_creator import create_materials
    from passable_flag_editor import register_passable_editor
    from apply_passable_to_all_meshes import apply_passable_to_all_meshes, apply_passable_to_mesh, create_passable_geometry_node_group, create_passable_material
    from create_mesh import create_mesh
    from create_armature import create_armature
    from assign_mesh_to_armature import assign_mesh_to_armature
    from create_animation import create_animation
    from create_default_pose import create_default_pose
    from create_polyhedron import create_polyhedron
    from create_mesh_and_bounding_shapes import create_bounding_sphere, create_bounding_box

# Function to process INCLUDE files
def process_include_file(include_line, file_dir, root_file_path, node_group_cache):
    folder_name = include_line.split('/')[0].upper()
    include_filepath = os.path.join(file_dir, include_line.strip('"'))
    root_file_dir = os.path.dirname(root_file_path)
    meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials = eq_ascii_parse(include_filepath)
    created_materials = create_materials(materials, textures, root_file_dir, node_group_cache)
    main_obj = bpy.data.objects.new(folder_name, None)
    bpy.context.collection.objects.link(main_obj)

    if armature_data and track_definitions:
        armature_tracks = track_definitions['armature_tracks']
        armature_obj, bone_map, cumulative_matrices = create_armature(armature_data, armature_tracks, main_obj)
        for mesh_data in meshes:
            mesh_obj = create_mesh(mesh_data, main_obj, armature_obj, armature_data, material_palettes, created_materials)
            assign_mesh_to_armature(mesh_obj, armature_obj, armature_data, cumulative_matrices)
        create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices, folder_name)
        create_animation(armature_obj, track_definitions, armature_data, model_prefix=folder_name)
    else:
        for mesh_data in meshes:
            mesh_obj = create_mesh(mesh_data, main_obj, None, None, material_palettes, created_materials)
            geo_node_group = create_passable_geometry_node_group()
            passable_mat = create_passable_material()
            apply_passable_to_mesh(mesh_obj, geo_node_group, passable_mat)

    for mesh_data in meshes:
        mesh_obj = bpy.data.objects.get(mesh_data['name'])
        if mesh_obj:
            bounding_radius = mesh_data.get('bounding_radius', 0)
            if bounding_radius > 0:
                bounding_sphere = create_bounding_sphere(mesh_obj, bounding_radius)
                bounding_sphere.hide_set(True)
            bounding_box_data = mesh_data.get('bounding_box', None)
            if bounding_box_data and any(v != 0 for pair in bounding_box_data for v in pair):
                bounding_box = create_bounding_box(mesh_obj, bounding_box_data)
                if bounding_box:
                    bounding_box.hide_set(True)
    
    for polyhedron_data in polyhedrons:
        polyhedron_obj = create_polyhedron(polyhedron_data)
        polyhedron_name = polyhedron_data['name']
        base_name = polyhedron_name.split('.')[0]
        for mesh_data in meshes:
            if mesh_data.get('polyhedron') == base_name:
                mesh_obj = bpy.data.objects.get(mesh_data['name'])
                if mesh_obj:
                    polyhedron_obj.parent = mesh_obj
                    break
    return main_obj

# Function to process the root file and includes
def process_root_file(file_path):
    file_dir = os.path.dirname(file_path)
    
    # Parse the root file
    meshes, armature_data, track_definitions, material_palettes, include_files, polyhedrons, textures, materials = eq_ascii_parse(file_path)

    # Cache for node groups
    node_group_cache = {}

    # Process each INCLUDE file, passing node_group_cache
    for include_line in include_files:
        process_include_file(include_line, file_dir, file_path, node_group_cache)

# Operator for file selection
class ImportWCEFileOperator(bpy.types.Operator):
    bl_idname = "import_wce.file"
    bl_label = "Import WCE File"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        # Load the necessary modules only when executing
        load_modules()
        # Call your root file processing function
        process_root_file(self.filepath)
        self.report({'INFO'}, f"Processed file: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# Panel to access the operator
class ImportWCEPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_import_wce"
    bl_label = "Import WCE Files"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'WCE Importer'

    def draw(self, context):
        layout = self.layout
        layout.operator("import_wce.file")

# Register and unregister classes
def register():
    bpy.utils.register_class(ImportWCEFileOperator)
    bpy.utils.register_class(ImportWCEPanel)

def unregister():
    bpy.utils.unregister_class(ImportWCEFileOperator)
    bpy.utils.unregister_class(ImportWCEPanel)

if __name__ == "__main__":
    register()
