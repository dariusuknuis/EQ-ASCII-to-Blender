import bpy
import os
import sys

sys.path.append(r'C:\Users\dariu\Documents\Quail\Exporter')

from dmspritedef2_export import write_dmspritedef
from track_export import export_animation_data

def get_armature(obj):
    """Finds and returns the armature associated with the given object."""
    # Check if the object itself has an armature modifier
    if obj.type == 'MESH' and obj.modifiers:
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object:
                return modifier.object
    
    # Check if the object has a parent that is an armature
    if obj.parent and obj.parent.type == 'ARMATURE':
        return obj.parent

    # Recursively check parent objects for an armature
    parent_obj = obj.parent
    while parent_obj:
        if parent_obj.type == 'ARMATURE':
            return parent_obj
        parent_obj = parent_obj.parent

    # Search for armature in the hierarchy (siblings or children)
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
    for mesh in meshes:
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
export_model('AVI')  # Replace 'AVI' with the name of the object you want to export
