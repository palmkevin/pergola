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


def _slab(x0, x1, y0, y1, zb0, zb1, thickness, category, material=""):
    """A roof slab spanning [x0,x1]x[y0,y1]; its underside runs from ``zb0`` at
    y0 to ``zb1`` at y1. Returns an axis-aligned :class:`Box` when level, else a
    tilted :class:`Prism` so flat roofs keep their simple box representation."""
    if abs(zb1 - zb0) < 1e-6:
        return Box(pos=(x0, y0, zb0), size=(x1 - x0, y1 - y0, thickness),
                   category=category, material=material)
    c = np.array([
        [x0, y0, zb0], [x1, y0, zb0], [x1, y1, zb1], [x0, y1, zb1],
        [x0, y0, zb0 + thickness], [x1, y0, zb0 + thickness],
        [x1, y1, zb1 + thickness], [x0, y1, zb1 + thickness],
    ])
    return Prism(corners_arr=c, category=category, material=material)


def _post_anchor(cx, cy, base, an, size_x, size_y) -> Box:
    """The galvanised U-Stützenfuß at one post foot.

    Modelled as one steel collar from the concrete top (z = ``base``) up the
    post sides by ``air_gap + wing_height``: the lower ``air_gap`` is the clear
    space holding the post off the concrete (ventilation), the rest wraps the
    post like the U's wings. The gap runs across the post's WIDER face (the one
    milled down to ``width`` so the standard U fits), so the anchor follows
    whichever way the post is turned; the wings wrap the narrower face over
    ``wing_depth``. The ribbed rod and its concrete live in the footing below,
    so they are not redrawn."""
    collar = an.width + 2.0 * an.plate      # across the milled face: the gap + both wings
    wings = an.wing_depth                   # along the narrower face
    sz = an.air_gap + an.wing_height
    if size_x >= size_y:                    # wider face is x -> gap across x
        sx, sy = collar, wings
    else:                                   # wider face is y -> gap across y
        sx, sy = wings, collar
    return Box(
        pos=(cx - sx / 2.0, cy - sy / 2.0, base),
        size=(sx, sy, sz),
        category="anchor",
        material=(an.material or ""),
    )


def _brace(cx, cy, half, axis, sign, z_top, length, t) -> Prism:
    """A 45° knee brace (Kopfband) in a vertical plane.

    Its foot is fixed to the post face ``length`` below the beam underside and
    its head meets the beam underside ``length`` inward, so the run down the
    post equals the run along the beam (a 45° strut). ``axis`` picks the plane
    (``x`` -> x-z, ``y`` -> y-z) and ``sign`` points toward the structure
    interior; ``z_top`` is the beam underside where the head lands. Built as a
    square-section (``t`` x ``t``) tilted :class:`Prism`."""
    if axis == "x":
        pf = cx + sign * half                       # post face toward the interior
        a = np.array([pf, cy, z_top - length])      # foot, on the post
        b = np.array([pf + sign * length, cy, z_top])  # head, at the beam underside
        v = np.array([0.0, 1.0, 0.0])               # out-of-plane (thickness) dir
    else:
        pf = cy + sign * half
        a = np.array([cx, pf, z_top - length])
        b = np.array([cx, pf + sign * length, z_top])
        v = np.array([1.0, 0.0, 0.0])
    u = b - a
    u = u / np.linalg.norm(u)                        # brace axis
    p = np.cross(u, v)
    p = p / np.linalg.norm(p)                        # in-plane perpendicular
    hw = t / 2.0
    corners = np.array([
        a - hw * p - hw * v, a + hw * p - hw * v, a + hw * p + hw * v, a - hw * p + hw * v,
        b - hw * p - hw * v, b + hw * p - hw * v, b + hw * p + hw * v, b - hw * p + hw * v,
    ])
    return Prism(corners_arr=corners, category="brace")


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
    # Post Y centres. Explicit `rows_y_from_wall` (centre distances from the
    # house wall = back roof edge) wins: both rows are placed by those values so
    # the roof can overhang the ring front AND back. Else house_offset (attached:
    # front row on the footprint corner, house-side row pulled off the wall),
    # else evenly spaced.
    if ps.rows_y_from_wall is not None:
        ys = np.sort(np.array([oy + d - v for v in ps.rows_y_from_wall]))
    elif ps.house_offset is not None:
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

    # Foundation step along the house wall (optional). Its back face sits at the
    # wall front face (= the footprint back edge, oy + d) and it projects out
    # toward the pergola by `depth`. The house-side post row (nearest the wall,
    # the largest-y row) stands flush ON this step instead of on a dug footing.
    step = ps.house_step
    house_cy = ys[-1]
    if step is not None:
        sy1 = oy + d                         # wall front face = footprint back edge
        sy0 = sy1 - step.depth               # front edge of the step
        boxes.append(Box(
            pos=(step.x0, sy0, 0.0),
            size=(step.x1 - step.x0, step.depth, step.height),
            category="step",
            label="Stufe",
        ))

    # Footings + posts at each grid node. Post tops follow the sloped underside.
    # A house-side post that lands on the step gets no footing and starts at the
    # step top (z = step.height) — the step is its foundation. When a post anchor
    # (U-Stützenfuß) is configured, the post stands on it, lifted `air_gap` above
    # its foundation so the end grain ventilates.
    an = ps.anchor
    for cx in xs:
        for cy in ys:
            on_step = (step is not None and cy == house_cy
                       and step.x0 <= cx <= step.x1)
            base = step.height if on_step else 0.0
            if not on_step:
                boxes.append(Box(
                    pos=(cx - ps.footing.size / 2, cy - ps.footing.size / 2, -ps.footing.depth),
                    size=(ps.footing.size, ps.footing.size, ps.footing.depth),
                    category="footing",
                ))
            post_base = base
            if an is not None:
                boxes.append(_post_anchor(cx, cy, base, an, ps.size_x, ps.size_y))
                post_base = base + an.air_gap
            boxes.append(Box(
                pos=(cx - half_x, cy - half_y, post_base),
                size=(ps.size_x, ps.size_y, underside(cy) - post_base),
                category="post",
            ))

    # Beams sit on top of the posts.
    bm = pg.beams
    bh = bm.height
    # The roof ends ABOVE the beams (no front/back overhang): the covering, the
    # side beams AND the rafters all span between the OUTER faces of the front and
    # house-side beams. In flush framing the rafters cross OVER those beams as a
    # cross-lap (Kämmung, see joinery.py) and end flush with their outer faces — no
    # overhang. Both edges derive from the post-row centres (ys), so moving a row
    # moves its roof edge with it.
    roof_y0 = ys[0] - bm.width / 2     # front beam, outer (front) face
    roof_y1 = ys[-1] + bm.width / 2    # house-side beam, outer (house) face
    if flush:
        # One-level frame: a full perimeter ring of beams. Front/back beams run
        # along x (horizontal, stepped to each row's underside); the left/right
        # beams run along y and follow the slope, so they are tilted slabs. The
        # rafters (below) cross over the front/back beams flush (cross-lap), ending
        # at their outer faces.
        for cy in (ys[0], ys[-1]):
            boxes.append(Box(
                pos=(ox, cy - bm.width / 2, underside(cy)),
                size=(w, bm.width, bh),
                category="beam",
            ))
        for cx in (xs[0], xs[-1]):
            boxes.append(_slab(cx - bm.width / 2, cx + bm.width / 2, roof_y0, roof_y1,
                               underside(roof_y0), underside(roof_y1), bh, "beam"))
    elif bm.direction == "x":
        for cy in ys:
            boxes.append(Box(
                pos=(ox, cy - bm.width / 2, underside(cy)),
                size=(w, bm.width, bh),
                category="beam",
            ))
    else:  # beams along y -> they follow the slope, so build as slabs
        for cx in xs:
            boxes.append(_slab(cx - bm.width / 2, cx + bm.width / 2, roof_y0, roof_y1,
                               underside(roof_y0), underside(roof_y1), bh, "beam"))

    # Panelised rigid cover: split a "glass" cover into equal panels across x
    # (roof.panel_width). Each interior joint then lands ON a rafter — the
    # rafters below are placed under the joints — so every panel edge is
    # supported and the joints can be closed with a connecting H-Profil. With no
    # panel_width there are no joints and the rafters fall back to even spacing.
    roof = pg.roof
    panel_joints: List[float] = []
    if roof.kind == "glass" and roof.panel_width is not None:
        n_panels = max(1, int(round(w / roof.panel_width)))
        panel_w = w / n_panels
        panel_joints = [ox + i * panel_w for i in range(1, n_panels)]

    # Rafters laid across the beams; they span the roof (no overhang past the
    # beams) and follow the roof slope. Both framings run the rafters out to the
    # roof edge (the front/house beam OUTER faces). Stacked framing rests them ON
    # TOP of the beams; flush framing drops them flush into the beam tops as a
    # cross-lap (rafter underside is then rh below the beam top), giving one roof
    # plane — the rafter crosses the beam and ends flush with its outer face.
    rf = pg.rafters
    rh = rf.height
    rb = (bh - rh) if flush else bh    # rafter underside, measured above the post top
    if rf.direction == "y":
        if flush:
            if panel_joints:
                # One rafter under each panel joint, so every joint (and its
                # H-Profil) is carried and each panel edge rests on a support.
                centers = np.array(panel_joints)
            else:
                # The two side beams of the perimeter ring already carry the
                # roof's left/right edges, so they act as the outer supports. The
                # rafters are then spread evenly across the OPEN bay between the
                # side beams with equal gaps — none doubled up against a side beam.
                lo = xs[0] + bm.width / 2      # inner face of the left side beam
                hi = xs[-1] - bm.width / 2     # inner face of the right side beam
                n = max(1, int(round((hi - lo) / rf.spacing)) - 1)   # interior rafters
                centers = lo + (hi - lo) * np.arange(1, n + 1) / (n + 1)
            ry0, ry1 = roof_y0, roof_y1    # cross over, flush, out to the outer faces
        else:
            n = _count_by_spacing(w - rf.width, rf.spacing)
            centers = _linspace_centers(ox + rf.width / 2, w - rf.width, n)
            ry0, ry1 = roof_y0, roof_y1    # rest on top, out to the roof edge
        for cx in centers:
            boxes.append(_slab(cx - rf.width / 2, cx + rf.width / 2, ry0, ry1,
                               underside(ry0) + rb, underside(ry1) + rb,
                               rh, "rafter"))
    else:  # rafters along x -> horizontal, one per row, stepped in z
        a, b = roof_y0, roof_y1
        n = _count_by_spacing((b - a) - rf.width, rf.spacing)
        for cy in _linspace_centers(a + rf.width / 2, (b - a) - rf.width, n):
            boxes.append(Box(
                pos=(ox, cy - rf.width / 2, underside(cy) + rb),
                size=(w, rf.width, rh),
                category="rafter",
            ))

    # Roof surface follows the slope, resting on the plane formed by the rafter
    # tops (stacked) or the flush frame+rafter tops (flush).
    def roof_base(y: float) -> float:
        return underside(y) + bh + (0.0 if flush else rh)

    if roof.kind == "glass":
        # Panel material name for the Materialliste (e.g. "PVC"); blank -> the
        # category default. Panels span the slope (y) full length; joints run
        # down-slope in x and are placed at panel_joints (each over a rafter).
        pmat = roof.material or ""
        # The cover (panels + profiles) oversails the front beam by
        # ``front_overhang`` so the drip line falls INTO the gutter trough, not on
        # its rear lip. The slope plane simply continues forward (roof_base is
        # linear in y); the structure (beams/rafters) stays put.
        cover_y0 = roof_y0 - roof.front_overhang
        edges = [ox] + list(panel_joints) + [ox + w]   # panel boundaries in x
        for px0, px1 in zip(edges[:-1], edges[1:]):
            boxes.append(_slab(px0, px1, cover_y0, roof_y1,
                               roof_base(cover_y0), roof_base(roof_y1),
                               roof.thickness, "glass", material=pmat))
        # Connecting H-Profil straddling each interior joint, running down the
        # slope over its rafter; drawn a little proud of the panels (a raised
        # seam / glazing bar). One per joint.
        pw = roof.profile_width
        cap = roof.thickness + 6.0                      # sits ~6 mm above the panels
        jmat = roof.profile_material or ""
        for jx in panel_joints:
            boxes.append(_slab(jx - pw / 2, jx + pw / 2, cover_y0, roof_y1,
                               roof_base(cover_y0), roof_base(roof_y1),
                               cap, "profile", material=jmat))
        # Edge/closure profiles along the two side roof edges, clamping each
        # outer panel edge onto the side beam (the front edge drains into the
        # gutter and the house edge is a wall flashing, so only the sides get one).
        if roof.edge_profile_width is not None:
            ew = roof.edge_profile_width
            emat = roof.edge_profile_material or ""
            for ex0 in (ox, ox + w - ew):
                boxes.append(_slab(ex0, ex0 + ew, cover_y0, roof_y1,
                                   roof_base(cover_y0), roof_base(roof_y1),
                                   cap, "edge_profile", material=emat))
    elif roof.kind != "open":
        sw, sh = roof.slat_width, roof.slat_height
        if roof.direction == "x":  # slats run along x at stepped heights
            span_y = roof_y1 - roof_y0
            n = _count_by_spacing(span_y - sw, roof.spacing)
            for cy in _linspace_centers(roof_y0 + sw / 2, span_y - sw, n):
                boxes.append(Box(
                    pos=(ox, cy - sw / 2, roof_base(cy)),
                    size=(w, sw, sh),
                    category="slat",
                ))
        else:  # slats run along y -> tilted slabs
            n = _count_by_spacing(w - sw, roof.spacing)
            for cx in _linspace_centers(ox + sw / 2, w - sw, n):
                boxes.append(_slab(cx - sw / 2, cx + sw / 2, roof_y0, roof_y1,
                                   roof_base(roof_y0), roof_base(roof_y1), sh, "slat"))

    # Rain gutter along the low (front) eave, just outboard of the front edge.
    if roof.gutter:
        g_depth, g_h = 120.0, 90.0
        eave_top = roof_base(roof_y0)           # underside of the roof at the front
        boxes.append(Box(
            pos=(ox, roof_y0 - g_depth, eave_top - g_h),
            size=(w, g_depth, g_h),
            category="gutter",
        ))

    # Diagonal knee braces (Kopfbänder) triangulating the post heads, for
    # lateral (racking) stiffness. The bare post-beam frame is pin-jointed and
    # would otherwise sway; each braced OUTER corner post gets a 45° strut up to
    # the beam underside, pointing toward the structure interior. "x" braces sit
    # in x-z planes (resist sway parallel to the wall); "y" braces in y-z planes
    # (resist sway toward/away from the house). The house-side beam slopes, so
    # the "y" head height is taken at the head's y position.
    # ``x_sides`` / ``y_sides`` narrow which planes are braced: the front (low,
    # house-away) row is ys[0] and the house row ys[-1]; the left column is xs[0]
    # and the right xs[-1]. Leaving a side out clears it (e.g. an open front).
    brc = pg.braces
    if brc is not None:
        for cx in (xs[0], xs[-1]):
            sx = 1.0 if cx == xs[0] else -1.0
            col = "left" if cx == xs[0] else "right"
            for cy in (ys[0], ys[-1]):
                sy = 1.0 if cy == ys[0] else -1.0
                row = "front" if cy == ys[0] else "house"
                if "x" in brc.directions and row in brc.x_sides:
                    boxes.append(_brace(cx, cy, half_x, "x", sx,
                                        underside(cy), brc.length, brc.size))
                if "y" in brc.directions and col in brc.y_sides:
                    y_head = cy + sy * (half_y + brc.length)
                    boxes.append(_brace(cx, cy, half_y, "y", sy,
                                        underside(y_head), brc.length, brc.size))

    # Fabric curtains on curtain rods, strung between the corner posts. Each
    # side gets one horizontal rod (attached to that side's two corner posts)
    # with a fabric panel hanging from it down toward the ground.
    cu = pg.curtains
    if cu is not None:
        rd = cu.rod_diameter
        ft = cu.fabric_thickness
        x0p, x1p = xs[0], xs[-1]                 # left / right post centre lines
        y0p, y1p = ys[0], ys[-1]                 # front / back post centre lines
        for side in cu.sides:
            if side in ("left", "right"):        # rod runs front->back along y
                xc = x0p if side == "left" else x1p
                rod_cz = underside(y0p) - cu.top_gap          # horizontal rod centre
                # Rod: a square bar spanning the posts (plus a small overhang).
                boxes.append(Box(
                    pos=(xc - rd / 2, y0p - cu.overhang, rod_cz - rd / 2),
                    size=(rd, (y1p - y0p) + 2 * cu.overhang, rd),
                    category="rod",
                ))
                # Fabric: a thin panel hung from the rod down to the hem.
                boxes.append(Box(
                    pos=(xc - ft / 2, y0p, cu.bottom_gap),
                    size=(ft, y1p - y0p, rod_cz - cu.bottom_gap),
                    category="curtain",
                ))
            else:                                # front / back: rod runs along x
                yc = y0p if side == "front" else y1p
                rod_cz = underside(yc) - cu.top_gap
                boxes.append(Box(
                    pos=(x0p - cu.overhang, yc - rd / 2, rod_cz - rd / 2),
                    size=((x1p - x0p) + 2 * cu.overhang, rd, rd),
                    category="rod",
                ))
                boxes.append(Box(
                    pos=(x0p, yc - ft / 2, cu.bottom_gap),
                    size=(x1p - x0p, ft, rod_cz - cu.bottom_gap),
                    category="curtain",
                ))

    return boxes


def build_surroundings(cfg: Config) -> List[Box]:
    boxes: List[Box] = []
    for w in cfg.walls:
        boxes.append(Box(
            pos=(w.at[0], w.at[1], w.z0),
            size=(w.size[0], w.size[1], w.height),
            category=(w.category or "wall"),
            label=w.name,
            board_height=w.board_height,
        ))
    for b in cfg.buildings:
        boxes.append(Box(
            pos=(b.at[0], b.at[1], b.z0),
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
