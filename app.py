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
PIXELS_AFTER = [1, 5, 14, 30, 35]  # 1 → 4 → 9 → 16 → +5 (5-я только в Профи)
BASE_MAX_WRONG = 4
PRO_MAX_WRONG = 5

SKIP_IDS = {f"destroy_stage_{i}" for i in range(10)} | {
    "fire_0", "fire_1", "soul_fire_0", "soul_fire_1",
    "water_still", "water_flow", "water_overlay",
    "lava_still", "lava_flow",
    "campfire_fire", "soul_campfire_fire",
}

HIDDEN_BLOCKS = {
    "vault", "vault_ominous", "trial_spawner", "ominous_item_spawner",
    "infested_stone", "infested_cobblestone", "infested_stone_bricks",
    "infested_mossy_stone_bricks", "infested_cracked_stone_bricks",
    "infested_chiseled_stone_bricks", "infested_deepslate",
    "frosted_ice",
    "light", "structure_void", "moving_piston",
    "piston_extended", "test_block", "test_instance_block",
    "chipped_anvil", "damaged_anvil",    # близнецы наковальни: только top-текстуры
    "barrier", "jigsaw", "structure_block",  # технические блоки редакторов
    "heavy_core",                         # навершие булавы
}

# Ручной выбор текстур для «Профи»: имена файлов из static/textures (без .png).
PREFERRED_TEXTURES = [
    "carrots_stage3",
    "potatoes_stage3",
    "wheat_stage7",
    "beetroots_stage3",
    "bee_nest_front",
    "beehive_front",
    "cocoa_stage2",
    "potted_azalea_bush_plant",
    "azalea_plant",
    "big_dripleaf_top",
    "small_dripleaf_stem_bottom",
    "potted_flowering_azalea_bush_plant",
    "nether_wart_stage2",
    "respawn_anchor_side4",
    "observer_front",
]

NAMES = {}
if NAMES_FILE.exists():
    NAMES = json.loads(NAMES_FILE.read_text(encoding="utf-8"))


def load_visible_pixels():
    """Индексы непрозрачных пикселей каждой текстуры — открываем только их."""
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

# ---- Категории ----
# Сравнение по ЦЕЛЫМ словам (coal_ore -> {"coal","ore"}), с учётом числа
# (carrots -> carrot). Категория ищется по id блока И по английскому названию,
# поэтому новые блоки будущих версий тоже попадают в категории.
# Порядок правил = приоритет.
CATEGORY_RULES = [
    ({"ore"}, "ore"),
    # Море раньше Света (sea_lantern) и Фермерства (turtle_egg)
    ({"coral", "prismarine", "sea", "seagrass", "kelp", "sponge", "conduit",
      "turtle", "bubble"}, "sea"),
    ({"sculk"}, "sculk"),
    # Край раньше Растений (chorus_flower)
    ({"end", "purpur", "chorus", "dragon"}, "end"),
    # Механизмы раньше Стройки (chain_command_block), Металлов (нажимные плиты)
    # и Незера (blackstone button)
    ({"redstone", "piston", "observer", "rail", "powered", "detector",
      "activator", "lever", "button", "pressure", "tripwire", "comparator",
      "repeater", "dispenser", "dropper", "hopper", "daylight", "command",
      "target", "lightning", "tnt", "slime"}, "redstone"),
    # Строительные элементы: ВСЯ семья дверей/люков/заборов/оград/цепей
    # независимо от материала. Раньше Незера (nether_brick_fence),
    # Меди (copper_door) и Металлов (iron_bars/door/trapdoor/chain).
    ({"door", "trapdoor", "fence", "gate", "bars", "chain", "ladder",
      "scaffolding"}, "construction"),
    # Незер раньше Земли (soul_sand) и Камня (blackstone, quartz)
    ({"nether", "netherrack", "soul", "magma", "basalt", "blackstone",
      "nylium", "wart", "gilded", "crying", "quartz", "debris", "bone",
      "shroomlight", "respawn", "ghast"}, "nether"),
    ({"glass"}, "glass"),
    ({"concrete"}, "concrete"),
    ({"terracotta"}, "terracotta"),
    # Медь: блоки и состояния окисления, лампы (двери/цепи — в Стройке)
    ({"copper", "malachite"}, "copper"),
    # Металлы и минералы: материалы и цельнометаллические изделия
    ({"iron", "gold", "diamond", "emerald", "lapis", "coal", "netherite",
      "raw", "amethyst", "anvil", "cauldron", "sulfur", "cinnabar"}, "metal"),
    # Фермерство раньше Дерева (melon_stem) и Света (jack_o_lantern)
    ({"wheat", "carrot", "potato", "beetroot", "melon", "pumpkin", "jack",
      "hay", "cake", "cookie", "cocoa", "berries", "honey", "honeycomb",
      "bee", "beehive", "nest", "composter", "sniffer", "farmland", "egg",
      "frogspawn"}, "farm"),
    # Дерево: доски, брёвна, таблички (без «stem» — он уводил сюда
    # ножку гриба и стебель бамбука; двери/заборы/люки — в Стройке)
    ({"planks", "log", "wood", "hyphae", "stripped", "mosaic", "sign",
      "creaking"}, "wood"),
    ({"leaves", "leaf", "sapling", "flower", "grass", "fern", "moss", "vine",
      "vines", "lichen", "bush", "sprouts", "fungus", "roots", "propagule",
      "azalea", "mushroom", "cactus", "cane", "lily", "bamboo", "stem",
      "torchflower", "pitcher", "dripleaf", "blossom", "dandelion",
      "sunflower", "poppy", "orchid", "allium", "bluet", "tulip", "daisy",
      "cornflower", "peony", "lilac", "rose", "petals", "eyeblossom",
      "wildflowers", "resin", "shrub"}, "plants"),
    ({"wool", "carpet"}, "wool"),
    ({"torch", "lantern", "lamp", "candle", "glowstone", "campfire",
      "froglight", "beacon"}, "light"),
    # Камень раньше Земли (sandstone, mud_bricks)
    ({"stone", "cobblestone", "granite", "diorite", "andesite", "tuff",
      "deepslate", "calcite", "dripstone", "obsidian", "bedrock", "bricks",
      "brick", "sandstone"}, "stone"),
    ({"dirt", "sand", "gravel", "clay", "soil", "mud", "podzol", "mycelium",
      "snow", "ice", "permafrost", "path"}, "earth"),
    ({"chest", "barrel", "shulker"}, "storage"),
    # Функциональные блоки (включая проигрыватель и нотный блок)
    ({"crafting", "enchanting", "brewing", "loom", "lectern", "cartography",
      "fletching", "smithing", "stonecutter", "grindstone", "crafter",
      "furnace", "smoker", "spawner", "lodestone", "jukebox", "note"},
     "functional"),
    ({"bed", "bookshelf", "cobweb", "web", "bell", "decorated", "skull",
      "head", "stairs", "slab", "wall"}, "deco"),
]

# Переопределения: все перечисленные слова должны быть в названии блока
# или его английском названии. Проверяются ДО общих правил.
CATEGORY_OVERRIDES = [
    ({"grass", "block"}, "earth"),     # дёрн: слово «grass» уводил бы в растения
    ({"muddy"}, "earth"),              # корни мангровa в грязи — земля
    ({"soul", "torch"}, "light"),      # факелы душ — источники света
    ({"soul", "lantern"}, "light"),
    ({"soul", "campfire"}, "light"),
    ({"flower", "pot"}, "deco"),       # цветочный горшок — декор
    ({"dragon", "head"}, "deco"),      # голова дракона — трофей, а не Край
    ({"ender", "chest"}, "storage"),   # эндер-сундук — сундук, а не Край
    ({"resin", "brick"}, "stone"),     # смоляные кирпичи — стройблок
    ({"resin", "bricks"}, "stone"),
    ({"cinnabar", "brick"}, "stone"),  # киноварные кирпичи — стройблок
    ({"cinnabar", "bricks"}, "stone"),
    ({"sulfur", "brick"}, "stone"),    # серные кирпичи (если появятся) — стройблок
    ({"sulfur", "bricks"}, "stone"),
    ({"sulfur", "tiles"}, "stone"),    # серная черепица — стройблок
    ({"chiseled", "sulfur"}, "stone"), # резная сера — стройблок
    ({"polished", "sulfur"}, "stone"),
]

# Порядок категорий в каталоге: природа -> стройка -> металлы -> живое -> миры -> техника
CATEGORY_ORDER = ["earth", "stone", "terracotta", "glass", "concrete",
                  "wood", "construction", "metal", "copper", "ore",
                  "plants", "farm", "wool", "sea", "nether", "end", "sculk",
                  "light", "redstone", "storage", "functional", "deco"]


def word_variants(word):
    """Слово + формы единственного числа (carrots -> carrot, potatoes -> potato)."""
    variants = {word}
    if len(word) > 3 and word.endswith("es"):
        variants.add(word[:-2])
    if len(word) > 2 and word.endswith("s"):
        variants.add(word[:-1])
    return variants


def category_of(block_id, en_name=""):
    """Категория по словам id блока и английского названия.
    «other» — только страховка: такие блоки печатаются при старте."""
    parts = set(block_id.lower().split("_"))
    if en_name:
        clean = en_name.lower().replace("'", " ").replace("-", " ")
        parts |= set(clean.split())
    expanded = set()
    for w in parts:
        expanded |= word_variants(w)
    for words, cat in CATEGORY_OVERRIDES:
        if set(words) <= expanded:
            return cat
    for keywords, cat in CATEGORY_RULES:
        if expanded & keywords:
            return cat
    return "other"


def normalize(text):
    return text.strip().lower().replace("ё", "е")


def fallback_name(block_id):
    return block_id.replace("_", " ").title()


def with_block(b):
    """Добавляем к блоку его настоящий id и английское название (из names.json)."""
    info = NAMES.get(b["id"], {})
    return {"id": b["id"], "ru": b["ru"], "en": b["en"],
            "block": info.get("block") or b["id"]}


def build_pools():
    """Пулы блоков: easy < medium < pro (по одной текстуре на блок)."""
    easy = [with_block(b) for b in EASY_BLOCKS
            if (TEXTURES_DIR / (b["id"] + ".png")).exists()]
    medium = easy + [with_block(b) for b in MEDIUM_BLOCKS
                     if (TEXTURES_DIR / (b["id"] + ".png")).exists()]

    used_blocks = {b["block"] for b in medium}
    best = {}  # block_key -> (ранг, имя текстуры)

    # 1. Ручной выбор — главнее любого автомата (ранг -1)
    applied = []
    for stem in PREFERRED_TEXTURES:
        info = NAMES.get(stem)
        if not info or not info.get("block"):
            print(f"Ручной выбор: '{stem}' — текстуры нет или блок не определён")
            continue
        block_key = info["block"]
        if block_key in used_blocks:
            print(f"Ручной выбор: '{stem}' пропущен — блок уже задан в лёгкой/средней (правь blocks.py)")
            continue
        if block_key in HIDDEN_BLOCKS or stem in HIDDEN_BLOCKS:
            print(f"Ручной выбор: '{stem}' пропущен — блок в HIDDEN_BLOCKS")
            continue
        best[block_key] = (-1, stem)
        applied.append(stem)
    if applied:
        print(f"Ручной выбор применён: {', '.join(applied)}")

    # 2. Автоматический выбор по рангу
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
            "block": block_key,
        })

    if TEXTURES_DIR.exists():
        missing = [b["id"] for b in EASY_BLOCKS + MEDIUM_BLOCKS
                   if not (TEXTURES_DIR / (b["id"] + ".png")).exists()]
        if missing:
            print("Внимание, нет текстур для:", ", ".join(missing))

    return {"easy": easy, "medium": medium, "pro": pro}


POOLS = build_pools()
print(f"Блоков в игре: лёгкая {len(POOLS['easy'])}, "
      f"средняя {len(POOLS['medium'])}, профи {len(POOLS['pro'])}")


def audit_categories():
    """Проверка: у каждого блока должна быть настоящая категория."""
    orphans = sorted({b["block"] for pool in POOLS.values() for b in pool
                      if category_of(b["block"], b["en"]) == "other"})
    if orphans:
        print("ВНИМАНИЕ! Блоки без категории:", ", ".join(orphans))
        print("Добавь их ключевые слова в CATEGORY_RULES.")
    else:
        print("Все блоки распределены по категориям ✓")


audit_categories()
GAMES = {}


def open_pixels(game, total):
    pool = VISIBLE.get(game["answer"]["id"]) or list(range(SIZE * SIZE))
    target = min(total, len(pool))
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
    answer = game["answer"]
    return jsonify({"category": category_of(answer["block"], answer["en"])})


@app.get("/api/catalog")
def catalog():
    difficulty = request.args.get("difficulty", "easy")
    lang = request.args.get("lang", "ru")
    key = "ru" if lang == "ru" else "en"

    groups = {}
    for b in POOLS.get(difficulty, []):
        cat = category_of(b["block"], b["en"])
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