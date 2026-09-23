# -*- coding: utf-8 -*-
"""
Скачивает официальные текстуры блоков Minecraft (последняя стабильная версия)
и официальные названия блоков.

Каждая текстура помечается id блока ("block") и рангом ("rank") — насколько
эта текстура хорошо представляет блок. У блока бывает несколько текстур
(бок, верх, варианты вроде vault_top_ejecting), но в игру попадёт одна.

Результат:
  static/textures/*.png      — текстуры (первый кадр для анимаций)
  static/textures/names.json — {"ru", "en", "block", "rank"} для каждой текстуры
"""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

DEST = Path("static/textures")
BLOCK_DIR = "assets/minecraft/textures/block/"

SKIP = {f"destroy_stage_{i}" for i in range(10)} | {
    "fire_0", "fire_1", "soul_fire_0", "soul_fire_1",
    "water_still", "water_flow", "water_overlay",
    "lava_still", "lava_flow",
    "campfire_fire", "soul_campfire_fire",
    "attached_melon_stem", "attached_pumpkin_stem",
}
SKIP_ENDINGS = ("_overlay",)

# Служебные «хвосты» имени текстуры: грань или состояние, а не часть названия
STRIP_WORDS = {
    "top", "bottom", "side", "front", "back", "inner", "outer", "end",
    "on", "off", "sticky", "moist", "inverted", "empty", "lit",
    "cracked", "slightly", "moderately", "very",
    "plant", "hanging", "crop", "base",
    "save", "load", "data", "corner", "tendril", "active", "idle", "lines",
    "lower", "upper", "left", "right", "snow", "ominous", "ejecting",
}
# Насколько текстура хорошо «представляет» блок (меньше = лучше)
FACE_RANK = {"side": 1, "front": 2, "top": 3, "bottom": 4, "lower": 4, "upper": 4}


def get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def download_ru_from_mojang(version):
    """Русский перевод из asset-индекса — как это делает сама игра."""
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
    """Возвращает (английский словарь, русский словарь)."""
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
    """Слово — служебный хвост (грань/состояние), а не часть названия?"""
    if token in STRIP_WORDS or token.isdigit() or token.startswith("stage"):
        return True
    # Варианты вида side1, side2 — цифра «приклеилась» к слову грани
    bare = token.rstrip("0123456789")
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
    """Страховка: текстуры-варианты, которым не нашлось блока напрямую,
    наследуют его от «родительской» текстуры. Отрезаем последнее слово,
    пока не получим имя уже сопоставленной текстуры:
    vault_top_ejecting -> vault_top (у неё блок vault) -> наследуем vault."""
    for stem in sorted(mapping, key=lambda s: s.count("_")):  # короткие — первыми
        if mapping[stem][0] is not None:
            continue
        tokens = stem.split("_")
        while len(tokens) > 1:
            tokens.pop()
            parent = "_".join(tokens)
            if parent in mapping and mapping[parent][0] is not None:
                mapping[stem] = [mapping[parent][0], 5]  # ранг 5 — обычный вариант
                break


def main():
    manifest = get_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
    version_id = manifest["latest"]["release"]
    version_url = next(v["url"] for v in manifest["versions"] if v["id"] == version_id)
    version = get_json(version_url)

    print(f"Скачиваю Minecraft {version_id}...")
    jar = urllib.request.urlopen(version["downloads"]["client"]["url"]).read()
    print("Распаковываю текстуры и переводы...")

    with zipfile.ZipFile(io.BytesIO(jar)) as z:
        en_lang, ru_lang = load_langs(z, version)
        blocks = {}
        for key, en in en_lang.items():
            if key.startswith("block.minecraft."):
                bid = key[len("block.minecraft."):]
                blocks[bid] = {"en": en, "ru": ru_lang.get(key, en)}

        DEST.mkdir(parents=True, exist_ok=True)
        mapping = {}  # имя текстуры -> [id блока или None, ранг]
        count = 0
        for name in z.namelist():
            if not name.startswith(BLOCK_DIR) or not name.endswith(".png"):
                continue
            stem = Path(name).stem
            if stem in SKIP or stem.endswith(SKIP_ENDINGS):
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
                continue
            count += 1

            mapping[stem] = list(find_block(stem, blocks))

        resolve_variants(mapping)

        names = {}
        official = 0
        for stem, (bid, rank) in mapping.items():
            if bid:
                ru, en = blocks[bid]["ru"], blocks[bid]["en"]
                official += 1
            else:
                ru = en = stem.replace("_", " ").title()
            names[stem] = {"ru": ru, "en": en, "block": bid, "rank": rank}

    (DEST / "names.json").write_text(
        json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")

    unique = len({v["block"] for v in names.values() if v["block"]})
    print(f"Готово! {count} текстур, из них с официальным названием: {official}")
    print(f"Уникальных блоков: {unique}")
    print("Проверка вариантов (должно быть имя блока, без «Side1»):")
    for sample in ("cartography_table_side1", "vault_top_ejecting", "stone"):
        if sample in names:
            v = names[sample]
            print(f"  {sample} -> {v['ru']} / {v['en']} (блок: {v['block']})")


if __name__ == "__main__":
    main()