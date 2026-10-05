import json
import os
import re
import pdfplumber

def find_pdf_path():
    candidates = [
        "piano attività.pdf",
        "piano attivita.pdf",
        os.path.join("data", "piano attività.pdf"),
        os.path.join("data", "piano attivita.pdf"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    for root, dirs, files in os.walk("."):
        for f in files:
            if "attivita" in f.lower() and f.endswith(".pdf"):
                return os.path.join(root, f)
    return "piano attività.pdf"

def norm_classe(raw):
    s = (raw or "").strip()
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()

def expand_classes(raw):
    """
    Estrae le classi individuali da stringhe come '3-4 CS', '4AFM-RIM', '1MMA', '5^ IAMI'.
    """
    raw_clean = re.sub(r"\^", "", raw or "").strip()
    
    # Gestione '3-4 CS' -> '3CS', '4CS'
    m_range = re.match(r"^([1-5])-([1-5])\s*([A-Za-z]+)$", raw_clean)
    if m_range:
        c1, c2, suffix = m_range.groups()
        return [f"{i}{suffix.upper()}" for i in range(int(c1), int(c2)+1)]
    
    # Gestione '4AFM-RIM' -> '4AFM', '4RIM'
    m_combo = re.match(r"^([1-5])([A-Z]+)-([A-Z]+)$", raw_clean, re.I)
    if m_combo:
        anno, s1, s2 = m_combo.groups()
        return [f"{anno}{s1}".upper(), f"{anno}{s2}".upper()]

    # Gestione '3BSB-AM' -> '3BSB', '3AM'
    m_combo2 = re.match(r"^([1-5])([A-Z]{3,4})-([A-Z]{2})$", raw_clean, re.I)
    if m_combo2:
        anno, s1, s2 = m_combo2.groups()
        return [f"{anno}{s1}".upper(), f"{anno}{s2}".upper()]

    c_norm = norm_classe(raw_clean)
    return [c_norm] if c_norm else []

def parse_page2_istituto(page):
    tables = page.extract_tables()
    if not tables:
        return []
    t = tables[0]
    items = []
    cur_item = None
    
    for row in t:
        if not row or not any(row):
            continue
        mese, data, attivita, orario, durata = [(c or "").strip() for c in (row + [""]*5)[:5]]
        
        if mese.lower() in ["mese", ""] and data.lower() in ["data", ""] and "attività" in attivita.lower():
            continue
        if "attività collegiali art." in mese.lower() or "istituto*" in mese.lower():
            continue

        if mese or data or orario or durata:
            if cur_item:
                items.append(cur_item)
            cur_item = {
                "mese": mese,
                "data": data,
                "attivita": attivita,
                "orario": orario or None,
                "durata": durata or None
            }
        else:
            if cur_item and attivita:
                cur_item["attivita"] += " " + attivita

    if cur_item:
        items.append(cur_item)

    # Fill empty 'mese' from previous row if needed
    last_mese = ""
    for it in items:
        if it["mese"]:
            last_mese = it["mese"]
        else:
            it["mese"] = last_mese

    return items

def parse_page3_sintesi(page):
    tables = page.extract_tables()
    if not tables:
        return []
    t = tables[0]
    items = []
    cur_item = None

    for row in t:
        if not row or not any(row):
            continue
        mese, data, attivita = [(c or "").strip() for c in (row + [""]*3)[:3]]

        if mese.lower() in ["mese", ""] and data.lower() in ["data", ""] and "attività" in attivita.lower():
            continue
        if "attività collegiali art." in mese.lower():
            continue

        if mese or data:
            if cur_item:
                items.append(cur_item)
            cur_item = {
                "mese": mese,
                "data": data,
                "attivita": attivita
            }
        else:
            if cur_item and attivita:
                cur_item["attivita"] += " " + attivita

    if cur_item:
        items.append(cur_item)

    last_mese = ""
    for it in items:
        if it["mese"]:
            last_mese = it["mese"]
        else:
            it["mese"] = last_mese

    return items

def parse_consigli_dettaglio(pdf):
    items = []
    
    for page_idx in range(3, 13):
        page = pdf.pages[page_idx]
        text = page.extract_text() or ""

        sezione = "Colotti"
        if "Negrelli" in text or "Forcellini" in text:
            sezione = "Negrelli"
        elif "Rizzarda" in text:
            sezione = "Rizzarda"

        periodo_match = re.search(r"(Ottobre|Novembre|Dicembre|Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno)\s+\d{4}(?::\s*Scrutini\s+.*)?", text, re.I)
        periodo = periodo_match.group(0) if periodo_match else ""

        tables = page.extract_tables()
        for t in tables:
            if not t or len(t) < 2:
                continue
            header = [str(c or "").strip() for c in t[0]]
            if "Giorno" not in header and "Ora" not in header and "Classe" not in header:
                continue

            cur_giorno = ""
            for row in t[1:]:
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                giorno_val = str(row[0] or "").strip() if len(row) > 0 else ""
                ora_val = str(row[1] or "").strip() if len(row) > 1 else ""
                classe_val = str(row[2] or "").strip() if len(row) > 2 else ""
                aula_val = str(row[3] or "").strip() if len(row) > 3 else ""

                if giorno_val and any(d in giorno_val for d in ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]):
                    cur_giorno = giorno_val

                if not classe_val or classe_val.lower() == "classe":
                    continue

                classi_target = expand_classes(classe_val)
                items.append({
                    "sezione": sezione,
                    "periodo": periodo,
                    "giorno": cur_giorno,
                    "ora": ora_val,
                    "classe_raw": classe_val,
                    "classi": classi_target,
                    "aula": aula_val
                })

    return items

def parse_colloqui(page):
    colloqui = [
        {"periodo": "I periodo", "giorno": "Martedì", "data": "01.12.26", "sede": "Colotti", "classi": "tutte"},
        {"periodo": "I periodo", "giorno": "Mercoledì", "data": "02.12.26", "sede": "Rizzarda", "classi": "tutte"},
        {"periodo": "I periodo", "giorno": "Giovedì", "data": "03.12.26", "sede": "Negrelli", "classi": "biennio"},
        {"periodo": "I periodo", "giorno": "Venerdì", "data": "04.12.26", "sede": "Negrelli", "classi": "triennio"},
        {"periodo": "II periodo", "giorno": "Lunedì", "data": "05.04.27", "sede": "Colotti", "classi": "tutte"},
        {"periodo": "II periodo", "giorno": "Martedì", "data": "06.04.27", "sede": "Negrelli", "classi": "triennio"},
        {"periodo": "II periodo", "giorno": "Mercoledì", "data": "07.04.27", "sede": "Negrelli", "classi": "biennio"},
        {"periodo": "II periodo", "giorno": "Giovedì", "data": "08.04.27", "sede": "Rizzarda", "classi": "tutte"}
    ]
    return colloqui

def parse_attivita_pdf(pdf_path=None):
    if not pdf_path:
        pdf_path = find_pdf_path()
    
    with pdfplumber.open(pdf_path) as pdf:
        istituto = parse_page2_istituto(pdf.pages[1])
        sintesi = parse_page3_sintesi(pdf.pages[2])
        consigli = parse_consigli_dettaglio(pdf)
        colloqui = parse_colloqui(pdf.pages[13])

    return {
        "attivita_istituto": istituto,
        "attivita_classe_sintesi": sintesi,
        "consigli_classe_dettaglio": consigli,
        "colloqui_generali": colloqui
    }

if __name__ == "__main__":
    data = parse_attivita_pdf()
    print("✓ Attività Istituto:", len(data["attivita_istituto"]))
    print("✓ Attività Classe Sintesi:", len(data["attivita_classe_sintesi"]))
    print("✓ Consigli Dettaglio:", len(data["consigli_classe_dettaglio"]))
    print("✓ Colloqui Generali:", len(data["colloqui_generali"]))
    
    # Save preview
    with open("data/piano_attivita.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✓ Saved data/piano_attivita.json")
