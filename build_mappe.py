#!/usr/bin/env python3
"""
Generatore Cartellonistica Wayfinding Scolastica (300 DPI PNG + PDF Vettoriale)
Partendo dai file DWG decodificati (Piano Terra, Piano Primo, Piano Secondo)
e incrociando i dati reali di orario_completo.json (I.T.T. Negrelli - I.T.G. Forcellini).
"""

import json
import math
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection, PolyCollection
import matplotlib.patheffects as pe

# Configurazione Font per estetica pulita e leggibilità da distanza (Wayfinding)
plt.rcParams['font.sans-serif'] = ['Helvetica Neue', 'Avenir Next', 'Arial', 'DejaVu Sans']
plt.rcParams['axes.edgecolor'] = '#CBD5E1'
plt.rcParams['axes.linewidth'] = 0.8

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRATCH_DIR = os.path.join(BASE_DIR, "mappe_stampabili", ".scratch")
OUT_PROJECT_DIR = os.path.join(BASE_DIR, "mappe_stampabili")
OUT_DOWNLOAD_DIR = os.path.join(BASE_DIR, "mappe_stampabili")

os.makedirs(OUT_PROJECT_DIR, exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

# Formato Standard ISO 216 A3 Orizzontale (420 x 297 mm, 300 DPI = 4961 x 3508 px)
A3_INCHES = (420.0 / 25.4, 297.0 / 25.4)

# Palette Colori Semantica Wayfinding (WCAG AAA high-contrast per stampa)
CAT_STYLES = {
    "aula": {
        "bg": "#1D4ED8",       # Royal Blue
        "fill": "#EFF6FF",     # Soft Blue tint
        "border": "#1E40AF",
        "text": "#FFFFFF",
        "sub_bg": "#DBEAFE",
        "sub_text": "#1E3A8A",
        "label": "Aule Didattiche",
    },
    "lab": {
        "bg": "#6D28D9",       # Deep Violet
        "fill": "#F5F3FF",     # Soft Violet tint
        "border": "#5B21B6",
        "text": "#FFFFFF",
        "sub_bg": "#EDE9FE",
        "sub_text": "#4C1D95",
        "label": "Laboratori & Officina",
    },
    "informale": {
        "bg": "#047857",       # Emerald Green
        "fill": "#ECFDF5",
        "border": "#065F46",
        "text": "#FFFFFF",
        "sub_bg": "#D1FAE5",
        "sub_text": "#064E3B",
        "label": "Aule Informali & Biblioteca",
    },
    "comuni": {
        "bg": "#D97706",       # Warm Amber
        "fill": "#FFFBEB",
        "border": "#B45309",
        "text": "#FFFFFF",
        "sub_bg": "#FEF3C7",
        "sub_text": "#78350F",
        "label": "Palestra, Mensa & Bar",
    },
    "uffici": {
        "bg": "#BE123C",       # Crimson Rose
        "fill": "#FFF1F2",
        "border": "#9F1239",
        "text": "#FFFFFF",
        "sub_bg": "#FFE4E6",
        "sub_text": "#881337",
        "label": "Sala Docenti, Uffici & Infermeria",
    },
    "scale": {
        "bg": "#0F172A",       # Dark Slate
        "fill": "#F8FAFC",
        "border": "#334155",
        "text": "#FFFFFF",
        "sub_bg": "#E2E8F0",
        "sub_text": "#0F172A",
        "label": "Scale & Ascensore",
    },
    "wc": {
        "bg": "#0284C7",       # Sky Cyan
        "fill": "#F0F9FF",
        "border": "#0369A1",
        "text": "#FFFFFF",
        "sub_bg": "#E0F2FE",
        "sub_text": "#0C4A6E",
        "label": "Servizi Igienici (WC)",
    },
    "ingresso": {
        "bg": "#DC2626",       # Alert Red
        "fill": "#FEF2F2",
        "border": "#991B1B",
        "text": "#FFFFFF",
        "sub_bg": "#FEE2E2",
        "sub_text": "#7F1D1D",
        "label": "Ingressi / Voi Siete Qui",
    },
    "vuoto": {
        "bg": "#64748B",
        "fill": "#F1F5F9",
        "border": "#94A3B8",
        "text": "#FFFFFF",
        "sub_bg": "#F1F5F9",
        "sub_text": "#475569",
        "label": "Doppia Altezza (Piano Sottostante)",
    }
}

# Definizione curata e centrata di tutti gli ambienti per ciascun piano
# Coordinate (x, y) centrate geometricamente all'interno di ogni stanza
ROOMS_PIANO_TERRA = [
    # Ingressi
    {"code": "INGRESSO", "name": "INGRESSO PRINCIPALE", "sub": "", "x": 8.2, "y": 8.7, "cat": "ingresso", "size": "lg"},
    {"code": "037", "name": "ENTRATA PALESTRA", "sub": "", "x": 12.1, "y": 12.3, "cat": "ingresso", "size": "sm"},

    # Aule Didattiche Piano Terra (solo numero aula)
    {"code": "014", "name": "AULA 014", "sub": "", "x": 36.5, "y": 25.4, "cat": "aula", "size": "md"},
    {"code": "015", "name": "AULA 015", "sub": "", "x": 35.1, "y": 23.0, "cat": "aula", "size": "md"},
    {"code": "016", "name": "AULA 016", "sub": "", "x": 33.7, "y": 20.5, "cat": "aula", "size": "md"},
    {"code": "017", "name": "AULA 017", "sub": "", "x": 32.1, "y": 17.8, "cat": "aula", "size": "md"},
    {"code": "019", "name": "AULA 019", "sub": "", "x": 27.3, "y": 27.6, "cat": "aula", "size": "md"},
    {"code": "022", "name": "AULA 022", "sub": "", "x": 21.7, "y": 16.0, "cat": "aula", "size": "md"},

    # Laboratori & Officina Piano Terra
    {"code": "018", "name": "LAB. LINUX", "sub": "", "x": 33.1, "y": 26.8, "cat": "lab", "size": "md"},
    {"code": "020", "name": "LAB. MULTIMEDIALE", "sub": "", "x": 25.0, "y": 23.2, "cat": "lab", "size": "md"},
    {"code": "021", "name": "LAB. MULTIMEDIALE", "sub": "", "x": 23.4, "y": 20.4, "cat": "lab", "size": "md"},
    {"code": "024", "name": "LAB 1", "sub": "", "x": 41.1, "y": 11.4, "cat": "lab", "size": "md"},
    {"code": "025", "name": "LAB 2", "sub": "", "x": 35.8, "y": 11.5, "cat": "lab", "size": "md"},
    {"code": "026", "name": "OFFICINA", "sub": "", "x": 38.3, "y": 6.2, "cat": "lab", "size": "lg"},
    {"code": "031", "name": "LAB 4", "sub": "", "x": 26.0, "y": 25.3, "cat": "lab", "size": "sm"},

    # Biblioteca & Spazi Informali (058 e 059 uniti in unico label BIBLIOTECA)
    {"code": "058-059", "name": "BIBLIOTECA", "sub": "", "x": 26.2, "y": 15.8, "cat": "informale", "size": "lg"},
    {"code": "032", "name": "SPAZIO INFORMALE", "sub": "", "x": 31.5, "y": 24.6, "cat": "informale", "size": "sm"},
    {"code": "033", "name": "AGORÀ / STUDIO", "sub": "", "x": 28.0, "y": 19.3, "cat": "informale", "size": "md"},

    # Grandi Spazi Comuni & Sport (solo titoli)
    {"code": "004", "name": "PALESTRA", "sub": "", "x": 8.0, "y": 19.8, "cat": "comuni", "size": "lg"},
    {"code": "005-006", "name": "SPOGLIATOI", "sub": "", "x": 13.3, "y": 22.5, "cat": "comuni", "size": "sm"},
    {"code": "028", "name": "AULA INSEGNANTI", "sub": "", "x": 17.2, "y": 6.0, "cat": "uffici", "size": "lg"},
    {"code": "069", "name": "AREA RISTORO", "sub": "", "x": 18.5, "y": 9.4, "cat": "comuni", "size": "md"},

    # Sala Insegnanti, Uffici & Infermeria (Archivio eliminato)
    {"code": "060", "name": "VICEPRESIDENZA", "sub": "", "x": 29.5, "y": 12.8, "cat": "uffici", "size": "md"},
    {"code": "035", "name": "SEGRETERIA DIDATTICA", "sub": "", "x": 29.7, "y": 16.1, "cat": "uffici", "size": "md"},
    {"code": "009", "name": "INFERMERIA", "sub": "", "x": 13.0, "y": 16.6, "cat": "uffici", "size": "sm"},

    # Scale & Ascensore (tutte le scale rinominate in SCALA)
    {"code": "ASC", "name": "ASCENSORE", "sub": "", "x": 28.5, "y": 23.7, "cat": "scale", "size": "sm"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 29.5, "y": 21.1, "cat": "scale", "size": "xs"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 30.9, "y": 27.6, "cat": "scale", "size": "xs"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 32.2, "y": 15.2, "cat": "scale", "size": "xs"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 23.4, "y": 7.6, "cat": "scale", "size": "xs"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 38.5, "y": 12.3, "cat": "scale", "size": "xs"},

    # WC principali
    {"code": "WC", "name": "WC", "sub": "", "x": 28.8, "y": 30.2, "cat": "wc", "size": "xs"},
    {"code": "WC", "name": "WC", "sub": "", "x": 25.0, "y": 17.9, "cat": "wc", "size": "xs"},
    {"code": "WC", "name": "WC", "sub": "", "x": 20.9, "y": 8.2, "cat": "wc", "size": "xs"},
    {"code": "WC", "name": "WC", "sub": "", "x": 35.6, "y": 9.3, "cat": "wc", "size": "xs"},
]

ROOMS_PIANO_PRIMO = [
    # Aule Didattiche Piano Primo (solo numero aula)
    {"code": "110", "name": "AULA 110", "sub": "", "x": 36.5, "y": 25.4, "cat": "aula", "size": "md"},
    {"code": "111", "name": "AULA 111", "sub": "", "x": 35.1, "y": 23.0, "cat": "aula", "size": "md"},
    {"code": "112", "name": "AULA 112", "sub": "", "x": 33.7, "y": 20.5, "cat": "aula", "size": "md"},
    {"code": "113", "name": "AULA 113", "sub": "", "x": 32.1, "y": 17.8, "cat": "aula", "size": "md"},
    {"code": "114", "name": "AULA 114", "sub": "", "x": 30.1, "y": 14.3, "cat": "aula", "size": "md"},
    {"code": "115", "name": "AULA 115", "sub": "", "x": 28.6, "y": 11.8, "cat": "aula", "size": "md"},
    {"code": "119", "name": "AULA 119", "sub": "", "x": 33.1, "y": 26.8, "cat": "aula", "size": "md"},
    {"code": "134", "name": "AULA 134", "sub": "", "x": 21.7, "y": 16.0, "cat": "aula", "size": "md"},

    # Laboratori Piano Primo (senza codice in pianta)
    {"code": "116", "name": "LAB. CAD", "sub": "", "x": 23.4, "y": 20.4, "cat": "lab", "size": "md"},
    {"code": "117", "name": "LAB. AUTOMAZIONE", "sub": "", "x": 25.0, "y": 23.2, "cat": "lab", "size": "md"},
    {"code": "118", "name": "LAB. COSTRUZIONI", "sub": "", "x": 27.3, "y": 27.6, "cat": "lab", "size": "md"},
    {"code": "125", "name": "LAB. CHIMICA", "sub": "", "x": 40.8, "y": 10.8, "cat": "lab", "size": "lg"},
    {"code": "126", "name": "LAB. BIOLOGIA", "sub": "", "x": 35.5, "y": 11.4, "cat": "lab", "size": "md"},
    {"code": "129", "name": "LAB. DISEGNO", "sub": "", "x": 26.8, "y": 16.8, "cat": "lab", "size": "md"},
    {"code": "135", "name": "LAB. FISICA", "sub": "", "x": 24.5, "y": 13.5, "cat": "lab", "size": "md"},

    # Aule Informali
    {"code": "128", "name": "AULA INFORMALE 128", "sub": "", "x": 31.3, "y": 24.8, "cat": "informale", "size": "md"},
    {"code": "130", "name": "AULA INFORMALE 130", "sub": "", "x": 26.0, "y": 25.3, "cat": "informale", "size": "md"},
    {"code": "131", "name": "AULA INFORMALE 131", "sub": "", "x": 22.5, "y": 18.2, "cat": "informale", "size": "md"},
    {"code": "137", "name": "SPAZIO INFORMALE", "sub": "", "x": 26.8, "y": 21.8, "cat": "informale", "size": "sm"},

    # Uffici: unica label Dirigenza e Uffici (eliminata aula 107)
    {"code": "UFFICI", "name": "DIRIGENZA E UFFICI", "sub": "", "x": 18.2, "y": 9.2, "cat": "uffici", "size": "lg"},

    # Scale & Ascensore (senza codice né scala centrale)
    {"code": "ASC", "name": "ASCENSORE", "sub": "", "x": 28.4, "y": 23.7, "cat": "scale", "size": "sm"},
    {"code": "SCALA N", "name": "SCALA", "sub": "", "x": 30.9, "y": 27.6, "cat": "scale", "size": "xs"},
    {"code": "SCALA E", "name": "SCALA", "sub": "", "x": 32.0, "y": 15.5, "cat": "scale", "size": "xs"},
    {"code": "052", "name": "SCALA", "sub": "", "x": 21.7, "y": 8.7, "cat": "scale", "size": "xs"},
    {"code": "SCALA L", "name": "SCALA", "sub": "", "x": 38.6, "y": 12.2, "cat": "scale", "size": "xs"},

    # Servizi Igienici: WC Docenti e WC Alunni senza numero aula
    {"code": "WC", "name": "WC ALUNNI", "sub": "", "x": 28.8, "y": 30.2, "cat": "wc", "size": "sm"},
    {"code": "WC", "name": "WC DOCENTI", "sub": "", "x": 25.2, "y": 17.9, "cat": "wc", "size": "sm"},

    # Vuoti su Piano Terra (per orientamento visivo)
    {"code": "P.T.", "name": "VUOTO SU PALESTRA", "sub": "", "x": 8.0, "y": 19.8, "cat": "vuoto", "size": "sm"},
    {"code": "P.T.", "name": "VUOTO SU DOCENTI", "sub": "", "x": 16.5, "y": 5.5, "cat": "vuoto", "size": "sm"},
    {"code": "P.T.", "name": "VUOTO SU OFFICINA", "sub": "", "x": 38.3, "y": 6.2, "cat": "vuoto", "size": "sm"},
]

ROOMS_PIANO_SECONDO = [
    # Aule Didattiche Piano Secondo (solo numero aula)
    {"code": "201", "name": "AULA 201", "sub": "", "x": 20.0, "y": 16.3, "cat": "aula", "size": "md"},
    {"code": "202", "name": "AULA 202", "sub": "", "x": 18.6, "y": 13.9, "cat": "aula", "size": "md"},
    {"code": "203", "name": "AULA 203", "sub": "", "x": 17.2, "y": 11.3, "cat": "aula", "size": "md"},
    {"code": "204", "name": "AULA 204", "sub": "", "x": 13.6, "y": 5.1, "cat": "aula", "size": "md"},
    {"code": "205", "name": "AULA 205", "sub": "", "x": 12.1, "y": 2.6, "cat": "aula", "size": "md"},
    {"code": "209", "name": "AULA 209", "sub": "", "x": 15.6, "y": 8.6, "cat": "aula", "size": "md"},
    {"code": "224", "name": "AULA 224", "sub": "", "x": 5.2, "y": 6.8, "cat": "aula", "size": "md"},

    # Laboratori Piano Secondo (senza codici né sottotitoli)
    {"code": "206", "name": "LAB. INFORMATICA", "sub": "", "x": 6.9, "y": 11.2, "cat": "lab", "size": "md"},
    {"code": "207", "name": "LAB. INFORMATICA", "sub": "", "x": 8.4, "y": 14.0, "cat": "lab", "size": "md"},
    {"code": "208", "name": "LAB. ELETTRONICA", "sub": "", "x": 10.7, "y": 18.4, "cat": "lab", "size": "md"},
    {"code": "210", "name": "LAB. LINGUE", "sub": "", "x": 16.6, "y": 17.6, "cat": "lab", "size": "md"},
    {"code": "223", "name": "LAB. SISTEMI", "sub": "", "x": 8.1, "y": 5.2, "cat": "lab", "size": "lg"},

    # Aule & Spazi Informali (senza codici nei label; eliminato Spazio Studio 225)
    {"code": "213", "name": "AULA INFORMALE", "sub": "", "x": 6.0, "y": 9.0, "cat": "informale", "size": "md"},
    {"code": "214", "name": "SPAZIO LAB", "sub": "", "x": 9.5, "y": 16.1, "cat": "informale", "size": "sm"},
    {"code": "221", "name": "SPAZIO STUDIO", "sub": "", "x": 10.3, "y": 11.4, "cat": "informale", "size": "sm"},
    {"code": "211", "name": "SPAZIO INFORMALE", "sub": "", "x": 10.5, "y": 7.5, "cat": "informale", "size": "sm"},
    {"code": "212", "name": "SPAZIO INFORMALE", "sub": "", "x": 14.9, "y": 15.6, "cat": "informale", "size": "sm"},

    # Scale & Ascensore
    {"code": "ASC", "name": "ASCENSORE", "sub": "", "x": 12.0, "y": 14.6, "cat": "scale", "size": "sm"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 14.4, "y": 18.5, "cat": "scale", "size": "xs"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 15.5, "y": 6.4, "cat": "scale", "size": "xs"},
    {"code": "SCALA", "name": "SCALA", "sub": "", "x": 11.5, "y": 8.8, "cat": "scale", "size": "xs"},

    # Servizi Igienici: WC Alunni a Nord, WC Docenti a Sud (eliminato WC CENTRO)
    {"code": "WC", "name": "WC ALUNNI", "sub": "", "x": 12.6, "y": 20.8, "cat": "wc", "size": "sm"},
    {"code": "WC", "name": "WC DOCENTI", "sub": "", "x": 8.8, "y": 8.8, "cat": "wc", "size": "sm"},
]


def load_floor_geometry(json_filename, block_keyword, xlim, ylim):
    """Estrae linee strutturali, arredi, archi e riempimenti (HATCH/SOLID) dal blocco attivo."""
    path = os.path.join(SCRATCH_DIR, json_filename)
    if not os.path.exists(path):
        fallback_path = os.path.join("/Users/mako/.gemini/antigravity/brain/a2ec4232-6b56-4a72-bc35-76c95efd3b6e/scratch/mappe", json_filename)
        if os.path.exists(fallback_path):
            path = fallback_path
    with open(path) as f:
        data = json.load(f)
    objs = data["OBJECTS"]
    bh = [
        o for o in objs
        if (o.get("object") or o.get("entity")) == "BLOCK_HEADER"
        and block_keyword in o.get("name", "")
    ][0]
    bh_id = bh["handle"][-1]
    ents = [o for o in objs if o.get("ownerhandle", [0])[-1] == bh_id]

    walls_primary = []
    walls_glass = []
    furniture = []
    polys_fill = []

    def in_bounds(x, y):
        return (xlim[0] <= x <= xlim[1]) and (ylim[0] <= y <= ylim[1])

    for o in ents:
        et = o.get("entity")
        if et == "LWPOLYLINE":
            pts = o.get("points", [])
            if len(pts) < 2:
                continue
            # Filter out outer sheet frame & cartiglio
            if not any(in_bounds(p[0], p[1]) for p in pts):
                continue
            if max(p[0] for p in pts) - min(p[0] for p in pts) > 42:
                continue
            seg = [(p[0], p[1]) for p in pts]
            if o.get("flag", 0) & 512:
                seg.append(seg[0])
            c_idx = o.get("color", {}).get("index", 256)
            if c_idx == 9:
                continue  # Mobilio su colore CAD 9 isolato ed escluso

            if c_idx == 254:
                walls_glass.append(seg)
            else:
                walls_primary.append(seg)

        elif et == "ARC":
            c = o.get("center", [0, 0])
            r = o.get("radius", 0)
            if not in_bounds(c[0], c[1]) or r > 15:
                continue
            sa = o.get("start_angle", 0.0)
            ea = o.get("end_angle", 0.0)
            if ea < sa:
                ea += 2 * math.pi
            steps = max(12, int((ea - sa) * 16))
            seg = [
                (c[0] + r * math.cos(sa + (ea - sa) * i / steps),
                 c[1] + r * math.sin(sa + (ea - sa) * i / steps))
                for i in range(steps + 1)
            ]
            c_idx = o.get("color", {}).get("index", 256)
            if c_idx == 9:
                continue
            else:
                walls_primary.append(seg)

        elif et == "CIRCLE":
            c = o.get("center", [0, 0])
            r = o.get("radius", 0)
            if not in_bounds(c[0], c[1]) or r > 10:
                continue
            c_idx = o.get("color", {}).get("index", 256)
            if c_idx == 9:
                continue
            steps = 24
            seg = [
                (c[0] + r * math.cos(2 * math.pi * i / steps),
                 c[1] + r * math.sin(2 * math.pi * i / steps))
                for i in range(steps + 1)
            ]
            walls_primary.append(seg)

        elif et == "SOLID":
            c1 = o.get("corner1")
            c2 = o.get("corner2")
            c3 = o.get("corner3")
            c4 = o.get("corner4")
            if c1 and c2 and c3 and c4 and in_bounds(c1[0], c1[1]):
                polys_fill.append([(c1[0], c1[1]), (c2[0], c2[1]), (c4[0], c4[1]), (c3[0], c3[1])])

        elif et == "HATCH":
            for p in o.get("paths", []):
                pts = []
                for s in p.get("segs", []):
                    if "first_endpoint" in s:
                        pts.append((s["first_endpoint"][0], s["first_endpoint"][1]))
                if len(pts) >= 3 and in_bounds(pts[0][0], pts[0][1]):
                    polys_fill.append(pts)

    return {
        "walls_primary": walls_primary,
        "walls_glass": walls_glass,
        "furniture": furniture,
        "polys_fill": polys_fill,
    }


def draw_floor_on_ax(ax, geom, rooms, xlim, ylim, scale_factor=1.0):
    """Disegna la planimetria e i badge Wayfinding su un Axes matplotlib."""
    ax.set_facecolor("#FFFFFF")

    # 1. Arredi interni (banchi, sedie, campi da basket) in grigio chiarissimo
    if geom["furniture"]:
        ax.add_collection(
            LineCollection(geom["furniture"], colors="#CBD5E1", linewidths=0.45 * scale_factor, zorder=1)
        )

    # 2. Vetrate / serramenti in grigio-azzurro
    if geom["walls_glass"]:
        ax.add_collection(
            LineCollection(geom["walls_glass"], colors="#64748B", linewidths=0.6 * scale_factor, zorder=2)
        )

    # 3. Linee strutturali muri, porte e scale in blu-ardesia scuro ad alto contrasto
    if geom["walls_primary"]:
        ax.add_collection(
            LineCollection(geom["walls_primary"], colors="#0F172A", linewidths=0.85 * scale_factor, zorder=3)
        )

    # 4. Pilastri e riempimenti strutturali (HATCH/SOLID)
    if geom["polys_fill"]:
        ax.add_collection(
            PolyCollection(geom["polys_fill"], facecolors="#1E293B", edgecolors="none", zorder=4)
        )

    # 5. Disegno Alone morbido + Badge Wayfinding per ciascun ambiente
    for r in rooms:
        st = CAT_STYLES[r["cat"]]
        x, y = r["x"], r["y"]
        sz = r.get("size", "md")

        # Cerchi dietro ai label rimossi su richiesta dell'utente

        # Font sizes calibrati sulla gerarchia visiva
        fs_map = {
            "lg": (10.5 * scale_factor, 7.5 * scale_factor),
            "md": (8.0 * scale_factor, 6.0 * scale_factor),
            "sm": (6.6 * scale_factor, 5.2 * scale_factor),
            "xs": (5.6 * scale_factor, 4.5 * scale_factor),
        }
        fs_main, fs_sub = fs_map.get(sz, (8.0 * scale_factor, 6.0 * scale_factor))

        # Testo principale + sottotitolo in un unico blocco compatto ad altissima leggibilità
        label_text = r["name"]
        if r.get("sub") and scale_factor >= 0.75:
            label_text = f"{r['name']}\n{r['sub']}"
        elif r.get("sub") and sz in ("lg", "md"):
            label_text = f"{r['name']}\n{r['sub']}"

        bbox_props = dict(
            boxstyle="round,pad=0.28,rounding_size=0.35",
            facecolor="#FFFFFF",
            edgecolor="#000000" if r["cat"] != "vuoto" else "#94A3B8",
            linewidth=(1.4 if r["cat"] == "ingresso" else 1.0) * scale_factor,
            linestyle="--" if r["cat"] == "vuoto" else "-",
            alpha=1.0,
        )

        txt_color = "#000000"
        ax.text(
            x, y, label_text,
            fontsize=fs_main if "\n" not in label_text else fs_main * 0.92,
            fontweight="bold",
            color=txt_color,
            ha="center", va="center",
            linespacing=1.18,
            bbox=bbox_props,
            zorder=10 if r["cat"] != "ingresso" else 15,
        )

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def add_poster_header_and_legend(fig, floor_num, floor_title, floor_subtitle, rooms):
    """Aggiunge l'intestazione istituzionale, la legenda colori e l'elenco ordinato delle stanze a lato."""
    # Banner Superiore Istituzionale
    header_ax = fig.add_axes([0.02, 0.905, 0.96, 0.075])
    header_ax.set_facecolor("#0F172A")
    header_ax.set_xticks([])
    header_ax.set_yticks([])
    for s in header_ax.spines.values():
        s.set_visible(False)

    # Pill numero piano
    badge_colors = {0: "#1D4ED8", 1: "#6D28D9", 2: "#047857"}
    header_ax.text(
        0.015, 0.5, f" PIANO {floor_num} ",
        fontsize=14, fontweight="heavy", color="#FFFFFF",
        ha="left", va="center",
        bbox=dict(boxstyle="round,pad=0.32", facecolor=badge_colors.get(floor_num, "#1D4ED8"), edgecolor="none")
    )

    header_ax.text(
        0.125, 0.64, floor_title,
        fontsize=15, fontweight="heavy", color="#FFFFFF", ha="left", va="center"
    )
    header_ax.text(
        0.125, 0.26, floor_subtitle,
        fontsize=8.8, fontweight="normal", color="#94A3B8", ha="left", va="center"
    )
    header_ax.text(
        0.985, 0.62, "I.T.T. «L. NEGRELLI» • I.T.G. «E. FORCELLINI»",
        fontsize=10.5, fontweight="bold", color="#F8FAFC", ha="right", va="center"
    )
    header_ax.text(
        0.985, 0.26, "POLO SCOLASTICO DI FELTRE (BL) — MAPPA DI ORIENTAMENTO",
        fontsize=7.8, fontweight="normal", color="#38BDF8", ha="right", va="center"
    )

    # Legenda inferiore rimossa su richiesta dell'utente per massimizzare l'area della pianta CAD


def add_sidebar_directory(fig, floor_title, sections):
    """Disegna sulla destra del poster la rubrica rapida 'DOVE ANDARE', compatta e ridotta del 75%."""
    total_items = sum(len(items) for _, _, items in sections)
    num_secs = len(sections)
    # Box compatto ridotto del 75%: altezza calibrata sulle sole righe presenti
    calc_h = max(0.22, min(0.58, 0.05 + num_secs * 0.032 + total_items * 0.024))
    
    side_ax = fig.add_axes([0.842, 0.885 - calc_h, 0.142, calc_h])
    side_ax.set_facecolor("#F8FAFC")
    side_ax.set_xticks([])
    side_ax.set_yticks([])
    for s in side_ax.spines.values():
        s.set_color("#CBD5E1")
        s.set_linewidth(1.0)

    side_ax.text(
        0.5, 0.94, f"ELENCO — {floor_title}",
        fontsize=8.5, fontweight="heavy", color="#FFFFFF",
        ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#0F172A", edgecolor="none"),
        transform=side_ax.transAxes
    )

    y_step_item = 0.83 / max(1, (num_secs * 1.4 + total_items))
    y = 0.84
    for sec_title, sec_cat, items in sections:
        st = CAT_STYLES.get(sec_cat, CAT_STYLES["aula"])
        side_ax.add_patch(mpatches.Rectangle(
            (0.06, y - 0.007), 0.03, 0.015,
            facecolor=st["bg"], edgecolor="none", transform=side_ax.transAxes
        ))
        side_ax.text(
            0.12, y, sec_title.upper(),
            fontsize=7.2, fontweight="heavy", color=st["bg"],
            ha="left", va="center", transform=side_ax.transAxes
        )
        y -= y_step_item * 0.7

        for code_str, desc_str in items:
            side_ax.text(
                0.08, y, code_str,
                fontsize=6.8, fontweight="heavy", color="#0F172A",
                ha="left", va="center", transform=side_ax.transAxes
            )
            side_ax.text(
                0.28, y, desc_str,
                fontsize=6.8, fontweight="medium", color="#334155",
                ha="left", va="center", transform=side_ax.transAxes
            )
            y -= y_step_item
        y -= y_step_item * 0.4
        y -= 0.012


def save_both(fig, basename):
    """Salva sia in PNG 300 DPI che in PDF Vettoriale nelle due cartelle."""
    for folder in (OUT_PROJECT_DIR, OUT_DOWNLOAD_DIR):
        png_path = os.path.join(folder, f"{basename}.png")
        pdf_path = os.path.join(folder, f"{basename}.pdf")
        fig.savefig(png_path, dpi=300, facecolor="#FFFFFF")
        fig.savefig(pdf_path, facecolor="#FFFFFF")
    print(f"✔ Salvato {basename} (.png 300DPI + .pdf)")


def build_single_floor_posters():
    # 1. PIANO TERRA (Formato A3 420x297mm 300 DPI)
    geom_0 = load_floor_geometry("0_Piano_Terra.json", "TERRA", (4.2, 43.2), (1.0, 32.3))
    fig = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    map_ax = fig.add_axes([0.02, 0.02, 0.815, 0.868])
    draw_floor_on_ax(map_ax, geom_0, ROOMS_PIANO_TERRA, (4.2, 43.2), (1.0, 32.3), scale_factor=0.98)
    add_poster_header_and_legend(
        fig, 0,
        "PIANO TERRA — INGRESSO, AULE, LABORATORI, PALESTRA E MENSA",
        "Codici Locali 001 – 073  •  Aule 014–022  •  Lab. Linux (018), Multimediale (020-021), Lab 1-2, Officina (026)",
        ROOMS_PIANO_TERRA
    )
    sections_0 = [
        ("Aule Didattiche", "aula", [
            ("014", "Aula 014"),
            ("015", "Aula 015"),
            ("016", "Aula 016"),
            ("017", "Aula 017"),
            ("019", "Aula 019"),
            ("022", "Aula 022"),
        ]),
        ("Laboratori & Officina", "lab", [
            ("018", "Lab. Linux"),
            ("020-021", "Lab. Multimediale"),
            ("024-025", "Laboratori 1 e 2"),
            ("026", "Officina Meccanica"),
            ("031", "Lab. 4"),
        ]),
        ("Uffici, Docenti & Ristoro", "uffici", [
            ("028", "Aula Insegnanti"),
            ("060", "Vicepresidenza"),
            ("035", "Segreteria Didattica"),
            ("069", "Area Ristoro / Bar"),
            ("009", "Infermeria"),
        ]),
        ("Sport, Studio & Accessi", "comuni", [
            ("004", "Palestra"),
            ("005-006", "Spogliatoi"),
            ("058-059", "Biblioteca"),
            ("032-033", "Agorà Studio"),
            ("INGRESSO", "Ingresso Principale"),
            ("037", "Entrata Palestra"),
            ("SCALA", "Scale"),
        ]),
    ]
    add_sidebar_directory(fig, "PIANO TERRA", sections_0)
    save_both(fig, "0_Cartello_Piano_Terra")
    plt.close(fig)

    # 2. PIANO PRIMO (Formato A3 420x297mm 300 DPI)
    geom_1 = load_floor_geometry("1_Piano_Primo.json", "PRIMO", (4.2, 43.2), (1.0, 32.3))
    fig = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    map_ax = fig.add_axes([0.02, 0.02, 0.815, 0.868])
    draw_floor_on_ax(map_ax, geom_1, ROOMS_PIANO_PRIMO, (4.2, 43.2), (1.0, 32.3), scale_factor=0.98)
    add_poster_header_and_legend(
        fig, 1,
        "PIANO PRIMO — AULE 110–134, LABORATORI, DIRIGENZA E UFFICI",
        "Aule 110–134  •  Lab. CAD (116), Automazione (117), Costruzioni (118), Chimica (125), Biologia (126), Disegno (129), Fisica (135)",
        ROOMS_PIANO_PRIMO
    )
    sections_1 = [
        ("Aule Didattiche", "aula", [
            ("110", "Aula 110"),
            ("111", "Aula 111"),
            ("112", "Aula 112"),
            ("113", "Aula 113"),
            ("114", "Aula 114"),
            ("115", "Aula 115"),
            ("119", "Aula 119"),
            ("134", "Aula 134"),
        ]),
        ("Laboratori", "lab", [
            ("116", "Lab. CAD"),
            ("117", "Lab. Automazione"),
            ("118", "Lab. Costruzioni"),
            ("125", "Lab. Chimica"),
            ("126", "Lab. Biologia"),
            ("129", "Lab. Disegno"),
            ("135", "Lab. Fisica"),
        ]),
        ("Uffici", "uffici", [
            ("UFFICI", "Dirigenza e Uffici"),
        ]),
        ("Servizi Igienici", "wc", [
            ("WC", "WC Docenti"),
            ("WC", "WC Alunni"),
        ]),
    ]
    add_sidebar_directory(fig, "PIANO PRIMO", sections_1)
    save_both(fig, "1_Cartello_Piano_Primo")
    plt.close(fig)

    # 3. PIANO SECONDO (Formato A3 420x297mm 300 DPI)
    geom_2 = load_floor_geometry("2_Piano_Secondo.json", "SECONDO", (4.0, 22.8), (1.0, 22.9))
    fig = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    map_ax = fig.add_axes([0.02, 0.02, 0.815, 0.868])
    draw_floor_on_ax(map_ax, geom_2, ROOMS_PIANO_SECONDO, (4.0, 22.8), (1.0, 22.9), scale_factor=1.12)
    add_poster_header_and_legend(
        fig, 2,
        "PIANO SECONDO — AULE 201–224 E LABORATORI INFORMATICA / ELETTRONICA",
        "Codici Locali 201 – 227  •  Lab. Informatica (206-207), Elettronica (208), Lingue (210), Sistemi (223)",
        ROOMS_PIANO_SECONDO
    )
    sections_2 = [
        ("Aule Didattiche", "aula", [
            ("201", "Aula 201"),
            ("202", "Aula 202"),
            ("203", "Aula 203"),
            ("204", "Aula 204"),
            ("205", "Aula 205"),
            ("209", "Aula 209"),
            ("224", "Aula 224"),
        ]),
        ("Laboratori", "lab", [
            ("206-207", "Lab. Informatica"),
            ("208", "Lab. Elettronica"),
            ("210", "Lab. Lingue"),
            ("223", "Lab. Sistemi e Reti"),
        ]),
        ("Aule & Spazi Informali", "informale", [
            ("213", "Aula Informale"),
            ("214", "Spazio Lab"),
            ("221", "Spazio Studio"),
            ("211-212", "Spazi Informali"),
        ]),
        ("Servizi & Accessi", "scale", [
            ("WC", "WC Alunni"),
            ("WC", "WC Docenti"),
            ("SCALA", "Scale"),
            ("ASC", "Ascensore"),
        ]),
    ]
    add_sidebar_directory(fig, "PIANO SECONDO", sections_2)
    save_both(fig, "2_Cartello_Piano_Secondo")
    plt.close(fig)

    return geom_0, geom_1, geom_2


def build_master_entrance_board(geom_0, geom_1, geom_2):
    """
    Crea il Tabellone Generale da Ingresso (Formato Poster Panoramico A2/A1):
    - In alto: Le 3 planimetrie affiancate (Piano Terra, Piano Primo, Piano Secondo)
    - In basso: La Tabella Direzionale Completa (Tutte le Aule, tutti i Laboratori, Palestra/Mensa/Uffici)
      così chi entra trova qualsiasi codice stanza in meno di 3 secondi.
    """
    fig = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#F8FAFC")

    # 1. Header Principale
    h_ax = fig.add_axes([0.015, 0.915, 0.97, 0.072])
    h_ax.set_facecolor("#0F172A")
    h_ax.set_xticks([])
    h_ax.set_yticks([])
    for s in h_ax.spines.values():
        s.set_visible(False)

    h_ax.text(
        0.015, 0.52, " GUIDA GENERALE DELL'ISTITUTO — DOVE ANDARE ",
        fontsize=16, fontweight="heavy", color="#FFFFFF", ha="left", va="center",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#DC2626", edgecolor="none")
    )
    h_ax.text(
        0.38, 0.64, "I.T.T. «L. NEGRELLI»  •  I.T.G. «E. FORCELLINI» — POLO SCOLASTICO DI FELTRE",
        fontsize=13, fontweight="heavy", color="#FFFFFF", ha="left", va="center"
    )
    h_ax.text(
        0.38, 0.25, "REGOLA RAPIDA CODICI STANZA:   0xx = PIANO TERRA   •   1xx = PIANO PRIMO   •   2xx = PIANO SECONDO",
        fontsize=9.5, fontweight="bold", color="#38BDF8", ha="left", va="center"
    )

    # 2. Le 3 mappe affiancate nella fascia centrale (y: 0.36 -> 0.90)
    floors_cfg = [
        (0, "PIANO TERRA (Codici 001 – 073)", "#1D4ED8", geom_0, ROOMS_PIANO_TERRA, (4.2, 43.2), (1.0, 32.3), [0.015, 0.365, 0.34, 0.505], 0.52),
        (1, "PIANO PRIMO (Codici 101 – 139)", "#6D28D9", geom_1, ROOMS_PIANO_PRIMO, (4.2, 43.2), (1.0, 32.3), [0.365, 0.365, 0.34, 0.505], 0.52),
        (2, "PIANO SECONDO (Codici 201 – 227)", "#047857", geom_2, ROOMS_PIANO_SECONDO, (4.0, 22.8), (1.0, 22.9), [0.715, 0.365, 0.27, 0.505], 0.58),
    ]

    for f_num, f_title, f_col, geom, rooms, xlim, ylim, rect, sc in floors_cfg:
        # Titolo card piano
        t_ax = fig.add_axes([rect[0], rect[1] + rect[3], rect[2], 0.032])
        t_ax.set_facecolor(f_col)
        t_ax.set_xticks([])
        t_ax.set_yticks([])
        for s in t_ax.spines.values():
            s.set_visible(False)
        t_ax.text(0.5, 0.5, f_title, fontsize=10.5, fontweight="heavy", color="#FFFFFF", ha="center", va="center")

        ax = fig.add_axes(rect)
        draw_floor_on_ax(ax, geom, rooms, xlim, ylim, scale_factor=sc)
        ax.set_aspect("equal", adjustable="datalim")
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color(f_col)
            s.set_linewidth(1.5)

    # 3. Directory Tabellare Inferiore (y: 0.02 -> 0.345) divisa in 4 colonne tematiche
    cols_data = [
        ("1. TUTTE LE AULE DIDATTICHE", "#1D4ED8", [
            ("Aula 014", "PIANO TERRA", ""),
            ("Aula 015", "PIANO TERRA", ""),
            ("Aula 016", "PIANO TERRA", ""),
            ("Aula 017", "PIANO TERRA", ""),
            ("Aula 019", "PIANO TERRA", ""),
            ("Aula 022", "PIANO TERRA", ""),
            ("Aula 110", "PIANO PRIMO", ""),
            ("Aula 111", "PIANO PRIMO", ""),
            ("Aula 112", "PIANO PRIMO", ""),
            ("Aula 113", "PIANO PRIMO", ""),
            ("Aula 114", "PIANO PRIMO", ""),
            ("Aula 115", "PIANO PRIMO", ""),
            ("Aula 119", "PIANO PRIMO", ""),
            ("Aula 134", "PIANO PRIMO", ""),
        ]),
        ("2. AULE 2° PIANO & INFORMALI", "#047857", [
            ("Aula 201", "PIANO SECONDO", ""),
            ("Aula 202", "PIANO SECONDO", ""),
            ("Aula 203", "PIANO SECONDO", ""),
            ("Aula 204", "PIANO SECONDO", ""),
            ("Aula 205", "PIANO SECONDO", ""),
            ("Aula 209", "PIANO SECONDO", ""),
            ("Aula 224", "PIANO SECONDO", ""),
            ("Informale 128", "PIANO PRIMO", ""),
            ("Informale 130", "PIANO PRIMO", ""),
            ("Informale 131", "PIANO PRIMO", ""),
            ("Informale 213", "PIANO SECONDO", ""),
            ("Spazi Studio", "TUTTI I PIANI", "032-033 / 137 / 211-212"),
            ("Biblioteca", "PIANO TERRA", "Locali 058 – 059"),
        ]),
        ("3. LABORATORI & OFFICINA", "#6D28D9", [
            ("Lab. Linux 018", "PIANO TERRA", "Locale 018"),
            ("Lab. Multimediale", "PIANO TERRA", "Locali 020 – 021"),
            ("Lab 1 & Lab 2", "PIANO TERRA", "Locali 024 – 025"),
            ("Officina Meccanica", "PIANO TERRA", "Locale 026"),
            ("Lab 4 & Lab 5", "PIANO TERRA", "Locali 030, 031"),
            ("Lab. CAD-Automaz.", "PIANO PRIMO", "Locali 116 – 117"),
            ("Lab. Costruzioni", "PIANO PRIMO", "Locale 118"),
            ("Lab. Chimica", "PIANO PRIMO", "Locale 125"),
            ("Lab. Biologia", "PIANO PRIMO", "Locale 126"),
            ("Lab. Disegno", "PIANO PRIMO", "Locale 129"),
            ("Lab. Fisica", "PIANO PRIMO", "Locale 135"),
            ("Lab. Informatica", "PIANO SECONDO", "Locali 206 – 207"),
            ("Lab. Elettronica", "PIANO SECONDO", "Locale 208"),
            ("Lab. Lingue", "PIANO SECONDO", "Locale 210"),
            ("Lab. Sistemi", "PIANO SECONDO", "Locale 223"),
        ]),
        ("4. SERVIZI, UFFICI, SPORT E RISTORO", "#BE123C", [
            ("Ingresso / Atrio", "PIANO TERRA", "Locali 029 / 036"),
            ("Sala Insegnanti", "PIANO TERRA", "Locale 060"),
            ("Uffici Accoglienza", "PIANO TERRA", "Locale 035"),
            ("Dirigenza e Uffici", "PIANO PRIMO", "Locali 104, 105, 106, 138"),
            ("Palestra", "PIANO TERRA", "Locale 004"),
            ("Spogliatoi Palestra", "PIANO TERRA", "Locali 005, 006, 008"),
            ("Infermeria", "PIANO TERRA", "Locale 009"),
            ("Caffetteria / Bar", "PIANO TERRA", "Locale 069"),
            ("Aula Insegnanti (028)", "PIANO TERRA", "Locale 028"),
            ("Ascensore", "TUTTI I PIANI", "Centro Edificio"),
            ("WC Docenti e Alunni", "TUTTI I PIANI", "Servizi Igienici"),
        ]),
    ]

    col_w = 0.235
    gap = 0.01
    for idx, (c_title, c_color, rows) in enumerate(cols_data):
        cx = 0.015 + idx * (col_w + gap)
        c_ax = fig.add_axes([cx, 0.02, col_w, 0.325])
        c_ax.set_facecolor("#FFFFFF")
        c_ax.set_xticks([])
        c_ax.set_yticks([])
        for s in c_ax.spines.values():
            s.set_color("#CBD5E1")
            s.set_linewidth(1.2)

        # Header colonna
        c_ax.add_patch(mpatches.Rectangle((0, 0.89), 1.0, 0.11, facecolor=c_color, edgecolor="none", transform=c_ax.transAxes))
        c_ax.text(0.5, 0.945, c_title, fontsize=10.5, fontweight="heavy", color="#FFFFFF", ha="center", va="center", transform=c_ax.transAxes)

        y = 0.84
        for r_idx, (name_s, floor_s, pos_s) in enumerate(rows):
            if r_idx % 2 == 1:
                c_ax.add_patch(mpatches.Rectangle((0.01, y - 0.026), 0.98, 0.052, facecolor="#F1F5F9", edgecolor="none", transform=c_ax.transAxes))

            f_badge_col = "#1D4ED8" if "TERRA" in floor_s else ("#6D28D9" if "PRIMO" in floor_s else ("#047857" if "SECONDO" in floor_s else "#475569"))
            c_ax.text(0.03, y, name_s, fontsize=8.5, fontweight="bold", color="#0F172A", ha="left", va="center", transform=c_ax.transAxes)
            c_ax.text(
                0.48, y, floor_s, fontsize=7.0, fontweight="heavy", color="#FFFFFF", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.16", facecolor=f_badge_col, edgecolor="none"),
                transform=c_ax.transAxes
            )
            c_ax.text(0.65, y, pos_s, fontsize=7.8, fontweight="normal", color="#334155", ha="left", va="center", transform=c_ax.transAxes)
            y -= 0.054

    save_both(fig, "Tabellone_Generale_Ingresso")
    plt.close(fig)


SCHEDULE_KEY_MAP = {
    "004": "Palestra",
    "014": "Aula 014",
    "015": "Aula 015",
    "016": "Aula 016",
    "017": "Aula 017",
    "018": "Lab. Linux 018",
    "019": "Aula 019",
    "020": "Lab. Multimediale 020-021",
    "021": "Lab. Multimediale 020-021",
    "022": "Aula 022",
    "110": "Aula 110",
    "111": "Aula 111",
    "112": "Aula 112",
    "113": "Aula 113",
    "114": "Aula 114",
    "115": "Aula 115",
    "116": "Lab. Cad-Automazione 116-117",
    "117": "Lab. Cad-Automazione 116-117",
    "118": "Lab. Costruzioni 118",
    "119": "Aula 119",
    "125": "Lab. Chimica 125",
    "126": "L. Biologia 126",
    "128": "Aula Informale 128",
    "129": "Lab. Disegno 129",
    "130": "Aula Informale 130",
    "131": "Aula Informale 131",
    "134": "Aula 134",
    "135": "Lab. Fisica 135",
    "201": "Aula 201",
    "202": "Aula 202",
    "203": "Aula 203",
    "204": "Aula 204",
    "205": "Aula 205",
    "206": "Lab. Informatica 206-207",
    "207": "Lab. Informatica 206-207",
    "208": "Lab. Elettronica 208",
    "209": "Aula 209",
    "210": "Lab. Lingue 210",
    "213": "Aula Informale 213",
    "223": "Lab. Sistemi 223",
    "224": "Aula 224",
}


def compute_wing(floor_num, x, y):
    """Restituisce l'indicazione direzionale umana (es. Ala Nord-Est, Blocco Est, Centro)."""
    if floor_num in (0, 1):
        if x < 15.0:
            return "Blocco Ovest (Lato Palestra)"
        if x > 34.5 and y < 14.0:
            return "Blocco Est (Lato Officina / Chimica)"
        if y > 23.5:
            return "Ala Nord-Est" if x > 31.0 else "Ala Nord-Ovest"
        if y < 12.5:
            return "Ala Sud (Lato Mensa / Uffici)" if x < 24.0 else "Ala Sud-Est"
        return "Ala Est" if x > 30.5 else ("Ala Ovest" if x < 25.5 else "Corpo Centrale")
    else:
        if y > 15.0:
            return "Ala Nord-Est" if x > 14.5 else "Ala Nord-Ovest"
        if y < 6.8:
            return "Ala Sud-Est" if x > 11.0 else "Ala Sud-Ovest"
        return "Ala Est" if x > 14.0 else ("Ala Ovest" if x < 9.0 else "Corpo Centrale")


def write_clean_svg(svg_path, geom, xlim, ylim, scale=40.0):
    """Esporta la geometria CAD pura in un file SVG vettoriale super-leggero e nitido per il web."""
    x0, x1 = xlim
    y0, y1 = ylim
    w = round((x1 - x0) * scale, 1)
    h = round((y1 - y0) * scale, 1)

    def tx(x):
        return round((x - x0) * scale, 1)

    def ty(y):
        return round((y1 - y) * scale, 1)

    def polylines_to_path(lines, min_len=0.06):
        cmds = []
        for seg in lines:
            if len(seg) < 2:
                continue
            length = sum(math.hypot(seg[i + 1][0] - seg[i][0], seg[i + 1][1] - seg[i][1]) for i in range(len(seg) - 1))
            if length < min_len:
                continue
            pts_str = []
            for p in seg:
                pt = f"{tx(p[0]):g},{ty(p[1]):g}"
                if not pts_str or pts_str[-1] != pt:
                    pts_str.append(pt)
            if len(pts_str) >= 2:
                cmds.append("M" + "L".join(pts_str))
        return "".join(cmds)

    def polys_to_path(polys):
        cmds = []
        for poly in polys:
            if len(poly) < 3:
                continue
            pts_str = [f"{tx(p[0]):g},{ty(p[1]):g}" for p in poly]
            cmds.append("M" + "L".join(pts_str) + "Z")
        return "".join(cmds)

    d_furn = polylines_to_path(geom["furniture"], min_len=0.08)
    d_glass = polylines_to_path(geom["walls_glass"], min_len=0.04)
    d_walls = polylines_to_path(geom["walls_primary"], min_len=0.05)
    d_fill = polys_to_path(geom["polys_fill"])

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="100%">',
        f'  <rect width="{w}" height="{h}" fill="#ffffff" rx="12" />',
    ]
    if d_furn:
        svg_parts.append(
            f'  <path id="cad-furniture" d="{d_furn}" stroke="#cbd5e1" stroke-width="0.9" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
        )
    if d_glass:
        svg_parts.append(
            f'  <path id="cad-glass" d="{d_glass}" stroke="#64748b" stroke-width="1.3" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
        )
    if d_walls:
        svg_parts.append(
            f'  <path id="cad-walls" d="{d_walls}" stroke="#0f172a" stroke-width="2.0" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
        )
    if d_fill:
        svg_parts.append(
            f'  <path id="cad-columns" d="{d_fill}" fill="#1e293b" stroke="none" />'
        )
    svg_parts.append("</svg>\n")

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_parts))


def export_web_assets(geom_0, geom_1, geom_2):
    """Genera public/data/mappe/piano_{0,1,2}.svg e public/data/mappe.json per l'app web."""
    web_map_dir = os.path.join(BASE_DIR, "public", "data", "mappe")
    os.makedirs(web_map_dir, exist_ok=True)
    scale = 40.0

    floors_spec = [
        (0, "Piano Terra", "PIANO TERRA", "Ingressi, Aule 014–022, Lab. Linux & Multimediale, Officina, Palestra, Mensa", geom_0, ROOMS_PIANO_TERRA, (4.2, 43.2), (1.0, 32.3)),
        (1, "1° Piano", "PIANO PRIMO", "Aule 110–134, Aule Informali, Lab. CAD, Costruzioni, Chimica, Biologia, Fisica, Segreteria", geom_1, ROOMS_PIANO_PRIMO, (4.2, 43.2), (1.0, 32.3)),
        (2, "2° Piano", "PIANO SECONDO", "Aule 201–224, Aula Informale 213, Lab. Informatica, Elettronica, Lingue, Sistemi", geom_2, ROOMS_PIANO_SECONDO, (4.0, 22.8), (1.0, 22.9)),
    ]

    floors_out = []
    for f_num, short_title, full_title, subtitle, geom, rooms, xlim, ylim in floors_spec:
        svg_filename = f"piano_{f_num}.svg"
        svg_abs = os.path.join(web_map_dir, svg_filename)
        write_clean_svg(svg_abs, geom, xlim, ylim, scale=scale)

        x0, x1 = xlim
        y0, y1 = ylim
        vw = round((x1 - x0) * scale, 1)
        vh = round((y1 - y0) * scale, 1)

        rooms_out = []
        for idx, r in enumerate(rooms):
            sx = round((r["x"] - x0) * scale, 1)
            sy = round((y1 - r["y"]) * scale, 1)
            code = r["code"]
            sched_key = SCHEDULE_KEY_MAP.get(code)
            wing = compute_wing(f_num, r["x"], r["y"])
            st = CAT_STYLES[r["cat"]]
            rooms_out.append({
                "id": f"f{f_num}_{idx}_{code.replace(' ', '_')}",
                "code": code,
                "name": r["name"],
                "sub": r.get("sub", ""),
                "cat": r["cat"],
                "catLabel": st["label"],
                "color": st["bg"],
                "fillColor": st["sub_bg"],
                "borderColor": st["border"],
                "size": r.get("size", "md"),
                "floor": f_num,
                "floorLabel": short_title,
                "wing": wing,
                "x": r["x"],
                "y": r["y"],
                "svgX": sx,
                "svgY": sy,
                "scheduleKey": sched_key,
            })

        floors_out.append({
            "floor": f_num,
            "shortTitle": short_title,
            "title": full_title,
            "subtitle": subtitle,
            "svgUrl": f"./public/data/mappe/{svg_filename}",
            "viewBox": [0, 0, vw, vh],
            "cadBounds": {"xlim": list(xlim), "ylim": list(ylim)},
            "rooms": rooms_out,
        })

    mappe_json_path = os.path.join(BASE_DIR, "public", "data", "mappe.json")
    with open(mappe_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "istituto": "I.T.T. L. Negrelli • I.T.G. E. Forcellini — Feltre",
            "categories": CAT_STYLES,
            "floors": floors_out,
        }, f, ensure_ascii=False, indent=2)
    print("✔ Esportati SVG web in public/data/mappe/ e metadati in public/data/mappe.json")


if __name__ == "__main__":
    g0, g1, g2 = build_single_floor_posters()
    build_master_entrance_board(g0, g1, g2)
    export_web_assets(g0, g1, g2)

