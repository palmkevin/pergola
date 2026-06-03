# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A parametric generator that turns a single description of a garden **pergola** and its
surroundings into architect-style drawings: dimensioned **2D plan + elevations** and a
**simple isometric 3D**, output as **PNG + PDF + HTML**. The end user has no CAD software,
so deliverables are shareable images only — never produce files that need a CAD app to open.

## Core design principle

**Model everything once as 3D boxes, then derive every view from that single model.**
`build.py` expands the YAML parameters into individual boxes (each post, beam, rafter, slat,
footing, wall, building). Every 2D view is just an orthographic projection of those boxes, and
the 3D view uses the same boxes — so all views stay dimensionally consistent. When adding a
feature, add it to the box model first; the views follow.

## How to run

```bash
./run.sh                # build image (first time) + generate from site.yaml
./run.sh other.yaml     # use a different config
```

Runs inside a `python:3.12-slim` Docker container (the host Python is 3.9; do not rely on it).
`run.sh` maps the caller's uid so `output/` files are not root-owned. Outputs:
`output/{plan,elev_front,elev_side,iso3d}.png`, `output/plan.pdf`, `output/index.html`.

Always **rebuild the image after editing `requirements.txt` or the `Dockerfile`**
(`docker build -t pergola-plan .`); code changes need no rebuild (the project is mounted).

## Verifying changes

There are no unit tests — verification is visual. After a change, run `./run.sh` and **read the
generated PNGs** (plan, elevations, 3D) to confirm geometry, dimensions, and labels are correct.

## The data interface — `site.yaml`

The one source of truth. Metric (`units: mm|cm|m`, normalised to mm internally). Coordinates:
`x` = left→right, `y` = front→back, `z` = up. Sections: `pergola` (footprint, post grid, beams,
rafters, roof slats, clear_height), `surroundings.walls` / `surroundings.buildings` (placed by
`at` corner + `size`), `ground`. `model.py` validates it and raises `ConfigError` with specific,
friendly messages — keep that style for new fields.

## Layout

```
generate.py        CLI entry (config -> all views -> report)
pergola/
  model.py         YAML -> validated dataclasses (mm)
  build.py         parameters -> individual box elements
  geometry.py      Box primitive + projection / bounds helpers
  views2d.py       plan + elevations, dimension lines, scale bar, North arrow
  view3d.py        isometric render (mplot3d)
  report.py        bundle into PNG + PDF + HTML
  style.py         colours, line weights, dimension styling
```

## Conventions

- Headless matplotlib only (Agg backend; set in the Dockerfile). No interactive/GUI code.
- Surroundings (walls/buildings) are drawn semi-transparent ("ghosted") in elevations and 3D so
  they never hide the pergola. Preserve this when touching those views.
- Keep everything pure-Python and pip-installable; do not introduce heavy CAD kernels
  (build123d/CadQuery/OpenSCAD) — the geometry is just orthogonal boxes.

## Known future extensions (not yet built)

Roof pitch/tilt and gable roofs; back & left elevations (currently front + right side); DXF
export via `ezdxf` if a builder ever needs an editable CAD file.
