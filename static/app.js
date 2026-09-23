// ---------- Переводы ----------
const STRINGS = {
  ru: {
    subtitle: "Игра загадывает блок и показывает 1 случайный пиксель его текстуры. У тебя 4 попытки — после каждой ошибки открывается больше пикселей (1 → 4 → 9 → 16).",
    nickname: "Твой никнейм:",
    difficulty: "Сложность:",
    easy: "Лёгкая", medium: "Средняя", pro: "Профи",
    start: "Начать игру",
    enterNickname: "Сначала введи никнейм 🙂",
    attempt: "Попытка {n} из 4",
    guessPlaceholder: "Введи название блока...",
    guess: "Ответить",
    hint: "Подсказка",
    hintUsed: "Категория блока: «{c}»",
    categories: { ore: "Руда", metal: "Металлы и минералы", stone: "Камень и кирпичи",
      earth: "Земля", wood: "Дерево", plants: "Растения", sea: "Море",
      nether: "Незер", end: "Край", mechanism: "Механизмы и свет", other: "Другое" },
    tried: "Уже пробовал(а):",
    win: "🎉 В точку!",
    lose: "😢 Попытки кончились. Это был(а):",
    again: "Играть ещё",
    recent: "Последние результаты",
    noResults: "Пока пусто — сыграй партию и стань первым!",
    resultsError: "Не удалось загрузить результаты",
    noTextures: "Текстуры не найдены. Сначала запусти get_textures.py",
    genericError: "Ошибка, попробуй ещё раз",
  },
  en: {
    subtitle: "The game picks a block and shows 1 random pixel of its texture. You have 4 tries — each miss reveals more pixels (1 → 4 → 9 → 16).",
    nickname: "Your nickname:",
    difficulty: "Difficulty:",
    easy: "Easy", medium: "Medium", pro: "Pro",
    start: "Start game",
    enterNickname: "Enter a nickname first 🙂",
    attempt: "Attempt {n} of 4",
    guessPlaceholder: "Type the block name...",
    guess: "Guess",
    hint: "Hint",
    hintUsed: "Block category: \"{c}\"",
    categories: { ore: "Ore", metal: "Metals & minerals", stone: "Stone & bricks",
      earth: "Earth", wood: "Wood", plants: "Plants", sea: "Ocean",
      nether: "The Nether", end: "The End", mechanism: "Mechanisms & light", other: "Other" },
    tried: "Already tried:",
    win: "🎉 Nailed it!",
    lose: "😢 Out of tries. It was:",
    again: "Play again",
    recent: "Recent results",
    noResults: "Nothing yet — play a round and be the first!",
    resultsError: "Failed to load results",
    noTextures: "Textures not found. Run get_textures.py first",
    genericError: "Something went wrong, try again",
  },
};

// ---------- Состояние ----------
let lang = localStorage.getItem("gtb_lang") || "ru";
let difficulty = localStorage.getItem("gtb_diff") || "easy";
let gameId = null;         // id текущей игры
let revealed = [];         // индексы открытых пикселей
let tex = null;            // картинка с текстурой загаданного блока
let currentLevel = 0;      // номер текущей попытки
let names = [];            // названия на текущем языке (для списка браузера)
let proNames = [];         // названия на двух языках (для подсказок Профи)
let sugIndex = -1;         // выбранная подсказка (только режим Профи)
let suppressFocus = false; // не открывать список при программном фокусе
let hintCategory = null;   // категория, показанная в подсказке

const $ = (id) => document.getElementById(id);

function t(key, vars) {
  let s = STRINGS[lang][key];
  if (vars) for (const k in vars) s = s.replace("{" + k + "}", vars[k]);
  return s;
}

function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  document.querySelectorAll(".diff").forEach(b => b.textContent = t(b.dataset.diff));
  $("langBtn").textContent = lang === "ru" ? "EN" : "RU";
  $("guessInput").placeholder = t("guessPlaceholder");
  document.documentElement.lang = lang;
  if (currentLevel) $("attemptLabel").textContent = t("attempt", {n: currentLevel});
  if (hintCategory) {
    const cats = STRINGS[lang].categories;
    $("hintLabel").textContent = t("hintUsed", {c: cats[hintCategory] || cats.other});
  }
}

// Лёгкая/средняя — родной список браузера (datalist), Профи — свои подсказки
function applyInputMode() {
  const input = $("guessInput");
  if (difficulty === "pro") {
    input.removeAttribute("list");
  } else {
    input.setAttribute("list", "names");
    hideSuggestions();
  }
}

// Фокус «как от игрока»: список не раскрываем сами
function focusGuessInput() {
  suppressFocus = true;
  $("guessInput").focus();
  setTimeout(() => { suppressFocus = false; }, 0);
}

// ---------- Чипсы «уже пробовал(а)» ----------
function renderGuesses(list) {
  const box = $("guesses");
  if (!list || !list.length) { box.classList.add("hidden"); box.innerHTML = ""; return; }
  box.innerHTML = "";
  const label = document.createElement("span");
  label.textContent = t("tried") + " ";
  box.appendChild(label);
  for (const g of list) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = g;
    box.appendChild(chip);
  }
  box.classList.remove("hidden");
}

// ---------- Умный поиск для режима Профи ----------
const norm = (s) => s.toLowerCase().replace(/ё/g, "е").trim();

// Соответствие клавиш двух раскладок: «fk» найдёт «Алмазный...»
const EN_RU = { q:"й", w:"ц", e:"у", r:"к", t:"е", y:"н", u:"г", i:"ш", o:"щ", p:"з",
                a:"ф", s:"ы", d:"в", f:"а", g:"п", h:"р", j:"о", k:"л", l:"д",
                z:"я", x:"ч", c:"с", v:"м", b:"и", n:"т", m:"ь",
                "[":"х", "]":"ъ", ";":"ж", "'":"э", ",":"б", ".":"ю" };
const RU_EN = {};
for (const key in EN_RU) RU_EN[EN_RU[key]] = key;

function switchLayout(text, toRussian) {
  const map = toRussian ? EN_RU : RU_EN;
  return text.split("").map(ch => map[ch] || ch).join("");
}

function matchNames(query) {
  const q = norm(query);
  if (!q) return [];

  const variants = [q];
  const alt = norm(switchLayout(q, /[a-z]/.test(q)));
  if (alt && alt !== q) variants.push(alt);

  const hits = [];
  for (const n of proNames) {
    const nn = norm(n);
    let score = null;
    for (const v of variants) {
      const tokens = v.split(/\s+/).filter(Boolean);
      if (!tokens.length) continue;
      if (!tokens.every(tok => nn.includes(tok))) continue;
      const atStart = tokens.every(tok => nn.startsWith(tok) || nn.includes(" " + tok));
      const s = atStart ? 0 : 1;
      if (score === null || s < score) score = s;
    }
    if (score !== null) hits.push([score, n]);
  }
  hits.sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1], lang));
  return hits.slice(0, 20).map(h => h[1]);
}

// ---------- Свой список подсказок (только Профи) ----------
function hideSuggestions() {
  $("suggestions").classList.add("hidden");
  sugIndex = -1;
}

function renderSuggestions() {
  const box = $("suggestions");
  if (difficulty !== "pro") { hideSuggestions(); return; }

  const q = $("guessInput").value.trim();
  // Пустой ввод — показываем весь список, как родной datalist в лёгкой/средней.
  // Если на слабом компьютере будет подтормаживать — замени на proNames.slice(0, 300)
  const matches = q ? matchNames(q) : proNames;
  if (!matches.length) { hideSuggestions(); return; }
  if (sugIndex >= matches.length) sugIndex = matches.length - 1;

  // Две колонки: первая половина — слева, вторая — справа.
  // Порядок прежний, поэтому стрелки и Enter работают как раньше.
  const half = Math.ceil(matches.length / 2);
  const cols = [matches.slice(0, half), matches.slice(half)];

  box.innerHTML = "";
  let idx = 0;
  for (const col of cols) {
    const colBox = document.createElement("div");
    colBox.className = "sugCol";
    for (const n of col) {
      const el = document.createElement("div");
      el.className = "sug" + (idx === sugIndex ? " active" : "");
      el.textContent = n;
      el.title = n;  // полное название при наведении, если текст обрезался
      el.onclick = () => pickSuggestion(n);
      colBox.appendChild(el);
      idx++;
    }
    box.appendChild(colBox);
  }
  box.classList.remove("hidden");
}

function pickSuggestion(name) {
  $("guessInput").value = name;
  hideSuggestions();
  focusGuessInput();  // возвращаем фокус, но список заново не открываем
}

function moveSuggestion(step) {
  const items = $("suggestions").querySelectorAll(".sug");
  if (!items.length) return;
  sugIndex = (sugIndex + step + items.length) % items.length;
  items.forEach((el, i) => el.classList.toggle("active", i === sugIndex));
  items[sugIndex].scrollIntoView({block: "nearest"});
}

// ---------- Игра ----------
async function startGame() {
  const nick = $("nickname").value.trim();
  if (!nick) { $("startError").textContent = t("enterNickname"); return; }
  localStorage.setItem("gtb_nick", nick);
  $("startError").textContent = "";

  const res = await fetch("/api/start", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({nickname: nick, difficulty: difficulty}),
  });
  const data = await res.json();
  if (!res.ok) {
    $("startError").textContent = data.error === "no_textures" ? t("noTextures") : t("genericError");
    return;
  }

  gameId = data.game_id;
  revealed = data.revealed;
  currentLevel = 1;

  $("setup").classList.add("hidden");
  $("result").classList.add("hidden");
  $("guessRow").classList.remove("hidden");
  $("game").classList.remove("hidden");
  $("attemptLabel").textContent = t("attempt", {n: 1});
  $("guessInput").value = "";
  renderGuesses(data.guesses);
  hintCategory = null;
  $("hintBtn").disabled = false;
  $("hintLabel").classList.add("hidden");
  $("hintLabel").textContent = "";
  hideSuggestions();
  focusGuessInput();

  tex = new Image();
  tex.src = "/api/texture/" + gameId;
  tex.onload = draw;
}

// Рисуем текстуру на холсте: закрытые пиксели — чёрные
function draw() {
  const ctx = $("canvas").getContext("2d");
  const cell = 20; // 16 пикселей текстуры по 20 px на экране
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#111";
  ctx.fillRect(0, 0, 320, 320);
  for (const idx of revealed) {
    const x = idx % 16, y = Math.floor(idx / 16);
    ctx.drawImage(tex, x, y, 1, 1, x * cell, y * cell, cell, cell);
  }
}

async function submitGuess() {
  if (!gameId) return;
  const guess = $("guessInput").value.trim();
  if (!guess) return;
  hideSuggestions();

  const res = await fetch("/api/guess", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({game_id: gameId, guess: guess}),
  });
  const data = await res.json();
  if (!res.ok) return;

  renderGuesses(data.guesses);

  if (data.over) {
    revealed = data.revealed || revealed;
    if (tex && tex.complete) draw();
    showResult(data);
  } else {
    revealed = data.revealed;
    currentLevel = data.level;
    draw();
    $("attemptLabel").textContent = t("attempt", {n: data.level});
    $("guessInput").value = "";
    focusGuessInput();
  }
}

function showResult(data) {
  currentLevel = 0;
  // Закрываем все выпадающие списки, чтобы не перекрывали результат:
  hideSuggestions();        // свой список подсказок (Профи)
  $("guessInput").blur();   // родной список браузера (Лёгкая/Средняя):
                            // Chrome не убирает его, если просто скрыть поле
  $("guessRow").classList.add("hidden");
  $("attemptLabel").textContent = "";
  $("hintLabel").classList.add("hidden");
  const title = $("resultTitle");
  title.textContent = data.correct ? t("win") : t("lose");
  title.className = data.correct ? "ok" : "bad";
  $("answerName").textContent = lang === "ru" ? data.answer.ru : data.answer.en;
  $("result").classList.remove("hidden");
  loadRecent();
}

// ---------- Загрузка данных ----------
async function loadNames() {
  try {
    const res = await fetch(`/api/names?difficulty=${difficulty}&lang=${lang}`);
    names = await res.json();
  } catch (e) {
    names = [];  // даже при сбое игра не должна ломаться
  }

  // заполняем родной список браузера (лёгкая/средняя)
  const dl = $("names");
  dl.innerHTML = "";
  for (const n of names) {
    const opt = document.createElement("option");
    opt.value = n;
    dl.appendChild(opt);
  }

  // Для Профи — названия на ОБОИХ языках, отсортированные один раз
  if (difficulty === "pro") {
    const other = lang === "ru" ? "en" : "ru";
    try {
      const res = await fetch(`/api/names?difficulty=pro&lang=${other}`);
      const otherNames = await res.json();
      proNames = [...new Set([...names, ...otherNames])];
    } catch (e) {
      proNames = [...names];
    }
    proNames.sort((a, b) => a.localeCompare(b, lang));
  } else {
    proNames = [];
  }
  applyInputMode();
}

async function loadRecent() {
  const list = $("recentList");
  const showNote = (msg) => {
    list.innerHTML = "";
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = msg;
    list.appendChild(li);
  };
  try {
    const res = await fetch("/api/results");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const items = await res.json();
    if (!Array.isArray(items) || !items.length) { showNote(t("noResults")); return; }
    list.innerHTML = "";
    for (const r of items) {
      const li = document.createElement("li");
      const block = lang === "ru" ? r.block_ru : r.block_en;
      li.textContent = `${r.won ? "✅" : "❌"}${r.hint ? "💡" : ""} ${r.nickname} — ${t(r.difficulty)} — ${block} (${r.attempts}/4)`;
      list.appendChild(li);
    }
  } catch (e) {
    console.error("Не удалось загрузить результаты:", e);
    showNote(t("resultsError"));
  }
}

// ---------- События ----------
 $("nickname").value = localStorage.getItem("gtb_nick") || "";

document.querySelectorAll(".diff").forEach(b => {
  b.classList.toggle("active", b.dataset.diff === difficulty);
  b.onclick = () => {
    difficulty = b.dataset.diff;
    localStorage.setItem("gtb_diff", difficulty);
    document.querySelectorAll(".diff").forEach(x => x.classList.toggle("active", x === b));
    loadNames();
  };
});

 $("startBtn").onclick = startGame;
 $("guessBtn").onclick = submitGuess;
 $("nickname").addEventListener("keydown", e => { if (e.key === "Enter") startGame(); });

// Клик/таб-переход на поле — раскрываем список (весь, если поле пустое)
function maybeShowSuggestions() {
  if (difficulty !== "pro" || suppressFocus) return;
  sugIndex = -1;
  renderSuggestions();
}
 $("guessInput").addEventListener("focus", maybeShowSuggestions);
 $("guessInput").addEventListener("click", () => {
  // если список уже открыт — не перерисовываем, иначе раскрываем заново
  if ($("suggestions").classList.contains("hidden")) maybeShowSuggestions();
});

 $("guessInput").addEventListener("input", () => { sugIndex = -1; renderSuggestions(); });
 $("guessInput").addEventListener("keydown", e => {
  const open = difficulty === "pro" && !$("suggestions").classList.contains("hidden");
  if (e.key === "ArrowDown" && open) { e.preventDefault(); moveSuggestion(1); }
  else if (e.key === "ArrowUp" && open) { e.preventDefault(); moveSuggestion(-1); }
  else if (e.key === "Enter") {
    if (open && sugIndex >= 0) {
      const item = $("suggestions").querySelectorAll(".sug")[sugIndex];
      pickSuggestion(item.textContent);
    } else {
      submitGuess();  // Enter без выбранной подсказки = отправить ответ
    }
  }
  else if (e.key === "Escape") hideSuggestions();
});
// клик мимо списка — закрыть подсказки
document.addEventListener("click", e => {
  if (!e.target.closest(".guessBox")) hideSuggestions();
});

// Кнопка подсказки — показывает категорию блока, один раз за партию
 $("hintBtn").onclick = async () => {
  if (!gameId || $("hintBtn").disabled) return;
  const res = await fetch("/api/hint", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({game_id: gameId}),
  });
  if (!res.ok) return;
  const data = await res.json();
  hintCategory = data.category;
  $("hintBtn").disabled = true;
  const cats = STRINGS[lang].categories;
  const label = $("hintLabel");
  label.textContent = t("hintUsed", {c: cats[hintCategory] || cats.other});
  label.classList.remove("hidden");
};

 $("againBtn").onclick = () => {
  gameId = null;
  $("game").classList.add("hidden");
  $("result").classList.add("hidden");
  $("setup").classList.remove("hidden");
};

 $("langBtn").onclick = () => {
  lang = lang === "ru" ? "en" : "ru";
  localStorage.setItem("gtb_lang", lang);
  applyLang();
  loadNames();
  loadRecent();
};

// ---------- Инициализация ----------
applyLang();
applyInputMode();
loadNames();
loadRecent();