// Motore di interrogazione dell'orario ITIS Negrelli: nessuna dipendenza dal DOM.
// Testabile offline tramite Node.js.
// parseQuery(text, idx, ctx) -> intento strutturato
// answer(parsed, idx, ctx)   -> { title, badge, lines[], note, speech, rooms[] }

const JS_DAYS = ["domenica", "lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"];
const ORD_F = { prima: 1, seconda: 2, terza: 3, quarta: 4, quinta: 5, sesta: 6, settima: 7, ottava: 8 };
const ORD_WORDS = Object.fromEntries(Object.entries(ORD_F).map(([w, n]) => [n, w]));
const LESSON_MIN = 55;

export function normalize(str) {
  return (str || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function titleCase(s) {
  return (s || "")
    .toLowerCase()
    .replace(/(^|[\s'./-])([a-zà-ÿ])/g, (m, p, c) => p + c.toUpperCase());
}

const DAY_LABEL = {
  lunedi: "lunedì",
  martedi: "martedì",
  mercoledi: "mercoledì",
  giovedi: "giovedì",
  venerdi: "venerdì",
  sabato: "sabato",
  domenica: "domenica",
};
const dl = (d) => DAY_LABEL[d] || d;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export const IT_MONTHS = {
  gennaio: 1,
  febbraio: 2,
  marzo: 3,
  aprile: 4,
  maggio: 5,
  giugno: 6,
  luglio: 7,
  agosto: 8,
  settembre: 9,
  ottobre: 10,
  novembre: 11,
  dicembre: 12,
};
export const IT_MONTH_NAMES = Object.entries(IT_MONTHS).reduce((acc, [k, v]) => {
  acc[v] = k;
  return acc;
}, {});

function pad2(n) {
  return String(n).padStart(2, "0");
}

export function formatDateYMD(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function formatDateSpoken(ymd) {
  if (!ymd) return "";
  const [y, m, d] = ymd.split("-").map(Number);
  const mName = IT_MONTH_NAMES[m] || "";
  return `${d} ${mName}`;
}

export function getISOWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d - yearStart) / 86400000 + 1) / 7);
}

export function getWeekParity(date) {
  const weekNum = getISOWeek(date);
  const isOdd = weekNum % 2 === 1;
  return {
    weekNum,
    code: isOdd ? "Q1" : "Q2",
    parityLabel: isOdd ? "dispari" : "pari",
    label: isOdd ? `Settimana Q1 (n° ${weekNum}, dispari)` : `Settimana Q2 (n° ${weekNum}, pari)`,
  };
}

export function formatDocenteName(nome) {
  if (!nome) return "";
  if (nome.startsWith("_")) {
    const clean = nome.replace(/^_\s*/, "").trim();
    return `Cattedra ${clean.toUpperCase()}`;
  }
  return titleCase(nome);
}

export function spokenDocenteName(nome) {
  if (!nome) return "";
  if (nome.startsWith("_")) {
    const clean = nome.replace(/^_\s*/, "").trim().toLowerCase();
    const expanded = clean
      .replace(/\binfo\s*(\d)/gi, "Informatica $1")
      .replace(/\bele\s*(\d)/gi, "Elettronica $1")
      .replace(/\bmecc\s*(\d)/gi, "Meccanica $1")
      .replace(/\bchim\s*(\d)/gi, "Chimica $1");
    return `la cattedra di ${titleCase(expanded)}`;
  }
  return `il professor ${titleCase(nome)}`;
}

// ------------------------------------------------------------------ indice
export function buildIndex(db) {
  // Tutti i docenti sono indicizzati, inclusi quelli non ancora arrivati (_info 5, _ele 2, ecc.)
  const docenti = Object.entries(db.docenti).map(([id, d]) => {
    const isPlaceholder = Boolean(d.senza_nome || d.nome.startsWith("_"));
    const clean = normalize(d.nome);
    const words = clean.split(" ").filter((t) => /^[a-z]{3,}$/.test(t));
    const compact = clean.replace(/\s+/g, "");
    const tokens = [...new Set([...words, compact])];
    return {
      id,
      nome: d.nome,
      isPlaceholder,
      tokens,
    };
  });

  const allClassSet = new Set(Object.keys(db.classi || {}));
  const gloIncontri = db.glo?.incontri || db.attivita?.glo || [];
  gloIncontri.forEach((g) => {
    if (g.classe) allClassSet.add(g.classe);
  });
  if (db.attivita?.consigli_classe_dettaglio) {
    db.attivita.consigli_classe_dettaglio.forEach((c) => {
      if (c.classi) c.classi.forEach((cls) => allClassSet.add(cls));
    });
  }

  const classKeys = Array.from(allClassSet).map((id) => ({
    id,
    key: id.toLowerCase(),
  }));

  const aule = Object.keys(db.aule).map((nome) => {
    const norm = normalize(nome);
    const numMatch = nome.match(/\b\d{3}\b/);
    return {
      nome,
      key: norm,
      num: numMatch ? numMatch[0] : null,
      isLab: /lab|laboratorio/i.test(nome),
      isPalestra: /palestra/i.test(nome),
    };
  });

  const starts = db.meta.ore.map((o) => {
    const [h, m] = o.inizio.split(":").map(Number);
    return { ora: o.ora, inizio: o.inizio, min: h * 60 + m };
  });

  const attivita = db.attivita || {
    attivita_istituto: [],
    attivita_classe_sintesi: [],
    consigli_classe_dettaglio: [],
    colloqui_generali: [],
    glo: [],
  };

  const glo = db.glo?.incontri || db.attivita?.glo || [];

  const scansione = db.meta?.scansione_oraria || null;

  const calendario = db.calendario || {
    meta: {},
    vacanze: [],
    festivita: [],
    chiusure_totali: [],
    giorni_sospensione: {},
  };

  const sorveglianze = db.sorveglianze || {
    meta: {},
    turni: [],
    per_giorno: {},
    per_docente: {},
  };

  const colloqui_docenti = db.colloqui_docenti || {
    meta: {},
    per_docente: {},
    per_classe: {},
  };

  return { db, docenti, classKeys, aule, starts, attivita, scansione, calendario, glo, sorveglianze, colloqui_docenti };
}

// ------------------------------------------------------------------ entità
function findClasses(q, idx) {
  const exists = (cand) => idx.classKeys.some((c) => c.key.startsWith(cand));
  let s = q;

  // "quarta ita" -> "4ita", "prima bta" -> "1bta", "prima a" -> "1a"
  s = s.replace(/\b(prima|seconda|terza|quarta|quinta)\s+([a-z]{1,5})\b/g, (m, o, l) =>
    exists(ORD_F[o] + l) ? ORD_F[o] + l : m
  );
  // "4 ita" -> "4ita", "1 bta" -> "1bta", "1 a" -> "1a"
  s = s.replace(/\b([1-5])\s+([a-z]{1,5})\b/g, (m, d, l) => (exists(d + l) ? d + l : m));

  const ids = [];
  const used = [];
  for (const tok of s.match(/\b[1-5][a-z]{1,5}\b/g) || []) {
    const exact = idx.classKeys.filter((c) => c.key === tok);
    const hits = exact.length ? exact : idx.classKeys.filter((c) => c.key.startsWith(tok));
    if (hits.length) {
      used.push(tok);
      hits.forEach((h) => !ids.includes(h.id) && ids.push(h.id));
    }
  }

  let rest = s;
  used.forEach((t) => (rest = rest.replace(new RegExp(`\\b${t}\\b`, "g"), " ")));
  return { ids, rest: rest.replace(/\s+/g, " ").trim() };
}

function scoreDocenti(q, idx) {
  const norm = normalize(q);
  const rawWords = norm.split(" ").filter((w) => w.length >= 3);
  const joined = norm.replace(/\b(info|ele|chim|mecc)\s+(\d)\b/gi, "$1$2");
  const words = [...new Set([...rawWords, ...joined.split(" ").filter((w) => w.length >= 3)])];
  const stopWords = new Set(["cosa", "prof", "docente", "cattedra", "orario", "della", "dello", "nelle", "delle"]);

  const scored = idx.docenti
    .map((d) => {
      let score = 0;
      const fullNorm = normalize(d.nome);
      if (fullNorm.length >= 3 && new RegExp(`(^|\\s)${fullNorm}(\\s|$)`).test(norm)) {
        score += 25 + fullNorm.length;
      }
      for (const w of words) {
        if (stopWords.has(w)) continue;
        for (const t of d.tokens) {
          if (t === w) {
            score += 10;
          } else if (w.length >= 4 && (t.startsWith(w) || (w.length >= 5 && w.startsWith(t)))) {
            score += 5;
          }
        }
      }
      return { d, score };
    })
    .filter((x) => x.score > 0);

  if (!scored.length) return [];
  const top = Math.max(...scored.map((x) => x.score));
  return scored.filter((x) => x.score === top).map((x) => x.d);
}

function findRooms(q, idx) {
  // 1. Cerca per numero aula a tre cifre (es. "201", "019", "116")
  const numMatch = q.match(/\b(\d{3})\b/);
  if (numMatch) {
    const hit = idx.aule.filter((a) => a.num === numMatch[1]);
    if (hit.length) return hit;
  }

  // 2. Cerca match esatto sulla chiave normalizzata
  const exact = idx.aule.filter((a) => new RegExp(`(^|\\s)${a.key}(\\s|$)`).test(q));
  if (exact.length) return exact;

  // 3. Cerca per parole chiave significative dell'aula (es. "palestra", "rizzarda", "linux")
  const words = new Set(q.split(" "));
  const hits = idx.aule.filter((a) => {
    const kWords = a.key.split(" ").filter((w) => w.length >= 4 && w !== "aula" && w !== "laboratorio");
    return kWords.some((kw) => words.has(kw));
  });
  if (hits.length) return hits;

  return [];
}

export function findExplicitDate(q) {
  const m = q.match(/\b(?:il|l|del|dello|della)?\s*(\d{1,2})(?:°|ª|o)?\s+(settembre|ottobre|novembre|dicembre|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto)(?:\s+(\d{4}))?\b/i);
  if (!m) return null;
  const day = parseInt(m[1], 10);
  const mName = m[2].toLowerCase();
  const month = IT_MONTHS[mName];
  if (!month) return null;
  const year = m[3] ? parseInt(m[3], 10) : (month >= 9 ? 2026 : 2027);
  const targetDate = new Date(year, month - 1, day, 10, 0, 0);
  const ymd = `${year}-${pad2(month)}-${pad2(day)}`;
  const dayOfWeek = JS_DAYS[targetDate.getDay()];
  return { ymd, targetDate, dayOfWeek, day, month, mName, year, matchedText: m[0] };
}

// Catalogo fisico completo (Wayfinding DWG) per tutte le aule, laboratori e servizi d'istituto
export const MAP_DIRECTORY = [
  // Piano Terra (0)
  { code: "INGRESSO", name: "Ingresso Principale / Atrio", floor: 0, floorLabel: "PIANO TERRA", wing: "Corpo Sud-Ovest (Locale 029)", keywords: ["ingresso", "entrata", "atrio", "portineria", "accoglienza"] },
  { code: "037", name: "Entrata Palestra", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Ovest, Accesso Palestra (Locale 037)", keywords: ["037", "entrata palestra", "accesso palestra", "ingresso palestra"] },
  { code: "004", name: "Palestra", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Ovest (Locale 004)", keywords: ["004", "palestra", "campo da gioco", "educazione fisica", "scienze motorie"] },
  { code: "005-006", name: "Spogliatoi Palestra", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Ovest (Locali 005-008)", keywords: ["005", "006", "005-006", "spogliatoio", "spogliatoi"] },
  { code: "009", name: "Infermeria", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Ovest, lato Palestra (Locale 009)", keywords: ["009", "infermeria", "primo soccorso", "pronto soccorso", "medicheria"] },
  { code: "014", name: "Aula 014", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Nord-Est", keywords: ["014"] },
  { code: "015", name: "Aula 015", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Est", keywords: ["015"] },
  { code: "016", name: "Aula 016", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Est", keywords: ["016"] },
  { code: "017", name: "Aula 017", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Centro-Est", keywords: ["017"] },
  { code: "018", name: "Lab. Linux 018", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Nord (Locale 018)", keywords: ["018", "lab linux", "laboratorio linux"] },
  { code: "019", name: "Aula 019", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Nord-Ovest", keywords: ["019"] },
  { code: "020-021", name: "Lab. Multimediale 020-021", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Ovest (Locali 020-021)", keywords: ["020", "021", "020-021", "multimediale", "lab multimediale"] },
  { code: "022", name: "Aula 022", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Sud-Ovest", keywords: ["022"] },
  { code: "024", name: "Lab 1 (Cod. 024)", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Est, lato Officina (Locale 024)", keywords: ["024", "lab 1", "laboratorio 1"] },
  { code: "025", name: "Lab 2 (Cod. 025)", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Est, lato Officina (Locale 025)", keywords: ["025", "lab 2", "laboratorio 2"] },
  { code: "026", name: "Officina Meccanica", floor: 0, floorLabel: "PIANO TERRA", wing: "Blocco Est (Locale 026 • 246 m²)", keywords: ["026", "officina", "officina meccanica", "macchine utensili", "torneria"] },
  { code: "028", name: "Aula Insegnanti", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Sud (Locale 028 • ex Mensa)", keywords: ["028", "aula insegnanti", "sala insegnanti", "sala docenti", "sala professori", "aula docenti", "docenti", "mensa", "pot disp", "disposizione"] },
  { code: "030", name: "Lab 5 (Cod. 030)", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Ovest (Locale 030)", keywords: ["030", "lab 5", "laboratorio 5"] },
  { code: "031", name: "Lab 4 (Cod. 031)", floor: 0, floorLabel: "PIANO TERRA", wing: "Ala Nord-Ovest (Locale 031)", keywords: ["031", "lab 4", "laboratorio 4"] },
  { code: "033", name: "Agorà / Spazio Studio", floor: 0, floorLabel: "PIANO TERRA", wing: "Corpo Centrale (Locali 032-033)", keywords: ["032", "033", "032-033", "agora", "spazio studio"] },
  { code: "035", name: "Segreteria Didattica", floor: 0, floorLabel: "PIANO TERRA", wing: "Corpo Centrale-Est (Locale 035)", keywords: ["035", "segreteria didattica", "didattica", "accoglienza", "sportello didattica"] },
  { code: "058-059", name: "Biblioteca d'Istituto", floor: 0, floorLabel: "PIANO TERRA", wing: "Corpo Centrale (Locali 058-059)", keywords: ["058", "059", "058-059", "biblioteca", "sala lettura"] },
  { code: "060", name: "Vicepresidenza", floor: 0, floorLabel: "PIANO TERRA", wing: "Corpo Centrale-Sud (Locale 060)", keywords: ["060", "vicepresidenza", "ufficio vicepresidenza", "vicepresidenza terra"] },
  { code: "069", name: "Area Ristoro / Bar", floor: 0, floorLabel: "PIANO TERRA", wing: "Atrio Sud, vicino all'Ingresso (Locale 069)", keywords: ["069", "area ristoro", "ristoro", "bar", "caffetteria", "macchinette"] },
  { code: "070", name: "Archivio", floor: 0, floorLabel: "PIANO TERRA", wing: "Lato Est (Locale 070)", keywords: ["070", "archivio"] },
  { code: "ASC", name: "Ascensore Centrale", floor: 0, floorLabel: "PIANO TERRA", wing: "Corpo Centrale (Locale 046 — collega Piani 0, 1 e 2)", keywords: ["asc", "046", "ascensore"] },

  // Primo Piano (1)
  { code: "104-106", name: "Segreteria & Uffici Dirigenza", floor: 1, floorLabel: "1° PIANO", wing: "Ala Sud-Ovest (Locali 104, 105, 106, 138)", keywords: ["104", "105", "106", "138", "104-106", "uffici", "segreteria", "ufficio", "presidenza", "dirigenza"] },
  { code: "107", name: "Ufficio Vicepresidenza", floor: 1, floorLabel: "1° PIANO", wing: "Ala Sud-Ovest (Locale 107)", keywords: ["107", "ufficio vicepresidenza", "vicepresidenza primo piano", "vicepresidenza 107"] },
  { code: "110", name: "Aula 110", floor: 1, floorLabel: "1° PIANO", wing: "Ala Nord-Est", keywords: ["110"] },
  { code: "111", name: "Aula 111", floor: 1, floorLabel: "1° PIANO", wing: "Ala Est", keywords: ["111"] },
  { code: "112", name: "Aula 112", floor: 1, floorLabel: "1° PIANO", wing: "Ala Est", keywords: ["112"] },
  { code: "113", name: "Aula 113", floor: 1, floorLabel: "1° PIANO", wing: "Ala Centro-Est", keywords: ["113"] },
  { code: "114", name: "Aula 114", floor: 1, floorLabel: "1° PIANO", wing: "Ala Sud-Est", keywords: ["114"] },
  { code: "115", name: "Aula 115", floor: 1, floorLabel: "1° PIANO", wing: "Ala Sud", keywords: ["115"] },
  { code: "116-117", name: "Lab. CAD-Automazione 116-117", floor: 1, floorLabel: "1° PIANO", wing: "Ala Ovest (Locali 116-117)", keywords: ["116", "117", "116-117", "cad", "automazione"] },
  { code: "118", name: "Lab. Costruzioni 118", floor: 1, floorLabel: "1° PIANO", wing: "Ala Nord-Ovest (Locale 118)", keywords: ["118", "costruzioni"] },
  { code: "119", name: "Aula 119", floor: 1, floorLabel: "1° PIANO", wing: "Ala Nord", keywords: ["119"] },
  { code: "125", name: "Lab. Chimica 125", floor: 1, floorLabel: "1° PIANO", wing: "Blocco Est (Locale 125)", keywords: ["125", "chimica"] },
  { code: "126", name: "Lab. Biologia 126", floor: 1, floorLabel: "1° PIANO", wing: "Blocco Est (Locale 126)", keywords: ["126", "biologia", "scienze"] },
  { code: "128", name: "Aula Informale 128", floor: 1, floorLabel: "1° PIANO", wing: "Corpo Centrale-Nord (Locale 128)", keywords: ["128"] },
  { code: "129", name: "Lab. Disegno 129", floor: 1, floorLabel: "1° PIANO", wing: "Corpo Centrale (Locale 129)", keywords: ["129", "disegno"] },
  { code: "130", name: "Aula Informale 130", floor: 1, floorLabel: "1° PIANO", wing: "Ala Ovest (Locale 130)", keywords: ["130"] },
  { code: "131", name: "Aula Informale 131", floor: 1, floorLabel: "1° PIANO", wing: "Ala Ovest (Locale 131)", keywords: ["131"] },
  { code: "134", name: "Aula 134", floor: 1, floorLabel: "1° PIANO", wing: "Ala Sud-Ovest (Locale 134)", keywords: ["134"] },
  { code: "135", name: "Lab. Fisica 135", floor: 1, floorLabel: "1° PIANO", wing: "Corpo Centrale-Sud (Locale 135)", keywords: ["135", "fisica"] },
  { code: "137", name: "Spazio Informale 137", floor: 1, floorLabel: "1° PIANO", wing: "Corpo Connettivo Centrale (Locale 137)", keywords: ["137", "informale 137", "spazio 137"] },

  // Secondo Piano (2)
  { code: "201", name: "Aula 201", floor: 2, floorLabel: "2° PIANO", wing: "Ala Nord-Est", keywords: ["201"] },
  { code: "202", name: "Aula 202", floor: 2, floorLabel: "2° PIANO", wing: "Ala Est", keywords: ["202"] },
  { code: "203", name: "Aula 203", floor: 2, floorLabel: "2° PIANO", wing: "Ala Est", keywords: ["203"] },
  { code: "204", name: "Aula 204", floor: 2, floorLabel: "2° PIANO", wing: "Ala Sud-Est", keywords: ["204"] },
  { code: "205", name: "Aula 205", floor: 2, floorLabel: "2° PIANO", wing: "Ala Sud", keywords: ["205"] },
  { code: "206-207", name: "Lab. Informatica 206-207", floor: 2, floorLabel: "2° PIANO", wing: "Ala Ovest (Locali 206-207)", keywords: ["206", "207", "206-207", "lab informatica", "laboratorio informatica"] },
  { code: "208", name: "Lab. Elettronica 208", floor: 2, floorLabel: "2° PIANO", wing: "Ala Nord-Ovest (Locale 208)", keywords: ["208", "elettronica", "elettrotecnica"] },
  { code: "209", name: "Aula 209", floor: 2, floorLabel: "2° PIANO", wing: "Ala Centro-Est", keywords: ["209"] },
  { code: "210", name: "Lab. Lingue 210", floor: 2, floorLabel: "2° PIANO", wing: "Ala Nord (Locale 210)", keywords: ["210", "lingue", "linguistico"] },
  { code: "211", name: "Spazio Informale 211", floor: 2, floorLabel: "2° PIANO", wing: "Ala Ovest (Locale 211)", keywords: ["211", "informale 211"] },
  { code: "212", name: "Spazio Informale 212", floor: 2, floorLabel: "2° PIANO", wing: "Ala Ovest (Locale 212)", keywords: ["212", "informale 212"] },
  { code: "213", name: "Aula Informale 213", floor: 2, floorLabel: "2° PIANO", wing: "Ala Ovest (Locale 213)", keywords: ["213"] },
  { code: "214", name: "Spazio Lab 214", floor: 2, floorLabel: "2° PIANO", wing: "Ala Ovest (Locale 214)", keywords: ["214", "lab 214", "spazio lab"] },
  { code: "221", name: "Spazio Studio 221", floor: 2, floorLabel: "2° PIANO", wing: "Corpo Centrale (Locale 221)", keywords: ["221", "studio 221", "spazio studio 221"] },
  { code: "223", name: "Lab. Sistemi 223", floor: 2, floorLabel: "2° PIANO", wing: "Ala Sud (Locale 223)", keywords: ["223", "sistemi"] },
  { code: "224", name: "Aula 224", floor: 2, floorLabel: "2° PIANO", wing: "Ala Sud-Ovest (Locale 224)", keywords: ["224"] },

  // Servizi Comuni
  { code: "WC", name: "Servizi Igienici (WC)", floor: 0, floorLabel: "TUTTI I PIANI", wing: "Dislocati su tutti i piani (Blocco Ovest, Est e Centrale)", keywords: ["wc", "bagno", "bagni", "toilette", "servizi igienici", "servizi"] },
  { code: "SCALA", name: "Scale Principali", floor: 0, floorLabel: "TUTTI I PIANI", wing: "Corpo Centrale, Ala Nord, Ala Est e Ala Ovest", keywords: ["scala", "scale", "gradini"] },
];

export function resolveRoomLocation(roomStr) {
  if (!roomStr) return null;
  const raw = String(roomStr).trim();
  const norm = normalize(raw);

  // 1. Match diretto su codice locale esatto (case-insensitive) o keyword esatta
  const directHit = MAP_DIRECTORY.find((m) =>
    m.code.toUpperCase() === raw.toUpperCase() ||
    m.code.toLowerCase() === norm ||
    m.keywords.includes(norm)
  );
  if (directHit) return directHit;

  // 2. Alias aule orario scolastico
  if (/\b(pot-disp|potenziamento|disposizione)\b/i.test(raw) || norm.includes("pot disp")) {
    const docentiHit = MAP_DIRECTORY.find((m) => m.code === "028");
    if (docentiHit) return docentiHit;
  }
  if (/rizzarda/i.test(raw)) {
    return { code: "RIZZARDA", name: "Sede Esterna Rizzarda", floor: -1, floorLabel: "SEDE ESTERNA", wing: "Succursale Rizzarda" };
  }
  if (/colotti/i.test(raw)) {
    return { code: "COLOTTI", name: "Sede Esterna Colotti", floor: -1, floorLabel: "SEDE ESTERNA", wing: "Sezione Colotti" };
  }
  if (/palestra/i.test(raw) && !/entrata|spogliatoi/i.test(raw)) {
    return MAP_DIRECTORY.find((m) => m.code === "004");
  }

  // 3. Estrazione codice numerico a 3 cifre
  const numMatch = raw.match(/\b(\d{3})\b/);
  if (numMatch) {
    const num = numMatch[1];
    const hit = MAP_DIRECTORY.find((m) => m.code === num || m.keywords.includes(num));
    if (hit) return hit;
    const f = num[0] === "1" ? 1 : num[0] === "2" ? 2 : 0;
    const fl = f === 1 ? "1° PIANO" : f === 2 ? "2° PIANO" : "PIANO TERRA";
    return { code: num, name: raw, floor: f, floorLabel: fl, wing: "Edificio Principale" };
  }

  // 4. Scansione parole chiave nel testo normalizzato
  for (const item of MAP_DIRECTORY) {
    if (item.keywords.some((kw) => new RegExp(`(^|\\s)${kw}(\\s|$)`).test(norm))) {
      return item;
    }
  }
  return null;
}

function findMapSpace(qNorm) {
  const numMatch = qNorm.match(/\b(\d{3})\b/);
  if (numMatch) {
    const hit = MAP_DIRECTORY.find((m) => m.code === numMatch[1] || m.keywords.includes(numMatch[1]));
    if (hit) return hit;
  }

  const mentionsPiano1 = /\b(primo piano|1° piano|piano 1|1 piano)\b/.test(qNorm);
  const mentionsPiano2 = /\b(secondo piano|2° piano|piano 2|2 piano)\b/.test(qNorm);
  const mentionsPiano0 = /\b(piano terra|terra|piano 0)\b/.test(qNorm);

  let best = null;
  let maxScore = 0;

  for (const item of MAP_DIRECTORY) {
    for (const kw of item.keywords) {
      if ((kw.length >= 3 || kw === "wc") && !/^\d{3}$/.test(kw) && new RegExp(`(^|\\s)${kw}(\\s|$)`).test(qNorm)) {
        let score = kw.length;
        if (mentionsPiano1 && item.floor === 1) score += 50;
        if (mentionsPiano2 && item.floor === 2) score += 50;
        if (mentionsPiano0 && item.floor === 0) score += 50;
        if (score > maxScore) {
          maxScore = score;
          best = item;
        }
      }
    }
  }
  return best;
}

function findDay(q, now) {
  const explicit = findExplicitDate(q);
  if (explicit) return explicit.dayOfWeek;
  for (const d of ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]) {
    if (new RegExp(`\\b${d}\\b`).test(q)) return d;
  }
  const n = now.getDay();
  if (/\bdopodomani\b/.test(q)) return JS_DAYS[(n + 2) % 7];
  if (/\bdomani\b/.test(q)) return JS_DAYS[(n + 1) % 7];
  if (/\bieri\b/.test(q)) return JS_DAYS[(n + 6) % 7];
  return JS_DAYS[n];
}

function findHour(q) {
  const ord = Object.keys(ORD_F).join("|");
  let m =
    q.match(new RegExp(`\\b(${ord})\\s+(?:ora|lezione)\\b`)) ||
    q.match(new RegExp(`\\b(?:alla|nella|all|nell)\\s+(${ord})\\b`));
  if (m) return ORD_F[m[1]];

  m =
    q.match(/\b(?:ora|ore)\s*([1-8])\b/) ||
    q.match(/\balla\s*([1-8])(?:ª|°|a)?\b/) ||
    q.match(/\b([1-8])\s*(?:ª|°|a)?\s*ora\b/);
  if (m) return Number(m[1]);

  return null;
}

export function getDaySchedule(day, idx) {
  const scansione = idx.scansione || idx.db?.meta?.scansione_oraria;
  if (scansione) {
    if (day === "sabato") return scansione.sabato;
    if (day === "giovedi" || day === "venerdi") return scansione.giovedi_venerdi;
    if (["lunedi", "martedi", "mercoledi"].includes(day)) return scansione.lunedi_mercoledi;
  }
  return null;
}

function currentLesson(now, idx, day = null) {
  const dayName = day || JS_DAYS[now.getDay()];
  const t = now.getHours() * 60 + now.getMinutes();
  const sched = getDaySchedule(dayName, idx);

  if (sched) {
    for (const item of sched) {
      if (item.ora) {
        const [h1, m1] = item.inizio.split(":").map(Number);
        const [h2, m2] = item.fine.split(":").map(Number);
        const minStart = h1 * 60 + m1;
        const minEnd = h2 * 60 + m2;
        if (t >= minStart && t < minEnd) return item.ora;
      }
    }
    return null;
  }

  const hit = idx.starts.find((s) => t >= s.min && t < s.min + LESSON_MIN);
  return hit ? hit.ora : null;
}

// ------------------------------------------------------------------ parsing
export function parseQuery(text, idx, ctx = {}) {
  const now = ctx.now || new Date();
  const q0 = normalize(text);
  const { ids: classi, rest } = findClasses(q0, idx);
  const q = rest;

  const explicitDate = findExplicitDate(q0);
  let targetDateYMD = null;
  let targetDate = null;
  if (explicitDate) {
    targetDateYMD = explicitDate.ymd;
    targetDate = explicitDate.targetDate;
  } else if (/\boggi\b/.test(q0)) {
    targetDate = new Date(now);
    targetDateYMD = formatDateYMD(targetDate);
  } else if (/\bdomani\b/.test(q0)) {
    targetDate = new Date(now.getTime() + 86400000);
    targetDateYMD = formatDateYMD(targetDate);
  } else if (/\bdopodomani\b/.test(q0)) {
    targetDate = new Date(now.getTime() + 2 * 86400000);
    targetDateYMD = formatDateYMD(targetDate);
  } else if (/\bieri\b/.test(q0)) {
    targetDate = new Date(now.getTime() - 86400000);
    targetDateYMD = formatDateYMD(targetDate);
  }

  const giorniSospensione = idx.calendario?.giorni_sospensione || {};
  const sospensione = targetDateYMD && giorniSospensione[targetDateYMD] ? giorniSospensione[targetDateYMD] : null;

  const day = findDay(q, now);
  const realtime = /\b(adesso|attualmente|in questo momento|in questo istante|ora attuale)\b/.test(q);
  let hour = findHour(q);
  if (realtime) hour = currentLesson(now, idx, day);

  const isProssimo = /\b(prossim[oiea]|successiv[oiea]|imminent[ei]|futur[oiea])\b/.test(q0);
  const isWhere = /\b(dove|dov e|che piano|quale piano|mappa|posizione|ubicazione|raggiung|in che aula|quale aula|che aula)\b/.test(q0);
  const base = { day, hour, realtime, raw: text, now, isProssimo, targetDateStr: targetDateYMD, sospensione, isWhere, qNorm: q0 };

  // Controllo per Richiesta Aiuto / Domande Possibili
  const isHelp =
    /\b(quali\s+(?:sono\s+le\s+)?domande(?:\s+posso\s+farti)?|domande\s+possibili|cosa\s+posso\s+(?:chiederti|chiedere|domandarti|fare)|cosa\s+sai\s+fare|cosa\s+puoi\s+fare|esempi\s+(?:di\s+)?domande|aiuto|help|istruzioni|come\s+funziona|come\s+ti\s+uso)\b/i.test(q0);

  if (isHelp) {
    return { ...base, intent: "aiuto", queryText: q0 };
  }

  // Controllo per Turni di Sorveglianza & Orario Intervallo (Comunicato n. 167, dal 19 novembre 2026)
  const isSorveglianza = /\b(sorveglianz[ae]|sorvegliare|vigilanza|ricreazione|intervallo)\b/.test(q0);
  if (isSorveglianza) {
    const asksDuration = /\b(quanto\s+dura|durata|a\s+che\s+ora|quando\s+(?:e|inizia|finisce)\s+(?:l\s*)?(?:intervallo|ricreazione)|orario\s+(?:dell\s*)?(?:intervallo|ricreazione))\b/.test(q0);
    const explicitDay = /\b(oggi|domani|dopodomani|lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)\b/.test(q0) || Boolean(explicitDate);
    const docs = scoreDocenti(q, idx);
    const sorvDocName = findSorveglianzaDocente(q0, idx);
    const zona = findSorveglianzaZona(q0);
    const wantsSelf = /\b(ho|mio|mia|miei|faccio|devo|tocca)\b/.test(q0);
    return {
      ...base,
      intent: "sorveglianza",
      asksDuration,
      explicitDay,
      docente: docs.length === 1 ? docs[0] : null,
      sorvDocName,
      zona,
      wantsSelf,
      queryText: q0,
    };
  }

  // Controllo per Ore di Recupero & Settimane Q1 / Q2 (Comunicato n. 167, dal 19 novembre 2026)
  const isRecuperoQuery = /\b(recuper[oi]|q1|q2|settimana\s+(?:pari|dispari))\b/.test(q0);
  if (isRecuperoQuery) {
    const asksWeekParity =
      /\b(q1|q2|settimana\s+(?:pari|dispari)|che\s+settimana|quale\s+settimana)\b/.test(q0) &&
      !/\b(chi\s+ha|quando\s+ha|quando\s+ho|ore\s+di\s+recupero)\b/.test(q0);
    const explicitDay = /\b(oggi|domani|dopodomani|lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)\b/.test(q0) || Boolean(explicitDate);
    const docs = scoreDocenti(q, idx);
    const wantsSelf = /\b(ho|mio|mia|miei|devo)\b/.test(q0);
    return {
      ...base,
      intent: "recupero",
      asksWeekParity,
      explicitDay,
      docente: docs.length === 1 ? docs[0] : null,
      wantsSelf,
      queryText: q0,
    };
  }

  // Controllo per le Attività (Collegi docenti, Consigli di classe, Scrutini, Colloqui, ecc.)
  const isAttivita = /\b(attivita|impegni|collegio|collegi|consiglio|consigli|cdc|scrutini|scrutinio|colloqui|colloquio|glo|pdp|pei|dipartimenti|dipartimento|esami|idoneita|debito|debiti|convocazion[ei]|odg|ordine del giorno)\b/.test(q0);

  if (isAttivita) {
    const isCollegio = /\b(collegio|collegi)\b/.test(q0);
    const isColloqui = /\b(colloqui|colloquio)\b/.test(q0);
    const isScrutini = /\b(scrutini|scrutinio)\b/.test(q0);
    const isGlo = /\b(glo|pei)\b/.test(q0);
    const isConsigli = /\b(consiglio|consigli|cdc|convocazion[ei]|odg|ordine del giorno)\b/.test(q0);
    const isDipartimenti = /\b(dipartimenti|dipartimento)\b/.test(q0);
    const monthMatch = q0.match(/\b(settembre|ottobre|novembre|dicembre|gennaio|febbraio|marzo|aprile|maggio|giugno)\b/);
    const mese = monthMatch ? monthMatch[1] : null;
    const docs = scoreDocenti(q, idx);
    const wantsSelf = /\b(ho|mio|mia|miei|faccio|devo|tocca)\b/.test(q0);
    const me = ctx.me ? scoreDocenti(normalize(ctx.me), idx) : [];
    const docente = docs.length === 1 ? docs[0] : (wantsSelf && me.length === 1 ? me[0] : null);
    const isSelf = Boolean(wantsSelf && me.length === 1 && (!docente || docente.id === me[0].id));

    let subType = "generale";
    if (isCollegio) subType = "collegio";
    else if (isColloqui) subType = "colloqui";
    else if (isScrutini) subType = "scrutini";
    else if (isGlo) subType = "glo";
    else if (isConsigli) subType = "consigli_classe";
    else if (isDipartimenti) subType = "dipartimenti";

    return { ...base, intent: "attivita", subType, classi, mese, docente, isSelf, wantsSelf, queryText: q0 };
  }

  // Controllo per Calendario Scolastico (vacanze, inizio/fine lezioni, ponti, festività)
  const isCalendario =
    /\b(calendario|vacanz[ae]|festivit[aà]|pont[ei]|sospension[ei]|rientro|chiusur[ae] scolastic[ae]|chiusur[ae] della scuola|chiusur[ae] dell istituto)\b/.test(q0) ||
    /\b(quando\s+(?:finisce|finiscono|termina|terminano)\s+(?:la\s+scuola|le\s+lezioni|l\s*anno))\b/.test(q0) ||
    /\b(quando\s+(?:inizia|iniziano|comincia|cominciano)\s+(?:la\s+scuola|le\s+lezioni|l\s*anno))\b/.test(q0) ||
    /\b(quando\s+(?:chiude|chiudono)\s+(?:la\s+scuola|i\s+cancelli|gli\s+uffici))\b/.test(q0) ||
    /\b(quando\s+(?:si\s+torna|si\s+rientra)\s+a\s+scuola)\b/.test(q0) ||
    /\b(fine\s+(?:della\s+scuola|scuola|delle\s+lezioni|lezioni)|ultimo\s+giorno\s+di\s+scuola|termine\s+(?:delle\s+lezioni|lezioni))\b/.test(q0) ||
    /\b(inizio\s+(?:della\s+scuola|scuola|delle\s+lezioni|lezioni)|primo\s+giorno\s+di\s+scuola)\b/.test(q0) ||
    /\b(natale|natalizi[ae]|pasqua|pasquali|carnevale|ceneri|mercoledi\s+delle\s+ceneri|patrono|santo\s+patrono|immacolata)\b/.test(q0);

  if (isCalendario) {
    let subType = "generale";
    if (/\b(fine\s+(?:della\s+scuola|scuola|delle\s+lezioni|lezioni)|ultimo\s+giorno\s+di\s+scuola|quando\s+(?:finisce|finiscono|termina|terminano)\s+(?:la\s+scuola|le\s+lezioni|l\s*anno)|termine\s+(?:delle\s+lezioni|lezioni))\b/.test(q0)) {
      subType = "fine_scuola";
    } else if (/\b(inizio\s+(?:della\s+scuola|scuola|delle\s+lezioni|lezioni)|primo\s+giorno\s+di\s+scuola|quando\s+(?:inizia|iniziano|comincia|cominciano)\s+(?:la\s+scuola|le\s+lezioni|l\s*anno))\b/.test(q0)) {
      subType = "inizio_scuola";
    } else if (/\b(natale|natalizi[ae]|vigilia\s+di\s+natale|capodanno|epifania)\b/.test(q0)) {
      subType = "natale";
    } else if (/\b(pasqua|pasquali|settimana\s+santa|lunedi\s+dell\s*angelo|pasquetta)\b/.test(q0)) {
      subType = "pasqua";
    } else if (/\b(carnevale|ceneri|mercoledi\s+delle\s+ceneri)\b/.test(q0)) {
      subType = "carnevale";
    } else if (/\b(pont[ei]|patrono|santo\s+patrono|immacolata|primo\s+maggio|1\s*maggio|festa\s+del\s+lavoro)\b/.test(q0)) {
      subType = "ponti";
    } else if (/\b(festivit[aà]|feste|giorni\s+festivi)\b/.test(q0)) {
      subType = "festivita";
    } else if (isProssimo) {
      subType = "prossima";
    }

    return { ...base, intent: "calendario", subType, targetDateYMD, sospensione, queryText: q0 };
  }

  const mentionsRoomWord = /\b(aula|aule|laboratorio|laboratori|lab|palestra|stanza|stanze)\b/.test(q);
  const wantsFree = /\b(liber[aeio]|vuot[aeio]|disponibil[ei])\b/.test(q);
  const onlyLabs = /\b(laboratori|laboratorio|lab)\b/.test(q);
  const rooms = findRooms(q, idx);

  if (wantsFree && (mentionsRoomWord || rooms.length)) {
    return { ...base, intent: "aule_libere", rooms, onlyLabs };
  }

  const docs = scoreDocenti(q, idx);
  if (docs.length > 1) return { ...base, intent: "ambiguo", candidati: docs };
  if (docs.length === 1) {
    const me = ctx.me ? scoreDocenti(normalize(ctx.me), idx) : [];
    return { ...base, intent: "docente", docente: docs[0], isSelf: me.length === 1 && me[0].id === docs[0].id };
  }
  if (classi.length) return { ...base, intent: "classe", classi };

  const mapSpace = findMapSpace(q0);
  if (isWhere && mapSpace && mapSpace.keywords.some((kw) => kw.includes(" ") && q0.includes(kw))) {
    return { ...base, intent: "spazio_mappa", space: mapSpace };
  }

  if (rooms.length) return { ...base, intent: "aula", rooms };

  if (mapSpace) return { ...base, intent: "spazio_mappa", space: mapSpace };

  const me = ctx.me ? scoreDocenti(normalize(ctx.me), idx) : [];
  if (me.length === 1) return { ...base, intent: "docente", docente: me[0], isSelf: true };

  if (sospensione) {
    return { ...base, intent: "sospensione", targetDateYMD, sospensione };
  }

  return { ...base, intent: "non_trovato" };
}

// ------------------------------------------------------------------ risposte
function groupHours(daySched, sameKey) {
  const groups = [];
  let cur = null;
  for (let h = 1; h <= 8; h++) {
    const s = daySched[String(h)];
    if (!s) {
      if (cur) groups.push(cur);
      cur = null;
      continue;
    }
    if (cur && cur.end === h - 1 && sameKey(cur.slot) === sameKey(s)) cur.end = h;
    else {
      if (cur) groups.push(cur);
      cur = { start: h, end: h, slot: s };
    }
  }
  if (cur) groups.push(cur);
  return groups;
}

const span = (g) => (g.start === g.end ? `${g.start}ª ora` : `${g.start}ª-${g.end}ª ora`);
const spokenSpan = (g) =>
  g.start === g.end
    ? `in ${ORD_WORDS[g.start]} ora`
    : g.end - g.start === 1
    ? `in ${ORD_WORDS[g.start]} e ${ORD_WORDS[g.end]} ora`
    : `dalla ${ORD_WORDS[g.start]} alla ${ORD_WORDS[g.end]} ora`;

const joinSpeech = (parts) =>
  parts.length === 1 ? parts[0] : parts.slice(0, -1).join(", ") + ", e " + parts[parts.length - 1];

export function startOf(idx, h, day = "lunedi") {
  const sched = getDaySchedule(day, idx);
  if (sched) {
    const item = sched.find((s) => s.ora === h);
    if (item) {
      const exitNote = item.uscita ? " - Uscita 12:05" : "";
      return `${item.inizio}-${item.fine}${exitNote}`;
    }
  }
  return idx.starts.find((s) => s.ora === h)?.inizio || "";
}

function saturdayExceeded(p, title) {
  return {
    title,
    badge: "SABATO • USCITA ORE 12:05",
    lines: [],
    note: "Il sabato le lezioni terminano al termine della 4ª ora (ore 12:05).",
    speech: "Il sabato le lezioni terminano alla quarta ora, alle 12:05. Non ci sono lezioni in quinta o sesta ora.",
    rooms: [],
  };
}

function extractRoomsFromText(text) {
  if (!text) return [];
  const m = text.match(/\b\d{3}\b/g);
  return m ? [...new Set(m)] : [];
}

function closedDay(p, title) {
  return {
    title,
    badge: "DOMENICA",
    lines: [],
    note: "Di domenica l'istituto è chiuso.",
    speech: "Di domenica l'istituto è chiuso.",
    rooms: [],
  };
}

function hourBadge(p, idx) {
  const st = startOf(idx, p.hour, p.day);
  return `${dl(p.day).toUpperCase()} • ${p.hour}ª ORA${st ? " (" + st + ")" : ""}`;
}

function noHourNow(p) {
  return {
    title: "Nessuna lezione in corso",
    badge: "ADESSO",
    lines: [],
    note: "In questo momento non c'è lezione (intervallo o fuori orario).",
    speech: "In questo momento non c'è lezione: è intervallo o fuori orario.",
    rooms: [],
  };
}

const ARTICOLATE_PARENT = {
  "1EE": "1ITE", "1ITB": "1ITE",
  "1CAT": "1MMC", "1MMB": "1MMC",
  "2EE": "2MME", "2MMB": "2MME",
  "3AMB": "3BSAM", "3BSB": "3BSAM", "3AM": "3BSAM",
  "3EE": "3ITE", "3ITB": "3ITE",
  "4AM": "4BSAM", "4BS": "4BSAM",
  "4CAT": "4EEC", "4EE": "4EEC",
  "5AM": "5BSAM", "5BS": "5BSAM",
  "5CAT": "5EEC", "5EE": "5EEC",
};

function getExactActivityYMD(item) {
  if (!item) return null;
  if (item.data_iso && /^\d{4}-\d{2}-\d{2}$/.test(item.data_iso)) return item.data_iso;
  const rawDateField = `${item.giorno || ""} ${item.data || ""}`.toLowerCase();
  if (/da\s+definire/.test(rawDateField)) return null;
  if (!/\b\d{1,2}\b/.test(rawDateField)) return null;
  const d = parseActivityDate(item);
  return d ? formatDateYMD(d) : null;
}

function resolveQueryDate(p) {
  if (p.targetDateStr) {
    const [y, m, d] = p.targetDateStr.split("-").map(Number);
    return { ymd: p.targetDateStr, date: new Date(y, m - 1, d, 10, 0) };
  }
  const baseNow = p.now || new Date();
  const targetDow = JS_DAYS.indexOf(p.day);
  if (targetDow < 0) {
    return { ymd: formatDateYMD(baseNow), date: baseNow };
  }
  const offset = (targetDow - baseNow.getDay() + 7) % 7;
  const dt = new Date(baseNow.getFullYear(), baseNow.getMonth(), baseNow.getDate() + offset, 10, 0);
  return { ymd: formatDateYMD(dt), date: dt };
}

function getTeacherClasses(d) {
  const clsSet = new Set();
  for (const daySched of Object.values(d.orario || {})) {
    for (const s of Object.values(daySched || {})) {
      if (s.classe) {
        const up = s.classe.toUpperCase();
        clsSet.add(up);
        if (ARTICOLATE_PARENT[up]) clsSet.add(ARTICOLATE_PARENT[up]);
      }
      for (const ac of s.altre_classi || []) {
        const up = ac.toUpperCase();
        clsSet.add(up);
        if (ARTICOLATE_PARENT[up]) clsSet.add(ARTICOLATE_PARENT[up]);
      }
    }
  }
  return clsSet;
}

function findSorveglianzaKeyForDocente(docName, idx) {
  const perDoc = idx.sorveglianze?.per_docente || {};
  const dNorm = normalize(docName);
  const dTokens = dNorm.split(" ").filter((t) => t.length >= 4);
  for (const key of Object.keys(perDoc)) {
    const kNorm = normalize(key);
    if (kNorm === dNorm || dNorm.includes(kNorm) || kNorm.includes(dNorm)) return key;
    if (dTokens.some((t) => kNorm.split(" ").includes(t))) return key;
  }
  return null;
}

function collectDocenteDayExtras(d, p, idx, resolvedDate) {
  const lines = [];
  const speechParts = [];
  const rooms = [];
  const ymd = resolvedDate.ymd;
  const teacherClasses = getTeacherClasses(d);
  const att = idx.attivita || {};

  // 1) Sorveglianza all'intervallo (in vigore dal 19/11/2026)
  if (ymd >= "2026-11-19") {
    const sorvKey = findSorveglianzaKeyForDocente(d.nome, idx);
    if (sorvKey) {
      const dayTurni = (idx.sorveglianze?.per_docente?.[sorvKey] || []).filter((t) => t.giorno === p.day);
      const rec = recessInfoForDay(p.day);
      for (const t of dayTurni) {
        lines.push({
          when: `Intervallo (${rec.orario})`,
          main: `Sorveglianza • ${t.zona}`,
          sub: `Durata ${rec.durata} min • Comunicato n. 167`,
          aula: null,
        });
        speechParts.push(
          p.isSelf
            ? `all'intervallo delle ${rec.orario} hai sorveglianza in zona ${t.zona}`
            : `all'intervallo delle ${rec.orario} ha sorveglianza in zona ${t.zona}`
        );
      }
    }
  }

  // 2) Consigli di Classe / Scrutini per le classi del docente in questa data
  const consigli = (att.consigli_classe_dettaglio || []).filter((c) => {
    if (getExactActivityYMD(c) !== ymd) return false;
    const cList = (c.classi || []).map((x) => x.toUpperCase());
    if (c.classe_raw) cList.push(c.classe_raw.toUpperCase());
    return cList.some((cls) => teacherClasses.has(cls));
  });
  consigli.sort((a, b) => (a.ora || "").localeCompare(b.ora || ""));
  for (const c of consigli) {
    const isScrut = /scrutini/i.test(c.periodo || "") || /scrutini/i.test(c.giorno || "");
    const label = isScrut ? "Scrutinio" : "Consiglio di Classe";
    const clsLabel = c.classe_raw || (c.classi || []).join("+");
    const aula = c.aula || "Lab. Multimediale";
    lines.push({
      when: `Ore ${c.ora}`,
      main: `${label} ${clsLabel} • ${aula}`,
      sub: c.nota_apertura || c.comunicato || c.periodo || "",
      aula,
    });
    if (aula) rooms.push(aula);
    speechParts.push(
      `alle ${c.ora} il ${label.toLowerCase()} della ${clsLabel}${aula ? " in " + aula : ""}`
    );
  }

  // 3) GLO per le classi del docente in questa data
  const gloMatches = (idx.glo || att.glo || []).filter(
    (g) => getExactActivityYMD(g) === ymd && teacherClasses.has((g.classe || "").toUpperCase())
  );
  gloMatches.sort((a, b) => (a.ora || "").localeCompare(b.ora || ""));
  for (const g of gloMatches) {
    lines.push({
      when: `Ore ${g.ora}`,
      main: `GLO ${g.classe} • ${g.luogo}`,
      sub: "Condivisione PEI (Comunicato n. 83)",
      aula: null,
    });
    speechParts.push(`alle ${g.ora} il GLO della ${g.classe}`);
  }

  // 4) Attività collegiali d'Istituto (Collegi Docenti, Dipartimenti, ecc.)
  const istMatches = (att.attivita_istituto || []).filter((i) => getExactActivityYMD(i) === ymd);
  for (const i of istMatches) {
    const actText = (i.attivita || "").replace(/\s+/g, " ").trim();
    const whenStr = i.orario ? `Ore ${i.orario.replace(/\s+/g, " ").trim()}` : "Istituto";
    lines.push({
      when: whenStr,
      main: actText,
      sub: i.durata ? `Durata: ${i.durata} • Piano Attività` : "Piano Annuale Attività",
      aula: null,
    });
    speechParts.push(i.orario ? `${actText} dalle ${i.orario.replace(/\s+/g, " ").trim()}` : actText);
  }

  // 5) Colloqui Generali (con supporto orari personalizzati docenti dal CSV)
  const teacherDocKey = p.docente?.id || Object.keys(idx.db?.docenti || {}).find((k) => idx.db.docenti[k]?.nome === d.nome) || null;
  const docColloquiInfo = idx.colloqui_docenti?.per_docente?.[teacherDocKey] || null;

  if (docColloquiInfo && (ymd === "2026-12-03" || ymd === "2026-12-04")) {
    if (ymd === "2026-12-03" && docColloquiInfo.biennio?.attivo) {
      const b = docColloquiInfo.biennio;
      if (b.assente) {
        lines.push({
          when: "Pomeriggio",
          main: "Colloqui Generali • Assente giustificato",
          sub: "Docente assente ai colloqui del biennio (Comunicato n. 185)",
          aula: null,
        });
        speechParts.push(p.isSelf ? "nel pomeriggio risulti assente giustificato ai colloqui del biennio" : "nel pomeriggio risulta assente giustificato ai colloqui del biennio");
      } else {
        const defaultNote = b.orario_default ? " (orario d'istituto)" : "";
        lines.push({
          when: `Ore ${b.orario}`,
          main: `Colloqui Generali • Negrelli (biennio)`,
          sub: `Classi: ${b.classi.join(", ")}${defaultNote} • in presenza`,
          aula: null,
        });
        speechParts.push(`dalle ${b.orario.replace("-", " alle ")} i colloqui generali per il biennio (Negrelli)`);
      }
    } else if (ymd === "2026-12-04" && docColloquiInfo.triennio?.attivo) {
      const t = docColloquiInfo.triennio;
      if (t.assente) {
        lines.push({
          when: "Pomeriggio",
          main: "Colloqui Generali • Assente giustificato",
          sub: "Docente assente ai colloqui del triennio (Comunicato n. 185)",
          aula: null,
        });
        speechParts.push(p.isSelf ? "nel pomeriggio risulti assente giustificato ai colloqui del triennio" : "nel pomeriggio risulta assente giustificato ai colloqui del triennio");
      } else {
        const defaultNote = t.orario_default ? " (orario d'istituto)" : "";
        const noteExtra = docColloquiInfo.note ? ` • ${docColloquiInfo.note}` : "";
        lines.push({
          when: `Ore ${t.orario}`,
          main: `Colloqui Generali • Negrelli (triennio)`,
          sub: `Classi: ${t.classi.join(", ")}${defaultNote}${noteExtra} • in presenza`,
          aula: null,
        });
        speechParts.push(`dalle ${t.orario.replace("-", " alle ")} i colloqui generali per il triennio (Negrelli)`);
      }
    }
  } else {
    // Fallback per II periodo o altri plessi (Colotti, Rizzarda)
    const hasBiennio = [...teacherClasses].some((c) => /^[12]/.test(c));
    const hasTriennio = [...teacherClasses].some((c) => /^[345]/.test(c));
    const hasColotti = [...teacherClasses].some((c) => /AFM|RIM|BRIM/i.test(c));
    const hasRizzarda = [...teacherClasses].some((c) => /ASS|SSAS|IAMI/i.test(c));
    const hasNegrelli = [...teacherClasses].some((c) => !/AFM|RIM|BRIM|ASS|SSAS|IAMI/i.test(c));
    const collMatches = (att.colloqui_generali || []).filter((c) => {
      if (getExactActivityYMD(c) !== ymd) return false;
      const sede = (c.sede || "").toLowerCase();
      const fascia = (c.classi || "").toLowerCase();
      if (sede === "negrelli") {
        if (!hasNegrelli) return false;
        if (fascia === "biennio") return hasBiennio;
        if (fascia === "triennio") return hasTriennio;
        return true;
      }
      if (sede === "colotti") return hasColotti;
      if (sede === "rizzarda") return hasRizzarda;
      return true;
    });
    for (const c of collMatches) {
      const whenStr = c.orario ? `Ore ${c.orario}` : "Pomeriggio";
      const subParts = [];
      if (c.modalita) subParts.push(c.modalita);
      if (c.comunicato) subParts.push(c.comunicato);
      else if (c.periodo) subParts.push(c.periodo);
      lines.push({
        when: whenStr,
        main: `Colloqui Generali • ${c.sede} (${c.classi})`,
        sub: subParts.join(" • "),
        aula: null,
      });
      const orarioSpeech = c.orario ? `dalle ${c.orario.replace("-", " alle ")} ` : "";
      speechParts.push(`${orarioSpeech}i colloqui generali per il ${c.classi} (${c.sede})`);
    }
  }

  return { lines, speechParts, rooms };
}

function collectClasseDayExtras(cid, p, idx, resolvedDate) {
  const lines = [];
  const speechParts = [];
  const rooms = [];
  const ymd = resolvedDate.ymd;
  const cidUp = cid.toUpperCase();
  const parentUp = ARTICOLATE_PARENT[cidUp] || null;
  const att = idx.attivita || {};

  // 1) Consigli di Classe / Scrutini
  const consigli = (att.consigli_classe_dettaglio || []).filter((c) => {
    if (getExactActivityYMD(c) !== ymd) return false;
    const cList = (c.classi || []).map((x) => x.toUpperCase());
    if (c.classe_raw) cList.push(c.classe_raw.toUpperCase());
    return cList.includes(cidUp) || (parentUp && cList.includes(parentUp));
  });
  for (const c of consigli) {
    const isScrut = /scrutini/i.test(c.periodo || "") || /scrutini/i.test(c.giorno || "");
    const label = isScrut ? "Scrutinio" : "Consiglio di Classe";
    const aula = c.aula || "Lab. Multimediale";
    lines.push({
      when: `Ore ${c.ora}`,
      main: `${label} ${c.classe_raw || cidUp} • ${aula}`,
      sub: c.nota_apertura || c.comunicato || c.periodo || "",
      aula,
    });
    if (aula) rooms.push(aula);
    speechParts.push(`alle ${c.ora} è previsto il ${label.toLowerCase()}${aula ? " in " + aula : ""}`);
  }

  // 2) GLO
  const gloMatches = (idx.glo || att.glo || []).filter(
    (g) => getExactActivityYMD(g) === ymd && ((g.classe || "").toUpperCase() === cidUp || (parentUp && (g.classe || "").toUpperCase() === parentUp))
  );
  for (const g of gloMatches) {
    lines.push({
      when: `Ore ${g.ora}`,
      main: `GLO ${g.classe} • ${g.luogo}`,
      sub: "Condivisione PEI (Comunicato n. 83)",
      aula: null,
    });
    speechParts.push(`alle ${g.ora} c'è il GLO`);
  }

  // 3) Colloqui Generali
  const isBiennio = /^[12]/.test(cidUp);
  const isColotti = /AFM|RIM|BRIM/i.test(cidUp);
  const isRizzarda = /ASS|SSAS|IAMI/i.test(cidUp);
  const isNegrelli = !isColotti && !isRizzarda;
  const collMatches = (att.colloqui_generali || []).filter((c) => {
    if (getExactActivityYMD(c) !== ymd) return false;
    const sede = (c.sede || "").toLowerCase();
    if (sede === "colotti" && !isColotti) return false;
    if (sede === "rizzarda" && !isRizzarda) return false;
    if (sede === "negrelli" && !isNegrelli) return false;
    const fascia = (c.classi || "").toLowerCase();
    return fascia === "tutte" || (isBiennio ? fascia === "biennio" : fascia === "triennio");
  });
  for (const c of collMatches) {
    const whenStr = c.orario ? `Ore ${c.orario}` : "Pomeriggio";
    const subParts = [];
    if (c.modalita) subParts.push(c.modalita);
    if (c.comunicato) subParts.push(c.comunicato);
    else if (c.periodo) subParts.push(c.periodo);
    lines.push({
      when: whenStr,
      main: `Colloqui Generali • ${c.sede} (${c.classi})`,
      sub: subParts.join(" • "),
      aula: null,
    });
    const orarioSpeech = c.orario ? `dalle ${c.orario.replace("-", " alle ")} ` : "";
    speechParts.push(`${orarioSpeech}ci sono i colloqui generali in presenza (${c.sede})`);
  }

  return { lines, speechParts, rooms };
}

function answerDocente(p, idx) {
  const d = idx.db.docenti[p.docente.id];
  const isPlaceholder = Boolean(d.senza_nome || d.nome.startsWith("_"));
  const nomeDisplay = formatDocenteName(d.nome);
  const title = isPlaceholder
    ? `${nomeDisplay} (Docente in arrivo)`
    : p.isSelf
    ? `Prof. ${titleCase(d.nome)} (Tu)`
    : `Prof. ${titleCase(d.nome)}`;

  if (p.day === "domenica") return closedDay(p, title);
  if (p.day === "sabato" && p.hour > 4) return saturdayExceeded(p, title);
  if (p.realtime && p.hour === null) return { ...noHourNow(p), title };

  const sched = d.orario[p.day] || {};
  const dayCap = cap(dl(p.day));
  const subj = p.isSelf ? "" : spokenDocenteName(d.nome);
  const resolvedDate = resolveQueryDate(p);
  const weekParity = getWeekParity(resolvedDate.date);

  const describe = (s) => {
    if (s.tipo === "recupero") {
      const sett = s.settimana || "tutte";
      const isActive = sett === "tutte" || sett === weekParity.code;
      const statusTag = sett === "tutte" ? "Settimanale" : isActive ? `${sett} • Attivo` : `${sett} • Non attivo (sett. ${weekParity.code})`;
      const settLabel =
        sett === "Q1"
          ? "Settimana Q1 (dispari)"
          : sett === "Q2"
          ? "Settimana Q2 (pari)"
          : "Settimanale (ogni settimana)";
      const settSay =
        sett === "Q1"
          ? "nelle settimane dispari Q1"
          : sett === "Q2"
          ? "nelle settimane pari Q2"
          : "ogni settimana";
      return {
        main: `Recupero (${statusTag})`,
        sub: `${settLabel} • Comunicato n. 167`,
        say: p.isSelf ? `hai recupero ${settSay}` : `ha recupero ${settSay}`,
        aula: null,
      };
    }
    if (s.tipo === "disposizione") {
      const dove = s.aula ? ` in ${titleCase(s.aula)}` : "";
      return {
        main: `Disposizione${dove}`,
        sub: "",
        say: p.isSelf ? `sarai a disposizione${dove}` : `è a disposizione${dove}`,
        aula: s.aula || null,
      };
    }
    const extra = [...(s.altre_classi || [])];
    const cls = [s.classe, ...extra].filter(Boolean).join(" + ");
    const con = s.copresenza?.length ? s.copresenza.map(formatDocenteName).join(", ") : "";
    const conSay = s.copresenza?.length ? s.copresenza.map(spokenDocenteName).join(", ") : "";
    const mat = s.materia ? titleCase(s.materia) : "materia non indicata";
    const aula = s.aula ? titleCase(s.aula) : "aula non indicata";
    if (!cls) {
      const mainLabel = s.aula && s.aula.toLowerCase() !== mat.toLowerCase() ? `${mat} • ${aula}` : mat;
      return {
        main: mainLabel,
        sub: con ? `con ${con}` : "Sede esterna / attività",
        say: p.isSelf ? `sei in ${mat}` : `è in ${mat}`,
        aula: s.aula || null,
      };
    }
    const verb = s.tipo === "compresenza" ? "è in compresenza" : "ha lezione";
    return {
      main: `${aula} • ${cls}`,
      sub: `${mat}${con ? " · con " + con : ""}`,
      say: `${p.isSelf ? "avrai lezione" : verb} di ${mat} con la ${cls}, in ${aula}${conSay ? ", insieme a " + conSay : ""}`
        .replace(/\binsieme a il\b/gi, "insieme al")
        .replace(/\binsieme a la\b/gi, "insieme alla"),
      aula: s.aula || null,
    };
  };

  if (p.hour === null) {
    const groups = groupHours(
      sched,
      (s) => JSON.stringify([s.tipo, s.settimana, s.classe, s.materia, s.aula, s.copresenza, s.altre_classi])
    );
    const extras = collectDocenteDayExtras(d, p, idx, resolvedDate);
    const dateLabel = formatDateSpoken(resolvedDate.ymd);

    if (!groups.length && !extras.lines.length) {
      return {
        title,
        badge: `${dl(p.day).toUpperCase()} • GIORNATA`,
        lines: [],
        note: isPlaceholder ? "Nessuna lezione in orario (cattedra provvisoria)." : "Nessuna lezione o attività in programma.",
        speech: p.isSelf ? `${dayCap} non hai lezioni in orario.` : `${dayCap} ${subj} non ha lezioni in orario.`,
        rooms: [],
      };
    }

    if (!groups.length && extras.lines.length) {
      return {
        title,
        badge: `${dl(p.day).toUpperCase()} ${dateLabel.toUpperCase()} • ATTIVITÀ`,
        lines: extras.lines,
        note: "Nessuna lezione al mattino, ma risultano impegni collegiali/sorveglianza in agenda.",
        speech: `${dayCap} ${p.isSelf ? "non hai lezioni al mattino, ma hai" : subj + " non ha lezioni al mattino, ma ha"} ${joinSpeech(extras.speechParts)}.`.replace(/\s+/g, " "),
        rooms: extras.rooms,
      };
    }

    const descs = groups.map((g) => ({ g, ...describe(g.slot) }));
    const lessonLines = descs.map((x) => ({ when: span(x.g), main: x.main, sub: x.sub, aula: x.aula }));
    const allLines = extras.lines.length
      ? [...lessonLines, { when: `IMPEGNI & ATTIVITÀ (${dateLabel.toUpperCase()})`, heading: true }, ...extras.lines]
      : lessonLines;
    const roomsCollected = [...descs.map((x) => x.aula).filter(Boolean), ...extras.rooms];
    const baseSpeech = `${dayCap} ${subj} ${joinSpeech(descs.map((x) => `${spokenSpan(x.g)} ${x.say}`))}.`.replace(/\s+/g, " ");
    const extraSpeech = extras.speechParts.length
      ? ` Inoltre, per il ${dateLabel}: ${joinSpeech(extras.speechParts)}.`
      : "";

    return {
      title,
      badge: extras.lines.length
        ? `${dl(p.day).toUpperCase()} ${dateLabel.toUpperCase()} • AGENDA COMPLETA`
        : `${dl(p.day).toUpperCase()} • GIORNATA INTERA`,
      lines: allLines,
      note: extras.lines.length ? `Include lezioni, sorveglianze e attività collegiali del ${dateLabel}.` : "",
      speech: `${baseSpeech}${extraSpeech}`.replace(/\s+/g, " ").trim(),
      rooms: roomsCollected,
    };
  }

  const s = sched[String(p.hour)];
  const when = `${ORD_WORDS[p.hour] || p.hour} ora`;
  if (!s) {
    return {
      title,
      badge: hourBadge(p, idx),
      lines: [],
      note: "Nessuna lezione in quest'ora.",
      speech: p.isSelf ? `${dayCap} in ${when} non hai lezioni.` : `${dayCap} in ${when} ${subj} non ha lezioni.`,
      rooms: [],
    };
  }
  const x = describe(s);
  return {
    title,
    badge: hourBadge(p, idx),
    lines: [{ when: `${p.hour}ª ora`, main: x.main, sub: x.sub, aula: x.aula }],
    speech: `${dayCap} in ${when} ${subj} ${x.say}.`.replace(/\s+/g, " "),
    rooms: x.aula ? [x.aula] : [],
  };
}

function answerClasse(p, idx) {
  const out = [];
  for (const cid of p.classi) {
    const sched = idx.db.classi[cid]?.[p.day] || {};
    const describe = (s) => {
      const doc = s.docenti?.length ? s.docenti.map(formatDocenteName).join(" e ") : "";
      const docSay = s.docenti?.length ? s.docenti.map(spokenDocenteName).join(" e ") : "";
      const mat = s.materia ? titleCase(s.materia) : "";
      const where = s.aula ? `in ${titleCase(s.aula)}` : "in aula";
      return {
        main: `${mat}${doc ? " • " + doc : ""}`,
        sub: s.aula ? titleCase(s.aula) : "Aula ordinaria",
        say: `ha ${mat}${docSay ? " con " + docSay : ""}, ${where}`,
        aula: s.aula || null,
      };
    };

    if (p.day === "domenica") {
      out.push(closedDay(p, `Classe ${cid}`));
      continue;
    }
    if (p.day === "sabato" && p.hour > 4) {
      out.push(saturdayExceeded(p, `Classe ${cid}`));
      continue;
    }
    if (p.realtime && p.hour === null) {
      out.push({ ...noHourNow(p), title: `Classe ${cid}` });
      continue;
    }
    const dayCap = cap(dl(p.day));

    if (p.hour === null) {
      const resolvedDate = resolveQueryDate(p);
      const dateLabel = formatDateSpoken(resolvedDate.ymd);
      const extras = collectClasseDayExtras(cid, p, idx, resolvedDate);
      const groups = groupHours(sched, (s) => JSON.stringify([s.materia, s.docenti, s.aula]));
      if (!groups.length && !extras.lines.length) {
        out.push({
          title: `Classe ${cid}`,
          badge: `${dl(p.day).toUpperCase()} • GIORNATA`,
          lines: [],
          note: "Nessuna lezione in orario.",
          speech: `${dayCap} la ${cid} non ha lezioni in orario.`,
          rooms: [],
        });
        continue;
      }
      const descs = groups.map((g) => ({ g, ...describe(g.slot) }));
      const lessonLines = descs.map((x) => ({ when: span(x.g), main: x.main, sub: x.sub, aula: x.aula }));
      const allLines = extras.lines.length
        ? (lessonLines.length
            ? [...lessonLines, { when: `IMPEGNI & ATTIVITÀ (${dateLabel.toUpperCase()})`, heading: true }, ...extras.lines]
            : extras.lines)
        : lessonLines;
      const baseSpeech = lessonLines.length
        ? `${dayCap} la ${cid} ${joinSpeech(descs.map((x) => `${spokenSpan(x.g)} ${x.say}`))}.`
        : `${dayCap} la ${cid} non ha lezioni in orario.`;
      const extraSpeech = extras.speechParts.length
        ? ` Inoltre, per il ${dateLabel}, ${joinSpeech(extras.speechParts)}.`
        : "";
      out.push({
        title: `Classe ${cid}`,
        badge: extras.lines.length
          ? `${dl(p.day).toUpperCase()} ${dateLabel.toUpperCase()} • AGENDA COMPLETA`
          : `${dl(p.day).toUpperCase()} • GIORNATA INTERA`,
        lines: allLines,
        note: extras.lines.length ? `Include lezioni e attività del ${dateLabel}.` : "",
        speech: `${baseSpeech}${extraSpeech}`.replace(/\s+/g, " ").trim(),
        rooms: [...descs.map((x) => x.aula).filter(Boolean), ...extras.rooms],
      });
      continue;
    }

    const s = sched[String(p.hour)];
    const when = `${ORD_WORDS[p.hour] || p.hour} ora`;
    if (!s) {
      out.push({
        title: `Classe ${cid}`,
        badge: hourBadge(p, idx),
        lines: [],
        note: "Nessuna lezione in quest'ora.",
        speech: `${dayCap} in ${when} la ${cid} non ha lezione.`,
        rooms: [],
      });
      continue;
    }
    const x = describe(s);
    out.push({
      title: `Classe ${cid}`,
      badge: hourBadge(p, idx),
      lines: [{ when: `${p.hour}ª ora`, main: x.main, sub: x.sub, aula: x.aula }],
      speech: `${dayCap} in ${when} la ${cid} ${x.say}.`,
      rooms: x.aula ? [x.aula] : [],
    });
  }
  return mergeAnswers(out);
}

function mergeAnswers(list) {
  if (list.length === 1) return list[0];
  const allRooms = [...new Set(list.flatMap((a) => a.rooms || []))];
  return {
    title: list.map((a) => a.title).join(" / "),
    badge: list[0].badge,
    lines: list.flatMap((a) =>
      a.lines.length
        ? [{ when: a.title, main: "", sub: "", heading: true }, ...a.lines]
        : [{ when: a.title, main: a.note || "", sub: "" }]
    ),
    speech: list.map((a) => a.speech).join(" "),
    rooms: allRooms,
  };
}

function answerAuleLibere(p, idx) {
  const title = p.onlyLabs ? "Laboratori liberi" : "Aule libere";
  if (p.day === "domenica") return closedDay(p, title);
  if (p.day === "sabato" && p.hour > 4) return saturdayExceeded(p, title);
  if (p.realtime && p.hour === null) return { ...noHourNow(p), title };

  const libereGiorno = idx.db.aule_libere[p.day] || {};
  const filter = (list) => {
    let res = list;
    if (p.rooms?.length) res = res.filter((a) => p.rooms.some((r) => r.nome === a));
    if (p.onlyLabs) res = res.filter((a) => /lab|laboratorio/i.test(a));
    return res;
  };

  const dayCap = cap(dl(p.day));

  if (p.hour === null) {
    const lines = Object.keys(libereGiorno).map((h) => ({
      when: `${h}ª ora`,
      main: filter(libereGiorno[h] || []).map(titleCase).join(", ") || "nessuna",
      sub: "",
    }));
    return {
      title,
      badge: `${dl(p.day).toUpperCase()} • TUTTE LE ORE`,
      lines,
      note: "Disponibilità calcolata su tutte le aule e laboratori dell'istituto.",
      speech: `Per quale ora? Ti mostro le disponibilità di ${dl(p.day)} per ogni ora.`,
      rooms: [],
    };
  }

  const free = filter(libereGiorno[String(p.hour)] || []);
  const when = `${ORD_WORDS[p.hour] || p.hour} ora`;

  if (p.rooms?.length) {
    const lines = p.rooms.map((r) => ({
      when: titleCase(r.nome),
      main: free.includes(r.nome) ? "Libera" : "Occupata",
      sub: "",
    }));
    return {
      title: "Disponibilità aula",
      badge: hourBadge(p, idx),
      lines,
      note: "Disponibilità verificata sull'orario d'istituto.",
      speech:
        `${dayCap} in ${when}: ` +
        p.rooms.map((r) => `${titleCase(r.nome)} è ${free.includes(r.nome) ? "libera" : "occupata"}`).join(", ") +
        ".",
      rooms: free,
    };
  }

  return {
    title,
    badge: hourBadge(p, idx),
    lines: free.map((a) => ({ when: "Libera", main: titleCase(a), sub: "", aula: a })),
    note: free.length ? "" : "Tutti gli spazi richiesti risultano occupati.",
    speech: free.length
      ? `${dayCap} in ${when} sono disponibili: ${joinSpeech(free.map(titleCase))}.`
      : `${dayCap} in ${when} tutti gli spazi risultano occupati.`,
    rooms: free,
  };
}

function answerAula(p, idx) {
  const out = [];
  for (const r of p.rooms) {
    const title = titleCase(r.nome);
    const loc = resolveRoomLocation(r.nome);
    const locNote = loc ? `📍 ${loc.floorLabel} • ${loc.wing}.` : "";
    const locSpeech = loc ? `${title} si trova al ${loc.floorLabel.toLowerCase()}, ${loc.wing}. ` : "";

    if (p.day === "domenica") {
      const c = closedDay(p, title);
      out.push({ ...c, rooms: [r.nome], note: locNote ? `${locNote} ${c.note}` : c.note, speech: p.isWhere ? `${locSpeech}${c.speech}` : c.speech });
      continue;
    }
    if (p.day === "sabato" && p.hour > 4) {
      const s = saturdayExceeded(p, title);
      out.push({ ...s, rooms: [r.nome], note: locNote ? `${locNote} ${s.note}` : s.note, speech: p.isWhere ? `${locSpeech}${s.speech}` : s.speech });
      continue;
    }
    if (p.realtime && p.hour === null) {
      const n = noHourNow(p);
      out.push({ ...n, title, rooms: [r.nome], note: locNote ? `${locNote} ${n.note}` : n.note, speech: p.isWhere ? `${locSpeech}${n.speech}` : n.speech });
      continue;
    }

    const occ = idx.db.aule[r.nome]?.[p.day] || {};
    const dayCap = cap(dl(p.day));
    const desc = (o) =>
      `${o.classe}${o.materia ? " (" + titleCase(o.materia) + ")" : ""}${
        o.docenti?.length ? " con " + o.docenti.map(titleCase).join(" e ") : ""
      }`;

    if (p.hour === null) {
      const lines = Object.keys(occ)
        .sort((a, b) => a - b)
        .map((h) => ({ when: `${h}ª ora`, main: desc(occ[h]), sub: "", aula: r.nome }));
      const baseNote = lines.length ? "" : "Non occupata in questa giornata.";
      const baseSpeech = lines.length
        ? `${dayCap} ${title} è occupata in ${lines.length} ore.`
        : `${dayCap} ${title} è libera per l'intera giornata.`;
      out.push({
        title,
        badge: `${dl(p.day).toUpperCase()} • GIORNATA`,
        lines,
        note: [locNote, baseNote].filter(Boolean).join(" "),
        speech: p.isWhere ? `${locSpeech}${baseSpeech}` : baseSpeech,
        rooms: [r.nome],
      });
      continue;
    }

    const o = occ[String(p.hour)];
    const when = `${ORD_WORDS[p.hour] || p.hour} ora`;
    out.push(
      o
        ? {
            title,
            badge: hourBadge(p, idx),
            lines: [{ when: "Occupata", main: desc(o), sub: "", aula: r.nome }],
            note: locNote,
            speech: `${p.isWhere ? locSpeech : ""}${dayCap} in ${when} ${title} è occupata dalla ${desc(o)}.`,
            rooms: [r.nome],
          }
        : {
            title,
            badge: hourBadge(p, idx),
            lines: [{ when: "Libera", main: "", sub: "", aula: r.nome }],
            note: locNote,
            speech: `${p.isWhere ? locSpeech : ""}${dayCap} in ${when} ${title} è libera.`,
            rooms: [r.nome],
          }
    );
  }
  return mergeAnswers(out);
}

function answerSpazioMappa(p) {
  const sp = p.space;
  return {
    title: sp.name,
    badge: `MAPPA ISTITUTO • ${sp.floorLabel}`,
    lines: [
      { when: "Piano", main: sp.floorLabel, sub: `Codice locale: ${sp.code}` },
      { when: "Posizione", main: sp.wing, sub: "Clicca sul badge posizione o apri la Mappa 2D per vederlo in pianta" },
    ],
    note: `Locale individuato sulle planimetrie ufficiali dell'istituto (${sp.floorLabel}).`,
    speech: `${sp.name} si trova al ${sp.floorLabel.toLowerCase()}, ${sp.wing}.`,
    rooms: [sp.code],
  };
}

const SORVEGLIANZA_ZONE_PATTERNS = [
  { label: "Scale lato bagni", re: /\b(scale?\s+lato\s+bagn[oi]|lato\s+bagn[oi]|bagn[oi])\b/ },
  { label: "Scale lato didattica", re: /\b(scale?\s+lato\s+didattica|lato\s+didattica|didattica)\b/ },
  { label: "MC Mario", re: /\b(mc\s*mario|mario)\b/ },
  { label: "Cortile ingresso", re: /\b(cortile|ingresso|cortile\s+ingresso)\b/ },
  { label: "Piano Terra", re: /\b(piano\s+terra|p\s*t|piano\s+0)\b/ },
  { label: "1° Piano", re: /\b(primo\s+piano|piano\s+primo|1\s*piano|piano\s+1)\b/ },
  { label: "2° Piano", re: /\b(secondo\s+piano|piano\s+secondo|2\s*piano|piano\s+2)\b/ },
  { label: "Laboratori", re: /\b(laboratori[o]?|lab)\b/ },
];

function findSorveglianzaZona(qNorm) {
  for (const z of SORVEGLIANZA_ZONE_PATTERNS) {
    if (z.re.test(qNorm)) return z.label;
  }
  return null;
}

function findSorveglianzaDocente(qNorm, idx) {
  const perDoc = idx.sorveglianze?.per_docente || {};
  const qWords = new Set(qNorm.split(" ").filter((w) => w.length >= 3));
  let best = null;
  let bestLen = 0;
  for (const name of Object.keys(perDoc)) {
    const nNorm = normalize(name);
    if (new RegExp(`(^|\\s)${nNorm}(\\s|$)`).test(qNorm)) {
      if (nNorm.length > bestLen) {
        best = name;
        bestLen = nNorm.length;
      }
      continue;
    }
    const tokens = nNorm.split(" ").filter((t) => t.length >= 4);
    if (tokens.some((t) => qWords.has(t)) && nNorm.length > bestLen) {
      best = name;
      bestLen = nNorm.length;
    }
  }
  return best;
}

function recessInfoForDay(day) {
  if (["lunedi", "martedi", "mercoledi"].includes(day)) {
    return { orario: "10:25-10:35", durata: 10, label: "10:25–10:35 (10 minuti)" };
  }
  return { orario: "10:50-11:05", durata: 15, label: "10:50–11:05 (15 minuti)" };
}

function answerSorveglianza(p, idx, ctx = {}) {
  const sorv = idx.sorveglianze || {};
  const perGiorno = sorv.per_giorno || {};
  const perDocente = sorv.per_docente || {};
  const noteStd =
    "Comunicato n. 167 (in vigore dal 19/11/2026). In caso di variazioni comunicare la modifica all'Ufficio Tecnico dopo aver individuato il sostituto.";

  // 1) Richiesta durata / orario intervallo
  if (p.asksDuration) {
    return {
      title: "Orario e Durata Intervallo",
      badge: "COMUNICATO N. 167",
      lines: [
        { when: "Lun – Mer", main: "10:25 – 10:35 (10 minuti)", sub: "Tra la 3ª e la 4ª ora" },
        { when: "Gio – Sab", main: "10:50 – 11:05 (15 minuti)", sub: "Tra la 3ª e la 4ª ora" },
      ],
      note: noteStd,
      speech: "L'intervallo dura 10 minuti dal lunedì al mercoledì, dalle 10:25 alle 10:35, e 15 minuti dal giovedì al sabato, dalle 10:50 alle 11:05.",
      rooms: [],
    };
  }

  // 2) Risoluzione docente (esplicito o self via ctx.me)
  let targetDocName = p.sorvDocName || null;
  let isSelf = false;
  if (!targetDocName && p.docente) {
    const docKeyNorm = normalize(p.docente.nome);
    const hit = Object.keys(perDocente).find((k) => {
      const kn = normalize(k);
      return kn === docKeyNorm || docKeyNorm.includes(kn) || kn.includes(docKeyNorm);
    });
    targetDocName = hit || p.docente.nome;
  }
  if (!targetDocName && !p.zona && p.wantsSelf && ctx.me) {
    const meNorm = normalize(ctx.me);
    const hit = Object.keys(perDocente).find((k) => {
      const kn = normalize(k);
      return kn === meNorm || meNorm.includes(kn) || kn.includes(meNorm);
    });
    targetDocName = hit || titleCase(ctx.me);
    isSelf = true;
  } else if (targetDocName && ctx.me) {
    const meNorm = normalize(ctx.me);
    const tNorm = normalize(targetDocName);
    isSelf = meNorm === tNorm || meNorm.includes(tNorm) || tNorm.includes(meNorm);
  }

  if (targetDocName) {
    const turniDoc = perDocente[targetDocName] || [];
    const displayDoc = isSelf ? `Prof. ${targetDocName} (Tu)` : `Prof. ${targetDocName}`;
    if (!turniDoc.length) {
      return {
        title: `Sorveglianze • ${displayDoc}`,
        badge: "SORVEGLIANZE • DAL 19 NOV",
        lines: [],
        note: `Nessun turno di sorveglianza assegnato nel prospetto dal 19 novembre 2026. ${noteStd}`,
        speech: isSelf
          ? "Non hai turni di sorveglianza assegnati all'intervallo nel prospetto dal 19 novembre."
          : `Il professor ${targetDocName} non ha turni di sorveglianza assegnati nel prospetto dal 19 novembre.`,
        rooms: [],
      };
    }

    if (p.explicitDay) {
      if (p.day === "domenica") return closedDay(p, `Sorveglianze • ${displayDoc}`);
      const dayTurni = turniDoc.filter((t) => t.giorno === p.day);
      const rec = recessInfoForDay(p.day);
      const dayCap = cap(dl(p.day));
      const allLines = turniDoc.map((t) => {
        const r = recessInfoForDay(t.giorno);
        return {
          when: cap(dl(t.giorno)),
          main: t.zona,
          sub: `Intervallo ${r.label}`,
        };
      });
      if (dayTurni.length) {
        const zoneStr = dayTurni.map((t) => t.zona).join(" e ");
        return {
          title: `Sorveglianza ${displayDoc}`,
          badge: `${dl(p.day).toUpperCase()} • ${rec.orario}`,
          lines: dayTurni.map((t) => ({ when: dayCap, main: t.zona, sub: `Intervallo ${rec.label}` })),
          note: noteStd,
          speech: isSelf
            ? `${dayCap} hai sorveglianza in zona ${zoneStr}, durante l'intervallo delle ${rec.orario}.`
            : `${dayCap} il professor ${targetDocName} ha sorveglianza in zona ${zoneStr}, durante l'intervallo delle ${rec.orario}.`,
          rooms: [],
        };
      }
      const otherStr = turniDoc.map((t) => `${dl(t.giorno)} in zona ${t.zona}`).join(" e ");
      return {
        title: `Sorveglianza ${displayDoc}`,
        badge: `${dl(p.day).toUpperCase()} • LIBERO`,
        lines: allLines,
        note: `${dayCap} non ha sorveglianza. Di seguito i turni settimanali assegnati. ${noteStd}`,
        speech: isSelf
          ? `${dayCap} non hai sorveglianza. Il tuo turno settimanale è ${otherStr}.`
          : `${dayCap} il professor ${targetDocName} non ha sorveglianza. Il suo turno settimanale è ${otherStr}.`,
        rooms: [],
      };
    }

    const lines = turniDoc.map((t) => {
      const r = recessInfoForDay(t.giorno);
      return { when: cap(dl(t.giorno)), main: t.zona, sub: `Intervallo ${r.label}` };
    });
    const spoken = turniDoc.map((t) => `${dl(t.giorno)} in zona ${t.zona}`).join(" e ");
    return {
      title: `Sorveglianze • ${displayDoc}`,
      badge: "SORVEGLIANZE • DAL 19 NOV",
      lines,
      note: noteStd,
      speech: isSelf
        ? `Hai sorveglianza all'intervallo ${spoken}.`
        : `Il professor ${targetDocName} ha sorveglianza all'intervallo ${spoken}.`,
      rooms: [],
    };
  }

  // 3) Per zona specifica (es. "sorveglianza cortile ingresso", "sorveglianza laboratori giovedì")
  if (p.zona) {
    const giorniOrd = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"];
    if (p.explicitDay) {
      if (p.day === "domenica") return closedDay(p, `Sorveglianza • ${p.zona}`);
      const list = (perGiorno[p.day] || []).filter((x) => x.zona === p.zona);
      const docs = list.flatMap((x) => x.docenti);
      const rec = recessInfoForDay(p.day);
      const dayCap = cap(dl(p.day));
      return {
        title: `Sorveglianza • ${p.zona}`,
        badge: `${dl(p.day).toUpperCase()} • ${rec.orario}`,
        lines: docs.length
          ? [{ when: dayCap, main: docs.join(", "), sub: `${p.zona} • Intervallo ${rec.label}` }]
          : [],
        note: noteStd,
        speech: docs.length
          ? `${dayCap} la sorveglianza in zona ${p.zona} è affidata a ${joinSpeech(docs)}.`
          : `${dayCap} non risultano docenti assegnati alla zona ${p.zona}.`,
        rooms: [],
      };
    }
    const lines = [];
    for (const g of giorniOrd) {
      const list = (perGiorno[g] || []).filter((x) => x.zona === p.zona);
      const docs = list.flatMap((x) => x.docenti);
      if (docs.length) {
        const rec = recessInfoForDay(g);
        lines.push({ when: cap(dl(g)), main: docs.join(", "), sub: `Intervallo ${rec.label}` });
      }
    }
    return {
      title: `Turni Sorveglianza • ${p.zona}`,
      badge: "SORVEGLIANZE • DAL 19 NOV",
      lines,
      note: noteStd,
      speech: `Ecco i turni settimanali di sorveglianza per la zona ${p.zona}: ` + lines.map((l) => `${l.when} ${l.main}`).join(", ") + ".",
      rooms: [],
    };
  }

  // 4) Per giorno (default: giorno della query o oggi)
  if (p.day === "domenica") return closedDay(p, "Turni di Sorveglianza");
  const dayItems = perGiorno[p.day] || [];
  const rec = recessInfoForDay(p.day);
  const dayCap = cap(dl(p.day));
  const lines = dayItems.map((it) => ({
    when: it.zona,
    main: it.docenti.join(", "),
    sub: `Intervallo ${rec.label}`,
  }));
  return {
    title: `Sorveglianze • ${dayCap}`,
    badge: `INTERVALLO ${rec.orario} (${rec.durata} MIN)`,
    lines,
    note: noteStd,
    speech: `${dayCap}, durante l'intervallo delle ${rec.orario} di ${rec.durata} minuti, i turni di sorveglianza coprono ${lines.length} zone dell'istituto.`,
    rooms: [],
  };
}

function answerRecupero(p, idx, ctx = {}) {
  const refDate = p.targetDateStr
    ? new Date(`${p.targetDateStr}T10:00:00`)
    : p.now || new Date();
  const parity = getWeekParity(refDate);
  const noteStd =
    "Comunicato n. 167 (in vigore dal 19/11/2026): recuperi Q1 nelle settimane dispari e Q2 nelle settimane pari del calendario.";

  // 1) Verifica docente (esplicito o self)
  let docObj = p.docente || null;
  let isSelf = false;
  if (!docObj && p.wantsSelf && ctx.me) {
    const meHits = scoreDocenti(normalize(ctx.me), idx);
    if (meHits.length === 1) {
      docObj = meHits[0];
      isSelf = true;
    }
  } else if (docObj && ctx.me) {
    const meHits = scoreDocenti(normalize(ctx.me), idx);
    isSelf = meHits.length === 1 && meHits[0].id === docObj.id;
  }

  if (docObj) {
    const d = idx.db.docenti[docObj.id];
    const displayDoc = isSelf ? `Prof. ${titleCase(d.nome)} (Tu)` : `Prof. ${titleCase(d.nome)}`;
    const giorniOrd = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"];
    const found = [];
    for (const g of giorniOrd) {
      const daySched = d.orario[g] || {};
      for (let h = 1; h <= 6; h++) {
        const s = daySched[String(h)];
        if (s && s.tipo === "recupero") {
          found.push({ day: g, hour: h, settimana: s.settimana || "tutte" });
        }
      }
    }

    if (!found.length) {
      return {
        title: `Ore di Recupero • ${displayDoc}`,
        badge: `SETTIMANA CORRENTE: ${parity.code} (${parity.parityLabel.toUpperCase()})`,
        lines: [],
        note: `Nessuna ora di recupero registrata nell'orario mod1a. ${noteStd}`,
        speech: isSelf
          ? "Non hai ore di recupero in orario."
          : `${cap(spokenDocenteName(d.nome))} non ha ore di recupero in orario.`,
        rooms: [],
      };
    }

    const lines = found.map((f) => {
      const activeNow = f.settimana === "tutte" || f.settimana === parity.code;
      const settDesc =
        f.settimana === "Q1"
          ? "Settimane dispari (Q1)"
          : f.settimana === "Q2"
          ? "Settimane pari (Q2)"
          : "Ogni settimana";
      const st = startOf(idx, f.hour, f.day);
      return {
        when: `${cap(dl(f.day))} • ${f.hour}ª ora`,
        main: `Recupero ${f.settimana === "tutte" ? "Settimanale" : f.settimana}${activeNow ? " • Attivo questa settimana" : " • Non attivo questa settimana"}`,
        sub: `${settDesc}${st ? " (" + st + ")" : ""}`,
      };
    });

    const spokenParts = found.map((f) => {
      const settSay =
        f.settimana === "Q1"
          ? "nelle settimane dispari Q1"
          : f.settimana === "Q2"
          ? "nelle settimane pari Q2"
          : "ogni settimana";
      return `${dl(f.day)} alla ${ORD_WORDS[f.hour]} ora ${settSay}`;
    });
    return {
      title: `Ore di Recupero • ${displayDoc}`,
      badge: `QUESTA SETTIMANA: ${parity.code} (N° ${parity.weekNum})`,
      lines,
      note: noteStd,
      speech: isSelf
        ? `Hai recupero ${joinSpeech(spokenParts)}. Questa settimana è ${parity.code}, settimana numero ${parity.weekNum} (${parity.parityLabel}).`
        : `${cap(spokenDocenteName(d.nome))} ha recupero ${joinSpeech(spokenParts)}. Questa settimana è ${parity.code}, numero ${parity.weekNum}.`,
      rooms: [],
    };
  }

  // 2) Richiesta stato settimana Q1/Q2
  if (p.asksWeekParity || !p.explicitDay) {
    return {
      title: `Settimana di Recupero: ${parity.code}`,
      badge: `SETTIMANA N° ${parity.weekNum} • ${parity.parityLabel.toUpperCase()}`,
      lines: [
        {
          when: "Settimana attuale",
          main: `${parity.code} — Settimana n° ${parity.weekNum} (${parity.parityLabel})`,
          sub: parity.code === "Q1" ? "Attivi i recuperi Q1 e i recuperi settimanali" : "Attivi i recuperi Q2 e i recuperi settimanali",
        },
        {
          when: "Regola Q1",
          main: "Settimane dispari del calendario",
          sub: "Es. settimana 47 (16–21 nov), settimana 49 (30 nov–5 dic)",
        },
        {
          when: "Regola Q2",
          main: "Settimane pari del calendario",
          sub: "Es. settimana 48 (23–28 nov), settimana 50 (7–12 dic)",
        },
      ],
      note: noteStd,
      speech: `La settimana numero ${parity.weekNum} è una settimana ${parity.parityLabel}, quindi è in vigore la settimana ${parity.code}. I recuperi Q1 sono attivi nelle settimane dispari e i recuperi Q2 nelle settimane pari.`,
      rooms: [],
    };
  }

  // 3) Tutti i docenti con recupero in un giorno specifico (es. "chi ha recupero lunedì")
  if (p.day === "domenica") return closedDay(p, "Ore di Recupero");
  const dayMatches = [];
  for (const d of Object.values(idx.db.docenti)) {
    const daySched = d.orario[p.day] || {};
    for (let h = 1; h <= 6; h++) {
      const s = daySched[String(h)];
      if (s && s.tipo === "recupero") {
        dayMatches.push({ nome: d.nome, hour: h, settimana: s.settimana || "tutte" });
      }
    }
  }
  dayMatches.sort((a, b) => a.hour - b.hour || a.nome.localeCompare(b.nome));
  const dayCap = cap(dl(p.day));
  const lines = dayMatches.map((m) => ({
    when: `${m.hour}ª ora`,
    main: `Prof. ${titleCase(m.nome)}`,
    sub: m.settimana === "tutte" ? "Recupero settimanale" : `Recupero ${m.settimana} (${m.settimana === "Q1" ? "settimane dispari" : "settimane pari"})`,
  }));
  return {
    title: `Recuperi • ${dayCap}`,
    badge: `SETTIMANA ${parity.code} • ${dayMatches.length} DOCENTI`,
    lines,
    note: noteStd,
    speech: `${dayCap} sono previste ${dayMatches.length} ore di recupero in orario. La settimana corrente è ${parity.code}.`,
    rooms: [],
  };
}

function answerAiuto(p) {
  return {
    title: "Guida alle Domande Possibili",
    badge: "GUIDA • COMANDI DISPONIBILI",
    lines: [
      {
        when: "Sorveglianze",
        main: "Chi fa sorveglianza oggi?",
        sub: "Anche: «Quando ho sorveglianza?», «Sorveglianza Cassarino», «Quanto dura l'intervallo?»",
        query: "chi fa sorveglianza oggi",
      },
      {
        when: "Recuperi Q1/Q2",
        main: "Questa settimana è Q1 o Q2?",
        sub: "Anche: «Quando ho recupero?», «Ore di recupero Cassarino», «Chi ha recupero lunedì?»",
        query: "questa settimana è Q1 o Q2",
      },
      {
        when: "Consigli CdC",
        main: "Quando è il consiglio di classe della 4ITA?",
        sub: "Anche: «Consigli di classe a novembre», «ODG consigli di classe», «Consiglio 1A»",
        query: "quando è il consiglio di classe della 4ITA",
      },
      {
        when: "Docenti",
        main: "Cosa fa Malè domani alla terza ora?",
        sub: "Anche: «Cosa ho oggi?» (salva il tuo cognome con 👤), «Cassarino lunedì ha disposizione?»",
        query: "cosa fa Malè domani alla terza ora",
      },
      {
        when: "Classi",
        main: "Dove si trova la 4ITA alla terza ora?",
        sub: "Anche: «Orario 3MM mercoledì», «Chi ha la 4EE adesso?»",
        query: "dove si trova la 4ITA alla terza ora",
      },
      {
        when: "Aule Libere",
        main: "Quali laboratori sono liberi mercoledì alla 2ª ora?",
        sub: "Anche: «Chi c'è in palestra martedì?», «Quali aule sono libere lunedì?»",
        query: "quali laboratori sono liberi mercoledì alla 2ª ora",
      },
      {
        when: "Mappa Piani",
        main: "Dov'è il laboratorio di chimica?",
        sub: "Anche: «Dov'è l'ufficio vicepresidenza?», «Dov'è la biblioteca?», «Dov'è l'ascensore?»",
        query: "dov'è il laboratorio di chimica",
      },
      {
        when: "Calendario",
        main: "Quando iniziano le vacanze di Natale?",
        sub: "Anche: «Qual è il prossimo ponte?», «Quando finisce la scuola?», «Carnevale»",
        query: "quando iniziano le vacanze di Natale",
      },
      {
        when: "Collegiali",
        main: "Quando è il prossimo collegio docenti?",
        sub: "Anche: «Quando ci sono i colloqui generali?», «Quando era il GLO della 4ITA?»",
        query: "quando è il prossimo collegio docenti",
      },
    ],
    note: "Tocca o clicca direttamente su una delle domande sopra per visualizzare subito la risposta.",
    speech: "Ecco le principali domande che puoi pormi: puoi chiedermi i turni di sorveglianza, le settimane Q1 e Q2 dei recuperi, l'orario di lezioni e docenti, le aule libere, la mappa dei piani, il calendario scolastico o i consigli di classe.",
    rooms: [],
  };
}

const MONTH_INDEX = {
  settembre: 8, ottobre: 9, novembre: 10, dicembre: 11,
  gennaio: 0, febbraio: 1, marzo: 2, aprile: 3, maggio: 4, giugno: 5, luglio: 6, agosto: 7
};

export function parseActivityDate(item) {
  if (!item) return null;
  if (item.data_iso) {
    const [y, m, d] = item.data_iso.split("-").map(Number);
    const [h, min] = (item.ora || "00:00").split(":").map(Number);
    return new Date(y, m - 1, d, h, min);
  }
  let year = null, month = null, day = null, hour = 0, minute = 0;
  const str = `${item.giorno || ""} ${item.periodo || ""} ${item.data || ""} ${item.mese || ""}`.toLowerCase();

  const numDate = str.match(/\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b/);
  if (numDate) {
    day = parseInt(numDate[1], 10);
    month = parseInt(numDate[2], 10) - 1;
    let y = parseInt(numDate[3], 10);
    year = y < 100 ? 2000 + y : y;
  } else {
    const mMatch = str.match(/\b(settembre|ottobre|novembre|dicembre|gennaio|febbraio|marzo|aprile|maggio|giugno)\b/);
    if (mMatch) {
      month = MONTH_INDEX[mMatch[1]];
      year = month >= 8 ? 2026 : 2027;
      const dMatch = str.match(/\b(\d{1,2})\b/);
      day = dMatch ? parseInt(dMatch[1], 10) : 1;
      const yMatch = str.match(/\b(202[6-7])\b/);
      if (yMatch) year = parseInt(yMatch[1], 10);
    }
  }

  const timeStr = `${item.ora || ""} ${item.orario || ""}`;
  const tMatch = timeStr.match(/\b(\d{1,2})[:.](\d{2})\b/);
  if (tMatch) {
    hour = parseInt(tMatch[1], 10);
    minute = parseInt(tMatch[2], 10);
  }

  if (year !== null && month !== null && day !== null) {
    return new Date(year, month, day, hour, minute);
  }
  return null;
}

function sortActivities(items) {
  return [...items].sort((a, b) => {
    const da = parseActivityDate(a);
    const db = parseActivityDate(b);
    if (da && db) return da.getTime() - db.getTime();
    if (da) return -1;
    if (db) return 1;
    return 0;
  });
}

function answerAttivita(p, idx, ctx = {}) {
  const att = idx.attivita || {};
  const istituto = att.attivita_istituto || [];
  const sintesi = att.attivita_classe_sintesi || [];
  const consigli = att.consigli_classe_dettaglio || [];
  const colloqui = att.colloqui_generali || [];
  const now = ctx?.now || p.now || new Date();

  // 1. Consigli di classe o Scrutini per una classe specifica
  if (p.classi?.length && (p.subType === "consigli_classe" || p.subType === "scrutini" || p.subType === "generale")) {
    const clsId = p.classi[0].toUpperCase();
    let matches = consigli.filter((item) =>
      (item.classi && item.classi.includes(clsId)) ||
      (item.classe_raw && item.classe_raw.toUpperCase() === clsId)
    );
    if (p.subType === "scrutini") {
      matches = matches.filter((item) => /scrutini/i.test(item.periodo) || /scrutini/i.test(item.giorno));
    }

    if (matches.length > 0) {
      matches = sortActivities(matches);
      const isScrutiniOnly = p.subType === "scrutini";

      if (p.isProssimo) {
        const upcoming = matches.filter((m) => {
          const d = parseActivityDate(m);
          return d && d >= now;
        });
        const target = upcoming.length > 0 ? upcoming[0] : matches[matches.length - 1];
        const nextList = upcoming.length > 0 ? upcoming : matches;
        const lines = nextList.map((m) => ({
          when: m.giorno || m.periodo,
          main: `Ore ${m.ora} • ${m.aula || "Lab. Multimediale"}`,
          sub: `${m.sezione ? "Sez. " + m.sezione + " • " : ""}${m.periodo ? m.periodo : ""}${m.comunicato ? " (" + m.comunicato.split(" del")[0] + ")" : ""}`,
        }));
        const targetWhere = target.aula ? ` in ${target.aula}` : "";
        const title = isScrutiniOnly ? `Prossimo Scrutinio ${clsId}` : `Prossimo Consiglio di Classe ${clsId}`;
        const isNov = /novembre/i.test(target.periodo || "") || /novembre/i.test(target.giorno || "");
        const extraNote = isNov ? " Negli ultimi 15' il consiglio è aperto alla rappresentanza di genitori e studenti." : "";
        const extraSpeech = isNov ? " Gli ultimi 15 minuti sono aperti ai rappresentanti di genitori e studenti." : "";
        const speech = isScrutiniOnly
          ? `Il prossimo scrutinio per la ${clsId} è in programma ${target.giorno || target.periodo} alle ore ${target.ora}${targetWhere}.`
          : `Il prossimo consiglio di classe per la ${clsId} si terrà ${target.giorno || target.periodo} alle ${target.ora}${targetWhere}.${extraSpeech}`;
        return {
          title,
          badge: "PROSSIMA ATTIVITÀ",
          lines,
          note: target.comunicato
            ? `${target.comunicato} per la classe ${clsId}.${extraNote}`
            : `Calendario dal Piano Annuale delle Attività 2026/27 per la classe ${clsId}.${extraNote}`,
          speech,
          rooms: nextList.map((m) => m.aula).filter(Boolean),
        };
      }

      const title = isScrutiniOnly ? `Scrutini Classe ${clsId}` : `Consigli di Classe ${clsId}`;
      const lines = matches.map((m) => ({
        when: m.giorno || m.periodo,
        main: `Ore ${m.ora} • ${m.aula || "Lab. Multimediale"}`,
        sub: `${m.sezione ? "Sez. " + m.sezione + " • " : ""}${m.periodo ? m.periodo : ""}${m.comunicato ? " (" + m.comunicato.split(" del")[0] + ")" : ""}`,
      }));

      const spokenDates = matches.slice(0, 4).map((m) => `${m.giorno || m.periodo} alle ${m.ora}`).join(", ");
      const hasNov = matches.some((m) => /novembre/i.test(m.periodo || "") || /novembre/i.test(m.giorno || ""));
      return {
        title,
        badge: "CALENDARIO ATTIVITÀ",
        lines,
        note: hasNov
          ? `Calendario ufficiale (incluso Comunicato n. 124 del 04/11/2026 per novembre). Negli ultimi 15' aperto a genitori e studenti.`
          : `Calendario dal Piano Annuale delle Attività 2026/27 per la classe ${clsId}.`,
        speech: `I consigli di classe in programma per la ${clsId} sono: ${spokenDates}${matches.length > 4 ? " e altri successivi." : "."}`,
        rooms: matches.map((m) => m.aula).filter(Boolean),
      };
    }
  }

  // 1b. Consigli di classe generali (senza classe: per ordine del giorno, sede o mese)
  if (p.subType === "consigli_classe" && (!p.classi || p.classi.length === 0)) {
    const isOdg = /\b(odg|ordine del giorno)\b/i.test(p.queryText || "");
    if (isOdg) {
      return {
        title: "Ordine del Giorno Consigli di Classe",
        badge: "COMUNICATO N. 124 • NOVEMBRE 2026",
        lines: [
          { when: "Punti 1-4", main: "Andamento didattico-disciplinare & Percorsi orientamento (≥30h)", sub: "Approvazione verbale precedente e attività integrative" },
          { when: "Punti 5-8", main: "Delibera PDP (DSA) & Delibera PEI (L. 104/92)", sub: "Designazione Tutor e prima condivisione P.F.I. (solo sez. Rizzarda)" },
          { when: "Punti 9-12", main: "PFP Studente-Atleta, provvedimenti disciplinari, FSL (triennio)", sub: "Varie ed eventuali" },
          { when: "Ultimi 15'", main: "Apertura a Rappresentanti Genitori e Studenti", sub: "Andamento generale didattico-disciplinare e offerte formative" },
        ],
        note: "Comunicato n. 124 del 04/11/2026 - Dirigente scolastica Manuela Muliner Biga.",
        speech: "L'ordine del giorno dei consigli di classe di novembre prevede l'andamento didattico-disciplinare, l'orientamento, la delibera di PDP e PEI, e negli ultimi 15 minuti l'apertura ai rappresentanti di genitori e studenti.",
        rooms: ["Lab. Multimediale", "Lim"],
      };
    }

    let novConsigli = consigli.filter((c) => c.periodo === "Novembre 2026" || /novembre/i.test(c.giorno || ""));

    if (/\b(colotti)\b/i.test(p.queryText || "")) {
      novConsigli = novConsigli.filter((c) => /colotti/i.test(c.sezione || ""));
    } else if (/\b(rizzarda)\b/i.test(p.queryText || "")) {
      novConsigli = novConsigli.filter((c) => /rizzarda/i.test(c.sezione || ""));
    } else if (/\b(negrelli|forcellini)\b/i.test(p.queryText || "")) {
      novConsigli = novConsigli.filter((c) => /negrelli/i.test(c.sezione || ""));
    }

    if (novConsigli.length > 0) {
      novConsigli = sortActivities(novConsigli);
      const grouped = {};
      novConsigli.forEach((c) => {
        const k = c.giorno || c.data_iso;
        if (!grouped[k]) grouped[k] = { giorno: c.giorno, sezione: c.sezione, aula: c.aula, items: [] };
        grouped[k].items.push(c);
      });

      const lines = Object.values(grouped).map((g) => ({
        when: g.giorno,
        main: `Sezione ${g.sezione} • ${g.items.map((it) => it.classe_raw).join(", ")}`,
        sub: `Dalle ${g.items[0].ora} alle ${g.items[g.items.length - 1].ora} • ${g.aula || "Lab. Multimediale"}`,
      }));

      return {
        title: "Consigli di Classe Novembre 2026",
        badge: "COMUNICATO N. 124",
        lines,
        note: "Comunicato n. 124 del 04/11/2026. Gli ultimi 15 minuti di ciascun consiglio sono aperti ai rappresentanti di genitori e studenti.",
        speech: "I consigli di classe di novembre si terranno dal 9 al 24 novembre: il 9 e 10 per la sede Colotti, l'11 e 12 per la sede Rizzarda, e dal 13 al 24 per la sede Negrelli. Gli ultimi 15 minuti sono aperti ai rappresentanti di genitori e studenti.",
        rooms: ["Lab. Multimediale", "Lim"],
      };
    }
  }

  // 2. Scrutini Generali (senza classe o sintesi)
  if (p.subType === "scrutini") {
    const scrutiniSintesi = sintesi.filter((s) => /scrutini/i.test(s.attivita));
    const lines = scrutiniSintesi.map((s) => ({
      when: `${cap(s.mese)} (${s.data})`,
      main: s.attivita,
      sub: "",
    }));
    return {
      title: p.isProssimo ? "Prossimi Scrutini" : "Calendario Scrutini",
      badge: p.isProssimo ? "PROSSIMA ATTIVITÀ" : "PIANO ATTIVITÀ",
      lines: lines.length ? lines : [{ when: "Gennaio / Giugno", main: "Scrutini I e II periodo", sub: "" }],
      note: "Sintesi sessioni di scrutinio dal Piano Annuale delle Attività.",
      speech: "Le sessioni di scrutinio sono previste a gennaio per il primo periodo e a giugno per il secondo periodo.",
      rooms: [],
    };
  }

  // 3. Collegio Docenti
  if (p.subType === "collegio" || /\bcollegio\b/i.test(p.queryText || "")) {
    let collegi = istituto.filter((i) => /collegio docenti/i.test(i.attivita));
    collegi = sortActivities(collegi);

    if (p.isProssimo) {
      const upcoming = collegi.filter((c) => {
        const d = parseActivityDate(c);
        return d && d >= now;
      });
      const target = upcoming.length > 0 ? upcoming[0] : collegi[collegi.length - 1];
      const nextList = upcoming.length > 0 ? upcoming : collegi;
      const lines = nextList.map((c) => ({
        when: `${cap(c.mese)} ${c.data}`,
        main: c.attivita,
        sub: c.orario ? `Orario: ${c.orario}${c.durata ? " (" + c.durata + ")" : ""}` : "",
      }));
      const orarioStr = target.orario ? ` dalle ore ${target.orario}` : "";
      return {
        title: "Prossimo Collegio Docenti",
        badge: "PROSSIMA ATTIVITÀ",
        lines,
        note: "Date e orari delle sedute del Collegio Docenti a.s. 2026/27.",
        speech: `Il prossimo Collegio Docenti si terrà in data ${cap(target.mese)} ${target.data}${orarioStr}. Oggetto: ${target.attivita.replace(/\n/g, ' ')}.`,
        rooms: [],
      };
    }

    const lines = collegi.map((c) => ({
      when: `${cap(c.mese)} ${c.data}`,
      main: c.attivita,
      sub: c.orario ? `Orario: ${c.orario}${c.durata ? " (" + c.durata + ")" : ""}` : "",
    }));
    return {
      title: "Collegio Docenti",
      badge: "ATTIVITÀ COLLEGIALI",
      lines,
      note: "Date e orari delle sedute del Collegio Docenti a.s. 2026/27.",
      speech: `Sono previste ${collegi.length} sedute del Collegio Docenti durante l'anno scolastico, tra cui il primo il 1° settembre e le delibere nei mesi di settembre, ottobre, dicembre, maggio e giugno.`,
      rooms: [],
    };
  }

  // 4. Colloqui Generali
  if (p.subType === "colloqui" || /\bcolloqui\b/i.test(p.queryText || "")) {
    let filtered = colloqui;

    // Filtro per Docente (esplicito o self "quando ho i colloqui?")
    let docObj = p.docente || null;
    if (!docObj && (p.wantsSelf || (!p.classi?.length && !p.targetDateStr)) && ctx.me) {
      const meHits = scoreDocenti(normalize(ctx.me), idx);
      if (meHits.length === 1) docObj = meHits[0];
    }

    let docFasciaDesc = "";
    if (docObj) {
      const d = idx.db.docenti[docObj.id];
      if (d) {
        const teacherClasses = getTeacherClasses(d);
        const hasBiennio = [...teacherClasses].some((c) => /^[12]/.test(c));
        const hasTriennio = [...teacherClasses].some((c) => /^[345]/.test(c));
        const hasColotti = [...teacherClasses].some((c) => /AFM|RIM|BRIM/i.test(c));
        const hasRizzarda = [...teacherClasses].some((c) => /ASS|SSAS|IAMI/i.test(c));
        const hasNegrelli = [...teacherClasses].some((c) => !/AFM|RIM|BRIM|ASS|SSAS|IAMI/i.test(c));

        if (hasBiennio && hasTriennio) docFasciaDesc = "biennio e triennio";
        else if (hasBiennio) docFasciaDesc = "biennio";
        else if (hasTriennio) docFasciaDesc = "triennio";

        filtered = filtered.filter((c) => {
          const sede = (c.sede || "").toLowerCase();
          const fascia = (c.classi || "").toLowerCase();
          if (sede === "negrelli") {
            if (!hasNegrelli) return false;
            if (fascia === "biennio") return hasBiennio;
            if (fascia === "triennio") return hasTriennio;
            return true;
          }
          if (sede === "colotti") return hasColotti;
          if (sede === "rizzarda") return hasRizzarda;
          return true;
        });
      }
    }

    // A) Orario individualizzato per Classe (es. "colloqui 4ITA")
    if (p.classi?.length && !docObj) {
      const clsId = p.classi[0].toUpperCase();
      const docList = idx.colloqui_docenti?.per_classe?.[clsId];
      if (docList && docList.length > 0) {
        const sample = docList[0];
        const lines = docList.map((d) => {
          const whenStr = d.assente ? "ASSENTE" : `Ore ${d.orario}`;
          const defStr = d.orario_default ? " (orario d'istituto)" : "";
          const extraStr = d.note ? ` • ${d.note}` : "";
          return {
            when: whenStr,
            main: `Prof. ${d.docente_nome}`,
            sub: `${d.giorno} ${d.data} • Negrelli (${d.ciclo})${defStr}${extraStr}`,
          };
        });
        return {
          title: `Colloqui Generali • Docenti ${clsId}`,
          badge: `${sample.giorno.toUpperCase()} ${sample.data} • ${sample.ciclo.toUpperCase()}`,
          lines,
          note: `Orari individuali di ricevimento docenti della classe ${clsId} (Comunicato n. 185). Chi non ha indicato orario specifico riceve dalle 14:30 alle 17:30.`,
          speech: `I colloqui generali per la ${clsId} si terranno ${sample.giorno} ${sample.data} in presenza al Negrelli. Sono indicati gli orari di ricevimento individuali per i ${docList.length} docenti della classe.`,
          rooms: [],
        };
      }
    }

    // B) Orario individualizzato per Docente (es. "a che ora riceve Basso?" o self)
    if (docObj && idx.colloqui_docenti?.per_docente?.[docObj.id]) {
      const docData = idx.colloqui_docenti.per_docente[docObj.id];
      const isMe = p.isSelf || (ctx.me && normalize(ctx.me) === normalize(docObj.nome));
      const subj = isMe ? "hai i colloqui generali" : `il professor ${docObj.nome} riceve ai colloqui generali`;
      const lines = [];
      const speechParts = [];

      if (docData.biennio?.attivo) {
        const b = docData.biennio;
        const whenStr = b.assente ? "ASSENTE" : `Ore ${b.orario}`;
        const noteStr = b.assente ? "Docente assente giustificato" : `Classi: ${b.classi.join(", ")}`;
        const defStr = b.orario_default ? " (orario d'istituto)" : "";
        lines.push({
          when: `I periodo • Giovedì 03.12.26 • ${whenStr}`,
          main: `Sede: Negrelli (biennio)`,
          sub: `${noteStr}${defStr}`,
        });
        if (b.assente) speechParts.push("giovedì 3 dicembre per il biennio risulta assente giustificato");
        else speechParts.push(`giovedì 3 dicembre dalle ${b.orario.replace("-", " alle ")} per il biennio (${b.classi.join(", ")})`);
      }

      if (docData.triennio?.attivo) {
        const t = docData.triennio;
        const whenStr = t.assente ? "ASSENTE" : `Ore ${t.orario}`;
        const noteStr = t.assente ? "Docente assente giustificato" : `Classi: ${t.classi.join(", ")}`;
        const defStr = t.orario_default ? " (orario d'istituto)" : "";
        const extraNote = docData.note ? ` • ${docData.note}` : "";
        lines.push({
          when: `I periodo • Venerdì 04.12.26 • ${whenStr}`,
          main: `Sede: Negrelli (triennio)`,
          sub: `${noteStr}${defStr}${extraNote}`,
        });
        if (t.assente) speechParts.push("venerdì 4 dicembre per il triennio risulta assente giustificato");
        else speechParts.push(`venerdì 4 dicembre dalle ${t.orario.replace("-", " alle ")} per il triennio (${t.classi.join(", ")})`);
      }

      if (!/dicembre/i.test(p.queryText || "") && !/dicembre/i.test(p.mese || "")) {
        const iiPeriodo = filtered.filter((c) => c.periodo === "II periodo");
        for (const c of iiPeriodo) {
          lines.push({
            when: `${c.periodo} • ${c.giorno} ${c.data}${c.orario ? " • Ore " + c.orario : ""}`,
            main: `Sede: ${c.sede} (${c.classi})`,
            sub: c.comunicato || "Piano Annuale Attività",
          });
        }
      }

      let speech = "";
      const anyAttivo = (docData.biennio?.attivo && !docData.biennio?.assente) || (docData.triennio?.attivo && !docData.triennio?.assente);
      if (!anyAttivo) {
        speech = `${isMe ? "Risulti" : `Il professor ${docObj.nome} risulta`} assente giustificato ai colloqui generali del I periodo (Comunicato n. 185).`;
      } else {
        speech = `${isMe ? "In base al tuo orario" : "In base all'orario di ricevimento"}, ${subj} ${speechParts.join(", e ")} in presenza nei rispettivi plessi (Comunicato n. 185).`;
      }
      return {
        title: `Colloqui Generali • ${docObj.nome}`,
        badge: "COLLOQUI INDIVIDUALI",
        lines,
        note: "Orario individuale di ricevimento per i colloqui generali del I periodo (Comunicato n. 185). Chi non ha indicato orario specifico riceve dalle 14:30 alle 17:30.",
        speech,
        rooms: [],
      };
    }

    if (p.classi?.length) {
      const clsId = p.classi[0].toUpperCase();
      const isBiennio = /^[12]/.test(clsId);
      if (/AFM|RIM|BRIM/i.test(clsId)) {
        filtered = filtered.filter((c) => c.sede.toLowerCase() === "colotti");
      } else if (/ASS|SSAS|IAMI/i.test(clsId)) {
        filtered = filtered.filter((c) => c.sede.toLowerCase() === "rizzarda");
      } else {
        filtered = filtered.filter((c) => {
          if (c.sede.toLowerCase() !== "negrelli") return false;
          const fascia = (c.classi || "").toLowerCase();
          return fascia === "tutte" || (isBiennio ? fascia === "biennio" : fascia === "triennio");
        });
      }
    }
    if (p.targetDateStr) {
      filtered = filtered.filter((c) => getExactActivityYMD(c) === p.targetDateStr);
    } else if (p.mese || /\bdicembre|aprile\b/i.test(p.queryText || "")) {
      const wantsDicembre = /dicembre/i.test(p.mese || "") || /dicembre/i.test(p.queryText || "");
      const wantsAprile = /aprile/i.test(p.mese || "") || /aprile/i.test(p.queryText || "");
      if (wantsDicembre && !wantsAprile) {
        filtered = filtered.filter((c) => c.periodo === "I periodo" || (c.data_iso && c.data_iso.includes("-12-")));
      } else if (wantsAprile && !wantsDicembre) {
        filtered = filtered.filter((c) => c.periodo === "II periodo" || (c.data_iso && c.data_iso.includes("-04-")));
      }
    }
    filtered = sortActivities(filtered);

    const makeLines = (list) =>
      list.map((c) => {
        const orarioText = c.orario ? ` • Ore ${c.orario}` : "";
        const subParts = [];
        if (c.modalita) subParts.push(c.modalita);
        if (c.comunicato) subParts.push(c.comunicato);
        else if (c.periodo) subParts.push(c.periodo);
        return {
          when: `${c.periodo} • ${c.giorno} ${c.data}${orarioText}`,
          main: `Sede: ${c.sede} (${c.classi})`,
          sub: subParts.join(" • "),
        };
      });

    if (p.isProssimo) {
      const upcoming = filtered.filter((c) => {
        const d = parseActivityDate(c);
        return d && d >= now;
      });
      const target = upcoming.length > 0 ? upcoming[0] : filtered[filtered.length - 1];
      const nextList = upcoming.length > 0 ? upcoming : filtered;
      const orarioSpeech = target.orario ? ` dalle ${target.orario.replace("-", " alle ")}` : "";
      return {
        title: "Prossimi Colloqui Generali",
        badge: "PROSSIMA ATTIVITÀ",
        lines: makeLines(nextList),
        note: "Colloqui in presenza nei rispettivi plessi (Comunicato n. 185 del 24/11/2026).",
        speech: `I prossimi colloqui generali per ${target.sede} si terranno ${target.giorno} ${target.data}${orarioSpeech} (${target.classi}).`,
        rooms: [],
      };
    }

    const isSingleClass = p.classi?.length && filtered.length > 0;
    const targetSingle = isSingleClass ? filtered[0] : null;
    let speech = "I colloqui generali del primo periodo si terranno dall'1 al 4 dicembre 2026 dalle 14:30 alle 17:30 in presenza nei rispettivi plessi.";

    if (docObj && filtered.length > 0) {
      const isMe = p.isSelf || (ctx.me && normalize(ctx.me) === normalize(docObj.nome));
      const subj = isMe ? "hai i colloqui generali" : `il professor ${docObj.nome} ha i colloqui generali`;
      const datesText = filtered.map((c) => `${c.giorno} ${c.data}${c.orario ? " dalle " + c.orario.replace("-", " alle ") : ""} (${c.sede} ${c.classi})`).join(", e ");
      speech = `In base alle tue classi (${docFasciaDesc || "competenza"}), ${subj} ${datesText} in presenza nei rispettivi plessi (Comunicato n. 185).`;
    } else if (targetSingle) {
      const orarioSpeech = targetSingle.orario ? ` dalle ${targetSingle.orario.replace("-", " alle ")}` : "";
      speech = `I colloqui generali per la ${p.classi[0].toUpperCase()} (${targetSingle.sede}) si terranno ${targetSingle.giorno} ${targetSingle.data}${orarioSpeech} in presenza nei rispettivi plessi (${targetSingle.comunicato || targetSingle.periodo}).`;
    }

    return {
      title: docObj ? `Colloqui Generali • ${docObj.nome}` : "Colloqui Generali con i Genitori",
      badge: "COLLOQUI",
      lines: makeLines(filtered),
      note: "Colloqui I periodo: 1–4 dicembre 2026 ore 14:30–17:30 in presenza nei rispettivi plessi (Comunicato n. 185 del 24/11/2026). II periodo: 5–8 aprile 2027.",
      speech,
      rooms: [],
    };
  }

  // 4b. GLO - Gruppo di Lavoro Operativo per l'inclusione (condivisione PEI)
  const gloList = idx.glo || att.glo || idx.db?.glo?.incontri || [];
  if (p.subType === "glo" || /\b(glo|pei)\b/i.test(p.queryText || "")) {
    if (p.classi?.length) {
      const clsId = p.classi[0].toUpperCase();
      const match = gloList.find((g) => g.classe === clsId || g.classe_raw?.toUpperCase() === clsId);
      if (match) {
        return {
          title: `GLO Classe ${clsId}`,
          badge: "GLO • CONDIVISIONE PEI",
          lines: [
            {
              when: `${match.giorno}`,
              main: `Ore ${match.ora} • ${match.luogo}`,
              sub: "Condivisione del Piano Educativo Individualizzato (PEI)",
            },
          ],
          note: `${match.comunicato || "Comunicato n. 83 del 14/10/2026"} - Dirigente scolastica Manuela Muliner Biga.`,
          speech: `Il GLO per la condivisione del PEI della ${clsId} si terrà ${match.giorno} alle ore ${match.ora} in un'aula della sede del Negrelli.`,
          rooms: [],
        };
      }
      return {
        title: `Nessun GLO per la ${clsId}`,
        badge: "GLO NON PREVISTO",
        lines: [],
        note: "Calendario convocazioni GLO (Comunicato n. 83 del 14/10/2026).",
        speech: `Non risultano convocazioni GLO per la classe ${clsId} nel calendario del Comunicato 83.`,
        rooms: [],
      };
    }

    if (p.isProssimo) {
      const upcoming = gloList.filter((g) => {
        const d = parseActivityDate(g);
        return d && d >= now;
      });
      const target = upcoming.length > 0 ? upcoming[0] : gloList[0];
      const nextList = upcoming.length > 0 ? upcoming : gloList;
      const lines = nextList.slice(0, 8).map((g) => ({
        when: `${g.giorno.split(" ")[0]} ${g.data_iso ? g.data_iso.split("-")[2] : ""} ott`,
        main: `Ore ${g.ora} • Classe ${g.classe}`,
        sub: g.luogo,
      }));
      return {
        title: `Prossimo GLO: ${target.classe}`,
        badge: "PROSSIMO GLO",
        lines,
        note: "Convocazioni GLO per la condivisione dei PEI (Comunicato n. 83 del 14/10/2026).",
        speech: `Il prossimo incontro GLO è per la classe ${target.classe}, in programma ${target.giorno} alle ore ${target.ora} in sede Negrelli.`,
        rooms: [],
      };
    }

    const lines = gloList.map((g) => ({
      when: `${g.giorno.split(" ")[0]} ${g.data_iso ? g.data_iso.split("-")[2] : ""} ott ore ${g.ora}`,
      main: `Classe ${g.classe} (PEI)`,
      sub: `${g.luogo}`,
    }));

    return {
      title: "Calendario Convocazione GLO",
      badge: "GLO • CONDIVISIONE PEI",
      lines,
      note: "Calendario riassuntivo convocazione GLO per la condivisione dei PEI (Comunicato n. 83 del 14/10/2026).",
      speech: "I GLO per la condivisione dei PEI si terranno dal 26 al 30 ottobre 2026 in sede Negrelli per 22 classi complessive.",
      rooms: [],
    };
  }

  // 5. Mese specifico
  if (p.mese) {
    const meseNorm = p.mese.toLowerCase();
    const listIst = istituto.filter((i) => i.mese.toLowerCase() === meseNorm);
    const listSin = sintesi.filter((s) => s.mese.toLowerCase() === meseNorm);
    const rawLines = [
      ...listIst.map((i) => ({ ...i, when: i.data, main: i.attivita, sub: i.orario ? `Orario: ${i.orario}` : "" })),
      ...listSin.map((s) => ({ ...s, when: s.data, main: s.attivita, sub: "Sintesi collegiale" })),
    ];
    if (meseNorm === "ottobre" && gloList.length) {
      rawLines.push(
        ...gloList.map((g) => ({
          data_iso: g.data_iso,
          ora: g.ora,
          when: `${g.data_iso.split("-")[2]} ${g.giorno.split(" ")[0]}`,
          main: `GLO ${g.classe} (condivisione PEI)`,
          sub: `Ore ${g.ora} • ${g.luogo}`,
        }))
      );
    }
    if (meseNorm === "novembre") {
      const novConsigli = consigli.filter((c) => c.periodo === "Novembre 2026" || /novembre/i.test(c.giorno || ""));
      if (novConsigli.length) {
        const grouped = {};
        novConsigli.forEach((c) => {
          const k = c.giorno || c.data_iso;
          if (!grouped[k]) grouped[k] = { giorno: c.giorno, data_iso: c.data_iso, ora: c.ora, sezione: c.sezione, aula: c.aula, count: 0 };
          grouped[k].count++;
        });
        rawLines.push(
          ...Object.values(grouped).map((g) => ({
            data_iso: g.data_iso,
            ora: g.ora,
            when: g.giorno,
            main: `Consigli di Classe (Sez. ${g.sezione})`,
            sub: `${g.count} classi • ${g.aula || "Lab. Multimediale"} (Comunicato n. 124)`,
          }))
        );
      }
    }
    const lines = sortActivities(rawLines);
    return {
      title: `Attività di ${cap(p.mese)}`,
      badge: "PIANO ATTIVITÀ",
      lines: lines.length ? lines : [{ when: cap(p.mese), main: "Nessuna attività istituzionale registrata", sub: "" }],
      note: `Impegni collegiali previsti per il mese di ${cap(p.mese)}.`,
      speech: lines.length
        ? `Nel mese di ${p.mese} sono previste ${lines.length} attività collegiali.`
        : `Nel mese di ${p.mese} non ci sono attività istituzionali previste nel piano.`,
      rooms: [],
    };
  }

  // 6. Panoramica generale attività o Prossima attività generale
  const sortedIst = sortActivities(istituto);
  if (p.isProssimo) {
    const upcoming = sortedIst.filter((i) => {
      const d = parseActivityDate(i);
      return d && d >= now;
    });
    const target = upcoming.length > 0 ? upcoming[0] : sortedIst[0];
    const nextList = upcoming.length > 0 ? upcoming : sortedIst;
    const lines = nextList.slice(0, 8).map((i) => ({
      when: `${cap(i.mese)} ${i.data}`,
      main: i.attivita,
      sub: i.orario ? `Orario: ${i.orario}` : "",
    }));
    return {
      title: "Prossima Attività d'Istituto",
      badge: "PROSSIMA ATTIVITÀ",
      lines,
      note: "Principali appuntamenti e impegni collegiali del personale docente.",
      speech: `La prossima attività d'istituto in programma è: ${target.attivita.replace(/\n/g, ' ')}, prevista il ${cap(target.mese)} ${target.data}.`,
      rooms: [],
    };
  }

  const lines = sortedIst.slice(0, 8).map((i) => ({
    when: `${cap(i.mese)} ${i.data}`,
    main: i.attivita,
    sub: i.orario ? `Orario: ${i.orario}` : "",
  }));
  return {
    title: "Piano Annuale delle Attività 2026/27",
    badge: "PANORAMICA",
    lines,
    note: "Principali appuntamenti e impegni collegiali del personale docente.",
    speech: "Ecco i principali impegni del Piano Annuale delle Attività dell'istituto.",
    rooms: [],
  };
}

function answerSospensione(p, idx) {
  const susp = p.sospensione;
  const isDoc = p.docente ? titleCase(p.docente.nome) : null;
  const isCls = p.classi?.length ? p.classi[0].toUpperCase() : null;
  const isRoom = p.rooms?.length ? p.rooms[0].nome : null;

  let whoSubject = "non ci sono lezioni";
  if (p.isSelf) {
    whoSubject = "non hai lezioni";
  } else if (isDoc) {
    whoSubject = `il professor ${isDoc} non ha lezioni`;
  } else if (isCls) {
    whoSubject = `la classe ${isCls} non ha lezioni`;
  } else if (isRoom) {
    whoSubject = `${isRoom} non è utilizzata per lezioni`;
  }

  const badge = susp.tipo === "vacanza" ? "VACANZE SCOLASTICHE" : susp.tipo === "festivita" ? "FESTIVITÀ" : "ISTITUTO CHIUSO";

  let rientroText = "";
  if (susp.rientro) {
    const [ry, rm, rd] = susp.rientro.split("-").map(Number);
    const rDate = new Date(ry, rm - 1, rd);
    const rDayName = dl(JS_DAYS[rDate.getDay()]);
    const rMonthName = IT_MONTH_NAMES[rm] || "";
    rientroText = `Le lezioni riprendono ${rDayName} ${rd} ${rMonthName}.`;
  }

  const lines = [
    {
      when: susp.titolo,
      main: susp.descrizione || "Sospensione delle lezioni",
      sub: susp.rientro ? `Rientro a scuola: ${susp.rientro}` : (susp.chiuso_uffici ? "Chiusura totale istituto e uffici" : "Attività didattiche sospese"),
    },
  ];

  let art = "Il ";
  if (p.targetDateStr) {
    const dNum = parseInt(p.targetDateStr.split("-")[2], 10);
    if (dNum === 1 || dNum === 8 || dNum === 11) art = "L'";
  }

  const dateSpoken = p.targetDateStr ? formatDateSpoken(p.targetDateStr) : "in questa data";
  const speech = `${art}${dateSpoken} ${whoSubject}: la scuola è chiusa per ${susp.titolo}.${rientroText ? " " + rientroText : ""}`;

  return {
    title: `Lezioni Sospese • ${susp.titolo}`,
    badge,
    lines,
    note: "Calendario scolastico ufficiale 2026/27 (Comunicato n. 75).",
    speech,
    rooms: [],
  };
}

function answerCalendario(p, idx, ctx = {}) {
  const cal = idx.calendario || {};
  const meta = cal.meta || {};
  const vacanze = cal.vacanze || [];
  const festivita = cal.festivita || [];
  const now = ctx?.now || p.now || new Date();
  const nowYMD = formatDateYMD(now);

  if (p.subType === "fine_scuola") {
    const fine = meta.fine_lezioni_testo || "Martedì 8 giugno 2027";
    const inizio = meta.inizio_lezioni_testo || "Giovedì 10 settembre 2026";
    return {
      title: "Termine delle Lezioni a.s. 2026/27",
      badge: "CALENDARIO SCOLASTICO",
      lines: [
        { when: fine, main: "Ultimo giorno di scuola (termine delle lezioni)", sub: meta.delibera || "Delibera CdI del 31 agosto 2026" },
        { when: inizio, main: "Inizio dell'anno scolastico", sub: meta.comunicato || "Comunicato n. 75" },
      ],
      note: "Calendario scolastico ufficiale 2026/27 dell'ITIS Negrelli.",
      speech: `Le lezioni per l'anno scolastico 2026/2027 terminano ${fine.toLowerCase()}.`,
      rooms: [],
    };
  }

  if (p.subType === "inizio_scuola") {
    const fine = meta.fine_lezioni_testo || "Martedì 8 giugno 2027";
    const inizio = meta.inizio_lezioni_testo || "Giovedì 10 settembre 2026";
    return {
      title: "Inizio delle Lezioni a.s. 2026/27",
      badge: "CALENDARIO SCOLASTICO",
      lines: [
        { when: inizio, main: "Inizio attività didattiche", sub: "Primo giorno di scuola" },
        { when: fine, main: "Fine attività didattiche", sub: "Ultimo giorno di lezione" },
      ],
      note: "Calendario scolastico ufficiale 2026/27 dell'ITIS Negrelli.",
      speech: `L'anno scolastico 2026/2027 è iniziato ${inizio.toLowerCase()} e terminerà ${fine.toLowerCase()}.`,
      rooms: [],
    };
  }

  if (p.subType === "natale") {
    return {
      title: "Vacanze di Natale",
      badge: "VACANZE NATALIZIE",
      lines: [
        { when: "24 dicembre 2026 - 5 gennaio 2027", main: "Sospensione delle lezioni", sub: "Chiusura totale istituto e uffici: 24 e 31 dicembre, 2 gennaio" },
        { when: "Mercoledì 6 gennaio 2027", main: "Epifania (festività obbligatoria)", sub: "Istituto chiuso" },
        { when: "Giovedì 7 gennaio 2027", main: "Rientro a scuola", sub: "Ripresa regolare delle lezioni" },
      ],
      note: "Delibera del Consiglio di Istituto del 31 agosto 2026 (Comunicato n. 75).",
      speech: "Le vacanze di Natale vanno da giovedì 24 dicembre 2026 a martedì 5 gennaio 2027. Considerando l'Epifania il 6 gennaio, si rientra a scuola giovedì 7 gennaio 2027.",
      rooms: [],
    };
  }

  if (p.subType === "pasqua") {
    return {
      title: "Vacanze di Pasqua",
      badge: "VACANZE PASQUALI",
      lines: [
        { when: "25 marzo - 30 marzo 2027", main: "Sospensione delle lezioni per festività pasquali", sub: "Domenica 28 Pasqua, lunedì 29 Pasquetta; sabato 27 chiusura uffici" },
        { when: "Mercoledì 31 marzo 2027", main: "Rientro a scuola", sub: "Ripresa regolare delle lezioni" },
      ],
      note: "Calendario scolastico regionale 2026/2027 e delibera d'istituto.",
      speech: "Le vacanze di Pasqua vanno da giovedì 25 marzo a martedì 30 marzo 2027. Il rientro a scuola è mercoledì 31 marzo 2027.",
      rooms: [],
    };
  }

  if (p.subType === "carnevale") {
    return {
      title: "Carnevale e Mercoledì delle Ceneri",
      badge: "CARNEVALE",
      lines: [
        { when: "8 febbraio - 10 febbraio 2027", main: "Sospensione delle lezioni per Carnevale e Ceneri", sub: "Lunedì 8, martedì 9 grasso e mercoledì 10 delle Ceneri" },
        { when: "Giovedì 11 febbraio 2027", main: "Rientro a scuola", sub: "Ripresa regolare delle lezioni" },
      ],
      note: "Calendario scolastico regionale 2026/2027.",
      speech: "Le vacanze di Carnevale e del Mercoledì delle Ceneri vanno da lunedì 8 febbraio a mercoledì 10 febbraio 2027. Si rientra a scuola giovedì 11 febbraio 2027.",
      rooms: [],
    };
  }

  if (p.subType === "ponti") {
    const qText = p.queryText || "";
    const isImmacolata = /immacolata/i.test(qText);
    const isPrimoMaggio = /primo\s*maggio|1\s*maggio|lavoro/i.test(qText);
    const isPatrono = /patrono/i.test(qText);

    if (isImmacolata) {
      return {
        title: "Ponte dell'Immacolata",
        badge: "PONTE DELIBERATO",
        lines: [
          { when: "Lunedì 7 dicembre 2026", main: "Ponte dell'Immacolata (lezioni sospese e chiusura istituto)", sub: "Deliberato dal Consiglio di Istituto" },
          { when: "Martedì 8 dicembre 2026", main: "Immacolata Concezione (festività obbligatoria)", sub: "Istituto chiuso" },
          { when: "Mercoledì 9 dicembre 2026", main: "Rientro a scuola", sub: "Ripresa regolare delle lezioni" },
        ],
        note: "Delibera del Consiglio di Istituto del 31 agosto 2026 (Comunicato n. 75).",
        speech: "Per l'Immacolata le lezioni sono sospese lunedì 7 dicembre per ponte deliberato con chiusura dell'istituto, e martedì 8 dicembre per festività. Si rientra a scuola mercoledì 9 dicembre.",
        rooms: [],
      };
    }

    if (isPrimoMaggio) {
      return {
        title: "Ponte del 1° Maggio",
        badge: "PONTE DELIBERATO",
        lines: [
          { when: "29 - 30 aprile 2027", main: "Sospensione delle lezioni per la Festa del Lavoro", sub: "Venerdì 30 aprile chiusura uffici" },
          { when: "Sabato 1 maggio 2027", main: "Festa del Lavoro (festività obbligatoria)", sub: "Istituto chiuso" },
          { when: "Lunedì 3 maggio 2027", main: "Rientro a scuola", sub: "Ripresa regolare delle lezioni" },
        ],
        note: "Delibera del Consiglio di Istituto del 31 agosto 2026 (Comunicato n. 75).",
        speech: "Il ponte del primo maggio va da giovedì 29 aprile a venerdì 30 aprile 2027. Con la festività di sabato 1° maggio e domenica 2, si rientra a scuola lunedì 3 maggio 2027.",
        rooms: [],
      };
    }

    if (isPatrono) {
      return {
        title: "Ponte del Santo Patrono",
        badge: "PONTE DELIBERATO",
        lines: [
          { when: "Sabato 15 maggio 2027", main: "Ponte del Santo Patrono", sub: "Lezioni sospese e chiusura totale istituto e uffici" },
          { when: "Lunedì 17 maggio 2027", main: "Rientro a scuola", sub: "Domenica 16 maggio" },
        ],
        note: "Delibera del Consiglio di Istituto del 31 agosto 2026 (Comunicato n. 75).",
        speech: "Il ponte del Santo Patrono è sabato 15 maggio 2027, con chiusura totale dell'istituto e sospensione delle lezioni. Si rientra a scuola lunedì 17 maggio 2027.",
        rooms: [],
      };
    }

    return {
      title: "Ponti e Sospensioni Deliberate 2026/27",
      badge: "PONTI DELIBERATI",
      lines: [
        { when: "Lunedì 7 dicembre 2026", main: "Ponte dell'Immacolata", sub: "8 dicembre festività • Rientro mercoledì 9 dicembre" },
        { when: "29 - 30 aprile 2027", main: "Ponte del 1° Maggio", sub: "1° maggio festività • Rientro lunedì 3 maggio" },
        { when: "Sabato 15 maggio 2027", main: "Ponte del Santo Patrono", sub: "Chiusura totale istituto • Rientro lunedì 17 maggio" },
      ],
      note: "Sospensioni deliberate dal Consiglio di Istituto (Comunicato n. 75).",
      speech: "I ponti deliberati per l'anno scolastico sono tre: lunedì 7 dicembre per l'Immacolata con rientro il 9 dicembre, dal 29 al 30 aprile per il primo maggio con rientro il 3 maggio, e sabato 15 maggio per il Santo Patrono con rientro il 17 maggio.",
      rooms: [],
    };
  }

  if (p.subType === "prossima") {
    const upcoming = vacanze.filter((v) => v.a >= nowYMD);
    const target = upcoming.length > 0 ? upcoming[0] : vacanze[vacanze.length - 1];
    const lines = upcoming.slice(0, 4).map((v) => ({
      when: v.titolo,
      main: v.descrizione,
      sub: v.rientro ? `Rientro a scuola: ${v.rientro}` : "",
    }));
    return {
      title: `Prossima Sospensione: ${target.titolo}`,
      badge: "PROSSIMA CHIUSURA",
      lines: lines.length ? lines : [{ when: "8 giugno 2027", main: "Fine anno scolastico", sub: "" }],
      note: "Calendario scolastico ufficiale 2026/27.",
      speech: `La prossima sospensione delle lezioni è per ${target.titolo}: ${target.descrizione}. Rientro a scuola il ${formatDateSpoken(target.rientro)}.`,
      rooms: [],
    };
  }

  if (p.subType === "festivita") {
    const lines = festivita.map((f) => ({
      when: formatDateSpoken(f.data),
      main: f.nome,
      sub: "Festività obbligatoria (istituto chiuso)",
    }));
    return {
      title: "Festività Obbligatorie a.s. 2026/27",
      badge: "FESTIVITÀ",
      lines,
      note: "Festività nazionali e religiose da calendario ufficiale.",
      speech: "Le festività obbligatorie dell'anno scolastico includono San Francesco il 4 ottobre, Ognissanti il 1° novembre, l'Immacolata l'8 dicembre, Natale, Capodanno, Epifania, Pasquetta il 29 marzo, il 25 aprile, il 1° maggio e il 2 giugno.",
      rooms: [],
    };
  }

  // Fallback generale calendario
  const lines = [
    { when: "10 settembre 2026", main: "Inizio delle lezioni", sub: "Primo giorno di scuola" },
    { when: "7 dicembre 2026", main: "Ponte dell'Immacolata", sub: "Rientro mercoledì 9 dicembre" },
    { when: "24 dic 2026 - 5 gen 2027", main: "Vacanze di Natale", sub: "Rientro giovedì 7 gennaio" },
    { when: "8 - 10 febbraio 2027", main: "Carnevale e Ceneri", sub: "Rientro giovedì 11 febbraio" },
    { when: "25 - 30 marzo 2027", main: "Vacanze di Pasqua", sub: "Rientro mercoledì 31 marzo" },
    { when: "29 - 30 aprile 2027", main: "Ponte del 1° Maggio", sub: "Rientro lunedì 3 maggio" },
    { when: "Sabato 15 maggio 2027", main: "Ponte del Santo Patrono", sub: "Rientro lunedì 17 maggio" },
    { when: "8 giugno 2027", main: "Termine delle lezioni", sub: "Ultimo giorno di scuola" },
  ];

  return {
    title: "Calendario Scolastico 2026/27",
    badge: "CALENDARIO",
    lines,
    note: "Calendario scolastico ufficiale ITIS Negrelli (Comunicato n. 75).",
    speech: "Il calendario scolastico 2026/2027 prevede le vacanze di Natale dal 24 dicembre al 5 gennaio, Carnevale dall'8 al 10 febbraio, Pasqua dal 25 al 30 marzo, e i tre ponti del 7 dicembre, del primo maggio e del Santo Patrono il 15 maggio. Le lezioni terminano l'8 giugno.",
    rooms: [],
  };
}

export function answer(p, idx, ctx = {}) {
  if (p.sospensione && p.intent !== "calendario") {
    return answerSospensione(p, idx);
  }

  switch (p.intent) {
    case "aiuto":
      return answerAiuto(p);
    case "sorveglianza":
      return answerSorveglianza(p, idx, ctx);
    case "recupero":
      return answerRecupero(p, idx, ctx);
    case "docente":
      return answerDocente(p, idx);
    case "classe":
      return answerClasse(p, idx);
    case "aule_libere":
      return answerAuleLibere(p, idx);
    case "aula":
      return answerAula(p, idx);
    case "spazio_mappa":
      return answerSpazioMappa(p);
    case "attivita":
      return answerAttivita(p, idx, ctx);
    case "calendario":
      return answerCalendario(p, idx, ctx);
    case "sospensione":
      return answerSospensione(p, idx);
    case "ambiguo": {
      const names = p.candidati.slice(0, 4).map((d) => titleCase(d.nome));
      return {
        title: "Quale docente?",
        badge: "AMBIGUO",
        lines: names.map((n) => ({ when: "", main: n, sub: "" })),
        note: "Ripeti la richiesta specificando il nome e cognome completo.",
        speech: `Ho trovato più docenti: ${joinSpeech(names)}. Specifica meglio.`,
        rooms: [],
      };
    }
    default:
      return {
        title: "Non ho capito",
        badge: "",
        lines: [],
        note: "Prova: «Dove si trova la 4ITA alla terza ora?», «Cosa ha Curtolo domani?», «Quali laboratori sono liberi mercoledì alla seconda ora?»",
        speech: "Non ho capito. Puoi chiedere di un docente, di una classe, o delle aule libere.",
        rooms: [],
      };
  }
}
