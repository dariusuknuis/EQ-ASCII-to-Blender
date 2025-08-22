import re

def write_variation_sprites_and_materials(material, file, written_sprites, written_materials):
    """Writes SIMPLESPRITEDEF and MATERIALDEFINITION for variation materials."""

    if material.name in written_materials:
        print(f"Material {material.name} already written; skipping.")
        return  # Skip already written materials
    
    def sanitize_filename(name):
        """Remove file extensions for sprite formatting."""
        return name.split(".")[0]

    def get_texture_name(node):
        """Retrieve the texture name, preferring node.name; if not, fallback to node.image.name."""
        return node.name if node.name else node.image.name

    def get_node_group_name(node):
        """Retrieve the node group name; if 'USERDEFINED_20' variation, keep only 'USERDEFINED_20'."""
        if "USERDEFINED_20" in node.node_tree.name:
            return "USERDEFINED_20"
        return node.node_tree.name

    def identify_nodes(material):
        """Identify specific nodes based on naming conventions in valid_nodes."""
        image_nodes = [node for node in material.node_tree.nodes if node.type == 'TEX_IMAGE']
        valid_nodes = [node for node in image_nodes if not node.name.endswith("_NC")]

        # Initialize nodes as None
        layer_node = None
        detail_node = None
        palette_mask_node = None
        palette_nodes = []
        primary_node = None

        # Identify nodes based on suffixes and naming patterns
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

    # SIMPLESPRITEDEF section
    primary_node, layer_node, detail_node, palette_mask_node, palette_nodes = identify_nodes(material)
    tag_index = material.get("TAGINDEX", 0)
    variation = material.get("VARIATION", 0)
    skipframes = "NULL" if not material.get("SKIPFRAMES", False) else 1
    animated = 1 if material.get("ANIMATED", False) else "NULL"
    sleep = material.get("SLEEP", 0)
    currentframe = material.get("CURRENTFRAME", "NULL") if material.get("CURRENTFRAME", 0) else "NULL"
    simple_sprite_tag_index = material.get("SIMPLESPRITETAGINDEX", 0)

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
        file.write(f'\tTAGINDEX {simple_sprite_tag_index}\n')
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
                overlay_texture = get_texture_name(detail_node)
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
    file.write(f'\t\tSIMPLESPRITETAGINDEX {simple_sprite_tag_index}\n')
    hex_flag = 1 if material.get("HEXFIFTYFLAG", False) else 0
    file.write(f'\t\tHEXFIFTYFLAG {hex_flag}\n')
    uvshiftperms = material.get("UVSHIFTPERMS", [0, 0.0])
    file.write(f'\tUVSHIFTPERMS? {uvshiftperms[0]:.8e} {uvshiftperms[1]:.8e}\n')
    file.write(f'\tDOUBLESIDED {0 if material.use_backface_culling else 1}\n')