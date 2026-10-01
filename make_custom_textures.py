# -*- coding: utf-8 -*-
"""Создаёт составные текстуры, которых нет в jar:
- stonecutter_combined   — камнерез: основание + диск пилы;
- campfire_combined      — костёр: пламя + платформа брёвен;
- soul_campfire_combined — костёр душ;
- end_rod_combined       — стержень Края вертикально.

Запускать ПОСЛЕ get_textures.py (при нём папка static/textures очищается).
Отсутствующие исходники пропускаются с предупреждением — скрипт не падает.
"""
import json
from pathlib import Path

from PIL import Image

DEST = Path("static/textures")
NAMES_FILE = DEST / "names.json"


def open_img(name, *fallbacks):
    """Открывает первую найденную текстуру из списка (или None)."""
    for n in (name, *fallbacks):
        p = DEST / n
        if p.exists():
            return Image.open(p).convert("RGBA")
    print(f"ВНИМАНИЕ: нет файла {'/'.join((name,) + fallbacks)} — сборка пропущена")
    return None


def register(stem, block, ru, en):
    names = json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    names[stem] = {"ru": ru, "en": en, "block": block, "rank": 1}
    NAMES_FILE.write_text(json.dumps(names, ensure_ascii=False, indent=1),
                          encoding="utf-8")


# --- 1. Камнерез ---
side = open_img("stonecutter_side.png")
saw = open_img("stonecutter_saw.png")
if side and saw:
    canvas = side.copy()
    canvas.paste(saw, (0, -9), saw)
    canvas.save(DEST / "stonecutter_combined.png")
    register("stonecutter_combined", "stonecutter",
             "Камнерезный станок", "Stonecutter")

# --- 2. Костёр (lit-вариант: брёвна с угольками, как у горящего) ---
fire = open_img("campfire_fire.png")
log = open_img("campfire_log_lit.png", "campfire_log.png")
if fire and log:
    canvas = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    canvas.paste(fire, (0, 0), fire)
    beam = log.crop((0, 0, 16, 6))          # верхняя полоса текстуры брёвен
    canvas.paste(beam, (0, 10), beam)
    canvas.save(DEST / "campfire_combined.png")
    register("campfire_combined", "campfire", "Костёр", "Campfire")

# --- 3. Костёр душ ---
sfire = open_img("soul_campfire_fire.png")
slog = open_img("soul_campfire_log_lit.png", "campfire_log_lit.png",
                "campfire_log.png")
if sfire and slog:
    canvas = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    canvas.paste(sfire, (0, 0), sfire)
    sbeam = slog.crop((0, 0, 16, 6))
    canvas.paste(sbeam, (0, 10), sbeam)
    canvas.save(DEST / "soul_campfire_combined.png")
    register("soul_campfire_combined", "soul_campfire", "Костёр душ", "Soul Campfire")

# --- 4. Стержень Края: колонна из самой длинной вертикальной полосы текстуры ---
rod = open_img("end_rod.png")
if rod:
    px = rod.load()
    w, h = rod.size
    # ищем столбец с максимумом непрозрачных пикселей
    best_x, best_count = 0, -1
    for x in range(w):
        c = sum(1 for y in range(h) if px[x, y][3] > 0)
        if c > best_count:
            best_x, best_count = x, c
    # берём 2 соседних столбца вокруг самого плотного (в игре стержень 2px шириной)
    x0 = max(0, min(best_x - 1, w - 2))
    strip = rod.crop((x0, 0, x0 + 2, h))
    # вытягиваем непрозрачную часть полосы на всю высоту карточки
    op = [y for y in range(h) if px[x0, y][3] > 0 or px[x0 + 1, y][3] > 0]
    if op:
        y0, y1 = min(op), max(op) + 1
        stick = rod.crop((x0, y0, x0 + 2, y1)).resize((2, 16), Image.NEAREST)
        canvas = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        canvas.paste(stick, (7, 0), stick)      # колонна по центру
        # подставка: 4x2 под колонной (серые пиксели текстуры, если есть)
        foot = rod.crop((0, 0, w, 1)).resize((4, 2), Image.NEAREST) if h > 1 else None
        if foot:
            canvas.paste(foot, (6, 14), foot)
        canvas.save(DEST / "end_rod_combined.png")
        register("end_rod_combined", "end_rod", "Стержень Края", "End Rod")

print("Сборка составных текстур завершена.")