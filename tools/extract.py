import sys
import math

sys.path.insert(0, "/home/bnuydev/wallgen")
from lxml import etree
from wallgen.svgpath import parse_path

NS = "http://www.w3.org/2000/svg"
INS = "{http://www.inkscape.org/namespaces/inkscape}"


def elname(tag):
    return tag.split("}")[-1] if tag.startswith("{") else tag


def parse_transform(tr):
    """Return affine (a,b,c,d,e,f) mapping (x,y)->(a*x+c*y+e, b*x+d*y+f)."""
    if not tr:
        return (1, 0, 0, 1, 0, 0)
    if tr.startswith("matrix("):
        vals = [float(v) for v in tr[7:-1].split(",")]
        return tuple(vals)
    if tr.startswith("translate("):
        vals = [float(v) for v in tr[10:-1].split(",")]
        return (1, 0, 0, 1, vals[0], vals[1] if len(vals) > 1 else 0)
    if tr.startswith("rotate("):
        a = math.radians(float(tr[7:-1]))
        return (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
    if tr.startswith("scale("):
        vals = [float(v) for v in tr[6:-1].split(",")]
        sx, sy = vals[0], vals[1] if len(vals) > 1 else vals[0]
        return (sx, 0, 0, sy, 0, 0)
    raise ValueError(f"unknown transform {tr}")


def compose(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def ap(t, x, y):
    a, b, c, d, e, f = t
    return a * x + c * y + e, b * x + d * y + f


def bbox_transformed(p, t):
    bb = p.bbox()
    x0, y0, x1, y1 = bb
    pts = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    tt = [ap(t, x, y) for x, y in pts]
    xs = [q[0] for q in tt]
    ys = [q[1] for q in tt]
    return min(xs), min(ys), max(xs), max(ys)


def rect_to_path(el):
    x, y = float(el.get("x")), float(el.get("y"))
    w, h = float(el.get("width")), float(el.get("height"))
    r = float(el.get("rx") or 0) or float(el.get("ry") or 0)
    return (
        f"M {x + r} {y} H {x + w - r} A {r} {r} 0 0 1 {x + w} {y + r} "
        f"V {y + h - r} A {r} {r} 0 0 1 {x + w - r} {y + h} H {x + r} "
        f"A {r} {r} 0 0 1 {x} {y + h - r} V {y + r} A {r} {r} 0 0 1 {x + r} {y} Z"
    )


def main():
    tree = etree.parse("/home/bnuydev/wallgen/assets/m3-source.svg")
    root = tree.getroot()
    for g in root.iter(f"{{{NS}}}g"):
        label = g.get(INS + "label")
        if label not in ("layout1", "layout2", "layout3"):
            continue
        gp = parse_transform(g.get("transform"))
        print("=" * 70)
        print("LAYOUT", label)
        out = []
        for child in g:
            items = list(child) if elname(child.tag) == "g" else [child]
            for el in items:
                tag = elname(el.tag)
                l = el.get(INS + "label")
                tp = compose(gp, parse_transform(el.get("transform")))
                if tag in ("path", "rect") and el.get("d") is not None:
                    p = parse_path(el.get("d"))
                elif tag == "rect":
                    p = parse_path(rect_to_path(el))
                else:
                    continue
                bb = bbox_transformed(p, tp)
                out.append((l, bb))
        for l, bb in out:
            print(
                f"  {str(l):26s} bbox=({bb[0]:6.1f},{bb[1]:6.1f})..({bb[2]:6.1f},{bb[3]:6.1f})"
                f"  center=({(bb[0]+bb[2])/2:6.1f},{(bb[1]+bb[3])/2:6.1f})  size=({bb[2]-bb[0]:5.1f}x{bb[3]-bb[1]:5.1f})"
            )


if __name__ == "__main__":
    main()