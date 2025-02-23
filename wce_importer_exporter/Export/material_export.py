import bpy
import re

def write_materials_and_sprites(mesh, file, written_sprites=set(), written_materials=set(), written_palettes=set()):
    """Writes materials, sprites, and palette definitions for a mesh, avoiding duplicates."""
    
    def sanitize_filename(name):
        """Remove file extension from a filename."""
        return name.split(".")[0]
    
    def get_texture_name(node):
        """Return node.name if it exists; otherwise return node.image.name."""
        return node.name if node.name else node.image.name

    def get_node_group_name(node):
        """Return the node group name; if 'USERDEFINED_20' variation, return just 'USERDEFINED_20'."""
        if "USERDEFINED_20" in node.node_tree.name:
            return "USERDEFINED_20"
        if "USERDEFINED_26" in node.node_tree.name:
            return "USERDEFINED_26"
        return node.node_tree.name

    def identify_nodes(material):
        """
        Identify key TEX_IMAGE nodes from the material's node tree.
        Returns:
          primary_node, layer_node, detail_node, palette_mask_node, palette_nodes
        """
        image_nodes = [node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE']
        valid_nodes = [node for node in image_nodes if not node.name.endswith("_NC")]
        primary_node = None
        layer_node = None
        detail_node = None
        palette_mask_node = None
        palette_nodes = []
        for node in valid_nodes:
            if node.name.upper().endswith("_LAYER") and layer_node is None:
                layer_node = node
            elif node.name.upper().endswith("_DETAIL") and detail_node is None:
                detail_node = node
            elif "PAL.BMP" in node.name.upper() and palette_mask_node is None:
                palette_mask_node = node
            elif re.match(r'^\d+,', node.name):
                palette_nodes.append(node)
            elif primary_node is None:
                primary_node = node
        return primary_node, layer_node, detail_node, palette_mask_node, palette_nodes

    def write_sprites_and_materials(mesh, file):
        # (Your existing code to write the SIMPLESPRITEDEF and MATERIALDEFINITION sections.)
        # For brevity, assume this function processes materials and writes their sprite definitions.
        # We'll focus here on how to write the FRAME block differently based on NUMFRAMES.
        palette_name = mesh.get("MATERIALPALETTE", "")
        if not palette_name or palette_name in written_palettes:
            return None, []
        mesh_materials = [mat for mat in mesh.data.materials if mat and mat.name.endswith("_MDF")]
        unique_materials = [mat.name for mat in mesh_materials if mat.name not in written_materials]
        for material in mesh_materials:
            if material.name in written_materials:
                continue
            written_materials.add(material.name)
            
            primary_node, layer_node, detail_node, palette_mask_node, palette_nodes = identify_nodes(material)
            tag_index = material.get("TAGINDEX", 0)
            variation = material.get("VARIATION", 0)
            skipframes = "NULL" if not material.get("SKIPFRAMES", False) else 1
            animated = 1 if material.get("ANIMATED", False) else "NULL"
            sleep = material.get("SLEEP", 0)
            currentframe = material.get("CURRENTFRAME", "NULL") if material.get("CURRENTFRAME", 0) else "NULL"

            # Determine sprite tag for the SIMPLESPRITEDEF header.
            if layer_node:
                sprite_tag = sanitize_filename(layer_node.name) + "_SPRITE"
            elif primary_node:
                sprite_tag = sanitize_filename(primary_node.name) + "_SPRITE"
            else:
                sprite_tag = ""
            
            if sprite_tag not in written_sprites and sprite_tag:
                written_sprites.add(sprite_tag)
                
                # Write SIMPLESPRITEDEF header.
                file.write(f'\nSIMPLESPRITEDEF "{sprite_tag}"\n')
                file.write(f'\tTAGINDEX {tag_index}\n')
                file.write(f'\tVARIATION {variation}\n')
                file.write(f'\tSKIPFRAMES? {skipframes}\n')
                file.write(f'\tANIMATED? {animated}\n')
                file.write(f'\tSLEEP? {sleep}\n')
                file.write(f'\tCURRENTFRAME? {currentframe}\n')
                
                # Now, handle the FRAME block differently based on NUMFRAMES.
                num_frames = int(material.get("NUMFRAMES", 1))
                if num_frames > 1:
                    # Animated: assume numbered properties "FRAME 001", "FRAME 002", etc.
                    frame_keys = sorted([k for k in material.keys() if k.startswith("FRAME ")])
                    file.write(f'\tNUMFRAMES {len(frame_keys)}\n')
                    for key in frame_keys:
                        parts = [p.strip() for p in material[key].split(",")]
                        if len(parts) < 2:
                            continue
                        frame_tag_val = parts[0]
                        base_file_val = parts[1]
                        file.write(f'\t\tFRAME "{frame_tag_val}"\n')
                        file.write(f'\t\t\tNUMFILES 1\n')
                        file.write(f'\t\t\t\tFILE "{base_file_val}"\n')
                else:
                    # Static: NUMFRAMES == 1.
                    # In this case, the custom property "FRAME" contains only the frame tag.
                    frame_tag_val = material.get("FRAME", "")
                    # Get the texture names from the nodes.
                    primary_node, layer_node, detail_node, palette_mask_node, palette_nodes = identify_nodes(material)
                    base_texture = get_texture_name(primary_node) if primary_node else ""
                    # Check if a _DETAIL or _LAYER node exists.
                    overlay_texture = ""
                    if detail_node:
                        mapping_node = next((link.from_node for link in detail_node.inputs["Vector"].links if link.from_node.type == 'MAPPING'), None)
                        scale_x = mapping_node.inputs["Scale"].default_value[0] if mapping_node else 1.0
                        texture_name = get_texture_name(detail_node)
                        overlay_texture = f"{texture_name}_{scale_x:.6f}"
                    elif layer_node:
                        overlay_texture = get_texture_name(layer_node)
                    
                    # Also, if a palette mask node exists, then we expect multiple valid nodes.
                    if palette_mask_node:
                        palette_nodes_sorted = sorted(palette_nodes, key=lambda n: int(re.search(r'^(\d+)', n.name).group(1)) if re.search(r'^(\d+)', n.name) else 0)
                        num_files = 2 + len(palette_nodes_sorted)
                        file.write(f'\tNUMFRAMES 1\n')
                        file.write(f'\t\tFRAME "{frame_tag_val}"\n')
                        file.write(f'\t\t\tNUMFILES {num_files}\n')
                        file.write(f'\t\t\t\tFILE "{base_texture}"\n')
                        file.write(f'\t\t\t\tFILE "{palette_mask_node.name}"\n')
                        for node in palette_nodes_sorted:
                            file.write(f'\t\t\t\tFILE "{node.name}"\n')
                    elif overlay_texture:
                        file.write(f'\tNUMFRAMES 1\n')
                        file.write(f'\t\tFRAME "{frame_tag_val}"\n')
                        file.write(f'\t\t\tNUMFILES 2\n')
                        file.write(f'\t\t\t\tFILE "{base_texture}"\n')
                        file.write(f'\t\t\t\tFILE "{overlay_texture}"\n')
                    else:
                        file.write(f'\tNUMFRAMES 1\n')
                        file.write(f'\t\tFRAME "{frame_tag_val}"\n')
                        file.write(f'\t\t\tNUMFILES 1\n')
                        file.write(f'\t\t\t\tFILE "{base_texture}"\n')

            # Write MATERIALDEFINITION section.
            file.write(f'\nMATERIALDEFINITION "{material.name}"\n')
            file.write(f'\tTAGINDEX {tag_index}\n')
            file.write(f'\tVARIATION {variation}\n')
            node_group = next((ng for ng in material.node_tree.nodes if ng.type == 'GROUP' and "PaletteMask" not in ng.name and "Blur" not in ng.name), None)
            if node_group:
                rm_name = get_node_group_name(node_group)
                file.write(f'\tRENDERMETHOD "{rm_name}"\n')
            rgbpen = material.get("RGBPEN", [0.7, 0.7, 0.7, 0])
            rgbpen_scaled = [int(round(c * 255)) for c in rgbpen]
            file.write(f'\tRGBPEN {" ".join(map(str, rgbpen_scaled))}\n')
            brightness = material.get("BRIGHTNESS", 0.0)
            scaledambient = material.get("SCALEDAMBIENT", 1.0)
            file.write(f'\tBRIGHTNESS {brightness:.8e}\n')
            file.write(f'\tSCALEDAMBIENT {scaledambient:.8e}\n')
            # Write SIMPLESPRITEINST section.
            file.write(f'\tSIMPLESPRITEINST\n')
            file.write(f'\t\tTAG "{sprite_tag}"\n')
            hex_flag = 1 if material.get("HEXFIFTYFLAG", False) else 0
            file.write(f'\t\tHEXFIFTYFLAG {hex_flag}\n')
            pairs = material.get("PAIRS", [0, 0.0])
            file.write(f'\tPAIRS? {int(pairs[0])} {pairs[1]:.8e}\n')
            file.write(f'\tDOUBLESIDED {0 if material.use_backface_culling else 1}\n')
    
        return palette_name, unique_materials

    def write_materialpalette(palette_name, materials, file):
        if palette_name not in written_palettes:
            written_palettes.add(palette_name)
            file.write(f'\nMATERIALPALETTE "{palette_name}"\n')
            file.write(f'\tNUMMATERIALS {len(materials)}\n')
            for mat in materials:
                file.write(f'\tMATERIAL "{mat}"\n')
    
    palette_name, unique_materials = write_sprites_and_materials(mesh, file)
    if palette_name and unique_materials:
        write_materialpalette(palette_name, unique_materials, file)
    
    print(f"Materials, sprites, and palette '{palette_name}' exported successfully.")

