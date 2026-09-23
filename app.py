# -*- coding: utf-8 -*-
"""Сервер игры Guess the Block."""
import json
import random
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from blocks import EASY_BLOCKS, MEDIUM_BLOCKS

app = Flask(__name__)

TEXTURES_DIR = Path("static/textures")
RESULTS_FILE = Path("data/results.json")
NAMES_FILE = TEXTURES_DIR / "names.json"

SIZE = 16                       # текстуры блоков 16x16
MAX_WRONG = 4                   # 4 попытки
LEVEL_PIXELS = [1, 5, 14, 30]   # открыто пикселей после каждой попытки: 1, +4, +9, +16

SKIP_IDS = {f"destroy_stage_{i}" for i in range(10)} | {
    "fire_0", "fire_1", "soul_fire_0", "soul_fire_1",
    "water_still", "water_flow", "water_overlay",
    "lava_still", "lava_flow",
    "campfire_fire", "soul_campfire_fire",
}

# Официальные названия блоков (создаёт get_textures.py)
NAMES = {}
if NAMES_FILE.exists():
    NAMES = json.loads(NAMES_FILE.read_text(encoding="utf-8"))

# Блоки, которые НЕ загадываем: технические, невидимые или неугадываемые.
# Узнаваемые (командный блок, пазл, структурный блок) — остаются.
HIDDEN_BLOCKS = {
    # механизмы испытательных комнат
    "vault", "vault_ominous", "trial_spawner", "ominous_item_spawner",
    # заражённые блоки: текстуры идентичны обычным камням — неугадываемо
    "infested_stone", "infested_cobblestone", "infested_stone_bricks",
    "infested_mossy_stone_bricks", "infested_cracked_stone_bricks",
    "infested_chiseled_stone_bricks", "infested_deepslate",
    # выглядит как обычный лёд
    "frosted_ice",
    # невидимые и технические
    "light", "structure_void", "moving_piston",
    "piston_extended", "test_block", "test_instance_block",
}

# Категории для подсказки: (ключевые слова в id блока, категория).
# Порядок важен: сначала специфичные.
CATEGORY_RULES = [
    (("ore",), "ore"),
    (("nether", "soul", "magma", "basalt", "blackstone", "nylium", "wart",
      "glowstone", "shroomlight", "respawn", "gilded", "crying", "quartz_"), "nether"),
    (("end_stone", "purpur", "chorus", "end_rod", "dragon_egg", "end_portal"), "end"),
    (("prismarine", "coral", "sea", "kelp", "sponge"), "sea"),
    (("leaves", "sapling", "flower", "grass", "fern", "moss", "vine", "bush",
      "sprouts", "fungus", "roots", "propagule", "azalea", "mushroom", "crop",
      "wheat", "carrot", "potato", "beetroot", "melon", "pumpkin", "cactus",
      "cane", "lily", "bamboo", "torchflower", "pitcher", "dripleaf"), "plants"),
    (("planks", "log", "wood", "stem", "hyphae", "stripped", "mosaic"), "wood"),
    (("dirt", "sand", "gravel", "clay", "soil", "mud", "podzol", "mycelium",
      "snow", "ice", "permafrost"), "earth"),
    (("iron", "gold", "copper", "diamond", "emerald", "lapis", "coal",
      "redstone", "netherite", "amethyst", "raw_"), "metal"),
    (("stone", "cobble", "granite", "diorite", "andesite", "tuff", "deepslate",
      "calcite", "dripstone", "obsidian", "bedrock", "bricks", "terracotta"), "stone"),
    (("furnace", "chest", "hopper", "dispenser", "dropper", "piston", "observer",
      "rail", "anvil", "cauldron", "bell", "lectern", "loom", "cartography",
      "grindstone", "smoker", "blast", "barrel", "beacon", "enchanting",
      "brewing", "command", "jukebox", "note_block", "target", "daylight",
      "torch", "lantern", "candle", "lamp", "rod", "chain", "campfire",
      "comparator", "repeater", "lever", "shulker", "conduit", "table"), "mechanism"),
]

def category_of(block_id):
    for keywords, cat in CATEGORY_RULES:
        if any(k in block_id for k in keywords):
            return cat
    return "other"

def normalize(text):
    """Ответ игрока к единому виду: нижний регистр, без ё."""
    return text.strip().lower().replace("ё", "е")


def fallback_name(block_id):
    return block_id.replace("_", " ").title()


def build_pools():
    """Пулы блоков: easy < medium < pro.

    В «Профи» у каждого блока одна карточка: из всех его текстур (бок, верх,
    варианты) берём самую узнаваемую — по рангу из names.json.
    Текстуры, которым не нашёлся блок, в игру НЕ попадают совсем —
    поэтому мусора вида «Cartography Table Side1» больше не будет.
    """
    easy = [b for b in EASY_BLOCKS if (TEXTURES_DIR / (b["id"] + ".png")).exists()]
    medium = easy + [b for b in MEDIUM_BLOCKS if (TEXTURES_DIR / (b["id"] + ".png")).exists()]

    used_blocks = set()
    for b in medium:
        info = NAMES.get(b["id"], {})
        used_blocks.add(info.get("block") or "#" + b["id"])

    # Для каждого блока ищем лучшую текстуру: меньший ранг выигрывает,
    # при равенстве — идущая раньше по алфавиту
    best = {}  # block_key -> (ранг, имя текстуры)
    if TEXTURES_DIR.exists():
        for png in sorted(TEXTURES_DIR.glob("*.png")):
            stem = png.stem
            if stem in SKIP_IDS:
                continue
            info = NAMES.get(stem)
            if not info or not info.get("block"):
                continue  # не сопоставлена с блоком — в игру не берём
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
GAMES = {}  # id игры -> её состояние


def open_pixels(game, total):
    """Открываем случайные пиксели, пока их не станет `total`."""
    while len(game["revealed"]) < total:
        idx = random.randrange(SIZE * SIZE)
        if idx not in game["revealed"]:
            game["revealed"].append(idx)


def accepted_answers(block):
    """Все варианты ответа, которые считаем правильными:
    наши названия + официальные названия из игры."""
    answers = {block["ru"], block["en"]}
    official = NAMES.get(block["id"])
    if official:
        answers |= {official["ru"], official["en"]}
    return {normalize(a) for a in answers}


def save_result(game, won):
    """Пишем результат в data/results.json — пригодится для конкурсов."""
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
        "attempts": game["wrong"] + 1 if won else MAX_WRONG,
        "won": won,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hint": game.get("hint_used", False),
    })
    RESULTS_FILE.write_text(json.dumps(results[-200:], ensure_ascii=False, indent=2),
                            encoding="utf-8")


# ---------------- страницы и API ----------------

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
        "guesses": [],   # что игрок уже называл — показываем под картинкой
        "nickname": (data.get("nickname") or "Аноним").strip()[:30],
        "difficulty": difficulty,
        "hint_used": False,
    }
    open_pixels(game, LEVEL_PIXELS[0])  # сразу открываем 1 пиксель
    GAMES[game_id] = game
    return jsonify({"game_id": game_id, "level": 1,
                    "revealed": game["revealed"], "guesses": []})


@app.get("/api/texture/<game_id>")
def texture(game_id):
    """Отдаём текстуру загаданного блока (имя файла игроку не видно)."""
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
        game["revealed"] = list(range(SIZE * SIZE))  # победа — показываем всю текстуру
        save_result(game, won=True)
        return jsonify({"correct": True, "over": True,
                        "attempts": game["wrong"] + 1,
                        "revealed": game["revealed"],
                        "guesses": game["guesses"], "answer": answer})

    game["wrong"] += 1
    game["guesses"].append(data.get("guess", "").strip()[:40])

    if game["wrong"] >= MAX_WRONG:
        game["over"] = True
        save_result(game, won=False)
        game["revealed"] = list(range(SIZE * SIZE))
        return jsonify({"correct": False, "over": True, "level": MAX_WRONG,
                        "revealed": game["revealed"],
                        "guesses": game["guesses"], "answer": answer})

    level = game["wrong"] + 1
    open_pixels(game, LEVEL_PIXELS[level - 1])
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

@app.get("/api/names")
def names():
    """Список названий блоков для подсказок."""
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
        # Файл повреждён — убираем его в сторону, игра продолжит работать,
        # а после первой же сыгранной партии создастся свежий файл.
        try:
            RESULTS_FILE.rename(RESULTS_FILE.with_name("results.broken.json"))
        except Exception:
            pass
        return jsonify([])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)