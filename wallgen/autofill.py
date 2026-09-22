"""Void-aware automatic composition.

Idea: pick a *dominant* letter, rasterise it, and find its voids (empty
pockets fully surrounded by ink — the counter of a boomerang, the bowl gap of
n/r/j).  We then fill those voids with smaller shapes AND greedily pack mid
and accent shapes into the remaining empty canvas.  Ordering is by occupied
volume (big->small) and each placed shape is checked on a boolean grid for
zero ink collision.  A "кегль" sanity constraint keeps the scaled stroke
weight comparable to the dominant's, so nothing reads as out-of-size type.

This is a genuinely combinatorial result (not a fixed template): every run is
different yet structurally sound.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, Tuple

import cairo
import numpy as np

from .layouts import Item, Layout
from .shapes import (
    add_arch, add_circle, add_crescent, add_leaf, add_letter, add_pill, add_ring, lib,
    _PRIMITIVES,
)

DESIGN_W = 3840.0
DESIGN_H = 2160.0

GRID = 12          # design px per grid cell
GW = int(DESIGN_W // GRID)   # 320
GH = int(DESIGN_H // GRID)   # 180

R = 232.3
_PORTRAIT_X_LO, _PORTRAIT_X_HI = 1300.0, 2620.0   # central column actually visible


def _natural(kind: str, **kw) -> Tuple[float, float]:
    """(w, h) of the shape's bounding box in design px at natural scale."""
    if kind == "letter":
        let = lib().letter(kw["letter"], kw.get("layout", "layout1"))
        return (let.w, let.h)
    if kind == "arch" or kind == "leaf":
        return (kw.get("w", 560), kw.get("h", 420))
    if kind == "crescent":
        return (kw.get("r", 232) * (1 + kw.get("shift", 0.62)) + kw.get("r", 232), 2 * kw.get("r", 232))
    if kind == "pill":
        return (kw.get("w", 640), kw.get("h", 240))
    if kind in _PRIMITIVES:
        r = kw.get("r", 232)
        size = 2.6 * r if kind == "puffy" else 2.0 * r
        return (size, size)
    return (2 * kw.get("r", 232), 2 * kw.get("r", 232))          # ring / circle


def _trace(cr, i: Item):
    if i.kind == "letter":
        add_letter(cr, lib().letter(i.letter, i.layout), i.x, i.y,
                   flip_x=i.flip_x, flip_y=i.flip_y, rot_deg=i.rot,
                   scale=i.scale if hasattr(i, "scale") else 1.0)
    elif i.kind == "pill":
        add_pill(cr, i.x, i.y, i.w, i.h)
    elif i.kind == "circle":
        add_circle(cr, i.x, i.y, i.r)
    elif i.kind == "ring":
        add_ring(cr, i.x, i.y, i.r, i.hole)
    elif i.kind == "crescent":
        add_crescent(cr, i.x, i.y, i.r, i.shift)
    elif i.kind == "arch":
        add_arch(cr, i.x, i.y, i.w, i.h)
    elif i.kind == "leaf":
        add_leaf(cr, i.x, i.y, i.w, i.h)
    elif i.kind in _PRIMITIVES:
        _PRIMITIVES[i.kind](cr, i.x, i.y, i.r, rot=getattr(i, "rot", 0.0))


def _mask(*items) -> np.ndarray:
    """Boolean ink mask (GH x GW) of the items on the design grid."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, GW, GH)
    cr = cairo.Context(surf)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.scale(1.0 / GRID, 1.0 / GRID)
    for i in items:
        _trace(cr, i)
    cr.set_source_rgb(0, 0, 0)
    cr.fill()
    buf = surf.get_data()
    arr = np.frombuffer(buf, np.uint8).reshape(GH, GW, 4)
    return arr[:, :, 0] < 128


_TILE_CACHE: Dict[Tuple, Tuple[np.ndarray, int, int]] = {}


def _tile(item) -> Tuple[np.ndarray, int, int]:
    """Cached local mask of `item` plus its design-space cell anchor.

    Renders the shape once into a tight grid buffer centred on (0,0); placement
    then shifts this tile by whole cells, so the packer never redraws a shape
    mask per trial position.  The shape scale is quantised to GRID-sized steps
    so repeated/neighbouring scales collapse onto the same cached tile. Returns
    (tile, row0, col0) — top-left cell offset from the shape centre.
    """
    qs = round(getattr(item, "scale", 1.0) * (100.0 / GRID)) / (100.0 / GRID) if item.kind == "letter" else None
    key = (item.kind,
           (item.letter, item.layout, qs) if item.kind == "letter" else
           (round(item.w, 1), round(item.h, 1), round(item.r, 1),
            round(getattr(item, "hole", 0.66), 3), round(getattr(item, "shift", 0.62), 3),
            round(getattr(item, "rot", 0.0), 1)))
    if key in _TILE_CACHE:
        return _TILE_CACHE[key]

    base = _item_of(item)
    if item.kind == "letter":
        base.scale = qs
    nw, nh = _natural(item.kind, w=base.w, h=base.h, r=base.r, shift=base.shift,
                      layout=base.layout, letter=base.letter)
    sc = base.scale if base.kind == "letter" else 1.0
    nw, nh = nw * sc, nh * sc
    hc = max(int(np.ceil(min(nh, 3000) / GRID)) + 2, 3)
    wc = max(int(np.ceil(min(nw, 3000) / GRID)) + 2, 3)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, wc * GRID, hc * GRID)
    cr = cairo.Context(surf)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.scale(1.0 / GRID, 1.0 / GRID)
    cr.translate(wc * GRID / 2.0, hc * GRID / 2.0)
    _trace(cr, base)
    cr.set_source_rgb(0, 0, 0)
    cr.fill()
    arr = np.frombuffer(surf.get_data(), np.uint8).reshape(hc * GRID, wc * GRID, 4)
    tile = arr[:, :, 0] < 128
    tile = tile.reshape(hc, GRID, wc, GRID).any(3).any(1)

    _TILE_CACHE[key] = (tile, -(hc // 2), -(wc // 2))
    return _TILE_CACHE[key]


def _item_of(it) -> Item:
    """A placement-free copy respecting item.scale so caching is stable."""
    base = Item(it.kind, "", 0.0, 0.0,
                w=getattr(it, "w", 0), h=getattr(it, "h", 0), r=getattr(it, "r", 0),
                shift=getattr(it, "shift", 0.62), hole=getattr(it, "hole", 0.66),
                rot=getattr(it, "rot", 0.0))
    if it.kind == "letter":
        base = Item("letter", "", 0.0, 0.0, layout=it.layout, letter=it.letter)
        base.scale = it.scale if hasattr(it, "scale") else 1.0
    return base


def _place_mask(occ: np.ndarray, item: Item) -> bool:
    """Try to fold `item` into occ (zero collision); True if placed."""
    tile, row0, col0 = _tile(item)
    th, tw = tile.shape
    cy = int(round(item.y / GRID)) + row0
    cx = int(round(item.x / GRID)) + col0
    if cy < 0 or cx < 0 or cy + th > GH or cx + tw > GW:
        return False
    window = occ[cy:cy + th, cx:cx + tw]
    if int(np.logical_and(window, tile).sum()) > 0:
        return False
    window |= tile
    return True


def _stroke(item) -> float:
    """Approximate stroke weight (кегль) in design px."""
    W = 360
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, W)
    cr = cairo.Context(surf)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    scl = item.scale if item.kind == "letter" else 1.0
    attrs = dict(w=getattr(item, "w", 0), h=getattr(item, "h", 0),
                 r=getattr(item, "r", 0), shift=getattr(item, "shift", 0.62),
                 hole=getattr(item, "hole", 0.66))
    nw = attrs["w"] if item.kind in ("arch", "leaf", "pill") else (
        (item.r * (1 + 0.62) + item.r) if item.kind == "crescent" else 2 * item.r)
    nh = attrs["h"] if item.kind in ("arch", "leaf", "pill") else (
        2 * item.r if item.kind == "crescent" else 2 * item.r)
    if item.kind in _PRIMITIVES:
        size = 2.6 * item.r if item.kind == "puffy" else 2.0 * item.r
        nw = nh = size
    if item.kind == "letter":
        from .shapes import lib as _l
        let = _l().letter(item.letter, item.layout)
        nw, nh = let.w * scl, let.h * scl
    size = max(nw, nh)
    if size <= 0:
        return 0.0
    s = (W * 0.42) / size
    cr.translate(W / 2, W / 2)
    cr.scale(s, s)
    if item.kind == "letter":
        add_letter(cr, lib().letter(item.letter, item.layout), 0, 0,
                   rot_deg=getattr(item, "rot", 0), scale=scl)
    else:
        _trace(cr, Item(item.kind, "", 0, 0,
                        w=attrs["w"], h=attrs["h"], r=attrs["r"],
                        shift=attrs["shift"], hole=attrs["hole"]))
    cr.set_source_rgb(0, 0, 0)
    cr.fill()
    buf = surf.get_data()
    arr = np.frombuffer(buf, np.uint8).reshape(W, W, 4)[:, :, 0] < 128
    pad = np.pad(arr, 1)
    bg = ~pad
    border = np.sum((bg[:-2, 1:-1] | bg[2:, 1:-1] | bg[1:-1, :-2] | bg[1:-1, 2:]) & arr)
    ink = int(arr.sum())
    return 2.0 * ink / max(border, 1) / s


def _voids(mask: np.ndarray, min_area: int = 24) -> List[Tuple[int, int, int, int]]:
    """Enclosed empty pockets fully surrounded by ink.

    The outer background (the component reaching the canvas border) is the
    open canvas; everything else is a void the composition can host a shape
    in. Returns (y0, x0, y1, x1) grid-rects (exclusive), largest first.
    """
    seen = np.zeros_like(mask, bool)
    out: List[Tuple[int, int, int, int]] = []
    for sy in range(GH):
        for sx in range(GW):
            if mask[sy, sx] or seen[sy, sx]:
                continue
            q = deque([(sy, sx)])
            seen[sy, sx] = True
            cells = []
            border = False
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                if cy in (0, GH - 1) or cx in (0, GW - 1):
                    border = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = cy + dy, cx + dx
                    if 0 <= yy < GH and 0 <= xx < GW and not mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        q.append((yy, xx))
            if not border and len(cells) >= min_area:
                cy0 = min(p[0] for p in cells); cy1 = max(p[0] for p in cells) + 1
                cx0 = min(p[1] for p in cells); cx1 = max(p[1] for p in cells) + 1
                out.append((cy0, cx0, cy1, cx1))
    out.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    return out


def _sized(kind: str, scale: float, **kw) -> Item:
    """Build an Item of `kind`, scaled to fit (bbox = natural * scale, centered at origin)."""
    kw = dict(kw)
    if kind == "letter":
        it = Item(kind, "", 0, 0, **kw)
        it.scale = scale
        return it
    kw.setdefault("w", 560)
    kw.setdefault("h", 420)
    kw.setdefault("r", 232.3)
    item = Item(kind, "", 0, 0, **kw)
    w, h = _natural(kind, **kw)
    if kind in ("arch", "leaf", "pill"):
        item.w, item.h = w * scale, h * scale
    else:
        item.r = item.r * scale
    return item


def _plot(occ: np.ndarray, item: Item) -> np.ndarray:
    """Return occ | item — via cached tile placement (origin-relative)."""
    _place_mask(occ, item)
    return occ


def fingerprint(layout) -> Tuple:
    """Structural signature of a composition: kinds, roles, positions and
    sizes of every item. Two layouts with the same fingerprint render the
    same shape arrangement (differences smaller than rounding are ignored)."""
    rows = []
    for i in layout.items:
        if i.kind == "letter":
            sz = (i.letter, i.layout, round(getattr(i, "scale", 1.0) or 1.0, 2))
        elif i.kind in ("arch", "leaf", "pill"):
            sz = (round(i.w), round(i.h))
        else:
            sz = (round(i.r, 1), round(getattr(i, "rot", 0.0) or 0.0))
        rows.append((i.kind, i.role, round(i.x), round(i.y), sz))
    return tuple(sorted(rows))


# ---------------------------------------------------------------------------
# composition driver
# ---------------------------------------------------------------------------

LETTERS = ("boomerang", "n", "r", "j", "m", "w", "k")
ROLES_HIER = ("deep", "mid", "dark", "container2", "accent", "accent2", "light")


def build(portrait: bool = False, rng=None) -> Layout:
    """Fully automatic, void- and volume-aware composition."""
    from .shapes import volume

    rng = rng or random

    # 1) dominant: a big letter, or an oversized ring whose hollow gets filled.
    if portrait:
        dom_letter = rng.choice(["n", "n", "r", "j", "k", "boomerang"])
    else:
        dom_letter = rng.choice(["w", "boomerang", "boomerang", "m", "n", "k"])
    if rng.random() < 0.22 and not portrait:
        dominant = Item("ring", "deep", 1920.0, 1080.0, r=480.0)
    else:
        dominant = Item("letter", "deep", 1920.0, 1080.0, layout="layout1", letter=dom_letter)
        if portrait:
            dominant.scale = 1.15 if dom_letter in ("n", "r", "j", "k") else 1.0

    items = [dominant]
    occ = np.zeros((GH, GW), bool)
    _place_mask(occ, dominant)
    dom_stroke = _stroke(dominant)

    def try_place(item, x, y) -> bool:
        item.x, item.y = x, y
        if not _place_mask(occ, item):
            return False
        items.append(item)
        return True

    def scale_for_void(kind, void, **kw):
        y0, x0, y1, x1 = void
        vw, vh = (x1 - x0) * GRID, (y1 - y0) * GRID
        nw, nh = _natural(kind, **kw)
        if nw <= 0 or nh <= 0:
            return 0.0
        return min(vw * 0.9 / nw, vh * 0.9 / nh)

    # 2) fill the dominant's voids with smaller shapes
    voids = _voids(occ)
    for void in voids[:4]:
        cx = (void[1] + void[3]) / 2.0 * GRID
        cy = (void[0] + void[2]) / 2.0 * GRID
        kind = rng.choice(["letter", "letter", "letter", "arch", "leaf", "ring",
                           "crescent", "squircle", "square", "diamond", "puffy"])
        role = rng.choice(["mid", "container2", "dark"])
        kw = {}
        if kind == "letter":
            kw = dict(layout="layout1", letter=rng.choice([k for k in LETTERS if k != dom_letter]))
        elif kind == "arch":
            kw = dict(w=560, h=800)
        elif kind == "leaf":
            kw = dict(w=560, h=400)
        s = scale_for_void(kind, void, **kw)
        if s <= 0:
            continue
        s *= rng.uniform(0.55, 0.75)
        item = _sized(kind, s, **kw)
        item.role = role
        if kind == "letter" and _stroke(item) < dom_stroke * 0.30:
            continue
        for jx, jy in ((0, 0), (GRID * 0.6, 0), (-GRID * 0.6, 0), (0, GRID * 0.6), (0, -GRID * 0.6)):
            if try_place(item, cx + jx, cy + jy):
                break

    # 3) greedily pack mid + accent shapes into remaining open canvas
    mids = [k for k in LETTERS if k != dom_letter]
    rng.shuffle(mids)
    pack_plan = []
    for m in mids:
        pack_plan.append(("letter", dict(layout="layout1", letter=m), 1.0))
    for k in ("arch", "crescent", "ring", "leaf", "circle", "pill", "circle",
              "square", "triangle", "pentagon", "diamond", "squircle",
              "hexagon", "arrow", "puffy", "softburst", "circle"):
        pack_plan.append((k, {}, 1.0))

    x_lo, x_hi = (0.0, DESIGN_W)
    if portrait:
        x_lo, x_hi = _PORTRAIT_X_LO, _PORTRAIT_X_HI

    dom_vol = volume(dominant)
    for kind, kw, _bs in pack_plan:
        placed = False
        for attempt in range(60):
            # scale degrades each try so big shapes still get a chance first
            s = 1.0 - 0.45 * (attempt // 20)
            s = max(s, 0.28)
            if kind == "letter":
                s *= rng.uniform(0.55, 0.8)
            x = rng.uniform(x_lo + 260, x_hi - 260)
            y = rng.uniform(320, DESIGN_H - 320)
            item = _sized(kind, s, **kw)
            item.role = rng.choice(["accent", "accent2", "light", "container2"])
            if kind == "arrow":
                item.rot = rng.choice([0, 90, 180, 270, 45, 135])
            if volume(item) > dom_vol * 0.6:
                continue
            if not try_place(item, x, y):
                continue
            placed = True
            break

    # 4) anchor pills (portrait keeps bottom/top rails, landscape a soft band)
    anchor_role = "dark" if not portrait else "container2"
    kw = dict(w=920, h=200) if not portrait else dict(w=780, h=180)
    y_anchor = 1860 if not portrait else 300
    if portrait:
        for _ in range(2):
            ay = rng.choice([300, 1810])
            aitem = _sized("pill", 1.0, **kw)
            aitem.role = anchor_role
            for jx in (0, GRID * 2, -GRID * 2):
                if try_place(aitem, 1920 + jx, ay):
                    break

    return Layout("auto", items, "panel", portrait)