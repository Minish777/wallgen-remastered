# wallgen

Генератор авторских обоев в стиле Material You (M3).

Просто запусти без флагов — и получишь случайные обои.

## Установка

**Через pip** (требуется Python ≥ 3.10, pycairo, Pillow, numpy, lxml):

```bash
git clone https://github.com/Minish777/wallgen-remastered.git
cd wallgen-remastered
pip install -e . --break-system-packages   # системная установка
# или в виртуальном окружении:
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

**Через pipx** (изолированно, без вмешательства в системный Python):

```bash
pipx install https://github.com/Minish777/wallgen-remastered/releases/latest/download/wallgen-0.2.0-py3-none-any.whl
# или из локальной сборки:
python3 -m build && pipx install ./dist/wallgen-0.2.0-py3-none-any.whl
```

**Автоматический установщик** (создаёт venv):

```bash
./install.sh
```

**Без установки** (через встроенный лаунчер):

```bash
./bin/wallgen
```

После установки доступна команда `wallgen` из любого места.

## Примеры

<p align="center">
  <img src="examples/tall.jpg" height="240"><br>
  <em>телефон 1080×2400</em><br><br>
  <img src="examples/landscape.jpg" height="240"><br>
  <em>ПК 3840×2160</em><br><br>
  <img src="examples/auto_phone.jpg" height="240"><br>
  <em><code>auto</code> — void-aware авто-композиция</em>
</p>

| Раскладка | Формат | Описание |
|-----------|--------|----------|
| `tall` | 1080×2400 | Портретная, одна большая буква + акценты |
| `layout2` | 3840×2160 | Горизонтальная, зеркальная композиция |

## Быстрый старт

```bash
# просто занято
wallgen

# телефон
wallgen -fp 1080x2400

# тёплая тема
wallgen -t terracotta -s 1080x2400

# цвета из фотографии
wallgen -i photo.jpg -fp 1080x2400

# пачка случайных
wallgen -f -c 8 -d ~/Pix/wallgen

# авто-композиция (фигуры ранжируются по объёму)
wallgen -L auto -fp 1080x2400
```

## Флаги

- `wallgen --help` — основные флаги
- `wallgen --advanced` — полная справка
- `wallgen --version` — версия
- `wallgen --list-themes`, `--list-styles`, `--list-layouts`, `--list-shapes`

## Новое

- **Фигуры** — буквы (`boomerang`, `n`, `r`, `j`, `m`, `w`, `k`), арка, лист, кольцо, полумесяц, пилюли и круги.
- **Ранжирование по объёму** — `ranked_shapes()` сортирует все фигуры по занимаемой площади; объёмы меряются растровым силуэтом.
- **Авто-раскладка** `-L auto` — движок `autofill`: выбирает доминанту (буква или большое кольцо), растрирует её и детектирует **замкнутые пустоты** (например, дырку кольца), затем заполняет их подходящими фигурами с соблюдением кегля (толщина штриха ~ как у доминанты). Остаток канвы жадно заселяется в порядке убывания объёма при нулевых коллизиях. Каждый запуск — новая, структурно корректная композиция.
- **Телефон** `-fp WxH` — вертикальная раскладка с `rotate=0` (буквы прямо).

## Разработка

```bash
make install   # установить
make lint      # проверить синтаксис
make version   # версия
make clean     # убрать .venv и кэш
```

## Лицензия

GPL-3.0 — см. [LICENSE](LICENSE)
