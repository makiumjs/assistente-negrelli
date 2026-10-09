import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { buildIndex, parseQuery, answer } from "../public/js/query-engine.js";

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

console.log("\n TUTTI I TEST SONO PASSATI CON SUCCESSO! ");
