"""Parse and validate ``site.yaml`` into typed dataclasses.

All lengths are normalised to **millimetres** regardless of the file's ``units``.
Validation raises :class:`ConfigError` with a friendly, specific message so that
mistakes in the YAML are easy to fix.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

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
    size: float
    count_x: int
    count_y: int
    footing: Footing


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


@dataclass
class Pergola:
    type: str           # attached | freestanding
    origin: Tuple[float, float]
    width: float
    depth: float
    clear_height: float
    posts: Posts
    beams: Beams
    rafters: Rafters
    roof: Roof


@dataclass
class Block:
    """A wall or building footprint."""

    name: str
    at: Tuple[float, float]
    size: Tuple[float, float]
    height: float


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
    posts = Posts(
        size=L(_require(po, "size", "pergola.posts"), "pergola.posts.size", positive=True),
        count_x=cx,
        count_y=cy,
        footing=Footing(
            size=L(_require(fo, "size", "footing"), "footing.size", positive=True),
            depth=L(_require(fo, "depth", "footing"), "footing.depth", positive=True),
        ),
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
    roof = Roof(
        kind=kind,
        slat_width=L(slat.get("width", 80), "pergola.roof.slat.width", positive=True),
        slat_height=L(slat.get("height", 20), "pergola.roof.slat.height", positive=True),
        spacing=L(ro.get("spacing", 100), "pergola.roof.spacing", positive=True),
        direction=_axis(ro.get("direction", "x"), "pergola.roof.direction"),
        thickness=L(ro.get("thickness", 10), "pergola.roof.thickness", positive=True),
    )

    pergola = Pergola(
        type=p_type,
        origin=P(pg.get("origin", [0, 0]), "pergola.origin"),
        width=L(_require(fp, "width", "pergola.footprint"), "pergola.footprint.width", positive=True),
        depth=L(_require(fp, "depth", "pergola.footprint"), "pergola.footprint.depth", positive=True),
        clear_height=L(_require(pg, "clear_height", "pergola"), "pergola.clear_height", positive=True),
        posts=posts,
        beams=beams,
        rafters=rafters,
        roof=roof,
    )

    # --- surroundings ------------------------------------------------------ #
    surroundings = raw.get("surroundings") or {}
    walls = [_block(w, P, L, "wall") for w in (surroundings.get("walls") or [])]
    buildings = [_block(b, P, L, "building") for b in (surroundings.get("buildings") or [])]

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
        ground=ground,
    )


def _axis(value, ctx: str) -> str:
    v = str(value).lower()
    if v not in ("x", "y"):
        raise ConfigError(f"{ctx} must be 'x' or 'y', got {value!r}.")
    return v


def _block(item, P, L, kind: str) -> Block:
    name = str(item.get("name", kind.title()))
    return Block(
        name=name,
        at=P(_require(item, "at", f"{kind} '{name}'"), f"{kind}.at"),
        size=P(_require(item, "size", f"{kind} '{name}'"), f"{kind}.size"),
        height=L(_require(item, "height", f"{kind} '{name}'"), f"{kind}.height", positive=True),
    )
