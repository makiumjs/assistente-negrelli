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

  const classKeys = Object.keys(db.classi).map((id) => ({
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
  };

  const scansione = db.meta?.scansione_oraria || null;

  return { db, docenti, classKeys, aule, starts, attivita, scansione };
}

// ------------------------------------------------------------------ entità
function findClasses(q, idx) {
  const exists = (cand) => idx.classKeys.some((c) => c.key.startsWith(cand));
  let s = q;

  // "quarta ita" -> "4ita", "prima bta" -> "1bta"
  s = s.replace(/\b(prima|seconda|terza|quarta|quinta)\s+([a-z]{2,5})\b/g, (m, o, l) =>
    exists(ORD_F[o] + l) ? ORD_F[o] + l : m
  );
  // "4 ita" -> "4ita", "1 bta" -> "1bta"
  s = s.replace(/\b([1-5])\s+([a-z]{2,5})\b/g, (m, d, l) => (exists(d + l) ? d + l : m));

  const ids = [];
  const used = [];
  for (const tok of s.match(/\b[1-5][a-z]{2,5}\b/g) || []) {
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

function findDay(q, now) {
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

  const day = findDay(q, now);
  const realtime = /\b(adesso|attualmente|in questo momento|in questo istante|ora attuale)\b/.test(q);
  let hour = findHour(q);
  if (realtime) hour = currentLesson(now, idx, day);

  const isProssimo = /\b(prossim[oiea]|successiv[oiea]|imminent[ei]|futur[oiea])\b/.test(q0);
  const base = { day, hour, realtime, raw: text, now, isProssimo };

  // Controllo per le Attività (Collegi docenti, Consigli di classe, Scrutini, Colloqui, ecc.)
  const isAttivita = /\b(attivita|impegni|collegio|collegi|consiglio|consigli|cdc|scrutini|scrutinio|colloqui|colloquio|glo|pdp|pei|dipartimenti|dipartimento|esami|idoneita|debito|debiti)\b/.test(q0);

  if (isAttivita) {
    const isCollegio = /\b(collegio|collegi)\b/.test(q0);
    const isColloqui = /\b(colloqui|colloquio)\b/.test(q0);
    const isScrutini = /\b(scrutini|scrutinio)\b/.test(q0);
    const isConsigli = /\b(consiglio|consigli|cdc)\b/.test(q0);
    const isDipartimenti = /\b(dipartimenti|dipartimento)\b/.test(q0);
    const monthMatch = q0.match(/\b(settembre|ottobre|novembre|dicembre|gennaio|febbraio|marzo|aprile|maggio|giugno)\b/);
    const mese = monthMatch ? monthMatch[1] : null;

    let subType = "generale";
    if (isCollegio) subType = "collegio";
    else if (isColloqui) subType = "colloqui";
    else if (isScrutini) subType = "scrutini";
    else if (isConsigli) subType = "consigli_classe";
    else if (isDipartimenti) subType = "dipartimenti";

    return { ...base, intent: "attivita", subType, classi, mese, queryText: q0 };
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
  if (rooms.length) return { ...base, intent: "aula", rooms };

  const me = ctx.me ? scoreDocenti(normalize(ctx.me), idx) : [];
  if (me.length === 1) return { ...base, intent: "docente", docente: me[0], isSelf: true };
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

  const describe = (s) => {
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
      (s) => JSON.stringify([s.tipo, s.classe, s.materia, s.aula, s.copresenza, s.altre_classi])
    );
    if (!groups.length) {
      return {
        title,
        badge: `${dl(p.day).toUpperCase()} • GIORNATA`,
        lines: [],
        note: isPlaceholder ? "Nessuna lezione in orario (cattedra provvisoria)." : "Nessuna lezione in orario.",
        speech: p.isSelf ? `${dayCap} non hai lezioni in orario.` : `${dayCap} ${subj} non ha lezioni in orario.`,
        rooms: [],
      };
    }
    const descs = groups.map((g) => ({ g, ...describe(g.slot) }));
    const roomsCollected = descs.map((x) => x.aula).filter(Boolean);
    return {
      title,
      badge: `${dl(p.day).toUpperCase()} • GIORNATA INTERA`,
      lines: descs.map((x) => ({ when: span(x.g), main: x.main, sub: x.sub })),
      speech: `${dayCap} ${subj} ${joinSpeech(descs.map((x) => `${spokenSpan(x.g)} ${x.say}`))}.`.replace(/\s+/g, " "),
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
    lines: [{ when: `${p.hour}ª ora`, main: x.main, sub: x.sub }],
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
      const groups = groupHours(sched, (s) => JSON.stringify([s.materia, s.docenti, s.aula]));
      if (!groups.length) {
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
      out.push({
        title: `Classe ${cid}`,
        badge: `${dl(p.day).toUpperCase()} • GIORNATA INTERA`,
        lines: descs.map((x) => ({ when: span(x.g), main: x.main, sub: x.sub })),
        speech: `${dayCap} la ${cid} ${joinSpeech(descs.map((x) => `${spokenSpan(x.g)} ${x.say}`))}.`,
        rooms: descs.map((x) => x.aula).filter(Boolean),
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
      lines: [{ when: `${p.hour}ª ora`, main: x.main, sub: x.sub }],
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
    lines: free.map((a) => ({ when: "Libera", main: titleCase(a), sub: "" })),
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
    if (p.day === "domenica") {
      out.push(closedDay(p, title));
      continue;
    }
    if (p.day === "sabato" && p.hour > 4) {
      out.push(saturdayExceeded(p, title));
      continue;
    }
    if (p.realtime && p.hour === null) {
      out.push({ ...noHourNow(p), title });
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
        .map((h) => ({ when: `${h}ª ora`, main: desc(occ[h]), sub: "" }));
      out.push({
        title,
        badge: `${dl(p.day).toUpperCase()} • GIORNATA`,
        lines,
        note: lines.length ? "" : "Non occupata in questa giornata.",
        speech: lines.length
          ? `${dayCap} ${title} è occupata in ${lines.length} ore.`
          : `${dayCap} ${title} è libera per l'intera giornata.`,
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
            lines: [{ when: "Occupata", main: desc(o), sub: "" }],
            speech: `${dayCap} in ${when} ${title} è occupata dalla ${desc(o)}.`,
            rooms: [r.nome],
          }
        : {
            title,
            badge: hourBadge(p, idx),
            lines: [{ when: "Libera", main: "", sub: "" }],
            speech: `${dayCap} in ${when} ${title} è libera.`,
            rooms: [r.nome],
          }
    );
  }
  return mergeAnswers(out);
}

const MONTH_INDEX = {
  settembre: 8, ottobre: 9, novembre: 10, dicembre: 11,
  gennaio: 0, febbraio: 1, marzo: 2, aprile: 3, maggio: 4, giugno: 5, luglio: 6, agosto: 7
};

export function parseActivityDate(item) {
  if (!item) return null;
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
          sub: m.periodo ? `${m.periodo}` : "",
        }));
        const targetWhere = target.aula ? ` in ${target.aula}` : "";
        const title = isScrutiniOnly ? `Prossimo Scrutinio ${clsId}` : `Prossimo Consiglio di Classe ${clsId}`;
        const speech = isScrutiniOnly
          ? `Il prossimo scrutinio per la ${clsId} è in programma ${target.giorno || target.periodo} alle ore ${target.ora}${targetWhere}.`
          : `Il prossimo consiglio di classe per la ${clsId} si terrà ${target.giorno || target.periodo} alle ${target.ora}${targetWhere}.`;
        return {
          title,
          badge: "PROSSIMA ATTIVITÀ",
          lines,
          note: `Calendario dal Piano Annuale delle Attività 2026/27 per la classe ${clsId}.`,
          speech,
          rooms: nextList.map((m) => m.aula).filter(Boolean),
        };
      }

      const title = isScrutiniOnly ? `Scrutini Classe ${clsId}` : `Consigli di Classe ${clsId}`;
      const lines = matches.map((m) => ({
        when: m.giorno || m.periodo,
        main: `Ore ${m.ora} • ${m.aula || "Lab. Multimediale"}`,
        sub: m.periodo ? `${m.periodo}` : "",
      }));

      const spokenDates = matches.slice(0, 4).map((m) => `${m.giorno || m.periodo} alle ${m.ora}`).join(", ");
      return {
        title,
        badge: "CALENDARIO ATTIVITÀ",
        lines,
        note: `Calendario dal Piano Annuale delle Attività 2026/27 per la classe ${clsId}.`,
        speech: `I consigli di classe in programma per la ${clsId} sono: ${spokenDates}${matches.length > 4 ? " e altri successivi." : "."}`,
        rooms: matches.map((m) => m.aula).filter(Boolean),
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
    if (p.classi?.length) {
      const clsId = p.classi[0].toUpperCase();
      if (/NEG|ITA|ITE|BTA|BTB|MMA|MMC|MME|CAT|EEC|BSA|BSB|CS|CMS|MS/i.test(clsId)) {
        filtered = colloqui.filter((c) => c.sede.toLowerCase() === "negrelli");
      } else if (/AFM|RIM|BRIM/i.test(clsId)) {
        filtered = colloqui.filter((c) => c.sede.toLowerCase() === "colotti");
      } else if (/ASS|SSAS|IAMI/i.test(clsId)) {
        filtered = colloqui.filter((c) => c.sede.toLowerCase() === "rizzarda");
      }
    }
    filtered = sortActivities(filtered);

    if (p.isProssimo) {
      const upcoming = filtered.filter((c) => {
        const d = parseActivityDate(c);
        return d && d >= now;
      });
      const target = upcoming.length > 0 ? upcoming[0] : filtered[filtered.length - 1];
      const nextList = upcoming.length > 0 ? upcoming : filtered;
      const lines = nextList.map((c) => ({
        when: `${c.periodo} • ${c.giorno} ${c.data}`,
        main: `Sede: ${c.sede} (${c.classi})`,
        sub: "",
      }));
      return {
        title: "Prossimi Colloqui Generali",
        badge: "PROSSIMA ATTIVITÀ",
        lines,
        note: "Date dei colloqui generali per il I e II periodo.",
        speech: `I prossimi colloqui generali per ${target.sede} si terranno ${target.giorno} ${target.data} (${target.classi}).`,
        rooms: [],
      };
    }

    const lines = filtered.map((c) => ({
      when: `${c.periodo} • ${c.giorno} ${c.data}`,
      main: `Sede: ${c.sede} (${c.classi})`,
      sub: "",
    }));
    return {
      title: "Colloqui Generali con i Genitori",
      badge: "COLLOQUI",
      lines,
      note: "Date dei colloqui generali per il I e II periodo.",
      speech: "I colloqui generali si terranno a dicembre 2026 per il primo periodo e ad aprile 2027 per il secondo periodo.",
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

export function answer(p, idx, ctx = {}) {
  switch (p.intent) {
    case "docente":
      return answerDocente(p, idx);
    case "classe":
      return answerClasse(p, idx);
    case "aule_libere":
      return answerAuleLibere(p, idx);
    case "aula":
      return answerAula(p, idx);
    case "attivita":
      return answerAttivita(p, idx, ctx);
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
