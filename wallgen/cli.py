"""wallgen CLI – generate a wallpaper with a single command.

Examples
--------
wallgen                                # random nice wallpaper, no flags needed
wallgen -L layout1 -t terracotta -s 3840x2160 -o wallpaper.jpg
wallgen --random --dir ~/Pictures/wallgen
wallgen --fun --count 8 --dir ~/Pictures/wallgen
wallgen --from-image photo.jpg -L layout3 -W 1080 -H 2400
wallgen --batch -o wallgen_{layout}_{mode}.jpg
"""
from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from .layouts import LAYOUTS, get_layout, compose
from .shapes import ranked_shapes

__version__ = "0.1.0"
from .palette import (
    STYLES,
    THEME_PRESETS,
    make_schemes,
    random_seed,
    seed_from_image,
)
from .render import render_wallpaper

IMG_EXTS = (".png", ".jpg", ".jpeg")

import os

_DEFAULT_DIR = None


def _default_dir() -> Path:
    """/home, если туда можно писать; иначе — домашняя папка; иначе ./out."""
    global _DEFAULT_DIR
    if _DEFAULT_DIR is None:
        for cand in (Path("/home"), Path.home(), Path("out")):
            try:
                cand.mkdir(parents=True, exist_ok=True)
                if os.access(cand, os.W_OK):
                    _DEFAULT_DIR = cand
                    break
            except OSError:
                continue
        if _DEFAULT_DIR is None:
            _DEFAULT_DIR = Path("out")
    return _DEFAULT_DIR


DEFAULT_DIR = _default_dir()


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

_SUPPRESS = argparse.SUPPRESS

# --- основной набор флагов (простая справка: wallgen --help) ---------------
_MAIN_SPEC = [
    ("Основное", ("-t", "--theme"), dict(default=None, choices=list(THEME_PRESETS),
                             help="тема-цвет; без неё — случайный")),
    ("Основное", ("-s", "--size"), dict(default="3840x2160", metavar="WxH",
                            help="размер в пикселях, например 1080x2400")),
    ("Основное", ("-c", "--count"), dict(type=int, default=1, metavar="N",
                             help="сколько обоев сгенерировать подряд")),
    ("Основное", ("-fp",), dict(default=None, metavar="WxH",
                            help="обои под телефон: размер WxH + вертикальная раскладка")),
    ("Основное", ("-d", "--dir"), dict(default=None, metavar="DIR",
                           help="куда сохранять (по умолчанию /home)")),
    ("Основное", ("-i", "--img", "--from-image"), dict(default=None, metavar="FILE",
                                           help="вытянуть гамму прямо из фотографии")),
    ("Основное", ("-f", "--fun"), dict(action="store_true",
                           help="полный рандом: раскладка + стиль + цвета + зеркало")),
]

# --- дополнительный набор (справка: wallgen --advanced) --------------------
# each: (group, opts, kwargs)
_ADV_SPEC = [
    ("Цвет и палитра", ("--seed",), dict(default=None, metavar="#RRGGBB",
                                          help="исходный цвет палитры вручную")),
    ("Цвет и палитра", ("--accent",), dict(default=None, metavar="#RRGGBB",
                                            help="перебить акцентный цвет")),
    ("Цвет и палитра", ("--style",), dict(choices=STYLES, default=None,
                                           help="стиль гаммы; без него 'tonal-spot'")),
    ("Цвет и палитра", ("--list-themes",), dict(action="store_true",
                                                 help="показать темы и выйти")),
    ("Цвет и палитра", ("--list-styles",), dict(action="store_true",
                                                 help="показать стили и выйти")),
("Композиция", ("-L", "--layout"), dict(default="random",
                                              choices=list(LAYOUTS) + ["random", "auto"],
                                              help="раскладка; 'auto' — собирается по объёму фигур; для портрета 'random' берёт tall/stacks")),
    ("Композиция", ("--container",), dict(default=None, choices=["none", "panel", "band"],
                                            help="подложка: none / panel / band")),
    ("Композиция", ("--mirror",), dict(action="store_true",
                                         help="отзеркалить композицию")),
    ("Композиция", ("--rotate",), dict(type=int, default=None, choices=[0, 90, 180, 270],
                                         help="поворот; авто 270 для портрета (H>W)")),
    ("Композиция", ("-l", "--list-layouts"), dict(action="store_true",
                                                    help="показать раскладки и выйти")),
    ("Композиция", ("--list-shapes",), dict(action="store_true",
                                              help="показать фигуры, отсортированные по объёму, и выйти")),
    ("Выход и формат", ("--mode",), dict(choices=["dark", "light", "both"], default="dark",
                                         help="режим гаммы; 'both' — тёмный и светлый")),
    ("Выход и формат", ("-o", "--out"), dict(default=None,
                                             help="файл .png/.jpg либо папка")),
    ("Выход и формат", ("--svg",), dict(default=None, metavar="FILE",
                                        help="дополнительно сохранить векторный SVG")),
    ("Выход и формат", ("--batch",), dict(action="store_true",
                                          help="прогнать все раскладки подряд")),
    ("Эффекты", ("--blur",), dict(type=float, default=None, metavar="0..1.5",
                                  help="мягкость теней (по умолчанию 1.0)")),
    ("Эффекты", ("-x", "--solid"), dict(action="store_true",
                                        help="жирная обводка букв (сплошные блоки)")),
    ("Служебное", ("-v", "--verbose"), dict(action="store_true",
                                            help="печатать гамму и путь")),
]


def _add_group(p, name, specs, suppress=False):
    g = p.add_argument_group(name)
    for entry in specs:
        group, opts, kw = entry
        if suppress and "help" in kw:
            kw = dict(kw)
            kw["help"] = _SUPPRESS
        g.add_argument(*opts, **kw)
    return g


def _full_parser():
    """Полная справка (wallgen --advanced): все флаги с пояснениями."""
    p = argparse.ArgumentParser(
        prog="wallgen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Все флаги wallgen. Основные — без флагов или wallgen --help.",
    )
    _add_group(p, "Цвет и палитра",
               [s for s in _ADV_SPEC if s[0] == "Цвет и палитра"])
    _add_group(p, "Композиция",
               [s for s in _ADV_SPEC if s[0] == "Композиция"])
    _add_group(p, "Выход и формат",
               [s for s in _ADV_SPEC if s[0] == "Выход и формат"])
    _add_group(p, "Эффекты",
               [s for s in _ADV_SPEC if s[0] == "Эффекты"])
    _add_group(p, "Служебное",
               [s for s in _ADV_SPEC if s[0] == "Служебное"])
    return p


def _main_parser():
    p = argparse.ArgumentParser(
        prog="wallgen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
description="Генератор обоев в стиле Material You (M3).\n"
                    "Просто набери wallgen — и получишь случайные авторские обои.\n"
                    "Темы:    wallgen --list-themes\n"
                    "Стили:   wallgen --list-styles\n"
                    "Раскладки: %s\n"
                    "Авто:    wallgen -L auto — растеризует доминанту, заполняет её пустоты и заселяет канву по объёму"
                     % ", ".join(f"{n}{'*' if l.portrait else ''}"
                                 for n, l in LAYOUTS.items()),
         epilog="Примеры:\n"
                "  wallgen                              просто занятно\n"
                "  wallgen -t terracotta -s 1080x2400   телефон, тёплая гамма\n"
                "  wallgen -fp 1080x2400                обои под телефон\n"
                "  wallgen -i photo.jpg                 цвета из фотографии\n"
                "  wallgen -f -c 8 -d ~/Pix/wallgen     пачка случайных\n"
                "  wallgen -L auto -fp 1080x2400        авто-композиция под телефон\n\n"
                "Все флаги — wallgen --advanced",
    )
    _add_group(p, "Основное", _MAIN_SPEC)
    _add_group(p, "Дополнительно", _ADV_SPEC, suppress=True)
    p.add_argument("-help", action="help", help=_SUPPRESS)  # alias для -h/--help
    p.add_argument("--advanced", action="store_true",
                   help="показать полную справку (все флаги)")
    p.add_argument("--version", action="version",
                   version=f"wallgen {__version__}")
    return p


_parser = None


def build_parser():
    global _parser
    if _parser is None:
        _parser = _main_parser()
    return _parser


# ---------------------------------------------------------------------------
# output paths
# ---------------------------------------------------------------------------

def _is_file_out(args):
    return (args.out or "").lower().endswith(IMG_EXTS)


def _target_dir(args) -> Path:
    d = args.dir or args.out or DEFAULT_DIR
    return Path(d) if not _is_file_out(args) else Path(d).parent


def _subst(template: str, *, theme, layout, mode, idx, seed) -> str:
    return (template.replace("{theme}", theme)
                    .replace("{layout}", layout)
                    .replace("{mode}", mode)
                    .replace("{seed}", seed.lstrip("#")))


def _out_path(args, theme, layout, mode, idx, seed) -> str:
    if _is_file_out(args):
        base = _subst(args.out, theme=theme, layout=layout, mode=mode, idx=idx, seed=seed)
        if args.count and args.count > 1:
            p = Path(base)
            base = str(p.with_name(f"{p.stem}_{idx:03d}{p.suffix}"))
        Path(base).parent.mkdir(parents=True, exist_ok=True)
        return base
    d = _target_dir(args)
    d.mkdir(parents=True, exist_ok=True)
    ext = "png" if (args.out or "").lower().endswith(".png") else "jpg"
    index = f"_{idx:03d}" if args.count and args.count > 1 else ""
    name = f"wallgen_{layout}_{theme}_{mode}{index}.{ext}"
    return str(d / name)


# ---------------------------------------------------------------------------
# rendering one wallpaper
# ---------------------------------------------------------------------------

def run_one(layout_name, theme, mode, out_path, seed, width, height, blur, rotate,
            mirror, container, style, svg=None, verbose=False, solid=False, accent=None):
    t0 = time.time()
    schemes = make_schemes(seed, mode, style)
    scheme = schemes["dark" if mode == "dark" else "light"]
    if accent:
        scheme.roles["accent"] = accent
        scheme.roles["accent2"] = accent
    if verbose:
        print("  " + scheme.summary())

    if layout_name == "auto":
        layout = compose(portrait=height > width)
    else:
        layout = get_layout(layout_name)
    if container is not None:
        layout.container = container

    img = render_wallpaper(layout, scheme, width, height, blur=blur, rotate=rotate,
                           mirror=mirror, solid=solid)
    if out_path.lower().endswith(".png"):
        img.convert("RGB").save(out_path, "PNG")
    else:
        img.convert("RGB").save(out_path, "JPEG", quality=94)
    if svg:
        from .svgout import to_svg
        Path(svg).parent.mkdir(parents=True, exist_ok=True)
        Path(svg).write_text(to_svg(layout, scheme))
    if verbose:
        print(f"  saved {out_path}  ({width}x{height})  {time.time() - t0:.2f}s")
    return out_path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)

    if args.advanced:
        _full_parser().print_help()
        return

    if args.list_shapes:
        for v, n in ranked_shapes():
            print(f"  {v:10.0f}  {n}")
        return
    if args.list_layouts:
        for name, lay in LAYOUTS.items():
            mark = "  (portrait)" if lay.portrait else ""
            print(f"  {name:10s}  container={lay.container}{mark}")
        return
    if args.list_themes:
        for name, col in THEME_PRESETS.items():
            print(f"  {name:12s} {col}")
        return
    if args.list_styles:
        for s in STYLES:
            print(f"  {s}")
        return

    def _parse_size(size: str):
        try:
            w, h = (int(x) for x in size.lower().split("x"))
        except ValueError:
            raise SystemExit(f"wallgen: неверный размер '{size}' — ожидается WxH "
                             "например 3840x2160")
        return w, h

    phone = args.fp is not None
    width, height = _parse_size(args.fp or args.size)

    # which knobs did the user touch explicitly?
    user = {
        "layout": args.layout != "random",
        "theme": args.theme is not None or args.seed is not None or args.img is not None,
        "style": args.style is not None,
        "mode": args.mode != "dark",
        "mirror": args.mirror,
        "blur": args.blur is not None,
        "container": args.container is not None,
    }

    layouts = list(LAYOUTS) if args.batch else [args.layout]

    def _random_layout():
        if not _bag:
            _bag.extend(random.sample(_pool, len(_pool)))
        return _bag.pop()

    _pool = ([n for n, l in LAYOUTS.items() if l.portrait] + ["auto", "auto"]
             if (phone or height > width)
             else list(LAYOUTS) + ["auto", "auto"]) or list(LAYOUTS)
    _bag: list = []

    idx = 0
    written: list[str] = []
    for _ in range(args.count):
        for layout_name in layouts:
            if layout_name == "random":
                layout_name = _random_layout()

            style = args.style
            if not user["style"]:
                style = random.choice(STYLES) if args.fun else "tonal-spot"

            if layout_name == "auto":
                layout_obj = compose(portrait=phone or height > width)
            else:
                layout_obj = get_layout(layout_name)
            if args.rotate is not None:
                rotate = args.rotate
            elif layout_obj.portrait:
                rotate = 0          # вертикальная колонка, буквы прямо
            else:
                rotate = 270 if height > width else 0

            modes = ["dark", "light"] if args.mode == "both" else [args.mode]
            if not user["mode"] and args.fun:
                modes = [random.choice(["dark", "dark", "dark", "light"])]

            mirror = args.mirror
            if not user["mirror"] and args.fun and random.random() < 0.5:
                mirror = True

            container = args.container
            if container is None and args.fun:
                container = random.choice([None, "panel", "band"])

            blur = args.blur
            if blur is None:
                blur = random.uniform(0.75, 1.25) if args.fun else 1.0

            accent = args.accent
            if args.img:
                seed, auto_accent = seed_from_image(args.img)
                accent = args.accent if args.accent else auto_accent
            elif args.seed:
                seed = args.seed
            elif args.theme:
                seed = THEME_PRESETS[args.theme]
            else:
                seed = random_seed()

            theme = args.theme or seed.lstrip("#")

            for mode in modes:
                idx += 1
                out_path = _out_path(args, theme, layout_name, mode, idx, seed)
                svg = None
                if args.svg:
                    svg = args.svg.replace("{theme}", theme).replace("{layout}", layout_name)
                run_one(layout_name, theme, mode, out_path, seed, width, height,
                        blur, rotate, mirror, container, style, svg=svg,
                        verbose=args.verbose, solid=args.solid, accent=accent)
                written.append(out_path)
                explicit_target = bool(args.dir or _is_file_out(args))
                if not explicit_target and not args.verbose:
                    print(f"  сохранил: {out_path}")

    if args.batch:
        pp = Path(written[0]).parent
        print(f"  wrote {len(written)} wallpapers into {pp}")

    return written


if __name__ == "__main__":
    main()