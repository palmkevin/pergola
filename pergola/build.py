"""Expand the parametric :class:`Config` into a fully detailed list of boxes.

Every structural member is generated individually (each post, footing, beam,
rafter and roof slat), so the drawings show real construction detail rather
than a schematic outline.

Stacking (bottom -> top), all in mm:
    footing : -footing.depth .. 0
    post    : 0 .. clear_height
    beam    : clear_height .. clear_height + beam.height      (on top of posts)
    rafter  : beam_top .. beam_top + rafter.height            (across the beams)
    slat    : rafter_top .. rafter_top + slat.height          (the roof surface)
"""
from __future__ import annotations

from typing import List

import numpy as np

from .geometry import Box
from .model import Config, Pergola


def _linspace_centers(start: float, length: float, count: int) -> np.ndarray:
    """Evenly spaced member centres spanning [start, start+length], inset so the
    outer members sit fully inside the footprint edges is handled by the caller."""
    if count == 1:
        return np.array([start + length / 2.0])
    return np.linspace(start, start + length, count)


def _count_by_spacing(length: float, spacing: float) -> int:
    return max(2, int(round(length / spacing)) + 1)


def build_pergola(pg: Pergola) -> List[Box]:
    boxes: List[Box] = []
    ox, oy = pg.origin
    w, d = pg.width, pg.depth
    ch = pg.clear_height
    ps = pg.posts

    # Post centres: outer posts inset by half a post so they sit inside the footprint.
    half = ps.size / 2.0
    xs = _linspace_centers(ox + half, w - ps.size, ps.count_x)
    ys = _linspace_centers(oy + half, d - ps.size, ps.count_y)

    # Footings + posts at each grid node.
    for cx in xs:
        for cy in ys:
            boxes.append(Box(
                pos=(cx - ps.footing.size / 2, cy - ps.footing.size / 2, -ps.footing.depth),
                size=(ps.footing.size, ps.footing.size, ps.footing.depth),
                category="footing",
            ))
            boxes.append(Box(
                pos=(cx - half, cy - half, 0.0),
                size=(ps.size, ps.size, ch),
                category="post",
            ))

    # Beams sit on top of the posts.
    bm = pg.beams
    beam_top = ch + bm.height
    if bm.direction == "x":
        # one beam per row of posts, spanning the full width
        for cy in ys:
            boxes.append(Box(
                pos=(ox, cy - bm.width / 2, ch),
                size=(w, bm.width, bm.height),
                category="beam",
            ))
    else:  # beams along y
        for cx in xs:
            boxes.append(Box(
                pos=(cx - bm.width / 2, oy, ch),
                size=(bm.width, d, bm.height),
                category="beam",
            ))

    # Rafters laid across the beams.
    rf = pg.rafters
    rafter_top = beam_top + rf.height
    if rf.direction == "y":
        n = _count_by_spacing(w - rf.width, rf.spacing)
        for cx in _linspace_centers(ox + rf.width / 2, w - rf.width, n):
            boxes.append(Box(
                pos=(cx - rf.width / 2, oy, beam_top),
                size=(rf.width, d, rf.height),
                category="rafter",
            ))
    else:  # rafters along x
        n = _count_by_spacing(d - rf.width, rf.spacing)
        for cy in _linspace_centers(oy + rf.width / 2, d - rf.width, n):
            boxes.append(Box(
                pos=(ox, cy - rf.width / 2, beam_top),
                size=(w, rf.width, rf.height),
                category="rafter",
            ))

    # Roof: glass pane, slats/louvres, or nothing ("open").
    roof = pg.roof
    if roof.kind == "glass":
        # A single translucent pane covering the footprint, resting on the rafters.
        boxes.append(Box(
            pos=(ox, oy, rafter_top),
            size=(w, d, roof.thickness),
            category="glass",
        ))
    elif roof.kind != "open":
        sw, sh = roof.slat_width, roof.slat_height
        if roof.direction == "x":
            n = _count_by_spacing(d - sw, roof.spacing)
            for cy in _linspace_centers(oy + sw / 2, d - sw, n):
                boxes.append(Box(
                    pos=(ox, cy - sw / 2, rafter_top),
                    size=(w, sw, sh),
                    category="slat",
                ))
        else:  # slats along y
            n = _count_by_spacing(w - sw, roof.spacing)
            for cx in _linspace_centers(ox + sw / 2, w - sw, n):
                boxes.append(Box(
                    pos=(cx - sw / 2, oy, rafter_top),
                    size=(sw, d, sh),
                    category="slat",
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
    return boxes


def build_elements(cfg: Config) -> List[Box]:
    """Full element list: pergola members + surrounding walls/buildings."""
    return build_pergola(cfg.pergola) + build_surroundings(cfg)
