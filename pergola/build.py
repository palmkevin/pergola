"""Expand the parametric :class:`Config` into a fully detailed list of boxes.

Every structural member is generated individually (each post, footing, beam,
rafter and roof slat), so the drawings show real construction detail rather
than a schematic outline.

Stacking (bottom -> top), all in mm:
    footing : -footing.depth .. 0
    post    : 0 .. underside(post)
    beam    : underside .. underside + beam.height            (on top of posts)
    rafter  : beam_top .. beam_top + rafter.height            (across the beams)
    slat    : rafter_top .. rafter_top + slat.height          (the roof surface)

When ``roof.tilt_deg`` is non-zero the roof slopes DOWN toward the front
(y-min), with the house side (y-max) held at ``clear_height``. Posts and beams
then have row-dependent heights, while rafters and the glass pane become tilted
:class:`Prism` slabs that follow the slope.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np

from .geometry import Box, Prism
from .model import Config, Path, Pergola


def _linspace_centers(start: float, length: float, count: int) -> np.ndarray:
    """Evenly spaced member centres spanning [start, start+length], inset so the
    outer members sit fully inside the footprint edges is handled by the caller."""
    if count == 1:
        return np.array([start + length / 2.0])
    return np.linspace(start, start + length, count)


def _count_by_spacing(length: float, spacing: float) -> int:
    return max(2, int(round(length / spacing)) + 1)


def _slab(x0, x1, y0, y1, zb0, zb1, thickness, category):
    """A roof slab spanning [x0,x1]x[y0,y1]; its underside runs from ``zb0`` at
    y0 to ``zb1`` at y1. Returns an axis-aligned :class:`Box` when level, else a
    tilted :class:`Prism` so flat roofs keep their simple box representation."""
    if abs(zb1 - zb0) < 1e-6:
        return Box(pos=(x0, y0, zb0), size=(x1 - x0, y1 - y0, thickness),
                   category=category)
    c = np.array([
        [x0, y0, zb0], [x1, y0, zb0], [x1, y1, zb1], [x0, y1, zb1],
        [x0, y0, zb0 + thickness], [x1, y0, zb0 + thickness],
        [x1, y1, zb1 + thickness], [x0, y1, zb1 + thickness],
    ])
    return Prism(corners_arr=c, category=category)


def build_pergola(pg: Pergola) -> List[Box]:
    boxes: List[Box] = []
    ox, oy = pg.origin
    w, d = pg.width, pg.depth
    ch = pg.clear_height
    ps = pg.posts
    half_x = ps.size_x / 2.0
    half_y = ps.size_y / 2.0
    flush = pg.framing == "flush"

    # Roof underside as a function of y: held at clear_height on the house side
    # (y = oy + d) and dropping toward the front by the pitch.
    t = math.tan(math.radians(pg.roof.tilt_deg))

    def underside(y: float) -> float:
        return ch - (oy + d - y) * t

    # Post X centres: outer posts inset by half a post so they sit inside the footprint.
    xs = _linspace_centers(ox + half_x, w - ps.size_x, ps.count_x)
    # Post Y centres. With house_offset (attached): front row on the footprint
    # corner, house-side row pulled `house_offset` off the wall; otherwise even.
    if ps.house_offset is not None:
        front = oy + half_y
        back = oy + d - ps.house_offset - half_y
        if ps.count_y == 2:
            ys = np.array([front, back])
        else:
            ys = np.concatenate(([front],
                                 np.linspace(front, back, ps.count_y)[1:-1],
                                 [back]))
    else:
        ys = _linspace_centers(oy + half_y, d - ps.size_y, ps.count_y)

    # Footings + posts at each grid node. Post tops follow the sloped underside.
    for cx in xs:
        for cy in ys:
            boxes.append(Box(
                pos=(cx - ps.footing.size / 2, cy - ps.footing.size / 2, -ps.footing.depth),
                size=(ps.footing.size, ps.footing.size, ps.footing.depth),
                category="footing",
            ))
            boxes.append(Box(
                pos=(cx - half_x, cy - half_y, 0.0),
                size=(ps.size_x, ps.size_y, underside(cy)),
                category="post",
            ))

    # Beams sit on top of the posts.
    bm = pg.beams
    bh = bm.height
    if flush:
        # One-level frame: a full perimeter ring of beams. Front/back beams run
        # along x (horizontal, stepped to each row's underside); the left/right
        # beams run along y and follow the slope, so they are tilted slabs. The
        # rafters (below) sit housed flush between the front and back beams.
        for cy in (ys[0], ys[-1]):
            boxes.append(Box(
                pos=(ox, cy - bm.width / 2, underside(cy)),
                size=(w, bm.width, bh),
                category="beam",
            ))
        for cx in (xs[0], xs[-1]):
            boxes.append(_slab(cx - bm.width / 2, cx + bm.width / 2, oy, oy + d,
                               underside(oy), underside(oy + d), bh, "beam"))
    elif bm.direction == "x":
        for cy in ys:
            boxes.append(Box(
                pos=(ox, cy - bm.width / 2, underside(cy)),
                size=(w, bm.width, bh),
                category="beam",
            ))
    else:  # beams along y -> they follow the slope, so build as slabs
        for cx in xs:
            boxes.append(_slab(cx - bm.width / 2, cx + bm.width / 2, oy, oy + d,
                               underside(oy), underside(oy + d), bh, "beam"))

    # Rafters laid across the beams; they span the full depth to the wall and
    # follow the roof slope. Stacked framing rests them ON TOP of the beams;
    # flush framing houses them BETWEEN the perimeter beams with tops aligned
    # (rafter underside is then rh below the beam top), giving one roof plane.
    rf = pg.rafters
    rh = rf.height
    rb = (bh - rh) if flush else bh    # rafter underside, measured above the post top
    if rf.direction == "y":
        a, b = (xs[0] + bm.width / 2, xs[-1] - bm.width / 2) if flush else (ox, ox + w)
        n = _count_by_spacing((b - a) - rf.width, rf.spacing)
        for cx in _linspace_centers(a + rf.width / 2, (b - a) - rf.width, n):
            boxes.append(_slab(cx - rf.width / 2, cx + rf.width / 2, oy, oy + d,
                               underside(oy) + rb, underside(oy + d) + rb,
                               rh, "rafter"))
    else:  # rafters along x -> horizontal, one per row, stepped in z
        a, b = (ys[0] + bm.width / 2, ys[-1] - bm.width / 2) if flush else (oy, oy + d)
        n = _count_by_spacing((b - a) - rf.width, rf.spacing)
        for cy in _linspace_centers(a + rf.width / 2, (b - a) - rf.width, n):
            boxes.append(Box(
                pos=(ox, cy - rf.width / 2, underside(cy) + rb),
                size=(w, rf.width, rh),
                category="rafter",
            ))

    # Roof surface follows the slope, resting on the plane formed by the rafter
    # tops (stacked) or the flush frame+rafter tops (flush).
    roof = pg.roof

    def roof_base(y: float) -> float:
        return underside(y) + bh + (0.0 if flush else rh)

    if roof.kind == "glass":
        boxes.append(_slab(ox, ox + w, oy, oy + d,
                           roof_base(oy), roof_base(oy + d), roof.thickness, "glass"))
    elif roof.kind != "open":
        sw, sh = roof.slat_width, roof.slat_height
        if roof.direction == "x":  # slats run along x at stepped heights
            n = _count_by_spacing(d - sw, roof.spacing)
            for cy in _linspace_centers(oy + sw / 2, d - sw, n):
                boxes.append(Box(
                    pos=(ox, cy - sw / 2, roof_base(cy)),
                    size=(w, sw, sh),
                    category="slat",
                ))
        else:  # slats run along y -> tilted slabs
            n = _count_by_spacing(w - sw, roof.spacing)
            for cx in _linspace_centers(ox + sw / 2, w - sw, n):
                boxes.append(_slab(cx - sw / 2, cx + sw / 2, oy, oy + d,
                                   roof_base(oy), roof_base(oy + d), sh, "slat"))

    # Rain gutter along the low (front) eave, just outboard of the front edge.
    if roof.gutter:
        g_depth, g_h = 120.0, 90.0
        eave_top = roof_base(oy)                # underside of the roof at the front
        boxes.append(Box(
            pos=(ox, oy - g_depth, eave_top - g_h),
            size=(w, g_depth, g_h),
            category="gutter",
        ))

    return boxes


def build_surroundings(cfg: Config) -> List[Box]:
    boxes: List[Box] = []
    for w in cfg.walls:
        boxes.append(Box(
            pos=(w.at[0], w.at[1], 0.0),
            size=(w.size[0], w.size[1], w.height),
            category="wall",
            label=w.name,
        ))
    for b in cfg.buildings:
        boxes.append(Box(
            pos=(b.at[0], b.at[1], 0.0),
            size=(b.size[0], b.size[1], b.height),
            category="building",
            label=b.name,
        ))
    for bed in cfg.beds:
        boxes.append(Box(
            pos=(bed.at[0], bed.at[1], 0.0),
            size=(bed.size[0], bed.size[1], bed.height),
            category="bed",
            label=bed.name,
        ))
    for p in cfg.paths:
        boxes.append(_build_path(p))
    return boxes


def _build_path(p: Path) -> Prism:
    """A ramp wedge: flat on the ground (z=0), rising to ``p.rise`` at the
    ``high_end`` edge and tapering to ground level at the opposite edge."""
    x0, y0 = p.at
    x1, y1 = x0 + p.size[0], y0 + p.size[1]
    r = p.rise
    # Top-corner heights, ordered (x0,y0) (x1,y0) (x1,y1) (x0,y1).
    if p.high_end == "x_min":
        tz = [r, 0, 0, r]
    elif p.high_end == "x_max":
        tz = [0, r, r, 0]
    elif p.high_end == "y_min":
        tz = [r, r, 0, 0]
    else:  # y_max
        tz = [0, 0, r, r]
    c = np.array([
        [x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0],          # bottom
        [x0, y0, tz[0]], [x1, y0, tz[1]], [x1, y1, tz[2]], [x0, y1, tz[3]],  # top
    ])
    return Prism(corners_arr=c, category="path", label=p.name)


def build_elements(cfg: Config) -> List[Box]:
    """Full element list: pergola members + surrounding walls/buildings."""
    return build_pergola(cfg.pergola) + build_surroundings(cfg)
