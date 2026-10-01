# -*- coding: utf-8 -*-
"""
Скачивает официальные текстуры блоков Minecraft (последняя стабильная версия)
и официальные названия блоков.

- каждая текстура помечается id блока ("block") и рангом ("rank");
- варианты (грани, состояния, направления) наследуют блок от родителя;
- обесцвеченные текстуры (листва, трава) красим цветами игры.

В конце печатается отчёт со всей воронкой.
"""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

DEST = Path("static/textures")
BLOCK_DIR = "assets/minecraft/textures/block/"

SKIP = {f"destroy_stage_{i}" for i in range(10)} | \
       {f"destroy_oit_stage_{i}" for i in range(10)} | {
    "debug", "debug2",
    "fire_0", "fire_1", "soul_fire_0", "soul_fire_1",
    "water_still", "water_flow", "water_overlay",
    "lava_still", "lava_flow",
    "attached_melon_stem", "attached_pumpkin_stem",
}
SKIP_ENDINGS = ("_overlay",)

# Служебные «хвосты» имени текстуры: грань/часть/состояние/направление,
# а не часть названия блока. Отрезаем, чтобы найти сам блок.
STRIP_WORDS = {
    # грани
    "top", "bottom", "side", "front", "back", "inner", "outer", "end",
    # состояния вкл/выкл
    "on", "off", "lit", "unlit", "empty", "full", "closed",
    # части составных блоков (кровать, костёр, кафедра, бамбук...)
    "foot", "head", "log", "leaves", "stalk", "stem", "tip", "body", "book",
    # направления (кровати, крафтер, командные блоки)
    "north", "south", "east", "west", "up", "down", "left", "right",
    # состояния блоков
    "conditional", "occupied", "compost", "ready", "crafting", "triggered",
    "ejecting", "ominous", "active", "idle", "lines", "tendril",
    # прочее служебное
    "sticky", "moist", "inverted", "cracked", "slightly", "moderately", "very",
    "plant", "hanging", "crop", "base", "save", "load", "data", "corner",
    "lower", "upper", "snow", "amethyst", "input",
    
    "hydration", "singleleaf", "large", "small",
}
# Насколько текстура хорошо «представляет» блок (меньше = лучше)
FACE_RANK = {"side": 1, "front": 2, "top": 3, "bottom": 4, "lower": 4, "upper": 4}

LEAF_GREEN = (119, 171, 47)
GRASS_GREEN = (145, 189, 89)
TINTS = {
    "oak_leaves": LEAF_GREEN,
    "jungle_leaves": LEAF_GREEN,
    "acacia_leaves": LEAF_GREEN,
    "dark_oak_leaves": LEAF_GREEN,
    "mangrove_leaves": LEAF_GREEN,
    "spruce_leaves": (97, 153, 97),
    "birch_leaves": (128, 167, 85),
    "grass_block_top": GRASS_GREEN,
    "short_grass": GRASS_GREEN,
    "tall_grass": GRASS_GREEN,
    "fern": GRASS_GREEN,
    "large_fern_top": GRASS_GREEN,
    "large_fern_bottom": GRASS_GREEN,
    "bush": GRASS_GREEN,
    "sugar_cane": GRASS_GREEN,
    "vine": LEAF_GREEN,
    "lily_pad": GRASS_GREEN,
    "melon_stem": GRASS_GREEN,
    "pumpkin_stem": GRASS_GREEN,
    "leaf_litter": (125, 120, 70),
}


def tint_for(stem):
    if stem in TINTS:
        return TINTS[stem]
    for key, rgb in TINTS.items():
        if stem.startswith(key + "_"):
            return rgb
    return None


def get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def download_ru_from_mojang(version):
    ai = version.get("assetIndex") or {}
    index_url = ai.get("url")
    if not index_url:
        return None
    try:
        index = get_json(index_url)
    except Exception as e:
        print("Не удалось получить asset-индекс:", e)
        return None
    obj = index.get("objects", {}).get("minecraft/lang/ru_ru.json")
    if not obj or "hash" not in obj:
        return None
    h = obj["hash"]
    url = f"https://resources.download.minecraft.net/{h[:2]}/{h}"
    print("Нашёл русский перевод на серверах Mojang, скачиваю...")
    try:
        return json.loads(urllib.request.urlopen(url).read())
    except Exception as e:
        print("Ошибка скачивания:", e)
        return None


def load_langs(z, version):
    lang_paths = {}
    for name in z.namelist():
        parts = name.lower().split("/")
        if len(parts) >= 2 and parts[-2] == "lang" and parts[-1].endswith(".json"):
            lang_paths[parts[-1]] = name

    en_path = lang_paths.get("en_us.json")
    if en_path is None:
        found = ", ".join(sorted(lang_paths)) or "нет json-файлов перевода"
        raise SystemExit(f"В jar не нашёлся en_us.json. Что нашлось: {found}")
    en = json.loads(z.read(en_path))

    if "ru_ru.json" in lang_paths:
        print("Русский перевод найден в jar.")
        return en, json.loads(z.read(lang_paths["ru_ru.json"]))

    ru = download_ru_from_mojang(version)
    if ru:
        print("Русский перевод успешно загружен с серверов Mojang.")
        return en, ru

    local = Path("ru_ru.json")
    if local.exists():
        print("Использую локальный файл ru_ru.json из папки проекта.")
        return en, json.loads(local.read_text(encoding="utf-8"))

    print("ВНИМАНИЕ: русский перевод получить не удалось, названия будут на английском.")
    return en, {}


def strippable(token):
    if token in STRIP_WORDS or token.isdigit() or token.startswith("stage"):
        return True
    bare = token.rstrip("0123456789")   # варианты вида side1, side2
    return bare != token and bare in STRIP_WORDS


def find_block(stem, blocks):
    """Сопоставляет текстуру с блоком напрямую. Возвращает (id блока, ранг)."""
    if stem in blocks:
        return stem, 0
    tokens = stem.split("_")
    rank = 5
    while len(tokens) > 1:
        last = tokens[-1]
        if not strippable(last):
            break
        bare = last.rstrip("0123456789")
        if bare in FACE_RANK:
            rank = min(rank, FACE_RANK[bare])
        tokens.pop()
        cand = "_".join(tokens)
        if cand in blocks:
            return cand, rank
    return None, None


def resolve_variants(mapping):
    """Текстуры-варианты без блока наследуют его от родительской текстуры,
    отрезая последнее слово, пока не найдётся сопоставленная:
    crafter_east_crafting -> crafter_east -> crafter. Повторяем проходы,
    пока что-то меняется (наследование через цепочки)."""
    inherited = 0
    changed = True
    while changed:
        changed = False
        for stem in sorted(mapping):
            if mapping[stem][0] is not None:
                continue
            tokens = stem.split("_")
            while len(tokens) > 1:
                tokens.pop()
                parent = "_".join(tokens)
                if parent in mapping and mapping[parent][0] is not None:
                    mapping[stem] = [mapping[parent][0], 5]
                    inherited += 1
                    changed = True
                    break
    return inherited


def apply_tint(path, rgb):
    img = Image.open(path).convert("RGBA")
    r, g, b, a = img.split()
    r = r.point(lambda v: v * rgb[0] // 255)
    g = g.point(lambda v: v * rgb[1] // 255)
    b = b.point(lambda v: v * rgb[2] // 255)
    Image.merge("RGBA", (r, g, b, a)).save(path)


def main():
    manifest = get_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
    version_id = manifest["latest"]["release"]
    version_url = next(v["url"] for v in manifest["versions"] if v["id"] == version_id)
    version = get_json(version_url)

    print(f"Скачиваю Minecraft {version_id}...")
    jar = urllib.request.urlopen(version["downloads"]["client"]["url"]).read()
    print("Распаковываю текстуры и переводы...")

    # Чистим папку: в ней должно быть ровно то, что скачано сейчас
    DEST.mkdir(parents=True, exist_ok=True)
    for old in DEST.glob("*.png"):
        old.unlink()

    stats = {"service": 0, "overlay": 0, "size": 0}
    total_png = 0

    with zipfile.ZipFile(io.BytesIO(jar)) as z:
        en_lang, ru_lang = load_langs(z, version)
        blocks = {}
        for key, en in en_lang.items():
            if key.startswith("block.minecraft."):
                bid = key[len("block.minecraft."):]
                blocks[bid] = {"en": en, "ru": ru_lang.get(key, en)}

        mapping = {}
        count = 0
        tinted = 0
        for name in z.namelist():
            if not name.startswith(BLOCK_DIR) or not name.endswith(".png"):
                continue
            total_png += 1
            stem = Path(name).stem
            if stem in SKIP:
                stats["service"] += 1
                continue
            if stem.endswith(SKIP_ENDINGS):
                stats["overlay"] += 1
                continue

            raw = z.read(name)
            w = int.from_bytes(raw[16:20], "big")
            h = int.from_bytes(raw[20:24], "big")
            path = DEST / f"{stem}.png"

            if (w, h) == (16, 16):
                path.write_bytes(raw)
            elif w == 16 and h % 16 == 0:
                Image.open(io.BytesIO(raw)).crop((0, 0, 16, 16)).save(path)
            else:
                stats["size"] += 1
                continue
            count += 1

            rgb = tint_for(stem)
            if rgb:
                apply_tint(path, rgb)
                tinted += 1

            mapping[stem] = list(find_block(stem, blocks))

        inherited = resolve_variants(mapping)

        names = {}
        for stem, (bid, rank) in mapping.items():
            if bid:
                ru, en = blocks[bid]["ru"], blocks[bid]["en"]
            else:
                ru = en = stem.replace("_", " ").title()
            names[stem] = {"ru": ru, "en": en, "block": bid, "rank": rank}

    (DEST / "names.json").write_text(
        json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")

    matched = sum(1 for v in names.values() if v["block"])
    unmatched = sorted(s for s, v in names.items() if not v["block"])
    unique = len({v["block"] for v in names.values() if v["block"]})

    print("---------- ОТЧЁТ ----------")
    print(f"png-файлов блоков в jar:  {total_png}")
    print(f"  сохранено:              {count}")
    print(f"  пропущено служебных:    {stats['service']} (огонь, вода, destroy_stage)")
    print(f"  пропущено накладок:     {stats['overlay']} (*_overlay)")
    print(f"  пропущено нестандартных:{stats['size']} (баннеры, щиты и т.п.)")
    print(f"Покрашено обесцвеченных:  {tinted}")
    print(f"Сопоставлено напрямую:    {matched - inherited}")
    print(f"Наследовано вариантов:    {inherited}")
    print(f"Без сопоставления:        {len(unmatched)}")
    if unmatched:
        print("  примеры:", ", ".join(unmatched[:40]))
    print(f"Уникальных блоков:        {unique}")


if __name__ == "__main__":
    main()