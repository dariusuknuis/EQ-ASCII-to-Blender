# import_wce_file.py
import bpy
import os

# Global flag to check if modules are loaded
modules_loaded = False

# Function that loads external modules only during execution
def load_modules():
    global eq_ascii_parse, create_materials, register_passable_editor, unregister_passable_editor, create_region
    global apply_passable_to_all_meshes, apply_passable_to_mesh, create_passable_geometry_node_group, create_passable_material
    global create_mesh, create_armature, assign_mesh_to_armature, create_animation, add_actordef_to_object, create_worldtree
    global create_default_pose, create_polyhedron, create_bounding_sphere, create_bounding_box, parent_polyhedron
    global modify_regions_and_worldtree, create_bounding_volume_for_region_empties, create_worlddef,create_zone
    global modules_loaded

    if not modules_loaded:
        from .eq_ascii_wld_parser import eq_ascii_parse
        from .material_creator import create_materials
        from .apply_passable_to_all_meshes import apply_passable_to_all_meshes, apply_passable_to_mesh, create_passable_geometry_node_group, create_passable_material
        from ..create.create_mesh import create_mesh
        from ..create.create_armature import create_armature
        from .assign_mesh_to_armature import assign_mesh_to_armature
        from ..create.create_animation import create_animation
        from ..create.create_default_pose import create_default_pose
        from ..create.create_polyhedron import create_polyhedron
        from ..create.create_worldtree import create_worldtree
        from ..create.create_worlddef import create_worlddef
        from ..create.create_mesh_and_bounding_shapes import create_bounding_sphere, create_bounding_box
        from .add_actordef_to_object import add_actordef_to_object
        from .parent_polyhedron import parent_polyhedron
        from ..create.create_region import create_region
        from ..create.create_zone import create_zone
        from ..create.modify_regions_and_worldtree import modify_regions_and_worldtree, create_bounding_volume_for_region_empties

        # Set the flag to True to prevent re-loading
        modules_loaded = True

# Process INCLUDE files
def process_include_file(include_line, file_dir, root_file_path, node_group_cache):
    load_modules()  # Ensure modules are loaded before use
    pending_objects = []

    # Normalize and construct the full path
    include_filepath = os.path.normpath(os.path.join(file_dir, include_line))

    # Call eq_ascii_parse after ensuring modules are loaded
    meshes, armature_data, track_definitions, material_palettes, includes, polyhedrons, textures, materials, vertex_animations, actordef_data, worldtree_data, regions, worlddef_data, zones, ambient_light = eq_ascii_parse(include_filepath)
    
    print(f"actordef_data in process_include_file: {actordef_data}")

    # Extract folder name for object naming
    folder_name = include_line.split('/')[0].upper()

    # Create the main object for the file
    if actordef_data:
        main_obj_name = actordef_data['name']
    else:
        main_obj_name = folder_name

    main_obj = bpy.data.objects.new(main_obj_name, None)
    bpy.context.collection.objects.link(main_obj)

    # Add actordef properties if available
    if actordef_data:
        add_actordef_to_object(main_obj, actordef_data)

    # Determine model prefix
    if actordef_data:
        model_prefix = actordef_data["actions"][0]["levelsofdetail"][0]["sprite"].split("_")[0]
    else:
        model_prefix = folder_name

    print(f"Model prefix: {model_prefix}")

    # Create materials
    created_materials = create_materials(materials, textures, file_dir, node_group_cache)

    armature_obj = None

    if armature_data and track_definitions:
        armature_tracks = track_definitions['armature_tracks']
        armature_obj, bone_map, cumulative_matrices = create_armature(armature_data, armature_tracks, main_obj)
        for mesh_data in meshes:
            mesh_obj = create_mesh(mesh_data, main_obj, armature_obj, armature_data, material_palettes, created_materials, vertex_animations, pending_objects)
            geo_node_group = create_passable_geometry_node_group()
            passable_mat = create_passable_material()
            apply_passable_to_mesh(mesh_obj, geo_node_group, passable_mat)
            assign_mesh_to_armature(mesh_obj, armature_obj, armature_data, cumulative_matrices)
        create_default_pose(armature_obj, track_definitions, armature_data, cumulative_matrices, model_prefix)
        create_animation(armature_obj, track_definitions, armature_data, model_prefix)
    else:
        for mesh_data in meshes:
            mesh_obj = create_mesh(mesh_data, main_obj, None, None, material_palettes, created_materials, vertex_animations, pending_objects)
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
        parent_polyhedron(polyhedron_obj, base_name, main_obj, armature_obj, meshes, armature_data)

    if regions:
        for region in regions:
            region_obj = create_region(region, pending_objects)

    # Process WorldTree if data is present
    if worldtree_data:
        worldtree_root = create_worldtree(worldtree_data, pending_objects)
        if worldtree_root:
            print(f"WorldTree created with root: {worldtree_root.name}")

    for obj in pending_objects:
        bpy.context.collection.objects.link(obj)

    if bpy.data.objects.get("WorldTree_Root") and bpy.data.objects.get("REGION") and not bpy.data.objects.get("WORLD_BOUNDS"):
        create_bounding_volume_for_region_empties()
        modify_regions_and_worldtree()
    else:
        print("WorldTree_Root or REGION not found, skipping region-to-worldtree parenting.")

    if zones:
        for zone in zones:
            zone_obj = create_zone(zone)

    quail_folder = os.path.basename(file_dir)

    if worlddef_data:
        worlddef_obj = create_worlddef(worlddef_data, quail_folder)

    worlddef_obj = None
    for obj in bpy.data.objects:
        if obj.name.upper().endswith("_WORLDDEF"):
            worlddef_obj = obj
            for obj in bpy.data.objects:
                if "_ZONE" in obj.name or obj.name == "WorldTree_Root" or obj.name == "REGION" or obj.name == "REGION_MESHES":
                    # Parent without changing world transform:
                    obj.parent = worlddef_obj  

    # Set an undo point for each model import
    bpy.ops.ed.undo_push(message=f"Imported model: {main_obj_name}")

    return main_obj

# Process the root file and includes
def process_root_file(file_path):
    load_modules()  # Ensure modules are loaded before use

    file_dir = os.path.dirname(file_path)
    meshes, armature_data, track_definitions, material_palettes, include_files, polyhedrons, textures, materials, vertex_animations, actordef_data, worldtree_data, regions, worlddef_data, zones, ambient_light = eq_ascii_parse(file_path)

    print(f"actordef in process_root_file: {actordef_data}")
    
    node_group_cache = {}

    for include_line in include_files:
        process_include_file(include_line, file_dir, file_path, node_group_cache)


