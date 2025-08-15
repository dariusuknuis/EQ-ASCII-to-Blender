import bpy
import mathutils
from .create_mesh_and_bounding_shapes import create_bounding_sphere

def create_armature(armature_data, armature_tracks, parent_obj):
    bpy.context.view_layer.objects.active = parent_obj

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_pattern(pattern=parent_obj.name)

    bpy.ops.object.armature_add(enter_editmode=True)
    armature_obj = bpy.context.object
    armature_obj.name = armature_data['name']
    armature = armature_obj.data
    armature.name = armature_data['name']
    armature_obj.parent = parent_obj

    armature.edit_bones.remove(armature.edit_bones[0])

    # Extract the bounding_radius and calculate the tail length
    bounding_radius = armature_data.get('bounding_radius', 1.0)  # Default to 1.0 if bounding_radius is not provided
    tail_length = round(bounding_radius / 10, 2)  # Calculate tail length based on bounding_radius

    bone_map = {}
    cumulative_matrices = {}
    for index, bone in enumerate(armature_data['bones']):
        bone_name = bone['name']
        bone_bpy = armature.edit_bones.new(bone_name)
        # Set the head of the bone at (0, 0, 0)
        bone_bpy.head = (0, 0, 0)
        # Set the tail Y position relative to the bounding_radius
        bone_bpy.tail = (0, tail_length, 0)

        bone_map[index] = bone_bpy

    bpy.ops.object.mode_set(mode='EDIT')

    for parent_index, child_indices in armature_data['relationships']:
        parent_bone = bone_map.get(parent_index)
        if not parent_bone:
            continue
        for child_index in child_indices:
            child_bone = bone_map.get(child_index)
            if child_bone:
                child_bone.parent = parent_bone

                cumulative_matrices[child_bone.name] = child_bone.matrix

        if not parent_bone.children:
            parent_bone.tail = parent_bone.head + mathutils.Vector((0, tail_length, 0))

    bpy.ops.object.mode_set(mode='OBJECT')

    # Assign the 'track' property to each pose bone
    for bone in armature_data['bones']:
        bone_name = bone['name']
        bone_track = bone.get('track', None)

        if bone_track:
            pose_bone = armature_obj.pose.bones.get(bone_name)
            if pose_bone:
                pose_bone["track"] = bone_track  # Assign track as custom property

    # Set armature custom properties based on flags
    armature_obj["HEXTWOHUNDREDFLAG"] = bool(armature_data.get("hextwohundredflag", 0))
    armature_obj["HEXTWENTYTHOUSANDFLAG"] = bool(armature_data.get("hextwentythousandflag", 0))

    # Add the "POLYHEDRON" custom property
    polyhedron_value = armature_data.get("polyhedron", "")
    armature_obj["POLYHEDRON"] = polyhedron_value  # Store as blank if polyhedron_value is ""

    # Adjust origin by the center_offset value only if it exists and is not NULL
    center_offset_data = armature_data.get('center_offset')
    if center_offset_data:
        center_offset = mathutils.Vector(center_offset_data)
        armature_obj.location = center_offset
        #print(f"Applied center_offset: {center_offset}")
    else:
        print("No valid center_offset found, using default location.")

    # Call the existing create_bounding_sphere function
    if bounding_radius > 0:
        bounding_sphere = create_bounding_sphere(armature_obj, bounding_radius)
        bounding_sphere.hide_set(True)
    
    return armature_obj, bone_map, cumulative_matrices