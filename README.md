# Pergola architect-plan workspace

Describe your garden pergola and its surroundings in one YAML file, and generate
dimensioned **2D plans + elevations** and a **simple isometric 3D** view — as
**PNG**, a combined **PDF**, and a shareable **HTML** page. No CAD software needed.

## How it works

```
site.yaml  ──▶  model (parse+validate)  ──▶  build (3D boxes)  ──▶  views (project)  ──▶  output/
```

Everything is modelled once as 3D boxes (posts, beams, rafters, slats, footings,
walls, buildings); every 2D view is an orthographic projection of that single
model, so all dimensions stay consistent, and the 3D view is essentially free.

## Cloud workflow (GitHub) — the normal way

This project runs entirely in the cloud; no local install needed.

1. **Edit** — change the model through Claude Code on the web (claude.ai/code) connected
   to this repo, or edit [site.yaml](site.yaml) directly in the GitHub web UI / a PR.
2. **Push to `main`** — GitHub Actions (`.github/workflows/deploy.yml`) builds the same
   `python:3.12-slim` image, runs `generate.py`, and publishes `output/` to GitHub Pages.
   You can also trigger a build manually from the **Actions** tab ("Run workflow").
3. **View** — the latest plans + interactive 3D model are served at
   **https://palmkevin.github.io/pergola/** (Pages serves over HTTPS, so the embedded
   `model.glb` viewer loads correctly).

Generated files live in `output/`:

| file | what |
|------|------|
| `output/index.html` | all views on one page + interactive 3D viewer |
| `output/plan.pdf`   | every view, one per page (print/email) |
| `output/plan.png`, `elev_front.png`, `elev_side.png`, `iso3d.png` | individual images |
| `output/model.step`, `model.stl`, `model.glb` | CAD solid / 3D-print mesh / interactive 3D |

`output/` is gitignored — Pages gets it from the build artifact, not from commits.

## Run it locally (optional / offline)

You need Docker (or podman). From this folder:

```bash
./run.sh                # uses site.yaml
./run.sh other.yaml     # use a different config
```

First run builds the image; later runs reuse it. `run.sh` then serves `output/` at
**http://localhost:8000/** (the local stand-in for the Pages URL above).

### Without Docker

The dependencies also work on the host's Python 3.9+:

```bash
pip install -r requirements.txt
python generate.py site.yaml
```

## Editing the model

Open [site.yaml](site.yaml) and change the numbers — or just tell Claude Code the
measurements and it will edit the file for you. Key sections:

- `pergola` — footprint, post grid, beams, rafters, clear height, and `roof.kind`
  (`glass`, `louvered`, `slatted`, or `open`).
- `surroundings.walls` / `surroundings.buildings` — context placed by `at` (corner)
  and `size`, in the same coordinate system.
- `ground` — the drawn ground area.

Coordinates: `x` = left→right, `y` = front→back, `z` = up. All values in `units`
(`mm`, `cm`, or `m`). The sample values are placeholders — replace with your real
measurements.

## Layout

```
generate.py            CLI entry point
pergola/
  model.py             YAML -> validated dataclasses (normalised to mm)
  build.py             expand parameters into every individual member (box)
  geometry.py          Box primitive + projection/bounds helpers
  views2d.py           plan + elevations, with dimension lines
  view3d.py            isometric 3D render
  report.py            bundle into PNG + PDF + HTML
  style.py             colours, line weights, dimension styling
```

## Possible future extensions

- **DXF export** (editable CAD file) via `ezdxf`, if a builder/architect wants one.
- **Roof pitch / tilt**, gable roofs, diagonal bracing.
- **Back / left elevations** (currently front + right side are generated).
