import os
import re
import json
import bpy

def find_region_empties(parent_obj):
    """Recursively collect all empties named R###### under parent_obj."""
    regions = []
    for child in parent_obj.children:
        if child.type == 'EMPTY' and re.match(r"^R\d{6}$", child.name):
            regions.append(child)
        regions.extend(find_region_empties(child))
    return regions

def export_regions(root_obj, output_path):
    """Write out regions.wce from all R###### empties under root_obj."""
    regs = find_region_empties(root_obj)
    if not regs:
        return

    path = os.path.join(output_path, "regions.wce")
    with open(path, "w") as f:
        for empty in sorted(regs, key=lambda o: int(o.name[1:])):
            # Header
            f.write(f'REGION "{empty.name}"\n')

            # defaults
            f.write("\tREVERBVOLUME 0.00000000e+00\n")
            f.write("\tREVERBOFFSET 0\n")
            f.write("\tREGIONFOG 0\n")
            f.write("\tGOURAND2 0\n")
            f.write("\tENCODEDVISIBILITY 0\n")

            # VISLISTBYTES
            vb = 1 if empty.get("VISLISTBYTES", True) else 0
            f.write(f"\tVISLISTBYTES {vb}\n")

            # more defaults
            f.write("\tNUMREGIONVERTEXS 0\n")
            f.write("\tNUMRENDERVERTICES 0\n")
            f.write("\tNUMWALLS 0\n")
            f.write("\tNUMOBSTACLES 0\n")
            f.write("\tNUMCUTTINGOBSTACLES 0\n")

            # VISTREE block
            f.write("\tVISTREE\n")
            f.write("\t\tNUMVISNODES 1\n")
            f.write("\t\t\tVISNODE // 0\n")
            f.write("\t\t\t\tVNORMALABCD 0.00000000e+00 0.00000000e+00 0.00000000e+00 0.00000000e+00\n")
            f.write("\t\t\t\tVISLISTINDEX 1\n")
            f.write("\t\t\t\tFRONTTREE 0\n")
            f.write("\t\t\t\tBACKTREE 0\n")

            # VISLISTS
            viskeys = [k for k in empty.keys() if re.match(r"^VISLIST_\d+$", k)]
            viskeys.sort(key=lambda k: int(k.split("_",1)[1]))
            f.write(f"\tNUMVISIBLELISTS {len(viskeys)}\n")
            for idx, key in enumerate(viskeys):
                raw = empty[key]
                try:
                    jd = json.loads(raw)
                    # support both "range_bytes" or older "ranges" key
                    bytes_list = jd.get("range_bytes", jd.get("ranges", []))
                    nums = [int(x) for x in bytes_list]
                    count = len(nums)
                except Exception:
                    count = 0
                    nums = []

                f.write(f"\t\tVISLIST // {idx}\n")
                if count:
                    seq = " ".join(str(x) for x in nums)
                    f.write(f"\t\t\tRANGE {count} {seq}\n")
                else:
                    f.write("\t\t\tRANGE 0\n")

            # SPHERE: location + empty size
            x,y,z = empty.location
            s     = empty.empty_display_size
            f.write(f"\tSPHERE {x:.8e} {y:.8e} {z:.8e} {s:.8e}\n")

            # USERDATA
            f.write("\tUSERDATA \"\"\n")

            # SPRITE: first mesh child
            sprite = next((c.name for c in empty.children if c.type=="MESH"), "")
            f.write(f"\tSPRITE \"{sprite}\"\n\n")

    print(f"[export_regions] wrote {path}")
