# -*- coding: utf-8 -*-
"""Сервер игры Guess the Block."""
import json
import random
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image

from blocks import EASY_BLOCKS, MEDIUM_BLOCKS

app = Flask(__name__)

TEXTURES_DIR = Path("static/textures")
RESULTS_FILE = Path("data/results.json")
NAMES_FILE = TEXTURES_DIR / "names.json"

SIZE = 16
# Открыто пикселей ПОСЛЕ каждой попытки: 1 → 4 → 9 → 16 → +5 (5-я только в Профи)
PIXELS_AFTER = [1, 5, 14, 30, 35]
BASE_MAX_WRONG = 4   # попыток в лёгкой и средней
PRO_MAX_WRONG = 5    # попыток в Профи

SKIP_IDS = {f"destroy_stage_{i}" for i in range(10)} | {
    "fire_0", "fire_1", "soul_fire_0", "soul_fire_1",
    "water_still", "water_flow", "water_overlay",
    "lava_still", "lava_flow",
    "campfire_fire", "soul_campfire_fire",
}

# Блоки, которые НЕ загадываем: технические, невидимые или неугадываемые
HIDDEN_BLOCKS = {
    "vault", "vault_ominous", "trial_spawner", "ominous_item_spawner",
    "infested_stone", "infested_cobblestone", "infested_stone_bricks",
    "infested_mossy_stone_bricks", "infested_cracked_stone_bricks",
    "infested_chiseled_stone_bricks", "infested_deepslate",
    "frosted_ice",
    "light", "structure_void", "moving_piston",
    "piston_extended", "test_block", "test_instance_block",
}

# Официальные названия блоков (создаёт get_textures.py)
NAMES = {}
if NAMES_FILE.exists():
    NAMES = json.loads(NAMES_FILE.read_text(encoding="utf-8"))


def load_visible_pixels():
    """Для каждой текстуры — индексы НЕПРОЗРАЧНЫХ пикселей.
    У маленьких текстур (факел, цветок, рельсы) большинство пикселей прозрачные:
    открываем случайные только среди видимых, иначе игрок может за всю игру
    так и не увидеть ни одного настоящего пикселя."""
    visible = {}
    if TEXTURES_DIR.exists():
        for png in TEXTURES_DIR.glob("*.png"):
            try:
                img = Image.open(png).convert("RGBA")
            except Exception:
                continue
            px = img.load()
            idxs = [y * SIZE + x
                    for y in range(min(img.height, SIZE))
                    for x in range(min(img.width, SIZE))
                    if px[x, y][3] > 0]
            if idxs:
                visible[png.stem] = idxs
    return visible


print("Индексирую видимые пиксели текстур...")
VISIBLE = load_visible_pixels()
print(f"Готово: {len(VISIBLE)} текстур.")

# Категории для подсказки. Порядок важен: сначала частные.
CATEGORY_RULES = [
    (("ore",), "ore"),
    (("iron", "gold", "copper", "diamond_", "emerald", "lapis", "coal_block",
      "redstone_block", "netherite", "amethyst", "raw_"), "metal"),
    (("wheat", "carrot", "potato", "beetroot", "melon", "pumpkin", "jack_o",
      "hay", "cake", "cookie", "sugar", "cocoa", "berries", "honey", "egg",
      "bee", "composter"), "farm"),
    (("planks", "log", "wood", "hyphae", "stripped", "mosaic", "door", "fence",
      "gate", "trapdoor", "sign", "stem"), "wood"),
    (("leaf", "sapling", "flower", "grass", "fern", "moss", "vine", "bush",
      "sprouts", "fungus", "roots", "propagule", "azalea", "mushroom", "crop",
      "cactus", "cane", "lily", "bamboo", "torchflower", "pitcher", "dripleaf"), "plants"),
    (("wool", "carpet"), "wool"),
    (("prismarine", "coral", "sea_", "seagrass", "kelp", "sponge", "conduit",
      "turtle", "bubble"), "sea"),
    (("nether", "soul", "magma", "basalt", "blackstone", "nylium", "wart",
      "respawn", "gilded", "crying", "quartz", "ancient_debris", "bone"), "nether"),
    (("end_", "purpur", "chorus", "dragon_egg"), "end"),
    (("torch", "lantern", "lamp", "candle", "glowstone", "shroomlight",
      "glow_", "bulb", "rod"), "light"),
    (("dirt", "sand", "gravel", "clay", "soil", "mud", "podzol", "mycelium",
      "snow", "ice", "permafrost"), "earth"),
    (("stone", "cobble", "granite", "diorite", "andesite", "tuff", "deepslate",
      "calcite", "dripstone", "obsidian", "bedrock", "bricks", "terracotta"), "stone"),
    (("furnace", "chest", "hopper", "dispenser", "dropper", "piston", "observer",
      "rail", "anvil", "cauldron", "bell", "lectern", "loom", "cartography",
      "grindstone", "smoker", "barrel", "beacon", "enchanting", "brewing",
      "command", "jukebox", "note_block", "target", "daylight", "chain",
      "campfire", "comparator", "repeater", "lever", "shulker", "table",
      "button", "pressure", "tripwire", "crafter", "stonecutter", "smithing"), "mechanism"),
]

# Ручные переопределения: проверяются ПЕРЕД общими правилами.
# Нужны там, где ключевое слово ловит не то: «egg» внутри dragon_egg,
# «stone» внутри grindstone, «fence» внутри nether_brick_fence и т.п.
# Ключ — подстрока в id текстуры, значение — категория.
CATEGORY_OVERRIDES = [
    ("dragon_egg", "end"),            # яйцо дракона: «egg» уводил в еду
    ("turtle", "sea"),                # черепашье яйцо: было «Фермерство»
    ("sniffer_egg", "other"),         # яйцо нюхача — без подходящей категории
    ("seagrass", "sea"),              # морская трава: «grass» уводил в растения
    ("grass_block", "earth"),         # дёрн: «grass» уводил в растения
    ("soul_torch", "light"),          # факел душ — как обычный факел
    ("soul_lantern", "light"),        # фонарь душ — как обычный фонарь
    ("soul_campfire", "mechanism"),   # костёр душ — как обычный костёр
    ("end_rod", "light"),             # стержень Края — источник света
    ("lightning_rod", "mechanism"),   # громоотвод — не источник света
    ("redstone_torch", "mechanism"),  # красный факел — сигнальный механизм
    ("stonecutter", "mechanism"),     # «stone» внутри слова ловил камень
    ("grindstone", "mechanism"),      # то же самое
    ("nether_brick_fence", "nether"), # «fence» уводил в дерево
]


def category_of(block_id):
    for key, cat in CATEGORY_OVERRIDES:
        if key in block_id:
            return cat
    for keywords, cat in CATEGORY_RULES:
        if any(k in block_id for k in keywords):
            return cat
    return "other"


# Порядок категорий в каталоге
CATEGORY_ORDER = ["ore", "metal", "farm", "wood", "plants", "wool", "sea",
                  "nether", "end", "light", "earth", "stone", "mechanism", "other"]


def normalize(text):
    """Ответ игрока к единому виду: нижний регистр, без ё."""
    return text.strip().lower().replace("ё", "е")


def fallback_name(block_id):
    return block_id.replace("_", " ").title()


def build_pools():
    """Пулы блоков: easy < medium < pro (по одной текстуре на блок)."""
    easy = [b for b in EASY_BLOCKS if (TEXTURES_DIR / (b["id"] + ".png")).exists()]
    medium = easy + [b for b in MEDIUM_BLOCKS if (TEXTURES_DIR / (b["id"] + ".png")).exists()]

    used_blocks = set()
    for b in medium:
        info = NAMES.get(b["id"], {})
        used_blocks.add(info.get("block") or "#" + b["id"])

    best = {}
    if TEXTURES_DIR.exists():
        for png in sorted(TEXTURES_DIR.glob("*.png")):
            stem = png.stem
            if stem in SKIP_IDS:
                continue
            info = NAMES.get(stem)
            if not info or not info.get("block"):
                continue
            block_key = info["block"]
            if block_key in used_blocks or block_key in HIDDEN_BLOCKS or stem in HIDDEN_BLOCKS:
                continue
            cand = (info.get("rank", 5), stem)
            if block_key not in best or cand < best[block_key]:
                best[block_key] = cand

    pro = list(medium)
    for block_key, (rank, stem) in sorted(best.items()):
        info = NAMES[stem]
        pro.append({
            "id": stem,
            "ru": info.get("ru") or fallback_name(stem),
            "en": info.get("en") or fallback_name(stem),
        })

    if TEXTURES_DIR.exists():
        missing = [b["id"] for b in EASY_BLOCKS + MEDIUM_BLOCKS
                   if not (TEXTURES_DIR / (b["id"] + ".png")).exists()]
        if missing:
            print("Внимание, нет текстур для:", ", ".join(missing))

    return {"easy": easy, "medium": medium, "pro": pro}


POOLS = build_pools()
GAMES = {}


def open_pixels(game, total):
    """Открываем случайные пиксели, но только среди видимых (не прозрачных)."""
    pool = VISIBLE.get(game["answer"]["id"]) or list(range(SIZE * SIZE))
    target = min(total, len(pool))  # у крошечных текстур видимых может быть меньше
    while len(game["revealed"]) < target:
        idx = random.choice(pool)
        if idx not in game["revealed"]:
            game["revealed"].append(idx)


def accepted_answers(block):
    answers = {block["ru"], block["en"]}
    official = NAMES.get(block["id"])
    if official:
        answers |= {official["ru"], official["en"]}
    return {normalize(a) for a in answers}


def save_result(game, won):
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    results = []
    if RESULTS_FILE.exists():
        try:
            results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            results = []
    results.append({
        "nickname": game["nickname"],
        "difficulty": game["difficulty"],
        "block_ru": game["answer"]["ru"],
        "block_en": game["answer"]["en"],
        "attempts": game["wrong"] + 1 if won else game["max_wrong"],
        "won": won,
        "hint": game.get("hint_used", False),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    RESULTS_FILE.write_text(json.dumps(results[-200:], ensure_ascii=False, indent=2),
                            encoding="utf-8")


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/start")
def start():
    data = request.get_json(force=True)
    difficulty = data.get("difficulty", "easy")
    if not POOLS.get(difficulty):
        return jsonify({"error": "no_textures"}), 400

    block = random.choice(POOLS[difficulty])
    game_id = uuid.uuid4().hex[:10]
    game = {
        "answer": block,
        "revealed": [],
        "wrong": 0,
        "guesses": [],
        "hint_used": False,
        "max_wrong": PRO_MAX_WRONG if difficulty == "pro" else BASE_MAX_WRONG,
        "nickname": (data.get("nickname") or "Аноним").strip()[:30],
        "difficulty": difficulty,
    }
    open_pixels(game, PIXELS_AFTER[0])
    GAMES[game_id] = game
    return jsonify({"game_id": game_id, "level": 1,
                    "revealed": game["revealed"], "guesses": [],
                    "max_wrong": game["max_wrong"]})


@app.get("/api/texture/<game_id>")
def texture(game_id):
    game = GAMES.get(game_id)
    if game is None:
        return jsonify({"error": "no_game"}), 404
    return send_file(TEXTURES_DIR / (game["answer"]["id"] + ".png"), mimetype="image/png")


@app.post("/api/guess")
def guess():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("game_id", ""))
    if game is None:
        return jsonify({"error": "no_game"}), 404
    if game.get("over"):
        return jsonify({"error": "already_over"}), 400

    answer = game["answer"]
    player_guess = normalize(data.get("guess", ""))
    correct = player_guess in accepted_answers(answer)

    if correct:
        game["over"] = True
        game["revealed"] = list(range(SIZE * SIZE))
        save_result(game, won=True)
        return jsonify({"correct": True, "over": True,
                        "attempts": game["wrong"] + 1,
                        "revealed": game["revealed"],
                        "guesses": game["guesses"], "answer": answer})

    game["wrong"] += 1
    game["guesses"].append(data.get("guess", "").strip()[:40])

    if game["wrong"] >= game["max_wrong"]:
        game["over"] = True
        save_result(game, won=False)
        game["revealed"] = list(range(SIZE * SIZE))
        return jsonify({"correct": False, "over": True, "level": game["max_wrong"],
                        "revealed": game["revealed"],
                        "guesses": game["guesses"], "answer": answer})

    level = game["wrong"] + 1
    open_pixels(game, PIXELS_AFTER[min(level, len(PIXELS_AFTER)) - 1])
    return jsonify({"correct": False, "over": False,
                    "level": level, "revealed": game["revealed"],
                    "guesses": game["guesses"]})


@app.post("/api/hint")
def hint():
    data = request.get_json(force=True)
    game = GAMES.get(data.get("game_id", ""))
    if game is None:
        return jsonify({"error": "no_game"}), 404
    if game.get("over"):
        return jsonify({"error": "already_over"}), 400
    if game.get("hint_used"):
        return jsonify({"error": "already_used"}), 400
    game["hint_used"] = True
    return jsonify({"category": category_of(game["answer"]["id"])})


@app.get("/api/catalog")
def catalog():
    """Каталог блоков, сгруппированный по категориям подсказок."""
    difficulty = request.args.get("difficulty", "easy")
    lang = request.args.get("lang", "ru")
    key = "ru" if lang == "ru" else "en"

    groups = {}
    for b in POOLS.get(difficulty, []):
        cat = category_of(b["id"])
        groups.setdefault(cat, []).append(
            {"name": b[key], "img": f"/static/textures/{b['id']}.png"})

    result = []
    for cat in CATEGORY_ORDER + sorted(set(groups) - set(CATEGORY_ORDER)):
        if cat in groups:
            items = sorted(groups[cat], key=lambda x: x["name"].lower())
            result.append({"key": cat, "items": items})
    return jsonify(result)

@app.get("/api/names")
def names():
    difficulty = request.args.get("difficulty", "easy")
    lang = request.args.get("lang", "ru")
    key = "ru" if lang == "ru" else "en"
    return jsonify(sorted({b[key] for b in POOLS.get(difficulty, [])}))


@app.get("/api/results")
def results():
    if not RESULTS_FILE.exists():
        return jsonify([])
    try:
        data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        return jsonify(data[-10:][::-1])
    except Exception:
        try:
            RESULTS_FILE.rename(RESULTS_FILE.with_name("results.broken.json"))
        except Exception:
            pass
        return jsonify([])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)