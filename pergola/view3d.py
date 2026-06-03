"""Simple isometric 3D render of the same box model.

Uses matplotlib's mplot3d (pure Python, headless). Faces are flat-shaded by
the angle between their outward normal and a fixed light direction, which gives
a clean, readable solid look without a heavy 3D engine.
"""
from __future__ import annotations

from typing import List

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from . import style
from .geometry import FACE_NORMALS, Box, bounds
from .model import Config

FIGSIZE = (11.0, 8.5)
DPI = 150
_LIGHT = np.array([0.4, -0.6, 0.8])
_LIGHT = _LIGHT / np.linalg.norm(_LIGHT)


_GHOST = frozenset({"wall", "building"})


def _shade(hex_color: str, normal: np.ndarray, alpha: float = 1.0) -> tuple:
    """Darken a face colour by how much it faces away from the light."""
    intensity = 0.55 + 0.45 * max(0.0, float(np.dot(normal, _LIGHT)))
    r, g, b = mcolors.to_rgb(hex_color)
    return (r * intensity, g * intensity, b * intensity, alpha)


def render_iso(elements: List[Box], cfg: Config):
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    ax = fig.add_subplot(111, projection="3d")
    fig.suptitle("Pergola — Isometric 3D", fontsize=style.TITLE_FONTSIZE,
                 fontweight="bold", x=0.04, ha="left")

    # Ground plane.
    g = cfg.ground
    gx0, gy0 = g.origin
    gx1, gy1 = gx0 + g.extent[0], gy0 + g.extent[1]
    ground = [np.array([[gx0, gy0, 0], [gx1, gy0, 0], [gx1, gy1, 0], [gx0, gy1, 0]])]
    ax.add_collection3d(Poly3DCollection(ground, facecolors=style.GROUND_FACE,
                                         edgecolors=style.GROUND_EDGE, linewidths=0.4))

    # Sort boxes far -> near for reasonable painter ordering in the iso view.
    view_dir = np.array([1.0, 1.0, -0.6])  # roughly toward the camera
    ordered = sorted(elements, key=lambda b: float(np.dot(b.center, view_dir)))

    polys, colors, edges = [], [], []
    for b in ordered:
        st = style.style_for(b.category)
        alpha = 0.35 if b.category in _GHOST else 1.0
        for face, normal in zip(b.faces_3d(), FACE_NORMALS):
            polys.append(face)
            colors.append(_shade(st["face"], normal, alpha))
            edges.append(mcolors.to_rgba(st["edge"], alpha))
    coll = Poly3DCollection(polys, facecolors=colors, edgecolors=edges, linewidths=0.25)
    ax.add_collection3d(coll)

    # Equal aspect from the data extents.
    lo, hi = bounds(elements)
    lo = np.minimum(lo, [gx0, gy0, 0])
    hi = np.maximum(hi, [gx1, gy1, 0])
    ctr = (lo + hi) / 2
    span = float(np.max(hi - lo)) / 2 * 1.02
    ax.set_xlim(ctr[0] - span, ctr[0] + span)
    ax.set_ylim(ctr[1] - span, ctr[1] + span)
    ax.set_zlim(min(lo[2], 0), ctr[2] + span)

    ax.view_init(elev=24, azim=-58)
    ax.set_axis_off()
    # Fill the figure and zoom in to remove mplot3d's large default margins.
    ax.set_position([0.0, 0.0, 1.0, 1.0])
    try:
        ax.set_box_aspect((1, 1, 0.5), zoom=1.6)  # matplotlib >= 3.6
    except TypeError:
        ax.set_box_aspect((1, 1, 0.5))
    return fig
