import bpy

def parent_polyhedron(polyhedron_obj, base_name, main_obj, armature_obj, meshes, armature_data):
    assigned = False

    # 1. Search for a matching mesh
    for mesh_data in meshes:
        if mesh_data.get('polyhedron') == base_name:
            mesh_obj = bpy.data.objects.get(mesh_data['name'])
            if mesh_obj:
                polyhedron_obj.parent = mesh_obj
                print(f"Polyhedron '{base_name}' parented to matching mesh '{mesh_obj.name}'")
                assigned = True
                break

    # 2. Check the armature object directly if not yet assigned
    if not assigned and armature_data.get('polyhedron') == base_name:
        polyhedron_obj.parent = armature_obj
        print(f"Polyhedron '{base_name}' parented directly to armature '{armature_obj.name}'")
        assigned = True

    # 3. Search for a matching bone in armature_data if still not assigned
    if not assigned:
        for bone_data in armature_data['bones']:
            if bone_data.get('sprite') == base_name:
                bone_name = bone_data['name']
                bone_obj = armature_obj.pose.bones.get(bone_name)
                if bone_obj:
                    polyhedron_obj.parent = armature_obj
                    polyhedron_obj.parent_bone = bone_name
                    polyhedron_obj.parent_type = 'BONE'
                    # Adjust the origin by subtracting the Y-length of the bone tail
                    bone_tail_y = bone_obj.tail.y
                    polyhedron_obj.location.y -= bone_tail_y
                    print(f"Polyhedron '{base_name}' parented to bone '{bone_name}' in armature '{armature_obj.name}'")
                    assigned = True
                    break

    # 4. Fallback: Parent to main empty object if no other match
    if not assigned:
        polyhedron_obj.parent = main_obj
        print(f"Polyhedron '{base_name}' parented to main object '{main_obj.name}' as no other match was found")
