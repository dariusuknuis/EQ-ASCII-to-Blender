import bpy
import bmesh
import mathutils
from mathutils import Quaternion
import os
import sys

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

# Path to the text file
file_path = r"C:\Users\dariu\Documents\Quail\chequip.new.quail\pre.wce"

# Get the base name for the main object
base_name = os.path.splitext(os.path.basename(file_path))[0]
prefix = base_name.upper()

def clear_console():
    if sys.platform.startswith('win'):
        os.system('cls')
    else:
        os.system('clear')

# Call the function to clear the console
clear_console()

# Read 3D data from file using eq_ascii_wld_parser
meshes, armature_data, track_definitions, material_palettes, include_files, polyhedrons, textures, materials = eq_ascii_parse(file_path)

# Cache for node groups
node_group_cache = {}

# Create materials using the separate script
created_materials = create_materials(materials, textures, file_path, node_group_cache)

# Create polyhedron objects
polyhedron_objects = {}

for polyhedron_data in polyhedrons:
    polyhedron_obj = create_polyhedron(polyhedron_data)
    polyhedron_objects[polyhedron_data['name']] = polyhedron_obj

# Create a new main object
main_obj = bpy.data.objects.new(base_name, None)
bpy.context.collection.objects.link(main_obj)

def create_mesh(mesh_data, parent_obj, armature_obj=None):
    #print(f"Creating mesh '{mesh_data['name']}'")

    mesh = bpy.data.meshes.new(mesh_data['name'])
    obj = bpy.data.objects.new(mesh_data['name'], mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent_obj

    # Adjust origin by the center_offset value
    center_offset = mathutils.Vector(mesh_data.get('center_offset', [0.0, 0.0, 0.0]))
    obj.location = center_offset

    # Extract only the first three vertices for each face
    faces_for_creation = [face[:3] for face in mesh_data['faces']]

    mesh.from_pydata(mesh_data['vertices'], [], faces_for_creation)
    mesh.update()

    # == UV mapping ==
    if 'uvs' in mesh_data and mesh_data['uvs']:  # Check if UV data is present
        uvlayer = mesh.uv_layers.new(name=mesh_data['name'] + "_uv")
        for i, triangle in enumerate(mesh.polygons):
            vertices = list(triangle.vertices)
            for j, vertex in enumerate(vertices):
                uvlayer.data[triangle.loop_indices[j]].uv = (mesh_data['uvs'][vertex][0], mesh_data['uvs'][vertex][1] - 1)

    # == Apply Custom Normals ==
    if 'normals' in mesh_data and len(mesh_data['normals']) == len(mesh_data['vertices']):
        mesh.use_auto_smooth = True  # Enable auto smooth for custom normals
        mesh.normals_split_custom_set_from_vertices(mesh_data['normals'])

    # Create vertex groups if armature data is available
    if armature_obj and 'vertex_groups' in mesh_data and mesh_data['vertex_groups']:
        for vg_start, vg_end, bone_index in mesh_data['vertex_groups']:
            bone_name = armature_data['bones'][bone_index]['name']
            group = obj.vertex_groups.new(name=bone_name)
            group.add(range(vg_start, vg_end), 1.0, 'ADD')
        
    # Create materials only if face materials exist
    if 'face_materials' in mesh_data and mesh_data['face_materials']:
        palette_name = mesh_data.get('material_palette', None)
        if palette_name:
            if palette_name not in material_palettes:
                print(f"Error: Material palette '{palette_name}' not found for mesh '{mesh_data['name']}'")
                return None

            materials = material_palettes[palette_name]
            for mat_name in materials:
                if mat_name in created_materials:
                    obj.data.materials.append(created_materials[mat_name])
                else:
                    print(f"Warning: Material '{mat_name}' not found in created materials")
        else:
            print(f"Warning: No material palette found for mesh '{mesh_data['name']}'")
            materials = []

        # Assign materials to faces
        face_index = 0
        for face_data in mesh_data['face_materials']:
            start_face, end_face, material_index = face_data[:3]
            num_faces = end_face - start_face

            if material_index < len(materials):
                material_name = materials[material_index]
                material_list_index = obj.data.materials.find(material_name)
                if material_list_index == -1:
                    material_list_index = len(obj.data.materials) - 1

                for i in range(num_faces):
                    if face_index < len(obj.data.polygons):
                        obj.data.polygons[face_index].material_index = material_list_index
                        face_index += 1

                #print(f"Material index: {material_list_index}, Material name: {material_name}")
            else:
                print(f"Material index: {material_index}, Material name: Unknown")

    return obj

# Function to create an armature from given data
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

    # Adjust origin by the center_offset value only if it exists and is not NULL
    center_offset_data = armature_data.get('center_offset')
    if center_offset_data:
        center_offset = mathutils.Vector(center_offset_data)
        armature_obj.location = center_offset
        print(f"Applied center_offset: {center_offset}")
    else:
        print("No valid center_offset found, using default location.")

    return armature_obj, bone_map, cumulative_matrices

# Function to handle parenting and modifiers for meshes
def assign_mesh_to_armature(mesh_obj, armature_obj, armature_data, cumulative_matrices):
    mesh_name = mesh_obj.name

    # Check if mesh belongs to attached skins
    for skin_data in armature_data.get('attached_skins', []):
        if skin_data['sprite'] == mesh_name:
            mesh_obj.parent = armature_obj
            mesh_obj.modifiers.new(name="Armature", type='ARMATURE').object = armature_obj
            mesh_obj["LINKSKINUPDATESTODAGINDEX"] = skin_data['link_skin_updates_to_dag_index']
            print(f"Mesh '{mesh_name}' parented to armature and assigned LINKSKINUPDATESTODAGINDEX: {skin_data['link_skin_updates_to_dag_index']}")
            return  # Mesh is assigned, no need to check further

    # Check if mesh belongs to a bone's sprite
    for bone in armature_data['bones']:
        if bone.get('sprite') == mesh_name:
            bone_obj = armature_obj.pose.bones.get(bone['name'])
            if bone_obj:
                mesh_obj.parent = armature_obj
                mesh_obj.parent_bone = bone_obj.name
                mesh_obj.parent_type = 'BONE'
                # Adjust the origin by subtracting the Y-length of the bone tail
                bone_tail_y = bone_obj.tail.y
                mesh_obj.location.y -= bone_tail_y
                #print(f"Mesh '{mesh_name}' parented to bone '{bone['name']}' with origin adjusted by tail length: {tail_length}")
                return  # Mesh is assigned, no need to check further

# Function to create and apply animations
def create_animation(armature_obj, track_definitions, armature_data, model_prefix=prefix):
    # Get the scene's frame rate
    frame_rate = bpy.context.scene.render.fps

    # Group tracks by their animation key and model prefix
    animations_by_key = {}

    for animation_name, animation_data in track_definitions['animations'].items():
        animation_key = animation_data.get('animation_prefix', animation_name[:3]).strip()
        
        action_name = f"{animation_key}_{model_prefix.strip()}"

        if action_name not in animations_by_key:
            animations_by_key[action_name] = []
        
        animations_by_key[action_name].append(animation_data)

    # Create actions for each animation key
    for action_name, tracks in animations_by_key.items():
        action = bpy.data.actions.new(name=action_name)
        
        # Assign the action to the armature to ensure it has a user
        if armature_obj.animation_data is None:
            armature_obj.animation_data_create()
        
        # Set the created action to be the active action for the armature
        armature_obj.animation_data.action = action

        # Optional: Mark the action as having a "fake user" to keep it even if unassigned
        action.use_fake_user = True  # This ensures the action will not be deleted even if it’s not actively used

        fcurves = {}

        # Go through each track in the animation data
        for track_data in tracks:
            track = track_data['definition']
            track_instance = track_data['instance']
            track_instance_name = track_instance['name']
            sleep = track_instance.get('sleep', None)

            # Determine frames_per_sleep only if sleep is not None
            frames_per_sleep = 1
            if sleep is not None:
                frames_per_sleep = (sleep / 1000) * frame_rate

            current_frame = 1

            # Strip the animation prefix and '_TRACK' from the track instance name
            stripped_track_instance_name = track_instance_name[len(animation_key):].replace('_TRACK', '')

            # Identify which bone this track belongs to
            bone_name = None
            for bone in armature_obj.pose.bones:
                stripped_bone_name = bone.name.replace('_DAG', '')

                if stripped_bone_name == stripped_track_instance_name:
                    bone_name = bone.name
                    break
                elif bone.name.replace('_ANIDAG', '') == stripped_track_instance_name:
                    bone_name = bone.name
                    break

            if not bone_name:
                # Create new animation-only bone with "_ANIDAG"
                bpy.ops.object.mode_set(mode='EDIT')
                parent_bone_name = stripped_track_instance_name[:-1] + '_DAG'
                parent_bone = armature_obj.data.edit_bones.get(parent_bone_name)

                if parent_bone:
                    anim_bone_name = f"{stripped_track_instance_name}_ANIDAG"
                    anim_bone = armature_obj.data.edit_bones.new(anim_bone_name)
                    anim_bone.head = parent_bone.tail
                    anim_bone.tail = anim_bone.head + mathutils.Vector((0, 0.1, 0))
                    anim_bone.parent = parent_bone
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # After creating the animation bone, retry matching
                    for bone in armature_obj.pose.bones:
                        stripped_bone_name = bone.name.replace('_ANIDAG', '')
                        if stripped_bone_name == stripped_track_instance_name:
                            bone_name = bone.name
                            break

            if bone_name:
                if bone_name not in fcurves:
                    fcurves[bone_name] = {
                        'location': [],
                        'rotation_quaternion': [],
                        'scale': []
                    }

                    for i in range(3):
                        fcurves[bone_name]['location'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].location', index=i))
                        fcurves[bone_name]['scale'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].scale', index=i))

                    for i in range(4):
                        fcurves[bone_name]['rotation_quaternion'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].rotation_quaternion', index=i))

                for frame_index, frame in enumerate(track['frames']):
                    location = frame.get('translation', [0, 0, 0])
                    frame_rotation = mathutils.Quaternion(frame.get('rotation', [1, 0, 0, 0]))
                    xyz_scale = track.get('xyz_scale', 256)
                    scale_factor = xyz_scale / 256.0

                    scale_matrix = mathutils.Matrix.Scale(scale_factor, 4)
                    rotation_matrix = frame_rotation.to_matrix().to_4x4()
                    translation_matrix = mathutils.Matrix.Translation(location)

                    bone_matrix = translation_matrix @ rotation_matrix @ scale_matrix

                    translation = bone_matrix.to_translation()
                    rotation = bone_matrix.to_quaternion()
                    scale = [scale_factor] * 3

                    for i, value in enumerate(translation):
                        fcurve = fcurves[bone_name]['location'][i]
                        kf = fcurve.keyframe_points.insert(current_frame, value)
                        kf.interpolation = 'LINEAR'

                    for i, value in enumerate(rotation):
                        fcurve = fcurves[bone_name]['rotation_quaternion'][i]
                        kf = fcurve.keyframe_points.insert(current_frame, value)
                        kf.interpolation = 'LINEAR'

                    for i, value in enumerate(scale):
                        fcurve = fcurves[bone_name]['scale'][i]
                        kf = fcurve.keyframe_points.insert(current_frame, value)
                        kf.interpolation = 'LINEAR'

                    current_frame += frames_per_sleep

    print("Animation creation complete")

# Function to create a default pose
def create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices):
    # Create a default pose action
    action_name = f"POS_{prefix}"
    action = bpy.data.actions.new(name=action_name)

    # Ensure the armature has animation data and assign the action
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()

    armature_obj.animation_data.action = action  # Assign the action to the armature

    # Optional: Mark the action as having a "fake user" to keep it even if not actively used
    action.use_fake_user = True  # This ensures the action will not be deleted

    fcurves = {}  # Initialize the fcurves dictionary

    # Loop through the bones in the armature and create default pose keyframes
    for bone_name, bone in armature_obj.pose.bones.items():
        stripped_bone_name = bone_name.replace('_DAG', '')
        corresponding_bone = next((b for b in armature_data['bones'] if b['name'] == bone_name), None)

        if corresponding_bone:
            track_name = corresponding_bone['track']
            track_def = track_definitions['armature_tracks'][track_name]['definition']
            initial_transform = track_def['frames'][0]

            armature_translation = initial_transform.get('translation', [0, 0, 0])
            armature_rotation = initial_transform.get('rotation', Quaternion((1, 0, 0, 0)))
            xyz_scale = track_def.get('xyz_scale', 256)
            scale_factor = xyz_scale / 256.0

            # Create a matrix that applies the cumulative matrix, translation, rotation, and scale
            scale_matrix = mathutils.Matrix.Scale(scale_factor, 4)
            rotation_matrix = armature_rotation.to_matrix().to_4x4()
            translation_matrix = mathutils.Matrix.Translation(armature_translation)

            # Combine the matrices in the correct order: Translation * Rotation * Scale * Cumulative Matrix
            bone_matrix = translation_matrix @ rotation_matrix @ scale_matrix @ cumulative_matrices.get(bone_name, mathutils.Matrix.Identity(4))

            # Initialize fcurves for location, rotation, and scale
            if bone_name not in fcurves:
                fcurves[bone_name] = {
                    'location': [],
                    'rotation_quaternion': [],
                    'scale': []
                }

                # Create fcurves for location, rotation, and scale
                for i in range(3):  # Location and Scale have 3 components: X, Y, Z
                    fcurves[bone_name]['location'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].location', index=i))
                    fcurves[bone_name]['scale'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].scale', index=i))

                for i in range(4):  # Rotation quaternion has 4 components: W, X, Y, Z
                    fcurves[bone_name]['rotation_quaternion'].append(action.fcurves.new(data_path=f'pose.bones["{bone_name}"].rotation_quaternion', index=i))

            # Extract translation, rotation, and scale from the bone matrix
            translation = bone_matrix.to_translation()
            rotation = bone_matrix.to_quaternion()
            scale = [scale_factor] * 3  # Apply the scaling factor uniformly on all axes

            # Insert location keyframes
            for i, value in enumerate(translation):
                fcurve = fcurves[bone_name]['location'][i]
                kf = fcurve.keyframe_points.insert(1, value)
                kf.interpolation = 'LINEAR'

            # Insert rotation keyframes
            for i, value in enumerate(rotation):
                fcurve = fcurves[bone_name]['rotation_quaternion'][i]
                kf = fcurve.keyframe_points.insert(1, value)
                kf.interpolation = 'LINEAR'

            # Insert scale keyframes
            for i, value in enumerate(scale):
                fcurve = fcurves[bone_name]['scale'][i]
                kf = fcurve.keyframe_points.insert(1, value)
                kf.interpolation = 'LINEAR'

    print(f"Created default pose action '{action_name}'")

# After armature creation, generate the default pose
if armature_data and track_definitions:
    armature_tracks = track_definitions['armature_tracks']
    armature_obj, bone_map, cumulative_matrices = create_armature(armature_data, armature_tracks, main_obj)
    
    # Create meshes
    for mesh_data in meshes:
        mesh_obj = create_mesh(mesh_data, main_obj, armature_obj)
        assign_mesh_to_armature(mesh_obj, armature_obj, armature_data, cumulative_matrices)

    # Create default pose based on the cumulative matrices
    create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices)

    # Create animations after parenting
    create_animation(armature_obj, track_definitions, armature_data)
else:
    # If no armature data, just create meshes
    for mesh_data in meshes:
        mesh_obj = create_mesh(mesh_data, main_obj)

# Parent polyhedron to matching DMSPRITEDEF mesh
for polyhedron_name, polyhedron_obj in polyhedron_objects.items():
    actual_polyhedron_name = polyhedron_obj.name  # Access the actual Blender name of the polyhedron object
    base_name = actual_polyhedron_name.split('.')[0]  # Get the base name without the suffix
    appendix = actual_polyhedron_name.split('.')[-1] if '.' in actual_polyhedron_name else ''
    
    print(f"Polyhedron Name: '{actual_polyhedron_name}', Base Name: '{base_name}', Appendix: '{appendix}'")
    
    for mesh_data in meshes:
        if mesh_data.get('polyhedron') == base_name:
            # Look for the mesh object with the same appendix
            mesh_name_with_appendix = f"{mesh_data['name']}.{appendix}" if appendix else mesh_data['name']
            mesh_obj = bpy.data.objects.get(mesh_name_with_appendix)
            if mesh_obj:
                print(f"Matching mesh found: {mesh_obj.name} for polyhedron: {actual_polyhedron_name}")
                polyhedron_obj.parent = mesh_obj
                break  # Stop searching once the correct parent is found

print("Created object '{}' with {} meshes and armature '{}'".format(base_name, len(meshes), armature_data['name'] if armature_data else "None"))
print("Included files:", include_files)  # Print the list of include files for reference
