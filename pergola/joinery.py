"""Timber-joint detail drawings — how the members are cut where they meet.

The box model lets members interpenetrate for simplicity (e.g. a flush rafter
runs the full depth straight *through* the beam it crosses). On the bench those
overlaps have to be cut away, so this module derives — from the same
:class:`Config` — the construction details that the plan/elevations cannot show:

  * ``detail_kaemmung``  — the cross-lap (Kreuzüberblattung / Kämmung) where a
    flush rafter crosses a perimeter beam, tops kept flush;
  * ``detail_corner``    — the corner half-lap (Eck-Überblattung) where two ring
    beams meet over a post;
  * ``detail_locator``   — a plan locating every joint, drawn from the box model.

Everything here is pure matplotlib/numpy off the box model + config numbers — no
build123d (kept to ``solid.py``), like the rest of the drawing code.

The flush geometry (see ``build.py``): the rafter top is flush with the beam
top, so the rafter occupies the top ``rafter.height`` of the taller beam. To
keep the tops flush while leaving each member as much section as possible, that
overlap is split between the two: a channel ``DB`` deep into the beam top and a
channel ``DR`` deep into the rafter underside, with ``DB + DR == rafter.height``.
We split it evenly by default; bias it (keeping the sum) to favour the
load-bearing member.
"""
from __future__ import annotations

import math
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrow
import matplotlib.patches as mpatches
import numpy as np

from . import style
from .geometry import X, Y, Z, bounds
from .model import Config

FIGSIZE = (11.0, 8.5)
DPI = 150

# Joint colours, reused from the element palette so details match the views.
_BEAM = style.CATEGORY_STYLE["beam"]
_RAF = style.CATEGORY_STYLE["rafter"]
_CUT = {"facecolor": "white", "edgecolor": "#555", "hatch": "////", "linewidth": 0.8}
_DIM = style.DIM_COLOR


# --------------------------------------------------------------------------- #
#  Small dimension helpers (mm coords, tuned to the detail scale)
# --------------------------------------------------------------------------- #
def _dh(ax, x1, x2, y, text, tick):
    ax.annotate("", (x1, y), (x2, y), arrowprops=dict(arrowstyle="<->", color=_DIM, lw=0.9))
    for x in (x1, x2):
        ax.plot([x, x], [y - tick, y + tick], color=_DIM, lw=0.7)
    ax.text((x1 + x2) / 2, y + tick * 1.4, text, ha="center", va="bottom",
            fontsize=style.DIM_FONTSIZE, color=_DIM)


def _dv(ax, y1, y2, x, text, tick, side="right"):
    ax.annotate("", (x, y1), (x, y2), arrowprops=dict(arrowstyle="<->", color=_DIM, lw=0.9))
    for y in (y1, y2):
        ax.plot([x - tick, x + tick], [y, y], color=_DIM, lw=0.7)
    dx = tick * 1.4 if side == "right" else -tick * 1.4
    ha = "left" if side == "right" else "right"
    ax.text(x + dx, (y1 + y2) / 2, text, ha=ha, va="center", rotation=90,
            fontsize=style.DIM_FONTSIZE, color=_DIM)


def _panel(ax, title):
    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal")
    ax.axis("off")


def _fmt(v: float) -> str:
    return f"{round(v):d}"


# --------------------------------------------------------------------------- #
#  Detail 1: the cross-lap (Kämmung) where a flush rafter crosses a beam
# --------------------------------------------------------------------------- #
def _render_kaemmung(cfg: Config):
    pg = cfg.pergola
    bw, bh = pg.beams.width, pg.beams.height
    rw, rh = pg.rafters.width, pg.rafters.height
    tilt = pg.roof.tilt_deg
    # Split the rh-deep overlap evenly between the two members (tops stay flush).
    db = round(rh / 2.0)       # channel depth into the beam top
    dr = rh - db               # channel depth into the rafter underside
    bear = bh - db             # bearing plane, above the beam underside
    tick = max(bw, bh) * 0.05

    fig, axs = plt.subplots(1, 3, figsize=(12.0, 5.0), dpi=DPI)
    fig.suptitle("Holzverbindung 1 — Kreuzüberblattung (Kämmung): Sparren kreuzt Ringbalken",
                 fontsize=style.TITLE_FONTSIZE, fontweight="bold", x=0.04, ha="left")
    fig.text(0.04, 0.9, f"Oberkanten bündig · Sparren {_fmt(rw)}×{_fmt(rh)} · "
             f"Balken {_fmt(bw)}×{_fmt(bh)} · Dachneigung {_fmt(tilt)}°    ·    Maße in "
             f"{cfg.units}", fontsize=style.LABEL_FONTSIZE, color="#555", ha="left")

    # ---- Panel 1: beam end-on (bw x bh) with a channel in its TOP edge ------
    ax = axs[0]
    _panel(ax, f"1) Ringbalken {_fmt(bw)}×{_fmt(bh)}\nKanal in OBERKANTE: {_fmt(rw)} breit × {_fmt(db)} tief")
    ax.add_patch(Rectangle((0, 0), bw, bh, facecolor=_BEAM["face"], edgecolor=_BEAM["edge"], lw=1.4))
    ax.add_patch(Rectangle(((bw - rw) / 2, bh - db), rw, db, **_CUT))
    _dh(ax, (bw - rw) / 2, (bw + rw) / 2, bh + tick * 2, f"{_fmt(rw)}", tick)
    _dv(ax, bh - db, bh, bw + tick * 2, f"{_fmt(db)}", tick)
    _dv(ax, 0, bh, -tick * 2, f"{_fmt(bh)}", tick, side="left")
    ax.text(bw / 2, (bh - db) / 2, "Balken\nbleibt", ha="center", va="center", fontsize=8)
    ax.set_xlim(-bw * 0.9, bw * 1.7); ax.set_ylim(-bh * 0.12, bh * 1.2)

    # ---- Panel 2: rafter along its run, channel in its UNDERSIDE ------------
    ax = axs[1]
    Lr = bw * 2.2
    _panel(ax, f"2) Sparren {_fmt(rw)}×{_fmt(rh)}\nKanal in UNTERKANTE: {_fmt(bw)} breit × {_fmt(dr)} tief")
    ax.add_patch(Rectangle((0, 0), Lr, rh, facecolor=_RAF["face"], edgecolor=_RAF["edge"], lw=1.4))
    ax.add_patch(Rectangle(((Lr - bw) / 2, 0), bw, dr, **_CUT))
    _dh(ax, (Lr - bw) / 2, (Lr + bw) / 2, -tick * 2.4, f"{_fmt(bw)}", tick)
    _dv(ax, 0, rh, -tick * 2, f"{_fmt(rh)}", tick, side="left")
    _dv(ax, 0, dr, Lr + tick * 2, f"{_fmt(dr)}", tick)
    ax.text(Lr / 2, (dr + rh) / 2, "Sparren bleibt", ha="center", va="center", fontsize=8)
    ax.set_xlim(-Lr * 0.18, Lr * 1.2); ax.set_ylim(-rh * 0.9, rh * 1.25)

    # ---- Panel 3: assembled section, tops flush ----------------------------
    ax = axs[2]
    _panel(ax, "3) Zusammengesetzt — Oberkanten BÜNDIG\nSparren fällt von oben ein")
    ax.add_patch(Rectangle((0, 0), bw, bh, facecolor=_BEAM["face"], edgecolor=_BEAM["edge"], lw=1.4))
    # the rafter now fills the beam's top channel (width rw, bear..bh)
    ax.add_patch(Rectangle(((bw - rw) / 2, bear), rw, bh - bear,
                           facecolor=_RAF["face"], edgecolor=_RAF["edge"], lw=1.2))
    ax.plot([0, bw], [bear, bear], color=_RAF["edge"], lw=1.6)
    ax.text(bw / 2, (bear + bh) / 2, "Sparren", ha="center", va="center", fontsize=7.5,
            color=_RAF["edge"], fontweight="bold")
    ax.text(bw / 2, bear / 2, "Balken", ha="center", va="center", fontsize=7.5,
            color=_BEAM["edge"], fontweight="bold")
    ax.add_patch(FancyArrow(bw / 2, bh * 1.45, 0, -bh * 0.28, width=bw * 0.03,
                            head_width=bw * 0.13, head_length=bh * 0.1, color="black"))
    ax.text(bw / 2, bh * 1.5, "einsetzen", ha="center", fontsize=8)
    ax.annotate(f"Auflagerfläche (waagerecht)\nz = +{_fmt(bear)}", (0, bear),
                (-bw * 1.05, bear * 0.55), fontsize=7,
                arrowprops=dict(arrowstyle="->", color="#444"))
    ax.annotate("Oberkanten bündig\n= eine Dachebene", (bw / 2, bh),
                (bw * 1.1, bh * 1.12), fontsize=7,
                arrowprops=dict(arrowstyle="->", color="#444"))
    _dv(ax, bear, bh, bw + tick * 2, f"{_fmt(bh - bear)}", tick)
    ax.set_xlim(-bw * 1.6, bw * 2.1); ax.set_ylim(-bh * 0.12, bh * 1.65)

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    return fig


# --------------------------------------------------------------------------- #
#  Detail 2: the corner half-lap (Eck-Überblattung) of two ring beams
# --------------------------------------------------------------------------- #
def _render_corner(cfg: Config):
    pg = cfg.pergola
    bw, bh = pg.beams.width, pg.beams.height
    psx, psy = pg.posts.size_x, pg.posts.size_y
    hh = bh / 2.0              # each beam halved in height over the lap
    tick = max(bw, bh) * 0.05

    fig, axs = plt.subplots(1, 2, figsize=(11.0, 5.8), dpi=DPI)
    fig.suptitle("Holzverbindung 2 — Eck-Überblattung: zwei Ringbalken treffen über dem Pfosten",
                 fontsize=style.TITLE_FONTSIZE, fontweight="bold", x=0.04, ha="left")
    fig.text(0.04, 0.9, f"beide Balken {_fmt(bw)}×{_fmt(bh)}, je auf halber Höhe "
             f"({_fmt(hh)}) ausgeklinkt    ·    Maße in {cfg.units}",
             fontsize=style.LABEL_FONTSIZE, color="#555", ha="left")

    # ---- Panel 1: the two beams exploded (elevation), each half-lapped -----
    ax = axs[0]
    _panel(ax, "1) Beide Balken ausgeklinkt (je halbe Höhe)")
    LA = bw * 3.0
    # Beam A (front/back, runs in x): full section, TOP half removed over the lap (right end).
    ax.add_patch(Rectangle((0, 0), LA, bh, facecolor=_BEAM["face"], edgecolor=_BEAM["edge"], lw=1.4))
    ax.add_patch(Rectangle((LA - bw, hh), bw, hh, **_CUT))            # removed top half at lap
    ax.text(LA * 0.45, bh / 2, "Balken A (in x)\nOberseite weg", ha="center", va="center", fontsize=7.5)
    # Beam B (side, runs in y): drawn offset upward; full section, BOTTOM half removed at the lap.
    yb = bh * 1.6
    ax.add_patch(Rectangle((0, yb), LA, bh, facecolor=_RAF["face"], edgecolor=_RAF["edge"], lw=1.4))
    ax.add_patch(Rectangle((LA - bw, yb), bw, hh, **_CUT))           # removed bottom half at lap
    ax.text(LA * 0.45, yb + bh / 2, "Balken B (in y)\nUnterseite weg", ha="center", va="center", fontsize=7.5)
    _dv(ax, 0, bh, -tick * 2, f"{_fmt(bh)}", tick, side="left")
    _dh(ax, LA - bw, LA, -tick * 2.6, f"{_fmt(bw)} (Überblattung)", tick)
    ax.set_xlim(-bw * 1.1, LA + bw * 0.3); ax.set_ylim(-bh * 0.45, yb + bh * 1.1)

    # ---- Panel 2: assembled on the post ------------------------------------
    ax = axs[1]
    _panel(ax, "2) Zusammengelegt, auf den Pfosten verdübelt")
    post_top = 0.0
    # post
    ax.add_patch(Rectangle((-psx / 2, post_top - bh * 1.3), psx, bh * 1.3,
                           facecolor=style.CATEGORY_STYLE["post"]["face"],
                           edgecolor=style.CATEGORY_STYLE["post"]["edge"], lw=1.4))
    # beam A bottom half + beam B top half = full height bh
    ax.add_patch(Rectangle((-bw * 1.6, post_top), bw * 3.2, hh, facecolor=_BEAM["face"],
                           edgecolor=_BEAM["edge"], lw=1.4))
    ax.add_patch(Rectangle((-bw / 2, post_top + hh), bw, hh, facecolor=_RAF["face"],
                           edgecolor=_RAF["edge"], lw=1.4))
    ax.plot([-bw / 2, bw / 2], [hh, hh], color="#333", lw=1.0, ls=(0, (4, 3)))
    ax.text(bw * 1.2, hh / 2, "Balken A", fontsize=7.5, color=_BEAM["edge"], va="center")
    ax.text(0, hh + hh / 2, "Balken B", fontsize=7.5, color=_RAF["edge"], ha="center", va="center")
    ax.text(0, post_top - bh * 0.7, "Pfosten", fontsize=7.5,
            color=style.CATEGORY_STYLE["post"]["edge"], ha="center", va="center")
    # dowel pin through the lap
    ax.plot([0, 0], [post_top - bh * 0.15, bh], color="#5c3d23", lw=2.4)
    ax.annotate("Holzdübel / Schraube\nvon oben durch beide Lagen", (0, bh),
                (bw * 1.0, bh * 1.25), fontsize=7, arrowprops=dict(arrowstyle="->", color="#444"))
    _dv(ax, post_top, bh, bw * 1.75, f"{_fmt(bh)}", tick)
    ax.set_xlim(-bw * 2.1, bw * 3.0); ax.set_ylim(post_top - bh * 1.45, bh * 1.5)

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    return fig


# --------------------------------------------------------------------------- #
#  Detail 3: locator plan — every joint, drawn from the box model
# --------------------------------------------------------------------------- #
def _plan_bbox(box):
    poly = np.array(box.poly_2d(X, Y))
    return poly[:, 0].min(), poly[:, 0].max(), poly[:, 1].min(), poly[:, 1].max()


def _render_locator(elements, cfg: Config):
    pg = cfg.pergola
    fig, ax = plt.subplots(figsize=(8.6, 8.6), dpi=DPI)
    fig.suptitle("Holzverbindungen — Lageplan: wo sitzt welcher Stoß?",
                 fontsize=style.TITLE_FONTSIZE, fontweight="bold", x=0.04, ha="left")

    beams = [b for b in elements if b.category == "beam"]
    rafters = [b for b in elements if b.category == "rafter"]
    posts = [b for b in elements if b.category == "post"]

    # Draw the ring + rafters as their plan silhouettes (handles tilted prisms).
    for b in beams + rafters:
        st = style.style_for(b.category)
        ax.add_patch(mpatches.Polygon(b.poly_2d(X, Y), closed=True, facecolor=st["face"],
                                      edgecolor=st["edge"], lw=1.0, zorder=2))
    for p in posts:
        st = style.style_for("post")
        ax.add_patch(mpatches.Polygon(p.poly_2d(X, Y), closed=True, facecolor=st["face"],
                                      edgecolor=st["edge"], lw=0.8, zorder=3))

    # Classify beams by plan aspect: cross beams (run in x) vs side beams (run in y).
    cross_y, side_x = [], []
    for b in beams:
        x0, x1, y0, y1 = _plan_bbox(b)
        if (x1 - x0) >= (y1 - y0):
            cross_y.append((y0 + y1) / 2)          # front/back beam, at this y
        else:
            side_x.append((x0 + x1) / 2)           # side beam, at this x
    raf_x = [(_plan_bbox(r)[0] + _plan_bbox(r)[1]) / 2 for r in rafters]

    r_mark = max(pg.beams.width, 60) * 0.9
    # Red rings: rafter × cross-beam crossings (Kämmung).
    for cx in raf_x:
        for cy in cross_y:
            ax.add_patch(plt.Circle((cx, cy), r_mark, fill=False, color="#c0392b", lw=2.0, zorder=6))
    # Green squares: ring corners (Eck-Überblattung).
    for cx in side_x:
        for cy in cross_y:
            s = r_mark * 1.5
            ax.add_patch(Rectangle((cx - s, cy - s), 2 * s, 2 * s, fill=False,
                                   color="#1e8449", lw=2.0, zorder=6))

    # Mark the house side (max y), where flush rafters cantilever past the beam.
    lo, hi = bounds(elements)
    ax.annotate("Hauswand-Seite — Sparren kragen über den Balken hinaus",
                ((lo[X] + hi[X]) / 2, max(cross_y) if cross_y else hi[Y]),
                ((lo[X] + hi[X]) / 2, hi[Y] + (hi[Y] - lo[Y]) * 0.07),
                ha="center", fontsize=8, color="#555",
                arrowprops=dict(arrowstyle="->", color="#888"))

    legend = [
        mpatches.Patch(facecolor=_BEAM["face"], edgecolor=_BEAM["edge"], label="Ringbalken (Rahmenring)"),
        mpatches.Patch(facecolor=_RAF["face"], edgecolor=_RAF["edge"], label="Sparren (nur innen)"),
        mpatches.Patch(facecolor="white", edgecolor="#c0392b", label="Kreuzüberblattung (Sparren × Balken)"),
        mpatches.Patch(facecolor="white", edgecolor="#1e8449", label="Eck-Überblattung (Balken × Balken, über Pfosten)"),
    ]
    ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(0, -0.02),
              fontsize=8, frameon=False, ncol=2)
    ax.set_aspect("equal")
    ax.axis("off")
    span = max(hi[X] - lo[X], hi[Y] - lo[Y])
    ax.set_xlim(lo[X] - span * 0.08, hi[X] + span * 0.08)
    ax.set_ylim(lo[Y] - span * 0.12, hi[Y] + span * 0.14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


# --------------------------------------------------------------------------- #
#  Public entry: build the joinery detail figures for this config
# --------------------------------------------------------------------------- #
def render_joinery(elements, cfg: Config) -> List[Tuple[str, str, "plt.Figure", str]]:
    """Return ``(key, title, figure, html_note)`` for each joinery detail.

    Only meaningful for ``framing: flush`` (the housed-rafter / perimeter-ring
    build, where members must interlock). For ``stacked`` framing the rafters
    simply rest on top of the beams, so the list is empty.
    """
    if cfg.pergola.framing != "flush":
        return []

    pg = cfg.pergola
    rh = pg.rafters.height
    db = round(rh / 2.0)
    bear = pg.beams.height - db
    tilt = pg.roof.tilt_deg

    return [
        ("detail_locator", "Holzverbindungen — Lageplan",
         _render_locator(elements, cfg),
         "Übersicht, wo welche Verbindung sitzt: rote Ringe = Sparren kreuzt einen "
         "Front-/Hinterbalken (Kämmung); grüne Quadrate = die zwei Seitenbalken des "
         "Rahmenrings treffen über einem Pfosten auf die Querbalken (Eck-Überblattung). "
         "Die Sparren (60×80) sind nur die <b>inneren</b> Hölzer — die äußeren Längskanten "
         "sind <b>Seitenbalken</b> des Rings, keine Sparren."),
        ("detail_kaemmung", "Detail 1 — Kreuzüberblattung (Sparren × Balken)",
         _render_kaemmung(cfg),
         f"Aus beiden Hölzern wird ein Kanal ausgenommen, der Sparren fällt von oben ein, "
         f"die Oberkanten fluchten (eine Dachebene). Die Überlappung von {_fmt(rh)} mm wird "
         f"geteilt: {_fmt(db)} mm aus der Balkenoberkante + {_fmt(rh - db)} mm aus der "
         f"Sparrenunterkante; Summe = Sparrenhöhe, also Oberkanten bündig. Auflagerfläche "
         f"<b>waagerecht</b> bei z = +{_fmt(bear)} mm schneiden — wegen der {_fmt(tilt)}°-"
         f"Neigung steht der Sparren sonst auf einer Kante."),
        ("detail_corner", "Detail 2 — Eck-Überblattung (Balken × Balken)",
         _render_corner(cfg),
         "An den vier Ecken treffen Seitenbalken und Front-/Hinterbalken über einem Pfosten "
         "aufeinander — beide gleich hoch. Klassisches Halbholz: jeden Balken auf halber Höhe "
         "ausklinken, ineinanderlegen, von oben mit Dübel/Schraube auf den Pfosten verbinden."),
    ]
