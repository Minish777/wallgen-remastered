"""Bake normalized letter-shape geometry from the Inkscape source into
assets/shapes.json. Each letter is normalized so its bbox center sits at
(0,0) — placing an instance anywhere is then just translate(center).

Also stores the source bbox *size* per kind per layout so new compositions
can scale them comfortably.

Usage: python3 tools/build_shapes.py
"""
import json
import math
import sys

sys.path.insert(0, "/home/bnuydev/wallgen")
from lxml import etree
from wallgen.svgpath import parse_path

NS = "http://www.w3.org/2000/svg"
INS = "{http://www.inkscape.org/namespaces/inkscape}"

KINDS = {"boomerang-shape": "boomerang", "n-shape": "n", "r-shape": "r", "mirrored-j-shape": "j"}


def cmd_to_d(cmds):
    parts = []
    for c in cmds:
        op, *a = c
        if op == "M":
            parts.append(f"M {a[0]:.5f} {a[1]:.5f}")
        elif op == "L":
            parts.append(f"L {a[0]:.5f} {a[1]:.5f}")
        elif op == "H":
            parts.append(f"H {a[0]:.5f}")
        elif op == "V":
            parts.append(f"V {a[0]:.5f}")
        elif op == "C":
            parts.append(f"C {a[0]:.5f} {a[1]:.5f} {a[2]:.5f} {a[3]:.5f} {a[4]:.5f} {a[5]:.5f}")
        elif op == "Q":
            parts.append(f"Q {a[0]:.5f} {a[1]:.5f} {a[2]:.5f} {a[3]:.5f}")
        elif op == "A":
            parts.append(f"A {a[2]:.5f} {a[3]:.5f} 0 {int(a[4])} {int(a[5])} {a[0]:.5f} {a[1]:.5f}")
        elif op == "Z":
            parts.append("Z")
    return " ".join(parts)


def translate_path(p, dx, dy):
    out = []
    for c in p.cmds:
        op, *a = c
        if op in ("M", "L"):
            out.append((op, a[0] - dx, a[1] - dy, 0, 0, 0, 0, 0))
        elif op == "H":
            out.append(("H", a[0] - dx, 0, 0, 0, 0, 0, 0))
        elif op == "V":
            out.append(("V", a[0] - dy, 0, 0, 0, 0, 0, 0))
        elif op == "C":
            out.append(("C", a[0] - dx, a[1] - dy, a[2] - dx, a[3] - dy, a[4] - dx, a[5] - dy, 0))
        elif op == "Q":
            out.append(("Q", a[0] - dx, a[1] - dy, a[2] - dx, a[3] - dy, 0, 0, 0))
        elif op == "A":
            out.append(("A", a[0] - dx, a[1] - dy, a[2], a[3], a[4], a[5], a[6]))
        elif op == "Z":
            out.append(("Z", 0, 0, 0, 0, 0, 0, 0))
    return out


def main():
    tree = etree.parse("/home/bnuydev/wallgen/assets/m3-source.svg")
    root = tree.getroot()
    letters = {}
    pills = {}
    for g in root.iter(f"{{{NS}}}g"):
        layout = g.get(INS + "label")
        if layout not in ("layout1", "layout2", "layout3"):
            continue
        for child in g:
            items = list(child) if child.tag.endswith("}g") else [child]
            for el in items:
                d = el.get("d")
                if d is None:
                    continue
                l = el.get(INS + "label")
                if l in KINDS:
                    p = parse_path(d)
                    x0, y0, x1, y1 = p.bbox()
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    pt = translate_path(p, cx, cy)
                    letters.setdefault(layout, {})[KINDS[l]] = {
                        "d": cmd_to_d(pt),
                        "w": x1 - x0,
                        "h": y1 - y0,
                    }
        # layout groups don't nest the pills; collect rect/pill paths too
        for child in g:
            if not child.tag.endswith("}g"):
                l = child.get(INS + "label")
                d = child.get("d")
                if l in ("pill", "rect1") and d is not None:
                    p = parse_path(d)
                    x0, y0, x1, y1 = p.bbox()
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    pt = translate_path(p, cx, cy)
                    pills.setdefault(layout, []).append({"d": cmd_to_d(pt), "w": x1 - x0, "h": y1 - y0})
    out = {"letters": letters, "pills": pills}
    with open("/home/bnuydev/wallgen/assets/shapes.json", "w") as f:
        json.dump(out, f, indent=1)
    print("wrote assets/shapes.json")
    for layout, kinds in letters.items():
        for k, v in kinds.items():
            print(f"  {layout} {k:10s} {v['w']:.0f}x{v['h']:.0f}".rstrip())


if __name__ == "__main__":
    main()