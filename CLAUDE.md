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

## The data interface — `site.yaml`

The one source of truth. Metric (`units: mm|cm|m`, normalised to mm internally). Coordinates:
`x` = left→right, `y` = front→back, `z` = up. Sections: `pergola` (footprint, post grid, beams,
rafters, roof, clear_height), `surroundings.walls` / `surroundings.buildings` / `surroundings.beds`
(all placed by `at` corner + `size` (+ `height`)) and `surroundings.paths` (sloping ramps: `at` +
`size` + `rise` + `high_end`), `ground`. `model.py` validates it and raises `ConfigError` with
specific, friendly messages — keep that style for new fields.

The house wall the pergola attaches to (`surroundings.walls` → `Hauswand`) is the **board wall
of a Blockbohlen (log-cabin) garden house** — the boards are **3 cm (30 mm) thick**, which is the
modelled wall thickness (`size` y). The wall is only drawn as far as the pergola needs it: it ends
**5 cm past the pergola** on the right, but runs long on the left (the steep-path side) where the
beds and ramp sit against it.

Notable `pergola` options: `posts.house_offset` (attached layout — front posts on the footprint
corners, house-side posts pulled this far off the wall while the roof still spans to it);
`posts.rows_y_from_wall` (a list of post-row centre distances from the house wall, one per
`count_y`; places BOTH rows explicitly so the roof can overhang the post ring on the front *and*
house sides — takes precedence over `house_offset`);
`posts.size` (a single number for a square post, or `[x, y]` for a rectangular section);
`framing` (`stacked`, the default — rafters sit on top of the beams; or `flush` — a one-level
roof: `build.py` builds a full perimeter beam ring on all four sides and houses the rafters
flush *between* the front/back beams, tops aligned, so the roof covering rests on a single plane);
`roof.tilt_deg` (mono-pitch, sloping down toward the front, `clear_height` held on the house side);
`roof.gutter` (rain gutter along the low front eave);
`curtains` (optional fabric curtains hung on curtain rods strung between the corner posts — pick
`sides` from `left`/`right`/`front`/`back`; each side adds a horizontal `rod` box between that
side's two corner posts plus a hanging `curtain` fabric panel, drawn semi-transparent like glass).

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

## The 3D view

`view3d.py` does NOT use mplot3d. It is a hand-rolled axonometric projection onto a 2D axes
(back-face culling + far→near painter ordering) because mplot3d mis-sorts many parts and
produces occlusion artefacts. Footings are excluded from 3D (they are underground and the
ground is a single flat plane). Keep this approach if editing the 3D view.

## Known future extensions (not yet built)

Gable / multi-pitch roofs (only mono-pitch `tilt_deg` exists); back & left elevations (currently
front + right side); 2D DXF export (`ezdxf` is already installed as a build123d dependency, so a
dimensioned DXF sheet is now low-effort if a builder wants editable 2D CAD).
