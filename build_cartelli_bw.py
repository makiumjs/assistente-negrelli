#!/usr/bin/env python3
"""
Generatore Cartellonistica Wayfinding Scolastica in Bianco e Nero (B&W) ad Alta Definizione (300 DPI A3)
Progettato specificamente per la stampa monocromatica su plotter / stampanti A3 da ufficio.

Produce:
1. 0_Cartello_Piano_Terra.png (+ _BN.png e .pdf)
2. 1_Cartello_Piano_Primo.png (+ _BN.png e .pdf)
3. 2_Cartello_Piano_Secondo.png (+ _BN.png e .pdf)
4. Tabellone_Generale_Ingresso.png (+ _BN.png e .pdf)
"""

import json
import math
import os
import re
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection, PolyCollection
import matplotlib.patheffects as pe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "mappe_stampabili")
os.makedirs(OUT_DIR, exist_ok=True)

# Formato Standard ISO 216 A3 Orizzontale (420 x 297 mm, 300 DPI = 4961 x 3508 px)
A3_INCHES = (420.0 / 25.4, 297.0 / 25.4)

plt.rcParams['font.sans-serif'] = ['Helvetica Neue', 'Avenir Next', 'Arial', 'DejaVu Sans']
plt.rcParams['axes.edgecolor'] = '#000000'
plt.rcParams['axes.linewidth'] = 1.0


# Stile Bianco e Nero ad alto contrasto ottimizzato per stampa laser e plotter
BW_STYLES = {
    "aula": {
        "bg": "#FFFFFF",
        "border": "#000000",
        "text": "#000000",
        "linewidth": 1.2,
        "label": "Aule Didattiche",
        "sub_text": "#333333"
    },
    "lab": {
        "bg": "#FFFFFF",
        "border": "#000000",
        "text": "#000000",
        "linewidth": 2.0,
        "label": "Laboratori & Officina",
        "sub_text": "#333333"
    },
    "informale": {
        "bg": "#F4F4F5",
        "border": "#000000",
        "text": "#000000",
        "linewidth": 1.0,
        "label": "Aule Informali & Biblioteca",
        "sub_text": "#444444"
    },
    "comuni": {
        "bg": "#FFFFFF",
        "border": "#000000",
        "text": "#000000",
        "linewidth": 1.8,
        "label": "Palestra, Area Ristoro & Bar",
        "sub_text": "#333333"
    },
    "uffici": {
        "bg": "#000000",
        "border": "#000000",
        "text": "#FFFFFF",
        "linewidth": 1.5,
        "label": "Docenti, Vicepresidenza & Segreteria",
        "sub_text": "#E4E4E7"
    },
    "scale": {
        "bg": "#27272A",
        "border": "#000000",
        "text": "#FFFFFF",
        "linewidth": 1.2,
        "label": "Scale & Ascensore",
        "sub_text": "#D4D4D8"
    },
    "wc": {
        "bg": "#FFFFFF",
        "border": "#000000",
        "text": "#000000",
        "linewidth": 1.0,
        "label": "Servizi Igienici (WC)",
        "sub_text": "#555555"
    },
    "ingresso": {
        "bg": "#000000",
        "border": "#000000",
        "text": "#FFFFFF",
        "linewidth": 2.2,
        "label": "Ingresso Principale (Voi Siete Qui)",
        "sub_text": "#FFFFFF"
    },
    "vuoto": {
        "bg": "#FFFFFF",
        "border": "#71717A",
        "text": "#52525B",
        "linewidth": 0.8,
        "label": "Doppia Altezza (Piano Sottostante)",
        "sub_text": "#71717A"
    }
}


def load_geom_from_svg(svg_path, xlim, ylim, scale=40.0):
    """Estrae i muri e pilastri CAD direttamente dal file SVG vettoriale."""
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_text = f.read()

    x0, x1 = xlim
    y0, y1 = ylim

    def to_cad(sx, sy):
        return (x0 + sx / scale, y1 - sy / scale)

    def is_furniture(pts):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        is_closed = (math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 0.02) if len(pts) > 2 else False
        if max(w, h) < 2.0 and min(w, h) > 0.18 and is_closed:
            return True
        if max(w, h) < 0.7:
            return True
        return False

    walls_primary = []
    polys_fill = []

    # Muri CAD
    m_walls = re.search(r'<path id="cad-walls" d="([^"]+)"', svg_text)
    if m_walls:
        d = m_walls.group(1)
        for part in d.split('M'):
            part = part.strip()
            if not part:
                continue
            points = part.split('L')
            pts = []
            for pt in points:
                coords = pt.split(',')
                if len(coords) == 2:
                    try:
                        pts.append(to_cad(float(coords[0]), float(coords[1])))
                    except ValueError:
                        pass
            if len(pts) >= 2 and not is_furniture(pts):
                for k in range(len(pts) - 1):
                    walls_primary.append([pts[k], pts[k + 1]])

    # Pilastri CAD
    m_cols = re.search(r'<path id="cad-columns" d="([^"]+)"', svg_text)
    if m_cols:
        d = m_cols.group(1)
        for part in d.split('M'):
            part = part.strip().rstrip('Zz')
            if not part:
                continue
            points = part.split('L')
            pts = []
            for pt in points:
                coords = pt.split(',')
                if len(coords) == 2:
                    try:
                        pts.append(to_cad(float(coords[0]), float(coords[1])))
                    except ValueError:
                        pass
            if len(pts) >= 3:
                polys_fill.append(pts)

    return {
        "walls_primary": walls_primary,
        "polys_fill": polys_fill,
        "walls_glass": [],
        "walls_furniture": []
    }


def draw_floor_bw(ax, geom, rooms, xlim, ylim, scale_factor=1.0):
    """Disegna la pianta in bianco e nero nitido su sfondo bianco."""
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")

    # Muri strutturali neri
    if geom["walls_primary"]:
        ax.add_collection(
            LineCollection(geom["walls_primary"], colors="#000000", linewidths=0.95 * scale_factor, zorder=2)
        )

    # Pilastri neri
    if geom["polys_fill"]:
        ax.add_collection(
            PolyCollection(geom["polys_fill"], facecolors="#18181B", edgecolors="none", zorder=3)
        )

    # Disegna cartellini delle stanze in bianco e nero (senza cerchi posteriori su richiesta)
    for r in rooms:
        st = BW_STYLES.get(r["cat"], BW_STYLES["aula"])
        x, y = r["x"], r["y"]
        sz = r.get("size", "md")

        # Dimensioni font
        fs_map = {
            "lg": (10.0 * scale_factor, 7.2 * scale_factor),
            "md": (7.8 * scale_factor, 5.8 * scale_factor),
            "sm": (6.5 * scale_factor, 5.0 * scale_factor),
            "xs": (5.4 * scale_factor, 4.4 * scale_factor),
        }
        fs_main, fs_sub = fs_map.get(sz, (7.8 * scale_factor, 5.8 * scale_factor))

        label_text = r["name"]
        if r.get("sub") and scale_factor >= 0.75:
            label_text = f"{r['name']}\n{r['sub']}"
        elif r.get("sub") and sz in ("lg", "md"):
            label_text = f"{r['name']}\n{r['sub']}"

        # Bbox in bianco e nero
        is_inverted = st["bg"] == "#000000" or st["bg"] == "#27272A"
        bbox_props = dict(
            boxstyle="round,pad=0.26,rounding_size=0.30",
            facecolor=st["bg"] if r["cat"] != "vuoto" else "#FFFFFF",
            edgecolor=st["border"] if r["cat"] != "vuoto" else "#71717A",
            linewidth=st["linewidth"] * scale_factor,
            linestyle="--" if r["cat"] == "vuoto" else "-",
        )

        txt_color = st["text"]
        ax.text(
            x, y, label_text,
            fontsize=fs_main if "\n" not in label_text else fs_main * 0.92,
            fontweight="bold",
            color=txt_color,
            ha="center", va="center",
            linespacing=1.15,
            bbox=bbox_props,
            zorder=6
        )

    # Rosa dei Venti / Indicatore Nord
    north_x = xlim[0] + 0.05 * (xlim[1] - xlim[0])
    north_y = ylim[1] - 0.08 * (ylim[1] - ylim[0])
    ax.annotate(
        "N", xy=(north_x, north_y), xytext=(north_x, north_y - 1.2),
        arrowprops=dict(facecolor="#000000", edgecolor="#000000", width=1.5, headwidth=6, headlength=7),
        fontsize=10, fontweight="heavy", color="#000000", ha="center", va="bottom", zorder=10
    )


def add_poster_header_bw(fig, floor_num, title, subtitle):
    """Disegna la testata pulita del poster A3 in bianco e nero."""
    h_ax = fig.add_axes([0.02, 0.905, 0.96, 0.075])
    h_ax.set_facecolor("#FFFFFF")
    h_ax.set_xticks([])
    h_ax.set_yticks([])
    for s in h_ax.spines.values():
        s.set_visible(False)

    # Linea superiore e inferiore
    h_ax.plot([0, 1], [0.98, 0.98], color="#000000", linewidth=2.5, transform=h_ax.transAxes)
    h_ax.plot([0, 1], [0.02, 0.02], color="#000000", linewidth=1.2, transform=h_ax.transAxes)

    # Badge piano invertito in nero
    badge_label = f" PIANO {floor_num} " if floor_num > 0 else " PIANO TERRA "
    h_ax.text(
        0.01, 0.50, badge_label,
        fontsize=15, fontweight="heavy", color="#FFFFFF",
        ha="left", va="center",
        bbox=dict(boxstyle="square,pad=0.45", facecolor="#000000", edgecolor="#000000", linewidth=1.5),
        transform=h_ax.transAxes
    )

    h_ax.text(
        0.18, 0.68, "I.T.T. «L. NEGRELLI»  •  I.T.G. «E. FORCELLINI» — POLO SCOLASTICO FELTRE",
        fontsize=10.5, fontweight="bold", color="#27272A",
        ha="left", va="center", transform=h_ax.transAxes
    )

    h_ax.text(
        0.18, 0.30, title,
        fontsize=13.5, fontweight="heavy", color="#000000",
        ha="left", va="center", transform=h_ax.transAxes
    )

    h_ax.text(
        0.99, 0.50, "ORIENTAMENTO & WAYFINDING\nFORMATO STAMPA A3 B&W",
        fontsize=8.5, fontweight="bold", color="#52525B",
        ha="right", va="center", linespacing=1.2, transform=h_ax.transAxes
    )


def add_legend_bw(fig):
    """Legenda inferiore rimossa su richiesta dell'utente per massimizzare la pianta."""
    pass


def add_sidebar_bw(fig, floor_title, sections):
    """Disegna sulla destra del poster la rubrica rapida in bianco e nero compatta (area ridotta del 75%)."""
    total_items = sum(len(items) for _, items in sections)
    num_secs = len(sections)
    calc_h = max(0.22, min(0.60, 0.05 + num_secs * 0.032 + total_items * 0.024))
    side_ax = fig.add_axes([0.842, 0.885 - calc_h, 0.142, calc_h])
    side_ax.set_facecolor("#FFFFFF")
    side_ax.set_xticks([])
    side_ax.set_yticks([])
    for s in side_ax.spines.values():
        s.set_color("#000000")
        s.set_linewidth(1.0)

    side_ax.text(
        0.5, 0.94, f"ELENCO — {floor_title}",
        fontsize=8.5, fontweight="heavy", color="#FFFFFF",
        ha="center", va="center",
        bbox=dict(boxstyle="square,pad=0.30", facecolor="#000000", edgecolor="#000000"),
        transform=side_ax.transAxes
    )

    y_step_item = 0.83 / max(1, (num_secs * 1.4 + total_items))
    y = 0.84
    for sec_title, items in sections:
        side_ax.text(
            0.06, y, sec_title.upper(),
            fontsize=7.2, fontweight="heavy", color="#000000",
            ha="left", va="center", transform=side_ax.transAxes
        )
        y -= y_step_item * 0.7

        for code_str, desc_str in items:
            badge_fs = 5.2 if len(code_str) >= 7 else (5.9 if len(code_str) >= 5 else 6.8)
            desc_x = 0.32 if len(code_str) >= 7 else (0.28 if len(code_str) >= 4 else 0.25)
            side_ax.text(
                0.06, y, code_str,
                fontsize=badge_fs, fontweight="heavy", color="#000000",
                ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="#000000", linewidth=0.6),
                transform=side_ax.transAxes
            )
            side_ax.text(
                desc_x, y, desc_str,
                fontsize=6.8,
                fontweight="bold" if any(k in desc_str for k in ("Vicepresidenza", "Insegnanti", "Segreteria", "Dirigenza")) else "normal",
                color="#000000",
                ha="left", va="center", transform=side_ax.transAxes
            )
            y -= y_step_item
        y -= y_step_item * 0.4


def save_poster(fig, basename):
    """Salva il cartello in alta definizione 300 DPI sia come PNG standard sia con suffisso _BN e PDF."""
    png_path_std = os.path.join(OUT_DIR, f"{basename}.png")
    png_path_bn = os.path.join(OUT_DIR, f"{basename}_BN.png")
    pdf_path = os.path.join(OUT_DIR, f"{basename}.pdf")

    fig.savefig(png_path_std, dpi=300, facecolor="#FFFFFF")
    fig.savefig(png_path_bn, dpi=300, facecolor="#FFFFFF")
    fig.savefig(pdf_path, facecolor="#FFFFFF")
    print(f"✔ Generato {basename}: {png_path_std} (300 DPI A3) e {png_path_bn}")
    plt.close(fig)


def build_all_posters():
    print("Avvio generazione cartellonistica A3 in Bianco e Nero...")

    with open(os.path.join(BASE_DIR, "public", "data", "mappe.json"), "r", encoding="utf-8") as f:
        mappe_data = json.load(f)

    floors_data = {f["floor"]: f for f in mappe_data["floors"]}

    svg_0 = os.path.join(BASE_DIR, "public", "data", "mappe", "piano_0.svg")
    svg_1 = os.path.join(BASE_DIR, "public", "data", "mappe", "piano_1.svg")
    svg_2 = os.path.join(BASE_DIR, "public", "data", "mappe", "piano_2.svg")

    geom_0 = load_geom_from_svg(svg_0, (4.2, 43.2), (1.0, 32.3))
    geom_1 = load_geom_from_svg(svg_1, (4.2, 43.2), (1.0, 32.3))
    geom_2 = load_geom_from_svg(svg_2, (4.0, 22.8), (1.0, 22.9))

    rooms_0 = floors_data[0]["rooms"]
    rooms_1 = floors_data[1]["rooms"]
    rooms_2 = floors_data[2]["rooms"]

    # ----------------------------------------------------
    # 1. CARTELLO PIANO TERRA
    # ----------------------------------------------------
    fig0 = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    ax0 = fig0.add_axes([0.02, 0.02, 0.815, 0.868])
    draw_floor_bw(ax0, geom_0, rooms_0, (4.2, 43.2), (1.0, 32.3), scale_factor=0.98)
    add_poster_header_bw(
        fig0, 0,
        "PIANO TERRA — INGRESSO, AULE, LABORATORI, PALESTRA E AULA INSEGNANTI",
        "Aule Didattiche 014–022  •  Lab. Linux (018), Multimediale (020-021), Officina (026)  •  Aula Insegnanti (028)"
    )
    add_legend_bw(fig0)
    sections_0 = [
        ("Aule Didattiche", [
            ("014", "Aula 014"),
            ("015", "Aula 015"),
            ("016", "Aula 016"),
            ("017", "Aula 017"),
            ("019", "Aula 019"),
            ("022", "Aula 022"),
        ]),
        ("Laboratori & Officina", [
            ("018", "Lab. Linux"),
            ("020-021", "Lab. Multimediale"),
            ("024-025", "Laboratori 1 e 2"),
            ("026", "Officina Meccanica"),
            ("030-031", "Laboratori 4 e 5"),
        ]),
        ("Uffici, Docenti & Ristoro", [
            ("028", "Aula Insegnanti"),
            ("060", "Vicepresidenza"),
            ("035", "Segreteria Didattica"),
            ("069", "Area Ristoro / Bar"),
            ("009", "Infermeria"),
        ]),
        ("Sport, Studio & Accessi", [
            ("004", "Palestra"),
            ("005-006", "Spogliatoi"),
            ("058-059", "Biblioteca"),
            ("032-033", "Agorà Studio"),
            ("INGRESSO", "Ingresso Principale"),
            ("037", "Entrata Palestra"),
        ]),
    ]
    add_sidebar_bw(fig0, "PIANO TERRA", sections_0)
    save_poster(fig0, "0_Cartello_Piano_Terra")

    # ----------------------------------------------------
    # 2. CARTELLO PRIMO PIANO
    # ----------------------------------------------------
    fig1 = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    ax1 = fig1.add_axes([0.02, 0.02, 0.815, 0.868])
    draw_floor_bw(ax1, geom_1, rooms_1, (4.2, 43.2), (1.0, 32.3), scale_factor=0.98)
    add_poster_header_bw(
        fig1, 1,
        "1° PIANO — AULE DIDATTICHE, LABORATORI, DIRIGENZA E UFFICI",
        "Aule 110–134  •  Lab. CAD (116), Automazione (117), Costruzioni (118), Chimica (125), Biologia (126), Disegno (129), Fisica (135)"
    )
    add_legend_bw(fig1)
    sections_1 = [
        ("Aule Didattiche", [
            ("110", "Aula 110"),
            ("111", "Aula 111"),
            ("112", "Aula 112"),
            ("113", "Aula 113"),
            ("114", "Aula 114"),
            ("115", "Aula 115"),
            ("119", "Aula 119"),
            ("134", "Aula 134"),
        ]),
        ("Laboratori", [
            ("116", "Lab. CAD"),
            ("117", "Lab. Automazione"),
            ("118", "Lab. Costruzioni"),
            ("125", "Lab. Chimica"),
            ("126", "Lab. Biologia"),
            ("129", "Lab. Disegno"),
            ("135", "Lab. Fisica"),
        ]),
        ("Uffici", [
            ("UFFICI", "Dirigenza e Uffici"),
        ]),
        ("Servizi Igienici", [
            ("WC", "WC Docenti"),
            ("WC", "WC Alunni"),
        ]),
    ]
    add_sidebar_bw(fig1, "PRIMO PIANO", sections_1)
    save_poster(fig1, "1_Cartello_Piano_Primo")

    # ----------------------------------------------------
    # 3. CARTELLO SECONDO PIANO
    # ----------------------------------------------------
    fig2 = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    ax2 = fig2.add_axes([0.02, 0.02, 0.815, 0.868])
    draw_floor_bw(ax2, geom_2, rooms_2, (4.0, 22.8), (1.0, 22.9), scale_factor=1.12)
    add_poster_header_bw(
        fig2, 2,
        "2° PIANO — AULE DIDATTICHE, INFORMATICA, ELETTRONICA, SISTEMI E LINGUE",
        "Aule 201–224  •  Lab. Informatica (206-207), Elettronica (208), Lingue (210), Sistemi (223)"
    )
    add_legend_bw(fig2)
    sections_2 = [
        ("Aule Didattiche", [
            ("201", "Aula 201"),
            ("202", "Aula 202"),
            ("203", "Aula 203"),
            ("204", "Aula 204"),
            ("205", "Aula 205"),
            ("209", "Aula 209"),
            ("224", "Aula 224"),
        ]),
        ("Laboratori Specialistici", [
            ("206-207", "Lab. Informatica"),
            ("208", "Lab. Elettronica"),
            ("210", "Lab. Lingue"),
            ("223", "Lab. Sistemi & Reti"),
        ]),
        ("Aule Informali & Studio", [
            ("213", "Aula Informale 213"),
            ("214", "Spazio Lab 214"),
            ("221", "Spazio Lab 221"),
            ("211-212", "Spazi Informali"),
            ("225", "Spazio Informale 225"),
        ]),
        ("Accessi & Servizi", [
            ("046", "Ascensore"),
            ("215", "Scale"),
            ("WC", "Servizi Igienici (WC)"),
        ]),
    ]
    add_sidebar_bw(fig2, "SECONDO PIANO", sections_2)
    save_poster(fig2, "2_Cartello_Piano_Secondo")

    # ----------------------------------------------------
    # 4. TABELLONE GENERALE INGRESSO (3 PIANI + RUBRICA)
    # ----------------------------------------------------
    fig_m = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")

    # Testata generale
    h_ax = fig_m.add_axes([0.015, 0.915, 0.97, 0.072])
    h_ax.set_facecolor("#FFFFFF")
    h_ax.set_xticks([])
    h_ax.set_yticks([])
    for s in h_ax.spines.values():
        s.set_visible(False)
    h_ax.plot([0, 1], [0.98, 0.98], color="#000000", linewidth=2.5, transform=h_ax.transAxes)
    h_ax.plot([0, 1], [0.02, 0.02], color="#000000", linewidth=1.2, transform=h_ax.transAxes)

    h_ax.text(
        0.015, 0.52, " GUIDA GENERALE DELL'ISTITUTO — DOVE ANDARE ",
        fontsize=15, fontweight="heavy", color="#FFFFFF", ha="left", va="center",
        bbox=dict(boxstyle="square,pad=0.45", facecolor="#000000", edgecolor="#000000"),
        transform=h_ax.transAxes
    )
    h_ax.text(
        0.42, 0.68, "I.T.T. «L. NEGRELLI»  •  I.T.G. «E. FORCELLINI» — POLO SCOLASTICO DI FELTRE",
        fontsize=11.5, fontweight="heavy", color="#000000", ha="left", va="center", transform=h_ax.transAxes
    )
    h_ax.text(
        0.42, 0.28, "REGOLA RAPIDA DEI CODICI LOCALE:   0xx = PIANO TERRA   •   1xx = 1° PIANO   •   2xx = 2° PIANO",
        fontsize=9.0, fontweight="bold", color="#3F3F46", ha="left", va="center", transform=h_ax.transAxes
    )

    # 3 piante affiancate
    floors_cfg = [
        (0, "PIANO TERRA (Locali 001 – 073)", geom_0, rooms_0, (4.2, 43.2), (1.0, 32.3), [0.015, 0.365, 0.34, 0.505], 0.52),
        (1, "1° PIANO (Locali 101 – 139)", geom_1, rooms_1, (4.2, 43.2), (1.0, 32.3), [0.365, 0.365, 0.34, 0.505], 0.52),
        (2, "2° PIANO (Locali 201 – 227)", geom_2, rooms_2, (4.0, 22.8), (1.0, 22.9), [0.715, 0.365, 0.27, 0.505], 0.58),
    ]

    for f_num, f_title, geom, rooms, xlim, ylim, rect, sc in floors_cfg:
        t_ax = fig_m.add_axes([rect[0], rect[1] + rect[3], rect[2], 0.030])
        t_ax.set_facecolor("#000000")
        t_ax.set_xticks([])
        t_ax.set_yticks([])
        for s in t_ax.spines.values():
            s.set_visible(False)
        t_ax.text(0.5, 0.5, f_title, fontsize=10.0, fontweight="heavy", color="#FFFFFF", ha="center", va="center")

        ax = fig_m.add_axes(rect)
        draw_floor_bw(ax, geom, rooms, xlim, ylim, scale_factor=sc)
        ax.set_aspect("equal", adjustable="datalim")
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color("#000000")
            s.set_linewidth(1.2)

    # 4 colonne inferiori di rubrica
    cols_data = [
        ("1. TUTTE LE AULE DIDATTICHE", [
            ("Aula 014", "PIANO TERRA", ""),
            ("Aula 015", "PIANO TERRA", ""),
            ("Aula 016", "PIANO TERRA", ""),
            ("Aula 017", "PIANO TERRA", ""),
            ("Aula 019", "PIANO TERRA", ""),
            ("Aula 022", "PIANO TERRA", ""),
            ("Aula 110", "1° PIANO", ""),
            ("Aula 111", "1° PIANO", ""),
            ("Aula 112", "1° PIANO", ""),
            ("Aula 113", "1° PIANO", ""),
            ("Aula 114", "1° PIANO", ""),
            ("Aula 115", "1° PIANO", ""),
            ("Aula 119", "1° PIANO", ""),
            ("Aula 134", "1° PIANO", ""),
        ]),
        ("2. AULE 2° PIANO & STUDIO", [
            ("Aula 201", "2° PIANO", ""),
            ("Aula 202", "2° PIANO", ""),
            ("Aula 203", "2° PIANO", ""),
            ("Aula 204", "2° PIANO", ""),
            ("Aula 205", "2° PIANO", ""),
            ("Aula 209", "2° PIANO", ""),
            ("Aula 224", "2° PIANO", ""),
            ("Informale 128", "1° PIANO", ""),
            ("Informale 130", "1° PIANO", ""),
            ("Informale 131", "1° PIANO", ""),
            ("Informale 213", "2° PIANO", ""),
            ("Spazi Studio", "TUTTI I PIANI", "032-033 / 137 / 211-212"),
            ("Biblioteca", "PIANO TERRA", "Locali 058 – 059"),
        ]),
        ("3. LABORATORI & OFFICINA", [
            ("Lab. Linux 018", "PIANO TERRA", "Locale 018"),
            ("Lab. Multimediale", "PIANO TERRA", "Locali 020 – 021"),
            ("Lab 1 & Lab 2", "PIANO TERRA", "Locali 024 – 025"),
            ("Officina Meccanica", "PIANO TERRA", "Locale 026"),
            ("Lab 4 & Lab 5", "PIANO TERRA", "Locali 030, 031"),
            ("Lab. CAD-Automaz.", "1° PIANO", "Locali 116 – 117"),
            ("Lab. Costruzioni", "1° PIANO", "Locale 118"),
            ("Lab. Chimica", "1° PIANO", "Locale 125"),
            ("Lab. Biologia", "1° PIANO", "Locale 126"),
            ("Lab. Disegno", "1° PIANO", "Locale 129"),
            ("Lab. Fisica", "1° PIANO", "Locale 135"),
            ("Lab. Informatica", "2° PIANO", "Locali 206 – 207"),
            ("Lab. Elettronica", "2° PIANO", "Locale 208"),
            ("Lab. Lingue", "2° PIANO", "Locale 210"),
            ("Lab. Sistemi", "2° PIANO", "Locale 223"),
        ]),
        ("4. UFFICI, DOCENTI & RISTORO", [
            ("Ingresso / Atrio", "PIANO TERRA", "Locali 029 / 036"),
            ("Aula Insegnanti", "PIANO TERRA", "Locale 028"),
            ("Vicepresidenza", "PIANO TERRA", "Locale 060"),
            ("Segreteria Didattica", "PIANO TERRA", "Locale 035"),
            ("Area Ristoro / Bar", "PIANO TERRA", "Locale 069"),
            ("Palestra & Spogliatoi", "PIANO TERRA", "Locali 004 – 008"),
            ("Infermeria", "PIANO TERRA", "Locale 009"),
            ("Dirigenza e Uffici", "1° PIANO", "Locali 104, 105, 106, 138"),
            ("Ascensore", "TUTTI I PIANI", "Centro Edificio"),
            ("Scale Principali", "TUTTI I PIANI", "Scale di Piano"),
            ("WC Docenti e Alunni", "TUTTI I PIANI", "Servizi Igienici"),
        ]),
    ]

    col_w = 0.235
    col_gap = 0.010
    start_x = 0.015

    for c_idx, (col_title, items) in enumerate(cols_data):
        cx = start_x + c_idx * (col_w + col_gap)
        c_ax = fig_m.add_axes([cx, 0.02, col_w, 0.325])
        c_ax.set_facecolor("#FFFFFF")
        c_ax.set_xticks([])
        c_ax.set_yticks([])
        for s in c_ax.spines.values():
            s.set_color("#000000")
            s.set_linewidth(1.0)

        c_ax.text(
            0.5, 0.965, col_title,
            fontsize=8.5, fontweight="heavy", color="#FFFFFF", ha="center", va="center",
            bbox=dict(boxstyle="square,pad=0.35", facecolor="#000000", edgecolor="#000000"),
            transform=c_ax.transAxes
        )

        y = 0.905
        for name, floor_str, note_str in items:
            c_ax.text(0.04, y, name, fontsize=7.2, fontweight="bold", color="#000000", ha="left", va="center", transform=c_ax.transAxes)
            c_ax.text(
                0.96, y, floor_str, fontsize=6.5, fontweight="heavy", color="#000000", ha="right", va="center",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFFFFF", edgecolor="#000000", linewidth=0.7),
                transform=c_ax.transAxes
            )
            if note_str:
                y -= 0.024
                c_ax.text(0.06, y, note_str, fontsize=6.2, fontweight="normal", color="#52525B", ha="left", va="center", transform=c_ax.transAxes)
                y -= 0.038
            else:
                y -= 0.056

    save_poster(fig_m, "Tabellone_Generale_Ingresso")

    print("\n Tutti i cartelli A3 B&W (PNG 300 DPI + PDF) sono stati generati con successo!")


if __name__ == "__main__":
    build_all_posters()
