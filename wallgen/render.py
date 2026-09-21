"""Render compositions to wallpapers.

Pipeline (all in memory, no external binaries):
  1. pycairo draws background, container(s), letters/pills/circles.
  2. Soft shadows are derived from the union alpha of the container / of all
     shapes, blurred with PIL, then painted under their layer.
  3. The final ARGB surface is read back to a PIL/numpy array and saved.

Design space is 3840x2160; any output resolution is cover-fitted and centred.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import cairo
import numpy as np
from PIL import Image, ImageFilter

from .layouts import Layout, get_layout
from .palette import Scheme
from .shapes import add_arch, add_circle, add_crescent, add_leaf, add_letter, add_pill, add_ring, background_rect, lib

DESIGN_W = 3840.0
DESIGN_H = 2160.0

SHAPE_BLUR = 85.0    # px sigma at design scale
CONTAINER_BLUR = 150.0
SHAPE_SHADOW_ALPHA = 0.43
CONTAINER_SHADOW_ALPHA = 0.50


def _rot_matrix(rot: int, mirror: bool = False) -> Tuple[Tuple[float, float, float, float, float, float], float, float]:
    """Affine (a,b,c,d,e,f) mapping design space into a DW' x DH' box that is
    then cover-fitted to the canvas. rot rotates 0/90/180/270; mirror flips the
    design horizontally about its centre."""
    if rot == 0:
        a, b, c, d = 1, 0, 0, 1
        dw, dh = DESIGN_W, DESIGN_H
        if mirror:
            a, e, f = -1, DESIGN_W, 0
        else:
            e = f = 0
    elif rot == 90:
        a, b, c, d = 0, -1, 1, 0
        dw, dh = DESIGN_H, DESIGN_W
        e, f = (0, DESIGN_H - DESIGN_W) if mirror else (0, DESIGN_H)
    elif rot == 180:
        a, b, c, d = -1, 0, 0, -1
        dw, dh = DESIGN_W, DESIGN_H
        if mirror:
            a = 1; d = -1; e, f = 0, DESIGN_H
        else:
            e, f = DESIGN_W, DESIGN_H
    else:  # 270
        a, b, c, d = 0, 1, -1, 0
        dw, dh = DESIGN_H, DESIGN_W
        e, f = (DESIGN_H, DESIGN_W) if mirror else (DESIGN_H, 0)
    return (a, b, c, d, e, f), dw, dh


def surface_to_image(surf: cairo.ImageSurface) -> Image.Image:
    surf.flush()
    buf = surf.get_data()
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(surf.get_height(), surf.get_width(), 4)
    out = np.empty_like(arr)
    out[..., 0] = arr[..., 2]  # R
    out[..., 1] = arr[..., 1]  # G
    out[..., 2] = arr[..., 0]  # B
    out[..., 3] = arr[..., 3]  # A (shapes are opaque; must un-premultiply color
    #                                  if we ever add translucent fills)
    return Image.fromarray(out, "RGBA")


def _blur_alpha(mask: np.ndarray, radius: float, shadow_color=(0, 0, 0), strength=1.0) -> Image.Image:
    """mask: (H,W) uint8 alpha. Returns RGBA image of the soft shadow."""
    m = Image.fromarray(mask, "L")
    if radius > 0.5:
        m = m.filter(ImageFilter.GaussianBlur(radius))
    a = np.asarray(m, dtype=np.float32) / 255.0 * strength
    a = np.clip(a, 0.0, 1.0)
    a = (a * 255.0).round().astype(np.uint8)
    rgba = np.empty((m.height, m.width, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = shadow_color
    rgba[..., 3] = a
    return Image.fromarray(rgba, "RGBA")


# ---------------------------------------------------------------------------
# drawing helpers (design space)
# ---------------------------------------------------------------------------

def draw_container_path(cr, style, x0, y0, x1, y1):
    if style == "panel":
        radius = min((x1 - x0), (y1 - y0)) * 0.085
        background_rect(cr, x0, y0, x1, y1, radius)
    elif style == "band":
        h = (y1 - y0) * 0.42
        cy = y0 + (y1 - y0) * 0.5
        background_rect(cr, x0, cy - h / 2, x1, cy + h / 2, h / 2)
    elif style == "side":
        w = (x1 - x0) * 0.5
        cx = x0 + (x1 - x0) * 0.28
        background_rect(cr, cx - w / 2, y0, cx + w / 2, y1, w / 2)


def _draw_all_items(cr, layout: Layout, scheme: Scheme, solid: bool = False):
    """Fill every item with its role colour (returns role -> colour map)."""
    seen: dict = {}
    order = layout.items

    def fill(i: Item):
        col = scheme.role(i.role)
        seen[i.role] = col
        if i.kind == "letter":
            add_letter(cr, lib().letter(i.letter, i.layout), i.x, i.y,
                       flip_x=i.flip_x, flip_y=i.flip_y, rot_deg=i.rot)
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
        cr.set_source_rgb(*hex_to_rgb01(col))
        cr.fill()
        if solid and i.kind == "letter":
            let = lib().letter(i.letter, i.layout)
            add_letter(cr, let, i.x, i.y, flip_x=i.flip_x, flip_y=i.flip_y, rot_deg=i.rot)
            cr.set_source_rgb(*hex_to_rgb01(col))
            cr.set_line_width(min(let.w, let.h) * 0.34)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.stroke()

    for i in order:
        fill(i)


def hex_to_rgb01(h):
    h = h.lstrip("#")
    return tuple(int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))


def _alpha(draw, cr, w, h) -> np.ndarray:
    """Union alpha (0 = background, 255 = covered) of the traced paths."""
    tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    tcr = cairo.Context(tmp)
    tcr.set_operator(cairo.OPERATOR_OVER)
    tcr.set_matrix(cr.get_matrix())
    tcr.set_source_rgb(1, 1, 1)
    draw(tcr)
    tcr.fill()
    rgba = surface_to_image(tmp)
    return np.asarray(rgba)[..., 3]


def _stroke_items(cr, layout: Layout):
    """Trace each item's path onto cr (for building masks)."""
    for i in layout.items:
        if i.kind == "letter":
            add_letter(cr, lib().letter(i.letter, i.layout), i.x, i.y,
                       flip_x=i.flip_x, flip_y=i.flip_y, rot_deg=i.rot)
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
        cr.close_path()
        cr.fill()


def render_wallpaper(
    layout: Layout,
    scheme: Scheme,
    width: int,
    height: int,
    blur: float = 1.0,
    rotate: int = 0,
    mirror: bool = False,
    solid: bool = False,
) -> Image.Image:
    """Render layout+scheme at the requested pixel size (cover-fit)."""
    rot = rotate % 360
    if rot not in (0, 90, 180, 270):
        raise ValueError("rotate must be one of 0, 90, 180, 270")

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surf)

    # background (device space, covers everything)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    bg = hex_to_rgb01(scheme.role("bg"))
    cr.set_source_rgb(*bg)
    cr.paint()

    (a, b, c, d, e, f), dw, dh = _rot_matrix(rot, mirror)
    s = max(width / dw, height / dh)
    ox = (width - dw * s) / 2
    oy = (height - dh * s) / 2
    cr.transform(cairo.Matrix(a * s, b * s, c * s, d * s, e * s + ox, f * s + oy))

    # container + container shadow
    if layout.container != "none":
        if layout.container != "panel":
            m = _alpha(lambda t: draw_container_path(t, layout.container, 0, 0, DESIGN_W, DESIGN_H),
                       cr, width, height)
            m = np.pad(m, 8)
            shadow = _blur_alpha(m, CONTAINER_BLUR * s * blur, strength=CONTAINER_SHADOW_ALPHA)
            _paint_image(cr, shadow, -8, -8, width, height)
        cr.save()
        draw_container_path(cr, layout.container, 0, 0, DESIGN_W, DESIGN_H)
        cr.set_source_rgb(*hex_to_rgb01(scheme.role("container" if layout.container == "panel" else "container2")))
        cr.fill()
        cr.restore()

    # shapes layer shadow + fill
    m = _alpha(lambda t: _stroke_items(t, layout), cr, width, height)
    m = np.pad(m, 8)
    shadow = _blur_alpha(m, SHAPE_BLUR * s * blur, strength=SHAPE_SHADOW_ALPHA)
    _paint_image(cr, shadow, -8, -8, width, height)

    _draw_all_items(cr, layout, scheme, solid)

    img = surface_to_image(surf)
    return img


def _paint_image(cr, img: Image.Image, x, y, w, h):
    tmp = cairo.ImageSurface(cairo.FORMAT_ARGB32, img.width, img.height)
    buf = tmp.get_data()
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(img.height, img.width, 4)
    rgba = np.asarray(img.convert("RGBA"))
    arr[..., 0] = rgba[..., 2]
    arr[..., 1] = rgba[..., 1]
    arr[..., 2] = rgba[..., 0]
    arr[..., 3] = rgba[..., 3]
    tmp.mark_dirty()
    cr.save()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.identity_matrix()
    cr.set_source_surface(tmp, x, y)
    cr.paint()
    cr.restore()