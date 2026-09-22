"""Compositions (layouts) built from letter shapes, pills and circles.

Each item references a *role* (bg/container2/deep/dark/mid/light/accent/...)
whose final colour comes from the active Scheme. Centres are in the design
space (3840x2160).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union

R = 232.3  # circle radius from the original artwork


@dataclass
class Item:
    kind: str  # "letter" | "pill" | "circle" | "ring" | "crescent" | "arch" | "leaf"
    role: str
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    r: float = R
    layout: str = "layout1"
    letter: str = None  # which letter shape for kind=="letter"
    flip_x: bool = False
    flip_y: bool = False
    rot: float = 0.0
    hole: float = 0.66   # ring: inner radius as a fraction of r
    shift: float = 0.62  # crescent: disk offset as a fraction of r
    scale: float = 1.0   # letters only: uniform scale relative to natural size


@dataclass
class Layout:
    name: str
    items: List[Item] = field(default_factory=list)
    container: str = "panel"  # "none" | "panel" | "band"
    portrait: bool = False    # composed for tall/phone frames (rendered rotated 270)

    def letters(self):
        return [i for i in self.items if i.kind == "letter"]

    def pills(self):
        return [i for i in self.items if i.kind == "pill"]

    def circles(self):
        return [i for i in self.items if i.kind == "circle"]


LAYOUTS: Dict[str, Layout] = {}


def _L(name, container, items, portrait=False):
    lay = Layout(name, items, container, portrait)
    LAYOUTS[name] = lay
    return lay


def _L3(name, container, **centers):
    """Layout from the source artwork's own geometry."""
    items = [
        Item("letter", "deep", centers["boom"][0], centers["boom"][1], layout=name, letter="boomerang"),
        Item("letter", "mid",  centers["n"][0], centers["n"][1], layout=name, letter="n"),
        Item("letter", "deep", centers["r"][0], centers["r"][1], layout=name, letter="r"),
        Item("letter", "accent", centers["j"][0], centers["j"][1], layout=name, letter="j"),
    ]
    return _L(name, container, items)


# --- layout 1 : the original dark composition -----------------------------
_L("layout1", "panel", [
    Item("letter", "deep",   930.0, 1156.0, layout="layout1", letter="boomerang"),
    Item("letter", "mid",   1177.5, 1402.0, layout="layout1", letter="n"),
    Item("letter", "deep",  3157.5,  832.1, layout="layout1", letter="r"),
    Item("letter", "accent",2167.5, 1332.9, layout="layout1", letter="j"),
    Item("pill", "mid",   2167.5,  442.7, w=959.5, h=464.5),        # upper-center
    Item("pill", "dark",  3405.0, 1455.7, w=464.5, h=991.7),        # r-bottom
    Item("circle", "mid",    2415.0,  939.9),
    Item("circle", "accent", 2910.0, 1719.3),
    Item("circle", "accent", 3405.0,  699.8),
    Item("circle", "light",   435.0,  442.7),
])

# --- layout 2 : mirrored, balancer composition ----------------------------
_L("layout2", "band", [
    Item("letter", "deep",  2910.0, 1081.0, layout="layout2", letter="boomerang"),
    Item("letter", "mid",   1672.5, 1329.8, layout="layout2", letter="n"),
    Item("letter", "deep",   682.5, 1081.0, layout="layout2", letter="r"),
    Item("letter", "accent",2662.5,  829.2, layout="layout2", letter="j"),
    Item("pill", "accent",  1177.5, 1719.3, w=959.5, h=464.5),      # bottom-left
    Item("pill", "mid",     1672.5,  442.7, w=959.5, h=464.5),      # top-centre
    Item("circle", "light",   930.0, 1207.0),
    Item("circle", "dark",   2415.0,  442.7),
    Item("circle", "mid",    2415.0, 1719.3),
    Item("circle", "accent", 1425.0,  442.7),
])

# --- layout 3 : the warm signature (m3-brown export) -----------------------
_L("layout3", "panel", [
    Item("letter", "deep", 2910.0,  834.1, layout="layout3", letter="boomerang"),
    Item("letter", "container2", 2662.5, 1332.3, layout="layout3", letter="n"),
    Item("letter", "deep", 1672.5, 1329.8, layout="layout3", letter="r"),
    Item("letter", "mid",   930.9,  690.2, layout="layout3", letter="j"),
    Item("pill", "accent",   682.5, 1329.8, w=959.5, h=1243.5),     # big left vertical
    Item("pill", "dark",    3405.0, 1455.7, w=464.5, h=991.7),      # right bottom
    Item("pill", "container2", 682.5, 442.7, w=959.5, h=464.5),     # top-left horizontal
    Item("pill", "light",    930.0, 1575.4, w=464.5, h=752.3),      # small mid
    Item("circle", "accent",   435.0,  940.3),
    Item("circle", "dark",    1425.0, 1460.2),
    Item("circle", "container2", 1920.9, 442.7),
])


# --- layout 4 : row — the four letters in a row, straight out of the
#                original artwork but re-composed horizontally -------------
_L("row", "panel", [
    Item("letter", "deep",   720.0, 1160.0, layout="layout1", letter="boomerang"),
    Item("letter", "mid",   1540.0, 1160.0, layout="layout1", letter="n"),
    Item("letter", "dark",  2400.0, 1160.0, layout="layout1", letter="r"),
    Item("letter", "accent",3070.0, 1160.0, layout="layout1", letter="j"),
    Item("pill", "accent",  3220.0,  520.0, w=700.0, h=330.0),
    Item("pill", "container2", 620.0, 1780.0, w=480.0, h=230.0),
    Item("circle", "accent", 820.0,  620.0),
    Item("circle", "light",  3220.0, 1780.0),
])

# --- layout 5 : minimal — a single big letter, a pill and a circle ----------
_L("minimal", "none", [
    Item("letter", "mid",    970.0, 1150.0, layout="layout1", letter="boomerang"),
    Item("pill", "accent",   2640.0,  470.0, w=650.0, h=285.0),
    Item("pill", "container2", 2640.0, 1430.0, w=460.0, h=200.0),
    Item("circle", "accent", 3310.0, 1000.0),
    Item("circle", "mid",     620.0, 1730.0),
])


# --- layout 6 : quad — the four letters in the corners, bridge pill in the
#                centre ------------------------------------------------------
_L("quad", "panel", [
    Item("letter", "mid",    1000.0,  700.0, layout="layout1", letter="j"),
    Item("letter", "deep",   2900.0,  700.0, layout="layout3", letter="boomerang"),
    Item("letter", "dark",   1000.0, 1450.0, layout="layout1", letter="n"),
    Item("letter", "deep",   2900.0, 1450.0, layout="layout1", letter="r"),
    Item("pill", "accent",   1920.0, 1080.0, w=300.0, h=1560.0),   # vertical bridge
    Item("pill", "container2", 1920.0, 390.0, w=620.0, h=150.0),
    Item("circle", "accent",  420.0, 300.0),
    Item("circle", "light",  3580.0, 1650.0),
    Item("circle", "mid",    3580.0, 450.0),
])

# --- layout 7 : stack — an ascending diagonal cascade ------------------------
_L("stack", "panel", [
    Item("letter", "mid",   700.0,  720.0, layout="layout1", letter="j"),
    Item("letter", "deep",  1900.0,  830.0, layout="layout1", letter="n"),
    Item("letter", "dark",  3180.0, 1500.0, layout="layout1", letter="r"),
    Item("letter", "deep",  1100.0, 1550.0, layout="layout3", letter="boomerang"),
    Item("pill", "accent",  3100.0,  520.0, w=560.0, h=240.0),
    Item("pill", "container2", 560.0, 1780.0, w=430.0, h=200.0),
    Item("circle", "accent", 2250.0, 1900.0),
    Item("circle", "light",   250.0, 400.0),
])


# --- layout 8 : tall — a single big letter centred for portrait/phone -------
# (центральная колонка, буквы НЕ поворачиваются: рендер rotate=0 + cover-fit)
_L("tall", "panel", [
    Item("letter", "mid", 1920.0, 1080.0, layout="layout1", letter="boomerang"),
    Item("pill", "accent", 1920.0, 400.0, w=900.0, h=230.0),
    Item("pill", "container2", 1920.0, 1760.0, w=900.0, h=230.0),
    Item("circle", "accent", 1600.0, 910.0),
    Item("circle", "light", 2240.0, 1250.0),
], portrait=True)


# --- layout 9 : stacks — the letters in a vertical column (прямо, без поворота)
_L("stacks", "panel", [
    Item("letter", "accent", 1920.0, 510.0, layout="layout1", letter="j"),
    Item("letter", "mid", 1920.0, 1100.0, layout="layout1", letter="n"),
    Item("letter", "deep", 1920.0, 1690.0, layout="layout1", letter="r"),
    Item("pill", "container2", 1920.0, 380.0, w=760.0, h=210.0),
    Item("pill", "dark", 1920.0, 1780.0, w=760.0, h=210.0),
], portrait=True)


# --- layout 10 : duo — две большие буквы, переплетённые по центру -----------
_L("duo", "panel", [
    Item("letter", "mid", 1920.0, 900.0, layout="layout1", letter="n"),
    Item("letter", "accent", 1920.0, 1360.0, layout="layout1", letter="j"),
    Item("pill", "container2", 1920.0, 380.0, w=720.0, h=200.0),
    Item("pill", "dark", 1920.0, 1780.0, w=720.0, h=200.0),
    Item("circle", "accent", 1920.0, 1120.0),
], portrait=True)


# --- layout 11 : ladder — лесенка букв с лёгким смещением вбок --------------
_L("ladder", "panel", [
    Item("letter", "accent", 1760.0, 520.0, layout="layout1", letter="j"),
    Item("letter", "mid", 1920.0, 1120.0, layout="layout1", letter="n"),
    Item("letter", "deep", 2080.0, 1720.0, layout="layout1", letter="r"),
    Item("circle", "light", 1840.0, 1960.0),
    Item("pill", "container2", 1920.0, 360.0, w=680.0, h=200.0),
], portrait=True)


# --- layout 12 : garden — новые фигуры (арка/лист/кольцо/полумесяц) -----------
_L("garden", "panel", [
    Item("letter", "deep", 1200.0, 1160.0, layout="layout1", letter="boomerang"),
    Item("letter", "mid", 2950.0, 1090.0, layout="layout1", letter="n"),
    Item("arch", "container2", 820.0, 620.0, w=560.0, h=800.0),
    Item("crescent", "accent", 2870.0, 460.0, r=225.0, rot=-30.0),
    Item("ring", "light", 3060.0, 1660.0, r=205.0),
    Item("leaf", "accent", 560.0, 1590.0, w=520.0, h=360.0, rot=25.0),
    Item("pill", "container2", 1650.0, 1780.0, w=700.0, h=200.0),
    Item("circle", "accent2", 2100.0, 620.0),
    Item("circle", "dark", 2330.0, 1500.0),
])


# --- layout 13 : moon — портретная с полумесяцем и кольцом -------------------
_L("moon", "panel", [
    Item("letter", "accent", 1920.0, 900.0, layout="layout1", letter="j"),
    Item("crescent", "mid", 2240.0, 500.0, r=250.0, rot=-40.0),
    Item("ring", "light", 1560.0, 1500.0, r=230.0),
    Item("leaf", "deep", 2240.0, 1650.0, w=560.0, h=400.0, rot=10.0),
    Item("pill", "container2", 1920.0, 300.0, w=760.0, h=180.0),
    Item("pill", "dark", 1920.0, 1820.0, w=760.0, h=180.0),
    Item("circle", "container2", 1560.0, 950.0),
], portrait=True)


# --- auto: композиция, собранная по объёмным полосам фигур -------------------
def compose(portrait: bool = False, rng=None) -> Layout:
    """Build a balanced composition from shapes ranked by occupied volume.

    Delegate to the void-aware engine (autofill.build) which rasterises the
    dominant, fills its enclosed voids and greedily packs the canvas so every
    result is structurally sound and truly randomised.
    """
    from .autofill import build as _auto_build
    return _auto_build(portrait=portrait, rng=rng)


def get_layout(name: str) -> Layout:
    if name not in LAYOUTS:
        raise KeyError(f"unknown layout {name!r}; available: {', '.join(LAYOUTS)}")
    return LAYOUTS[name]