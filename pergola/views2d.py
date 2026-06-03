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
from matplotlib.patches import Rectangle

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
        x, y, w, ht = b.rect_2d(h, v)
        st = style.style_for(b.category)
        alpha = ghost_alpha if b.category in ghost else style.ALPHA.get(b.category, 1.0)
        ax.add_patch(Rectangle(
            (x, y), w, ht,
            facecolor=st["face"], edgecolor=st["edge"], alpha=alpha,
            linewidth=style.EDGE_WIDTH, zorder=2 + i * 1e-3,
        ))


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
        if b.category in ("wall", "building") and b.label:
            ax.text(b.center[X], b.center[Y], b.label, ha="center", va="center",
                    fontsize=style.LABEL_FONTSIZE, color="#444444", zorder=10)

    # Overall pergola dimensions.
    ox, oy = pg.origin
    _hdim(ax, ox, ox + pg.width, oy - pg.depth * 0.18, feat_y=oy)
    _vdim(ax, oy, oy + pg.depth, ox - pg.width * 0.14, feat_x=ox)

    lo, hi = _content_bounds_2d(elements, g, X, Y)
    _set_limits(ax, lo[0], hi[0], lo[1], hi[1])
    _scale_bar(ax, lo[0], lo[1] - (hi[1] - lo[1]) * 0.04)
    _north_arrow(ax, hi[0], hi[1], (hi[0] - lo[0]), cfg.north_deg)
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
                ghost=frozenset({"wall", "building"}))

    # Pergola extents along the horizontal axis of this elevation.
    ph0 = pg.origin[h] if h in (X, Y) else 0.0
    pspan = pg.width if h == X else pg.depth
    # Heights from the actual pergola elements (top of roof).
    perg = [b for b in elements if b.category in ("post", "beam", "rafter", "slat", "glass", "footing")]
    plo, phi = bounds(perg)
    top = phi[Z]

    _hdim(ax, ph0, ph0 + pspan, -top * 0.12, feat_y=0)              # overall horizontal
    _vdim(ax, 0, top, ph0 - pspan * 0.10, feat_x=ph0)               # overall height
    _vdim(ax, 0, pg.clear_height, ph0 + pspan + pspan * 0.10,
          feat_x=ph0 + pspan, text=_fmt(pg.clear_height))           # clear height

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
