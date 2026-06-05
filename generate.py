#!/usr/bin/env python3
"""Generate all pergola plan views from a site YAML file.

Usage:
    python generate.py [site.yaml] [--out output]
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib.pyplot as plt

from pergola.build import build_elements
from pergola.model import ConfigError, load_config
from pergola import views2d, view3d, report, solid


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate pergola plan views.")
    parser.add_argument("config", nargs="?", default="site.yaml", help="path to site YAML")
    parser.add_argument("--out", default="output", help="output directory")
    args = parser.parse_args(argv)

    if not os.path.exists(args.config):
        print(f"error: config file not found: {args.config}", file=sys.stderr)
        return 2

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"error in {args.config}: {exc}", file=sys.stderr)
        return 1

    elements = build_elements(cfg)
    print(f"Built {len(elements)} elements from {args.config}.")

    views = [
        ("plan",       "Plan (top view)",     views2d.render_plan(elements, cfg)),
        ("elev_front", "Front elevation",     views2d.render_front(elements, cfg)),
        ("elev_side",  "Side elevation",      views2d.render_side(elements, cfg)),
        ("iso3d",      "Isometric 3D",        view3d.render_iso(elements, cfg)),
    ]

    # Real 3D solid model (STEP / STL / glTF) from the same box model.
    model_paths = solid.export_model(elements, args.out)

    paths = report.write_outputs(views, args.out, os.path.basename(args.config),
                                 cfg.units, model_paths)
    for _, _, fig in views:
        plt.close(fig)

    print("Wrote:")
    for p in paths["pngs"]:
        print(f"  {p}")
    print(f"  {paths['pdf']}")
    print(f"  {paths['html']}   <- open this in a browser")
    print("  --- 3D model ---")
    print(f"  {model_paths['step']}   <- editable CAD / hand to a fabricator")
    print(f"  {model_paths['stl']}    <- 3D printing / quick view")
    if "glb" in model_paths:
        print(f"  {model_paths['glb']}    <- rotate / photorealistic render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
