"""Derive a bill of materials (Materialliste) from the box model.

Every pergola member is a :class:`Box` or :class:`Prism`; both expose their 8
corners in the same order (bottom face 0..3 as (x0,y0)(x1,y0)(x1,y1)(x0,y1),
then the top face 4..7). The three box edges therefore run from corner 0 to
corners 1, 3 and 4, so their lengths are the member's three real dimensions —
including the TRUE sloped length of a tilted rafter/glass slab and the 45°
length of a knee brace, not just an axis-aligned bounding extent.

Members are grouped by (kind, cross-section, length) and counted, so the HTML
report can show "wie viele Balken, welche Längen, Breiten" at a glance. Only
pergola material is listed; the surroundings (Hauswand, Beete, Pfad) describe
the existing site, not material to buy, so they are skipped.
"""
from __future__ import annotations

from typing import List

import numpy as np

# category -> (German Bauteil name, material, metric kind).
#   metric "length" -> running length in metres (Holz, Blech, Metall)
#   metric "volume" -> concrete volume in m³ (Beton)
#   metric "area"   -> sheet/fabric area in m² (Platte, Stoff)
# Surrounding categories (wall/building/bed/path) are deliberately absent: they
# are the existing site, not pergola material.
_MATERIAL = {
    "post":    ("Pfosten", "Holz", "length"),
    "beam":    ("Balken (Pfette / Randbalken)", "Holz", "length"),
    "rafter":  ("Sparren", "Holz", "length"),
    "slat":    ("Dachlamelle", "Holz", "length"),
    "brace":   ("Kopfband / Eckstrebe", "Holz", "length"),
    "footing": ("Fundament", "Beton", "volume"),
    "step":    ("Fundamentstufe", "Beton", "volume"),
    "glass":   ("Dachplatte", "Glas / PVC-Platte", "area"),
    "profile": ("Verbindungsprofil (H-Profil)", "Aluminium", "length"),
    "gutter":  ("Dachrinne", "Blech / Zink", "length"),
    "rod":     ("Gardinenstange", "Metall / Holz", "length"),
    "curtain": ("Gardine", "Stoff", "area"),
}

# Display order of the rows.
_ORDER = ["footing", "step", "post", "beam", "rafter", "slat",
          "glass", "profile", "gutter", "brace", "rod", "curtain"]

# Unit label per metric kind.
_UNIT = {"length": "lfm (m)", "volume": "m³", "area": "m²"}


def _dims_mm(el) -> List[float]:
    """The element's three real edge lengths (mm), ascending."""
    c = el.corners()
    edges = (c[1] - c[0], c[3] - c[0], c[4] - c[0])
    return sorted(float(np.linalg.norm(e)) for e in edges)


def _metric_value(kind: str, d0: float, d1: float, d2: float) -> float:
    """Per-piece summary value for one member, in metric units (m / m² / m³)."""
    if kind == "length":
        return d2 / 1000.0                      # longest edge = the run length
    if kind == "area":
        return d1 * d2 / 1.0e6                  # two larger edges = the panel face
    return d0 * d1 * d2 / 1.0e9                 # volume


def summarize(elements) -> dict:
    """Return a bill of materials for the pergola members in ``elements``.

    Result: ``{"rows": [...], "totals": [...]}`` where each row is a grouped
    member type (Bauteil, Material, Abmessungen, Anzahl, Menge+Einheit) and
    totals aggregate the running length / area / volume per material kind."""
    # group key -> [qty, label, material, kind, d0, d1, d2]
    groups: dict = {}
    for el in elements:
        info = _MATERIAL.get(el.category)
        if info is None:
            continue                            # surroundings etc.: not material
        label, material, kind = info
        material = getattr(el, "material", "") or material   # per-box override wins
        d0, d1, d2 = (round(d) for d in _dims_mm(el))
        key = (el.category, material, d0, d1, d2)
        if key in groups:
            groups[key][0] += 1
        else:
            groups[key] = [1, label, material, kind, d0, d1, d2]

    rows = []
    totals: dict = {}                           # metric kind -> [value, unit]
    # Sort by display order (by category), then longest member first.
    for key in sorted(groups, key=lambda k: (_ORDER.index(k[0]), -k[4])):
        category, _material, _d0, _d1, _d2 = key
        qty, label, material, kind, d0, d1, d2 = groups[key]
        per = _metric_value(kind, d0, d1, d2)
        total = per * qty
        rows.append({
            "label": label,
            "material": material,
            "dims": f"{d0:g} × {d1:g} × {d2:g}",   # ascending: section/thickness .. length
            "qty": qty,
            "amount": round(total, 2),
            "unit": "m" if kind == "length" else _UNIT[kind],
        })
        bucket = totals.setdefault(kind, [0.0, _UNIT[kind]])
        bucket[0] += total

    total_rows = [{
        "material": {"length": "Holz / Metall / Blech", "volume": "Beton",
                     "area": "Platten / Stoff"}[kind],
        "amount": round(val, 2),
        "unit": unit,
    } for kind, (val, unit) in sorted(totals.items())]

    return {"rows": rows, "totals": total_rows}
