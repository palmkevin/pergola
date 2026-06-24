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

The flush geometry (see ``build.py``): each rafter crosses OVER the front/house
beams and ends flush with their outer faces (no overhang). Its top is flush with
the beam top, so it occupies the top ``rafter.height`` of the taller beam. To
keep the tops flush, that overlap is split between the two as a cross-lap: a
channel ``DB`` deep into the beam top and a channel ``DR`` deep into the rafter
underside, with ``DB + DR == rafter.height``.

The split is biased to PROTECT the beam: the beam-top notch ``DB`` is capped at
``MAX_BEAM_NOTCH`` mm (35), so the 120 mm ring beam keeps as much depth as it
can. The remainder goes into the rafter — and that is "free" structurally,
because the rafter is notched exactly at its END, i.e. over its support, where
its bending moment is ~zero. For the sample (rafter 80, beam 120) this gives
DB = 35 into the beam (leaving 85) and DR = 45 into the rafter.
"""
from __future__ import annotations

import math
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
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


def _panel(ax, title):
    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal")
    ax.axis("off")


def _fmt(v: float) -> str:
    return f"{round(v):d}"


# --------------------------------------------------------------------------- #
#  Tiny isometric helper — the joints are inherently 3D (two perpendicular
#  members, and *which face* gets notched), so the details are drawn as simple
#  axonometric boxes rather than orthographic sections (which a layperson
#  cannot mentally re-assemble). x -> right, z -> up, y (depth) -> up-right.
# --------------------------------------------------------------------------- #
_ISO_A = math.radians(27.0)
_ISO_DS = 0.62                      # depth compression along y


def _iso(x, y, z):
    return (x + math.cos(_ISO_A) * _ISO_DS * y, z + math.sin(_ISO_A) * _ISO_DS * y)


def _shade(hex_color: str, f: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * f))) for c in (r, g, b))


def _box3d(ax, x0, x1, y0, y1, z0, z1, face, edge, z=2.0, alpha=1.0):
    """Draw the three visible faces (top, front, right) of an axis-aligned box."""
    top = [_iso(x0, y0, z1), _iso(x1, y0, z1), _iso(x1, y1, z1), _iso(x0, y1, z1)]
    front = [_iso(x0, y0, z0), _iso(x1, y0, z0), _iso(x1, y0, z1), _iso(x0, y0, z1)]
    right = [_iso(x1, y0, z0), _iso(x1, y1, z0), _iso(x1, y1, z1), _iso(x1, y0, z1)]
    for poly, fc, zi in ((top, face, z + 0.2), (front, _shade(face, 0.85), z + 0.1),
                         (right, _shade(face, 0.70), z)):
        ax.add_patch(Polygon(poly, closed=True, facecolor=fc, edgecolor=edge,
                             lw=1.0, alpha=alpha, zorder=zi, joinstyle="round"))


def _ghost3d(ax, x0, x1, y0, y1, z0, z1, color="#c0392b", z=6.0):
    """Dashed wireframe of a box — the chunk that gets sawn out."""
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    for a, b in edges:
        pa, pb = _iso(*c[a]), _iso(*c[b])
        ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color=color, lw=1.1,
                ls=(0, (3, 2)), zorder=z)


def _iso_arrow(ax, x, y, z0, z1, text):
    """A vertical drop arrow in iso space, with a label."""
    p0, p1 = _iso(x, y, z0), _iso(x, y, z1)
    ax.annotate("", p1, p0, arrowprops=dict(arrowstyle="-|>", color="#222", lw=2.2))
    pm = _iso(x, y, (z0 + z1) / 2)
    ax.text(pm[0] + 6, pm[1], text, fontsize=8, ha="left", va="center")


# --------------------------------------------------------------------------- #
#  Detail 1: the cross-lap (Kämmung) where a flush rafter crosses a beam
# --------------------------------------------------------------------------- #
MAX_BEAM_NOTCH = 35   # mm — deepest cut allowed into the load-bearing ring beam's top


def _lap_split(rh: float):
    """Cross-lap depths (DB into beam top, DR into rafter underside), DB+DR=rh.

    The deeper cut goes into the RAFTER, at its zero-moment support end where
    depth costs no bending capacity; the beam-top notch is capped at
    ``MAX_BEAM_NOTCH`` mm so the main ring beam keeps the most section it can. An
    even split (rh/2) is used only when that is already within the cap. For the
    sample (rafter 80, beam 120): DB = 35 into the beam (leaving 85), DR = 45.
    """
    db = min(round(rh / 2.0), MAX_BEAM_NOTCH)   # channel depth into the beam top
    dr = round(rh) - db                          # channel depth into the rafter underside
    return db, dr


def _render_kaemmung(cfg: Config):
    pg = cfg.pergola
    bw, bh = pg.beams.width, pg.beams.height
    rw, rh = pg.rafters.width, pg.rafters.height
    db, dr = _lap_split(rh)
    bear = bh - db             # bearing plane (notch floor), above the beam underside

    fig, axs = plt.subplots(1, 2, figsize=(12.0, 6.2), dpi=DPI)
    fig.suptitle("Holzverbindung 1 — Kreuzüberblattung (Kämmung): Sparren kreuzt Ringbalken",
                 fontsize=style.TITLE_FONTSIZE, fontweight="bold", x=0.04, ha="left")
    fig.text(0.04, 0.92, f"Sparren {_fmt(rw)}×{_fmt(rh)} kreuzt den Balken {_fmt(bw)}×{_fmt(bh)} "
             f"und endet bündig an dessen Außenkante — kein Überstand · Maße in {cfg.units}",
             fontsize=style.LABEL_FONTSIZE, color="#555", ha="left")

    Lb = bw * 4.0                  # beam length shown (runs in x); beam spans y [0, bw]
    Rin = bw + bw * 2.0            # rafter runs from the OUTER face (y=0) into the bay (y=Rin)
    rx0, rx1 = (Lb - rw) / 2, (Lb + rw) / 2  # rafter x-band, centred on the beam

    # ---- Panel 1: exploded — saw these chunks out --------------------------
    ax = axs[0]
    _panel(ax, "1) Was wird ausgesägt? (auseinandergezogen)")
    # Beam, with the red ghost chunk removed from its TOP (rw wide × bw deep × db).
    _box3d(ax, 0, Lb, 0, bw, 0, bh, _BEAM["face"], _BEAM["edge"], z=2)
    _ghost3d(ax, rx0, rx1, 0, bw, bh - db, bh)
    pc = _iso((rx0 + rx1) / 2, bw, bh)
    ax.annotate(f"Balken: oben {_fmt(rw)}×{_fmt(bw)} ×\nnur Tiefe {_fmt(db)} heraus\n"
                f"(bleibt {_fmt(bh - db)} von {_fmt(bh)})",
                pc, (pc[0] + bw * 0.9, pc[1] + bh * 0.35), fontsize=7.5, color="#c0392b",
                arrowprops=dict(arrowstyle="->", color="#c0392b"))
    # Rafter, lifted above; notch removed from its UNDERSIDE at the END (y 0..bw).
    gap = bh * 1.7
    rz0, rz1 = bh + gap, bh + gap + rh
    _box3d(ax, rx0, rx1, 0, Rin, rz0, rz1, _RAF["face"], _RAF["edge"], z=4)
    _ghost3d(ax, rx0, rx1, 0, bw, rz0, rz0 + dr)
    pr = _iso(rx0, 0, rz0)
    ax.annotate(f"Sparren: unten {_fmt(rw)}×{_fmt(bw)}\n× Tiefe {_fmt(dr)} heraus\n"
                f"(am SparrenENDE, dort\nkein Biegemoment)",
                pr, (pr[0] - bw * 1.6, pr[1] - bh * 0.2), fontsize=7.5, color="#c0392b",
                ha="right", arrowprops=dict(arrowstyle="->", color="#c0392b"))
    _iso_arrow(ax, (rx0 + rx1) / 2, bw * 0.5, rz0 - bh * 0.2, bh + bh * 0.25, "einsetzen")
    ax.set_xlim(-bw * 3.4, Lb + bw * 2.4); ax.set_ylim(-bh * 0.5, rz1 + bh * 0.7)

    # ---- Panel 2: assembled — tops flush, rafter end flush with outer face --
    ax = axs[1]
    _panel(ax, "2) Zusammengesteckt — Oberkanten bündig, Sparrenende bündig")
    # Draw back -> front. The rafter continues into the bay (y bw..Rin) at full
    # depth; over the beam (y 0..bw) its underside is notched up to `bear`; its
    # end face sits at y=0, flush with the beam's outer face — no overhang.
    _box3d(ax, rx0, rx1, bw, Rin, bh - rh, bh, _RAF["face"], _RAF["edge"], z=3)       # bay continuation
    _box3d(ax, 0, Lb, 0, bw, 0, bh, _BEAM["face"], _BEAM["edge"], z=4)                # beam
    _box3d(ax, rx0, rx1, 0, bw, bear, bh, _RAF["face"], _RAF["edge"], z=6)            # crossing (in notch)
    # tops-flush line across the top
    fa, fb = _iso(0, 0, bh), _iso(Lb, 0, bh)
    ax.plot([fa[0], fb[0]], [fa[1], fb[1]], color="#1e8449", lw=1.6, zorder=10)
    ax.annotate("Oberkanten bündig", _iso(Lb * 0.5, 0, bh),
                (_iso(Lb, 0, bh)[0] + bw * 0.2, _iso(Lb, 0, bh)[1] + bh * 0.6),
                fontsize=8, color="#1e8449", arrowprops=dict(arrowstyle="->", color="#1e8449"))
    # rafter end flush with the beam's outer (front, y=0) face — no overhang
    ef = _iso((rx0 + rx1) / 2, 0, (bear + bh) / 2)
    ax.annotate("Sparrenende bündig mit\nBalken-Außenkante\n(kein Überstand)", ef,
                (ef[0] - bw * 0.4, ef[1] - bh * 1.4), ha="center",
                fontsize=7.5, color="#1e8449", arrowprops=dict(arrowstyle="->", color="#1e8449"))
    # the bearing shoulder: the rafter rests on the notch floor at z = bear
    s0 = _iso(rx1, bw, bear)
    ax.annotate(f"Sparren liegt auf dem\nKanalboden auf (z = {_fmt(bear)})",
                s0, (s0[0] + bw * 0.6, s0[1] + bh * 1.4), ha="left",
                fontsize=7.5, color="#444", arrowprops=dict(arrowstyle="->", color="#444"))
    # rafter runs on into the bay (inner side)
    be = _iso((rx0 + rx1) / 2, Rin, bh)
    ax.annotate("", _iso((rx0 + rx1) / 2, Rin + bw * 1.1, bh), be,
                arrowprops=dict(arrowstyle="-|>", color="#444", lw=1.6))
    ax.text(_iso((rx0 + rx1) / 2, Rin + bw * 1.1, bh)[0],
            _iso((rx0 + rx1) / 2, Rin + bw * 1.1, bh)[1] + bh * 0.18,
            "Sparren läuft ins\nDachfeld weiter", fontsize=7.5, color="#444", ha="center")
    ax.set_xlim(-bw * 3.4, Lb + bw * 2.8); ax.set_ylim(-bh * 1.4, bh + bw * 2.6)

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    return fig


# --------------------------------------------------------------------------- #
#  Detail 2: the corner half-lap (Eck-Überblattung) of two ring beams
# --------------------------------------------------------------------------- #
def _render_corner(cfg: Config):
    pg = cfg.pergola
    bw, bh = pg.beams.width, pg.beams.height
    hh = bh / 2.0              # each beam halved in height over the lap

    fig, axs = plt.subplots(1, 2, figsize=(12.0, 6.2), dpi=DPI)
    fig.suptitle("Holzverbindung 2 — Eck-Überblattung: zwei Ringbalken treffen über dem Pfosten",
                 fontsize=style.TITLE_FONTSIZE, fontweight="bold", x=0.04, ha="left")
    fig.text(0.04, 0.92, f"Beide Balken {_fmt(bw)}×{_fmt(bh)}, im Überlappungsquadrat "
             f"({_fmt(bw)}×{_fmt(bw)}) je auf halbe Höhe ({_fmt(hh)}) ausgeklinkt → "
             f"{_fmt(hh)} + {_fmt(hh)} = {_fmt(bh)} (Höhe EINES Balkens, nicht zwei) · "
             f"Maße in {cfg.units}", fontsize=style.LABEL_FONTSIZE, color="#555", ha="left")

    arm = bw * 2.6                 # arm length each side of the corner
    lo, hi = arm, arm + bw         # the bw×bw overlap square sits at [lo, hi]²
    POST = style.CATEGORY_STYLE["post"]
    # Both members are beams; tint B a lighter beam shade (NOT the rafter colour)
    # just to tell the two ring beams apart.
    B_FACE = _shade(_BEAM["face"], 1.18)

    # ---- Panel 1: exploded — each beam loses HALF its height at the lap -----
    ax = axs[0]
    _panel(ax, "1) Was wird ausgesägt? (je halbe Höhe im Eck-Quadrat)")
    # Beam A runs in x (its bar lies along y = [lo, hi]); ghost removes its TOP half.
    _box3d(ax, 0, hi, lo, hi, 0, bh, _BEAM["face"], _BEAM["edge"], z=2)
    _ghost3d(ax, lo, hi, lo, hi, hh, bh)
    pa = _iso(hi, (lo + hi) / 2, bh)
    ax.annotate("Balken A:\nOberseite weg", pa,
                (pa[0] + bw * 0.5, pa[1] - bh * 0.9), fontsize=7.5, color="#c0392b",
                ha="left", arrowprops=dict(arrowstyle="->", color="#c0392b"))
    # Beam B runs in y (bar along x = [lo, hi]); lifted up, ghost removes its BOTTOM half.
    gap = bh * 1.9
    bz0 = bh + gap
    _box3d(ax, lo, hi, 0, hi, bz0, bz0 + bh, B_FACE, _BEAM["edge"], z=4)
    _ghost3d(ax, lo, hi, lo, hi, bz0, bz0 + hh)
    pb = _iso(lo, lo, bz0)
    ax.annotate("Balken B:\nUnterseite weg", pb,
                (pb[0] - bw * 2.2, pb[1] + bh * 0.15), fontsize=7.5, color="#c0392b",
                ha="right", arrowprops=dict(arrowstyle="->", color="#c0392b"))
    _iso_arrow(ax, (lo + hi) / 2, (lo + hi) / 2, bz0 - bh * 0.2, bh + bh * 0.25, "absenken")
    ax.set_xlim(-bw * 3.4, hi + bw * 3.4); ax.set_ylim(-bh * 0.5, bz0 + bh * 1.4)

    # ---- Panel 2: assembled on the post — corner is ONE beam high ----------
    ax = axs[1]
    _panel(ax, f"2) Zusammengelegt: Eck-Höhe = {_fmt(bh)} (= ein Balken), auf dem Pfosten")
    # post under the overlap square
    _box3d(ax, lo + 8, hi - 8, lo + 8, hi - 8, -bh * 1.4, 0, POST["face"], POST["edge"], z=1)
    # back arm: beam A (in x) at full height, behind the corner
    _box3d(ax, 0, lo, lo, hi, 0, bh, _BEAM["face"], _BEAM["edge"], z=3)
    # overlap: A keeps the bottom half, B the top half
    _box3d(ax, lo, hi, lo, hi, 0, hh, _BEAM["face"], _BEAM["edge"], z=4)
    _box3d(ax, lo, hi, lo, hi, hh, bh, B_FACE, _BEAM["edge"], z=6)
    # front arm: beam B (in y) at full height
    _box3d(ax, lo, hi, 0, lo, 0, bh, B_FACE, _BEAM["edge"], z=8)
    # seam line of the half-lap on the visible front face
    q0, q1 = _iso(lo, lo, hh), _iso(hi, lo, hh)
    ax.plot([q0[0], q1[0]], [q0[1], q1[1]], color="#333", lw=1.0, ls=(0, (4, 3)), zorder=9)
    # dowel through both layers
    d0, d1 = _iso((lo + hi) / 2, (lo + hi) / 2, -bh * 0.3), _iso((lo + hi) / 2, (lo + hi) / 2, bh)
    ax.plot([d0[0], d1[0]], [d0[1], d1[1]], color="#5c3d23", lw=2.4, zorder=10)
    ax.annotate("Holzdübel / Schraube\ndurch beide Lagen", d1,
                (d1[0] + bw * 1.1, d1[1] + bh * 0.15), fontsize=7.5,
                arrowprops=dict(arrowstyle="->", color="#444"))
    eh0, eh1 = _iso(hi, hi, 0), _iso(hi, hi, bh)
    ax.annotate(f"Eck-Höhe {_fmt(bh)}\n({_fmt(hh)}+{_fmt(hh)})", _iso(hi, hi, bh * 0.5),
                (eh0[0] + bw * 0.5, eh0[1]), fontsize=7.5, color="#1e8449",
                arrowprops=dict(arrowstyle="->", color="#1e8449"))
    ax.set_xlim(-bw * 1.0, hi + bw * 2.4); ax.set_ylim(-bh * 1.9, bh + bw + bh * 0.5)

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

    # Note the rafter ends: they cross the front/house beams and stop flush with
    # the outer faces — no overhang either side.
    lo, hi = bounds(elements)
    ax.annotate("Sparren kreuzen Front- und Hausbalken und enden bündig an deren Außenkante",
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
    bh = pg.beams.height
    db, dr = _lap_split(rh)
    bear = bh - db
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
         f"Der Sparren kreuzt den Front-/Hausbalken und <b>endet bündig an dessen "
         f"Außenkante</b> — kein Überstand. Aus beiden Hölzern wird dafür ein Kanal "
         f"ausgenommen, der Sparren fällt von oben ein, die Oberkanten fluchten (eine "
         f"Dachebene). Die Überlappung von {_fmt(rh)} mm wird <b>balkenschonend</b> geteilt: "
         f"nur {_fmt(db)} mm aus der Balkenoberkante (der {_fmt(bh)}-er Balken behält "
         f"{_fmt(bh - db)} mm) + {_fmt(dr)} mm aus der Sparren­unterkante. Der tiefere "
         f"Schnitt sitzt im Sparren, und zwar genau an seinem <b>Auflager-Ende</b> (dort ist "
         f"das Biegemoment ~0, kostet also keine Tragfähigkeit). Auflagerfläche "
         f"<b>waagerecht</b> bei z = +{_fmt(bear)} mm schneiden — wegen der {_fmt(tilt)}°-"
         f"Neigung steht der Sparren sonst auf einer Kante."),
        ("detail_corner", "Detail 2 — Eck-Überblattung (Balken × Balken)",
         _render_corner(cfg),
         "An den vier Ecken treffen Seitenbalken und Front-/Hinterbalken über einem Pfosten "
         "aufeinander — beide gleich hoch. Klassisches Halbholz: jeden Balken im "
         "Überlappungsquadrat auf <b>halbe Höhe</b> ausklinken, ineinanderlegen, von oben mit "
         "Dübel/Schraube auf den Pfosten verbinden. Wichtig: die Ecke wird dadurch genau so "
         "hoch wie <b>ein</b> Balken (60+60=120), nicht doppelt — es liegen zwei "
         "<i>halbierte</i> Balken ineinander, nicht zwei volle aufeinander."),
    ]
