import bpy
import re

def write_materials_and_sprites(mesh, file, written_sprites=set(), written_materials=set(), written_palettes=set()):
    """Writes materials, sprites, and palette definitions for a mesh, avoiding duplicates."""

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
            if node.name.endswith("_LAYER") and layer_node is None:
                layer_node = node
            elif node.name.endswith("_DETAIL") and detail_node is None:
                detail_node = node
            elif node.name.endswith("PAL.BMP") and palette_mask_node is None:
                palette_mask_node = node
            elif re.match(r'^\d+,', node.name):
                palette_nodes.append(node)
            elif primary_node is None:
                primary_node = node  # Assign the first remaining node as primary_node

        return primary_node, layer_node, detail_node, palette_mask_node, palette_nodes

    def write_sprites_and_materials(mesh, file):
        palette_name = mesh.get("MATERIALPALETTE", "")
        if not palette_name or palette_name in written_palettes:
            return None, []  # Skip if no palette or already processed

        # Track materials used in this mesh for MATERIALPALETTE
        mesh_materials = [mat for mat in mesh.data.materials if mat and mat.name.endswith("_MDF")]
        unique_materials = [mat.name for mat in mesh_materials if mat.name not in written_materials]

        for material in mesh_materials:
            if material.name in written_materials:
                continue  # Skip already processed materials
            written_materials.add(material.name)

            # SIMPLESPRITEDEF section
            primary_node, layer_node, detail_node, palette_mask_node, palette_nodes = identify_nodes(material)
            variation = material.get("VARIATION", 0)
            skipframes = 1 if material.get("SKIPFRAMES", False) else "NULL"
            animated = 1 if material.get("ANIMATED", False) else "NULL"
            sleep = material.get("SLEEP", 0)
            currentframe = material.get("CURRENTFRAME", "NULL") if material.get("CURRENTFRAME", 0) else "NULL"

            # Determine SIMPLESPRITEDEF tag
            if layer_node:
                sprite_tag = sanitize_filename(layer_node.name) + "_SPRITE"
            elif primary_node:
                sprite_tag = sanitize_filename(primary_node.name) + "_SPRITE"
            else:
                sprite_tag = ""

            if sprite_tag not in written_sprites and sprite_tag:
                written_sprites.add(sprite_tag)
                
                # Write SIMPLESPRITEDEF header
                file.write(f'\nSIMPLESPRITEDEF "{sprite_tag}"\n')
                file.write(f'\tVARIATION {variation}\n')
                file.write(f'\tSKIPFRAMES? {skipframes}\n')
                file.write(f'\tANIMATED? {animated}\n')
                file.write(f'\tSLEEP? {sleep}\n')
                file.write(f'\tCURRENTFRAME? {currentframe}\n')

                # Determine and write FRAME entries based on node presence and conditions
                frames = []
                
                # Start with the primary texture node
                if primary_node:
                    frames.append((primary_node, sanitize_filename(get_texture_name(primary_node))))
                
                # Add layer, detail, palette mask, and palette nodes
                if layer_node:
                    frames.append((layer_node, sanitize_filename(get_texture_name(primary_node))))
                if detail_node:
                    frames.append((detail_node, sanitize_filename(get_texture_name(primary_node))))
                if palette_mask_node:
                    frames.append((palette_mask_node, sanitize_filename(get_texture_name(primary_node))))
                if palette_nodes:
                    frames.extend((node, sanitize_filename(get_texture_name(primary_node))) for node in palette_nodes)
                
                # Handle animated frames from custom properties
                frame_props = sorted([k for k in material.keys() if k.startswith("FRAME")])
                if frame_props:
                    # Count all frames except the first one to add to NUMFRAMES
                    for prop in frame_props[1:]:
                        texture_name = material[prop]
                        frame_tag = sanitize_filename(texture_name)
                        frames.append((texture_name, frame_tag))

                # Write NUMFRAMES and individual FRAME lines
                file.write(f'\tNUMFRAMES {len(frames)}\n')
                for node, frame_tag in frames:
                    texture_name = get_texture_name(node) if isinstance(node, bpy.types.Node) else node
                    
                    # Check if the node is detail_node and append the scale value if so
                    if node == detail_node:
                        # Get the mapping scale value if available, default to 1.0 if not
                        mapping_node = next((link.from_node for link in detail_node.inputs["Vector"].links if link.from_node.type == 'MAPPING'), None)
                        scale_x = mapping_node.inputs["Scale"].default_value[0] if mapping_node else 1.0
                        texture_name = f"{texture_name}_{scale_x:.6f}"

                    file.write(f'\t\tFRAME "{texture_name}" "{frame_tag}"\n')

            # MATERIALDEFINITION section
            file.write(f'\nMATERIALDEFINITION "{material.name}"\n')
            file.write(f'\tVARIATION {variation}\n')
            
            # Find the primary node group (ignoring "PaletteMask" and "Blur" groups)
            rendermethod = next((ng for ng in material.node_tree.nodes if ng.type == 'GROUP' and "PaletteMask" not in ng.name and "Blur" not in ng.name), None)
            if rendermethod:
                rm_name = get_node_group_name(rendermethod)
                file.write(f'\tRENDERMETHOD "{rm_name}"\n')

            rgbpen = material.get("RGBPEN", [0.7, 0.7, 0.7, 0])
            rgbpen_scaled = [int(round(c * 255)) for c in rgbpen]
            file.write(f'\tRGBPEN {" ".join(map(str, rgbpen_scaled))}\n')
            brightness = material.get("BRIGHTNESS", 0.0)
            scaledambient = material.get("SCALEDAMBIENT", 0.75)
            file.write(f'\tBRIGHTNESS {brightness:.8e}\n')
            file.write(f'\tSCALEDAMBIENT {scaledambient:.8e}\n')
            file.write(f'\tSIMPLESPRITEINST\n\t\tTAG "{sprite_tag}"\n')
            hex_fifty_flag = 1 if material.get("HEXFIFTYFLAG", False) else 0
            file.write(f'\t\tHEXFIFTYFLAG {hex_fifty_flag}\n')
            pairs = material.get("PAIRS", [0, 0.0])
            file.write(f'\tPAIRS? {int(pairs[0])} {pairs[1]:.8e}\n')
            double_sided = 0 if material.use_backface_culling else 1
            file.write(f'\tDOUBLESIDED {double_sided}\n')

        return palette_name, unique_materials

    def write_materialpalette(palette_name, materials, file):
        if palette_name not in written_palettes:
            written_palettes.add(palette_name)
            file.write(f'\nMATERIALPALETTE "{palette_name}"\n')
            file.write(f'\tNUMMATERIALS {len(materials)}\n')
            for mat in materials:
                file.write(f'\tMATERIAL "{mat}"\n')

    # Process each _DMSPRITEDEF mesh
    palette_name, unique_materials = write_sprites_and_materials(mesh, file,)
    if palette_name and unique_materials:
        write_materialpalette(palette_name, unique_materials, file)

    print(f"Materials, sprites, and palette '{palette_name}' exported successfully.")
