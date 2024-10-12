import bpy

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
