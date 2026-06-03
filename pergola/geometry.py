"""Geometry primitives shared by all views.

Everything in the model is an axis-aligned box (post, beam, rafter, slat,
footing, wall, building). A :class:`Box` is stored by its minimum corner and
its size along each axis, all in millimetres in site coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

# Axis indices for readability.
X, Y, Z = 0, 1, 2


@dataclass
class Box:
    """An axis-aligned box element in site coordinates (mm)."""

    pos: Tuple[float, float, float]   # minimum corner (x, y, z)
    size: Tuple[float, float, float]  # extent along (x, y, z)
    category: str                     # post | beam | rafter | slat | footing | wall | building
    label: str = ""

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


def bounds(boxes: List[Box]) -> Tuple[np.ndarray, np.ndarray]:
    """Return (min_corner, max_corner) enclosing all boxes."""
    if not boxes:
        return np.zeros(3), np.ones(3)
    lo = np.min([b.min for b in boxes], axis=0)
    hi = np.max([b.max for b in boxes], axis=0)
    return lo, hi
