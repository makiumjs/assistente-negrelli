#!/usr/bin/env python3
"""
Esportatore CAD DWG e DXF Ufficiale per l'Istituto Tecnico Negrelli / Forcellini.
Estrae le geometrie architettoniche reali (pareti, pilastri, serramenti, arredi) 
direttamente dai blocchi CAD originali e vi applica i cartellini di Wayfinding 
aggiornati su layer strutturati e indipendenti.

Genera in dwg/:
- 0_Piano_Terra.dwg (.dxf)
- 1_Piano_Primo.dwg (.dxf)
- 2_Piano_Secondo.dwg (.dxf)
"""

import os
import json
import subprocess
import ezdxf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DWG_OUT_DIR = os.path.join(BASE_DIR, "dwg")
os.makedirs(DWG_OUT_DIR, exist_ok=True)

# Mappatura blocchi CAD originali estratti
FLOORS_CONFIG = [
    {
        "floor": 0,
        "name": "0_Piano_Terra",
        "dxf_src": "/tmp/test_0.dxf",
        "block_name": "FEL_VAR2_ARCH_002 - PARAMETRI GEOMETRICI - PIANTA PIANO TERRA",
        "bounds": {"xlim": (3.5, 44.5), "ylim": (0.5, 33.0)},
    },
    {
        "floor": 1,
        "name": "1_Piano_Primo",
        "dxf_src": "/tmp/test_1.dxf",
        "block_name": "FEL_VAR2_ARCH_003 - PARAMETRI GEOMETRICI - PIANTA PIANO PRIMO",
        "bounds": {"xlim": (3.5, 44.5), "ylim": (0.5, 33.0)},
    },
    {
        "floor": 2,
        "name": "2_Piano_Secondo",
        "dxf_src": "/tmp/test_2.dxf",
        "block_name": "FEL_VAR2_ARCH_004 - PARAMETRI GEOMETRICI - PIANTA PIANO SECONDO",
        "bounds": {"xlim": (3.5, 23.5), "ylim": (0.5, 23.5)},
    },
]


def export_floor_dwg(cfg, rooms_data):
    floor_num = cfg["floor"]
    fname = cfg["name"]
    dxf_src = cfg["dxf_src"]
    bname = cfg["block_name"]
    xlim = cfg["bounds"]["xlim"]
    ylim = cfg["bounds"]["ylim"]

    print(f"\n--- Elaborazione {fname} (Piano {floor_num}) ---")
    if not os.path.exists(dxf_src):
        # Genera il DXF da DWG originale se non presente
        src_dwg = f"/Users/mako/Downloads/mappe/{fname}.dwg"
        print(f"Conversione sorgente {src_dwg} in {dxf_src}...")
        subprocess.run(["dwg2dxf", src_dwg, "-o", dxf_src], check=True)

    src_doc = ezdxf.readfile(dxf_src)
    block = src_doc.blocks.get(bname)
    if not block:
        raise ValueError(f"Blocco {bname} non trovato in {dxf_src}")

    dst_doc = ezdxf.new("R2000")
    msp = dst_doc.modelspace()

    # Creazione Layer Standard AutoCAD
    dst_doc.layers.add("PARETI_STRUTTURE", color=7)      # Bianco / Nero in stampa
    dst_doc.layers.add("PILASTRI_SETTI", color=8)        # Grigio scuro / Sezione
    dst_doc.layers.add("INFISSI_VETRATE", color=4)       # Ciano
    dst_doc.layers.add("PORTE_SCALE", color=2)           # Giallo
    dst_doc.layers.add("ARREDI", color=9)                # Grigio medio (congelabile)
    dst_doc.layers.add("WAYFINDING_TESTI", color=7)      # Testo cartellino bianco/nero
    dst_doc.layers.add("WAYFINDING_RIQUADRI", color=7)   # Riquadro cartellino

    def in_bounds(x, y):
        return xlim[0] <= x <= xlim[1] and ylim[0] <= y <= ylim[1]

    stats = {"PARETI": 0, "PILASTRI": 0, "INFISSI": 0, "ARREDI": 0, "PORTE_SCALE": 0}

    for e in block:
        t = e.dxftype()
        c = e.dxf.color if e.dxf.hasattr("color") else 256

        if t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            if not pts or not any(in_bounds(p[0], p[1]) for p in pts):
                continue
            is_closed = bool(e.closed)
            if c == 9:
                layer = "ARREDI"
                stats["ARREDI"] += 1
            elif c == 254:
                layer = "INFISSI_VETRATE"
                stats["INFISSI"] += 1
            else:
                layer = "PARETI_STRUTTURE"
                stats["PARETI"] += 1
            msp.add_lwpolyline(pts, close=is_closed, dxfattribs={"layer": layer})

        elif t == "LINE":
            p1 = (e.dxf.start.x, e.dxf.start.y)
            p2 = (e.dxf.end.x, e.dxf.end.y)
            if not (in_bounds(p1[0], p1[1]) or in_bounds(p2[0], p2[1])):
                continue
            if c == 9:
                layer = "ARREDI"
                stats["ARREDI"] += 1
            elif c == 254:
                layer = "INFISSI_VETRATE"
                stats["INFISSI"] += 1
            else:
                layer = "PARETI_STRUTTURE"
                stats["PARETI"] += 1
            msp.add_line(p1, p2, dxfattribs={"layer": layer})

        elif t == "ARC":
            cp = (e.dxf.center.x, e.dxf.center.y)
            if not in_bounds(cp[0], cp[1]):
                continue
            layer = "ARREDI" if c == 9 else "PORTE_SCALE"
            stats["PORTE_SCALE" if c != 9 else "ARREDI"] += 1
            msp.add_arc(cp, e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle, dxfattribs={"layer": layer})

        elif t == "CIRCLE":
            cp = (e.dxf.center.x, e.dxf.center.y)
            if not in_bounds(cp[0], cp[1]):
                continue
            layer = "ARREDI" if c == 9 else "PARETI_STRUTTURE"
            stats["ARREDI" if c == 9 else "PARETI"] += 1
            msp.add_circle(cp, e.dxf.radius, dxfattribs={"layer": layer})

        elif t == "SOLID":
            c1 = (e.dxf.vtx0.x, e.dxf.vtx0.y)
            if not in_bounds(c1[0], c1[1]):
                continue
            c2 = (e.dxf.vtx1.x, e.dxf.vtx1.y)
            c3 = (e.dxf.vtx2.x, e.dxf.vtx2.y)
            c4 = (e.dxf.vtx3.x, e.dxf.vtx3.y) if e.dxf.hasattr("vtx3") else c3
            msp.add_solid([c1, c2, c3, c4], dxfattribs={"layer": "PILASTRI_SETTI"})
            stats["PILASTRI"] += 1

    # Aggiunta Cartellini Wayfinding (posizioni metriche 1:1)
    floor_rooms = [r for r in rooms_data if r["floor"] == floor_num]
    for r in floor_rooms:
        rx, ry = r["x"], r["y"]
        name = r["name"]
        sub = r.get("sub", "")
        text_content = f"{name}\\P{sub}" if sub else name

        char_h = 0.32 if floor_num < 2 else 0.28
        txt = msp.add_mtext(text_content, dxfattribs={
            "layer": "WAYFINDING_TESTI",
            "char_height": char_h,
            "attachment_point": 5,  # Centrato (Middle Center)
        })
        txt.set_location((rx, ry))

        # Riquadro perimetrale attorno alla label
        bw = max(1.1, len(name) * 0.20)
        bh = 0.75 if sub else 0.50
        box_pts = [
            (rx - bw / 2, ry - bh / 2),
            (rx + bw / 2, ry - bh / 2),
            (rx + bw / 2, ry + bh / 2),
            (rx - bw / 2, ry + bh / 2),
        ]
        msp.add_lwpolyline(box_pts, close=True, dxfattribs={"layer": "WAYFINDING_RIQUADRI"})

    dxf_out = os.path.join(DWG_OUT_DIR, f"{fname}.dxf")
    dwg_out = os.path.join(DWG_OUT_DIR, f"{fname}.dwg")

    dst_doc.saveas(dxf_out)
    subprocess.run(["dxf2dwg", "-y", "-v0", dxf_out, "-o", dwg_out], check=True)

    size_mb = os.path.getsize(dwg_out) / (1024 * 1024)
    print(f"✔ Generato con successo: {dwg_out} ({size_mb:.2f} MB)")
    print(f"  Entità salvate: {stats}, {len(floor_rooms)} label posizionate.")


def main():
    print("==================================================")
    print("Avvio esportazione DWG e DXF ufficiali con layer")
    print("==================================================")

    with open(os.path.join(BASE_DIR, "public", "data", "mappe.json"), "r", encoding="utf-8") as f:
        mdata = json.load(f)

    all_rooms = []
    for fl in mdata["floors"]:
        for r in fl["rooms"]:
            all_rooms.append(r)

    for cfg in FLOORS_CONFIG:
        export_floor_dwg(cfg, all_rooms)

    print("\n TUTTI I FILE DWG E DXF SONO STATI GENERATI IN:")
    print(f"  {DWG_OUT_DIR}")


if __name__ == "__main__":
    main()
