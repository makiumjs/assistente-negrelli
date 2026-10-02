import pdfplumber
import re

PDF_PATH = "orario.pdf"

with pdfplumber.open(PDF_PATH) as pdf:
    p0 = pdf.pages[0]
    text = p0.extract_text() or ""
    
    print("=== 1. ANALISI ELEMENTI GRAFICI (PAGINA 1) ===")
    print(f"Segmenti linea (lines): {len(p0.lines)}")
    print(f"Rettangoli (rects): {len(p0.rects)}")
    print(f"Curve (curves): {len(p0.curves)}")

    print("\n=== 2. ANALISI NOMI DOCENTI ===")
    nomi = []
    for line in text.split("\n"):
        if "Orario dal" in line:
            nome = line.split("Orario dal")[0].strip()
            # Rimuove eventuali prefissi come numeri pagina
            nome = re.sub(r"^[0-9\s]+", "", nome)
            nomi.append(nome)
    print(f"Docenti rilevati su Pagina 1: {nomi}")

    print("\n=== 3. TEST STRATEGIE DI ESTRAZIONE TABELLA ===")
    
    # Test A: Default
    t_def = p0.extract_tables()
    print(f"Strategia Default: {len(t_def)} tabelle")

    # Test B: Bordi con Snap aumentato
    t_snap = p0.extract_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 6,
        "join_tolerance": 6
    })
    print(f"Strategia Lines + Snap: {len(t_snap)} tabelle")

    # Test C: Allineamento Testuale
    t_text = p0.extract_tables({
        "vertical_strategy": "text",
        "horizontal_strategy": "text"
    })
    print(f"Strategia Text: {len(t_text)} tabelle")

    if t_snap:
        print("\nAnteprima prima riga (Strategia Snap):")
        print(t_snap[0][:2])
    elif t_text:
        print("\nAnteprima prima riga (Strategia Text):")
        print(t_text[0][:2])
