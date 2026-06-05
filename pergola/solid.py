"""Turn the shared box model into a real CAD solid model.

This is the second backend off the single source of truth: where ``views2d``
and ``view3d`` *draw* the :class:`~pergola.geometry.Box`/:class:`Prism`
elements, this module turns the very same element list into watertight B-rep
solids (via build123d / OpenCascade) and exports them as portable 3D files:

  * ``model.step`` — true parametric CAD solids (ISO 10303). The format to
    hand to a fabricator / open in any CAD package (FreeCAD, Fusion, SolidWorks).
  * ``model.stl``  — triangulated mesh, for quick 3D viewing / 3D printing.
  * ``model.glb``  — binary glTF, for rotating / photorealistic rendering
    (Blender, three.js, the macOS/Windows 3D viewers, <model-viewer>).

Each member keeps its category colour (shared with the drawings) and a label,
so the assembly opens as a coloured, named part tree rather than a grey blob.
Footings are included here (unlike the 3D *drawing*) because a real model may
as well carry them; the caller can filter if undesired.
"""
from __future__ import annotations

import os
from typing import List

from build123d import (
    Align,
    Box as B3dBox,
    Color,
    Compound,
    Face,
    Pos,
    Shell,
    Solid,
    Vector,
    Wire,
    export_step,
    export_stl,
)

try:  # glTF export is optional (newer build123d); degrade gracefully if absent.
    from build123d import export_gltf
except ImportError:  # pragma: no cover - depends on build123d version
    export_gltf = None

from .geometry import Box, Prism
from . import style


def _hex_to_rgb(hexstr: str):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _color_for(category: str) -> Color:
    face = style.style_for(category)["face"]
    r, g, b = _hex_to_rgb(face)
    alpha = style.ALPHA.get(category, 1.0)
    return Color(r, g, b, alpha)


def _solid_from_box(box: Box) -> Solid:
    """An axis-aligned box, placed by its minimum corner."""
    dx, dy, dz = (float(s) for s in box.size)
    part = B3dBox(dx, dy, dz, align=(Align.MIN, Align.MIN, Align.MIN))
    part = Pos(*(float(c) for c in box.min)) * part
    return part.solid()


def _solid_from_prism(prism: Prism) -> Solid:
    """A general 8-corner hexahedron (tilted slab, sloped pane, ramp wedge).

    Built by sewing the element's own six quad faces into a shell. Faces that
    collapse to zero area — the low edge of a ramp wedge, where two corners
    coincide — are dropped, leaving a watertight 5-face shell. (Lofting the
    bottom quad to the top quad works for tilted slabs but fails on that
    degenerate wedge, so face-sewing is used uniformly.)
    """
    faces = []
    for quad in prism.faces_3d():
        wire = Wire.make_polygon([Vector(*p) for p in quad], close=True)
        face = Face(wire)
        if face.area > 1e-6:
            faces.append(face)
    return Solid(Shell(faces))


def _to_solid(element):
    if isinstance(element, Box):
        return _solid_from_box(element)
    if isinstance(element, Prism):
        return _solid_from_prism(element)
    raise TypeError(f"don't know how to turn {type(element).__name__} into a solid")


def build_assembly(elements: List, *, include_footings: bool = True) -> Compound:
    """Assemble all elements into one coloured, labelled :class:`Compound`."""
    parts = []
    counters: dict = {}
    for el in elements:
        if not include_footings and el.category == "footing":
            continue
        solid = _to_solid(el)
        solid.color = _color_for(el.category)
        n = counters.get(el.category, 0) + 1
        counters[el.category] = n
        solid.label = el.label or f"{el.category}_{n}"
        parts.append(solid)
    asm = Compound(children=parts)
    asm.label = "pergola"
    return asm


def export_model(elements: List, outdir: str, *, include_footings: bool = True) -> dict:
    """Write STEP + STL + (if available) glTF of the assembly. Returns paths."""
    os.makedirs(outdir, exist_ok=True)
    asm = build_assembly(elements, include_footings=include_footings)

    paths = {}
    step_path = os.path.join(outdir, "model.step")
    export_step(asm, step_path)
    paths["step"] = step_path

    stl_path = os.path.join(outdir, "model.stl")
    export_stl(asm, stl_path)
    paths["stl"] = stl_path

    if export_gltf is not None:
        glb_path = os.path.join(outdir, "model.glb")
        export_gltf(asm, glb_path, binary=True)
        paths["glb"] = glb_path

    return paths
