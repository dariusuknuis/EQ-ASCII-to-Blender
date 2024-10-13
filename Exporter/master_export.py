import bpy
import os
import sys

# Add the path where everquestize_mesh.py is located
sys.path.append(r'C:\Users\dariu\Documents\Quail\Exporter')

from dmspritedef2_export import write_dmspritedef
from track_export import export_animation_data
from everquestize_mesh import split_vertices_by_uv, reindex_vertices_by_vertex_group

def get_armature(obj):
    """Finds and returns the armature associated with the given object."""
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

# Call the mesh export and POS animation
def export_mesh_and_pos_animation(obj, output_path):
    mesh_output_file = os.path.join(output_path, f"{obj.name.lower()}.wce")
    with open(mesh_output_file, 'w') as file:
        # Call the mesh export function
        export_dmspritedef(obj, file)
        
        # Try to find the armature for POS action export
        armature = get_armature(obj)
        if armature:
            export_pos_animation(armature, file)
        else:
            print("No armature found for the mesh object!")

    print(f"Mesh and POS animation data exported to {mesh_output_file}")


# Call the rest of the animation export
def export_animation(obj, output_path):
    ani_output_file = os.path.join(output_path, f"{obj.name.lower()}_ani.wce")
    with open(ani_output_file, 'w') as file:
        armature = get_armature(obj)
        if armature:
            export_track_animation(armature, file)
        else:
            print("No armature found for the mesh object!")

    print(f"Remaining animation data exported to {ani_output_file}")


def export_dmspritedef(obj, file):
    print("Running mesh export...")
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    meshes = find_all_child_meshes(obj)
    
    # Run everquestize_mesh.py functions on all meshes before export
    for mesh in meshes:
        split_vertices_by_uv(mesh)
        reindex_vertices_by_vertex_group(mesh)
        write_dmspritedef(mesh, file)


def export_pos_animation(armature, file):
    print("Running POS action export...")
    export_animation_data(armature, file, include_pos=True)


def export_track_animation(armature, file):
    print("Running track action export...")
    export_animation_data(armature, file, include_pos=False)


def find_all_child_meshes(parent_obj):
    meshes = []
    for child in parent_obj.children:
        if child.type == 'MESH' and child.name.endswith("_DMSPRITEDEF"):
            meshes.append(child)
        meshes.extend(find_all_child_meshes(child))  # Recursive search
    return meshes


def export_model(obj_name):
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        print(f"Object '{obj_name}' not found!")
        return
    
    output_path = r"C:\Users\dariu\Documents\Quail\Exporter"  # Update the path to your preferred location

    # Step 1: Export mesh and POS animation
    export_mesh_and_pos_animation(obj, output_path)

    # Step 2: Export remaining animations
    export_animation(obj, output_path)


# Example usage:
export_model('ELF') #empty object containing models and armature here