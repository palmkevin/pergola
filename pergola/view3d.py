"""Isometric 3D view, drawn as a 2D axonometric projection.

matplotlib's mplot3d depth-sorts whole polygons by their centroid, which causes
visible occlusion errors once a scene has many parts (parts wrongly drawn in
front of others). Instead we project every box face onto a 2D plane ourselves,
discard faces pointing away from the camera (back-face culling), then paint the
remaining faces far -> near. For an axis-aligned box scene this yields clean,
correct occlusion and full control over shading and transparency.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from . import style
from .geometry import Box, bounds
from .model import Config

FIGSIZE = (11.0, 8.5)
DPI = 150
AZIM = -35.0   # camera bearing (degrees); looks from the front-right...
ELEV = 26.0    # ...and slightly above
_GHOST = frozenset({"wall", "fascia", "building"})

_LIGHT = np.array([-0.3, -0.55, 0.78])
_LIGHT = _LIGHT / np.linalg.norm(_LIGHT)


def _camera_basis(azim_deg: float, elev_deg: float):
    """Return orthonormal (right, up, toward-camera) vectors for the projection."""
    az, el = math.radians(azim_deg), math.radians(elev_deg)
    f = np.array([math.cos(el) * math.cos(az),
                  math.cos(el) * math.sin(az),
                  math.sin(el)])                      # scene -> camera
    u = np.cross([0.0, 0.0, 1.0], f)
    u /= np.linalg.norm(u)                            # screen right (horizontal)
    v = np.cross(f, u)                                # screen up
    return u, v, f


def _shade(hex_color: str, normal: np.ndarray, alpha: float = 1.0) -> tuple:
    intensity = 0.5 + 0.5 * max(0.0, float(np.dot(normal, _LIGHT)))
    r, g, b = mcolors.to_rgb(hex_color)
    return (r * intensity, g * intensity, b * intensity, alpha)


def render_iso(elements: List[Box], cfg: Config):
    u, v, f = _camera_basis(AZIM, ELEV)

    def project(pts):  # (N,3) -> (N,2) screen coordinates
        pts = np.asarray(pts)
        return np.column_stack([pts @ u, pts @ v])

    def depth(pts):    # mean distance toward the camera (larger = nearer)
        return float(np.mean(np.asarray(pts) @ f))

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.02)
    fig.suptitle("Pergola — Isometric 3D", fontsize=style.TITLE_FONTSIZE,
                 fontweight="bold", x=0.04, ha="left")
    ax.set_aspect("equal")
    ax.axis("off")

    faces = []  # (depth, screen_polygon, face_rgba, edge_rgba)

    # Ground quad sized to the content (not the whole configured area, so the
    # pergola fills the frame). Forced behind everything via a large depth bias.
    lo, hi = bounds(elements)
    m = 0.18 * max(hi[0] - lo[0], hi[1] - lo[1])
    ground = np.array([[lo[0] - m, lo[1] - m, 0], [hi[0] + m, lo[1] - m, 0],
                       [hi[0] + m, hi[1] + m, 0], [lo[0] - m, hi[1] + m, 0]])
    faces.append((-1e12, project(ground),
                  mcolors.to_rgba(style.GROUND_FACE),
                  mcolors.to_rgba(style.GROUND_EDGE, 0.5)))

    for b in elements:
        if b.category == "footing":
            continue  # underground — would otherwise float over the flat ground plane
        st = style.style_for(b.category)
        if b.category in _GHOST:
            alpha = 0.5
        else:
            alpha = style.ALPHA.get(b.category, 1.0)
        center = b.center
        for face in b.faces_3d():
            face = np.asarray(face, dtype=float)
            # Outward normal straight from the geometry (so tilted prisms work too).
            normal = np.cross(face[1] - face[0], face[2] - face[0])
            nlen = np.linalg.norm(normal)
            if nlen <= 1e-9:                            # degenerate (collapsed) face
                continue
            normal = normal / nlen
            if np.dot(normal, face.mean(axis=0) - center) < 0:
                normal = -normal                        # orient away from the body
            if float(np.dot(normal, f)) <= 1e-6:        # back-face cull
                continue
            faces.append((depth(face), project(face),
                          _shade(st["face"], normal, alpha),
                          mcolors.to_rgba(st["edge"], min(1.0, alpha + 0.35))))

    faces.sort(key=lambda t: t[0])  # far first
    for _, poly, fc, ec in faces:
        ax.add_patch(Polygon(poly, closed=True, facecolor=fc, edgecolor=ec, linewidth=0.3))

    pts = np.vstack([poly for _, poly, _, _ in faces])
    px = (pts[:, 0].max() - pts[:, 0].min()) * 0.04
    py = (pts[:, 1].max() - pts[:, 1].min()) * 0.04
    ax.set_xlim(pts[:, 0].min() - px, pts[:, 0].max() + px)
    ax.set_ylim(pts[:, 1].min() - py, pts[:, 1].max() + py)
    return fig
