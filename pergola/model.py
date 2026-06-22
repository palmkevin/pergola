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
class HouseStep:
    """A foundation step/ledge running along the house wall at its base.

    The house-side post row stands flush on this step instead of on a dug
    concrete footing — the step *is* their foundation. It spans ``[x0, x1]``
    along the wall (x), projects ``depth`` out from the wall front face (toward
    the pergola, in -y) and rises ``height`` above the ground (z = 0); the
    house-side posts start at z = ``height`` (on top of it)."""

    height: float       # z height of the step (posts rest on top)
    depth: float        # y depth, projecting out from the wall front face
    x0: float           # left end along x
    x1: float           # right end along x


@dataclass
class PostAnchor:
    """Galvanised steel post base (U-Stützenfuß) tying each post to its
    foundation, instead of standing the post directly on the concrete.

    The real part is a 71 mm Alberts U-anchor on a ribbed rod cast into the
    concrete (CE ETA-10/0210). The post's wider face is milled down (80 ->
    ``width``) so the standard U fits snug and FLUSH, and the post stands
    ``air_gap`` clear of the concrete (a spacer / capillary break so the end
    grain ventilates). Modelled as a single steel collar at the post foot that
    fills the air gap and wraps ``wing_height`` up the post sides like the U's
    wings; the cast-in rod/concrete lives in the footing. The gap runs across x
    (the milled wider face). See CLAUDE.md "Pfosten-Verankerung"."""

    width: float        # U gap = the milled post face it clamps (mm)
    wing_depth: float   # how far the wings wrap along the other post face (mm)
    wing_height: float  # how far the wings rise up the post sides (mm)
    plate: float        # steel thickness (mm)
    air_gap: float      # post lifted this far above the concrete (ventilation, mm)
    material: Optional[str] = None


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
    # Foundation step along the house wall: when set, the house-side post row
    # (the row nearest the wall) stands on this step rather than on dug footings.
    house_step: Optional["HouseStep"] = None
    # Galvanised steel post base (U-Stützenfuß) under each post. When set, every
    # post stands on this anchor, lifted `air_gap` above its foundation. None ->
    # the post sits directly on the footing/step (the old behaviour).
    anchor: Optional["PostAnchor"] = None


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
    # Material name of the rigid cover (only used when kind == "glass"); shown in
    # the Materialliste. None -> fall back to the generic "Glas / PVC-Platte".
    material: Optional[str] = None
    # Panelisation of a "glass" cover: split it into equal panels ~this wide
    # across x. Each interior joint then lands on a rafter (the rafters are
    # placed under the joints) and gets a connecting H-Profil. None -> one panel.
    panel_width: Optional[float] = None
    profile_width: float = 50.0       # H-Profil width across x (straddles a joint)
    profile_material: Optional[str] = None  # H-Profil material (Materialliste)
    # Edge/closure profiles along the two side (left/right) roof edges, clamping
    # each outer panel edge down onto the side beam. None -> no edge profiles.
    # (The front edge drains into the gutter and the house edge is a wall
    # flashing, so only the two longitudinal side edges get a clamp profile.)
    edge_profile_width: Optional[float] = None
    edge_profile_material: Optional[str] = None


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
class Braces:
    """Diagonal knee braces (Kopfbänder) at the post heads that triangulate the
    post-beam corners and give the otherwise pin-jointed frame its lateral
    (racking) stiffness.

    Each outer corner post gets a 45° strut running from the post face up to the
    beam underside. ``directions`` selects the vertical plane(s) each corner is
    braced in: ``x`` -> braces in x-z planes (resist sway *parallel* to the wall),
    ``y`` -> braces in y-z planes (resist sway *toward/away* from the wall).

    ``x_sides`` / ``y_sides`` then narrow *which* of those planes actually get a
    brace, so a side can be left clear (e.g. an open front): the x-z planes are
    the ``front`` and ``house`` post rows, the y-z planes the ``left`` and
    ``right`` post columns. Default is every plane braced."""

    size: float            # square cross-section of the brace (mm)
    length: float          # 45° leg length: run down the post == run along the beam
    directions: List[str]  # subset of {"x", "y"}: which vertical planes to brace
    x_sides: List[str]     # subset of {"front", "house"}: rows that get x-braces
    y_sides: List[str]     # subset of {"left", "right"}: columns that get y-braces


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
    braces: Optional[Braces] = None


@dataclass
class Block:
    """A wall or building footprint.

    ``z0`` is the base height (ground = 0 for a normal wall/building); set it to
    float the block — e.g. a fascia board / eave block sitting up at the garden
    house's roof edge rather than starting from the ground."""

    name: str
    at: Tuple[float, float]
    size: Tuple[float, float]
    height: float
    z0: float = 0.0


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
    # Foundation step along the house wall (optional). The house-side post row
    # stands flush on it instead of on dug footings.
    hs_raw = po.get("house_step")
    house_step = None
    if hs_raw is not None:
        if not isinstance(hs_raw, dict):
            raise ConfigError("pergola.posts.house_step must be a mapping of options.")
        sx0, sx1 = P(_require(hs_raw, "x_extent", "pergola.posts.house_step"),
                     "pergola.posts.house_step.x_extent")
        if sx1 <= sx0:
            raise ConfigError(
                "pergola.posts.house_step.x_extent must be [x0, x1] with x1 > x0, "
                f"got {[sx0, sx1]!r}.")
        house_step = HouseStep(
            height=L(_require(hs_raw, "height", "pergola.posts.house_step"),
                     "pergola.posts.house_step.height", positive=True),
            depth=L(_require(hs_raw, "depth", "pergola.posts.house_step"),
                    "pergola.posts.house_step.depth", positive=True),
            x0=sx0,
            x1=sx1,
        )
    # Post anchor (galvanised U-Stützenfuß) under each post (optional).
    an_raw = po.get("anchor")
    anchor = None
    if an_raw is not None:
        if not isinstance(an_raw, dict):
            raise ConfigError("pergola.posts.anchor must be a mapping of options.")
        anchor = PostAnchor(
            width=L(_require(an_raw, "width", "pergola.posts.anchor"),
                    "pergola.posts.anchor.width", positive=True),
            wing_depth=L(an_raw.get("wing_depth", 60),
                         "pergola.posts.anchor.wing_depth", positive=True),
            wing_height=L(an_raw.get("wing_height", 150),
                          "pergola.posts.anchor.wing_height", positive=True),
            plate=L(an_raw.get("plate", 4),
                    "pergola.posts.anchor.plate", positive=True),
            air_gap=L(an_raw.get("air_gap", 10),
                      "pergola.posts.anchor.air_gap", positive=True),
            material=(str(an_raw["material"]) if an_raw.get("material") is not None else None),
        )
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
        house_step=house_step,
        anchor=anchor,
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
    # Optional panelisation of a rigid ("glass") cover. `panel_width` splits the
    # cover into equal panels across x; `join_profile` describes the connecting
    # H-Profil placed over each interior joint.
    panel_width = ro.get("panel_width")
    jp = ro.get("join_profile") or {}
    if not isinstance(jp, dict):
        raise ConfigError("pergola.roof.join_profile must be a mapping of options.")
    ep_raw = ro.get("edge_profile")
    edge_profile_width = None
    edge_profile_material = None
    if ep_raw is not None:
        if not isinstance(ep_raw, dict):
            raise ConfigError("pergola.roof.edge_profile must be a mapping of options.")
        edge_profile_width = L(ep_raw.get("width", 40),
                               "pergola.roof.edge_profile.width", positive=True)
        edge_profile_material = (str(ep_raw["material"])
                                 if ep_raw.get("material") is not None else None)
    roof = Roof(
        kind=kind,
        slat_width=L(slat.get("width", 80), "pergola.roof.slat.width", positive=True),
        slat_height=L(slat.get("height", 20), "pergola.roof.slat.height", positive=True),
        spacing=L(ro.get("spacing", 100), "pergola.roof.spacing", positive=True),
        direction=_axis(ro.get("direction", "x"), "pergola.roof.direction"),
        thickness=L(ro.get("thickness", 10), "pergola.roof.thickness", positive=True),
        tilt_deg=tilt,
        gutter=bool(ro.get("gutter", False)),
        material=(str(ro["material"]) if ro.get("material") is not None else None),
        panel_width=(L(panel_width, "pergola.roof.panel_width", positive=True)
                     if panel_width is not None else None),
        profile_width=L(jp.get("width", 50), "pergola.roof.join_profile.width", positive=True),
        profile_material=(str(jp["material"]) if jp.get("material") is not None else None),
        edge_profile_width=edge_profile_width,
        edge_profile_material=edge_profile_material,
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

    braces = None
    br = pg.get("braces")
    if br:
        if not isinstance(br, dict):
            raise ConfigError("pergola.braces must be a mapping of options.")
        raw_dirs = br.get("directions", ["x", "y"])
        if not isinstance(raw_dirs, (list, tuple)) or not raw_dirs:
            raise ConfigError(
                "pergola.braces.directions must be a non-empty list of 'x'/'y'.")
        directions = [_axis(d, "pergola.braces.directions") for d in raw_dirs]
        x_sides = _sides(br.get("x_sides", ["front", "house"]),
                         ("front", "house"), "pergola.braces.x_sides")
        y_sides = _sides(br.get("y_sides", ["left", "right"]),
                         ("left", "right"), "pergola.braces.y_sides")
        braces = Braces(
            size=L(br.get("size", 60), "pergola.braces.size", positive=True),
            length=L(br.get("length", 400), "pergola.braces.length", positive=True),
            directions=directions,
            x_sides=x_sides,
            y_sides=y_sides,
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
        braces=braces,
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


def _sides(value, allowed: Tuple[str, ...], ctx: str) -> List[str]:
    """Validate a list of side names (a subset of ``allowed``), preserving order
    and dropping duplicates. An empty list means 'no side braced on this axis'."""
    if not isinstance(value, (list, tuple)):
        raise ConfigError(
            f"{ctx} must be a list, any of {list(allowed)}, got {value!r}.")
    out: List[str] = []
    for item in value:
        v = str(item).lower()
        if v not in allowed:
            raise ConfigError(
                f"{ctx} entries must be one of {list(allowed)}, got {item!r}.")
        if v not in out:
            out.append(v)
    return out


_DE_NAMES = {"wall": "Wand", "building": "Gebäude", "bed": "Beet"}


def _block(item, P, L, kind: str) -> Block:
    name = str(item.get("name", _DE_NAMES.get(kind, kind.title())))
    return Block(
        name=name,
        at=P(_require(item, "at", f"{kind} '{name}'"), f"{kind}.at"),
        size=P(_require(item, "size", f"{kind} '{name}'"), f"{kind}.size"),
        height=L(_require(item, "height", f"{kind} '{name}'"), f"{kind}.height", positive=True),
        z0=L(item.get("z0", 0), f"{kind}.z0"),
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
