# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A parametric generator that turns a single description of a garden **pergola** and its
surroundings into two kinds of deliverable from one source model:
1. **Architect-style drawings** — dimensioned 2D plan + elevations and a simple isometric 3D,
   as **PNG + PDF + HTML** (viewable with no special software).
2. **A real 3D solid model** — exported as **STEP** (editable CAD / hand to a fabricator),
   **STL** (3D printing / quick view) and **GLB** (rotate / photorealistic render, also embedded
   as an interactive viewer in the HTML).

The end user drives this by describing measurements in plain language (or editing `site.yaml`);
they do not operate CAD software themselves.

## Core design principle

**Model everything once as 3D boxes, then derive every output from that single model.**
`build.py` expands the YAML parameters into individual boxes (each post, beam, rafter, slat,
footing, wall, building). Every 2D view is an orthographic projection of those boxes, the
isometric drawing uses the same boxes, and the solid model (`solid.py`) turns each box/prism
into a B-rep solid — so drawings and the CAD model stay dimensionally identical. When adding a
feature, add it to the box model first; every output follows.

## How to run

**Canonical (cloud):** push to `main` → GitHub Actions (`.github/workflows/deploy.yml`) builds
the image, runs `generate.py`, and publishes `output/` to GitHub Pages at
**https://palmkevin.github.io/pergola/**. The workflow reproduces `run.sh` step-for-step, so
**keep it in step with `run.sh` / `Dockerfile`** (it triggers on changes to `site.yaml`,
`pergola/**`, `generate.py`, `requirements.txt`, `Dockerfile`, and the workflow itself; a manual
"Run workflow" button also exists). Pages serves over HTTPS, so the embedded `<model-viewer>`
3D loads — that's the cloud replacement for the old local `http.server`.

**Local (optional / offline):**

```bash
./run.sh                # build image (first time) + generate from site.yaml
./run.sh other.yaml     # use a different config
```

Runs inside a `python:3.12-slim` Docker container (the host Python is 3.9; do not rely on it).
`run.sh` maps the caller's uid so `output/` files are not root-owned. Outputs:
`output/{plan,elev_front,elev_side,iso3d}.png`, `output/plan.pdf`, `output/index.html`,
and the 3D model `output/model.{step,stl,glb}`.

After generating, `run.sh` serves `output/` over HTTP at **http://localhost:8000/** (a
backgrounded host `python3 -m http.server`, started only if the port is not already answering) —
the local stand-in for the Pages URL. View there, not by opening the file directly — browsers
block the `model.glb` fetch under a `file://` URL, so the embedded `<model-viewer>` 3D only loads
over HTTP. The server streams the live directory, so the URL keeps showing the latest output after
every regeneration (no restart).

Always **rebuild the image after editing `requirements.txt` or the `Dockerfile`**
(`docker build -t pergola-plan .`); code changes need no rebuild (the project is mounted).

## Verifying changes

There are no unit tests — verification is visual. After a change, run `./run.sh` and **read the
generated PNGs** (plan, elevations, 3D) to confirm geometry, dimensions, and labels are correct.
For solid-model changes, also re-import `output/model.step` with `build123d.import_step` and sanity
-check the solid count, total volume and bounding box against the box model (a quick way to catch a
member that failed to become a watertight solid).

**Verifying in the cloud / web sandbox.** The remote (Claude Code on the web) environment has **no
Docker daemon** (`docker build` / `run.sh` fail) and its host Python has none of the deps, so the
flow above does not run there. Instead: make a venv and install **only** the 2D stack —
`matplotlib numpy PyYAML Jinja2` — then render the views directly off the box model (import
`pergola.build` + `pergola.views2d` / `pergola.view3d`, call `render_plan` / `render_front` /
`render_side` / `render_iso`, `savefig`) and **read those PNGs**. Deliberately **skip `solid.py`**
(and `generate.py`, which imports it): `build123d` needs the OpenCascade CAD kernel + the `libgl1`
/`libglu1`/`libxrender1`/… system libs, which are not present. The real STEP/STL/GLB export is
therefore left to the **GitHub Actions build on push to `main`** (`deploy.yml`), which is the only
place the solid model is validated in this setup.

## The data interface — `site.yaml`

The one source of truth. Metric (`units: mm|cm|m`, normalised to mm internally). Coordinates:
`x` = left→right, `y` = front→back, `z` = up. Sections: `pergola` (footprint, post grid, beams,
rafters, roof, clear_height), `surroundings.walls` / `surroundings.buildings` / `surroundings.beds`
(all placed by `at` corner + `size` (+ `height`)) and `surroundings.paths` (sloping ramps: `at` +
`size` + `rise` + `high_end`), `ground`. `model.py` validates it and raises `ConfigError` with
specific, friendly messages — keep that style for new fields.

The house wall the pergola stands in front of (`surroundings.walls` → `Hauswand`) is the **board wall
of a Blockbohlen (log-cabin) garden house** — the boards are **3 cm (30 mm) thick**, which is the
modelled wall thickness (`size` y). The pergola is pulled **29.5 cm off this wall** so its house-side
roof edge lands at the bracket carrying the garden-house's upper grey fascia board (it does not tuck
under the eave; the lower board is removed, which is what frees the +10 cm of height). The wall is
only drawn as far as the pergola needs it: it ends
**5 cm past the pergola** on the right, but runs long on the left (the steep-path side) where the
beds and ramp sit against it.

Notable `pergola` options: `posts.house_offset` (attached layout — front posts on the footprint
corners, house-side posts pulled this far off the wall while the roof still spans to it);
`posts.rows_y_from_wall` (a list of post-row centre distances from the house wall, one per
`count_y`; places BOTH rows explicitly so the roof can overhang the post ring on the front *and*
house sides — takes precedence over `house_offset`);
`posts.size` (a single number for a square post, or `[x, y]` for a rectangular section);
`posts.anchor` (galvanised steel post base / U-Stützenfuß under every post — see "Pfosten-
Verankerung" below; lifts the post `air_gap` clear of the concrete and adds an `anchor` element);
`framing` (`stacked`, the default — rafters sit on top of the beams; or `flush` — a one-level
roof: `build.py` builds a full perimeter beam ring on all four sides and houses the rafters
flush *between* the front/back beams, tops aligned, so the roof covering rests on a single plane);
`roof.tilt_deg` (mono-pitch, sloping down toward the front, `clear_height` held on the house side);
`roof.gutter` (rain gutter along the low front eave);
`curtains` (optional fabric curtains hung on curtain rods strung between the corner posts — pick
`sides` from `left`/`right`/`front`/`back`; each side adds a horizontal `rod` box between that
side's two corner posts plus a hanging `curtain` fabric panel, drawn semi-transparent like glass);
`braces` (optional diagonal knee braces / Kopfbänder that triangulate the post heads for lateral
stiffness — the bare post-beam frame is pin-jointed and would otherwise rack; each outer corner
post gets a 45° strut up to the beam underside per requested `directions` entry: `x` braces sit in
x-z planes (resist sway parallel to the wall), `y` braces in y-z planes (resist sway toward/away
from the wall); `size` is the square section, `length` the 45° leg — built as `brace` `Prism`s).

## Layout

```
generate.py        CLI entry (config -> all views -> report)
pergola/
  model.py         YAML -> validated dataclasses (mm)
  build.py         parameters -> individual box elements
  geometry.py      Box + Prism primitives, convex-hull / projection / bounds helpers
  views2d.py       plan + elevations, dimension lines, scale bar, North arrow
  joinery.py       timber-joint detail drawings (flush only): cross-lap (Kämmung) where a
                   rafter crosses a beam, corner half-lap (Eck-Überblattung), and a locator plan
  view3d.py        isometric render (hand-rolled axonometric, see below)
  solid.py         box model -> build123d B-rep solids -> STEP / STL / GLB export
  materials.py     box model -> grouped bill of materials (Materialliste) for the HTML
  report.py        bundle into PNG + PDF + HTML (HTML embeds the GLB via <model-viewer>)
  style.py         colours, line weights, dimension styling
```

## Conventions

- Headless matplotlib only (Agg backend; set in the Dockerfile). No interactive/GUI code.
- Surroundings (walls/buildings) are drawn semi-transparent ("ghosted") in elevations and 3D so
  they never hide the pergola. Preserve this when touching those views.
- Keep everything pure-Python and pip-installable. The one CAD kernel in use is **build123d**
  (OpenCascade under the hood), confined to `solid.py` for the 3D-model export; it needs the
  `libgl1`/`libglu1-mesa`/`libxrender1`/`libxext6`/`libsm6` system libs (installed in the
  Dockerfile) even when fully headless. Do NOT let build123d leak into the drawing code — the 2D
  views and the isometric drawing stay pure matplotlib/numpy off the box model.
- In `solid.py`: an axis-aligned `Box` becomes a `build123d.Box` placed by its min corner; a
  `Prism` is built by sewing its six `faces_3d()` quads into a shell (dropping any zero-area face),
  which handles both tilted slabs and the degenerate ramp wedge — lofting does not.
- Most elements are axis-aligned `Box`es. Tilted members (pitched-roof rafters/glass, sloping
  paths) are `Prism`s — general 8-corner hexahedra. Both expose the same interface
  (`corners`/`faces_3d`/`poly_2d`/`min`/`max`/`center`); views project the corners and draw the
  convex-hull silhouette, so they handle either uniformly. Add new tilted geometry as a `Prism`.

## Roof types

`roof.kind` supports `glass` (one translucent pane, `roof.thickness`), `louvered`/`slatted`
(slats laid out by `roof.spacing`/`direction`), and `open` (no roof). `glass` is the model's
stand-in for any rigid translucent panel — real glass, or a polycarbonate / acrylic twin-wall
(Hohlkammer) sheet; pick `roof.thickness` to match (e.g. 16 for a 16 mm twin-wall sheet) and note
the real material in a `site.yaml` comment. Glass is rendered translucent everywhere
(`style.ALPHA`); the sample uses it. `roof.tilt_deg` gives a mono-pitch:
members spanning the slope direction (rafters/glass with `direction: y`) become tilted `Prism`s,
while cross-members stay stepped boxes. `roof.gutter` adds a box gutter at the low front eave.
`roof.material` names the cover for the Materialliste (e.g. `PVC`). `roof.panel_width` panelises a
`glass` cover into equal panels ~that wide across x (e.g. 800 → 3 × 800 mm on a 2400 wide roof):
the rafters are then placed UNDER each interior joint (so a joint never floats between supports) and
each joint gets a connecting H-Profil (`roof.join_profile.width`/`material`, a new `profile`
element). Panels and profiles carry a per-box `material` (on `Box`/`Prism`) that overrides the
category default in `materials.py`. Omit `panel_width` for one continuous pane (old behaviour).

## Pfosten-Verankerung (post anchoring)

How the posts tie to the ground (`posts.anchor` → an `anchor` element per post, category styled steel
grey, counted in the Materialliste as **Stück** via the new `count` metric).

- **Principle.** Never set timber directly in/on concrete — the end grain wicks water and rots, and
  the foot must also resist wind **uplift**, not just compression. So every post stands on a
  galvanised steel base with an **air gap** (capillary break) and bolted/screwed fixing. Lateral
  stiffness comes from the `braces`; the feet carry vertical load + uplift.
- **Chosen part.** A **71 mm Alberts U-Stützenfuß to embed in concrete** (ribbed rod ~16 mm/200 mm,
  CE ETA-10/0210; Brico Art. 5340037). Cheaper than an adjustable foot and adequate for this light,
  braced pergola (an H-anchor is more robust — broad blade vs a single rod — but was not needed).
- **80 × 60 post is a non-standard section.** Mill a ~4.5 mm rebate into two opposite faces so that
  dimension goes **80 → 71**; the standard 71 U then fits snug and **flush** (overall 80 preserved),
  and the 60 mm wings cover the 60 mm face exactly. Keep the rebate **open at the bottom** (drainage)
  and treat the cut wood. This U is plain (no step) → a **spacer (washers/EPDM) under the end grain**
  gives the ventilation gap; the U is open front/back so water drains sideways (no drain hole).
- **Post orientation.** All posts are turned **80 mm front-back** (y, away from the house), **60 mm
  along the wall** (`posts.size: [60, 80]`), so the U-anchor bolts run front-back and stay reachable
  (on the house-side corner the wall blocks one side). Consequence: the front/back beams (80 mm in y)
  now sit flush on the 80 mm post depth, while the side beams overhang the 60 mm post width by ~10 mm
  each side — unavoidable with a rectangular post; orientation is driven by bolt access, not flushness.
- **Modelling.** `build._post_anchor` emits **one** steel collar per post from the concrete top up
  by `air_gap + wing_height` (the lower `air_gap` is the clear gap; the rest wraps the post like the
  wings); the post is raised by `air_gap`. The cast-in rod + its concrete live in the `footing`/house
  support and are **not** redrawn. The collar runs the gap across the post's **wider (milled) face**,
  so it follows whichever way the post is turned (here y).
- **Site facts (build, not dimensioned in the model).** Ground = 3 cm terrace slabs on a chipping
  bed. *Front row:* pour each footing **monolithic up to slab level** (pier ≥ ~15 cm for rod cover),
  cut slabs around with a 5–10 mm gap. *House side:* the pergola now stands **29.5 cm off the wall**
  (no `house_step` any more), so this row is founded **in the ground like the front row** — its post
  centre sits ~33.5 cm out from the wall, roughly in the existing **8 cm gravel drainage strip** behind
  the **6 cm curb**, with the garden-house **concrete foundation** beyond. Pour each footing monolithic
  up to slab level; excavate the gravel ~**20 cm** and bond the new concrete to the curb and the
  garden-house foundation, keeping the drainage.

## The 3D view

`view3d.py` does NOT use mplot3d. It is a hand-rolled axonometric projection onto a 2D axes
(back-face culling + far→near painter ordering) because mplot3d mis-sorts many parts and
produces occlusion artefacts. Footings are excluded from 3D (they are underground and the
ground is a single flat plane). Keep this approach if editing the 3D view.

## Known future extensions (not yet built)

Gable / multi-pitch roofs (only mono-pitch `tilt_deg` exists); back & left elevations (currently
front + right side); 2D DXF export (`ezdxf` is already installed as a build123d dependency, so a
dimensioned DXF sheet is now low-effort if a builder wants editable 2D CAD).
