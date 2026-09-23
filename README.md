# Guess the Block 🎮

[English](#english) | [Русский](#русский)

---

## English

Guess a Minecraft block by its texture! The game reveals 1 random pixel —
each wrong guess uncovers more of it (1 → 4 → 9 → 16). You have 4 tries to name the block.

### Features

- 3 difficulty levels: **Easy** (~36 blocks), **Medium** (~85), **Pro** (every block from the latest game version)
- Official block textures and names (EN/RU) — downloaded straight from Mojang's servers
- Answers accepted in both English and Russian; case- and ё-insensitive
- Smart search in Pro mode: partial words, any word order, keyboard-layout independent
- One "block category" hint per round
- Player nicknames + recent results list — great for community contests
- UI in English and Russian

### Quick start (Docker)

    docker compose build                                # build the image
    docker compose run --rm web python get_textures.py  # download textures (once)
    docker compose up                                   # start: http://localhost:5000

get_textures.py fetches the latest stable Minecraft release from Mojang's servers
and saves textures plus official block names to static/textures/.
When a new Minecraft version drops, just re-run the script — the block pool updates itself.

### Project structure

    guess-the-block/
    ├── app.py               # Flask server: game logic and API
    ├── blocks.py            # block lists for Easy and Medium difficulties
    ├── get_textures.py      # downloads textures and translations from Mojang
    ├── requirements.txt     # flask, gunicorn, pillow
    ├── Dockerfile
    ├── docker-compose.yml
    ├── templates/
    │   └── index.html       # game page
    └── static/
        ├── style.css
        ├── app.js           # frontend logic
        └── textures/        # created by get_textures.py (not committed)

### Customization

- Easy/Medium block lists — edit blocks.py (texture id + EN/RU names).
- Exclude blocks — add their ids to HIDDEN_BLOCKS in app.py
  (technical and unguessable blocks are already excluded: infested stones, vaults, etc.).
- Hint categories — see the CATEGORY_RULES list in app.py.

### Contest data

Every round (nickname, difficulty, block, attempts used, hint usage) is appended
to data/results.json — handy for leaderboards and community events.

---

## Русский

Угадай блок Minecraft по его текстуре! Игра показывает 1 случайный пиксель —
с каждой ошибкой открывается больше (1 → 4 → 9 → 16). 4 попытки, чтобы назвать блок.

### Возможности

- 3 сложности: **Лёгкая** (~36 блоков), **Средняя** (~85), **Профи** (все блоки текущей версии игры)
- Официальные текстуры и названия блоков (RU/EN) — скачиваются прямо с серверов Mojang
- Ответ принимается на русском и английском, регистр и «ё» не важны
- Умный поиск в режиме Профи: части слов, любой порядок слов, не зависит от раскладки
- Подсказка «категория блока» (1 раз за партию)
- Никнейм игрока + список последних результатов — удобно для конкурсов
- Интерфейс на русском и английском

### Запуск (Docker)

    docker compose build                                # сборка
    docker compose run --rm web python get_textures.py  # скачать текстуры (один раз)
    docker compose up                                   # старт: http://localhost:5000

Скрипт get_textures.py берёт последнюю стабильную версию Minecraft с серверов Mojang
и сохраняет текстуры и официальные названия в static/textures/.
Когда выйдет новая версия игры — просто запусти скрипт снова, набор блоков обновится.

### Структура проекта

    guess-the-block/
    ├── app.py               # сервер Flask: игровая логика и API
    ├── blocks.py            # списки блоков для лёгкой и средней сложности
    ├── get_textures.py      # скачивание текстур и переводов с серверов Mojang
    ├── requirements.txt     # flask, gunicorn, pillow
    ├── Dockerfile
    ├── docker-compose.yml
    ├── templates/
    │   └── index.html       # страница игры
    └── static/
        ├── style.css
        ├── app.js           # фронтенд-логика
        └── textures/        # создаётся get_textures.py (в git не входит)

### Настройка под себя

- Блоки лёгкой/средней — редактируй blocks.py (id текстуры + названия RU/EN).
- Исключить блоки из игры — добавь id в HIDDEN_BLOCKS в app.py
  (там уже исключены технические и неугадываемые: заражённые камни, vault и т.п.).
- Категории для подсказки — список CATEGORY_RULES в app.py.

### Данные конкурсов

Результаты партий (ник, сложность, блок, попытки, была ли подсказка)
сохраняются в data/results.json.

---

## License / Лицензия

The project code is free to use. Minecraft textures and names belong to Mojang
(© Mojang / Microsoft) and are fetched only from official distribution servers.
This project is not affiliated with Mojang.

Код проекта — свободный. Текстуры и названия Minecraft принадлежат Mojang
(© Mojang / Microsoft) и используются только через официальные серверы
распространения. Проект не связан с Mojang.