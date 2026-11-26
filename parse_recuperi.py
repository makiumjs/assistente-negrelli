#!/usr/bin/env python3
"""
parse_recuperi.py - Estrazione della tabella dei recuperi Q1/Q2
da data/Recuperi-30-Novembre.pdf (in vigore da lunedì 30 novembre 2026).
"""

import json
import os
import re
import pdfplumber

RECUPERI_PDF = os.path.join(os.path.dirname(__file__), "data", "Recuperi-30-Novembre.pdf")
OUT_JSON = os.path.join(os.path.dirname(__file__), "data", "recuperi_30_nov.json")
ORARIO_COMPLETO_PATH = os.path.join(os.path.dirname(__file__), "public", "data", "orario_completo.json")

DAYS_X = [
    ("lunedi", 56.0, 180.0),
    ("martedi", 180.0, 305.0),
    ("mercoledi", 305.0, 430.0),
    ("giovedi", 430.0, 555.0),
    ("venerdi", 555.0, 680.0),
    ("sabato", 680.0, 810.0),
]

HOURS_Y = [
    (1, 69.0, 147.2),
    (2, 147.2, 225.4),
    (3, 225.4, 303.6),
    (4, 303.6, 381.8),
    (5, 381.8, 460.0),
    (6, 460.0, 538.0),
]

ALIASES = {
    "dajnko (caligiuri)": "PLUTINO_CALIGIURI",
    "dajnko": "PLUTINO_CALIGIURI",
    "caligiuri": "PLUTINO_CALIGIURI",
    "foltran (lusuardi)": "FOLTRAN_LUSUARDI",
    "meneguz": "MENEGUZ_SCIENZE",
    "malè (curtolo)": "MALE_CURTOLO",
    "de bortoli": "DE_BORTOLI",
}


def parse_recuperi_pdf(pdf_path=None, orario_json_path=None):
    target_pdf = pdf_path or RECUPERI_PDF
    target_db = orario_json_path or ORARIO_COMPLETO_PATH

    docenti_db = {}
    if os.path.exists(target_db):
        with open(target_db, "r", encoding="utf-8") as f:
            docenti_db = json.load(f).get("docenti", {})

    recuperi = []
    per_docente = {}
    per_giorno = {d[0]: [] for d in DAYS_X}

    if os.path.exists(target_pdf):
        with pdfplumber.open(target_pdf) as pdf:
            p = pdf.pages[0]
            words = p.extract_words()

            for ora, y0, y1 in HOURS_Y:
                for giorno, x0, x1 in DAYS_X:
                    cell_words = [
                        w for w in words
                        if x0 <= w["x0"] < x1 and y0 <= w["top"] < y1 and w["text"] != "RECUPER"
                    ]
                    if not cell_words:
                        continue
                    mid_x = (x0 + x1) / 2
                    sub_groups = [
                        [w for w in cell_words if w["x0"] < mid_x],
                        [w for w in cell_words if w["x0"] >= mid_x],
                    ]
                    for sub_w in sub_groups:
                        if not sub_w:
                            continue
                        q_tag = "tutte"
                        names = []
                        for w in sub_w:
                            if w["text"] in ["Q1", "Q2"]:
                                q_tag = w["text"]
                            else:
                                names.append(w["text"])
                        if names:
                            raw_name = " ".join(names)
                            low = raw_name.lower()
                            doc_id = ALIASES.get(low)
                            if not doc_id:
                                for d_id, d_data in docenti_db.items():
                                    if d_data.get("nome", "").lower() == low or d_id.lower() == low:
                                        doc_id = d_id
                                        break
                                if not doc_id:
                                    doc_id = raw_name.upper().replace(" ", "_").replace("'", "")
                            doc_nome = docenti_db.get(doc_id, {}).get("nome", raw_name)
                            item = {
                                "docente_id": doc_id,
                                "docente_nome": doc_nome,
                                "giorno": giorno,
                                "ora": ora,
                                "settimana": q_tag,
                            }
                            recuperi.append(item)
                            per_docente.setdefault(doc_id, []).append({
                                "giorno": giorno,
                                "ora": ora,
                                "settimana": q_tag,
                            })
                            per_giorno[giorno].append({
                                "ora": ora,
                                "docente_id": doc_id,
                                "docente_nome": doc_nome,
                                "settimana": q_tag,
                            })

    return {
        "meta": {
            "documento": "RECUPER dal 30 novembre 2026",
            "in_vigore_dal": "2026-11-30",
            "in_vigore_label": "lunedì 30 novembre 2026",
            "fonte": "Index Education 2026",
        },
        "recuperi": recuperi,
        "per_docente": dict(sorted(per_docente.items())),
        "per_giorno": per_giorno,
    }


def main():
    data = parse_recuperi_pdf()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ Recuperi salvati in {OUT_JSON} ({len(data['recuperi'])} slot, {len(data['per_docente'])} docenti)")


if __name__ == "__main__":
    main()
