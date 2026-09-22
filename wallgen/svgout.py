"""Vector (SVG) export of a composition.

Produces a self-contained 3840x2160 SVG: background, optional container path,
soft shadows via feGaussianBlur (renders in browsers/Inkscape), and every
shape filled with its role colour from the scheme.
"""
from __future__ import annotations

import math
from xml.sax.saxutils import escape

from .layouts import Item, Layout
from .palette import Scheme
from .shapes import lib


def to_svg(layout: Layout, scheme: Scheme) -> str:
    W, H = 3840, 2160
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
        '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">',
        '<feGaussianBlur stdDeviation="85"/>',
        "</filter>",
        '<filter id="shc" x="-20%" y="-20%" width="140%" height="140%">',
        '<feGaussianBlur stdDeviation="150"/>',
        "</filter>",
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="#{_hex(scheme.role("bg"))}"/>',
    ]
    if layout.container != "none":
        ccol = scheme.role("container" if layout.container == "panel" else "container2")
        parts.append(_path_d(_container(layout), "url(#shc)", "#000000", 0.5))
        parts.append(_path_d(_container(layout), None, "#" + _hex(ccol), 1.0))
    parts.append(_path_d(_all_items_d(layout), "url(#sh)", "#000000", 0.43))
    for i in layout.items:
        parts.append(_path_d(_item_d(i), None, "#" + _hex(scheme.role(i.role)), 1.0))
    parts.append("</svg>")
    return "\n".join(parts)


def _hex(col: str) -> str:
    return col.lstrip("#")


def _path_d(d, filt, fill, opacity):
    f = f' filter="{filt}"' if filt else ""
    return f'<path d="{escape(d)}"{f} fill="{fill}" fill-opacity="{opacity}"/>'


# ---------------------------------------------------------------------------
# per-item geometry (design space 3840x2160)
# ---------------------------------------------------------------------------

def _tf(m00, m01, m10, m11, tx, ty, x, y):
    return m00 * x + m01 * y + tx, m10 * x + m11 * y + ty


def _rect_d(x0, y0, x1, y1, r):
    return (
        f"M {x0 + r:.2f} {y0:.2f} "
        f"L {x1 - r:.2f} {y0:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x1:.2f} {y0 + r:.2f} "
        f"L {x1:.2f} {y1 - r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x1 - r:.2f} {y1:.2f} "
        f"L {x0 + r:.2f} {y1:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x0:.2f} {y1 - r:.2f} "
        f"L {x0:.2f} {y0 + r:.2f} "
        f"A {r:.2f} {r:.2f} 0 0 1 {x0 + r:.2f} {y0:.2f} Z"
    )


def _letter_d(letter, i) -> str:
    a = math.radians(i.rot)
    ca, sa = math.cos(a), math.sin(a)
    sc = i.scale if hasattr(i, "scale") else 1.0
    fx = -1.0 if i.flip_x else 1.0
    fy = -1.0 if i.flip_y else 1.0
    m00, m01 = fx * sc * ca, -sc * sa
    m10, m11 = sc * sa, fy * sc * ca
    tx, ty = i.x, i.y
    out = []
    for op, *aa in letter.path.cmds:
        if op == "M":
            x, y = _tf(m00, m01, m10, m11, tx, ty, aa[0], aa[1])
            out.append(f"M {x:.2f} {y:.2f}")
        elif op == "L":
            x, y = _tf(m00, m01, m10, m11, tx, ty, aa[0], aa[1])
            out.append(f"L {x:.2f} {y:.2f}")
        elif op == "H":
            x, _ = _tf(m00, m01, m10, m11, tx, ty, aa[0], 0)
            out.append(f"H {x:.2f}")
        elif op == "V":
            _, y = _tf(m00, m01, m10, m11, tx, ty, 0, aa[0])
            out.append(f"V {y:.2f}")
        elif op == "C":
            p0 = _tf(m00, m01, m10, m11, tx, ty, aa[0], aa[1])
            p1 = _tf(m00, m01, m10, m11, tx, ty, aa[2], aa[3])
            p2 = _tf(m00, m01, m10, m11, tx, ty, aa[4], aa[5])
            out.append("C " + " ".join(f"{q:.2f} {r:.2f}" for q, r in (p0, p1, p2)))
        elif op == "Q":
            p0 = _tf(m00, m01, m10, m11, tx, ty, aa[0], aa[1])
            p1 = _tf(m00, m01, m10, m11, tx, ty, aa[2], aa[3])
            out.append("Q " + " ".join(f"{q:.2f} {r:.2f}" for q, r in (p0, p1)))
        elif op == "A":
            x, y = _tf(m00, m01, m10, m11, tx, ty, aa[0], aa[1])
            out.append(f"A {aa[2]:.2f} {aa[3]:.2f} 0 {int(aa[4])} {int(aa[5])} {x:.2f} {y:.2f}")
        elif op == "Z":
            out.append("Z")
    return " ".join(out)


def _pill_d(i: Item) -> str:
    return _rect_d(i.x - i.w / 2, i.y - i.h / 2, i.x + i.w / 2, i.y + i.h / 2, min(i.w, i.h) / 2)


def _circle_d(i: Item) -> str:
    r = i.r
    return f"M {i.x - r:.2f} {i.y:.2f} A {r:.2f} {r:.2f} 0 1 0 {i.x + r:.2f} {i.y:.2f} A {r:.2f} {r:.2f} 0 1 0 {i.x - r:.2f} {i.y:.2f} Z"


def _item_d(i: Item) -> str:
    if i.kind == "letter":
        return _letter_d(lib().letter(i.letter, i.layout), i)
    if i.kind == "pill":
        return _pill_d(i)
    return _circle_d(i)


def _all_items_d(layout: Layout) -> str:
    return " ".join(_item_d(i) for i in layout.items)


def _container(layout: Layout) -> str:
    from .render import DESIGN_H, DESIGN_W

    if layout.container == "band":
        rad = DESIGN_H * 0.21
        h = DESIGN_H * 0.42
        cy = DESIGN_H * 0.5
        return _rect_d(0, cy - h / 2, DESIGN_W, cy + h / 2, rad)
    rad = min(DESIGN_W, DESIGN_H) * 0.085
    return _rect_d(0, 0, DESIGN_W, DESIGN_H, rad)