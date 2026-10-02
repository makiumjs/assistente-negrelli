import pdfplumber
import json
import re
import os

PDF_PATH = "orario.pdf"
OUTPUT_DIR = "public/data"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "orario.json")
DAYS = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"]

def parse_cell(cell_text):
    if not cell_text:
        return None
    clean = cell_text.strip()
    if not clean:
        return None

    if "DISPOSIZIONE" in clean.upper():
        aula = ""
        for l in clean.split("\n"):
            if any(k in l.lower() for k in ["aula", "lab", "spazio", "palestra", "rizzarda"]):
                aula = l.strip()
        return {"tipo": "disposizione", "aula": aula}

    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    if not lines:
        return None

    materia = lines[0]
    aula = ""
    classe = ""
    copresenza = ""

    for line in lines[1:]:
        lower = line.lower()
        if any(k in lower for k in ["aula", "lab", "spazio", "palestra", "rizzarda"]):
            aula = line
        elif re.search(r'\b[1-5]\s*([a-z]{2,3}|cat|bsa|bsb|mma|mmb|ita|itb|ee)\b', lower) or "[" in line:
            classe = line
        else:
            copresenza = line

    return {
        "tipo": "lezione",
        "materia": materia,
        "classe": classe,
        "aula": aula,
        "copresenza": copresenza
    }

def clean_teacher_name(raw_name):
    """Rimuove prefissi di pagina e pulisce caratteri duplicati residui."""
    name = re.sub(r"^(?:Pagina\s+\d+|[0-9]+)\s*", "", raw_name, flags=re.IGNORECASE).strip()
    # Se i caratteri sono ancora raddoppiati a coppie (es: 'SSsscchhiirròò')
    if len(name) >= 2 and all(name[i] == name[i+1] for i in range(0, len(name)-1, 2)):
        name = name[::2].strip()
    return name

def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    docenti = {}
    aule = {}

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 6,
        "join_tolerance": 6
    }

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            # 1. Rimuove i caratteri sovrapposti tipici del finto grassetto
            clean_page = page.dedupe_chars(tolerance=1)
            text = clean_page.extract_text() or ""

            # 2. Estrazione sicura dei nomi dei docenti nella pagina
            nomi = []
            for line in text.split("\n"):
                if "orario dal" in line.lower():
                    raw = re.split(r"orario dal", line, flags=re.IGNORECASE)[0]
                    nome_pulito = clean_teacher_name(raw)
                    if nome_pulito and nome_pulito not in nomi:
                        nomi.append(nome_pulito)

            # Fallback regex se dedupe_chars non cattura tutte le occorrenze
            if not nomi:
                raw_text = page.extract_text() or ""
                matches = re.findall(r"([A-Za-z0-9À-ÿ_\s\-']+?)\s*(?:O+r+a+r+i+o+|Orario)\s*(?:d+a+l+|dal)", raw_text, re.IGNORECASE)
                for m in matches:
                    nome_pulito = clean_teacher_name(m)
                    if nome_pulito and nome_pulito not in nomi:
                        nomi.append(nome_pulito)

            # 3. Estrazione tabelle con snap
            tables = clean_page.extract_tables(table_settings)

            for t_idx, table in enumerate(tables):
                if t_idx >= len(nomi):
                    break
                prof = nomi[t_idx]
                if not prof:
                    continue

                if prof not in docenti:
                    docenti[prof] = {d: {} for d in DAYS}

                # Escludiamo le righe d'intestazione (celle dove le colonne 1..6 sono tutte None)
                valid_rows = [
                    r for r in table 
                    if r and len(r) >= 7 and not all(c is None for c in r[1:7])
                ]

                # Mappatura delle ore (1..5) e dei giorni (colonne 1..6)
                for h_idx, row in enumerate(valid_rows, start=1):
                    if h_idx > 5:
                        break
                    
                    # Se la prima colonna contiene già il numero dell'ora usa quello, altrimenti usa h_idx
                    ora = row[0].strip() if (row[0] and row[0].strip().isdigit()) else str(h_idx)

                    for day_idx in range(6):
                        cell = row[day_idx + 1]
                        res = parse_cell(cell)
                        if res:
                            docenti[prof][DAYS[day_idx]][ora] = res

                            # Mappatura inversa per le aule
                            room = res.get("aula")
                            if room:
                                if room not in aule:
                                    aule[room] = []
                                aule[room].append({
                                    "docente": prof,
                                    "giorno": DAYS[day_idx],
                                    "ora": ora,
                                    "classe": res.get("classe"),
                                    "materia": res.get("materia"),
                                    "copresenza": res.get("copresenza")
                                })

    dataset = {
        "docenti": docenti,
        "aule": aule
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"Completato con successo! Estratti {len(docenti)} docenti e {len(aule)} aule/laboratori in {OUTPUT_JSON}")

if __name__ == "__main__":
    run()