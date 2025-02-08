import bpy
import os
import re
import shutil
from dds_checker import check_and_fix_dds
from wce_importer_exporter.update_handler import update_animated_texture_nodes

def add_animated_texture_nodes(material, texture_info, base_path=None):
    """
    Configures a material's image texture nodes for animation based on parsed texture_info.
    
    This function:
      - Finds the base image texture node (the first TEX_IMAGE node that does not have a name ending with "LAYER" or "DETAIL")
        and any overlay nodes (nodes whose names end with "LAYER" or "DETAIL").
      - Sets these nodes to use sequence animation.
      - Processes each frame in texture_info by running check_and_fix_dds on each referenced texture file.
      - Creates numbered custom properties on the material (e.g. "FRAME 001") with a value formatted as:
            <frame_tag>, <base texture file name>[, <overlay texture file name>]
      - Defines and registers a frame-change handler (update_animated_texture_nodes) that uses these custom properties
        (and the base node’s image filepath for a dynamic base path) to update the node images at runtime.
      - The material’s "SLEEP" value (in milliseconds) is used to determine how many scene frames each texture frame is shown.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # --- 1. Identify nodes ---
    base_node = None
    overlay_nodes = []
    for node in nodes:
        if node.type == 'TEX_IMAGE':
            if node.name.upper().endswith("LAYER") or node.name.upper().endswith("DETAIL"):
                overlay_nodes.append(node)
            else:
                if base_node is None:
                    base_node = node
    if not base_node:
        print(f"[add_animated_texture_nodes] No base image texture node found in material: {material.name}")
        return

    # --- 3. Build lists from texture_info ---
    base_frame_files = []
    overlay_frame_files = []
    for frame in texture_info.get('frames', []):
        files = frame.get('frame_files', [])
        if len(files) > 0:
            # Run DDS check on the base file.
            base_file = files[0].get('file', '')
            full_path = os.path.join(base_path, base_file) if base_path else base_file
            texture_path = bpy.path.abspath(full_path)
            if os.path.isfile(texture_path):
                try:
                    check_and_fix_dds(texture_path)
                except Exception as e:
                    print(f"Error processing DDS for {texture_path}: {e}")
            base_frame_files.append(base_file)
        else:
            base_frame_files.append('')
        if len(files) > 1:
            overlay_file = files[1].get('file', '')
            full_path = os.path.join(base_path, overlay_file) if base_path else overlay_file
            texture_path = bpy.path.abspath(full_path)
            if os.path.isfile(texture_path):
                try:
                    check_and_fix_dds(texture_path)
                except Exception as e:
                    print(f"Error processing DDS for {texture_path}: {e}")
            overlay_frame_files.append(overlay_file)
        else:
            overlay_frame_files.append('')

    # --- 4. Create numbered custom properties on the material ---
    # For each frame, create a property key "FRAME 001", "FRAME 002", etc.
    for idx, frame in enumerate(texture_info.get("frames", [])):
        frame_key = f"FRAME {idx + 1:03}"
        tag = frame.get("tag", "")
        base_file = ""
        overlay_file = ""
        frame_files = frame.get("frame_files", [])
        if len(frame_files) > 0:
            base_file = frame_files[0].get("file", "")
        if len(frame_files) > 1:
            overlay_file = frame_files[1].get("file", "")
        if overlay_file:
            value = f"{tag}, {base_file}, {overlay_file}"
        else:
            value = f"{tag}, {base_file}"
        material[frame_key] = value
        print(f"Set custom property {frame_key} = {value}")

    # Register the update handler.
    if update_animated_texture_nodes not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(update_animated_texture_nodes)