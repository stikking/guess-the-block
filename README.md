# Guess the Block 🎮

[English](#english) | [Русский](#русский)

---

## Русский

Угадай блок Minecraft по его текстуре! Игра показывает 1 случайный пиксель —
с каждой ошибкой открывается больше (1 → 4 → 9 → 16). 4 попытки, чтобы назвать блок.

### Возможности

- 3 сложности: Лёгкая, Средняя, Профи (все блоки текущей версии игры)
- Официальные текстуры и названия блоков (RU/EN) — скачиваются прямо с серверов Mojang
- Ввод ника — алиас Telegram
- Ответ принимается на русском и английском, регистр и «ё» не важны
- Умный поиск в режиме Профи: части слов, любой порядок слов, не зависит от раскладки
- Подсказка «категория блока» (до 2 категорий на блок)
- Каталог блоков по категориям для изучения перед игрой
- Список последних результатов — удобно для конкурсов
- Интерфейс на русском и английском

### Быстрый старт (Windows, PowerShell)

Нужен только установленный Docker Desktop (docker.com/products/docker-desktop).
Скопируй команды по очереди:

    # 1. Сборка образа (первый раз занимает пару минут)
    docker compose build

    # 2. Скачать текстуры и переводы с серверов Mojang (один раз,
    #    повторять при выходе новых версий Minecraft)
    docker compose run --rm web python get_textures.py

    # 3. Собрать составные текстуры (камнерез, костры, стержень Края)
    docker compose run --rm web python make_custom_textures.py

    # 4. Запустить игру (в фоне)
    docker compose up -d

Открой http://localhost:5000 — и играй.

Важно: шаги 2–3 нужно повторять после каждого запуска get_textures.py
(при нём папка текстур очищается). Остановить игру: docker compose down.

### Структура проекта

    guess-the-block/
    ├── app.py                  # сервер Flask: игровая логика и API
    ├── blocks.py               # списки блоков для лёгкой и средней сложности
    ├── get_textures.py         # скачивание текстур и переводов с серверов Mojang
    ├── make_custom_textures.py # сборка составных текстур (камнерез, костры, стержень)
    ├── requirements.txt        # flask, gunicorn, pillow
    ├── Dockerfile
    ├── docker-compose.yml
    ├── templates/
    │   └── index.html          # страница игры
    └── static/
        ├── style.css
        ├── app.js              # фронтенд-логика
        └── textures/           # создаётся get_textures.py (в git не входит)

### Настройка под себя

- Блоки лёгкой/средней — редактируй blocks.py (id текстуры + названия RU/EN).
- Исключить блоки из игры — добавь id в HIDDEN_BLOCKS в app.py.
- Свои текстуры для блоков Профи — список PREFERRED_TEXTURES в app.py.
- Категории для подсказок — CATEGORY_RULES / SECONDARY_RULES в app.py.

### Данные конкурсов

Результаты партий (ник, сложность, блок, попытки, была ли подсказка)
сохраняются в data/results.json.

---

## English

Guess a Minecraft block by its texture! The game reveals 1 random pixel —
each wrong guess uncovers more of it (1 → 4 → 9 → 16). You have 4 tries to name the block.

### Features

- 3 difficulty levels: Easy, Medium, Pro (every block from the latest game version)
- Official block textures and names (EN/RU) — downloaded straight from Mojang's servers
- Nickname input — your Telegram alias
- Answers accepted in both English and Russian; case- and ё-insensitive
- Smart search in Pro mode: partial words, any word order, keyboard-layout independent
- One "block category" hint per round (up to 2 categories per block)
- Block catalog grouped by categories to study before playing
- Recent results list — great for community contests
- UI in English and Russian

### Quick start (Windows, PowerShell)

Requires Docker Desktop (docker.com/products/docker-desktop).
Copy the commands one by one:

    # 1. Build the image (a couple of minutes the first time)
    docker compose build

    # 2. Download textures and translations from Mojang's servers (once;
    #    repeat when a new Minecraft version drops)
    docker compose run --rm web python get_textures.py

    # 3. Assemble composite textures (stonecutter, campfires, end rod)
    docker compose run --rm web python make_custom_textures.py

    # 4. Start the game (in the background)
    docker compose up -d

Open http://localhost:5000 and play.

Note: steps 2–3 must be re-run after every get_textures.py run
(it wipes the textures folder). Stop the game: docker compose down.

### Project structure

    guess-the-block/
    ├── app.py                  # Flask server: game logic and API
    ├── blocks.py               # block lists for Easy and Medium difficulties
    ├── get_textures.py         # downloads textures and translations from Mojang
    ├── make_custom_textures.py # composite textures (stonecutter, campfires, end rod)
    ├── requirements.txt        # flask, gunicorn, pillow
    ├── Dockerfile
    ├── docker-compose.yml
    ├── templates/
    │   └── index.html          # game page
    └── static/
        ├── style.css
        ├── app.js              # frontend logic
        └── textures/           # created by get_textures.py (not committed)

### Customization

- Easy/Medium block lists — edit blocks.py (texture id + EN/RU names).
- Exclude blocks — add their ids to HIDDEN_BLOCKS in app.py.
- Custom Pro textures — see PREFERRED_TEXTURES in app.py.
- Hint categories — see CATEGORY_RULES / SECONDARY_RULES in app.py.

### Contest data

Every round (nickname, difficulty, block, attempts used, hint usage) is appended
to data/results.json.

---

## License / Лицензия

The project code is free to use. Minecraft textures and names belong to Mojang
(© Mojang / Microsoft) and are fetched only from official distribution servers.
This project is not affiliated with Mojang.

Код проекта — свободный. Текстуры и названия Minecraft принадлежат Mojang
(© Mojang / Microsoft) и используются только через официальные серверы
распространения. Проект не связан с Mojang.
