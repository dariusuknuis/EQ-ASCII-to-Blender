import os

def find_worldnodes(parent_obj):
    nodes = []
    for child in parent_obj.children:
        if child.type == 'MESH' and child.name.startswith("WorldNode"):
            nodes.append(child)
        nodes.extend(find_worldnodes(child))
    return nodes

def export_worldtree(root_obj, output_path):
    worldnodes = find_worldnodes(root_obj)
    if not worldnodes:
        return

    zone_file = os.path.join(output_path, "zone.wce")
    with open(zone_file, 'a') as f:
        # Header
        f.write('WORLDTREE ""\n')
        f.write(f"\tNUMWORLDNODES {len(worldnodes)}\n")

        # sort by the custom "worldnode" integer property
        for node in sorted(worldnodes, key=lambda o: o.get("worldnode", 0)):
            idx = node.get("worldnode", 0)
            f.write(f"\t\tWORLDNODE // {idx}\n")

            # NORMALABCD: first 3 floats from 'normal' array + 'd' float
            normal = node.get("normal", [0.0, 0.0, 0.0])
            d      = node.get("d", 0.0)
            vals   = [*normal[:3], d]
            vals_s = " ".join(f"{v:.8e}" for v in vals)
            f.write(f"\t\t\tNORMALABCD {vals_s}\n")

            # WORLDREGIONTAG
            tag = node.get("region_tag", "")
            f.write(f"\t\t\tWORLDREGIONTAG \"{tag}\"\n")

            # FRONTTREE / BACKTREE
            ft = node.get("front_tree", 0)
            bt = node.get("back_tree",  0)
            f.write(f"\t\t\tFRONTTREE {ft}\n")
            f.write(f"\t\t\tBACKTREE  {bt}\n")

    print(f"[export_worldtree] wrote {zone_file}")