"""2D architectural views: plan + elevations, with dimension lines.

Each renderer returns a matplotlib ``Figure``. Every view is just an
orthographic projection of the same 3D box list onto a pair of axes, so all
views stay dimensionally consistent.

Projection conventions (h = screen horizontal axis, v = screen vertical):
    plan  : h=x, v=y   (looking straight down; larger z is nearer the viewer)
    front : h=x, v=z   (viewer to the south, looking +y; smaller y is nearer)
    side  : h=y, v=z   (viewer to the east, looking -x; larger x is nearer)
"""
from __future__ import annotations

import math
from typing import Callable, List, Sequence

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

from . import style
from .geometry import X, Y, Z, Box, bounds
from .model import Config

FIGSIZE = (11.0, 8.5)
DPI = 150


# --------------------------------------------------------------------------- #
#  Low-level drawing helpers
# --------------------------------------------------------------------------- #
def _fmt(mm: float) -> str:
    return f"{round(mm):d}"


def _new_fig(title: str, subtitle: str, units: str):
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.subplots_adjust(left=0.04, right=0.96, top=0.92, bottom=0.06)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.suptitle(title, fontsize=style.TITLE_FONTSIZE, fontweight="bold", x=0.04, ha="left")
    ax.set_title(f"{subtitle}      ·      all dimensions in {units}",
                 fontsize=style.LABEL_FONTSIZE, loc="left", color="#555555")
    return fig, ax


def _draw_boxes(ax, boxes: Sequence[Box], h: int, v: int, nearness: Callable[[Box], float],
                ghost: frozenset = frozenset(), ghost_alpha: float = 0.28):
    """Draw box projections onto axes (h, v), painter-ordered far -> near.

    Categories listed in ``ghost`` are drawn semi-transparently so they give
    context without hiding the pergola (e.g. a tall house wall in an elevation).
    """
    ordered = sorted(boxes, key=lambda b: (nearness(b), style.zorder_for(b.category)))
    for i, b in enumerate(ordered):
        poly = b.poly_2d(h, v)            # true silhouette (handles tilted prisms)
        if len(poly) < 2:
            continue
        st = style.style_for(b.category)
        alpha = ghost_alpha if b.category in ghost else style.ALPHA.get(b.category, 1.0)
        zo = 2 + i * 1e-3
        ax.add_patch(Polygon(
            poly, closed=True,
            facecolor=st["face"], edgecolor=st["edge"], alpha=alpha,
            linewidth=style.EDGE_WIDTH, zorder=zo,
        ))
        _draw_cladding(ax, b, h, v, zo + 0.5e-3)


def _draw_cladding(ax, b, h, v, zorder):
    """Light horizontal board-course lines across a cladded wall face (Blockbohlen).

    Only drawn in an elevation (v == Z) and only when the face is seen broadside —
    i.e. the wall's screen-horizontal extent is at least its depth — so the side
    elevation (wall seen edge-on as a 30 mm strip) gets none. The lines sit just
    above the wall fill but below the pergola, so the structure stays in front."""
    bh = getattr(b, "board_height", 0.0)
    if bh <= 0 or v != Z:
        return
    depth = 3 - h - v                      # the remaining (into-screen) axis
    if b.size[h] < b.size[depth]:          # edge-on -> nothing meaningful to draw
        return
    h0, h1 = float(b.min[h]), float(b.max[h])
    z0, z1 = float(b.min[Z]), float(b.max[Z])
    z = z0 + bh
    while z < z1 - 1e-6:
        ax.plot([h0, h1], [z, z], color=style.CLADDING_COLOR, lw=style.CLADDING_LW,
                alpha=style.CLADDING_ALPHA, zorder=zorder, solid_capstyle="butt")
        z += bh


def _hdim(ax, x1: float, x2: float, y: float, feat_y: float, text: str | None = None):
    """Horizontal dimension between x1 and x2, drawn at height ``y``.
    Extension lines reach from the feature edge (``feat_y``) to the dim line."""
    c, lw, t = style.DIM_COLOR, style.DIM_LINEWIDTH, style.DIM_TICK
    ax.plot([x1, x1], [feat_y, y + math.copysign(t, y - feat_y)], color=c, lw=lw, zorder=20)
    ax.plot([x2, x2], [feat_y, y + math.copysign(t, y - feat_y)], color=c, lw=lw, zorder=20)
    ax.plot([x1, x2], [y, y], color=c, lw=lw, zorder=20)
    for xt in (x1, x2):  # perpendicular ticks
        ax.plot([xt, xt], [y - t, y + t], color=c, lw=lw, zorder=20)
    ax.text((x1 + x2) / 2, y + t * 1.2, text or _fmt(abs(x2 - x1)),
            ha="center", va="bottom", fontsize=style.DIM_FONTSIZE, color=c, zorder=21)


def _vdim(ax, y1: float, y2: float, x: float, feat_x: float, text: str | None = None):
    """Vertical dimension between y1 and y2, drawn at horizontal position ``x``."""
    c, lw, t = style.DIM_COLOR, style.DIM_LINEWIDTH, style.DIM_TICK
    ax.plot([feat_x, x + math.copysign(t, x - feat_x)], [y1, y1], color=c, lw=lw, zorder=20)
    ax.plot([feat_x, x + math.copysign(t, x - feat_x)], [y2, y2], color=c, lw=lw, zorder=20)
    ax.plot([x, x], [y1, y2], color=c, lw=lw, zorder=20)
    for yt in (y1, y2):
        ax.plot([x - t, x + t], [yt, yt], color=c, lw=lw, zorder=20)
    ax.text(x + t * 1.2, (y1 + y2) / 2, text or _fmt(abs(y2 - y1)),
            ha="left", va="center", rotation=90, fontsize=style.DIM_FONTSIZE, color=c, zorder=21)


def _scale_bar(ax, lo_h, lo_v, length=1000.0, label="1 m"):
    """A simple scale bar at the lower-left of the drawing area."""
    x0 = lo_h
    y0 = lo_v
    ax.plot([x0, x0 + length], [y0, y0], color="#222222", lw=2.2, zorder=22,
            solid_capstyle="butt")
    for xt in (x0, x0 + length):
        ax.plot([xt, xt], [y0, y0 + length * 0.05], color="#222222", lw=1.2, zorder=22)
    ax.text(x0 + length / 2, y0 - length * 0.12, label, ha="center", va="top",
            fontsize=style.LABEL_FONTSIZE, color="#222222", zorder=22)


def _set_limits(ax, lo_h, hi_h, lo_v, hi_v, pad_frac=0.12):
    span = max(hi_h - lo_h, hi_v - lo_v)
    pad = span * pad_frac
    ax.set_xlim(lo_h - pad, hi_h + pad)
    ax.set_ylim(lo_v - pad, hi_v + pad)


# --------------------------------------------------------------------------- #
#  Plan view
# --------------------------------------------------------------------------- #
def render_plan(elements: List[Box], cfg: Config):
    fig, ax = _new_fig("Pergola — Plan (top view)", "Looking straight down", cfg.units)
    pg = cfg.pergola
    g = cfg.ground

    # Ground area.
    ax.add_patch(Rectangle(g.origin, g.extent[0], g.extent[1],
                           facecolor=style.GROUND_FACE, edgecolor=style.GROUND_EDGE,
                           linewidth=0.8, zorder=0))

    _draw_boxes(ax, elements, h=X, v=Y, nearness=lambda b: b.center[Z])

    # Labels for surroundings.
    for b in elements:
        if b.category in ("wall", "building", "bed", "path") and b.label:
            ax.text(b.center[X], b.center[Y], b.label, ha="center", va="center",
                    fontsize=style.LABEL_FONTSIZE, color="#444444", zorder=10)

    # Overall pergola dimensions. In y the footprint depth runs all the way to
    # the house wall, but the built pergola stops short of it (the roof ends over
    # the house-side beam), so dimension BOTH: the real structure depth (front
    # edge -> house-side roof edge) as the primary, inner line, and the footprint
    # depth to the wall just outboard of it for reference.
    ox, oy = pg.origin
    slo, shi = _structure_bounds(elements)
    _hdim(ax, ox, ox + pg.width, oy - pg.depth * 0.18, feat_y=oy)

    inner_x = ox - pg.width * 0.14
    outer_x = ox - pg.width * 0.30
    _vdim(ax, slo[Y], shi[Y], inner_x, feat_x=ox)             # real pergola depth
    ax.text(inner_x - pg.width * 0.035, (slo[Y] + shi[Y]) / 2, "Pergola-Tiefe",
            ha="right", va="center", rotation=90,
            fontsize=style.LABEL_FONTSIZE, color=style.DIM_COLOR, zorder=21)
    _vdim(ax, oy, oy + pg.depth, outer_x, feat_x=ox)          # to the house wall
    ax.text(outer_x - pg.width * 0.035, oy + pg.depth / 2, "bis Hauswand",
            ha="right", va="center", rotation=90,
            fontsize=style.LABEL_FONTSIZE, color=style.DIM_COLOR, zorder=21)

    lo, hi = _content_bounds_2d(elements, g, X, Y)
    _set_limits(ax, lo[0], hi[0], lo[1], hi[1])
    _scale_bar(ax, lo[0], lo[1] - (hi[1] - lo[1]) * 0.04)
    _north_arrow(ax, hi[0], hi[1], (hi[0] - lo[0]), cfg.north_deg)
    return fig


# --------------------------------------------------------------------------- #
#  Rafter-spacing plan (top view focused on the roof framing)
# --------------------------------------------------------------------------- #
def render_rafter_plan(elements: List[Box], cfg: Config):
    """A top view focused on the roof framing, dimensioning the rafter layout:
    the centre-to-centre (axis) spacing between the rafters and the gap from the
    two outer rafters to the side beams (the perimeter ring's edge members)."""
    fig, ax = _new_fig("Pergola — Sparrenabstände (Draufsicht)",
                       "Sparren von oben · Achsmaße (Mitte–Mitte) und lichte Felder",
                       cfg.units)
    pg = cfg.pergola
    ox, oy = pg.origin
    w, d = pg.width, pg.depth

    # Pergola framing only — skip surroundings, the ground, and the translucent
    # roof pane (it spans the whole footprint and would hide the rafters here).
    members = [b for b in elements
               if b.category in ("post", "beam", "rafter", "gutter")]
    _draw_boxes(ax, members, h=X, v=Y, nearness=lambda b: b.center[Z])

    rafters = [b for b in elements if b.category == "rafter"]
    if not rafters:
        _set_limits(ax, ox, ox + w, oy, oy + d)
        return fig

    # Spacing axis s = the axis the rafters are distributed along; o = the axis
    # they span. (Here rafters run in y, so they are spread along x: s = X.)
    spread_x = max(b.center[X] for b in rafters) - min(b.center[X] for b in rafters)
    spread_y = max(b.center[Y] for b in rafters) - min(b.center[Y] for b in rafters)
    s = X if spread_x >= spread_y else Y
    o = Y if s == X else X

    rs = sorted(rafters, key=lambda b: b.center[s])
    r_axis = [float(b.center[s]) for b in rs]
    r_lo = [float(b.min[s]) for b in rs]
    r_hi = [float(b.max[s]) for b in rs]

    # The "edge beams" parallel to the rafters: ring members narrow along s.
    edge = sorted((b for b in elements if b.category == "beam"
                   and (b.max[s] - b.min[s]) < (b.max[o] - b.min[o])),
                  key=lambda b: b.center[s])
    if len(edge) >= 2:
        left_axis, right_axis = float(edge[0].center[s]), float(edge[-1].center[s])
        left_inner, right_inner = float(edge[0].max[s]), float(edge[-1].min[s])
    else:  # no flanking beams — fall back to the footprint edges
        left_axis = left_inner = (ox if s == X else oy)
        right_axis = right_inner = (ox + w if s == X else oy + d)

    blo, bhi = bounds(members)
    lo_o = float(blo[o])
    hi_o = float(bhi[o])
    span_o = hi_o - lo_o

    def dim(a, b, level, feat):
        if s == X:
            _hdim(ax, a, b, level, feat_y=feat)
        else:
            _vdim(ax, a, b, level, feat_x=feat)

    # Axis chain (centre-to-centre) on the near/low side: side-beam axis through
    # every rafter axis to the far side-beam axis -> 700 · 660 · 660 · 700.
    axis_pts = [left_axis] + r_axis + [right_axis]
    axis_level = lo_o - span_o * 0.18
    for a, b in zip(axis_pts[:-1], axis_pts[1:]):
        dim(a, b, axis_level, lo_o)

    # Clear-field chain on the far/high side: side-beam inner face to rafter
    # face, between rafters, then to the far inner face -> 630 · 600 · 600 · 630.
    clear_pairs = ([(left_inner, r_lo[0])]
                   + [(r_hi[i], r_lo[i + 1]) for i in range(len(rs) - 1)]
                   + [(r_hi[-1], right_inner)])
    clear_level = hi_o + span_o * 0.18
    for a, b in clear_pairs:
        dim(a, b, clear_level, hi_o)

    # Light dashed centre lines through each rafter and the two edge beams, so
    # the axis dimensions are easy to read back onto the framing.
    for ax_pt in axis_pts:
        if s == X:
            ax.plot([ax_pt, ax_pt], [lo_o, hi_o], color=style.DIM_COLOR,
                    lw=0.5, ls=(0, (4, 3)), alpha=0.5, zorder=15)
        else:
            ax.plot([lo_o, hi_o], [ax_pt, ax_pt], color=style.DIM_COLOR,
                    lw=0.5, ls=(0, (4, 3)), alpha=0.5, zorder=15)

    # Row captions so the two chains are unambiguous.
    cen = (axis_pts[0] + axis_pts[-1]) / 2
    if s == X:
        ax.text(cen, axis_level - span_o * 0.07, "Achsabstand (Mitte–Mitte)",
                ha="center", va="top", fontsize=style.LABEL_FONTSIZE,
                color=style.DIM_COLOR, zorder=21)
        ax.text(cen, clear_level + span_o * 0.07, "lichter Abstand (freies Feld)",
                ha="center", va="bottom", fontsize=style.LABEL_FONTSIZE,
                color=style.DIM_COLOR, zorder=21)
    else:
        ax.text(axis_level - span_o * 0.07, cen, "Achsabstand (Mitte–Mitte)",
                ha="right", va="center", rotation=90,
                fontsize=style.LABEL_FONTSIZE, color=style.DIM_COLOR, zorder=21)
        ax.text(clear_level + span_o * 0.07, cen, "lichter Abstand (freies Feld)",
                ha="left", va="center", rotation=90,
                fontsize=style.LABEL_FONTSIZE, color=style.DIM_COLOR, zorder=21)

    _set_limits(ax, blo[X], bhi[X], blo[Y], bhi[Y], pad_frac=0.30)
    return fig


def _north_arrow(ax, x, y, span, north_deg):
    """Small North arrow near the top-right; +y rotated by the compass bearing."""
    L = span * 0.06
    ang = math.radians(north_deg)
    dx, dy = -math.sin(ang) * L, math.cos(ang) * L
    bx, by = x - L * 1.4, y - L * 1.4
    ax.annotate("", xy=(bx + dx, by + dy), xytext=(bx, by),
                arrowprops=dict(arrowstyle="-|>", color="#222222", lw=1.5), zorder=23)
    ax.text(bx + dx * 1.25, by + dy * 1.25, "N", ha="center", va="center",
            fontsize=9, fontweight="bold", color="#222222", zorder=23)


# --------------------------------------------------------------------------- #
#  Elevations
# --------------------------------------------------------------------------- #
def render_front(elements: List[Box], cfg: Config):
    return _render_elevation(
        elements, cfg, h=X, v=Z, nearness=lambda b: -b.center[Y],
        title="Pergola — Front elevation", subtitle="Viewed from the front (south)",
        overall_label="width",
    )


def render_side(elements: List[Box], cfg: Config):
    return _render_elevation(
        elements, cfg, h=Y, v=Z, nearness=lambda b: b.center[X],
        title="Pergola — Side elevation", subtitle="Viewed from the right (east)",
        overall_label="depth",
    )


def _render_elevation(elements, cfg: Config, *, h, v, nearness, title, subtitle, overall_label):
    fig, ax = _new_fig(title, subtitle, cfg.units)
    pg = cfg.pergola

    # Ground line at z = 0.
    lo, hi = _content_bounds_2d(elements, cfg.ground, h, v)
    ax.plot([lo[0], hi[0]], [0, 0], color="#8a7d5f", lw=1.4, zorder=1)

    # Surroundings are ghosted so the pergola is never hidden behind a tall wall.
    _draw_boxes(ax, elements, h=h, v=v, nearness=nearness,
                ghost=frozenset({"wall", "fascia", "building"}))

    # Pergola extents along the horizontal axis of this elevation.
    ph0 = pg.origin[h] if h in (X, Y) else 0.0
    pspan = pg.width if h == X else pg.depth
    # Heights from the actual pergola elements (top of roof).
    perg = [b for b in elements if b.category in ("post", "beam", "rafter", "slat", "glass", "footing")]
    plo, phi = bounds(perg)
    top = phi[Z]

    _hdim(ax, ph0, ph0 + pspan, -top * 0.12, feat_y=0)              # overall horizontal
    # In the side elevation the overall horizontal runs to the house wall, but the
    # built pergola stops short of it; add the real structure depth (front edge ->
    # house-side roof edge) below it and label both so the actual pergola end is
    # readable, not just the distance to the wall.
    if h == Y:
        slo, shi = _structure_bounds(elements)
        _hdim(ax, slo[Y], shi[Y], -top * 0.26, feat_y=0)
        ax.text((slo[Y] + shi[Y]) / 2, -top * 0.30, "Pergola-Tiefe",
                ha="center", va="top", fontsize=style.LABEL_FONTSIZE,
                color=style.DIM_COLOR, zorder=21)
        ax.text((ph0 + ph0 + pspan) / 2, -top * 0.12 - top * 0.005, "bis Hauswand",
                ha="center", va="top", fontsize=style.LABEL_FONTSIZE,
                color=style.DIM_COLOR, zorder=21)
    _vdim(ax, 0, top, ph0 - pspan * 0.10, feat_x=ph0)               # overall height
    _vdim(ax, 0, pg.clear_height, ph0 + pspan + pspan * 0.10,
          feat_x=ph0 + pspan, text=_fmt(pg.clear_height))           # clear height

    # Post height on the house-averted (low/front) side. The roof slopes down to
    # the front, so the front posts are shorter than the clear_height held at the
    # house side; that figure was missing from the elevations, so dimension it on
    # the front (left) edge, just outboard of the overall-height line.
    posts = [b for b in elements if b.category == "post"]
    if posts:
        fy = min(b.center[Y] for b in posts)
        front_top = max(b.max[Z] for b in posts if abs(b.center[Y] - fy) < 1.0)
        fx = ph0 - pspan * 0.22
        _vdim(ax, 0, front_top, fx, feat_x=ph0, text=_fmt(front_top))
        ax.text(fx - pspan * 0.035, front_top / 2, "Pfostenhöhe vorne",
                ha="right", va="center", rotation=90,
                fontsize=style.LABEL_FONTSIZE, color=style.DIM_COLOR, zorder=21)

    _set_limits(ax, lo[0], hi[0], min(lo[1], plo[Z]), hi[1])
    _scale_bar(ax, lo[0], min(lo[1], plo[Z]) - top * 0.06)
    return fig


# --------------------------------------------------------------------------- #
#  Shared bounds helper
# --------------------------------------------------------------------------- #
def _content_bounds_2d(elements, ground, h, v):
    """(lo, hi) bounds on screen axes (h, v), widened to include the ground area.

    Returns two length-2 arrays: lo = [min_h, min_v], hi = [max_h, max_v].
    """
    lo, hi = bounds(elements)
    lo, hi = lo.copy(), hi.copy()
    for axis, gmin, gext in ((X, ground.origin[0], ground.extent[0]),
                             (Y, ground.origin[1], ground.extent[1])):
        lo[axis] = min(lo[axis], gmin)
        hi[axis] = max(hi[axis], gmin + gext)
    return lo[[h, v]], hi[[h, v]]


# The built pergola itself (roof structure), excluding footings (underground),
# the foundation step, the gutter/curtain overhangs and the steel anchors. Used
# to dimension the REAL extent of the pergola, which along y stops short of the
# house wall (the roof ends over the house-side beam, not at the wall) — so the
# footprint depth alone never tells you where the pergola actually ends.
_STRUCTURE = frozenset({"post", "beam", "rafter", "slat", "glass",
                        "profile", "edge_profile"})


def _structure_bounds(elements):
    """(lo, hi) bounds of the pergola's structural members only."""
    return bounds([b for b in elements if b.category in _STRUCTURE])
