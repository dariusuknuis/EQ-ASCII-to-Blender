import bpy
import re
import json
from mathutils import Vector

# ------------------------------------------------------------
# Operator: Generate Radial Visibility
# ------------------------------------------------------------

def encode_rle(regions):
    """Run‑length encode a sorted 1‑based region list into the Go‑style bytes."""
    if not regions:
        return []
    max_reg = regions[-1]
    # build (visible, count) groups
    groups = []
    cur = 1
    start = 1
    vis = (regions[0] == 1)
    while cur <= max_reg:
        is_vis = cur in regions
        if is_vis != vis:
            groups.append((vis, cur - start))
            vis = is_vis
            start = cur
        cur += 1
    groups.append((vis, cur - start))

    out = []
    i = 0
    while i < len(groups):
        vis_flag, cnt = groups[i]
        nxt = groups[i+1] if i+1 < len(groups) else (None, None)
        if vis_flag:
            # visible run
            if nxt[0] is False and cnt <= 7 and nxt[1] <= 7:
                out.append(0x80 | (cnt << 3) | nxt[1])
                i += 2
                continue
            elif cnt <= 62:
                out.append(0xC0 + cnt)
            else:
                out.extend([0xFF, cnt & 0xFF, (cnt >> 8) & 0xFF])
        else:
            # invisible run
            if nxt[0] is True and cnt <= 7 and nxt[1] <= 7:
                out.append(0x40 | (cnt << 3) | nxt[1])
                i += 2
                continue
            elif cnt <= 62:
                out.append(cnt)
            else:
                out.extend([0x3F, cnt & 0xFF, (cnt >> 8) & 0xFF])
        i += 1
    return out

class OBJECT_OT_generate_radial_visibility(bpy.types.Operator):
    """Run a radial visibility pass on all R###### empties"""
    bl_idname = "object.generate_radial_visibility"
    bl_label = "Generate Radial Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    search_radius: bpy.props.FloatProperty(
        name="Search Radius",
        description="Radius within which to search for neighboring regions",
        default=2000.0,
        min=0.0,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        pattern = re.compile(r"^R\d{6}$")
        # gather all region empties in the scene
        region_empties = [obj for obj in context.scene.objects
                          if obj.type == 'EMPTY' and pattern.match(obj.name)]
        for empty in region_empties:
            center = empty.location
            # find neighbors within radius
            neighbors = [n for n in region_empties
                         if n is not empty and (n.location - center).length <= self.search_radius]
            region_ids = sorted(int(n.name[1:]) for n in neighbors)

            # choose encoding strategy
            if empty.get('VISLISTBYTES', False):
                byte_list = encode_rle(region_ids)
            else:
                byte_list = []
                for rid in region_ids:
                    idx0 = rid - 1
                    byte_list.extend([idx0 & 0xFF, (idx0 >> 8) & 0xFF])

            # build JSON
            out = { 'num_ranges': len(byte_list),
                    'range_bytes': [str(b) for b in byte_list] }
            empty['VISLIST_01'] = json.dumps(out)

        self.report({'INFO'}, "Radial visibility data generated for {} regions".format(len(region_empties)))
        return {'FINISHED'}

# ------------------------------------------------------------
# Panel: Add button under Outdoor World
# ------------------------------------------------------------

class VIEW3D_PT_radial_visibility(bpy.types.Panel):
    bl_label = ""  # nested under parent
    bl_idname = "VIEW3D_PT_radial_visibility"
    bl_parent_id = "VIEW3D_PT_outdoor_world"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_context = 'objectmode'

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_generate_radial_visibility.bl_idname,
                        text="Generate Radial Visibility", icon='PLUGIN')

# registration
classes = (
    OBJECT_OT_generate_radial_visibility,
    VIEW3D_PT_radial_visibility,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
