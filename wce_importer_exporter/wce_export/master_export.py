import bpy
import os
import sys
import re

# Add the path where everquestize_mesh.py is located
sys.path.append(r'C:\Users\dariu\Documents\Quail\Exporter')

from export_dm_sprite_def_2 import write_dm_sprite_def
from export_dm_track_def_2 import write_dm_track_def_2
from export_hierarchical_sprite_def import write_hierarchical_sprite_def
from export_track import export_animation_data
from export_actor_def import write_actor_def
from export_material import write_materials_and_sprites
from export_world_tree import export_world_tree
from export_regions import export_regions
from export_ambient_light import export_ambient_light
from export_zones import export_zones
from export_variation_material import write_variation_sprites_and_materials
from everquestize_mesh import split_vertices_by_uv, reindex_vertices_and_faces, update_vertex_material_indices

def get_armature(obj):
    """Finds and returns the armature associated with the given object."""
    if obj.type == 'EMPTY':
        # Check children for armatures
        for child in obj.children:
            if child.type == 'ARMATURE':
                return child

    if obj.type == 'MESH' and obj.modifiers:
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object:
                return modifier.object

    if obj.parent and obj.parent.type == 'ARMATURE':
        return obj.parent

    parent_obj = obj.parent
    while parent_obj:
        if parent_obj.type == 'ARMATURE':
            return parent_obj
        parent_obj = parent_obj.parent

    for sibling in obj.parent.children if obj.parent else bpy.data.objects:
        if sibling.type == 'ARMATURE':
            return sibling

    return None

def sanitize_name(name):
    """Removes '_ACTORDEF' suffix from the object name if present."""
    return name.replace("_ACTORDEF", "").lower()

# Call the mesh export and POS animation
def export_mesh_and_pos_animation(obj, output_path):
    mesh_output_file = os.path.join(output_path, f"{sanitize_name(obj.name)}.wce")
    with open(mesh_output_file, 'w') as file:

        # Assuming `empty_obj` is the main object
        export_materials(obj, file)

        # Call the mesh export function
        export_dm_sprite_def(obj, file)

        # Call the DMTRACKDEF2 export for each DMSPRITEDEF mesh with shape keys
        meshes = find_all_child_meshes(obj)
        for mesh in meshes:
            if mesh.data.shape_keys and len(mesh.data.shape_keys.key_blocks) > 1:
                write_dm_track_def_2(mesh, file)
        
        # Try to find the armature for POS action export
        armature = get_armature(obj)
        if armature:
            export_animation_data(armature, file, action_filter="POS")
            write_hierarchical_sprite_def(armature, file)
        else:
            print("No armature found for the mesh object!")

        # Call the ACTORDEF export if the object has "_ACTORDEF" in its name
        if obj.name.endswith("_ACTORDEF"):
            write_actor_def(obj, file)

    print(f"Mesh and POS animation data exported to {mesh_output_file}")


# Call the rest of the animation export
def export_animation(obj, output_path):
    armature = get_armature(obj)
    if armature:
        # Export each non-POS action separately
        for nla_track in armature.animation_data.nla_tracks:
            for strip in nla_track.strips:
                action = strip.action
                if action and not action.name.startswith("POS"):
                    ani_output_file = os.path.join(output_path, f"{sanitize_name(action.name)}.wce")
                    with open(ani_output_file, 'w') as file:
                        export_animation_data(armature, file, action_filter=action.name)
    else:
        print(f"No armature found for object {obj.name}. Skipping animation export.")

def export_materials(obj, file):
    print("Running material export...")
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Create fresh tracking sets
    written_sprites = set()
    written_materials = set()
    written_palettes = set()

    meshes = find_all_child_meshes(obj)
    for mesh in meshes:
        # Pass fresh sets to avoid retained data between runs
        write_materials_and_sprites(mesh, file, written_sprites, written_materials, written_palettes)

    # Print the materials that were written out
    print("Written materials:", written_materials)

    # After writing the materials, identify and write out variation materials
    write_variation_materials(file, written_materials, written_sprites)


def write_variation_materials(file, written_materials, written_sprites):
    # Function to create a regex pattern for each base material
    def create_pattern(base_name):
        return re.compile(rf"^{base_name[:5]}\w*_MDF$")

    # Set to hold the names of all written variation materials to avoid duplicates
    written_variation_materials = set()

    print("\nSearching for variation materials:")
    found_matches = False

    for base_name in written_materials:
        pattern = create_pattern(base_name)  # Generate pattern based on current written material
        print(f"\nLooking for variations of: {base_name}")

        for mat in bpy.data.materials:
            mat_name = mat.name
            match = pattern.match(mat_name)

            if match and mat_name != base_name and mat_name not in written_variation_materials:
                print(f"Matched variation material: {mat_name}")
                found_matches = True
                written_variation_materials.add(mat_name)

                # Write SIMPLESPRITEDEF and MATERIALDEFINITION for this variation material
                write_variation_sprites_and_materials(mat, file, written_sprites, written_materials)

    if not found_matches:
        print("No variation materials matched the pattern.")

def export_dm_sprite_def(obj, file):
    print("Running mesh export...")
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    meshes = find_all_child_meshes(obj)
    
    # Run everquestize_mesh.py functions on all meshes before export
    for mesh in meshes:
        # DEBUG: list any new‑style Color attributes
        print(f"[DEBUG] Mesh {mesh.name}: color_attributes = {list(mesh.data.color_attributes.keys())}")
        # DEBUG: list any legacy vertex_colors layers
        print(f"[DEBUG] Mesh {mesh.name}: vertex_colors = {[vcol.name for vcol in mesh.data.vertex_colors]}")
        if mesh.data.uv_layers:
            split_vertices_by_uv(mesh)
        update_vertex_material_indices(mesh)
        reindex_vertices_and_faces(mesh)
        write_dm_sprite_def(mesh, file)

# def export_pos_animation(armature, file):
#     print("Running POS action export...")
#     export_animation_data(armature, file, include_pos=True)


# def export_track_animation(armature, file):
#     print("Running track action export...")
#     export_animation_data(armature, file, include_pos=False)

def find_all_child_meshes(parent_obj):
    meshes = []
    for child in parent_obj.children:
        if child.type == 'MESH' and child.name.endswith("_DMSPRITEDEF"):
            meshes.append(child)
        meshes.extend(find_all_child_meshes(child))  # Recursive search
    return meshes

def export_model(obj_name, output_path):
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        print(f"[DEBUG] Object '{obj_name}' not found!")
        return

    print(f"[DEBUG] Starting export for object: {obj_name}")
    print(f"[DEBUG] Output path: {output_path}")

    try:
        export_mesh_and_pos_animation(obj, output_path)
        export_animation(obj, output_path)

        export_ambient_light(obj, output_path)
        export_world_tree(obj, output_path)
        export_regions(obj, output_path)
        export_zones(obj, output_path)

        print(f"[DEBUG] Successfully exported: {obj_name}")
    except Exception as e:
        print(f"[DEBUG] Failed to export {obj_name}: {e}")



# Example usage:
# export_model('ELF_ACTORDEF') #empty object containing models and armature here