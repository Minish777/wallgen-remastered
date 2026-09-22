"""Geometric primitives for compositions.

Letter shapes come from assets/shapes.json (normalised: their bbox center is
at (0,0)) so an instance anywhere is translate(center) + optional rotation /
flip / scale. Pills and circles are fully parametric.
"""
from __future__ import annotations

import cairo
import json
import math
import os
from typing import Dict, Tuple

import numpy as np

from .svgpath import append_to_cairo, parse_path

SHAPES_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "shapes.json")


class Letter:
    __slots__ = ("kind", "layout", "path", "w", "h")

    def __init__(self, kind: str, layout: str, path, w: float, h: float):
        self.kind = kind
        self.layout = layout
        self.path = path
        self.w = w
        self.h = h


class _Library:
    def __init__(self):
        with open(SHAPES_PATH) as f:
            data = json.load(f)
        self._letters: Dict[Tuple[str, str], Letter] = {}
        for layout, kinds in data["letters"].items():
            for kind, v in kinds.items():
                self._letters[(layout, kind)] = Letter(kind, layout, parse_path(v["d"]), v["w"], v["h"])

    def letter(self, kind: str, layout: str = "layout1") -> Letter:
        return self._letters[(layout, kind)]


_LIB: _Library | None = None


def lib() -> _Library:
    global _LIB
    if _LIB is None:
        _LIB = _Library()
    return _LIB


def background_rect(cr, x0, y0, x1, y1, radius=0.0):
    """Fill a rounded rect in user space onto the cairo context."""
    r = max(0.0, min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    if r <= 0:
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        return
    cr.move_to(x0 + r, y0)
    cr.line_to(x1 - r, y0)
    cr.arc(x1 - r, y0 + r, r, -math.pi / 2.0, 0)
    cr.line_to(x1, y1 - r)
    cr.arc(x1 - r, y1 - r, r, 0, math.pi / 2.0)
    cr.line_to(x0 + r, y1)
    cr.arc(x0 + r, y1 - r, r, math.pi / 2.0, math.pi)
    cr.line_to(x0, y0 + r)
    cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2.0)
    cr.close_path()


def add_pill(cr, cx, cy, w, h, radius=None, rot=0.0):
    """Rounded rect of size w x h centered at (cx,cy), optionally rotated (deg)."""
    if radius is None:
        radius = min(w, h) / 2.0
    cr.save()
    cr.translate(cx, cy)
    if rot:
        cr.rotate(math.radians(rot))
    background_rect(cr, -w / 2.0, -h / 2.0, w / 2.0, h / 2.0, radius)
    cr.restore()


def add_circle(cr, cx, cy, r):
    cr.save()
    cr.translate(cx, cy)
    cr.arc(0, 0, r, 0, 2 * math.pi)
    cr.restore()


def add_ring(cr, cx, cy, r, hole=0.66):
    """Donut: two concentric circles in one path; the inner one is wound the
    opposite way (cairo.arc_negative) so non-zero fill carves the hole and no
    special fill rule is required by the caller."""
    cr.save()
    cr.translate(cx, cy)
    cr.arc(0, 0, r, 0, 2 * math.pi)
    cr.arc_negative(0, 0, r * hole, 2 * math.pi, 0)
    cr.restore()


def add_crescent(cr, cx, cy, r, shift=0.62):
    """Moon: a disk carved by an offset disk; crescents open to the right.
    The carving disk is wound opposite (arc_negative) so non-zero fill gives
    the crescent without any fill-rule dependency on the caller."""
    cr.save()
    cr.translate(cx, cy)
    cr.arc(shift * r, 0, r, 0, 2 * math.pi)
    cr.arc_negative(-shift * r, 0, r * 0.92, 2 * math.pi, 0)
    cr.restore()


def add_arch(cr, cx, cy, w, h, radius=None):
    """Tombstone: semicircular dome on top, straight body, rounded feet.
    Requires w <= h so the dome doesn't eat the body."""
    r = min(w, h) / 2.0
    cr.save()
    cr.translate(cx, cy)
    R = radius if radius is not None else min(r * 0.6, h * 0.14)
    yc = -h / 2.0 + r                      # dome centre; apex sits at -h/2
    bottom = h / 2.0
    rr = max(0.0, min(R, r, bottom - yc))
    cr.move_to(-r, yc)
    cr.arc(0.0, yc, r, math.pi, 0.0)       # dome over the top (apex at -h/2)
    cr.line_to(r, bottom - rr)
    cr.arc(r - rr, bottom - rr, rr, 0.0, math.pi / 2.0)
    cr.line_to(-r + rr, bottom)
    cr.arc(-r + rr, bottom - rr, rr, math.pi / 2.0, math.pi)
    cr.close_path()
    cr.restore()


def add_leaf(cr, cx, cy, w, h):
    """Almond/leaf: two cubic lips meeting at pointed tips."""
    cr.save()
    cr.translate(cx, cy)
    hw, hh = w / 2.0, h / 2.0
    cr.move_to(-hw, 0.0)
    cr.curve_to(-hw * 0.3, -hh, hw * 0.3, -hh, hw, 0.0)
    cr.curve_to(hw * 0.3, hh, -hw * 0.3, hh, -hw, 0.0)
    cr.close_path()
    cr.restore()


def add_letter(cr, letter: Letter, cx, cy, flip_x=False, flip_y=False, rot_deg=0.0, scale=1.0):
    """Append the letter shape's path around a center, with optional mirroring."""
    cr.save()
    cr.translate(cx, cy)
    if rot_deg:
        cr.rotate(math.radians(rot_deg))
    if flip_x or flip_y:
        cr.scale(-1.0 if flip_x else 1.0, -1.0 if flip_y else 1.0)
    if scale != 1.0:
        cr.scale(scale, scale)
    cr.new_path()
    append_to_cairo(cr, letter.path)
    cr.restore()


# ---------------------------------------------------------------------------
# volume (занимаемая площадь силуэта в пикселях дизайна) и ранжирование фигур
# ---------------------------------------------------------------------------

_VOL_CACHE: Dict[Tuple, float] = {}


def _draw(kind: str, key: Tuple):
    """Return a callable that traces kind's path centered at (0,0)."""
    if kind == "letter":
        _, layout, name = key
        let = lib().letter(name, layout)
        return lambda cr: add_letter(cr, let, 0, 0), max(let.w, let.h)
    if kind == "arch":
        _, w, h = key
        return lambda cr: add_arch(cr, 0, 0, w, h), max(w, h)
    if kind == "leaf":
        _, w, h = key
        return lambda cr: add_leaf(cr, 0, 0, w, h), max(w, h)
    if kind == "crescent":
        _, r, shift = key
        return lambda cr: add_crescent(cr, 0, 0, r, shift), 2 * r * (1 + shift)
    raise KeyError(kind)


def _measure_ink(kind: str, key: Tuple) -> float:
    """Ink area (design px^2) of the shape at its natural size."""
    draw, size = _draw(kind, key)
    N = 1024
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, N, N)
    cr = cairo.Context(surf)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    scale = (N * 0.45) / max(size, 1.0)
    cr.translate(N / 2, N / 2)
    cr.scale(scale, scale)
    cr.set_source_rgb(0, 0, 0)
    draw(cr)
    cr.fill()
    surf.flush()
    buf = surf.get_data()
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(N, N, 4)
    rgb = arr[:, :, :3][:, :, ::-1].copy()
    dark = int((rgb.astype(np.float32).mean(2) < 128).sum())
    return dark / (scale * scale)


def volume(item) -> float:
    """Occupied area of an item silhouette in design-space px^2.

    Letters and the organic primitives (arch/leaf/crescent) are measured by
    rasterising silhhouette; pills/circles/rings use exact formulas. A
    `scale` (SD letter only) scales the volume by scale**2."""
    k = item.kind
    sc = (item.scale if getattr(item, "scale", None) else 1.0) if k == "letter" else 1.0
    if k == "pill":
        return max(0.0, item.w * item.h - 0.033 * min(item.w, item.h) ** 2)
    if k == "circle":
        return math.pi * item.r ** 2
    if k == "ring":
        return math.pi * item.r ** 2 * (1.0 - item.hole ** 2)
    if k == "letter":
        key = ("letter", item.layout, item.letter)
    elif k == "arch":
        key = ("arch", item.w, item.h)
    elif k == "leaf":
        key = ("leaf", item.w, item.h)
    elif k == "crescent":
        key = ("crescent", item.r, item.shift)
    else:
        return 0.0
    if key not in _VOL_CACHE:
        _VOL_CACHE[key] = _measure_ink(k, key)
    return _VOL_CACHE[key] * sc * sc


def ranked_shapes() -> list:
    """All shape families ranked by occupied volume (design px^2), biggest first."""
    rows = []
    for kind in ("w", "boomerang", "m", "n", "k", "r", "j"):
        it = type("I", (), {
            "kind": "letter", "layout": "layout1", "letter": kind,
            "w": 0, "h": 0, "r": 0, "hole": 0, "shift": 0,
        })()
        rows.append((volume(it), f"{kind} (буква)"))
    for name, kind, kw in (
        ("пилюля 960x465", "pill", dict(w=959.5, h=464.5)),
        ("арка", "arch", dict(w=560, h=800)),
        ("лист", "leaf", dict(w=520, h=360)),
        ("круг", "circle", dict(r=232.3)),
        ("кольцо", "ring", dict(r=232.3)),
        ("полумесяц", "crescent", dict(r=232.3)),
    ):
        it = type("I", (), {"kind": kind, "w": kw.get("w", 0), "h": kw.get("h", 0),
                            "r": kw.get("r", 0), "hole": 0.66, "shift": 0.62})()
        rows.append((volume(it), name))
    rows.sort(reverse=True)
    return rows