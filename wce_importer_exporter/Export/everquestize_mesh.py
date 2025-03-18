import bmesh
import bpy

def update_vertex_material_indices(mesh_obj):
    """
    Updates the Vertex_Material_Index attribute for each vertex based on the materials
    of the faces it is part of. Loose vertices retain their existing values.
    """
    mesh = mesh_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Ensure lookup tables are available
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Create or get the material index attribute for vertices
    material_layer = bm.verts.layers.int.get("Vertex_Material_Index")
    if not material_layer:
        material_layer = bm.verts.layers.int.new("Vertex_Material_Index")

    # Iterate through all vertices
    for vertex in bm.verts:
        # Check if vertex is part of any face
        connected_faces = vertex.link_faces

        if connected_faces:
            # Get the material index of the first connected face
            material_index = connected_faces[0].material_index
            vertex[material_layer] = material_index  # Update material index
        else:
            # For loose vertices, retain existing value by skipping update
            try:
                _ = vertex[material_layer]  # Access attribute to ensure it exists
            except KeyError:
                continue  # Skip loose vertices without an existing value

    # Write the updated bmesh data back to the mesh
    bm.to_mesh(mesh)
    bm.free()

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
    # print("\nUVs by Vertex (in vertex index order):")
    for vertex_index in sorted(uv_map.keys()):
        uvs = uv_map[vertex_index]
        uv_list = ', '.join([f"({uv[0]:.4f}, {uv[1]:.4f})" for uv in uvs])
        # print(f"Vertex {vertex_index}: {uv_list}")
        
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
    # print("Before Splitting UVs:")
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
        
        # print(f"Split {len(vertices_to_split)} vertices with different UV values.")

    # Step 3: Update the mesh after the split
    bm.to_mesh(mesh)
    bm.free()

    # Step 4: Reload the bmesh after the split and reassign the UV layer
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    uv_layer = bm.loops.layers.uv.active  # Reassign the UV layer after reloading the bmesh

    # Step 5: Print UVs after splitting
    # print("After Splitting UVs:")
    # print_uvs_per_vertex(bm, uv_layer)
    bm.free()

    print(f"Finished splitting vertices by UVs for object: {mesh_obj.name}")


def reindex_vertices_and_faces(mesh_obj, armature_obj=None):
    # Check if the mesh has any vertex groups; skip if not
    # if not mesh_obj.vertex_groups:
    #     # print(f"Skipping reindexing: No vertex groups found for {mesh_obj.name}")
    #     return
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
    has_uvs = uv_layer is not None
    passable_layer = bm.faces.layers.int.get('PASSABLE')
    material_layer = bm.verts.layers.int.get('Vertex_Material_Index')

    has_vertex_groups = bool(mesh_obj.vertex_groups)

    # Collect vertex group weights by name for each vertex
    for v in bm.verts:
        mesh_data['vertices'].append(v.co.copy())

        # Collect vertex material index (applies to all cases)
        if material_layer:
            mesh_data['vertex_materials'].append(v[material_layer])
        
        # Collect vertex group data if available
        if has_vertex_groups:
            mesh_data['vertex_groups'][v.index] = {}
            for group in mesh_obj.vertex_groups:
                try:
                    weight = group.weight(v.index)
                    if weight > 0:
                        mesh_data['vertex_groups'][v.index][group.name] = weight
                except RuntimeError:
                    pass

    # Collect face and loop data
    for face in bm.faces:
        mesh_data['faces'].append([v.index for v in face.verts])
        mesh_data['face_materials'].append(face.material_index)  # Collect material index for each face
        if passable_layer:
            mesh_data['passable'].append(face[passable_layer])

        if has_uvs:
            mesh_data['uvs'].append([loop[uv_layer].uv.copy() for loop in face.loops])

    # Collect and store custom split normals (before reindexing)
    mesh.calc_normals_split()
    mesh_data['normals'] = []

    # Access split normals from the mesh, not bmesh
    for poly in mesh.polygons:
        face_normals = []
        for loop_index in poly.loop_indices:
            loop = mesh.loops[loop_index]
            face_normals.append(loop.normal.copy())
        mesh_data['normals'].append(face_normals)

    # print("\nCustom Split Normals Before Reindexing:")
    # for loop in normals_before:
    #     vertex_index, loop_index, normal = loop
        # print(f"Loop {loop_index}: Vertex {vertex_index} - Normal {normal}")

    # Step 2: Reorder vertices
    sorted_vertex_indices = []

    if has_vertex_groups:
        group_assignments = {}

        # Collect vertex group assignments
        for v in bm.verts:
            group_data = [(group.group, group.weight) for group in mesh_obj.data.vertices[v.index].groups]
            if group_data:
                group_index = group_data[0][0]  # First group assigned
                if group_index not in group_assignments:
                    group_assignments[group_index] = []
                group_assignments[group_index].append(v.index)

        # Sort by vertex group, then by material index within the group
        for group_index, vertices in sorted(group_assignments.items()):
            vertices_sorted_by_material = sorted(vertices, key=lambda v: mesh_data['vertex_materials'][v])
            sorted_vertex_indices.extend(vertices_sorted_by_material)

    else:
        sorted_vertex_indices = sorted(range(len(mesh_data['vertices'])), 
                                       key=lambda v: mesh_data['vertex_materials'][v])

    # Create a mapping from old index to new index
    old_to_new_vertex_index = {old_index: new_index for new_index, old_index in enumerate(sorted_vertex_indices)}

    # Step 3: Update the face vertex indices to reflect the new vertex order
    new_faces = [[old_to_new_vertex_index[vi] for vi in face] for face in mesh_data['faces']]
    mesh_data['faces'] = new_faces

    # 🔹 Sort faces, passable values, and optionally UVs by face material index
    if has_uvs:
        sorted_faces_data = sorted(enumerate(zip(mesh_data['faces'], mesh_data['face_materials'],
                                                mesh_data['passable'], mesh_data['uvs'], mesh_data['normals'])),
                                key=lambda x: x[1][1])  # Sort by material index

        old_to_new_face_index = {original_idx: new_idx for new_idx, (original_idx, _) in enumerate(sorted_faces_data)}

        # Extract the sorted lists
        mesh_data['faces'] = [face for _, (face, _, _, _, _) in sorted_faces_data]
        mesh_data['face_materials'] = [mat for _, (_, mat, _, _, _) in sorted_faces_data]
        mesh_data['passable'] = [pas for _, (_, _, pas, _, _) in sorted_faces_data]
        mesh_data['uvs'] = [uvs for _, (_, _, _, uvs, _) in sorted_faces_data]
        mesh_data['normals'] = [normals for _, (_, _, _, _, normals) in sorted_faces_data]
    else:
        sorted_faces_data = sorted(enumerate(zip(mesh_data['faces'], mesh_data['face_materials'],
                                                mesh_data['passable'], mesh_data['normals'])),
                                key=lambda x: x[1][1])  # Sort by material index

        old_to_new_face_index = {original_idx: new_idx for new_idx, (original_idx, _) in enumerate(sorted_faces_data)}

        # Extract the sorted lists without UVs
        mesh_data['faces'] = [face for _, (face, _, _, _) in sorted_faces_data]
        mesh_data['face_materials'] = [mat for _, (_, mat, _, _) in sorted_faces_data]
        mesh_data['passable'] = [pas for _, (_, _, pas, _) in sorted_faces_data]
        mesh_data['normals'] = [normals for _, (_, _, _, normals) in sorted_faces_data]

    # Step 4: Clear the original mesh data
    mesh.clear_geometry()

    # Step 5: Rebuild the mesh with the new vertex order
    new_vertices = [mesh_data['vertices'][i] for i in sorted_vertex_indices]
    mesh.from_pydata(new_vertices, [], mesh_data['faces'])
    mesh.update()

    # Step 6: Reapply UVs, normals, vertex materials, material index, and passable flags
    if has_uvs and 'uvs' in mesh_data and mesh_data['uvs']:
        uvlayer = mesh.uv_layers.new(name=mesh_obj.name + "_uv")
        for i, poly in enumerate(mesh.polygons):
            for j, loop_index in enumerate(poly.loop_indices):
                uv = mesh_data['uvs'][i][j]
                uvlayer.data[loop_index].uv = uv

    # Step 7: Reapply custom split normals (reorder them based on new vertex indices)
    if 'normals' in mesh_data and mesh_data['normals']:
        mesh.use_auto_smooth = True
        reordered_normals = []

        for i, poly in enumerate(mesh.polygons):
            for j, loop_index in enumerate(poly.loop_indices):
                normal = mesh_data['normals'][i][j]  # Extract normal
                reordered_normals.append(normal)

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
    if has_vertex_groups:
        mesh_obj.vertex_groups.clear()

        for old_index, new_index in old_to_new_vertex_index.items():
            for group_name, weight in mesh_data['vertex_groups'][old_index].items():
                group = mesh_obj.vertex_groups.get(group_name)
                if not group:
                    group = mesh_obj.vertex_groups.new(name=group_name)
                group.add([new_index], weight, 'ADD')

    mesh.calc_normals_split()
    # normals_after = []
    # for loop in mesh.loops:
    #     normals_after.append((loop.vertex_index, loop.normal.copy()))

    # print("\nCustom Split Normals After Reindexing:")
    # for idx, (vertex_index, normal) in enumerate(normals_after):
    #     print(f"Loop {idx}: Vertex {vertex_index} - Normal {normal}")

    mesh.update()

    # print(f"Reindexed and modified the object: {mesh_obj.name}")

    # Reindex MESHOPS within the same function
    meshops_name = f"{mesh_obj.name}_MESHOPS"
    if meshops_name in bpy.data.texts:
        meshops_text = bpy.data.texts[meshops_name]
        updated_lines = []

        for line in meshops_text.lines:
            if not line.body.strip().startswith("MESHOP"):
                updated_lines.append(line.body)
                continue

            parts = line.body.strip().split()
            if len(parts) != 6:
                print(f"Invalid MESHOP line: {line.body}")
                updated_lines.append(line.body)
                continue

            _, idx1, idx2, distance, idx3, op_type = parts

            idx1 = int(idx1)
            idx2 = int(idx2)
            idx3 = int(idx3)
            op_type = int(op_type)

            # Apply reindexing based on MESHOP type
            if op_type == 1:
                face_idx = old_to_new_face_index.get(idx1, idx1)
                dest_vertex_idx = old_to_new_vertex_index.get(idx2, idx2)
                updated_line = f"MESHOP {face_idx} {dest_vertex_idx} {distance} {idx3} {op_type}"

            elif op_type == 2:
                face_idx = old_to_new_face_index.get(idx1, idx1)
                updated_line = f"MESHOP {face_idx} {idx2} {distance} {idx3} {op_type}"

            elif op_type == 3:
                vertex_idx = old_to_new_vertex_index.get(idx1, idx1)
                updated_line = f"MESHOP {vertex_idx} {idx2} {distance} {idx3} {op_type}"

            elif op_type == 4:
                updated_line = f"MESHOP {idx1} {idx2} {distance} {idx3} {op_type}"

            else:
                updated_line = line.body

            updated_lines.append(updated_line)

        # Clear and update MESHOPS text block
        meshops_text.clear()
        for updated_line in updated_lines:
            meshops_text.write(updated_line + "\n")

def reindex_faces_by_material(mesh_obj):
    """
    Reorders faces in the mesh so that faces using the same material index are grouped together,
    while preserving UVs, normals, and custom attributes.
    """
    mesh = mesh_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Ensure lookup tables
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Step 1: Store existing face data
    face_data = []
    
    uv_layer = bm.loops.layers.uv.active
    passable_layer = bm.faces.layers.int.get('PASSABLE')

    for face in bm.faces:
        face_info = {
            'material_index': face.material_index,
            'vertices': [v.index for v in face.verts],  # Store original vertex indices
            'uvs': [loop[uv_layer].uv.copy() for loop in face.loops] if uv_layer else None,
            'passable': face[passable_layer] if passable_layer else None
        }
        face_data.append(face_info)

    # Step 2: Sort faces by material index
    face_data.sort(key=lambda x: x['material_index'])

    # Step 3: Clear existing faces and recreate them in the new order
    bmesh.ops.delete(bm, geom=bm.faces, context='FACES')

    # 🔹 **Fix: Ensure Lookup Tables Are Updated**
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    for face_info in face_data:
        new_face = bm.faces.new([bm.verts[i] for i in face_info['vertices']])
        new_face.material_index = face_info['material_index']

        if passable_layer and face_info['passable'] is not None:
            new_face[passable_layer] = face_info['passable']

        # Restore UVs
        if uv_layer and face_info['uvs']:
            for loop, uv in zip(new_face.loops, face_info['uvs']):
                loop[uv_layer].uv = uv

    # 🔹 **Fix: Ensure Lookup Tables Are Updated Again**
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    # Apply changes back to the mesh
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
