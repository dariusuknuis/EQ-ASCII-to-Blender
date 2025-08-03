import os
import re

# ——— utility to find all R###### empties under a root —————————————
def find_region_empties(parent_obj):
    regs = []
    for child in parent_obj.children:
        if child.type == 'EMPTY' and re.match(r"^R\d{6}$", child.name):
            regs.append(child)
        regs.extend(find_region_empties(child))
    return regs

# ——— ambient‐light exporter ————————————————————————————
def export_ambient_light(root_obj, output_path):
    """
    If no empty ending '_AMBIENTLIGHT' exists, write a default
    AMBIENTLIGHT block (with region count) to 'zone.wce' (overwrite).
    """
    # bail if user has placed their own *_AMBIENTLIGHT empty
    def has_amb(o):
        for c in o.children:
            if c.type=='EMPTY' and c.name.endswith("_AMBIENTLIGHT"):
                return True
            if has_amb(c):
                return True
        return False

    if has_amb(root_obj):
        return

    regions = find_region_empties(root_obj)
    n       = len(regions)
    indices = " ".join(str(i) for i in range(n))

    path = os.path.join(output_path, "zone.wce")
    with open(path, "w") as f:
        f.write('AMBIENTLIGHT "DEFAULT_AMBIENTLIGHT"\n')
        f.write('\tLIGHT "DEFAULT_LIGHTDEF"\n')
        f.write('\t// LIGHTFLAGS 0\n')
        f.write(f'\tREGIONLIST {n} {indices}\n\n')

    print(f"[export_ambientlight] wrote header to {path}")