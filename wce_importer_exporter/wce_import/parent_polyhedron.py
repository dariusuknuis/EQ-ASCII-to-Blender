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
                pb = armature_obj.pose.bones.get(bone_name)
                if not pb:
                    continue

                # Parent polyhedron to the *parent of the armature* (or world if none)
                polyhedron_obj.parent_type = 'OBJECT'
                polyhedron_obj.parent_bone = ""
                polyhedron_obj.parent = armature_obj.parent  # None => world

                # Remove any existing duplicate Child Of to the same bone (idempotent runs)
                for c in list(polyhedron_obj.constraints):
                    if c.type == 'CHILD_OF' and c.target == armature_obj and c.subtarget == pb.name:
                        polyhedron_obj.constraints.remove(c)

                # Add Child Of constraint targeting the bone
                con = polyhedron_obj.constraints.new('CHILD_OF')
                con.name = f"ChildOf_{armature_obj.name}_{pb.name}"
                con.target = armature_obj
                con.subtarget = pb.name
                con.use_location_x = con.use_location_y = con.use_location_z = True
                con.use_rotation_x = con.use_rotation_y = con.use_rotation_z = True
                con.use_scale_x = con.use_scale_y = con.use_scale_z = True
                con.influence = 1.0

                # "Clear Inverse" so the object snaps to the bone HEAD and then follows it
                bpy.context.view_layer.update()
                con.inverse_matrix.identity()

                # (Optional) If you want the polyhedron's local transforms reset right now:
                # polyhedron_obj.location = (0.0, 0.0, 0.0)
                # polyhedron_obj.rotation_euler = (0.0, 0.0, 0.0)
                # polyhedron_obj.scale = (1.0, 1.0, 1.0)

                print(
                    f"Polyhedron '{base_name}' parented to armature parent and "
                    f"constrained to bone '{bone_name}' (Child Of with Clear Inverse)."
                )
                assigned = True
                break

    # 4. Fallback: Parent to main empty object if no other match
    if not assigned:
        polyhedron_obj.parent = main_obj
        print(f"Polyhedron '{base_name}' parented to main object '{main_obj.name}' as no other match was found")
