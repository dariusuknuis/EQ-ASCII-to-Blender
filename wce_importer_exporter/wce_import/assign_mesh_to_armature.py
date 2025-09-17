import bpy

def assign_mesh_to_armature(mesh_obj, armature_obj, armature_data, cumulative_matrices):
    mesh_name = mesh_obj.name
    assigned = False

    # Check if mesh belongs to attached skins
    for skin_data in armature_data.get('attached_skins', []):
        if skin_data['sprite'] == mesh_name:
            mesh_obj.parent = armature_obj
            armature_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
            armature_mod.object = armature_obj
            armature_mod.show_on_cage = True  # Enable "On Cage"
            armature_mod.show_in_editmode = True  # Enable "Edit Mode"
            mesh_obj["DMSPRITEINDEX"] = skin_data['sprite_index']
            mesh_obj["LINKSKINUPDATESTODAGINDEX"] = skin_data['link_skin_updates_to_dag_index']
            print(f"Mesh '{mesh_name}' parented to armature and assigned LINKSKINUPDATESTODAGINDEX: {skin_data['link_skin_updates_to_dag_index']}")
            assigned = True
            break  # Mesh is assigned, no need to check further

    # Check if mesh belongs to a bone's sprite
    if not assigned:
        for bone in armature_data['bones']:
            if bone.get('sprite') == mesh_name:
                pb = armature_obj.pose.bones.get(bone['name'])
                if not pb:
                    continue

                # 1) Parent mesh to the *parent of the armature* (or world if none)
                mesh_obj.parent_type = 'OBJECT'
                mesh_obj.parent_bone = ""
                mesh_obj.parent = armature_obj.parent  # can be None (world)

                # Optional: ensure no stale "Child Of" from earlier runs
                for c in list(mesh_obj.constraints):
                    if c.type == 'CHILD_OF' and c.target == armature_obj and c.subtarget == pb.name:
                        mesh_obj.constraints.remove(c)

                # 2) Add "Child Of" constraint targeting the bone
                con = mesh_obj.constraints.new('CHILD_OF')
                con.name = f"ChildOf_{armature_obj.name}_{pb.name}"
                con.target = armature_obj
                con.subtarget = pb.name
                con.use_location_x = con.use_location_y = con.use_location_z = True
                con.use_rotation_x = con.use_rotation_y = con.use_rotation_z = True
                con.use_scale_x = con.use_scale_y = con.use_scale_z = True
                con.influence = 1.0

                # 3) "Clear Inverse" so the child snaps to the bone HEAD and then follows it
                # (In UI this is Constraint > Clear Inverse; in API it's zeroing the inverse matrix)
                # Note: needs depsgraph update so constraint has valid matrices
                bpy.context.view_layer.update()
                con.inverse_matrix.identity()

                # (Optional) If you want the mesh geometry centered exactly at the head right now
                # without changing its origin permanently, you can zero its local transforms:
                # mesh_obj.location = (0.0, 0.0, 0.0)
                # mesh_obj.rotation_euler = (0.0, 0.0, 0.0)
                # mesh_obj.scale = (1.0, 1.0, 1.0)

                mesh_obj["SPRITEINDEX"] = bone.get("sprite_index", 0)
                print(
                    f"Mesh '{mesh_name}' parented to armature parent "
                    f"and constrained to bone '{bone['name']}' (Child Of with Clear Inverse)."
                )
                assigned = True
                break  # Mesh is assigned; stop searching

    # If not assigned to a skin or bone, add the armature modifier without parenting
    if not assigned:
        print(f"Mesh '{mesh_name}' not in attached_skins or bone sprites. Applying armature modifier without parenting.")
        armature_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
        armature_mod.object = armature_obj
        armature_mod.show_on_cage = True  # Enable "On Cage"
        armature_mod.show_in_editmode = True  # Enable "Edit Mode"

