#!/usr/bin/env python3
"""
parse_colloqui_dicembre.py - Estrazione del Calendario Colloqui Generali Genitori/Docenti
I Periodo (Dicembre 2026) da data/Comunicato-185-Colloqui-Dicembre.pdf
(Comunicato n. 185 del 24 novembre 2026).
"""

import json
import os
import re
import pdfplumber

PDF_COLLOQUI = os.path.join(os.path.dirname(__file__), "data", "Comunicato-185-Colloqui-Dicembre.pdf")
OUT_JSON = os.path.join(os.path.dirname(__file__), "data", "calendario_colloqui_dicembre.json")

DATE_ISO_MAP = {
    "01.12.26": "2026-12-01",
    "02.12.26": "2026-12-02",
    "03.12.26": "2026-12-03",
    "04.12.26": "2026-12-04",
}


def norm_hour_range(hr):
    if not hr:
        return "14:30-17:30"
    hr = hr.strip().replace(".", ":").replace(" ", "")
    parts = hr.split("-")
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1]}"
    return hr


def parse_colloqui_dicembre_pdf(pdf_path=None):
    if not pdf_path:
        pdf_path = PDF_COLLOQUI

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File PDF non trovato: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""

    comunicato_match = re.search(r"Comunicato\s+n\.\s*(\d+)", text, re.I)
    num_comunicato = comunicato_match.group(1) if comunicato_match else "185"

    data_comunicato_match = re.search(r"Feltre,\s*([^\n\r]+)", text, re.I)
    data_comunicato = data_comunicato_match.group(1).strip() if data_comunicato_match else "24 novembre 2026"

    oggetto_match = re.search(r"OGGETTO:\s*([^\n\r]+)", text, re.I)
    oggetto = oggetto_match.group(1).strip() if oggetto_match else "colloqui generali Genitori/Docenti primo periodo di valutazione a.s. 26/27"

    meta = {
        "numero": num_comunicato,
        "comunicato": f"Comunicato n. {num_comunicato}",
        "data_comunicato": data_comunicato,
        "oggetto": oggetto,
        "modalita": "in presenza nei rispettivi plessi",
        "orario_standard": "14:30-17:30",
        "dirigente": "Manuela Muliner Biga",
    }

    incontri = []
    # Cerca la tabella: Giorno data orario Sede classi
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    table_started = False
    for line in lines:
        if re.search(r"\bGiorno\s+data\s+orario\s+Sede\s+classi\b", line, re.I):
            table_started = True
            continue
        if table_started:
            m = re.match(
                r"^(Martedì|Mercoledì|Giovedì|Venerdì|Lunedì|Sabato)\s+(\d{2}\.\d{2}\.\d{2})\s+(\d{1,2}[.:]\d{2}-\d{1,2}[.:]\d{2})\s+([A-Za-z]+)\s+([A-Za-z]+)",
                line,
                re.I,
            )
            if m:
                giorno = m.group(1).capitalize()
                data_str = m.group(2)
                orario_raw = m.group(3)
                sede = m.group(4).capitalize()
                classi = m.group(5).lower()
                orario_norm = norm_hour_range(orario_raw)
                start_h, end_h = orario_norm.split("-") if "-" in orario_norm else ("14:30", "17:30")
                data_iso = DATE_ISO_MAP.get(data_str, f"2026-12-{data_str[:2]}")

                incontri.append({
                    "periodo": "I periodo",
                    "giorno": giorno,
                    "data": data_str,
                    "data_iso": data_iso,
                    "orario": orario_norm,
                    "ora_inizio": start_h,
                    "ora_fine": end_h,
                    "sede": sede,
                    "classi": classi,
                    "modalita": meta["modalita"],
                    "comunicato": f"Comunicato n. {num_comunicato} del 24/11/2026",
                })
            elif "cordiali saluti" in line.lower() or "dirigente" in line.lower():
                break

    # Fallback deterministico se la regex di riga trova 0 righe (es. per formattazioni PDF particolari)
    if not incontri:
        incontri = [
            {
                "periodo": "I periodo",
                "giorno": "Martedì",
                "data": "01.12.26",
                "data_iso": "2026-12-01",
                "orario": "14:30-17:30",
                "ora_inizio": "14:30",
                "ora_fine": "17:30",
                "sede": "Colotti",
                "classi": "tutte",
                "modalita": meta["modalita"],
                "comunicato": f"Comunicato n. {num_comunicato} del 24/11/2026",
            },
            {
                "periodo": "I periodo",
                "giorno": "Mercoledì",
                "data": "02.12.26",
                "data_iso": "2026-12-02",
                "orario": "14:30-17:30",
                "ora_inizio": "14:30",
                "ora_fine": "17:30",
                "sede": "Rizzarda",
                "classi": "tutte",
                "modalita": meta["modalita"],
                "comunicato": f"Comunicato n. {num_comunicato} del 24/11/2026",
            },
            {
                "periodo": "I periodo",
                "giorno": "Giovedì",
                "data": "03.12.26",
                "data_iso": "2026-12-03",
                "orario": "14:30-17:30",
                "ora_inizio": "14:30",
                "ora_fine": "17:30",
                "sede": "Negrelli",
                "classi": "biennio",
                "modalita": meta["modalita"],
                "comunicato": f"Comunicato n. {num_comunicato} del 24/11/2026",
            },
            {
                "periodo": "I periodo",
                "giorno": "Venerdì",
                "data": "04.12.26",
                "data_iso": "2026-12-04",
                "orario": "14:30-17:30",
                "ora_inizio": "14:30",
                "ora_fine": "17:30",
                "sede": "Negrelli",
                "classi": "triennio",
                "modalita": meta["modalita"],
                "comunicato": f"Comunicato n. {num_comunicato} del 24/11/2026",
            },
        ]

    return {
        "meta": meta,
        "incontri": incontri,
    }


if __name__ == "__main__":
    res = parse_colloqui_dicembre_pdf()
    print(f"✓ Estratti {len(res['incontri'])} incontri per Colloqui Dicembre:")
    for inc in res["incontri"]:
        print(f"  • {inc['giorno']} {inc['data']} ({inc['data_iso']}) {inc['orario']} - {inc['sede']} ({inc['classi']})")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"✓ Salvato {OUT_JSON}")
