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

from .geometry import X, Y

# category -> (German Bauteil name, material, metric kind).
#   metric "length" -> running length in metres (Holz, Blech, Metall)
#   metric "volume" -> concrete volume in m³ (Beton)
#   metric "area"   -> sheet/fabric area in m² (Platte, Stoff)
#   metric "count"  -> a counted fitting, reported as Stück (Beschläge)
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
    "anchor":  ("Pfostenanker (U-Stützenfuß)", "Stahl, verzinkt", "count"),
    "glass":   ("Dachplatte", "Glas / PVC-Platte", "area"),
    "profile": ("Verbindungsprofil (H-Profil)", "Aluminium", "length"),
    "edge_profile": ("Randabschlussprofil", "Aluminium", "length"),
    "gutter":  ("Dachrinne", "Blech / Zink", "length"),
    "rod":     ("Gardinenstange", "Metall / Holz", "length"),
    "curtain": ("Gardine", "Stoff", "area"),
}

# Display order of the rows.
_ORDER = ["footing", "step", "anchor", "post", "beam", "rafter", "slat",
          "glass", "profile", "edge_profile", "gutter", "brace", "rod", "curtain"]

# Unit label per metric kind.
_UNIT = {"length": "lfm (m)", "volume": "m³", "area": "m²", "count": "Stück"}


def _dims_mm(el) -> List[float]:
    """The element's three real edge lengths (mm), ascending."""
    c = el.corners()
    edges = (c[1] - c[0], c[3] - c[0], c[4] - c[0])
    return sorted(float(np.linalg.norm(e)) for e in edges)


def _metric_value(kind: str, d0: float, d1: float, d2: float) -> float:
    """Per-piece summary value for one member, in metric units (m / m² / m³ /
    Stück)."""
    if kind == "count":
        return 1.0                              # a counted fitting -> total = qty
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
            "amount": int(round(total)) if kind == "count" else round(total, 2),
            "unit": "m" if kind == "length" else _UNIT[kind],
        })
        bucket = totals.setdefault(kind, [0.0, _UNIT[kind]])
        bucket[0] += total

    total_rows = [{
        "material": {"length": "Holz / Metall / Blech", "volume": "Beton",
                     "area": "Platten / Stoff", "count": "Beschläge"}[kind],
        "amount": int(round(val)) if kind == "count" else round(val, 2),
        "unit": unit,
    } for kind, (val, unit) in sorted(totals.items())]

    return {"rows": rows, "totals": total_rows, "fasteners": fasteners(elements)}


# --------------------------------------------------------------------------- #
#  Verbindungsmittel (Schrauben & Bolzen)
# --------------------------------------------------------------------------- #
# The Materialliste above lists the pieces (timber, panels, anchors …); it does
# NOT list how they are FIXED together. The frame's joints are pure carpentry
# joints (Eck-/Kreuzüberblattung) plus the post bases and knee braces, so the
# only fixings needed are screws/bolts — no angle brackets.
#
# Each joint type below pairs the recommended fixing(s) with the number needed
# per joint; the joint COUNTS are derived from the box model (so the list scales
# with the design). A single joint may need MORE THAN ONE kind of fixing — the
# post base, for instance, takes one through-bolt PLUS side screws — so the spec
# is a LIST of (Schraubentyp · Größe, fixings per joint) pairs.
#
# Post base (anchor): the chosen U-Stützenfuß has three holes per wing, but only
# the MIDDLE pair lines up across the U, so it takes ONE through-bolt there; the
# remaining two holes per wing (4 per post) are fixed with hex-head coach screws
# (Schlüsselschrauben) driven into the post — they don't pass through. The screw
# length (60) stays under the post depth (71–80 mm milled) so it cannot exit the
# far face; pre-drill (Ø10) to avoid splitting.
#
# The through-bolt is a hex-head bolt (Sechskantschraube DIN 931, mit Schaft) —
# preferred over a carriage bolt (Schlossschraube DIN 603) here because the U's
# bolt hole is round, so a carriage bolt's square neck cannot lock and the head
# spins when torquing; a hex head can be counter-held with a spanner. Both bear
# on STEEL (a wing each side), so it needs a washer under BOTH the head and the
# nut (A2, anti-galling + hole cover) — noted inline in the spec; per-bolt that
# is 1 nut + 2 washers (4 nuts + 8 washers over the 4 posts). DIN 603 is an
# equivalent fallback. Nuts/washers are usually NOT in the bolt listing — buy A2
# separately.
#
# Corrosion class: A2 (Edelstahl) for the wet/critical joints — the post base
# (damp ground zone; verzinkt next to A2 there would galvanically sacrifice the
# zinc) and the roof-plane laps (Eck-Überblattung, Kämmung). The knee braces sit
# UNDER the covered roof, so WIROX (zinc-nickel, rated for a covered exterior) is
# used there as the cheaper choice — a deliberate cost trade-off, still well above
# bright zinc, which must NOT be used anywhere outdoors here.
#   (Bauteil/Verbindung, [(Schraubentyp · Größe, fixings per joint), …])
_FASTENERS = {
    "anchor":   ("Pfosten → U-Stützenfuß", [
        ("Sechskantschraube M10 × 90, DIN 931 mit Schaft (Durchgang, mittleres Loch; M10-Mutter + 2 Scheiben unter Kopf & Mutter), Edelstahl A2", 1),
        ("Schlüsselschraube/Sechskant-Holzschraube Ø10 × 60 (in den Pfosten, 2 je Wange; mit Scheibe), Edelstahl A2", 4),
    ]),
    "corner":   ("Eck-Überblattung (Balken × Balken, über Pfosten)", [
        ("Konstruktionsschraube Ø8 × 140, Senkkopf, Torx · Teilgewinde, Edelstahl A2", 2),
    ]),
    "kaemmung": ("Kämmung (Sparren × Balken)", [
        ("Konstruktionsschraube Ø6 × 120, Senkkopf, Torx · Teilgewinde, Edelstahl A2", 2),
    ]),
    "brace":    ("Kopfband (Fuß + Kopf)", [
        ("Konstruktionsschraube Ø8 × 140, Tellerkopf, Torx · Teilgewinde, WIROX (Zink-Nickel, überdacht)", 4),
    ]),
}
# Display order of the fastener rows.
_FASTENER_ORDER = ["anchor", "corner", "kaemmung", "brace"]


def _classify_beams(elements) -> tuple:
    """Count the perimeter-ring beams by run direction: ``(n_cross, n_side)``.

    Cross beams run along x (the front/house Pfetten); side beams run along y
    (the left/right Randbalken). The ring corners — where the carpentry
    Eck-Überblattung sits over a post — number ``n_cross × n_side``."""
    cross = side = 0
    for b in elements:
        if b.category != "beam":
            continue
        poly = np.array(b.poly_2d(X, Y))
        if (poly[:, X].max() - poly[:, X].min()) >= (poly[:, Y].max() - poly[:, Y].min()):
            cross += 1
        else:
            side += 1
    return cross, side


def fasteners(elements) -> dict:
    """Screw/bolt shopping list derived from the box model.

    Counts every structural joint the frame has — post bases (``anchor``), ring
    corners (Eck-Überblattung), rafter×beam crossings (Kämmung) and knee braces
    (``brace``) — and multiplies by the fixings each joint needs. Returns
    ``{"rows": [...], "total": <Gesamtzahl Schrauben/Bolzen>}``; each row carries
    the joint count, fixings-per-joint and the resulting quantity."""
    n_cross, n_side = _classify_beams(elements)
    n_rafter = sum(1 for e in elements if e.category == "rafter")
    joints = {
        "anchor":   sum(1 for e in elements if e.category == "anchor"),
        "corner":   n_cross * n_side,        # two ring beams meet over each corner post
        "kaemmung": n_rafter * n_cross,      # each rafter crosses each front/house beam
        "brace":    sum(1 for e in elements if e.category == "brace"),
    }
    rows = []
    total = 0
    for key in _FASTENER_ORDER:
        nj = joints.get(key, 0)
        if nj <= 0:
            continue
        label, specs = _FASTENERS[key]
        for spec, per in specs:
            qty = nj * per
            total += qty
            rows.append({"label": label, "spec": spec,
                         "joints": nj, "per": per, "qty": qty})
    return {"rows": rows, "total": total}
