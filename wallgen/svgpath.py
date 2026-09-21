"""SVG path parsing and cairo-path building.

Supports the full command set (MmLlHhVvCcSsQqTtAaZz). The parser yields
command records with *absolute* coordinates. Also provides a tiny bounding-box
tracker so layouts can be introspected, and a cairo-builder with the SVG
elliptical-arc -> cairo arc conversion.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Tuple

_NUM = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?"
_NUMRE = re.compile(_NUM)
_STREAM = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(" + _NUM + r")|[\s,]+")
_ARGS = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7}

# Command record: ("OP", a0, a1, a2, a3, a4, a5, a6)
#   M: x y | L: x y | H: x | V: y | C: x1 y1 x2 y2 x y
#   Q: x1 y1 x y | A: x y rx ry phi laf sf | Z: none
Cmd = Tuple[str, float, float, float, float, float, float, float]


@dataclass
class Path:
    cmds: List[Cmd] = field(default_factory=list)

    def bbox(self, samples: int = 8) -> Tuple[float, float, float, float]:
        xs: List[float] = []
        ys: List[float] = []
        x = y = 0.0
        start = (0.0, 0.0)
        pen = False

        def emit(px: float, py: float) -> None:
            xs.append(px)
            ys.append(py)

        for c in self.cmds:
            op, *a = c
            if op == "M":
                x, y = a[0], a[1]
                start = (x, y)
                emit(x, y)
            elif op == "L":
                x, y = a[0], a[1]
                emit(x, y)
            elif op == "H":
                x = a[0]
                emit(x, y)
            elif op == "V":
                y = a[0]
                emit(x, y)
            elif op == "C":
                x, y = a[4], a[5]
                emit(x, y)
            elif op == "Q":
                x, y = a[2], a[3]
                emit(x, y)
            elif op == "A":
                xn, yn, rx, ry, phi, laf, sf = a
                for k in range(samples + 1):
                    # sample points on the arc in the ellipse frame
                    theta = _endpoint_angle(x, y, xn, yn, rx, ry, phi, laf, sf, k / samples)
                    cx, cy = _center(x, y, xn, yn, rx, ry, phi, laf, sf)[0:2]
                    xx = cx + rx * math.cos(phi) * math.cos(theta) - ry * math.sin(phi) * math.sin(theta)
                    yy = cy + rx * math.sin(phi) * math.cos(theta) + ry * math.cos(phi) * math.sin(theta)
                    emit(xx, yy)
                x, y = xn, yn
            elif op == "Z":
                x, y = start
        if not xs:
            return 0.0, 0.0, 0.0, 0.0
        return min(xs), min(ys), max(xs), max(ys)

    def center(self) -> Tuple[float, float]:
        x0, y0, x1, y1 = self.bbox()
        return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _token_stream(d: str):
    i = 0
    n = len(d)
    pending: List[str] = []
    while i < n:
        if pending:
            yield pending.pop()
            continue
        m = _STREAM.match(d, i)
        if m is None:
            i += 1
            continue
        if m.group(1):
            yield m.group(1)
        elif m.group(2):
            yield m.group(2)
        i = m.end()


def _parse_args(d: str, i: int, count: int):
    out: List[float] = []
    while count > 0 and i < len(d):
        m = _STREAM.match(d, i)
        if m.group(1):
            break
        if m.group(2):
            out.append(float(m.group(2)))
            count -= 1
        i = m.end()
    return out, i


def parse_path(d: str) -> Path:
    p = Path()
    i = 0
    n = len(d)
    cmd: str | None = None
    x, y = 0.0, 0.0
    start = (0.0, 0.0)
    ctl: Tuple[float, float] | None = None  # last curve control point

    while i < n:
        m = _STREAM.match(d, i)
        if m is None:
            i += 1
            continue
        if m.group(1):
            cmd = m.group(1)
            i = m.end()
            if cmd in "Zz":
                p.cmds.append(("Z", 0, 0, 0, 0, 0, 0, 0))
                x, y = start
                ctl = None
                continue
        elif m.group(2):
            if cmd is None:
                cmd = "L"
            pass  # implicit continuation handled below
        else:
            i = m.end()
            continue  # advance the number-less cursor

        upper = cmd.upper()
        args, i = _parse_args(d, i, _ARGS.get(upper, 0))
        if len(args) < _ARGS.get(upper, 0):
            continue

        rel = cmd.islower()
        X, Y = (x, y) if rel else (0.0, 0.0)

        if upper == "M":
            nx, ny = X + args[0], Y + args[1]
            p.cmds.append(("M", nx, ny, 0, 0, 0, 0, 0))
            x, y = nx, ny
            start = (nx, ny)
            ctl = None
            cmd = "l" if rel else "L"
        elif upper == "L":
            nx, ny = X + args[0], Y + args[1]
            p.cmds.append(("L", nx, ny, 0, 0, 0, 0, 0))
            x, y = nx, ny
            ctl = None
        elif upper == "H":
            x = X + args[0]
            p.cmds.append(("H", x, 0, 0, 0, 0, 0, 0))
            ctl = None
        elif upper == "V":
            y = Y + args[0]
            p.cmds.append(("V", y, 0, 0, 0, 0, 0, 0))
            ctl = None
        elif upper == "C":
            a0, a1, a2, a3, a4, a5 = args
            x1, y1, x2, y2, nx, ny = X + a0, Y + a1, X + a2, Y + a3, X + a4, Y + a5
            p.cmds.append(("C", x1, y1, x2, y2, nx, ny, 0))
            ctl = (x2, y2)
            x, y = nx, ny
        elif upper == "S":
            a0, a1, a2, a3 = args
            x2, y2, nx, ny = X + a0, Y + a1, X + a2, Y + a3
            if ctl is None:
                x1, y1 = x, y
            else:
                x1, y1 = 2 * x - ctl[0], 2 * y - ctl[1]
            p.cmds.append(("C", x1, y1, x2, y2, nx, ny, 0))
            ctl = (x2, y2)
            x, y = nx, ny
        elif upper == "Q":
            a0, a1, a2, a3 = args
            qx, qy, nx, ny = X + a0, Y + a1, X + a2, Y + a3
            p.cmds.append(("Q", qx, qy, nx, ny, 0, 0, 0))
            ctl = (qx, qy)
            x, y = nx, ny
        elif upper == "T":
            nx, ny = X + args[0], Y + args[1]
            if ctl is None:
                qx, qy = x, y
            else:
                qx, qy = 2 * x - ctl[0], 2 * y - ctl[1]
            p.cmds.append(("Q", qx, qy, nx, ny, 0, 0, 0))
            ctl = (qx, qy)
            x, y = nx, ny
        elif upper == "A":
            rx, ry, phi, laf, sf, nx, ny = args
            nx_, ny_ = X + nx, Y + ny
            if (rx, ry) == (0, 0) or (nx_, ny_) == (x, y):
                p.cmds.append(("L", nx_, ny_, 0, 0, 0, 0, 0))
            else:
                p.cmds.append(("A", nx_, ny_, rx, ry, math.radians(phi), laf, sf))
            x, y = nx_, ny_
            ctl = None
        if upper in ("M", "L", "H", "V", "T"):
            pass  # these can implicitly repeat; handled via loop naturally
    return p


# ---------------------------------------------------------------------------
# Arc math
# ---------------------------------------------------------------------------


def _center(x1, y1, xn, yn, rx, ry, phi, laf, sf):
    """Endpoint -> center parameterization. Returns (cx, cy, rx, ry, phi)."""
    cos, sin = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - xn) / 2.0, (y1 - yn) / 2.0
    xp = cos * dx + sin * dy
    yp = -sin * dx + cos * dy
    rx, ry = abs(rx), abs(ry)
    lam = (xp * xp) / (rx * rx) + (yp * yp) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
    num = max(rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp, 0.0)
    den = rx * rx * yp * yp + ry * ry * xp * xp
    coef = 0.0 if den == 0 else math.sqrt(num / den)
    if laf == sf:
        coef = -coef
    cxp = coef * (rx * yp / ry)
    cyp = coef * (-ry * xp / rx)
    cx = cos * cxp - sin * cyp + (x1 + xn) / 2.0
    cy = sin * cxp + cos * cyp + (y1 + yn) / 2.0
    return cx, cy, rx, ry, phi


def _endpoint_angle(x1, y1, xn, yn, rx, ry, phi, laf, sf, t):
    """Interpolate the arc parameter theta at t in [0,1]."""
    cx, cy, rx, ry, phi = _center(x1, y1, xn, yn, rx, ry, phi, laf, sf)
    cos, sin = math.cos(phi), math.sin(phi)

    def angle_at(px, py):
        Qx = (cos * (px - cx) + sin * (py - cy)) / rx
        Qy = (-sin * (px - cx) + cos * (py - cy)) / ry
        return math.atan2(Qy, Qx)

    t1 = angle_at(x1, y1)
    t2 = angle_at(xn, yn)
    delta = t2 - t1
    if sf == 1:
        while delta < 0:
            delta += 2 * math.pi
    else:
        while delta > 0:
            delta -= 2 * math.pi
    return t1 + delta * t


# ---------------------------------------------------------------------------
# cairo builder
# ---------------------------------------------------------------------------


def append_to_cairo(ctx, path: Path, k: float = 1.0) -> None:
    """Append an SVG path to a cairo context, scaled by k (design units)."""
    x, y = 0.0, 0.0
    start = (0.0, 0.0)
    pen = False
    ctx.new_path()
    for c in path.cmds:
        op, *a = c
        if op == "M":
            x, y = a[0] * k, a[1] * k
            start = (x, y)
            pen = True
            ctx.move_to(x, y)
        elif op == "L":
            x, y = a[0] * k, a[1] * k
            ctx.line_to(x, y)
        elif op == "H":
            x = a[0] * k
            ctx.line_to(x, y)
        elif op == "V":
            y = a[0] * k
            ctx.line_to(x, y)
        elif op == "C":
            ctx.curve_to(a[0] * k, a[1] * k, a[2] * k, a[3] * k, a[4] * k, a[5] * k)
            x, y = a[4] * k, a[5] * k
        elif op == "Q":
            ctx.curve_to(a[0] * k, a[1] * k, a[0] * k, a[1] * k, a[2] * k, a[3] * k)
            x, y = a[2] * k, a[3] * k
        elif op == "A":
            na = (a[0] * k, a[1] * k, a[2], a[3], a[4], a[5], a[6])
            _append_arc(ctx, x, y, *na)
            x, y = a[0] * k, a[1] * k
        elif op == "Z":
            ctx.close_path()
            if pen:
                x, y = start


def _append_arc(ctx, x1, y1, xn, yn, rx, ry, phi, laf, sf, segs: int = 24):
    for k in range(1, segs + 1):
        t = _endpoint_angle(x1, y1, xn, yn, rx, ry, phi, laf, sf, k / segs)
        cx, cy, rxx, ryy, _ = _center(x1, y1, xn, yn, rx, ry, phi, laf, sf)
        xx = cx + rxx * math.cos(phi) * math.cos(t) - ryy * math.sin(phi) * math.sin(t)
        yy = cy + rxx * math.sin(phi) * math.cos(t) + ryy * math.cos(phi) * math.sin(t)
        ctx.line_to(xx, yy)


def path_to_cairo_path(path: Path, k: float = 1.0):
    """Return a draw(ctx) function that appends the (scaled) path geometry."""

    def draw(ctx) -> None:
        append_to_cairo(ctx, path, k)

    return draw