#!/usr/bin/env python3
"""
parse_sorveglianze.py - Estrazione dei turni di sorveglianza all'intervallo
da data/Sorveglianze-Novembre.pdf (in vigore da giovedì 19 novembre 2026,
Comunicato n. 167 del 18 novembre 2026).
"""

import json
import os
import re
import unicodedata
import pdfplumber

PDF_SORVEGLIANZE = os.path.join(os.path.dirname(__file__), "data", "Sorveglianze-Novembre.pdf")
OUT_JSON = os.path.join(os.path.dirname(__file__), "data", "sorveglianze.json")

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"]

ZONE_LABELS = {
    "scale lato bagni": "Scale lato bagni",
    "scale lato didattica": "Scale lato didattica",
    "mc mario": "MC Mario",
    "cortile ingresso": "Cortile ingresso",
    "piano terra": "Piano Terra",
    "piano primo": "1° Piano",
    "piano secondo": "2° Piano",
    "laboratori": "Laboratori",
}

TEACHER_CANON_MAP = {
    "d'incau": "D'Incau",
    "da rold": "Da Rold",
    "de bacco": "De Bacco",
    "de boni": "De Boni",
    "de min": "De Min",
    "de pellegrin": "De Pellegrin",
    "de pizzol": "De Pizzol",
    "schirò": "Schirò",
    "schiro": "Schirò",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def norm_teacher(raw):
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return ""
    low = s.lower()
    if low in TEACHER_CANON_MAP:
        return TEACHER_CANON_MAP[low]
    # Preserve apostrophes cleanly (e.g. D'Incau)
    return re.sub(r"(^|[\s'-])([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), low)


def norm_zone(raw):
    key = re.sub(r"\s+", " ", (raw or "").strip().lower())
    return ZONE_LABELS.get(key, key.title())


def parse_sorveglianze_pdf(pdf_path=None):
    target_path = pdf_path or PDF_SORVEGLIANZE
    turni = []  # lista piatta: [{ giorno, zona, docenti: [...] }]
    per_giorno = {g: [] for g in GIORNI}
    per_docente = {}

    if os.path.exists(target_path):
        with pdfplumber.open(target_path) as pdf:
            tables = pdf.pages[0].extract_tables()
            if tables:
                t = tables[0]
                # Trova riga intestazione giorni
                header_idx = None
                for i, row in enumerate(t):
                    joined = " ".join((c or "").lower() for c in row)
                    if "luned" in joined and "marted" in joined:
                        header_idx = i
                        break
                if header_idx is not None:
                    # Raggruppa per (giorno, zona) mantenendo ordine zone
                    zone_order = []
                    day_zone_docs = {g: {} for g in GIORNI}

                    for row in t[header_idx + 1:]:
                        if not row or not any(row):
                            continue
                        zona_raw = (row[0] or "").strip()
                        if not zona_raw:
                            continue
                        zona = norm_zone(zona_raw)
                        if zona not in zone_order:
                            zone_order.append(zona)

                        for col_i, g in enumerate(GIORNI):
                            val = (row[col_i + 1] or "").strip() if len(row) > col_i + 1 else ""
                            if not val:
                                continue
                            doc = norm_teacher(val)
                            day_zone_docs[g].setdefault(zona, [])
                            if doc not in day_zone_docs[g][zona]:
                                day_zone_docs[g][zona].append(doc)

                    for g in GIORNI:
                        for zona in zone_order:
                            docs = day_zone_docs[g].get(zona, [])
                            if docs:
                                entry = {"giorno": g, "zona": zona, "docenti": docs}
                                turni.append(entry)
                                per_giorno[g].append({"zona": zona, "docenti": docs})
                                for d in docs:
                                    per_docente.setdefault(d, []).append({"giorno": g, "zona": zona})

    return {
        "meta": {
            "comunicato": "Comunicato n. 167 del 18 novembre 2026",
            "in_vigore_dal": "2026-11-19",
            "in_vigore_label": "giovedì 19 novembre 2026",
            "intervallo": {
                "lunedi_mercoledi": {"orario": "10:25-10:35", "durata_min": 10},
                "giovedi_sabato": {"orario": "10:50-11:05", "durata_min": 15},
            },
            "nota_sostituzioni": "In caso di variazioni, comunicare la modifica all'Ufficio Tecnico dopo aver provveduto all'individuazione del sostituto.",
            "dirigente": "Manuela Muliner Biga",
        },
        "turni": turni,
        "per_giorno": per_giorno,
        "per_docente": dict(sorted(per_docente.items())),
    }


def main():
    data = parse_sorveglianze_pdf()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    total_slots = sum(len(v) for v in data["per_docente"].values())
    print(f"✓ Sorveglianze salvate in {OUT_JSON} ({len(data['per_docente'])} docenti, {total_slots} turni)")


if __name__ == "__main__":
    main()
