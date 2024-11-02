import bpy
import bmesh

def print_uvs_per_vertex(bm, uv_layer):
    # Create an empty UV map with a list for each vertex
    uv_map = {v.index: [] for v in bm.verts}

    # Populate the UV map by going through the loops and assigning UVs to corresponding vertices
    for face in bm.faces:
        for loop in face.loops:
            vertex_index = loop.vert.index
            uv = loop[uv_layer].uv
            uv_map[vertex_index].append(uv.copy())

    # Print UVs by vertex, in the order of vertex index
    print("\nUVs by Vertex (in vertex index order):")
    for vertex_index in sorted(uv_map.keys()):
        uvs = uv_map[vertex_index]
        uv_list = ', '.join([f"({uv[0]:.4f}, {uv[1]:.4f})" for uv in uvs])
        print(f"Vertex {vertex_index}: {uv_list}")
        
    return uv_map

def split_vertices_by_uv(mesh_obj):
    # Get the mesh data and create a bmesh instance
    mesh = mesh_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Ensure UV layer exists
    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        print("No UV layer found.")
        bm.free()
        return

    # Step 1: Print UVs before splitting
    print("Before Splitting UVs:")
    uv_map = print_uvs_per_vertex(bm, uv_layer)

    # Step 2: Check for vertices with multiple different UVs and split them
    vertices_to_split = []
    for vertex_index, uvs in uv_map.items():
        # If there's more than one UV associated with a vertex, check if they are different
        if len(uvs) > 1:
            first_uv = uvs[0]
            if any(uv != first_uv for uv in uvs):
                # Ensure lookup table before accessing verts by index
                bm.verts.ensure_lookup_table()
                vertices_to_split.append(bm.verts[vertex_index])

    if vertices_to_split:
        # Perform the split operation on each vertex explicitly using bmesh's split_edges()
        for v in vertices_to_split:
            bmesh.ops.split_edges(bm, edges=[e for e in v.link_edges])
        
        print(f"Split {len(vertices_to_split)} vertices with different UV values.")

    # Step 3: Update the mesh after the split
    bm.to_mesh(mesh)
    bm.free()

    # Step 4: Reload the bmesh after the split and reassign the UV layer
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active  # Reassign the UV layer after reloading the bmesh

    # Step 5: Print UVs after splitting
    print("After Splitting UVs:")
    print_uvs_per_vertex(bm, uv_layer)
    bm.free()

    print(f"Finished splitting vertices by UVs for object: {mesh_obj.name}")


def reindex_vertices_by_vertex_group(mesh_obj, armature_obj=None):
    mesh = mesh_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Ensure lookup tables are available
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Step 1: Collect data (vertex groups, custom normals, UVs, vertex materials, etc.)
    mesh_data = {
        'vertices': [],
        'faces': [],
        'uvs': [],
        'normals': [],
        'vertex_materials': [],
        'passable': [],
        'face_materials': [],
        'vertex_groups': {}
    }

    uv_layer = bm.loops.layers.uv.active
    passable_layer = bm.faces.layers.int.get('PASSABLE')
    material_layer = bm.verts.layers.int.get('Vertex_Material_Index')

    # Collect vertex group weights by name for each vertex
    for v in bm.verts:
        mesh_data['vertices'].append(v.co.copy())

        # Collect vertex group weights by group name
        mesh_data['vertex_groups'][v.index] = {}
        for group in mesh_obj.vertex_groups:
            try:
                weight = group.weight(v.index)
                if weight > 0:
                    mesh_data['vertex_groups'][v.index][group.name] = weight
            except RuntimeError:
                pass

        # Collect vertex materials
        if material_layer:
            mesh_data['vertex_materials'].append(v[material_layer])

    # Collect face and loop data
    for face in bm.faces:
        mesh_data['faces'].append([v.index for v in face.verts])
        mesh_data['face_materials'].append(face.material_index)  # Collect material index for each face
        if passable_layer:
            mesh_data['passable'].append(face[passable_layer])

        if uv_layer:
            mesh_data['uvs'].append([loop[uv_layer].uv.copy() for loop in face.loops])

    # Collect and store custom split normals (before reindexing)
    mesh.calc_normals_split()
    normals_before = [(loop.vertex_index, loop.index, loop.normal.copy()) for loop in mesh.loops]
    mesh_data['normals'] = normals_before

    print("\nCustom Split Normals Before Reindexing:")
    for loop in normals_before:
        vertex_index, loop_index, normal = loop
        print(f"Loop {loop_index}: Vertex {vertex_index} - Normal {normal}")

    # Step 2: Reorder vertices by vertex group, preserving order within groups
    group_assignments = {}
    for v in bm.verts:
        group_data = [(group.group, group.weight) for group in mesh_obj.data.vertices[v.index].groups]
        if group_data:
            group_index = group_data[0][0]  # Use the first group the vertex belongs to
            if group_index not in group_assignments:
                group_assignments[group_index] = []
            group_assignments[group_index].append(v.index)

    # Flatten and reorder vertices by vertex group
    sorted_vertex_indices = []
    for group_index, vertices in sorted(group_assignments.items()):
        sorted_vertex_indices.extend(vertices)

    # Create a mapping from old index to new index
    old_to_new_index = {old_index: new_index for new_index, old_index in enumerate(sorted_vertex_indices)}

    # Step 3: Update the face vertex indices to reflect the new vertex order
    new_faces = []
    for face in mesh_data['faces']:
        new_faces.append([old_to_new_index[vi] for vi in face])
    mesh_data['faces'] = new_faces

    # Step 4: Clear the original mesh data
    mesh.clear_geometry()

    # Step 5: Rebuild the mesh with the new vertex order
    new_vertices = [mesh_data['vertices'][i] for i in sorted_vertex_indices]
    mesh.from_pydata(new_vertices, [], mesh_data['faces'])
    mesh.update()

    # Step 6: Reapply UVs, normals, vertex materials, material index, and passable flags
    if 'uvs' in mesh_data and mesh_data['uvs']:
        uvlayer = mesh.uv_layers.new(name=mesh_obj.name + "_uv")
        for i, poly in enumerate(mesh.polygons):
            for j, loop_index in enumerate(poly.loop_indices):
                uv = mesh_data['uvs'][i][j]
                uvlayer.data[loop_index].uv = uv

    # Step 7: Reapply custom split normals (reorder them based on new vertex indices)
    if 'normals' in mesh_data and mesh_data['normals']:
        mesh.use_auto_smooth = True

        # Rebuild the correct normal assignments based on both the loop and vertex indices
        reordered_normals = [None] * len(mesh.loops)
        for loop in mesh.loops:
            new_vertex_index = loop.vertex_index

            # Find the original loop that corresponds to this new loop's vertex
            original_normal = None
            for orig_v_idx, orig_loop_idx, normal in normals_before:
                if old_to_new_index.get(orig_v_idx, None) == new_vertex_index and loop.index == orig_loop_idx:
                    original_normal = normal
                    break

            if original_normal:
                reordered_normals[loop.index] = original_normal
            else:
                # Use the default loop normal if no match is found
                reordered_normals[loop.index] = loop.normal

        # Set the custom split normals
        mesh.normals_split_custom_set(reordered_normals)

    if 'vertex_materials' in mesh_data:
        vertex_material_attribute = mesh.attributes.new(name="Vertex_Material_Index", type='INT', domain='POINT')
        for i, v_index in enumerate(sorted_vertex_indices):
            vertex_material_attribute.data[i].value = mesh_data['vertex_materials'][v_index]

    if 'passable' in mesh_data and mesh_data['passable']:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        passable_layer = bm.faces.layers.int.new("PASSABLE")
        for i, face in enumerate(bm.faces):
            face[passable_layer] = mesh_data['passable'][i]
        bm.to_mesh(mesh)
        bm.free()

    # Reapply face material indices
    for i, poly in enumerate(mesh.polygons):
        poly.material_index = mesh_data['face_materials'][i]

    # Step 8: Recreate and apply vertex groups using the collected data
    mesh_obj.vertex_groups.clear()  # Clear existing vertex groups

    # Loop through each vertex and reapply the vertex groups
    for old_index, new_index in old_to_new_index.items():
        for group_name, weight in mesh_data['vertex_groups'][old_index].items():
            # Find or create the vertex group by name
            group = mesh_obj.vertex_groups.get(group_name)
            if not group:
                group = mesh_obj.vertex_groups.new(name=group_name)
            # Apply the weight to the new vertex index
            group.add([new_index], weight, 'ADD')

    # Print custom split normals after reindexing
    mesh.calc_normals_split()
    normals_after = []
    for loop in mesh.loops:
        normals_after.append((loop.vertex_index, loop.normal.copy()))

    print("\nCustom Split Normals After Reindexing:")
    for idx, (vertex_index, normal) in enumerate(normals_after):
        print(f"Loop {idx}: Vertex {vertex_index} - Normal {normal}")

    # Update the mesh
    mesh.update()

    print(f"Reindexed and modified the object: {mesh_obj.name}")

# Example usage
mesh_object = bpy.data.objects['BAM01_DMSPRITEDEF']  # Replace with your mesh object
split_vertices_by_uv(mesh_object)  # Split vertices by UV discrepancies
reindex_vertices_by_vertex_group(mesh_object)  # Reindex vertices after the split operation
