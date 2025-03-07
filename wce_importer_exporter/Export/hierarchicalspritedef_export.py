import bpy

def write_hierarchicalspritedef(armature, file):
    # Set the name of the hierarchical sprite definition based on the armature's name
    hs_def_name = f"{armature.name}"
    
    # Filter bones to only include those ending in "_DAG", skipping "_ANIDAG" bones
    bones = [bone for bone in armature.data.bones if bone.name.endswith("_DAG") and not bone.name.endswith("_ANIDAG")]
    num_dags = len(bones)
    
    # Generate adjusted indices for bones, ignoring _ANIDAG bones
    adjusted_indices = {bone.name: idx for idx, bone in enumerate(bones)}
    print(f"Adjusted indices map: {adjusted_indices}")  # Debug output to verify indexing
    
    # Write the HIERARCHICALSPRITEDEF header
    file.write(f'\nHIERARCHICALSPRITEDEF "{hs_def_name}"\n')
    file.write(f'\tNUMDAGS {num_dags}\n')

    # Write each bone's DAG definition
    for idx, bone in enumerate(bones):
        file.write(f'\t\tDAG // {idx}\n')
        file.write(f'\t\t\tTAG "{bone.name}"\n')
        
        # SPRITE field - Check for a mesh parented to the bone
        sprite_name = ""
        sprite_index = 0  # Initialize with a default value
        for child in armature.children:
            if child.parent_bone == bone.name:
                sprite_name = child.name
                sprite_index = child.get("SPRITEINDEX", 0)
                break
        file.write(f'\t\t\tSPRITE "{sprite_name}"\n')
        file.write(f'\t\t\tSPRITEINDEX {sprite_index}\n')
        
        # TRACK field - Replace "_DAG" with "_TRACK" in the bone's name
        track_name = bone.name.replace("_DAG", "_TRACK")
        file.write(f'\t\t\tTRACK "{track_name}"\n')
        file.write(f'\t\t\tTRACKINDEX 0\n')
        
        # SUBDAGLIST - Collect children that match the adjusted indices and aren't _ANIDAG
        child_indices = [
            adjusted_indices[child.name] for child in bone.children
            if child.name in adjusted_indices
        ]
        file.write(f'\t\t\tSUBDAGLIST {len(child_indices)} {" ".join(map(str, child_indices))}\n')

    # Write NUMATTACHEDSKINS based on meshes with "_DMSPRITEDEF" suffix
    # Write NUMATTACHEDSKINS based on meshes directly parented to the armature with "_DMSPRITEDEF" suffix
    attached_skins = [
        child for child in armature.children 
        if child.type == 'MESH' and child.name.endswith("_DMSPRITEDEF") and child.parent_type == 'OBJECT'
    ]
    file.write(f'\n\tNUMATTACHEDSKINS {len(attached_skins)}\n')
    
    for skin in attached_skins:
        sprite_index = skin.get("DMSPRITEINDEX", 0)
        link_dag_index = skin.get("LINKSKINUPDATESTODAGINDEX", 0)
        file.write(f'\t\tATTACHEDSKIN\n')
        file.write(f'\t\t\tDMSPRITE "{skin.name}"\n')
        file.write(f'\t\t\tDMSPRITEINDEX {sprite_index}\n')
        file.write(f'\t\t\tLINKSKINUPDATESTODAGINDEX {link_dag_index}\n')
    
    # Determine the POLYHEDRON definition from the armature's custom property
    polyhedron_name = armature.get("POLYHEDRON", "")

    file.write(f'\n\tPOLYHEDRON\n')
    file.write(f'\t\tSPRITE "{polyhedron_name}"\n')
        
    # CENTEROFFSET and BOUNDINGRADIUS calculations
    armature_loc = armature.location
    if armature_loc.x == 0 and armature_loc.y == 0 and armature_loc.z == 0:
        file.write('\tCENTEROFFSET? NULL NULL NULL\n')
    else:
        file.write(f'\tCENTEROFFSET? {armature_loc.x:.8e} {armature_loc.y:.8e} {armature_loc.z:.8e}\n')
    
    bounding_mesh = next((child for child in armature.children if child.name.endswith("_BR")), None)
    if bounding_mesh:
        bounding_radius = max((v.co.length for v in bounding_mesh.data.vertices), default=0)
        file.write(f'\tBOUNDINGRADIUS? {bounding_radius:.8e}\n')
    
    # Write flag properties
    hex_two_hundred_flag = 1 if armature.get("HEXTWOHUNDREDFLAG", False) else 0
    hex_twenty_thousand_flag = 1 if armature.get("HEXTWENTYTHOUSANDFLAG", False) else 0
    file.write(f'\tHEXTWOHUNDREDFLAG {hex_two_hundred_flag}\n')
    file.write(f'\tHEXTWENTYTHOUSANDFLAG {hex_twenty_thousand_flag}\n')
    
    print(f'HIERARCHICALSPRITEDEF data for "{hs_def_name}" exported.')
