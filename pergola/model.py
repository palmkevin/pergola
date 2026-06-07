"""Parse and validate ``site.yaml`` into typed dataclasses.

All lengths are normalised to **millimetres** regardless of the file's ``units``.
Validation raises :class:`ConfigError` with a friendly, specific message so that
mistakes in the YAML are easy to fix.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import yaml


class ConfigError(ValueError):
    """Raised when site.yaml is missing data or has invalid values."""


# Conversion factors to millimetres.
_UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}


# --------------------------------------------------------------------------- #
#  Dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class Footing:
    size: float
    depth: float


@dataclass
class Posts:
    size_x: float       # post cross-section along x
    size_y: float       # post cross-section along y (equal to size_x for a square post)
    count_x: int
    count_y: int
    footing: Footing
    # Attached pergolas only: distance from the house wall to the FACE of the
    # house-side post row. When set, the front row sits on the footprint corners
    # and the back row is pulled this far off the wall (the roof still spans to
    # the wall). None -> posts are evenly spaced across the footprint as before.
    house_offset: Optional[float] = None
    # Explicit post-row CENTRE distances from the house wall (back roof edge),
    # one per row (== count_y). When set, both rows are placed by these values
    # so the roof can overhang the post ring on BOTH the front and house sides.
    # Takes precedence over house_offset. None -> use house_offset / even layout.
    rows_y_from_wall: Optional[List[float]] = None


@dataclass
class Beams:
    width: float
    height: float
    direction: str  # "x" or "y"


@dataclass
class Rafters:
    width: float
    height: float
    spacing: float
    direction: str


@dataclass
class Roof:
    kind: str           # louvered | slatted | glass | open
    slat_width: float
    slat_height: float
    spacing: float
    direction: str
    thickness: float    # glass pane thickness (only used when kind == "glass")
    tilt_deg: float     # roof pitch; slopes DOWN toward the front (y-min), house
                        # side (y-max) high. clear_height is the house-side value.
    gutter: bool        # add a rain gutter along the low (front) eave


@dataclass
class Curtains:
    """Fabric curtains hung on curtain rods between the corner posts.

    Each named side gets a horizontal rod spanning between that side's two
    corner posts (attached to them), with a fabric panel hanging from it down
    toward the ground. Sides: ``left``/``right`` (rods run front->back along y)
    and ``front``/``back`` (rods run left->right along x)."""

    sides: List[str]            # subset of left | right | front | back
    rod_diameter: float         # curtain-rod cross-section (square, mm)
    fabric_thickness: float     # drawn thickness of the hanging fabric (mm)
    top_gap: float              # rod centre this far below the beam underside
    bottom_gap: float           # fabric hem this far above the ground (z=0)
    overhang: float             # rod extension beyond each post end


@dataclass
class Pergola:
    type: str           # attached | freestanding
    origin: Tuple[float, float]
    width: float
    depth: float
    clear_height: float
    framing: str        # "stacked" (rafters on top of beams) | "flush" (one-level
                        # frame: a perimeter beam ring with rafters housed flush
                        # between the front/back beams, so the roof is one plane)
    posts: Posts
    beams: Beams
    rafters: Rafters
    roof: Roof
    curtains: Optional[Curtains] = None


@dataclass
class Block:
    """A wall or building footprint."""

    name: str
    at: Tuple[float, float]
    size: Tuple[float, float]
    height: float


@dataclass
class Path:
    """A sloping garden path / ramp: a flat footprint that rises to ``rise`` at
    one edge (``high_end``) and meets ground level (z=0) at the opposite edge."""

    name: str
    at: Tuple[float, float]    # min corner (x, y)
    size: Tuple[float, float]  # (x, y) footprint
    rise: float                # height (z) at the high edge
    high_end: str              # which edge is high: x_min | x_max | y_min | y_max


@dataclass
class Ground:
    origin: Tuple[float, float]
    extent: Tuple[float, float]


@dataclass
class Config:
    units: str
    north_deg: float
    pergola: Pergola
    walls: List[Block]
    buildings: List[Block]
    beds: List[Block]
    paths: List[Path]
    ground: Ground


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _require(d: dict, key: str, ctx: str):
    if not isinstance(d, dict) or key not in d:
        raise ConfigError(f"Missing '{key}' in {ctx}.")
    return d[key]


def _num(value, ctx: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{ctx} must be a number, got {value!r}.")
    if positive and value <= 0:
        raise ConfigError(f"{ctx} must be greater than 0, got {value}.")
    return float(value)


def _pair(value, ctx: str) -> Tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigError(f"{ctx} must be a list of two numbers, got {value!r}.")
    return (_num(value[0], f"{ctx}[0]"), _num(value[1], f"{ctx}[1]"))


# --------------------------------------------------------------------------- #
#  Loader
# --------------------------------------------------------------------------- #
def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} did not parse to a mapping.")

    units = str(raw.get("units", "mm")).lower()
    if units not in _UNIT_TO_MM:
        raise ConfigError(f"units must be one of {list(_UNIT_TO_MM)}, got {units!r}.")
    scale = _UNIT_TO_MM[units]

    def L(value, ctx, *, positive=False) -> float:  # length -> mm
        return _num(value, ctx, positive=positive) * scale

    def P(value, ctx) -> Tuple[float, float]:       # pair of lengths -> mm
        a, b = _pair(value, ctx)
        return (a * scale, b * scale)

    site = raw.get("site") or {}
    north_deg = _num(site.get("north_deg", 0), "site.north_deg")

    # --- pergola ----------------------------------------------------------- #
    pg = _require(raw, "pergola", "the file")
    fp = _require(pg, "footprint", "pergola")
    p_type = str(pg.get("type", "freestanding")).lower()
    if p_type not in ("attached", "freestanding"):
        raise ConfigError("pergola.type must be 'attached' or 'freestanding'.")

    po = _require(pg, "posts", "pergola")
    cx = int(_num(_require(po, "count_x", "pergola.posts"), "pergola.posts.count_x"))
    cy = int(_num(_require(po, "count_y", "pergola.posts"), "pergola.posts.count_y"))
    if cx < 2 or cy < 2:
        raise ConfigError("pergola.posts.count_x and count_y must each be >= 2.")
    fo = _require(po, "footing", "pergola.posts")
    house_offset = po.get("house_offset")
    rows_raw = po.get("rows_y_from_wall")
    rows_y_from_wall = None
    if rows_raw is not None:
        if not isinstance(rows_raw, (list, tuple)) or len(rows_raw) != cy:
            raise ConfigError(
                "pergola.posts.rows_y_from_wall must list exactly count_y "
                f"value(s) (one centre distance from the wall per row), got {rows_raw!r}.")
        rows_y_from_wall = [
            L(v, "pergola.posts.rows_y_from_wall", positive=True) for v in rows_raw]
    # size: a single number (square post) or a [x, y] pair (rectangular post).
    raw_size = _require(po, "size", "pergola.posts")
    if isinstance(raw_size, (list, tuple)):
        size_x, size_y = P(raw_size, "pergola.posts.size")
        if size_x <= 0 or size_y <= 0:
            raise ConfigError("pergola.posts.size values must each be greater than 0.")
    else:
        size_x = size_y = L(raw_size, "pergola.posts.size", positive=True)
    posts = Posts(
        size_x=size_x,
        size_y=size_y,
        count_x=cx,
        count_y=cy,
        footing=Footing(
            size=L(_require(fo, "size", "footing"), "footing.size", positive=True),
            depth=L(_require(fo, "depth", "footing"), "footing.depth", positive=True),
        ),
        house_offset=(L(house_offset, "pergola.posts.house_offset", positive=True)
                      if house_offset is not None else None),
        rows_y_from_wall=rows_y_from_wall,
    )

    be = _require(pg, "beams", "pergola")
    beams = Beams(
        width=L(_require(be, "width", "pergola.beams"), "pergola.beams.width", positive=True),
        height=L(_require(be, "height", "pergola.beams"), "pergola.beams.height", positive=True),
        direction=_axis(be.get("direction", "x"), "pergola.beams.direction"),
    )

    ra = _require(pg, "rafters", "pergola")
    rafters = Rafters(
        width=L(_require(ra, "width", "pergola.rafters"), "pergola.rafters.width", positive=True),
        height=L(_require(ra, "height", "pergola.rafters"), "pergola.rafters.height", positive=True),
        spacing=L(_require(ra, "spacing", "pergola.rafters"), "pergola.rafters.spacing", positive=True),
        direction=_axis(ra.get("direction", "y"), "pergola.rafters.direction"),
    )

    ro = pg.get("roof") or {}
    kind = str(ro.get("kind", "open")).lower()
    if kind not in ("louvered", "slatted", "glass", "open"):
        raise ConfigError("pergola.roof.kind must be 'louvered', 'slatted', 'glass' or 'open'.")
    slat = ro.get("slat") or {}
    tilt = _num(ro.get("tilt_deg", 0), "pergola.roof.tilt_deg")
    if not 0 <= tilt < 60:
        raise ConfigError("pergola.roof.tilt_deg must be between 0 and 60 degrees.")
    roof = Roof(
        kind=kind,
        slat_width=L(slat.get("width", 80), "pergola.roof.slat.width", positive=True),
        slat_height=L(slat.get("height", 20), "pergola.roof.slat.height", positive=True),
        spacing=L(ro.get("spacing", 100), "pergola.roof.spacing", positive=True),
        direction=_axis(ro.get("direction", "x"), "pergola.roof.direction"),
        thickness=L(ro.get("thickness", 10), "pergola.roof.thickness", positive=True),
        tilt_deg=tilt,
        gutter=bool(ro.get("gutter", False)),
    )

    framing = str(pg.get("framing", "stacked")).lower()
    if framing not in ("stacked", "flush"):
        raise ConfigError("pergola.framing must be 'stacked' or 'flush'.")

    curtains = None
    cu = pg.get("curtains")
    if cu:
        if not isinstance(cu, dict):
            raise ConfigError("pergola.curtains must be a mapping of options.")
        raw_sides = cu.get("sides", ["left", "right"])
        if not isinstance(raw_sides, (list, tuple)) or not raw_sides:
            raise ConfigError("pergola.curtains.sides must be a non-empty list.")
        sides = []
        for s in raw_sides:
            sv = str(s).lower()
            if sv not in ("left", "right", "front", "back"):
                raise ConfigError(
                    "pergola.curtains.sides entries must be one of "
                    f"left/right/front/back, got {s!r}.")
            sides.append(sv)
        curtains = Curtains(
            sides=sides,
            rod_diameter=L(cu.get("rod_diameter", 30), "pergola.curtains.rod_diameter", positive=True),
            fabric_thickness=L(cu.get("fabric_thickness", 30), "pergola.curtains.fabric_thickness", positive=True),
            top_gap=L(cu.get("top_gap", 80), "pergola.curtains.top_gap"),
            bottom_gap=L(cu.get("bottom_gap", 100), "pergola.curtains.bottom_gap"),
            overhang=L(cu.get("overhang", 40), "pergola.curtains.overhang"),
        )

    pergola = Pergola(
        type=p_type,
        origin=P(pg.get("origin", [0, 0]), "pergola.origin"),
        width=L(_require(fp, "width", "pergola.footprint"), "pergola.footprint.width", positive=True),
        depth=L(_require(fp, "depth", "pergola.footprint"), "pergola.footprint.depth", positive=True),
        clear_height=L(_require(pg, "clear_height", "pergola"), "pergola.clear_height", positive=True),
        framing=framing,
        posts=posts,
        beams=beams,
        rafters=rafters,
        roof=roof,
        curtains=curtains,
    )

    # --- surroundings ------------------------------------------------------ #
    surroundings = raw.get("surroundings") or {}
    walls = [_block(w, P, L, "wall") for w in (surroundings.get("walls") or [])]
    buildings = [_block(b, P, L, "building") for b in (surroundings.get("buildings") or [])]
    beds = [_block(b, P, L, "bed") for b in (surroundings.get("beds") or [])]
    paths = [_path(p, P, L) for p in (surroundings.get("paths") or [])]

    # --- ground ------------------------------------------------------------ #
    gr = raw.get("ground") or {}
    ground = Ground(
        origin=P(gr.get("origin", [-1000, -1000]), "ground.origin"),
        extent=P(gr.get("extent", [8000, 6000]), "ground.extent"),
    )

    return Config(
        units=units,
        north_deg=north_deg,
        pergola=pergola,
        walls=walls,
        buildings=buildings,
        beds=beds,
        paths=paths,
        ground=ground,
    )


def _axis(value, ctx: str) -> str:
    v = str(value).lower()
    if v not in ("x", "y"):
        raise ConfigError(f"{ctx} must be 'x' or 'y', got {value!r}.")
    return v


_DE_NAMES = {"wall": "Wand", "building": "Gebäude", "bed": "Beet"}


def _block(item, P, L, kind: str) -> Block:
    name = str(item.get("name", _DE_NAMES.get(kind, kind.title())))
    return Block(
        name=name,
        at=P(_require(item, "at", f"{kind} '{name}'"), f"{kind}.at"),
        size=P(_require(item, "size", f"{kind} '{name}'"), f"{kind}.size"),
        height=L(_require(item, "height", f"{kind} '{name}'"), f"{kind}.height", positive=True),
    )


def _path(item, P, L) -> Path:
    name = str(item.get("name", "Pfad"))
    high = str(item.get("high_end", "x_min")).lower()
    if high not in ("x_min", "x_max", "y_min", "y_max"):
        raise ConfigError(
            f"path '{name}': high_end must be one of x_min/x_max/y_min/y_max, got {high!r}.")
    return Path(
        name=name,
        at=P(_require(item, "at", f"path '{name}'"), "path.at"),
        size=P(_require(item, "size", f"path '{name}'"), "path.size"),
        rise=L(_require(item, "rise", f"path '{name}'"), "path.rise", positive=True),
        high_end=high,
    )
