"""Material You style color system for the wallpaper generator.

Generates tonal palettes (13 tones, 0..100) from a seed color the same way
Material 3 does conceptually: hue + chroma + a perceptual-lightness ramp.
One palette per colour family (primary / secondary / tertiary / neutral) and
themes are just tone assignments for the roles used by the layouts
(bg, container, deep/dark/mid/light letters, accent, accent2).

Expressive styles remap hues/chroma (tonal-spot, monochrome, rainbow,
ocean, sunset, forest, spring).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Tuple

import colorsys


# ---------------------------------------------------------------------------
# color math
# ---------------------------------------------------------------------------

def _sf(v: float) -> int:
    return max(0, min(255, int(round(v))))


def rgb255(r: float, g: float, b: float) -> str:
    return "#%02x%02x%02x" % (_sf(r), _sf(g), _sf(b))


def hex_to_rgb(h: str) -> Tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hue(r: float, g: float, b: float) -> float:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return h * 360


def srgb_from_y(y: float) -> float:
    y = max(0.0, min(1.0, y))
    if y <= 0.0031308:
        return 12.92 * y
    return 1.055 * (y ** (1 / 2.4)) - 0.055


def tone_to_y(tone: float) -> float:
    """Perceptual tone (0..100) -> linear luminance Y."""
    tone = max(0.0, min(100.0, tone))
    if tone <= 8:
        return tone / 8 * 0.0031308 * 0.9  # near black
    yy = ((tone + 16) / 116) ** 3
    return yy


def tonal(hue: float, chroma: float, tone: float, power: float = 0.7) -> str:
    """A Material-ish tonal colour.

    hue: 0..360 degrees, chroma: 0..1, tone: 0..100.
    The colour is built in HLS so that perceptual lightness follows the
    Material curve and chroma peaks mid-tones and dies toward 0/100.
    """
    t = max(0.0, min(1.0, tone / 100.0))
    y = tone_to_y(tone)
    # HLS lightness approximates the perceptual tone mapped to sRGB value
    l = y ** 0.55
    l = max(0.0, min(1.0, l))
    env = math.sin(math.pi * t) ** power
    s = chroma * (0.22 + 0.78 * t) * env * 2.2
    s = min(1.0, s)
    # keep extremely light/dark nearly neutral
    if l > 0.93:
        s *= (1.0 - (l - 0.93) / 0.07) * 0.6
    r, g, b = colorsys.hls_to_rgb(hue / 360, l, s)
    return rgb255(r * 255, g * 255, b * 255)


TONES = [0, 4, 6, 8, 12, 16, 20, 24, 28, 32, 36, 40, 50, 60, 68, 70, 80, 90, 95, 98, 100]


@dataclass
class Family:
    name: str
    hue: float
    chroma: float

    def tonal(self, tone: float, power: float = 0.7) -> str:
        return tonal(self.hue, self.chroma, tone, power)

    def ramp(self) -> Dict[int, str]:
        return {t: self.tonal(t) for t in TONES}


# ---------------------------------------------------------------------------
# scheme
# ---------------------------------------------------------------------------

ROLE_KEYS = ["bg", "container", "deep", "dark", "mid", "light", "accent", "accent2", "on_accent"]


@dataclass
class Scheme:
    name: str
    mode: str  # "dark" | "light"
    seed: str
    families: Dict[str, Family] = field(default_factory=dict)
    roles: Dict[str, str] = field(default_factory=dict)

    def role(self, key: str) -> str:
        return self.roles[key]

    def summary(self) -> str:
        parts = [f"{k}={self.roles[k]}" for k in ROLE_KEYS if k in self.roles]
        return f"{self.name}/{self.mode} seed={self.seed} :: " + " ".join(parts)


def make_schemes(
    seed: str = "#b25d36",
    mode: str = "dark",
    style: str = "tonal-spot",
    hue_shift: float = 0.0,
) -> Dict[str, Scheme]:
    seed_rgb = hex_to_rgb(seed)
    base_hue = (rgb_to_hue(*seed_rgb) + hue_shift) % 360

    if style == "ocean":
        base_hue = 190.0
    elif style == "sunset":
        base_hue = 25.0
    elif style == "forest":
        base_hue = 138.0
    elif style == "spring":
        base_hue = 300.0
    elif style == "gem":
        base_hue = 262.0

    if style == "rainbow":
        families = {
            "primary": Family("primary", 0, 0.42),
            "secondary": Family("secondary", 55, 0.38),
            "tertiary": Family("tertiary", 140, 0.36),
            "neutral": Family("neutral", 30, 0.06),
            "surface": Family("surface", 20, 0.14),
        }
    elif style == "monochrome":
        families = {
            "primary": Family("primary", base_hue, 0.0),
            "secondary": Family("secondary", base_hue, 0.0),
            "tertiary": Family("tertiary", base_hue, 0.0),
            "neutral": Family("neutral", base_hue, 0.0),
            "surface": Family("surface", base_hue, 0.0),
        }
    else:
        chroma = 0.10 if style == "soft" else 0.30
        families = {
            "primary": Family("primary", base_hue, 0.34),
            "secondary": Family("secondary", (base_hue + 60) % 360, 0.30),
            "tertiary": Family("tertiary", (base_hue + 140) % 360, 0.28),
            "neutral": Family("neutral", base_hue, chroma),
            "surface": Family("surface", base_hue, max(chroma + 0.10, 0.20)),
        }
        if style == "bw":
            for f in families.values():
                f.chroma = 0.0

    schemes: Dict[str, Scheme] = {}
    if mode in ("dark", "both"):
        sc = Scheme(f"{seed}-dark", "dark", seed, families)
        n = families["neutral"]
        sf = families["surface"]
        p = families["primary"]
        sc.roles = {
            "bg": n.tonal(11),
            "container": sf.tonal(36, power=0.6),
            "container2": sf.tonal(24),
            "deep": n.tonal(13),
            "dark": n.tonal(16),
            "mid": n.tonal(27),
            "light": n.tonal(37),
            "accent": p.tonal(79),
            "accent2": families["tertiary"].tonal(70),
            "on_accent": n.tonal(6),
        }
        schemes["dark"] = sc
    if mode in ("light", "both"):
        sc = Scheme(f"{seed}-light", "light", seed, families)
        n = families["neutral"]
        sf = families["surface"]
        p = families["primary"]
        sc.roles = {
            "bg": n.tonal(96),
            "container": sf.tonal(88),
            "container2": sf.tonal(92),
            "deep": p.tonal(46),
            "dark": n.tonal(38),
            "mid": n.tonal(28),
            "light": n.tonal(18),
            "accent": p.tonal(50),
            "accent2": families["tertiary"].tonal(60),
            "on_accent": n.tonal(98),
        }
        schemes["light"] = sc
    return schemes


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------

THEME_PRESETS = {
    "brown": "#8a6749",
    "terracotta": "#b25d36",
    "amber": "#b07d28",
    "teal": "#0f6b5c",
    "sage": "#5c7a62",
    "moss": "#4a6e3a",
    "azure": "#2b6ea8",
    "ocean": "#126a86",
    "indigo": "#3f51b5",
    "purple": "#7a4f9e",
    "magenta": "#a04c84",
    "rose": "#b45a72",
    "cherry": "#a81f3d",
    "crimson": "#8f2c3c",
    "slate": "#4a5568",
    "graphite": "#3a4250",
    "mono": "#525252",
}

STYLES = ["tonal-spot", "monochrome", "soft", "rainbow", "ocean", "sunset", "forest", "spring", "gem", "bw"]


# ---------------------------------------------------------------------------
# random seed colours (curated so random output always looks decent)
# ---------------------------------------------------------------------------

PRETTY_SEEDS = [
    "#b25d36",  # terracotta
    "#b07d28",  # amber
    "#a34b3f",  # rust
    "#b0506f",  # rosewood
    "#9b4dca",  # orchid
    "#7a4f9e",  # purple
    "#4a6bb0",  # periwinkle
    "#2b6ea8",  # azure
    "#126a86",  # deep ocean
    "#0f6b5c",  # teal
    "#3e9c5a",  # emerald
    "#5c7a62",  # sage
    "#6e5aa8",  # violet
    "#b0619e",  # berry
    "#8a6749",  # leather
    "#bf5757",  # coral
]


def random_seed(rng=None) -> str:
    """A random but guaranteed-decent seed colour."""
    from random import Random

    r = rng if rng is not None else Random()
    if r.random() < 0.35:
        # fully random hue but keep it within nice chroma/lightness bands
        import colorsys

        hue = r.uniform(0, 360)
        sat = r.uniform(0.45, 0.75)
        li = r.uniform(0.40, 0.58)
        rr, gg, bb = colorsys.hls_to_rgb(hue / 360, li, sat)
        return rgb255(rr * 255, gg * 255, bb * 255)
    return r.choice(PRETTY_SEEDS)


# ---------------------------------------------------------------------------
# seed from an image (like real Material You wallpaper extraction)
# ---------------------------------------------------------------------------

def seed_from_image(path: str) -> Tuple[str, str]:
    """Extract (seed, accent) hex colours from a photo.

    seed   — the most representative mid-tone colour (drives the palette).
    accent — the most vivid / colourful colour among the frequent ones.
    """
    from PIL import Image
    import colorsys

    img = Image.open(path).convert("RGB")
    img.thumbnail((96, 96))
    q = img.quantize(colors=24, method=2)
    palette = q.getpalette()
    counts = sorted(q.getcolors() or [], reverse=True)

    def lum8(r, g, b):
        return int(0.2126 * r + 0.7152 * g + 0.0722 * b)

    colours = []
    for count, idx in counts[:24]:
        r, g, b = palette[idx * 3:idx * 3 + 3]
        l = lum8(r, g, b)
        if l < 40 or l > 230:
            continue
        h, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0], \
               colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[2]
        colours.append((count, r, g, b, l, s))

    if not colours:
        px = img.convert("RGB").resize((1, 1)).getpixel((0, 0))
        return rgb255(*px), rgb255(*px)

    # seed: frequent + colourful, mild preference for mid lightness
    seed_col = max(colours, key=lambda t: t[0] * (1.0 + 0.7 * t[5]) - abs(t[4] - 120) * 0.004 * t[0])
    # accent: same colours, chase max saturation instead (still frequent enough)
    pool = sorted(colours, key=lambda t: t[0], reverse=True)[:10]
    accent_col = max(pool, key=lambda t: t[5])
    return (rgb255(seed_col[1], seed_col[2], seed_col[3]),
            rgb255(accent_col[1], accent_col[2], accent_col[3]))