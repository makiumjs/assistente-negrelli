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
from parse_calendario import parse_calendario_pdf
from parse_glo import parse_glo_pdf
from parse_sorveglianze import parse_sorveglianze_pdf
from parse_colloqui_docenti import parse_colloqui_docenti
from parse_recuperi import parse_recuperi_pdf

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
    r"\b(aula|lab|spazio|palestra|rizzarda|colotti|atrio|l\s*chimica|l\.\s*biologia|cad|costr|disegno|fisica|sistemi)\b",
    re.I,
)

CLASSI_ARTICOLATE_MAP = {
    "1ITE": ("1EE", "1ITB"),
    "1MMC": ("1CAT", "1MMB"),
    "2MME": ("2EE", "2MMB"),
    "3BSAM": ("3AMB", "3BSB"),
    "3ITE": ("3EE", "3ITB"),
    "4BSAM": ("4AM", "4BS"),
    "4EEC": ("4CAT", "4EE"),
    "5BSAM": ("5AM", "5BS"),
    "5EEC": ("5CAT", "5EE"),
}


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
                h_crop = clean.crop(h_cell)
                h_big = h_crop.filter(lambda obj: obj.get("object_type") != "char" or obj.get("size", 0) >= 10)
                h_txt = h_big.extract_text() or h_crop.extract_text() or ""
                lines = [l.strip() for l in h_txt.split("\n") if "orario dal" in l.lower()]
                if not lines:
                    h_txt = h_crop.extract_text() or ""
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

                unique_cells = [
                    c for c in set(c for r in t.rows for c in r.cells if c)
                    if c[0] >= v_start - 5
                    and c[1] >= h_start - 5
                    and (c[2] - c[0]) >= 0.4 * v_step
                    and (c[3] - c[1]) >= 0.8 * h_step
                ]

                def encloses(a, b):
                    return (
                        a != b
                        and a[0] <= b[0] + 1
                        and a[1] <= b[1] + 1
                        and a[2] >= b[2] - 1
                        and a[3] >= b[3] - 1
                    )

                real_cells = [c for c in unique_cells if not any(encloses(c, b) for b in unique_cells)]

                grid = {g: {} for g in GIORNI}
                for cell in sorted(real_cells, key=lambda c: (c[1], c[0])):
                    x0, y0, x1, y1 = cell
                    cx = (x0 + x1) / 2.0
                    col_idx = int((cx - v_start) / v_step)
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
                upper = cell_text.upper()

                # 1) Ore di recupero (Q1 settimane dispari, Q2 settimane pari, oppure settimanale)
                if "RECUPER" in upper:
                    sett = "Q1" if re.search(r"\bQ1\b", upper) else ("Q2" if re.search(r"\bQ2\b", upper) else "tutte")
                    sched[giorno][ora] = {
                        "tipo": "recupero",
                        "settimana": sett,
                        "materia": "Recupero",
                        "aula": None,
                    }
                    continue

                # 2) Ore di disposizione / potenziamento
                is_disp = "DISPOSIZIONE" in upper or "POTENZIAMENTO" in upper
                if is_disp:
                    aula = ""
                    for l in cell_text.split("\n"):
                        if RE_AULA.search(l) or "POT-DISP" in l.upper():
                            aula = l.strip()
                    sched[giorno][ora] = {
                        "tipo": "disposizione",
                        "aula": norm_aula(aula) or "Aula Pot-Disp",
                    }
                    continue

                lines = [l.strip() for l in cell_text.split("\n") if l.strip()]
                if not lines:
                    continue

                # 3) Celle speciali mono-riga (Rizzarda, Colotti, Alfabet)
                if len(lines) == 1:
                    val = lines[0]
                    if re.fullmatch(r"rizzarda", val, re.I):
                        sched[giorno][ora] = {
                            "tipo": "lezione",
                            "materia": "Rizzarda",
                            "classi": [],
                            "aula": "Rizzarda",
                            "copresenza": [],
                        }
                        continue
                    if re.fullmatch(r"colotti", val, re.I):
                        sched[giorno][ora] = {
                            "tipo": "lezione",
                            "materia": "Colotti",
                            "classi": [],
                            "aula": "Colotti",
                            "copresenza": [],
                        }
                        continue
                    if re.fullmatch(r"alfabet", val, re.I):
                        sched[giorno][ora] = {
                            "tipo": "lezione",
                            "materia": "Alfabetizzazione",
                            "classi": [],
                            "aula": None,
                            "copresenza": [],
                        }
                        continue

                materia = lines[0]
                aule_found = []
                classi_found = []
                copresenze = []

                for l in lines[1:]:
                    if RE_AULA.search(l):
                        for part in l.split(","):
                            p_norm = norm_aula(part)
                            if p_norm and p_norm not in aule_found:
                                aule_found.append(p_norm)
                    elif re.search(r"\b[1-5]\s*[a-z]{2,4}\b", l, re.I):
                        classi_found = parse_classi_list(l)
                    else:
                        for part in l.split(","):
                            c_clean = clean_name(part)
                            if c_clean and c_clean not in copresenze:
                                copresenze.append(c_clean)

                sched[giorno][ora] = {
                    "tipo": "lezione",
                    "materia": materia,
                    "classi": classi_found,
                    "aula": ", ".join(aule_found) if aule_found else None,
                    "aule": aule_found,
                    "copresenza": copresenze,
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

    def canon(raw, materia=""):
        if clean_name(raw) == "Meneguz":
            return "Meneguz (Chimica)" if "chimica" in (materia or "").lower() else "Meneguz (Scienze)"
        k = compatto(raw)
        esatti = [n for n in reali if compatto(n) == k]
        if esatti:
            return esatti[0]
        # Match anche su nomi sostituiti tra parentesi es. "Curtolo" -> "Malè (Curtolo)"
        cand = [
            n for n in reali
            if k.startswith(compatto(n))
            or compatto(n).startswith(k)
            or (len(k) >= 4 and k in compatto(n))
        ]
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
                if s["tipo"] in ("disposizione", "recupero"):
                    continue
                total_slots += 1
                # Se un altro docente non anonimo insegna nella stessa classe/ora con la stessa materia
                for cls_name in s.get("classi", []):
                    for d_other, d_sched in docenti_raw.items():
                        if d_other != n and not RE_CODICE.match(d_other):
                            osl = d_sched.get(g, {}).get(ora)
                            if osl and osl.get("tipo") == "lezione":
                                if cls_name in osl.get("classi", []):
                                    voti[canon(d_other, osl.get("materia", ""))] += 1

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
    """
    Costruisce docenti e classi direttamente dall'orario docenti aggiornato (mod1a),
    ricostruendo poi le 9 classi articolate composite da CLASSI_ARTICOLATE_MAP
    così da evitare dati obsoleti dal vecchio Orario-Classi.pdf.
    """
    docenti_raw, canon = risolvi_docenti(classi_raw, docenti_raw, report)

    classi = {}
    docenti = {n: {g: {} for g in GIORNI} for n in docenti_raw}

    # 1) Elabora gli slot dei docenti e popola le classi individuali aggiornate
    for nome, sched in docenti_raw.items():
        for g, ore in sched.items():
            for ora, s in ore.items():
                if s["tipo"] == "recupero":
                    # I recuperi ufficiali vengono caricati da parse_recuperi_pdf()
                    continue

                if s["tipo"] == "disposizione":
                    docenti[nome][g][ora] = {
                        "tipo": "disposizione",
                        "aula": s.get("aula") or "Aula Pot-Disp",
                    }
                    continue

                materia_finale = s.get("materia")
                aula_finale = s.get("aula")
                raw_copr = s.get("copresenza") or []
                if isinstance(raw_copr, str):
                    raw_copr = [raw_copr]
                copresenze = []
                for c_name in raw_copr:
                    c_canon = canon(c_name, materia_finale)
                    if c_canon and c_canon != nome and c_canon not in copresenze:
                        copresenze.append(c_canon)

                classi_target = s.get("classi", [])
                if not classi_target:
                    docenti[nome][g][ora] = {
                        "tipo": "lezione",
                        "classe": None,
                        "materia": materia_finale,
                        "aula": aula_finale,
                        "copresenza": copresenze,
                        "fonte": "docenti",
                    }
                    continue

                prima_classe = classi_target[0]
                altre_classi = classi_target[1:]
                if altre_classi:
                    report["classi_articolate"].append(f"{nome} {g} ora {ora}: {prima_classe} + {altre_classi}")

                art_label = ",".join(f"[{c.lower()}]" for c in classi_target) if len(classi_target) > 1 else ""

                for cid in classi_target:
                    if cid not in classi:
                        classi[cid] = {gg: {} for gg in GIORNI}

                    cs = classi[cid][g].get(ora)
                    if cs is None:
                        docs_init = [nome] + [c for c in copresenze if c != nome]
                        classi[cid][g][ora] = {
                            "materia": materia_finale,
                            "docenti": docs_init,
                            "aula": aula_finale,
                            "articolazione": art_label,
                        }
                    else:
                        if nome not in cs["docenti"]:
                            cs["docenti"].append(nome)
                        for c_canon in copresenze:
                            if c_canon not in cs["docenti"]:
                                cs["docenti"].append(c_canon)
                        if not cs["aula"] and aula_finale:
                            cs["aula"] = aula_finale

                docenti[nome][g][ora] = {
                    "tipo": "lezione",
                    "classe": prima_classe,
                    "altre_classi": altre_classi,
                    "materia": materia_finale,
                    "aula": aula_finale,
                    "copresenza": copresenze,
                    "fonte": "docenti_mod1a",
                }

    # 2) Sintetizza le 9 classi articolate composite (1ITE, 1MMC, 2MME, 3BSAM, 3ITE, 4BSAM, 4EEC, 5BSAM, 5EEC)
    for parent_id, (sub1, sub2) in CLASSI_ARTICOLATE_MAP.items():
        if sub1 not in classi and sub2 not in classi:
            continue
        classi[parent_id] = {g: {} for g in GIORNI}
        for g in GIORNI:
            for ora in ORE_NUMS:
                s1 = classi.get(sub1, {}).get(g, {}).get(ora)
                s2 = classi.get(sub2, {}).get(g, {}).get(ora)
                if s1 and s2 and s1.get("materia") == s2.get("materia") and s1.get("aula") == s2.get("aula"):
                    docs_merged = list(s1["docenti"])
                    for d in s2["docenti"]:
                        if d not in docs_merged:
                            docs_merged.append(d)
                    classi[parent_id][g][ora] = {
                        "materia": s1["materia"],
                        "docenti": docs_merged,
                        "aula": s1["aula"],
                        "articolazione": f"[{sub1.lower()}],[{sub2.lower()}]",
                    }
                elif s1:
                    classi[parent_id][g][ora] = {
                        "materia": s1["materia"],
                        "docenti": list(s1["docenti"]),
                        "aula": s1["aula"],
                        "articolazione": f"[{sub1.lower()}]",
                    }
                elif s2:
                    classi[parent_id][g][ora] = {
                        "materia": s2["materia"],
                        "docenti": list(s2["docenti"]),
                        "aula": s2["aula"],
                        "articolazione": f"[{sub2.lower()}]",
                    }

    return classi, docenti


def split_rooms(aula_str):
    if not aula_str:
        return []
    return [norm_aula(part) for part in str(aula_str).split(",") if part.strip()]


def costruisci_aule(classi, docenti):
    """Costruisce la mappa di occupazione di tutte le aule e laboratori presenti."""
    occ = defaultdict(lambda: {g: {} for g in GIORNI})

    # Priorità alle classi composite per slot condivisi (es. 2MME), poi classi individuali
    ordered_cids = [cid for cid in CLASSI_ARTICOLATE_MAP if cid in classi] + [
        cid for cid in sorted(classi) if cid not in CLASSI_ARTICOLATE_MAP
    ]

    for cid in ordered_cids:
        sched = classi[cid]
        for g, ore in sched.items():
            for ora, cs in ore.items():
                for aula in split_rooms(cs.get("aula")):
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
                for aula in split_rooms(s.get("aula")):
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

    print(f"Lettura Orario Docenti (mod1a): {PDF_DOCENTI}")
    docenti_raw, periodo_doc = parse_docenti(report)
    classi_raw = {}

    periodo = "dal 30 novembre 2026 (mod1a • orario con recuperi dal 30/11/2026)"

    classi, docenti = riconcilia(classi_raw, docenti_raw, report)

    print("Lettura Recuperi Ufficiali Q1/Q2 (dal 30 novembre 2026)...")
    try:
        recuperi_data = parse_recuperi_pdf()
        count_rec = 0
        for r in recuperi_data.get("recuperi", []):
            d_id = r["docente_id"]
            matched_name = None
            for n in docenti:
                if persona_id(n) == d_id or n.lower() == r["docente_nome"].lower():
                    matched_name = n
                    break
            if matched_name:
                docenti[matched_name][r["giorno"]][str(r["ora"])] = {
                    "tipo": "recupero",
                    "settimana": r["settimana"],
                    "materia": "Recupero",
                    "aula": None,
                }
                count_rec += 1
        print(f"  ✓ Recuperi caricati: {count_rec} slot (in vigore dal 30 novembre 2026).")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare i Recuperi ({e})")

    aule = costruisci_aule(classi, docenti)
    libere = aule_libere(aule)

    print("Lettura Turni Sorveglianza (da 30 novembre 2026)...")
    try:
        sorveglianze = parse_sorveglianze_pdf()
        total_turni = sum(len(v) for v in sorveglianze.get("per_docente", {}).values())
        print(f"  ✓ Sorveglianze caricate: {len(sorveglianze.get('per_docente', {}))} docenti, {total_turni} turni settimanali.")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare le Sorveglianze ({e})")
        sorveglianze = {}

    print("Lettura Piano Attività PDF...")
    try:
        attivita = parse_attivita_pdf()
        print(f"  ✓ Attività caricate: {len(attivita.get('consigli_classe_dettaglio', []))} consigli di classe, {len(attivita.get('attivita_istituto', []))} attività istituto.")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare il Piano Attività ({e})")
        attivita = {}

    print("Lettura Calendario Scolastico PDF...")
    try:
        calendario = parse_calendario_pdf()
        print(f"  ✓ Calendario caricato: {len(calendario.get('vacanze', []))} periodi vacanze, {len(calendario.get('giorni_sospensione', {}))} giorni sospesi.")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare il Calendario Scolastico ({e})")
        calendario = {}

    print("Lettura Calendario GLO (Comunicato n. 83)...")
    try:
        glo = parse_glo_pdf()
        incontri_glo = glo.get("incontri", [])
        attivita["glo"] = incontri_glo
        print(f"  ✓ GLO caricati: {len(incontri_glo)} convocazioni PEI.")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare il Calendario GLO ({e})")
        glo = {}

    print("Lettura Orari Individuali Colloqui Docenti...")
    try:
        colloqui_docenti = parse_colloqui_docenti()
        print(f"  ✓ Orari colloqui caricati per {len(colloqui_docenti.get('per_docente', {}))} docenti.")
    except Exception as e:
        print(f"  ⚠ Avviso: impossibile caricare gli orari colloqui docenti ({e})")
        colloqui_docenti = {}

    dataset = {
        "meta": {
            "istituto": "ITIS Negrelli Feltre",
            "periodo": periodo,
            "ore": ORE_INFO,
            "scansione_oraria": SCANSIONE_ORARIA,
            "giorni": GIORNI,
            "nota_aule": "Copre aule, laboratori, palestra e spazi dell'istituto Negrelli.",
            "nota_sabato": "Il sabato le lezioni terminano alla 4ª ora (uscita ore 12:05).",
            "recuperi_info": {
                "comunicato": "Orario con recuperi dal 30 novembre 2026",
                "in_vigore_dal": "2026-11-30",
                "in_vigore_label": "lunedì 30 novembre 2026",
                "Q1": "Settimane con numero dispari del calendario",
                "Q2": "Settimane con numero pari del calendario",
                "intervallo_lun_mer": "10 minuti (10:25-10:35)",
                "intervallo_gio_sab": "15 minuti (10:50-11:05)",
            },
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
        "calendario": calendario,
        "glo": glo,
        "sorveglianze": sorveglianze,
        "colloqui_docenti": colloqui_docenti,
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
