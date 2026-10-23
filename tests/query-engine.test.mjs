import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { buildIndex, parseQuery, answer, resolveRoomLocation } from "../public/js/query-engine.js";

const db = JSON.parse(readFileSync(new URL("../public/data/orario_completo.json", import.meta.url)));
const idx = buildIndex(db);
const now = new Date("2026-10-07T10:00:00"); // mercoledì 7 ottobre 2026 ore 10:00
const ask = (t, me = "") => {
  const p = parseQuery(t, idx, { now, me });
  return { p, a: answer(p, idx) };
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
assert.equal(r.p.docente.nome, "Curtolo");
assert.equal(r.p.day, "giovedi");
console.log("✓ Curtolo domani:", r.a.speech);

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
console.log("✓ Cassarino lunedì (3ª-4ª ora 3ITA + 5ª disp):", r.a.speech);

r = ask("orario cattedra ele 4 lunedì");
assert.equal(r.p.intent, "docente");
assert.equal(r.p.docente.nome, "_ele 4");
assert.equal(r.p.day, "lunedi");
console.log("✓ Placeholder _ele 4:", r.a.speech);

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

console.log("\n TUTTI I TEST SONO PASSATI CON SUCCESSO! ");

