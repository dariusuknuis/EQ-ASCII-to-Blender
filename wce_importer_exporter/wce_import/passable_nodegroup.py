# passable_nodegroup.py
import bpy
from .material_utils import _add_group_socket, _get_group_io_sockets

GREEN = (0.0, 1.0, 0.0, 1.0)

def create_node_group_passable(name: str = "Passable"):
    """
    Create (or fetch) a node group that:
      Inputs:
        - Texture (Color)
        - PassableDisplay (Float)  <-- drive this from Scene
      Outputs:
        - Result (Color)            <-- texture tinted toward green by the mask
        - Value  (Float)            <-- mask * 0.3 (use as transparency factor)
        - BSDF   (Shader)           <-- Transparent BSDF

      Internals:
        PASSABLE attribute -> Compare(==1.0) -> Multiply(* PassableDisplay) -> mask
        mask -> Mix(Color): A=Texture, B=Green -> Result
        mask -> Multiply(* 0.3) -> Value
        Transparent BSDF -> BSDF
    """
    # Idempotent: reuse if it already exists
    if name in bpy.data.node_groups:
        ng = bpy.data.node_groups[name]
        # make sure IO sockets exist (safe if already there)
        _ensure_io(ng)
        return ng

    ng = bpy.data.node_groups.new(name=name, type='ShaderNodeTree')

    # --- IO ---
    group_in  = ng.nodes.new("NodeGroupInput");  group_in.location  = (-800, 0)
    group_out = ng.nodes.new("NodeGroupOutput"); group_out.location = ( 600, 0)

    # --- IO (Blender 5+ safe via your helper) ---
    _add_group_socket(ng, 'Texture',         'NodeSocketColor',  is_input=True)
    _add_group_socket(ng, 'PassableDisplay', 'NodeSocketFloat',  is_input=True)
    _add_group_socket(ng, 'Result',          'NodeSocketColor',  is_input=False)
    _add_group_socket(ng, 'Value',           'NodeSocketFloat',  is_input=False)
    _add_group_socket(ng, 'BSDF',            'NodeSocketShader', is_input=False)

    # --- Nodes (as in your screenshot) ---
    # Attribute PASSABLE
    n_attr = ng.nodes.new("ShaderNodeAttribute")
    n_attr.location = (-800, -280)
    n_attr.attribute_name = "PASSABLE"
    # Compare == 1.0
    n_cmp = ng.nodes.new("ShaderNodeMath")
    n_cmp.location = (-520, -280)
    n_cmp.operation = 'COMPARE'
    n_cmp.inputs[1].default_value = 1.0      # B = 1.0
    n_cmp.inputs[2].default_value = 0.0005   # Epsilon (tolerance)
    # Multiply (mask * PassableDisplay)
    n_mul_mask = ng.nodes.new("ShaderNodeMath")
    n_mul_mask.location = (-280, -180)
    n_mul_mask.operation = 'MULTIPLY'
    # Multiply (mask * 0.3) -> transparency strength
    n_mul_alpha = ng.nodes.new("ShaderNodeMath")
    n_mul_alpha.location = (  40, -180)
    n_mul_alpha.operation = 'MULTIPLY'
    n_mul_alpha.inputs[1].default_value = 0.3

    # Mix Color (tint toward green)
    n_mix_col = ng.nodes.new("ShaderNodeMix")
    n_mix_col.location = (  80,  120)
    n_mix_col.data_type = 'RGBA'
    n_mix_col.blend_type = 'COLOR'
    b_sock = n_mix_col.inputs.get("B")     # Name is 'B' on ShaderNodeMix
    b_sock.default_value = (0.0, 1.0, 0.0, 1.0)

    # Transparent BSDF
    n_tr = ng.nodes.new("ShaderNodeBsdfTransparent")
    n_tr.location = (360, -110)

    # --- Links ---
    in_sock, out_sock = _get_group_io_sockets(ng)
    L = ng.links
    # Attribute PASSABLE -> Compare (A is the attribute's "Factor" – index 2)
    L.new(n_attr.outputs["Factor"], n_cmp.inputs[0])  # A
    # Compare -> Multiply (mask)
    L.new(n_cmp.outputs["Value"], n_mul_mask.inputs[0])
    # Group Input PassableDisplay -> Multiply (mask)
    L.new(in_sock["PassableDisplay"], n_mul_mask.inputs[1])

    # mask -> Mix Color (Factor)
    L.new(n_mul_mask.outputs["Value"], n_mix_col.inputs["Factor"])
    # Texture -> Mix Color A
    L.new(in_sock["Texture"], n_mix_col.inputs["A"])

    # mask -> Multiply(*0.3) -> alpha value out
    L.new(n_mul_mask.outputs["Value"], n_mul_alpha.inputs[0])

    # Outputs
    L.new(n_mix_col.outputs["Result"],  out_sock["Result"])
    L.new(n_mul_alpha.outputs["Value"], out_sock["Value"])
    L.new(n_tr.outputs["BSDF"],         out_sock["BSDF"])

    return ng


def _ensure_io(ng: bpy.types.NodeTree):
    """Make sure the group has the expected sockets (safe on existing groups)."""
    want_in = {"Texture": "NodeSocketColor", "PassableDisplay": "NodeSocketFloat"}
    want_out = {"Result": "NodeSocketColor", "Value": "NodeSocketFloat", "BSDF": "NodeSocketShader"}
    for name, stype in want_in.items():
        if name not in ng.inputs:
            ng.inputs.new(stype, name)
    if "PassableDisplay" in ng.inputs:
        ng.inputs["PassableDisplay"].default_value = ng.inputs["PassableDisplay"].default_value or 0.0
    for name, stype in want_out.items():
        if name not in ng.outputs:
            ng.outputs.new(stype, name)
