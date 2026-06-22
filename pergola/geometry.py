"""Geometry primitives shared by all views.

Most elements are axis-aligned boxes (post, beam, footing, wall, building,
bed, gutter). Tilted members — a pitched roof's rafters and glass pane, or a
sloping garden path/ramp — cannot be axis-aligned, so they are stored as a
:class:`Prism`: a general 8-corner hexahedron. Both primitives expose the same
small interface (``corners``/``faces_3d``/``poly_2d``/``min``/``max``/``center``)
so every view treats them uniformly. All coordinates are millimetres.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

# Axis indices for readability.
X, Y, Z = 0, 1, 2


def convex_hull_2d(points: np.ndarray) -> np.ndarray:
    """Ordered convex-hull vertices of 2D ``points`` (Andrew's monotone chain).

    Used to turn the projected corners of a box/prism into a filled outline
    polygon, so a tilted member draws as its true silhouette in any view.
    """
    pts = sorted({(round(float(p[0]), 4), round(float(p[1]), 4)) for p in points})
    if len(pts) <= 2:
        return np.array(pts, dtype=float)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1], dtype=float)


@dataclass
class Box:
    """An axis-aligned box element in site coordinates (mm)."""

    pos: Tuple[float, float, float]   # minimum corner (x, y, z)
    size: Tuple[float, float, float]  # extent along (x, y, z)
    category: str                     # post | beam | rafter | slat | footing | wall | building
    label: str = ""
    material: str = ""                # optional material override for the Materialliste
                                      # (e.g. "PVC" panel, "Aluminium" profile); blank
                                      # -> use the category's default material
    board_height: float = 0.0         # drawing hint (walls): visible cladding board
                                      # course height (mm), e.g. Blockbohlen — the
                                      # elevations draw light horizontal course lines
                                      # across the face. 0 -> no cladding lines.

    # --- convenience accessors -------------------------------------------------
    @property
    def min(self) -> np.ndarray:
        return np.asarray(self.pos, dtype=float)

    @property
    def max(self) -> np.ndarray:
        return self.min + np.asarray(self.size, dtype=float)

    @property
    def center(self) -> np.ndarray:
        return self.min + np.asarray(self.size, dtype=float) / 2.0

    def rect_2d(self, h: int, v: int) -> Tuple[float, float, float, float]:
        """Return (x, y, width, height) of this box projected onto axes (h, v)."""
        lo = self.min
        sz = np.asarray(self.size, dtype=float)
        return float(lo[h]), float(lo[v]), float(sz[h]), float(sz[v])

    def corners(self) -> np.ndarray:
        """The 8 corner points (x, y, z) of the box."""
        x0, y0, z0 = self.min
        x1, y1, z1 = self.max
        return np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                         [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])

    def poly_2d(self, h: int, v: int) -> np.ndarray:
        """Convex-hull outline of the box projected onto axes (h, v)."""
        return convex_hull_2d(self.corners()[:, [h, v]])

    def faces_3d(self) -> List[np.ndarray]:
        """Return the 6 faces as arrays of 4 corner points (for 3D rendering)."""
        x0, y0, z0 = self.min
        x1, y1, z1 = self.max
        return [
            np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0]]),  # bottom (-z)
            np.array([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]),  # top (+z)
            np.array([[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]]),  # front (-y)
            np.array([[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]),  # back (+y)
            np.array([[x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1]]),  # left (-x)
            np.array([[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]]),  # right (+x)
        ]


# Face outward normals, matching the order returned by Box.faces_3d().
FACE_NORMALS = np.array(
    [
        [0, 0, -1],
        [0, 0, 1],
        [0, -1, 0],
        [0, 1, 0],
        [-1, 0, 0],
        [1, 0, 0],
    ],
    dtype=float,
)


# Corner indices for the 6 faces of a Prism, matching the corner order below.
_PRISM_FACES = [
    [0, 1, 2, 3],  # bottom
    [4, 5, 6, 7],  # top
    [0, 1, 5, 4],  # front (-y)
    [3, 2, 6, 7],  # back  (+y)
    [0, 3, 7, 4],  # left  (-x)
    [1, 2, 6, 5],  # right (+x)
]


@dataclass
class Prism:
    """A general 8-corner hexahedron (e.g. a tilted rafter, sloped roof pane or
    ramp). Corners are ordered bottom face [0..3] then top face [4..7], each
    going (x0,y0) (x1,y0) (x1,y1) (x0,y1). Degenerate (collapsed) corners are
    allowed, so a wedge/ramp is just a prism whose two top corners meet the
    bottom. Face winding is irrelevant — the 3D view derives normals from the
    geometry itself."""

    corners_arr: np.ndarray            # (8, 3) corner points (mm)
    category: str
    label: str = ""
    material: str = ""                 # optional material override (see Box.material)

    @property
    def min(self) -> np.ndarray:
        return np.asarray(self.corners_arr, dtype=float).min(axis=0)

    @property
    def max(self) -> np.ndarray:
        return np.asarray(self.corners_arr, dtype=float).max(axis=0)

    @property
    def center(self) -> np.ndarray:
        return np.asarray(self.corners_arr, dtype=float).mean(axis=0)

    def corners(self) -> np.ndarray:
        return np.asarray(self.corners_arr, dtype=float)

    def poly_2d(self, h: int, v: int) -> np.ndarray:
        return convex_hull_2d(self.corners()[:, [h, v]])

    def faces_3d(self) -> List[np.ndarray]:
        c = self.corners()
        return [c[idx] for idx in _PRISM_FACES]


# Anything with the box/prism interface (corners, faces_3d, poly_2d, min/max/center).
Element = "Box | Prism"


def bounds(boxes) -> Tuple[np.ndarray, np.ndarray]:
    """Return (min_corner, max_corner) enclosing all boxes/prisms."""
    if not boxes:
        return np.zeros(3), np.ones(3)
    lo = np.min([b.min for b in boxes], axis=0)
    hi = np.max([b.max for b in boxes], axis=0)
    return lo, hi
