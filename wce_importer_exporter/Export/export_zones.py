import os
import re
import bpy

def find_zones(parent_obj):
    zones = []
    for child in parent_obj.children:
        if child.type == 'MESH' and "_ZONE" in child.name:
            zones.append(child)
        zones.extend(find_zones(child))
    return zones

def export_zones(root_obj, output_path):
    """
    Appends ZONE entries for every mesh under `root_obj` whose name ends with "_ZONE"
    into the same zone.wce file that export_worldtree wrote.
    """
    zone_file = os.path.join(output_path, "zone.wce")
    zones = find_zones(root_obj)
    if not zones:
        return

    with open(zone_file, 'a') as f:
        for zone in zones:
            f.write(f'ZONE "{zone.name}"\n')

            # parse the custom REGIONLIST string, e.g. "[1, 4, 7]"
            raw = zone.get("REGIONLIST", "").strip()
            nums = [n.strip() for n in re.sub(r'[\[\]]', '', raw).split(',') if n.strip()]
            count = len(nums)

            # write count + values
            if count:
                f.write("\tREGIONLIST " + str(count) + " " + " ".join(nums) + "\n")
            else:
                f.write("\tREGIONLIST 0\n")

            # write USERDATA (possibly empty string)
            userdata = zone.get("USERDATA", "")
            f.write(f'\tUSERDATA "{userdata}"\n\n')

    print(f"[export_zones] appended {len(zones)} zone entries to {zone_file}")
