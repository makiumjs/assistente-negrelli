#!/usr/bin/env python3
"""
parse_colloqui_docenti.py - Parser degli orari individuali di ricevimento docenti
per i Colloqui Generali Negrelli (Dicembre 2026) da data/orari_docenti_colloqui_dicembre.csv.

Regola fornita dalla dirigenza/utente:
- I docenti che non hanno inserito orario specifico faranno l'orario ufficiale del PDF: 14:30-17:30.
- Chi ha indicato "ASSENTE" viene contrassegnato come assente giustificato.
- Le caselle "NON PREVISTO" / "—" indicano che il docente non ha classi in quel ciclo.
"""

import csv
import json
import os
import re
import unicodedata

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "orari_docenti_colloqui_dicembre.csv")
OUT_JSON = os.path.join(os.path.dirname(__file__), "data", "orari_docenti_colloqui_dicembre.json")
ORARIO_COMPLETO_PATH = os.path.join(os.path.dirname(__file__), "public", "data", "orario_completo.json")


def normalize_str(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def clean_time(t_str, default=""):
    if not t_str:
        return default
    t_str = t_str.strip()
    if not t_str or t_str in ["—", "-", "NON PREVISTO"]:
        return default
    if "assente" in t_str.lower():
        return "ASSENTE"
    # match hh:mm[:ss]
    m = re.match(r"^(\d{1,2})[.:](\d{2})(?:[.:]\d{2})?$", t_str)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return t_str


def parse_classes(cls_str):
    if not cls_str:
        return []
    cls_str = cls_str.strip()
    if cls_str in ["—", "-", "NON PREVISTO"]:
        return []
    parts = re.split(r"[,;]+", cls_str)
    classes = []
    for p in parts:
        p = re.sub(r"\s+", "", p).upper()
        if p and p not in ["—", "-"]:
            classes.append(p)
    return classes


def parse_colloqui_docenti(csv_path=None, orario_json_path=None):
    if not csv_path:
        csv_path = CSV_PATH
    if not orario_json_path:
        orario_json_path = ORARIO_COMPLETO_PATH

    with open(orario_json_path, "r", encoding="utf-8") as f:
        db = json.load(f)
    docenti_db = db.get("docenti", {})

    doc_map = {}
    for k, v in docenti_db.items():
        doc_map[normalize_str(k)] = k
        doc_map[normalize_str(v.get("nome", ""))] = k

    aliases = {
        normalize_str("Mulè (Curtolo) Matteo (Chiara)"): "MALE_CURTOLO",
        normalize_str("Malè (Curtolo)"): "MALE_CURTOLO",
        normalize_str("Meneguz Barbara"): "MENEGUZ_SCIENZE",
        normalize_str("Meneguz Nicolò"): "MENEGUZ_CHIMICA",
        normalize_str("Chiariello [Bucca (Di Mari)] Jacqueline"): "CHIARIELLO_BUCCA_DI_MARI",
        normalize_str("Foltran (Lusuardi) Damiano"): "FOLTRAN_LUSUARDI",
        normalize_str("Plutino (Caligiuri) Maria Rita"): "PLUTINO_CALIGIURI",
        normalize_str("De Bortoli Francesca"): "DE_BORTOLI",
        normalize_str("Debortoli Simone"): "DEBORTOLI",
    }

    per_docente = {}
    per_classe = {}

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Trova la riga di intestazione delle colonne
    data_rows = []
    header_found = False
    for row in rows:
        if not row or not any(row):
            continue
        if "Cognome e nome docente" in row[0]:
            header_found = True
            continue
        if header_found:
            data_rows.append(row)

    for row in data_rows:
        if not row or not row[0].strip():
            continue

        raw_name = row[0].strip()
        classi_biennio_raw = row[1].strip() if len(row) > 1 else ""
        ora_ini_b_raw = row[2].strip() if len(row) > 2 else ""
        ora_fine_b_raw = row[3].strip() if len(row) > 3 else ""

        classi_triennio_raw = row[4].strip() if len(row) > 4 else ""
        ora_ini_t_raw = row[5].strip() if len(row) > 5 else ""
        ora_fine_t_raw = row[6].strip() if len(row) > 6 else ""

        note_raw = row[7].strip() if len(row) > 7 else ""

        # Risolvi ID docente
        n_clean = normalize_str(raw_name)
        doc_id = aliases.get(n_clean)
        if not doc_id:
            for k_norm, k in doc_map.items():
                if n_clean.startswith(k_norm) or k_norm.startswith(n_clean) or normalize_str(raw_name.split()[0]) == k_norm:
                    doc_id = k
                    break

        doc_info = docenti_db.get(doc_id, {})
        nome_display = doc_info.get("nome", raw_name)

        # 1. BIENNIO (Giovedì 03.12.26)
        classi_b = parse_classes(classi_biennio_raw)
        non_previsto_b = "non previsto" in classi_biennio_raw.lower() or "non previsto" in ora_ini_b_raw.lower() or classi_biennio_raw == "—"
        assente_b = "assente" in ora_ini_b_raw.lower() or "assente" in ora_fine_b_raw.lower()

        biennio_info = {
            "attivo": not non_previsto_b and (bool(classi_b) or not assente_b),
            "data": "03.12.26",
            "data_iso": "2026-12-03",
            "giorno": "Giovedì",
            "sede": "Negrelli",
            "ciclo": "biennio",
            "classi": classi_b,
            "assente": assente_b,
            "non_previsto": non_previsto_b,
        }

        if non_previsto_b:
            biennio_info["attivo"] = False
            biennio_info["orario"] = "NON PREVISTO"
        elif assente_b:
            biennio_info["orario"] = "ASSENTE"
            biennio_info["ora_inizio"] = None
            biennio_info["ora_fine"] = None
            biennio_info["orario_default"] = False
        else:
            ini_b = clean_time(ora_ini_b_raw)
            fine_b = clean_time(ora_fine_b_raw)
            if ini_b and fine_b:
                biennio_info["ora_inizio"] = ini_b
                biennio_info["ora_fine"] = fine_b
                biennio_info["orario"] = f"{ini_b}-{fine_b}"
                biennio_info["orario_default"] = False
            elif ini_b and not fine_b:
                biennio_info["ora_inizio"] = ini_b
                biennio_info["ora_fine"] = "17:30"
                biennio_info["orario"] = f"{ini_b}-17:30"
                biennio_info["orario_default"] = False
            else:
                # Regola: chi non ha inserito orario fa l'orario ufficiale 14:30-17:30
                biennio_info["ora_inizio"] = "14:30"
                biennio_info["ora_fine"] = "17:30"
                biennio_info["orario"] = "14:30-17:30"
                biennio_info["orario_default"] = True

        # 2. TRIENNIO (Venerdì 04.12.26)
        classi_t = parse_classes(classi_triennio_raw)
        non_previsto_t = "non previsto" in classi_triennio_raw.lower() or "non previsto" in ora_ini_t_raw.lower() or classi_triennio_raw == "—"
        assente_t = "assente" in ora_ini_t_raw.lower() or "assente" in ora_fine_t_raw.lower()

        triennio_info = {
            "attivo": not non_previsto_t and (bool(classi_t) or not assente_t),
            "data": "04.12.26",
            "data_iso": "2026-12-04",
            "giorno": "Venerdì",
            "sede": "Negrelli",
            "ciclo": "triennio",
            "classi": classi_t,
            "assente": assente_t,
            "non_previsto": non_previsto_t,
        }

        if non_previsto_t:
            triennio_info["attivo"] = False
            triennio_info["orario"] = "NON PREVISTO"
        elif assente_t:
            triennio_info["orario"] = "ASSENTE"
            triennio_info["ora_inizio"] = None
            triennio_info["ora_fine"] = None
            triennio_info["orario_default"] = False
        else:
            ini_t = clean_time(ora_ini_t_raw)
            fine_t = clean_time(ora_fine_t_raw)
            if ini_t and fine_t:
                triennio_info["ora_inizio"] = ini_t
                triennio_info["ora_fine"] = fine_t
                triennio_info["orario"] = f"{ini_t}-{fine_t}"
                triennio_info["orario_default"] = False
            elif ini_t and not fine_t:
                triennio_info["ora_inizio"] = ini_t
                triennio_info["ora_fine"] = "17:30"
                triennio_info["orario"] = f"{ini_t}-17:30"
                triennio_info["orario_default"] = False
            else:
                triennio_info["ora_inizio"] = "14:30"
                triennio_info["ora_fine"] = "17:30"
                triennio_info["orario"] = "14:30-17:30"
                triennio_info["orario_default"] = True

        entry = {
            "docente_id": doc_id or normalize_str(raw_name).upper(),
            "docente_nome": nome_display,
            "nome_originale": raw_name,
            "biennio": biennio_info,
            "triennio": triennio_info,
            "note": note_raw,
        }

        dict_key = doc_id or normalize_str(raw_name).upper()
        per_docente[dict_key] = entry

        # Popola indice per classe
        for c in classi_b:
            per_classe.setdefault(c, []).append({
                "docente_id": dict_key,
                "docente_nome": nome_display,
                "ciclo": "biennio",
                "data": "03.12.26",
                "giorno": "Giovedì",
                "orario": biennio_info["orario"],
                "ora_inizio": biennio_info.get("ora_inizio"),
                "ora_fine": biennio_info.get("ora_fine"),
                "assente": biennio_info["assente"],
                "orario_default": biennio_info.get("orario_default", False),
                "note": note_raw,
            })

        for c in classi_t:
            per_classe.setdefault(c, []).append({
                "docente_id": dict_key,
                "docente_nome": nome_display,
                "ciclo": "triennio",
                "data": "04.12.26",
                "giorno": "Venerdì",
                "orario": triennio_info["orario"],
                "ora_inizio": triennio_info.get("ora_inizio"),
                "ora_fine": triennio_info.get("ora_fine"),
                "assente": triennio_info["assente"],
                "orario_default": triennio_info.get("orario_default", False),
                "note": note_raw,
            })

    # Ordina i docenti di ogni classe per cognome
    for c in per_classe:
        per_classe[c].sort(key=lambda x: x["docente_nome"])

    res = {
        "meta": {
            "descrizione": "Orari individuali di ricevimento docenti Colloqui Dicembre 2026 (Sede Negrelli)",
            "comunicato": "Comunicato n. 185 del 24/11/2026",
            "regola_orario_default": "Chi non ha inserito orario specifico effettua 14:30-17:30",
            "data_biennio": "03.12.26",
            "data_triennio": "04.12.26",
            "sede": "Negrelli",
        },
        "per_docente": per_docente,
        "per_classe": per_classe,
    }

    return res


if __name__ == "__main__":
    data = parse_colloqui_docenti()
    print(f"✓ Parsati orari per {len(data['per_docente'])} docenti Negrelli.")
    print(f"✓ Mappate {len(data['per_classe'])} classi.")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ Salvato {OUT_JSON}")
