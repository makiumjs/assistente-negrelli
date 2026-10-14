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
            if len(pts) >= 2:
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

    # Disegna cartellini delle stanze in bianco e nero
    for r in rooms:
        st = BW_STYLES.get(r["cat"], BW_STYLES["aula"])
        x, y = r["x"], r["y"]
        sz = r.get("size", "md")

        # Alone circolare sottile tratteggiato intorno alle aule didattiche e uffici
        rad_map = {"lg": 1.55, "md": 1.0, "sm": 0.68, "xs": 0.48}
        rad = rad_map.get(sz, 1.0)
        if xlim[1] - xlim[0] < 25:
            rad *= 0.68

        if r["cat"] not in ("vuoto", "scale", "wc"):
            circle = mpatches.Circle(
                (x, y), radius=rad,
                facecolor="#FAFAFA", edgecolor="#A1A1AA",
                linewidth=0.6 * scale_factor, linestyle=":", zorder=4
            )
            ax.add_patch(circle)

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
    """Disegna la legenda inferiore in bianco e nero."""
    leg_ax = fig.add_axes([0.02, 0.02, 0.72, 0.052])
    leg_ax.set_facecolor("#FFFFFF")
    leg_ax.set_xticks([])
    leg_ax.set_yticks([])
    for s in leg_ax.spines.values():
        s.set_color("#000000")
        s.set_linewidth(1.0)

    items = [
        ("[ AULA ]", "Aule Didattiche (Bordo nero sottile)"),
        ("[ LAB ]", "Laboratori / Officina (Bordo nero spesso)"),
        ("[ INGRESSO ]", "Ingressi (Fondo nero, testo bianco)"),
        ("[ UFFICI ]", "Uffici & Vicepresidenza (Fondo nero)"),
        ("[ INFORMALE ]", "Spazi Studio (Fondo grigio chiaro)"),
        ("[ WC ]", "Servizi Igienici (Cod. WC)"),
    ]

    for idx, (sym, desc) in enumerate(items):
        col_i = idx % 3
        row_i = idx // 3
        x_pos = 0.02 + col_i * 0.33
        y_pos = 0.72 if row_i == 0 else 0.28
        leg_ax.text(
            x_pos, y_pos, sym,
            fontsize=7.8, fontweight="heavy", color="#000000",
            ha="left", va="center", transform=leg_ax.transAxes
        )
        leg_ax.text(
            x_pos + 0.08, y_pos, desc,
            fontsize=7.2, fontweight="medium", color="#27272A",
            ha="left", va="center", transform=leg_ax.transAxes
        )


def add_sidebar_bw(fig, floor_title, sections):
    """Disegna sulla destra del poster la rubrica rapida in bianco e nero con griglia allineata."""
    side_ax = fig.add_axes([0.755, 0.02, 0.225, 0.868])
    side_ax.set_facecolor("#FFFFFF")
    side_ax.set_xticks([])
    side_ax.set_yticks([])
    for s in side_ax.spines.values():
        s.set_color("#000000")
        s.set_linewidth(1.4)

    side_ax.text(
        0.5, 0.974, f"ELENCO LOCALI — {floor_title}",
        fontsize=9.5, fontweight="heavy", color="#FFFFFF",
        ha="center", va="center",
        bbox=dict(boxstyle="square,pad=0.40", facecolor="#000000", edgecolor="#000000"),
        transform=side_ax.transAxes
    )

    y = 0.932
    for sec_title, items in sections:
        side_ax.text(
            0.04, y, sec_title.upper(),
            fontsize=8.0, fontweight="heavy", color="#000000",
            ha="left", va="center", transform=side_ax.transAxes
        )
        y -= 0.012
        side_ax.plot([0.04, 0.96], [y, y], color="#000000", linewidth=1.0, transform=side_ax.transAxes)
        y -= 0.018

        for code_str, desc_str in items:
            side_ax.text(
                0.04, y, code_str,
                fontsize=7.0, fontweight="heavy", color="#000000",
                ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="#FFFFFF", edgecolor="#000000", linewidth=0.8),
                transform=side_ax.transAxes
            )
            side_ax.text(
                0.25, y, desc_str,
                fontsize=7.0,
                fontweight="bold" if any(k in desc_str for k in ("Vicepresidenza", "Insegnanti", "Segreteria", "Ristoro")) else "normal",
                color="#000000",
                ha="left", va="center", transform=side_ax.transAxes
            )
            y -= 0.0245
        y -= 0.012


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
    ax0 = fig0.add_axes([0.02, 0.082, 0.72, 0.805])
    draw_floor_bw(ax0, geom_0, rooms_0, (4.2, 43.2), (1.0, 32.3), scale_factor=0.92)
    add_poster_header_bw(
        fig0, 0,
        "PIANO TERRA — INGRESSO, AULE, LABORATORI, PALESTRA E AULA INSEGNANTI",
        "Aule Didattiche 014–022  •  Lab. Linux (018), Multimediale (020-021), Officina (026)  •  Aula Insegnanti (028)"
    )
    add_legend_bw(fig0)
    sections_0 = [
        ("Aule Didattiche", [
            ("014", "Aula didattica (Ala Nord-Est)"),
            ("015", "Aula didattica (Ala Est)"),
            ("016", "Aula didattica (Ala Est)"),
            ("017", "Aula didattica (Ala Centro-Est)"),
            ("019", "Aula didattica (Ala Nord-Ovest)"),
            ("022", "Aula didattica (Ala Sud-Ovest)"),
        ]),
        ("Laboratori & Officina", [
            ("018", "Lab. Linux (Ala Nord)"),
            ("020-021", "Lab. Multimediale (Ala Ovest)"),
            ("024-025", "Laboratori 1 e 2 (Blocco Est)"),
            ("026", "Officina Meccanica (Blocco Est)"),
            ("030-031", "Laboratori 4 e 5 (Ala Ovest)"),
        ]),
        ("Uffici, Docenti & Ristoro", [
            ("028", "Aula Insegnanti (Ala Sud)"),
            ("060", "Vicepresidenza (Centro-Sud)"),
            ("035", "Segreteria Didattica (Centro-Est)"),
            ("069", "Area Ristoro / Bar (Atrio Sud)"),
            ("009", "Infermeria (Lato Palestra)"),
            ("070", "Archivio (Lato Est)"),
        ]),
        ("Sport, Studio & Accessi", [
            ("004", "Palestra (Blocco Ovest)"),
            ("005-006", "Spogliatoi Palestra (Ovest)"),
            ("058-059", "Biblioteca d'Istituto (Centro)"),
            ("032-033", "Agorà Studio (Centro)"),
            ("029", "Ingresso Principale (Atrio Sud)"),
            ("037", "Entrata Palestra (Accesso Ovest)"),
        ]),
    ]
    add_sidebar_bw(fig0, "PIANO TERRA", sections_0)
    save_poster(fig0, "0_Cartello_Piano_Terra")

    # ----------------------------------------------------
    # 2. CARTELLO PRIMO PIANO
    # ----------------------------------------------------
    fig1 = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    ax1 = fig1.add_axes([0.02, 0.082, 0.72, 0.805])
    draw_floor_bw(ax1, geom_1, rooms_1, (4.2, 43.2), (1.0, 32.3), scale_factor=0.92)
    add_poster_header_bw(
        fig1, 1,
        "1° PIANO — AULE DIDATTICHE, LABORATORI, SEGRETERIA E VICEPRESIDENZA",
        "Aule 110–134  •  Lab. Costruzioni (118), Chimica (125), Biologia (126), Disegno (129), Fisica (135)"
    )
    add_legend_bw(fig1)
    sections_1 = [
        ("Aule Didattiche", [
            ("110", "Aula didattica (Ala Nord-Est)"),
            ("111", "Aula didattica (Ala Est)"),
            ("112", "Aula didattica (Ala Est)"),
            ("113", "Aula didattica (Ala Centro-Est)"),
            ("114", "Aula didattica (Ala Sud-Est)"),
            ("115", "Aula didattica (Ala Sud)"),
            ("119", "Aula didattica (Ala Nord)"),
            ("134", "Aula didattica (Ala Sud-Ovest)"),
        ]),
        ("Grandi Laboratori", [
            ("116-117", "Lab. CAD-Automaz. (Ovest)"),
            ("118", "Lab. Costruzioni (Nord-Ovest)"),
            ("125", "Lab. Chimica (Blocco Est)"),
            ("126", "Lab. Biologia (Blocco Est)"),
            ("129", "Lab. Disegno (Corpo Centro)"),
            ("135", "Lab. Fisica (Centro-Sud)"),
        ]),
        ("Aule Informali & Studio", [
            ("128", "Aula Informale (Centro-Nord)"),
            ("130", "Aula Informale (Ala Ovest)"),
            ("131", "Aula Informale (Ala Ovest)"),
            ("137", "Spazio Studio Connettivo"),
        ]),
        ("Dirigenza, Uffici & Accessi", [
            ("104-106", "Uffici & Segreteria (Sud-Ovest)"),
            ("107", "Ufficio Vicepresidenza (Sud-Ovest)"),
            ("046", "Ascensore Centrale (Tutti i piani)"),
            ("SCALE", "Scale Principali (Nord, Centro, Est)"),
        ]),
    ]
    add_sidebar_bw(fig1, "PRIMO PIANO", sections_1)
    save_poster(fig1, "1_Cartello_Piano_Primo")

    # ----------------------------------------------------
    # 3. CARTELLO SECONDO PIANO
    # ----------------------------------------------------
    fig2 = plt.figure(figsize=A3_INCHES, dpi=300, facecolor="#FFFFFF")
    ax2 = fig2.add_axes([0.02, 0.082, 0.72, 0.805])
    draw_floor_bw(ax2, geom_2, rooms_2, (4.0, 22.8), (1.0, 22.9), scale_factor=0.95)
    add_poster_header_bw(
        fig2, 2,
        "2° PIANO — AULE DIDATTICHE, INFORMATICA, ELETTRONICA, SISTEMI E LINGUE",
        "Aule 201–224  •  Lab. Informatica (206-207), Elettronica (208), Lingue (210), Sistemi (223)"
    )
    add_legend_bw(fig2)
    sections_2 = [
        ("Aule Didattiche", [
            ("201", "Aula didattica (Ala Nord-Est)"),
            ("202", "Aula didattica (Ala Est)"),
            ("203", "Aula didattica (Ala Est)"),
            ("204", "Aula didattica (Ala Sud-Est)"),
            ("205", "Aula didattica (Ala Sud)"),
            ("209", "Aula didattica (Ala Centro-Est)"),
            ("224", "Aula didattica (Ala Sud-Ovest)"),
        ]),
        ("Laboratori Specialistici", [
            ("206", "Lab. Informatica Sud (Ala Ovest)"),
            ("207", "Lab. Informatica Nord (Ala Ovest)"),
            ("208", "Lab. Elettronica (Nord-Ovest)"),
            ("210", "Lab. Lingue (Ala Nord)"),
            ("223", "Lab. Sistemi & Reti (Ala Sud)"),
        ]),
        ("Aule Informali & Studio", [
            ("213", "Aula Informale (Ala Ovest)"),
            ("214", "Laboratorio / Aula (Ala Ovest)"),
            ("221", "Laboratorio / Studio (Centro)"),
            ("211-212", "Spazi Studio (Nord & Sud)"),
            ("225", "Spazio Studio (Ala Sud)"),
        ]),
        ("Connettivo & Servizi", [
            ("046", "Ascensore Centrale (Tutti i piani)"),
            ("215", "Scala Centrale / Connettivo"),
            ("SCALE", "Scale Nord e Sud di Sicurezza"),
            ("WC", "Servizi Igienici (Nord, Centro, Sud)"),
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
            ("Lab. Linux 018", "PIANO TERRA", "Locale 018 (Ala Nord)"),
            ("Lab. Multimediale", "PIANO TERRA", "Locali 020 – 021 (Ovest)"),
            ("Lab 1 & Lab 2", "PIANO TERRA", "Locali 024 – 025 (Est)"),
            ("Officina Meccanica", "PIANO TERRA", "Locale 026 (Blocco Est)"),
            ("Lab 4 & Lab 5", "PIANO TERRA", "Locali 031 e 030 (Ovest)"),
            ("Lab. CAD-Automaz.", "1° PIANO", "Locali 116 – 117 (Ovest)"),
            ("Lab. Costruzioni", "1° PIANO", "Locale 118 (Nord-Ovest)"),
            ("Lab. Chimica", "1° PIANO", "Locale 125 (Blocco Est)"),
            ("Lab. Biologia", "1° PIANO", "Locale 126 (Blocco Est)"),
            ("Lab. Disegno", "1° PIANO", "Locale 129 (Centro)"),
            ("Lab. Fisica", "1° PIANO", "Locale 135 (Centro-Sud)"),
            ("Lab. Informatica", "2° PIANO", "Locali 206 – 207 (Ovest)"),
            ("Lab. Elettronica", "2° PIANO", "Locale 208 (Nord-Ovest)"),
            ("Lab. Lingue", "2° PIANO", "Locale 210 (Ala Nord)"),
            ("Lab. Sistemi", "2° PIANO", "Locale 223 (Ala Sud)"),
        ]),
        ("4. UFFICI, DOCENTI & RISTORO", [
            ("Ingresso / Atrio", "PIANO TERRA", "Locali 029 / 036 (Sud-Ovest)"),
            ("Aula Insegnanti", "PIANO TERRA", "Locale 028 (ex Mensa)"),
            ("Vicepresidenza", "PIANO TERRA", "Locale 060 (Centro-Sud)"),
            ("Segreteria Didattica", "PIANO TERRA", "Locale 035 (Centro-Est)"),
            ("Area Ristoro / Bar", "PIANO TERRA", "Locale 069 (Atrio Sud)"),
            ("Palestra & Spogliatoi", "PIANO TERRA", "Locali 004 – 008 (Ovest)"),
            ("Infermeria", "PIANO TERRA", "Locale 009 (Lato Palestra)"),
            ("Segreteria / Dirigenza", "1° PIANO", "Locali 104, 105, 106, 138"),
            ("Uff. Vicepresidenza", "1° PIANO", "Locale 107 (Ala Sud-Ovest)"),
            ("Ascensore Centrale", "TUTTI I PIANI", "Locale 046 (Collega 0, 1, 2)"),
            ("Scale Principali", "TUTTI I PIANI", "Scala Centrale, Nord, Est, Sud"),
            ("Servizi Igienici (WC)", "TUTTI I PIANI", "Presenti in ogni ala"),
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
