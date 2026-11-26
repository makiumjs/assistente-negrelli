import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { buildIndex, parseQuery, answer, resolveRoomLocation } from "../public/js/query-engine.js";

const db = JSON.parse(readFileSync(new URL("../public/data/orario_completo.json", import.meta.url)));
const idx = buildIndex(db);
const now = new Date("2026-10-07T10:00:00"); // mercoledì 7 ottobre 2026 ore 10:00
const ask = (t, me = "", customNow = now) => {
  const ctx = { now: customNow, me };
  const p = parseQuery(t, idx, ctx);
  return { p, a: answer(p, idx, ctx) };
};

console.log("=== 1. Test Query Classe ===");
let r = ask("Dove si trova la 4ITA alla terza ora?");
assert.equal(r.p.intent, "classe");
assert.deepEqual(r.p.classi, ["4ITA"]);
assert.equal(r.p.hour, 3);
console.log("✓ 4ITA 3ª ora:", r.a.speech);

for (const v of [
  "4 ita giovedì alla terza ora",
  "quarta ITA giovedi 3 ora",
  "[4 ITA] giovedì ora 3",
  "4ita giovedì alla 3",
]) {
  r = ask(v);
  assert.deepEqual(r.p.classi, ["4ITA"], v);
  assert.equal(r.p.hour, 3, v);
  assert.equal(r.p.day, "giovedi", v);
}
console.log("✓ Variazioni sintattiche 4ITA superate");

r = ask("dove è la 4ee lunedì");
assert.deepEqual(r.p.classi, ["4EE"]);
console.log("✓ 4EE lunedì:", r.a.speech);

console.log("\n=== 2. Test Query Docente ===");
r = ask("Cosa ha Curtolo domani?");
assert.equal(r.p.intent, "docente");
assert.equal(r.p.docente.nome, "Malè (Curtolo)");
assert.equal(r.p.day, "giovedi");
console.log("✓ Malè (Curtolo) domani:", r.a.speech);

r = ask("cosa ho oggi", "Cassarino");
assert.ok(r.p.isSelf);
assert.equal(r.p.intent, "docente");
console.log("✓ Cassarino self oggi:", r.a.speech);

r = ask("cosa ha Cassarino lunedì");
assert.equal(r.p.intent, "docente");
assert.equal(r.p.docente.nome, "Cassarino");
assert.ok(r.a.speech.includes("terza e quarta ora"));
assert.ok(r.a.speech.includes("3ITA"));
assert.ok(r.a.speech.includes("quinta ora"));
assert.ok(r.a.speech.includes("disposizione"));
assert.ok(r.a.speech.includes("sesta ora") && r.a.speech.includes("Q1"));
console.log("✓ Cassarino lunedì (3ª-4ª 3ITA + 5ª disp + 6ª rec Q1):", r.a.speech);

r = ask("orario Guizzo lunedì");
assert.equal(r.p.intent, "docente");
assert.equal(r.p.docente.nome, "Guizzo");
assert.equal(r.p.day, "lunedi");
console.log("✓ Guizzo (ex _ele 4) lunedì:", r.a.speech);

r = ask("cosa ha Curtolo lunedì alla sesta ora");
assert.equal(r.p.intent, "docente");
assert.equal(r.p.hour, 6);
assert.equal(r.p.day, "lunedi");
assert.ok(r.a.speech.includes("sesta ora"));
assert.ok(r.a.speech.includes("Aula 115"));
console.log("✓ Curtolo 6ª ora:", r.a.speech);

console.log("\n=== 3. Test Query Aule Libere ===");
r = ask("Quali laboratori sono liberi mercoledì alla 2ª ora?");
assert.equal(r.p.intent, "aule_libere");
assert.equal(r.p.hour, 2);
assert.equal(r.p.day, "mercoledi");
console.log("✓ Laboratori liberi:", r.a.speech);

r = ask("quali aule sono libere lunedì");
assert.equal(r.p.intent, "aule_libere");
assert.equal(r.p.hour, null);
console.log("✓ Aule libere intera giornata:", r.a.speech);

console.log("\n=== 4. Test Singola Aula / Spazio ===");
r = ask("chi c'è in palestra martedì alla seconda ora");
assert.equal(r.p.intent, "aula");
assert.equal(r.p.hour, 2);
console.log("✓ Palestra martedì:", r.a.speech);

r = ask("chi c'è in aula 201 lunedì alla prima ora");
assert.equal(r.p.intent, "aula");
assert.equal(r.p.hour, 1);
console.log("✓ Aula 201 lunedì:", r.a.speech);

console.log("\n=== 5. Test Casi Limite ed Edge Cases ===");
r = ask("cosa ha Curtolo domenica");
assert.equal(r.a.badge, "DOMENICA");
console.log("✓ Domenica chiusa:", r.a.speech);

r = ask("dov'è bortol"); // Match ambiguo: Bortolamiol e Bortolas
assert.equal(r.p.intent, "ambiguo");
console.log("✓ Ambiguità rilevata:", r.a.speech);

r = ask("quanto fa due più due");
assert.equal(r.p.intent, "non_trovato");
console.log("✓ Non trovato:", r.a.speech);

console.log("\n=== 6. Test Piano Attività ===");
r = ask("quando sono i consigli di classe della 4ITA");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "consigli_classe");
assert.ok(r.a.title.includes("4ITA"));
console.log("✓ Consigli di Classe 4ITA:", r.a.speech);

r = ask("quando è il collegio docenti");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "collegio");
assert.equal(r.a.title, "Collegio Docenti");
console.log("✓ Collegio Docenti:", r.a.speech);

r = ask("quando ci sono i colloqui generali");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "colloqui");
assert.ok(r.a.title.includes("Colloqui"));
console.log("✓ Colloqui Generali:", r.a.speech);

r = ask("quali sono le attività di ottobre");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.mese, "ottobre");
assert.ok(r.a.title.includes("Ottobre"));
console.log("✓ Attività Ottobre:", r.a.speech);

r = ask("quando sono gli scrutini della 4ITA");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "scrutini");
assert.ok(r.a.title.includes("4ITA"));
console.log("✓ Scrutini 4ITA:", r.a.speech);

r = ask("qual è il prossimo collegio docenti");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.isProssimo, true);
assert.equal(r.a.title, "Prossimo Collegio Docenti");
assert.equal(r.a.badge, "PROSSIMA ATTIVITÀ");
assert.ok(r.a.speech.includes("28 mercoledì"));
console.log("✓ Prossimo Collegio Docenti:", r.a.speech);

r = ask("prossimo consiglio di classe della 4ITA");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.isProssimo, true);
assert.equal(r.a.title, "Prossimo Consiglio di Classe 4ITA");
assert.equal(r.a.badge, "PROSSIMA ATTIVITÀ");
assert.ok(r.a.speech.includes("9 ottobre 2026"));
console.log("✓ Prossimo CdC 4ITA:", r.a.speech);

r = ask("qual è la prossima attività");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.isProssimo, true);
assert.equal(r.a.title, "Prossima Attività d'Istituto");
assert.equal(r.a.badge, "PROSSIMA ATTIVITÀ");
console.log("✓ Prossima Attività Istituto:", r.a.speech);

console.log("\n=== 7. Test Scansione Oraria Ufficiale ===");
r = ask("4ITA lunedì alla prima ora");
assert.ok(r.a.badge.includes("7:50-8:40"));
console.log("✓ Scansione Lun-Mer (1ª ora 7:50-8:40):", r.a.badge);

r = ask("4ITA giovedì alla prima ora");
assert.ok(r.a.badge.includes("7:50-8:50"));
console.log("✓ Scansione Gio-Ven (1ª ora 7:50-8:50):", r.a.badge);

r = ask("4ITA sabato alla quinta ora");
assert.equal(r.a.badge, "SABATO • USCITA ORE 12:05");
console.log("✓ Sabato oltre 4ª ora (Uscita ore 12:05):", r.a.speech);

console.log("\n=== 8. Test Calendario Scolastico ===");
r = ask("quando finisce la scuola");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "fine_scuola");
assert.ok(r.a.speech.includes("8 giugno 2027"));
assert.equal(r.a.badge, "CALENDARIO SCOLASTICO");
console.log("✓ Fine scuola:", r.a.speech);

r = ask("quando inizia la scuola");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "inizio_scuola");
assert.ok(r.a.speech.includes("10 settembre 2026"));
console.log("✓ Inizio scuola:", r.a.speech);

r = ask("quando sono le vacanze di natale");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "natale");
assert.ok(r.a.speech.includes("24 dicembre 2026"));
assert.ok(r.a.speech.includes("7 gennaio 2027"));
assert.equal(r.a.badge, "VACANZE NATALIZIE");
console.log("✓ Vacanze di Natale:", r.a.speech);

r = ask("quando sono le vacanze di pasqua");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "pasqua");
assert.ok(r.a.speech.includes("25 marzo"));
assert.ok(r.a.speech.includes("31 marzo 2027"));
assert.equal(r.a.badge, "VACANZE PASQUALI");
console.log("✓ Vacanze di Pasqua:", r.a.speech);

r = ask("quando è carnevale");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "carnevale");
assert.ok(r.a.speech.includes("8 febbraio"));
assert.ok(r.a.speech.includes("11 febbraio 2027"));
assert.equal(r.a.badge, "CARNEVALE");
console.log("✓ Carnevale e Ceneri:", r.a.speech);

r = ask("quali sono i ponti");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "ponti");
assert.ok(r.a.speech.includes("7 dicembre"));
assert.ok(r.a.speech.includes("primo maggio"));
assert.ok(r.a.speech.includes("Santo Patrono"));
assert.equal(r.a.badge, "PONTI DELIBERATI");
console.log("✓ Tutti i ponti deliberati:", r.a.speech);

r = ask("quando è il ponte dell'immacolata");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "ponti");
assert.ok(r.a.speech.includes("7 dicembre"));
assert.ok(r.a.speech.includes("9 dicembre"));
console.log("✓ Ponte Immacolata specifico:", r.a.speech);

r = ask("qual è la prossima vacanza");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "prossima");
assert.ok(r.a.speech.includes("Ponte dell'Immacolata"));
console.log("✓ Prossima vacanza:", r.a.speech);

r = ask("calendario scolastico");
assert.equal(r.p.intent, "calendario");
assert.equal(r.p.subType, "generale");
assert.equal(r.a.badge, "CALENDARIO");
console.log("✓ Panoramica calendario:", r.a.speech);

r = ask("cosa fa Cassarino il 7 dicembre");
assert.ok(r.a.speech.includes("Cassarino non ha lezioni"));
assert.ok(r.a.speech.includes("Ponte dell'Immacolata"));
assert.ok(r.a.speech.includes("9 dicembre"));
assert.equal(r.a.badge, "VACANZE SCOLASTICHE");
console.log("✓ Blocco orario docente su sospensione (7 dic):", r.a.speech);

r = ask("cosa ha la 4ITA il 25 dicembre");
assert.ok(r.a.speech.includes("4ITA non ha lezioni"));
assert.ok(r.a.speech.includes("Natale"));
assert.equal(r.a.badge, "FESTIVITÀ");
console.log("✓ Blocco orario classe su festività (25 dic):", r.a.speech);

const dec7Now = new Date("2026-12-07T10:00:00");
const pDec7 = parseQuery("cosa ho oggi", idx, { now: dec7Now, me: "Cassarino" });
const aDec7 = answer(pDec7, idx);
assert.ok(aDec7.speech.includes("non hai lezioni"));
assert.ok(aDec7.speech.includes("Ponte dell'Immacolata"));
console.log("✓ Blocco orario relativo 'oggi' in giorno di vacanza:", aDec7.speech);

console.log("\n=== 9. Test Convocazioni GLO (Comunicato n. 83) ===");
r = ask("quando è il GLO della 4ITA");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "glo");
assert.ok(r.a.speech.includes("lunedì 26 ottobre 2026"));
assert.ok(r.a.speech.includes("15:30"));
assert.ok(r.a.speech.includes("sede del Negrelli"));
assert.equal(r.a.badge, "GLO • CONDIVISIONE PEI");
console.log("✓ GLO 4ITA:", r.a.speech);

r = ask("quando sono i GLO della 3ITA");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "glo");
assert.ok(r.a.speech.includes("16:00"));
assert.ok(r.a.speech.includes("26 ottobre"));
console.log("✓ GLO 3ITA:", r.a.speech);

r = ask("quando è il GLO della 5IAMI");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "glo");
assert.ok(r.a.speech.includes("martedì 27 ottobre 2026"));
assert.ok(r.a.speech.includes("13:45"));
console.log("✓ GLO 5IAMI:", r.a.speech);

r = ask("quando sono i GLO per il PEI");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "glo");
assert.ok(r.a.speech.includes("26 al 30 ottobre 2026"));
assert.ok(r.a.speech.includes("22 classi"));
assert.equal(r.a.badge, "GLO • CONDIVISIONE PEI");
console.log("✓ Panoramica GLO:", r.a.speech);

r = ask("qual è il prossimo GLO");
assert.equal(r.p.intent, "attivita");
assert.equal(r.p.subType, "glo");
assert.equal(r.p.isProssimo, true);
assert.equal(r.a.badge, "PROSSIMO GLO");
assert.ok(r.a.speech.includes("lunedì 26 ottobre 2026"));
console.log("✓ Prossimo GLO:", r.a.speech);

console.log("\n=== 10. Test Ricerca Posizione & Mappe Piani (Wayfinding) ===");
r = ask("dov'è l'aula 118");
assert.equal(r.p.intent, "aula");
assert.equal(r.p.isWhere, true);
assert.ok(r.a.note.includes("1° PIANO"));
assert.ok(r.a.speech.includes("1° piano") || r.a.speech.includes("primo piano"));
console.log("✓ Dov'è Aula 118:", r.a.speech);

r = ask("dov'è la mensa");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "028");
assert.equal(r.p.space.floor, 0);
assert.ok(r.a.speech.includes("piano terra"));
console.log("✓ Dov'è Mensa (Locale 028):", r.a.speech);

r = ask("dove si trova la segreteria");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.floor, 1);
assert.ok(r.a.speech.includes("1° piano"));
console.log("✓ Dov'è Segreteria:", r.a.speech);

r = ask("dov'è la biblioteca");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.floor, 0);
assert.ok(r.a.speech.includes("piano terra"));
console.log("✓ Dov'è Biblioteca:", r.a.speech);

r = ask("dov'è l'officina");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "026");
assert.ok(r.a.speech.includes("piano terra"));
console.log("✓ Dov'è Officina (Locale 026):", r.a.speech);

r = ask("dov'è l'aula insegnanti");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "028");
assert.ok(r.a.speech.includes("piano terra"));
console.log("✓ Dov'è Aula Insegnanti (Locale 028):", r.a.speech);

r = ask("dov'è la vicepresidenza");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "060");
assert.ok(r.a.speech.includes("piano terra"));
console.log("✓ Dov'è Vicepresidenza (Locale 060):", r.a.speech);

r = ask("dov'è la segreteria didattica");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "035");
assert.ok(r.a.speech.includes("piano terra"));
console.log("✓ Dov'è Segreteria Didattica (Locale 035):", r.a.speech);

r = ask("dov'è l'area ristoro");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "069");
console.log("✓ Dov'è Area Ristoro / Bar (Locale 069):", r.a.speech);

r = ask("dov'è l'ufficio vicepresidenza al primo piano");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.p.space.code, "107");
assert.equal(r.p.space.floor, 1);
assert.ok(r.a.speech.includes("1° piano"));
console.log("✓ Dov'è Ufficio Vicepresidenza (Locale 107):", r.a.speech);

console.log("\n=== 11. Test Risoluzione Locali & Servizi Speciali (Systematic Debugging) ===");
// Ascensore
r = ask("dov'è l'ascensore");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.a.rooms[0], "ASC");
const ascLoc = resolveRoomLocation(r.a.rooms[0]);
assert.ok(ascLoc);
assert.equal(ascLoc.code, "ASC");
assert.equal(ascLoc.floor, 0);
console.log("✓ Ascensore risolto:", ascLoc.name, "-> Piano", ascLoc.floor);

// Bagni / WC
r = ask("dov'è il bagno");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.a.rooms[0], "WC");
const wcLoc = resolveRoomLocation(r.a.rooms[0]);
assert.ok(wcLoc);
assert.equal(wcLoc.code, "WC");
console.log("✓ Servizi Igienici (WC) risolti:", wcLoc.name);

// Scale
r = ask("dove sono le scale");
assert.equal(r.p.intent, "spazio_mappa");
assert.equal(r.a.rooms[0], "SCALA");
const scalaLoc = resolveRoomLocation(r.a.rooms[0]);
assert.ok(scalaLoc);
assert.equal(scalaLoc.code, "SCALA");
console.log("✓ Scale risolte:", scalaLoc.name);

// Aula Pot-Disp
const potLoc = resolveRoomLocation("Aula Pot-Disp");
assert.ok(potLoc);
assert.equal(potLoc.code, "028");
console.log("✓ Aula Pot-Disp risolta su Locale 028 (Aula Insegnanti)");

// Nuovi locali aggiunti a MAP_DIRECTORY
for (const code of ["037", "137", "211", "212", "214", "221"]) {
  const loc = resolveRoomLocation(code);
  assert.ok(loc, `Locale ${code} deve essere risolto da MAP_DIRECTORY`);
  assert.equal(loc.code, code);
}
console.log("✓ Tutti i locali 037, 137, 211, 212, 214, 221 verificati con successo");

console.log("\n=== 12. Test Convocazioni Consigli di Classe Novembre 2026 (Comunicato n. 124) ===");
const novNow = new Date("2026-11-06T10:00:00"); // 6 novembre 2026

// 1. Prossimo CdC 4ITA a novembre
let pNov = parseQuery("prossimo consiglio di classe della 4ITA", idx, { now: novNow });
let aNov = answer(pNov, idx, { now: novNow });
assert.equal(pNov.intent, "attivita");
assert.equal(pNov.subType, "consigli_classe");
assert.equal(aNov.title, "Prossimo Consiglio di Classe 4ITA");
assert.ok(aNov.speech.includes("Giovedì 19 novembre 2026 alle 16:00"));
assert.ok(aNov.speech.includes("genitori e studenti"));
assert.ok(aNov.note.includes("Comunicato n. 124"));
console.log("✓ CdC 4ITA Novembre:", aNov.speech);

// 2. CdC Sezione Colotti (1A)
pNov = parseQuery("prossimo consiglio di classe 1A", idx, { now: novNow });
aNov = answer(pNov, idx, { now: novNow });
assert.equal(aNov.title, "Prossimo Consiglio di Classe 1A");
assert.ok(aNov.speech.includes("Lunedì 9 novembre 2026 alle 14:30"));
assert.ok(aNov.speech.includes("Lim"));
console.log("✓ CdC 1A (Colotti):", aNov.speech);

// 3. CdC Sezione Rizzarda (5IAMI)
pNov = parseQuery("prossimo consiglio di classe 5IAMI", idx, { now: novNow });
aNov = answer(pNov, idx, { now: novNow });
assert.equal(aNov.title, "Prossimo Consiglio di Classe 5IAMI");
assert.ok(aNov.speech.includes("Mercoledì 11 novembre 2026 alle 17:30"));
assert.ok(aNov.speech.includes("LIM 1"));
console.log("✓ CdC 5IAMI (Rizzarda):", aNov.speech);

// 4. CdC Corso Serale Negrelli (5CMS)
pNov = parseQuery("prossimo consiglio di classe 5CMS", idx, { now: novNow });
aNov = answer(pNov, idx, { now: novNow });
assert.equal(aNov.title, "Prossimo Consiglio di Classe 5CMS");
assert.ok(aNov.speech.includes("Martedì 24 novembre 2026 alle 16:00"));
console.log("✓ CdC 5CMS (Serale Negrelli):", aNov.speech);

// 5. Panoramica calendario novembre (senza classe)
pNov = parseQuery("quando sono i consigli di classe a novembre", idx, { now: novNow });
aNov = answer(pNov, idx, { now: novNow });
assert.equal(aNov.badge, "COMUNICATO N. 124");
assert.equal(aNov.lines.length, 11);
assert.ok(aNov.speech.includes("dal 9 al 24 novembre"));
assert.ok(aNov.speech.includes("genitori e studenti"));
console.log("✓ Panoramica CdC Novembre:", aNov.speech);

// 6. Ordine del giorno Consigli di Classe
pNov = parseQuery("ordine del giorno consigli di classe", idx, { now: novNow });
aNov = answer(pNov, idx, { now: novNow });
assert.equal(aNov.title, "Ordine del Giorno Consigli di Classe");
assert.ok(aNov.speech.includes("ordine del giorno dei consigli di classe"));
assert.ok(aNov.speech.includes("PDP e PEI"));
console.log("✓ Ordine del Giorno CdC:", aNov.speech);

console.log("\n=== 13. Test Guida alle Domande Possibili (Help) ===");
for (const helpQ of ["quali domande posso farti?", "domande possibili", "cosa posso chiederti", "cosa posso chiedere?", "esempi di domande", "cosa sai fare?"]) {
  const rHelp = ask(helpQ);
  assert.equal(rHelp.p.intent, "aiuto", `Query "${helpQ}" deve avere intent "aiuto"`);
  assert.equal(rHelp.a.title, "Guida alle Domande Possibili");
  assert.equal(rHelp.a.badge, "GUIDA • COMANDI DISPONIBILI");
  assert.ok(rHelp.a.lines.length >= 7);
  assert.ok(rHelp.a.lines.some((l) => l.when === "Consigli CdC"));
  assert.ok(rHelp.a.lines.some((l) => l.when === "Mappa Piani"));
  assert.ok(rHelp.a.lines.every((l) => Boolean(l.query)));
}
console.log("✓ Guida alle domande verificata con successo per tutte le varianti");

console.log("\n=== 14. Test Orario mod1a, Recuperi Q1/Q2 & Sorveglianze (Comunicato n. 167) ===");
const nov19 = new Date("2026-11-19T10:00:00"); // Giovedì 19 novembre 2026 -> Settimana ISO 47 (dispari -> Q1)
const nov23 = new Date("2026-11-23T10:00:00"); // Lunedì 23 novembre 2026 -> Settimana ISO 48 (pari -> Q2)

// 1. Verifica parità settimane Q1 / Q2
let r14 = ask("questa settimana è Q1 o Q2?", "", nov19);
assert.equal(r14.p.intent, "recupero");
assert.ok(r14.a.title.includes("Q1"));
assert.ok(r14.a.speech.includes("47") && r14.a.speech.includes("dispari"));
console.log("✓ Settimana 19 nov -> Q1:", r14.a.speech);

r14 = ask("questa settimana è Q1 o Q2?", "", nov23);
assert.equal(r14.p.intent, "recupero");
assert.ok(r14.a.title.includes("Q2"));
assert.ok(r14.a.speech.includes("48") && r14.a.speech.includes("pari"));
console.log("✓ Settimana 23 nov -> Q2:", r14.a.speech);

// 2. Recuperi per docente (Cassarino = Lunedì 6ª ora Q1; Zadra = Mer 4ª Q2)
r14 = ask("ore di recupero Cassarino", "", nov19);
assert.equal(r14.p.intent, "recupero");
assert.equal(r14.a.lines.length, 1);
assert.ok(r14.a.lines[0].when.includes("Lunedì") && r14.a.lines[0].when.includes("6ª"));
assert.ok(r14.a.lines[0].main.includes("Q1") && r14.a.lines[0].main.includes("Attivo questa settimana"));
console.log("✓ Recupero Cassarino (Q1 attivo in sett. 47):", r14.a.speech);

r14 = ask("quando ho recupero?", "Zadra", nov23);
assert.equal(r14.p.intent, "recupero");
assert.equal(r14.a.lines.length, 1);
assert.ok(r14.a.lines.some((l) => l.when.includes("Mercoledì") && l.main.includes("Q2")));
console.log("✓ Recuperi Zadra (Mer Q2):", r14.a.speech);

// 3. Chi ha recupero in un giorno specifico
r14 = ask("chi ha recupero lunedì?", "", nov19);
assert.equal(r14.p.intent, "recupero");
assert.equal(r14.a.lines.length, 10);
assert.ok(r14.a.lines.some((l) => l.main.includes("Cassarino")));
console.log("✓ Recuperi lunedì:", r14.a.lines.length, "docenti");

// 4. Sorveglianze per docente (esplicito e self)
r14 = ask("quando ho sorveglianza?", "Cassarino", nov19);
assert.equal(r14.p.intent, "sorveglianza");
assert.equal(r14.a.lines.length, 2);
assert.ok(r14.a.lines.some((l) => l.when === "Lunedì" && l.main === "2° Piano"));
assert.ok(r14.a.lines.some((l) => l.when === "Sabato" && l.main === "Cortile ingresso"));
console.log("✓ Sorveglianza self Cassarino (Lun 2° Piano + Sab Cortile):", r14.a.speech);

r14 = ask("dove fa sorveglianza Chiariello?", "", nov19);
assert.equal(r14.p.intent, "sorveglianza");
assert.equal(r14.a.lines.length, 1);
assert.ok(r14.a.lines.some((l) => l.when === "Venerdì" && l.main === "Cortile ingresso"));
console.log("✓ Sorveglianza Chiariello (Ven Cortile):", r14.a.speech);

// 5. Sorveglianze per giorno e zona
r14 = ask("chi fa sorveglianza oggi?", "", nov19);
assert.equal(r14.p.intent, "sorveglianza");
assert.equal(r14.a.title, "Sorveglianze • Giovedì");
assert.equal(r14.a.lines.length, 8);
assert.ok(r14.a.badge.includes("10:50-11:05") && r14.a.badge.includes("15 MIN"));
console.log("✓ Sorveglianze giovedì (8 zone):", r14.a.speech);

r14 = ask("chi fa sorveglianza in cortile ingresso lunedì?", "", nov19);
assert.equal(r14.p.intent, "sorveglianza");
assert.ok(r14.a.speech.includes("Debortoli") && r14.a.speech.includes("Feltrin") && r14.a.speech.includes("Palma"));
console.log("✓ Sorveglianza Cortile ingresso lunedì:", r14.a.speech);

// 6. Durata intervallo
r14 = ask("quanto dura l'intervallo?", "", nov19);
assert.equal(r14.p.intent, "sorveglianza");
assert.ok(r14.a.speech.includes("10 minuti") && r14.a.speech.includes("15 minuti"));
console.log("✓ Durata intervallo:", r14.a.speech);

// 7. Nuovi docenti mod1a (Chiariello, Plutino, Panico, Carruggio, Di Palma, D'Albore)
for (const docName of ["Chiariello", "Plutino", "Panico", "Carruggio", "Di Palma", "D'Albore", "Malè"]) {
  const rd = ask(`cosa ha ${docName} venerdì`, "", nov19);
  assert.equal(rd.p.intent, "docente", `Docente ${docName} non trovato`);
}
console.log("✓ Tutti i nuovi/sostituiti docenti mod1a risolti correttamente");

console.log("\n=== 15. Test Agenda Completa di Giornata (Lezioni + Sorveglianze + CdC + Collegi) ===");
const nov18 = new Date("2026-11-18T11:30:00"); // Mercoledì 18 novembre 2026

// 1. "domani" per Cassarino (19 nov): lezioni + CdC 3ITA, 4ITA, 5ITA (NO 3CAT!)
let r15 = ask("domani", "Cassarino", nov18);
assert.equal(r15.p.intent, "docente");
assert.ok(r15.a.badge.includes("AGENDA COMPLETA"));
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 3ITA")));
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 4ITA")));
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 5ITA")));
assert.ok(!r15.a.lines.some((l) => l.main && l.main.includes("3CAT")), "Non deve includere CdC di classi non del docente");
console.log("✓ Cassarino 'domani' (19 nov): lezioni + 3 CdC propri");

// 2. "venerdì" per Cassarino (20 nov): lezioni + CdC 5ITB
r15 = ask("venerdì", "Cassarino", nov18);
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 5ITB")));
console.log("✓ Cassarino 'venerdì' (20 nov): lezioni + CdC 5ITB");

// 2b. "lunedì 30 novembre" per Cassarino: lezioni + Sorveglianza 2° Piano + Recupero Q1
let r15b = ask("cosa ho il 30 novembre", "Cassarino");
assert.ok(r15b.a.lines.some((l) => l.main && l.main.includes("Sorveglianza • 2° Piano")));
assert.ok(r15b.a.lines.some((l) => l.main && l.main.includes("Recupero (Q1")));
console.log("✓ Cassarino '30 novembre': lezioni + sorveglianza 2° Piano + recupero Q1");

// 3. Mapping classi articolate (De Bacco 4EE/5EE -> CdC 4EEC/5EEC venerdì 20 nov)
r15 = ask("cosa ha De Bacco venerdì", "", nov18);
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 4EEC")));
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 5EEC")));
console.log("✓ De Bacco venerdì (20 nov): mapping articolate 4EE/5EE -> CdC 4EEC/5EEC");

// 4. Agenda classe ("4ITA domani" il 18 nov -> lezioni + CdC 4ITA ore 16:00)
r15 = ask("4ITA domani", "", nov18);
assert.equal(r15.p.intent, "classe");
assert.ok(r15.a.badge.includes("AGENDA COMPLETA"));
assert.ok(r15.a.lines.some((l) => l.main && l.main.includes("Consiglio di Classe 4ITA")));
console.log("✓ 4ITA 'domani' (19 nov): lezioni + CdC 4ITA");

// 5. Giorno senza lezioni al mattino ma con Collegio Docenti (Cassarino mer 28 ott)
r15 = ask("cosa ho il 28 ottobre", "Cassarino", new Date("2026-10-18T10:00:00"));
assert.equal(r15.p.intent, "docente");
assert.ok(r15.a.lines.some((l) => l.main && /collegio docenti/i.test(l.main)));
console.log("✓ Giorno libero al mattino con Collegio Docenti rilevato correttamente");

console.log("\n=== 16. Test Colloqui Generali Genitori/Docenti Dicembre 2026 (Comunicato n. 185) ===");

// 1. Query generale per i colloqui di dicembre
let r16 = ask("quando sono i colloqui di dicembre");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.equal(r16.a.lines.length, 4);
assert.ok(r16.a.lines.some((l) => l.when.includes("01.12.26") && l.main.includes("Colotti")));
assert.ok(r16.a.lines.some((l) => l.when.includes("02.12.26") && l.main.includes("Rizzarda")));
assert.ok(r16.a.lines.some((l) => l.when.includes("03.12.26") && l.main.includes("Negrelli (biennio)")));
assert.ok(r16.a.lines.some((l) => l.when.includes("04.12.26") && l.main.includes("Negrelli (triennio)")));
assert.ok(r16.a.lines.every((l) => l.when.includes("Ore 14:30-17:30")));
assert.ok(r16.a.note.includes("Comunicato n. 185"));
assert.ok(r16.a.speech.includes("14:30 alle 17:30"));
console.log("✓ Colloqui dicembre generale:", r16.a.speech);

// 2. Query specifica classe triennio Negrelli (4ITA)
r16 = ask("quando ci sono i colloqui per la 4ITA?");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.equal(r16.a.lines.length, 13); // Elenco 13 docenti con orari individuali
assert.ok(r16.a.lines.some((l) => l.main.includes("Cassarino") && l.when === "Ore 14:30-17:30"));
assert.ok(r16.a.lines.some((l) => l.main.includes("Boschello") && l.when === "Ore 14:00-17:00"));
assert.ok(r16.a.lines.every((l) => l.sub.includes("04.12.26")));
assert.ok(r16.a.speech.includes("4ITA"));
console.log("✓ Colloqui 4ITA (Negrelli triennio):", r16.a.speech);

// 3. Query specifica classe biennio Negrelli (1ITA)
r16 = ask("colloqui genitori 1ITA");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.ok(r16.a.lines.length > 0);
assert.ok(r16.a.lines.every((l) => l.sub.includes("03.12.26")));
console.log("✓ Colloqui 1ITA (Negrelli biennio):", r16.a.speech);

// 4. Agenda docente con solo triennio (Cassarino il 3 dicembre - biennio: solo lezioni, niente colloqui)
r16 = ask("cosa ho il 3 dicembre", "Cassarino");
assert.equal(r16.p.intent, "docente");
assert.ok(!r16.a.lines.some((l) => l.main && l.main.includes("Colloqui")), "Cassarino ha solo classi di triennio, non deve avere colloqui il 3 dicembre");
console.log("✓ Cassarino 3 dicembre (solo lezioni ordinarie, nessun colloquio biennio)");

// 5. Agenda docente con biennio (Basso il 3 dicembre - biennio: lezioni + colloqui orario personalizzato 14:00-15:30)
r16 = ask("cosa ho il 3 dicembre", "Basso");
assert.equal(r16.p.intent, "docente");
assert.ok(r16.a.badge.includes("AGENDA COMPLETA"));
assert.ok(r16.a.lines.some((l) => l.when === "Ore 14:00-15:30" && l.main.includes("Colloqui Generali • Negrelli (biennio)")));
console.log("✓ Basso 3 dicembre (Lezioni + Colloqui personalizzati biennio ore 14:00-15:30)");

// 6. Agenda docente triennio (Cassarino il 4 dicembre - triennio: lezioni + colloqui ore 14:30-17:30)
r16 = ask("cosa ho il 4 dicembre", "Cassarino");
assert.equal(r16.p.intent, "docente");
assert.ok(r16.a.badge.includes("AGENDA COMPLETA"));
assert.ok(r16.a.lines.some((l) => l.when === "Ore 14:30-17:30" && l.main.includes("Colloqui Generali • Negrelli (triennio)")));
console.log("✓ Cassarino 4 dicembre (Lezioni + Colloqui triennio ore 14:30-17:30)");

// 7. Agenda classe biennio (1ITA il 3 dicembre)
r16 = ask("1ITA il 3 dicembre");
assert.equal(r16.p.intent, "classe");
assert.ok(r16.a.badge.includes("AGENDA COMPLETA"));
assert.ok(r16.a.lines.some((l) => l.when === "Ore 14:30-17:30" && l.main.includes("Colloqui Generali • Negrelli (biennio)")));
console.log("✓ 1ITA 3 dicembre (Lezioni + Colloqui biennio ore 14:30-17:30)");

// 8. Agenda classe triennio (4ITA il 4 dicembre)
r16 = ask("4ITA il 4 dicembre");
assert.equal(r16.p.intent, "classe");
assert.ok(r16.a.badge.includes("AGENDA COMPLETA"));
assert.ok(r16.a.lines.some((l) => l.when === "Ore 14:30-17:30" && l.main.includes("Colloqui Generali • Negrelli (triennio)")));
console.log("✓ 4ITA 4 dicembre (Lezioni + Colloqui triennio ore 14:30-17:30)");

// 9. Query diretta docente self triennio ("quando ho i colloqui di dicembre")
r16 = ask("quando ho i colloqui di dicembre", "Cassarino");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.ok(r16.a.lines.some((l) => l.when.includes("04.12.26") && l.when.includes("Ore 14:30-17:30")));
assert.ok(!r16.a.lines.some((l) => l.when.includes("03.12.26")), "Cassarino non deve avere biennio");
assert.ok(r16.a.speech.includes("venerdì 4 dicembre") || r16.a.speech.includes("Venerdì 04.12.26"));
console.log("✓ Cassarino 'quando ho i colloqui di dicembre': profilato solo su venerdì 4 dicembre ore 14:30-17:30");

// 10. Query diretta docente self biennio+triennio ("quando ho i colloqui di dicembre" per Basso)
r16 = ask("quando ho i colloqui di dicembre", "Basso");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.ok(r16.a.lines.some((l) => l.when.includes("03.12.26") && l.when.includes("Ore 14:00-15:30")));
assert.ok(r16.a.lines.some((l) => l.when.includes("04.12.26") && l.when.includes("Ore 13:30-15:00")));
console.log("✓ Basso 'quando ho i colloqui di dicembre': orari personalizzati 14:00-15:30 e 13:30-15:00");

// 11. Orario colloqui docenti per una classe specifica ("colloqui 4ITA")
r16 = ask("colloqui 4ITA");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.equal(r16.a.title, "Colloqui Generali • Docenti 4ITA");
assert.equal(r16.a.lines.length, 13);
assert.ok(r16.a.lines.some((l) => l.main.includes("Boschello") && l.when === "Ore 14:00-17:00"));
assert.ok(r16.a.lines.some((l) => l.main.includes("Cassarino") && l.when === "Ore 14:30-17:30"));
assert.ok(r16.a.lines.some((l) => l.main.includes("Fantinel") && l.when === "Ore 14:30-16:30"));
console.log("✓ Colloqui 4ITA: elenco 13 docenti con orari individuali");

// 12. Query docente assente ai colloqui ("a che ora riceve Berlese ai colloqui?")
r16 = ask("a che ora riceve Berlese ai colloqui?");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.ok(r16.a.lines.some((l) => l.when.includes("ASSENTE")));
assert.ok(r16.a.speech.includes("assente giustificato"));
console.log("✓ Berlese ai colloqui: rilevato assente giustificato");

// 13. Query docente con orario standard non compilato ("a che ora riceve De Bacco ai colloqui?")
r16 = ask("a che ora riceve De Bacco ai colloqui?");
assert.equal(r16.p.intent, "attivita");
assert.equal(r16.p.subType, "colloqui");
assert.ok(r16.a.lines.some((l) => l.when.includes("Ore 14:30-17:30") && l.sub.includes("orario d'istituto")));
console.log("✓ De Bacco ai colloqui: applicato orario d'istituto 14:30-17:30");

console.log("\n TUTTI I TEST SONO PASSATI CON SUCCESSO! ");

