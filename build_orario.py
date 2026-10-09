"""
Costruisce public/data/orario_completo.json incrociando:
  - data/Orario-Classi.pdf   (orario per classe: classi, materie, aule/lab)
  - data/Orario-Docenti.pdf  (orario per docente: docenti, disposizioni, compresenze)
Le incongruenze tra i due PDF NON vengono corrette in silenzio:
finiscono in data/report_anomalie.json.
"""
import json
import os
import re
import unicodedata
from collections import defaultdict

import pdfplumber
from parse_attivita import parse_attivita_pdf

def find_pdf_path(filename):
    candidates = [
        os.path.join("data", filename),
        filename,
        os.path.join(os.path.dirname(__file__), "data", filename),
        os.path.join(os.path.dirname(__file__), filename),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return os.path.join("data", filename)

PDF_CLASSI = find_pdf_path("Orario-Classi.pdf")
PDF_DOCENTI = find_pdf_path("Orario-Docenti.pdf")
OUT_JSON = "public/data/orario_completo.json"
OUT_REPORT = "data/report_anomalie.json"

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"]

ORE_INFO = [
    {"ora": 1, "inizio": "7:50"},
    {"ora": 2, "inizio": "8:40"},
    {"ora": 3, "inizio": "9:35"},
    {"ora": 4, "inizio": "10:35"},
    {"ora": 5, "inizio": "11:25"},
    {"ora": 6, "inizio": "12:15"},
]
ORE_NUMS = [o["ora"] for o in ORE_INFO]

SCANSIONE_ORARIA = {
    "lunedi_mercoledi": [
        {"ora": 1, "inizio": "7:50", "fine": "8:40", "durata": 50},
        {"ora": 2, "inizio": "8:40", "fine": "9:35", "durata": 55},
        {"ora": 3, "inizio": "9:35", "fine": "10:25", "durata": 50},
        {"pausa": "10:25-10:35", "durata": 10},
        {"ora": 4, "inizio": "10:35", "fine": "11:25", "durata": 50},
        {"ora": 5, "inizio": "11:25", "fine": "12:15", "durata": 50},
        {"ora": 6, "inizio": "12:15", "fine": "13:05", "durata": 50},
    ],
    "giovedi_venerdi": [
        {"ora": 1, "inizio": "7:50", "fine": "8:50", "durata": 60},
        {"ora": 2, "inizio": "8:50", "fine": "9:50", "durata": 60},
        {"ora": 3, "inizio": "9:50", "fine": "10:50", "durata": 60},
        {"pausa": "10:50-11:05", "durata": 15},
        {"ora": 4, "inizio": "11:05", "fine": "12:05", "durata": 60},
        {"ora": 5, "inizio": "12:05", "fine": "13:05", "durata": 60},
    ],
    "sabato": [
        {"ora": 1, "inizio": "7:50", "fine": "8:50", "durata": 60},
        {"ora": 2, "inizio": "8:50", "fine": "9:50", "durata": 60},
        {"ora": 3, "inizio": "9:50", "fine": "10:50", "durata": 60},
        {"pausa": "10:50-11:05", "durata": 15},
        {"ora": 4, "inizio": "11:05", "fine": "12:05", "durata": 60, "uscita": True},
    ],
}

TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 6,
    "join_tolerance": 6,
}

RE_AULA = re.compile(
    r"\b(aula|lab|spazio|palestra|rizzarda|l\s*chimica|l\.\s*biologia|cad|costr|disegno|fisica|sistemi)\b",
    re.I,
)


# ---------------------------------------------------------------- normalizzazione
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_giorno(label):
    w = strip_accents(label.strip().split()[0]).lower()
    return w if w in GIORNI else None


def norm_classe(raw):
    """'<1 ite> 1 ee' -> '1EE', '[4 ee]' -> '4EE', '3 bsa' -> '3BSA'."""
    s = re.sub(r"<[^>]*>", "", raw or "")
    s = re.sub(r"^\s*CLASSE\s+", "", s, flags=re.I)
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()


def parse_classi_list(raw):
    """Estrae tutte le classi da stringhe singole o articolate tipo '[4 cat],[4 ee]'."""
    matches = re.findall(r"[1-5]\s*[a-zA-Z]{2,4}", raw or "")
    if matches:
        return [norm_classe(m) for m in matches]
    single = norm_classe(raw)
    return [single] if single else []


def norm_persona(raw):
    """Chiave canonica per docenti."""
    s = strip_accents(raw or "").upper()
    return re.sub(r"[^A-Z0-9_ ]", "", s).strip()


def persona_id(raw):
    s = re.sub(r"\s+", "_", norm_persona(raw))
    return re.sub(r"_+", "_", s)


def norm_aula(raw):
    s = re.sub(r"\s+", " ", (raw or "").strip())
    # Normalizza spaziatura e capitalizzazione comune
    return s.title() if s else ""


def clean_name(raw):
    name = re.sub(r"^(?:Istituto Superiore Feltre - Negrelli|Pagina\s+\d+)\s*", "", raw or "", flags=re.I).strip()
    name = re.sub(r"^_\s+", "_", name)
    return name


# ---------------------------------------------------------------- estrazione
def extract_grid_tables(pdf_path):
    """
    Estrae le tabelle da ciascuna pagina calcolando giorno e ora
    dalle coordinate spaziali (bounding box) di ciascuna cella,
    supportando correttamente celle accorpate su blocchi di piu ore (es. ore doppie).
    Yields: (page_idx, header_raw, {giorno: {ora: cell_text}})
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            clean = page.dedupe_chars(tolerance=1)
            tables = clean.find_tables(TABLE_SETTINGS)
            for t in tables:
                if not t.rows or not t.rows[0].cells or not t.rows[0].cells[0]:
                    continue
                h_cell = t.rows[0].cells[0]
                h_txt = clean.crop(h_cell).extract_text() or ""
                lines = [l.strip() for l in h_txt.split("\n") if "orario dal" in l.lower()]
                if not lines:
                    continue
                header_raw = lines[0]

                # Coordinate spaziali dinamiche delle righe e delle colonne
                h_lines = sorted(set([round(c[1], 1) for r in t.rows for c in r.cells if c] + [round(c[3], 1) for r in t.rows for c in r.cells if c]))
                v_lines = sorted(set([round(c[0], 1) for r in t.rows for c in r.cells if c] + [round(c[2], 1) for r in t.rows for c in r.cells if c]))

                if len(h_lines) < 2 or len(v_lines) < 2:
                    continue

                h_start = h_lines[1]
                h_step = (h_lines[-1] - h_start) / 6.0
                v_start = v_lines[1]
                v_step = (v_lines[-1] - v_start) / 6.0

                unique_cells = set()
                for r in t.rows:
                    for c in r.cells:
                        if c:
                            unique_cells.add(c)

                grid = {g: {} for g in GIORNI}
                for cell in sorted(unique_cells, key=lambda c: (c[1], c[0])):
                    x0, y0, x1, y1 = cell
                    if x0 < v_start - 5:
                        continue  # colonna numeri ore
                    if y0 < h_start - 5:
                        continue  # riga di intestazione
                    col_idx = int(round((x0 - v_start) / v_step))
                    if not (0 <= col_idx < len(GIORNI)):
                        continue
                    giorno = GIORNI[col_idx]
                    ora_start = int(round((y0 - h_start) / h_step)) + 1
                    ora_end = int(round((y1 - h_start) / h_step))
                    ora_start = max(1, min(6, ora_start))
                    ora_end = max(1, min(6, ora_end))
                    if ora_start > ora_end:
                        continue

                    cell_text = clean.crop(cell).extract_text() or ""
                    cell_text = cell_text.strip()
                    if not cell_text:
                        continue

                    for o in range(ora_start, ora_end + 1):
                        grid[giorno][o] = cell_text

                yield page_idx, header_raw, grid


def parse_classi(report):
    """-> {classe: {giorno: {ora: slot}}}, periodo"""
    out = {}
    periodo = None

    for page_idx, header_raw, grid in extract_grid_tables(PDF_CLASSI):
        if periodo is None:
            m = re.search(r"orario\s+dal\s+(\d{1,2}\s+[a-z]+\s+\d{4})", header_raw, re.I)
            if m:
                periodo = f"dal {m.group(1)}"

        raw_name = re.split(r"orario dal", header_raw, flags=re.I)[0].strip()
        raw_name = re.sub(r"^(?:Istituto Superiore Feltre - Negrelli|Pagina\s+\d+)\s*", "", raw_name, flags=re.I).strip()
        classe = norm_classe(raw_name)
        if not classe:
            report["classi_tabelle_ignorate"].append(f"Pagina {page_idx}: nome classe nullo da '{header_raw}'")
            continue

        sched = out.setdefault(classe, {g: {} for g in GIORNI})

        for giorno, ore in grid.items():
            for ora, cell_text in ore.items():
                lines = [l.strip() for l in cell_text.split("\n") if l.strip()]
                if not lines:
                    continue

                materia = lines[0]
                aula = ""
                articolazione = ""
                docenti_cell = []

                for l in lines[1:]:
                    if RE_AULA.search(l):
                        aula = l
                    elif re.search(r"\[.*?\]", l):
                        articolazione = l
                    else:
                        docenti_cell.extend([d.strip() for d in l.split(",") if d.strip()])

                sched[giorno][ora] = {
                    "materia": materia,
                    "aula": norm_aula(aula) or None,
                    "articolazione": articolazione,
                    "docenti": docenti_cell,
                }

    return out, periodo


def parse_docenti(report):
    """-> {nome_docente: {giorno: {ora: slot}}}, periodo"""
    out = {}
    periodo = None

    for page_idx, header_raw, grid in extract_grid_tables(PDF_DOCENTI):
        if periodo is None:
            m = re.search(r"orario\s+dal\s+(\d{1,2}\s+[a-z]+\s+\d{4})", header_raw, re.I)
            if m:
                periodo = f"dal {m.group(1)}"

        raw_name = re.split(r"orario dal", header_raw, flags=re.I)[0].strip()
        raw_name = re.sub(r"^(?:Istituto Superiore Feltre - Negrelli|Pagina\s+\d+)\s*", "", raw_name, flags=re.I).strip()
        raw_name = re.sub(r"^_\s+", "_", raw_name)
        nome = clean_name(raw_name)
        if not nome:
            report["docenti_tabelle_ignorate"].append(f"Pagina {page_idx}: nome docente nullo da '{header_raw}'")
            continue

        if nome == "Meneguz":
            if any("chimica" in txt.lower() for ore in grid.values() for txt in ore.values()):
                nome = "Meneguz (Chimica)"
            else:
                nome = "Meneguz (Scienze)"

        sched = out.setdefault(nome, {g: {} for g in GIORNI})

        for giorno, ore in grid.items():
            for ora, cell_text in ore.items():
                is_disp = "DISPOSIZIONE" in cell_text.upper() or "POTENZIAMENTO" in cell_text.upper()
                if is_disp:
                    aula = ""
                    for l in cell_text.split("\n"):
                        if RE_AULA.search(l) or "POT-DISP" in l.upper():
                            aula = l.strip()
                    sched[giorno][ora] = {
                        "tipo": "disposizione",
                        "aula": norm_aula(aula) or None,
                    }
                    continue

                lines = [l.strip() for l in cell_text.split("\n") if l.strip()]
                if not lines:
                    continue

                materia = lines[0]
                aula = ""
                classi_found = []
                copresenza = ""

                for l in lines[1:]:
                    if RE_AULA.search(l):
                        aula = l
                    elif re.search(r"\b[1-5]\s*[a-z]{2,4}\b", l, re.I) or "[" in l:
                        classi_found = parse_classi_list(l)
                    else:
                        copresenza = l

                sched[giorno][ora] = {
                    "tipo": "lezione",
                    "materia": materia,
                    "classi": classi_found,
                    "aula": norm_aula(aula) or None,
                    "copresenza": clean_name(copresenza) if copresenza else None,
                }

    return out, periodo


# ---------------------------------------------------------------- riconciliazione
RE_CODICE = re.compile(r"^(_\s*[a-z0-9]+|[A-Z]\d{3})\b", re.I)


def compatto(n):
    return norm_persona(n).replace(" ", "").replace("_", "")


def risolvi_docenti(classi_raw, docenti_raw, report):
    """
    1) Corrispondenza nomi troncati/spaziati diversamente tra docenti e classi.
    2) Risoluzione codici cattedra anonimi tramite maggioranza >= 80% su slot classi corrispondenti.
    """
    reali = [n for n in docenti_raw if not RE_CODICE.match(n)]

    def canon(raw):
        k = compatto(raw)
        esatti = [n for n in reali if compatto(n) == k]
        if esatti:
            return esatti[0]
        cand = [n for n in reali if k.startswith(compatto(n)) or compatto(n).startswith(k)]
        if len(cand) == 1:
            return cand[0]
        if len(cand) > 1:
            report["nomi_ambigui"].append(f"{raw}: {cand}")
        return raw

    alias = {}
    for n, sched in docenti_raw.items():
        if not RE_CODICE.match(n):
            continue
        voti = defaultdict(int)
        total_slots = 0
        for g, ore in sched.items():
            for ora, s in ore.items():
                if s["tipo"] == "disposizione":
                    continue
                total_slots += 1
                # Se un altro docente non anonimo insegna nella stessa classe/ora con la stessa materia
                for cls_name in s.get("classi", []):
                    for d_other, d_sched in docenti_raw.items():
                        if d_other != n and not RE_CODICE.match(d_other):
                            osl = d_sched.get(g, {}).get(ora)
                            if osl and osl.get("tipo") == "lezione":
                                if cls_name in osl.get("classi", []):
                                    voti[canon(d_other)] += 1

        best = max(voti, key=voti.get) if voti else None
        # Risolvi come alias solo se la maggioranza copre almeno l'80% di TUTTI gli slot della cattedra
        if best and total_slots > 0 and (voti[best] / total_slots) >= 0.8:
            alias[n] = best
            report["alias_codici"].append(f"{n} -> {best} ({voti[best]}/{total_slots} slot)")
        else:
            report["codici_non_risolti"].append(f"{n}: {dict(voti)} (su {total_slots} slot)")

    uniti = {}
    for n, sched in docenti_raw.items():
        nome = alias.get(n, n)
        dst = uniti.setdefault(nome, {g: {} for g in GIORNI})
        for g, ore in sched.items():
            for ora, s in ore.items():
                if ora in dst[g]:
                    report["slot_duplicati_docente"].append(f"{nome} {g} ora {ora} (da {n})")
                dst[g][ora] = s

    return uniti, canon


def riconcilia(classi_raw, docenti_raw, report):
    docenti_raw, canon = risolvi_docenti(classi_raw, docenti_raw, report)

    classi = {}
    for cid, sched in classi_raw.items():
        classi[cid] = {g: {} for g in GIORNI}
        for g, ore in sched.items():
            for ora, s in ore.items():
                docenti_iniziali = []
                for d in s.get("docenti", []):
                    d_clean = clean_name(d)
                    if d_clean == "Meneguz":
                        d_clean = "Meneguz (Chimica)" if "chimica" in s["materia"].lower() else "Meneguz (Scienze)"
                    docenti_iniziali.append(canon(d_clean))
                classi[cid][g][ora] = {
                    "materia": s["materia"],
                    "docenti": docenti_iniziali,
                    "aula": s["aula"],
                    "articolazione": s.get("articolazione", ""),
                }

    docenti = {n: {g: {} for g in GIORNI} for n in docenti_raw}

    # 1) Elabora gli slot dei docenti e arricchiscili con i dati delle classi
    for nome, sched in docenti_raw.items():
        for g, ore in sched.items():
            for ora, s in ore.items():
                if s["tipo"] == "disposizione":
                    docenti[nome][g][ora] = {
                        "tipo": "disposizione",
                        "aula": s.get("aula"),
                    }
                    continue

                classi_target = s.get("classi", [])
                if not classi_target:
                    # Nessuna classe specificata nello slot
                    docenti[nome][g][ora] = {
                        "tipo": "lezione",
                        "classe": None,
                        "materia": s.get("materia"),
                        "aula": s.get("aula"),
                        "copresenza": [s["copresenza"]] if s.get("copresenza") else [],
                        "fonte": "docenti",
                    }
                    continue

                prima_classe = classi_target[0]
                altre_classi = classi_target[1:]
                if altre_classi:
                    report["classi_articolate"].append(f"{nome} {g} ora {ora}: {prima_classe} + {altre_classi}")

                # Collega il docente a ciascuna classe coinvolta
                materia_classe = None
                aula_classe = None

                for cid in classi_target:
                    if cid not in classi:
                        report["docenti_classe_inesistente"].append(f"{nome} {g} ora {ora}: {cid}")
                        classi[cid] = {gg: {} for gg in GIORNI}

                    cs = classi[cid][g].get(ora)
                    if cs is None:
                        report["docenti_slot_assente_in_classi"].append(f"{nome} {g} ora {ora}: {cid}")
                        classi[cid][g][ora] = {
                            "materia": s.get("materia"),
                            "docenti": [nome],
                            "aula": s.get("aula"),
                            "articolazione": "",
                        }
                    else:
                        if nome not in cs["docenti"]:
                            cs["docenti"].append(nome)
                        if s.get("copresenza"):
                            copr_canon = canon(s["copresenza"])
                            if copr_canon not in cs["docenti"]:
                                cs["docenti"].append(copr_canon)

                        if materia_classe is None:
                            materia_classe = cs["materia"]
                        if aula_classe is None and cs["aula"]:
                            aula_classe = cs["aula"]

                        if s.get("aula") and cs.get("aula") and s["aula"].lower() != cs["aula"].lower():
                            report["conflitti_aula"].append(
                                f"{nome} {g} ora {ora} {cid}: docenti='{s['aula']}' classi='{cs['aula']}'"
                            )

                aula_finale = aula_classe or s.get("aula")
                materia_finale = s.get("materia") or materia_classe
                copresenze = [s["copresenza"]] if s.get("copresenza") else []

                docenti[nome][g][ora] = {
                    "tipo": "lezione",
                    "classe": prima_classe,
                    "altre_classi": altre_classi,
                    "materia": materia_finale,
                    "aula": aula_finale,
                    "copresenza": copresenze,
                    "fonte": "docenti+classi",
                }

    # 2) Slot presenti nelle classi ma senza docenti assegnati
    for cid, sched in classi.items():
        for g, ore in sched.items():
            for ora, cs in ore.items():
                if not cs["docenti"]:
                    report["classi_slot_senza_docente"].append(f"{cid} {g} ora {ora} ({cs['materia']})")

    return classi, docenti


def costruisci_aule(classi, docenti):
    """Costruisce la mappa di occupazione di tutte le aule e laboratori presenti."""
    occ = defaultdict(lambda: {g: {} for g in GIORNI})

    # Da classi
    for cid, sched in classi.items():
        for g, ore in sched.items():
            for ora, cs in ore.items():
                aula = cs.get("aula")
                if not aula:
                    continue
                e = occ[aula][g].setdefault(
                    ora, {"classe": cid, "materia": cs.get("materia"), "docenti": []}
                )
                for d in cs.get("docenti", []):
                    if d not in e["docenti"]:
                        e["docenti"].append(d)

    # Da docenti (integrazione disposizioni con aula o lezioni con aula speciale)
    for nome, sched in docenti.items():
        for g, ore in sched.items():
            for ora, s in ore.items():
                aula = s.get("aula")
                if not aula:
                    continue
                e = occ[aula][g].setdefault(
                    ora,
                    {
                        "classe": s.get("classe") or "Disposizione",
                        "materia": s.get("materia") or "Disposizione",
                        "docenti": [],
                    },
                )
                if nome not in e["docenti"]:
                    e["docenti"].append(nome)

    return {a: occ[a] for a in sorted(occ)}


def aule_libere(aule):
    ore = ORE_NUMS
    return {g: {str(o): sorted(a for a in aule if o not in aule[a][g]) for o in ore} for g in GIORNI}


# ---------------------------------------------------------------- main
def run():
    keys = [
        "classi_tabelle_ignorate",
        "classi_slot_senza_docente",
        "docenti_tabelle_ignorate",
        "docenti_classe_inesistente",
        "docenti_slot_assente_in_classi",
        "conflitti_aula",
        "classi_articolate",
        "nomi_ambigui",
        "alias_codici",
        "codici_non_risolti",
        "slot_duplicati_docente",
    ]
    report = {k: [] for k in keys}

    print(f"Lettura Orario Classi: {PDF_CLASSI}")
    classi_raw, periodo_cls = parse_classi(report)
    print(f"Lettura Orario Docenti: {PDF_DOCENTI}")
    docenti_raw, periodo_doc = parse_docenti(report)

    periodo = periodo_doc or periodo_cls or "dal 12 ottobre 2026"

    classi, docenti = riconcilia(classi_raw, docenti_raw, report)
    aule = costruisci_aule(classi, docenti)
    libere = aule_libere(aule)

    print("Lettura Piano Attività PDF...")
    try:
        attivita = parse_attivita_pdf()
        print(f"  ✓ Attività caricate: {len(attivita.get('consigli_classe_dettaglio', []))} consigli di classe, {len(attivita.get('attivita_istituto', []))} attività istituto.")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare il Piano Attività ({e})")
        attivita = {}

    dataset = {
        "meta": {
            "istituto": "ITIS Negrelli Feltre",
            "periodo": periodo,
            "ore": ORE_INFO,
            "scansione_oraria": SCANSIONE_ORARIA,
            "giorni": GIORNI,
            "nota_aule": "Copre aule, laboratori, palestra e spazi dell'istituto Negrelli.",
            "nota_sabato": "Il sabato le lezioni terminano alla 4ª ora (uscita ore 12:05).",
        },
        "docenti": {
            persona_id(n): {
                "nome": n,
                "senza_nome": bool(RE_CODICE.match(n)),
                "orario": s,
            }
            for n, s in sorted(docenti.items())
        },
        "classi": dict(sorted(classi.items())),
        "aule": aule,
        "aule_libere": libere,
        "attivita": attivita,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_REPORT), exist_ok=True)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✓ SUCCESSO:")
    print(f"  Docenti riconciliati: {len(docenti)}")
    print(f"  Classi elaborate:     {len(classi)}")
    print(f"  Aule censite:         {len(aule)}")
    print(f"  Output dataset:       {OUT_JSON}")
    print(f"  Output anomalie:      {OUT_REPORT}")

    print("\nReport discrepanze:")
    for k, v in report.items():
        if v:
            print(f"  ⚠ {k}: {len(v)}")


if __name__ == "__main__":
    run()
