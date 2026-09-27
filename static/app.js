// ---------- Переводы ----------
const STRINGS = {
  ru: {
    subtitle: "Игра загадывает блок и показывает 1 случайный пиксель текстуры. С каждой ошибкой пикселей становится больше (1 → 4 → 9 → 16). Попыток: 4, в Профи — 5 (последняя открывает ещё 5 пикселей). Совет: перед игрой загляни в каталог блоков!",
    nickname: "Твой никнейм:",
    difficulty: "Сложность:",
    easy: "Лёгкая", medium: "Средняя", pro: "Профи",
    start: "Начать игру",
    catalog: "Каталог блоков",
    back: "← Назад",
    catalogFilter: "Найти блок...",
    enterNickname: "Сначала введи никнейм 🙂",
    attempt: "Попытка {n} из {m}",
    guessPlaceholder: "Введи название блока...",
    guess: "Ответить",
    hint: "Подсказка",
    hintUsed: "Категория блока: «{c}»",
    categories: { ore: "Руда", metal: "Металлы и минералы", farm: "Фермерство и еда",
      wood: "Дерево", plants: "Растения", wool: "Шерсть и ткани", sea: "Море",
      nether: "Незер", end: "Край", light: "Свет", earth: "Земля",
      stone: "Камень и кирпичи", mechanism: "Механизмы", other: "Другое" },
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
    subtitle: "The game picks a block and shows 1 random pixel of its texture. Each miss reveals more pixels (1 → 4 → 9 → 16). You have 4 tries — 5 in Pro (the last one reveals 5 more pixels). Tip: browse the block catalog before playing!",
    nickname: "Your nickname:",
    difficulty: "Difficulty:",
    easy: "Easy", medium: "Medium", pro: "Pro",
    start: "Start game",
    catalog: "Block catalog",
    back: "← Back",
    catalogFilter: "Find a block...",
    enterNickname: "Enter a nickname first 🙂",
    attempt: "Attempt {n} of {m}",
    guessPlaceholder: "Type the block name...",
    guess: "Guess",
    hint: "Hint",
    hintUsed: "Block category: \"{c}\"",
    categories: { ore: "Ore", metal: "Metals & minerals", farm: "Farming & food",
      wood: "Wood", plants: "Plants", wool: "Wool & fabric", sea: "Ocean",
      nether: "The Nether", end: "The End", light: "Light", earth: "Earth",
      stone: "Stone & bricks", mechanism: "Mechanisms", other: "Other" },
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
let gameId = null;
let revealed = [];
let tex = null;
let currentLevel = 0;
let maxWrong = 4;          // попыток в текущей игре (5 в Профи)
let names = [];
let proNames = [];
let sugIndex = -1;
let suppressFocus = false;
let hintCategory = null;
let triedList = [];        // что игрок уже называл (для подсветки)
let catalogItems = [];     // содержимое каталога

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
  $("catalogFilter").placeholder = t("catalogFilter");
  document.documentElement.lang = lang;
  if (currentLevel) $("attemptLabel").textContent = t("attempt", {n: currentLevel, m: maxWrong});
  if (hintCategory) {
    const cats = STRINGS[lang].categories;
    $("hintLabel").textContent = t("hintUsed", {c: cats[hintCategory] || cats.other});
  }
}

function applyInputMode() {
  const input = $("guessInput");
  if (difficulty === "pro") {
    input.removeAttribute("list");
  } else {
    input.setAttribute("list", "names");
    hideSuggestions();
  }
}

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
  const matches = q ? matchNames(q) : proNames;
  if (!matches.length) { hideSuggestions(); return; }
  if (sugIndex >= matches.length) sugIndex = matches.length - 1;

  // Уже попробованные варианты — серым с зачёркиванием
  const triedSet = new Set(triedList.map(norm));

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
      if (triedSet.has(norm(n))) el.classList.add("tried");
      el.textContent = n;
      el.title = n;
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
  focusGuessInput();
}

function moveSuggestion(step) {
  const items = $("suggestions").querySelectorAll(".sug");
  if (!items.length) return;
  sugIndex = (sugIndex + step + items.length) % items.length;
  items.forEach((el, i) => el.classList.toggle("active", i === sugIndex));
  items[sugIndex].scrollIntoView({block: "nearest"});
}

// ---------- Каталог блоков (только перед игрой) ----------
async function openCatalog() {
  try {
    const res = await fetch(`/api/catalog?difficulty=${difficulty}&lang=${lang}`);
    catalogItems = await res.json();
  } catch (e) {
    catalogItems = [];
  }
  $("catalogFilter").value = "";
  renderCatalog();
  $("setup").classList.add("hidden");
  $("catalog").classList.remove("hidden");
}

function renderCatalog() {
  const q = norm($("catalogFilter").value);
  const items = q ? catalogItems.filter(i => norm(i.name).includes(q)) : catalogItems;
  const grid = $("catalogGrid");
  grid.innerHTML = "";
  for (const it of items) {
    const cell = document.createElement("div");
    cell.className = "catCell";
    const img = document.createElement("img");
    img.src = it.img;
    img.loading = "lazy";   // не грузим 700 картинок разом
    img.alt = it.name;
    img.title = it.name;
    const name = document.createElement("div");
    name.className = "catName";
    name.textContent = it.name;
    cell.append(img, name);
    grid.appendChild(cell);
  }
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
  maxWrong = data.max_wrong || 4;
  triedList = data.guesses || [];

  $("setup").classList.add("hidden");
  $("catalog").classList.add("hidden");
  $("result").classList.add("hidden");
  $("guessRow").classList.remove("hidden");
  $("game").classList.remove("hidden");
  $("attemptLabel").textContent = t("attempt", {n: 1, m: maxWrong});
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

function draw() {
  const ctx = $("canvas").getContext("2d");
  const cell = 20;
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

  triedList = data.guesses || triedList;
  renderGuesses(data.guesses);

  if (data.over) {
    revealed = data.revealed || revealed;
    if (tex && tex.complete) draw();
    showResult(data);
  } else {
    revealed = data.revealed;
    currentLevel = data.level;
    draw();
    $("attemptLabel").textContent = t("attempt", {n: data.level, m: maxWrong});
    $("guessInput").value = "";
    focusGuessInput();
  }
}

function showResult(data) {
  currentLevel = 0;
  hideSuggestions();
  $("guessInput").blur();
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
    names = [];
  }

  const dl = $("names");
  dl.innerHTML = "";
  for (const n of names) {
    const opt = document.createElement("option");
    opt.value = n;
    dl.appendChild(opt);
  }

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
      const total = r.difficulty === "pro" ? 5 : 4;
      li.textContent = `${r.won ? "✅" : "❌"}${r.hint ? "💡" : ""} ${r.nickname} — ${t(r.difficulty)} — ${block} (${r.attempts}/${total})`;
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
 $("catalogBtn").onclick = openCatalog;
 $("catalogBack").onclick = () => {
  $("catalog").classList.add("hidden");
  $("setup").classList.remove("hidden");
};
 $("catalogFilter").addEventListener("input", renderCatalog);

 $("guessBtn").onclick = submitGuess;
 $("nickname").addEventListener("keydown", e => { if (e.key === "Enter") startGame(); });

function maybeShowSuggestions() {
  if (difficulty !== "pro" || suppressFocus) return;
  sugIndex = -1;
  renderSuggestions();
}
 $("guessInput").addEventListener("focus", maybeShowSuggestions);
 $("guessInput").addEventListener("click", () => {
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
      submitGuess();
    }
  }
  else if (e.key === "Escape") hideSuggestions();
});
document.addEventListener("click", e => {
  if (!e.target.closest(".guessBox")) hideSuggestions();
});

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