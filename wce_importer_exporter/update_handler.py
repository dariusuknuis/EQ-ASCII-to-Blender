import bpy, os, re

@bpy.app.handlers.persistent
def update_animated_texture_nodes(scene):
    """
    Frame-change handler that updates animated texture nodes based on custom properties
    (e.g. "FRAME 001", "FRAME 002", etc.) stored on materials.
    
    The property value is expected to be a comma-separated string:
         <frame_tag>, <base texture file>[, <overlay texture file>]
    
    This version derives the base path from the base image texture node's image filepath
    and uses the material's SLEEP value (in milliseconds) to control how long each frame is shown.
    """
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue

        # Identify the base node (the first TEX_IMAGE node not ending with "LAYER" or "DETAIL")
        base_node = None
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and not (node.name.upper().endswith("LAYER") or node.name.upper().endswith("DETAIL")):
                base_node = node
                break
        if not base_node or not base_node.image:
            continue

        # Derive dynamic base path from the base node's image filepath.
        dynamic_base = os.path.dirname(bpy.path.abspath(base_node.image.filepath))

        # Collect custom properties with keys starting with "FRAME "
        frame_keys = [key for key in mat.keys() if key.startswith("FRAME ")]
        if not frame_keys:
            continue
        frame_keys.sort()
        total = len(frame_keys)

        # Get SLEEP value from the material (in milliseconds) and calculate effective duration (in scene frames)
        sleep_val = mat.get("SLEEP", 0)
        fps = scene.render.fps
        effective_duration = max(1, int(round((sleep_val * fps) / 1000))) if sleep_val else 1

        # Determine the current frame index (cycling using effective_duration)
        current_index = ((scene.frame_current - 1) // effective_duration) % total
        current_key = frame_keys[current_index]
        prop_value = mat[current_key]
        # Expected format: "<frame_tag>, <base texture file>[, <overlay texture file>]"
        parts = [p.strip() for p in prop_value.split(",")]
        if len(parts) < 2:
            continue
        base_file = parts[1]
        overlay_file = parts[2] if len(parts) >= 3 else ""

        # Locate the animated texture nodes.
        base_tex_node = None
        overlay_tex_node = None
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                if node.name.upper().endswith("LAYER") or node.name.upper().endswith("DETAIL"):
                    overlay_tex_node = node
                else:
                    if base_tex_node is None:
                        base_tex_node = node

        # Update the base node.
        bp = os.path.join(dynamic_base, base_file)
        texture_path = bpy.path.abspath(bp)
        if os.path.isfile(texture_path):
            image = bpy.data.images.get(base_file)
            if not image:
                try:
                    image = bpy.data.images.load(texture_path)
                except Exception as e:
                    print(f"Error loading base image '{texture_path}': {e}")
                    continue
            if base_tex_node.image != image:
                base_tex_node.image = image
                print(f"Material '{mat.name}': Updated base node with image '{base_file}' from property '{current_key}'.")
        else:
            print(f"Base image file not found: {texture_path}")

        # Update the overlay node if specified.
        if overlay_tex_node and overlay_file:
            op = os.path.join(dynamic_base, overlay_file)
            texture_path = bpy.path.abspath(op)
            if os.path.isfile(texture_path):
                image = bpy.data.images.get(overlay_file)
                if not image:
                    try:
                        image = bpy.data.images.load(texture_path)
                    except Exception as e:
                        print(f"Error loading overlay image '{texture_path}': {e}")
                        continue
                if overlay_tex_node.image != image:
                    overlay_tex_node.image = image
                    print(f"Material '{mat.name}': Updated overlay node with image '{overlay_file}' from property '{current_key}'.")
            else:
                print(f"Overlay image file not found: {texture_path}")
