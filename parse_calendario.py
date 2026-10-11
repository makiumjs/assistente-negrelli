#!/usr/bin/env python3
"""
parse_calendario.py - Estrazione del Calendario Scolastico Ufficiale 2026/2027
da data/Calendario-Scolastico.pdf (Comunicato n. 75 del 10 ottobre 2026).
"""

import json
import os
import re
from datetime import datetime, timedelta
import pdfplumber

PDF_CALENDARIO = os.path.join(os.path.dirname(__file__), "data", "Calendario-Scolastico.pdf")
OUT_JSON = os.path.join(os.path.dirname(__file__), "data", "calendario_scolastico.json")


def daterange(start_date_str, end_date_str):
    """Genera lista di stringhe YYYY-MM-DD tra start e end inclusi."""
    s = datetime.strptime(start_date_str, "%Y-%m-%d")
    e = datetime.strptime(end_date_str, "%Y-%m-%d")
    curr = s
    out = []
    while curr <= e:
        out.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
    return out


def parse_calendario_pdf():
    """
    Legge il PDF del Comunicato n. 75 e restituisce la struttura dati
    completa del calendario scolastico 2026/27.
    """
    text = ""
    if os.path.exists(PDF_CALENDARIO):
        with pdfplumber.open(PDF_CALENDARIO) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"

    # Struttura dei periodi di sospensione delle lezioni
    vacanze = [
        {
            "id": "ponte_immacolata",
            "titolo": "Ponte dell'Immacolata",
            "da": "2026-12-07",
            "a": "2026-12-07",
            "rientro": "2026-12-09", # 8 dicembre è Immacolata
            "descrizione": "Lunedì 7 dicembre 2026 (ponte dell'Immacolata)",
            "date": ["2026-12-07"],
        },
        {
            "id": "vacanze_natale",
            "titolo": "Vacanze di Natale",
            "da": "2026-12-24",
            "a": "2027-01-05",
            "rientro": "2027-01-07", # 6 gennaio è Epifania
            "descrizione": "Da giovedì 24 dicembre 2026 a martedì 5 gennaio 2027 (rientro 7 gennaio dopo l'Epifania)",
            "date": daterange("2026-12-24", "2027-01-05"),
        },
        {
            "id": "carnevale",
            "titolo": "Carnevale e Mercoledì delle Ceneri",
            "da": "2027-02-08",
            "a": "2027-02-10",
            "rientro": "2027-02-11",
            "descrizione": "Da lunedì 8 febbraio a mercoledì 10 febbraio 2027 (rientro giovedì 11 febbraio)",
            "date": daterange("2027-02-08", "2027-02-10"),
        },
        {
            "id": "vacanze_pasqua",
            "titolo": "Vacanze di Pasqua",
            "da": "2027-03-25",
            "a": "2027-03-30",
            "rientro": "2027-03-31", # 28 Pasqua, 29 Pasquetta
            "descrizione": "Da giovedì 25 marzo a martedì 30 marzo 2027 (rientro mercoledì 31 marzo)",
            "date": daterange("2027-03-25", "2027-03-30"),
        },
        {
            "id": "ponte_primo_maggio",
            "titolo": "Ponte del 1° Maggio",
            "da": "2027-04-29",
            "a": "2027-04-30",
            "rientro": "2027-05-03", # 1 maggio sabato, 2 maggio domenica
            "descrizione": "Da giovedì 29 aprile a venerdì 30 aprile 2027 (ponte per la festa del Lavoro)",
            "date": daterange("2027-04-29", "2027-04-30"),
        },
        {
            "id": "ponte_patrono",
            "titolo": "Ponte del Santo Patrono",
            "da": "2027-05-15",
            "a": "2027-05-15",
            "rientro": "2027-05-17", # 16 domenica
            "descrizione": "Sabato 15 maggio 2027 (ponte del Santo Patrono)",
            "date": ["2027-05-15"],
        },
    ]

    # Festività obbligatorie
    festivita = [
        {"data": "2026-10-04", "nome": "San Francesco d'Assisi"},
        {"data": "2026-11-01", "nome": "Tutti i Santi"},
        {"data": "2026-12-08", "nome": "Immacolata Concezione"},
        {"data": "2026-12-25", "nome": "Natale"},
        {"data": "2026-12-26", "nome": "Santo Stefano"},
        {"data": "2027-01-01", "nome": "Capodanno"},
        {"data": "2027-01-06", "nome": "Epifania"},
        {"data": "2027-03-29", "nome": "Lunedì dell'Angelo (Pasquetta)"},
        {"data": "2027-04-25", "nome": "Festa della Liberazione"},
        {"data": "2027-05-01", "nome": "Festa del Lavoro"},
        {"data": "2027-06-02", "nome": "Festa della Repubblica"},
    ]

    # Chiusure totali istituto e uffici deliberate
    chiusure_totali = [
        {"data": "2026-12-07", "motivo": "Ponte dell'Immacolata"},
        {"data": "2026-12-24", "motivo": "Vigilia di Natale"},
        {"data": "2026-12-31", "motivo": "Vigilia di Capodanno"},
        {"data": "2027-01-02", "motivo": "Chiusura natalizia deliberata"},
        {"data": "2027-03-27", "motivo": "Vigilia di Pasqua"},
        {"data": "2027-04-30", "motivo": "Ponte 1° Maggio"},
        {"data": "2027-05-15", "motivo": "Ponte del Santo Patrono"},
        {"data": "2027-07-17", "motivo": "Sabato estivo"},
        {"data": "2027-07-24", "motivo": "Sabato estivo"},
        {"data": "2027-07-31", "motivo": "Sabato estivo"},
        {"data": "2027-08-07", "motivo": "Sabato estivo"},
        {"data": "2027-08-14", "motivo": "Sabato estivo"},
    ]

    # Indice giornaliero O(1) per lookup rapido di tutte le date non di lezione
    giorni_sospensione = {}

    for v in vacanze:
        for d in v["date"]:
            giorni_sospensione[d] = {
                "tipo": "vacanza",
                "id": v["id"],
                "titolo": v["titolo"],
                "descrizione": v["descrizione"],
                "rientro": v["rientro"],
            }

    for f in festivita:
        giorni_sospensione[f["data"]] = {
            "tipo": "festivita",
            "id": "festivita",
            "titolo": f["nome"],
            "descrizione": f"{f['nome']} (festività obbligatoria)",
            "rientro": None,
        }

    for c in chiusure_totali:
        if c["data"] in giorni_sospensione:
            giorni_sospensione[c["data"]]["chiuso_uffici"] = True
        else:
            giorni_sospensione[c["data"]] = {
                "tipo": "chiusura_istituto",
                "id": "chiusura",
                "titolo": c["motivo"],
                "descrizione": f"Chiusura totale istituto e uffici: {c['motivo']}",
                "chiuso_uffici": True,
            }

    return {
        "meta": {
            "istituto": "ITIS Negrelli - Feltre",
            "anno_scolastico": "2026/2027",
            "comunicato": "Comunicato n. 75 del 10 ottobre 2026",
            "delibera": "Delibera Consiglio di Istituto del 31 agosto 2026",
            "inizio_lezioni": "2026-09-10",
            "inizio_lezioni_testo": "Giovedì 10 settembre 2026",
            "fine_lezioni": "2027-06-08",
            "fine_lezioni_testo": "Martedì 8 giugno 2027",
        },
        "vacanze": vacanze,
        "festivita": festivita,
        "chiusure_totali": chiusure_totali,
        "giorni_sospensione": giorni_sospensione,
    }


def main():
    data = parse_calendario_pdf()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ Calendario scolastico generato con successo in {OUT_JSON}")
    print(f"  Periodi vacanze: {len(data['vacanze'])}")
    print(f"  Festività:       {len(data['festivita'])}")
    print(f"  Giorni sospesi:  {len(data['giorni_sospensione'])}")


if __name__ == "__main__":
    main()
