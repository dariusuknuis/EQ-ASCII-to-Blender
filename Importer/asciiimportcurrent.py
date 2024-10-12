import bpy
import bmesh
import mathutils
from mathutils import Quaternion
import os
import sys
import shlex

# Manually set the directory containing your scripts
script_dir = r'C:\Users\dariu\Documents\Quail\Importer'  # Replace with the actual path
print(f"Script directory: {script_dir}")  # Check the path
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Import the modules
from eq_ascii_wld_parser import eq_ascii_parse
from calculations import euler_to_quaternion
from create_polyhedron import create_polyhedron
from material_creator import create_materials  # Import the material creation function
from passable_flag_editor import register_passable_editor
from apply_passable_to_all_meshes import apply_passable_to_all_meshes, apply_passable_to_mesh, create_passable_geometry_node_group, create_passable_material
from create_mesh import create_mesh
from create_armature import create_armature
from assign_mesh_to_armature import assign_mesh_to_armature
from create_animation import create_animation
from create_default_pose import create_default_pose
from create_mesh_and_bounding_shapes import create_bounding_sphere, create_bounding_box

# Path to the root file
file_path = r"C:\Users\dariu\Documents\Quail\global_chr.quail\_root.wce"

# Get the base name for the main object
root_base_name = os.path.splitext(os.path.basename(file_path))[0]

def clear_console():
    if sys.platform.startswith('win'):
        os.system('cls')
    else:
        os.system('clear')

# Call the function to clear the console
clear_console()

# Function to process INCLUDE files
def process_include_file(include_line, file_dir, root_file_path, node_group_cache):
    # Extract the folder name from the INCLUDE line
    folder_name = include_line.split('/')[0].upper()
    
    # Create the path to the INCLUDE file
    include_filepath = os.path.join(file_dir, include_line.strip('"'))
    
    # Extract the root file directory to pass for texture resolution
    root_file_dir = os.path.dirname(root_file_path)
    
    # Parse the INCLUDE file
    meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials = eq_ascii_parse(include_filepath)
    
    # Create materials, passing the root file's directory for texture resolution
    created_materials = create_materials(materials, textures, root_file_dir, node_group_cache)
    
    # Create a new empty object named after the folder
    main_obj = bpy.data.objects.new(folder_name, None)
    bpy.context.collection.objects.link(main_obj)
    
    # Process armature and meshes
    if armature_data and track_definitions:
        armature_tracks = track_definitions['armature_tracks']
        armature_obj, bone_map, cumulative_matrices = create_armature(armature_data, armature_tracks, main_obj)
        
        # Create meshes
        for mesh_data in meshes:
            mesh_obj = create_mesh(mesh_data, main_obj, armature_obj, armature_data, material_palettes, created_materials)
            assign_mesh_to_armature(mesh_obj, armature_obj, armature_data, cumulative_matrices)
        
        # Create default pose based on cumulative matrices
        create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices, folder_name)
        
        # Create animations after parenting
        create_animation(armature_obj, track_definitions, armature_data, model_prefix=folder_name)
    else:
        # If no armature data, just create meshes
        for mesh_data in meshes:
            mesh_obj = create_mesh(mesh_data, main_obj, material_palettes, created_materials)
            
            # Apply PASSABLE geometry node and material immediately after mesh creation
            geo_node_group = create_passable_geometry_node_group()  # Get or create the geometry node group
            passable_mat = create_passable_material()  # Get or create the passable material
            apply_passable_to_mesh(mesh_obj, geo_node_group, passable_mat)
    
    # Create bounding spheres and bounding boxes for meshes with bounding_radius > 0 or valid bounding box data
    for mesh_data in meshes:
        mesh_obj = bpy.data.objects.get(mesh_data['name'])
        
        if mesh_obj:
            # Create bounding sphere if bounding_radius > 0
            bounding_radius = mesh_data.get('bounding_radius', 0)
            if bounding_radius > 0:
                bounding_sphere = create_bounding_sphere(mesh_obj, bounding_radius)
                bounding_sphere.hide_set(True)  # Hide the bounding sphere after creation

            # Create bounding box if valid bounding box data is available
            bounding_box_data = mesh_data.get('bounding_box', None)
            if bounding_box_data and any(v != 0 for pair in bounding_box_data for v in pair):
                bounding_box = create_bounding_box(mesh_obj, bounding_box_data)
                if bounding_box:
                    bounding_box.hide_set(True)  # Optionally, hide the bounding box after creation

    # Parent polyhedron to matching DMSPRITEDEF mesh
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

# Register and apply PASSABLE to all meshes
register_passable_editor()
apply_passable_to_all_meshes()

# Process the root file
process_root_file(file_path)

print(f"Processed INCLUDE files and created respective objects.")
