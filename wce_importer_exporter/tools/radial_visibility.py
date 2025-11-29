# radial_visibility.py

import bpy, re, json

def encode_rle(regions):
    """Run-length encode a sorted 1-based region list into compact bytes."""
    if not regions:
        return []
    max_reg = regions[-1]
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

def run_radial_visibility(search_radius=2000.0):
    """
    Finds all empties named R######, computes neighbors within search_radius,
    and writes VISLIST_01 (and uses VISLISTBYTES flag) on each empty.
    """
    pattern = re.compile(r"^R\d{6}$")
    empties = [o for o in bpy.context.scene.objects
               if o.type == 'EMPTY' and pattern.match(o.name)]

    for e in empties:
        center = e.location
        nbrs = [n for n in empties
                if n is not e and (n.location - center).length <= search_radius]
        ids = sorted(int(n.name[1:]) for n in nbrs)

        if e.get('VISLISTBYTES', False):
            data = encode_rle(ids)
        else:
            data = []
            for rid in ids:
                idx0 = rid - 1
                data.extend([idx0 & 0xFF, (idx0 >> 8) & 0xFF])

        e['VISLIST_01'] = json.dumps({
            'num_ranges': len(data),
            'range_bytes': [str(b) for b in data]
        })

    print(f"Radial visibility computed for {len(empties)} regions.")
