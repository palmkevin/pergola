"""Drawing style: per-category colours, line weights and dimension styling.

Tuned for a clean, readable architectural look on a white background.
"""
from __future__ import annotations

# facecolor, edgecolor for each element category.
CATEGORY_STYLE = {
    "footing":  {"face": "#d9d2c5", "edge": "#9a8f7a"},
    "post":     {"face": "#b07d52", "edge": "#5c3d23"},
    "beam":     {"face": "#caa06e", "edge": "#5c3d23"},
    "rafter":   {"face": "#dcb887", "edge": "#6b4a2b"},
    "slat":     {"face": "#e8d2ab", "edge": "#7a5a34"},
    "glass":    {"face": "#bfe0ee", "edge": "#6f9fb5"},
    "gutter":   {"face": "#9aa3a8", "edge": "#5d666b"},
    "rod":      {"face": "#6e7377", "edge": "#43484b"},
    "curtain":  {"face": "#e7ddc9", "edge": "#c7bba0"},
    "wall":     {"face": "#cfcfcf", "edge": "#7a7a7a"},
    "building": {"face": "#dde3e8", "edge": "#8a949c"},
    "bed":      {"face": "#9cae6e", "edge": "#5e6b3e"},
    "path":     {"face": "#cfc8ba", "edge": "#9a9182"},
}
DEFAULT_STYLE = {"face": "#cccccc", "edge": "#666666"}

# Per-category opacity (1.0 = solid). Glass is translucent so structure shows
# through; fabric curtains are drawn semi-transparent for the same reason (so a
# near-side curtain never fully hides the pergola in an elevation or the 3D view).
ALPHA = {"glass": 0.40, "curtain": 0.55}

# Painter order within a single view (low drawn first / behind).
CATEGORY_ZORDER = {
    "footing": 0,
    "path": 0,
    "bed": 1,
    "wall": 1,
    "building": 1,
    "post": 2,
    "curtain": 3,
    "rafter": 4,
    "beam": 3,
    "slat": 5,
    "glass": 6,
    "gutter": 6,
    "rod": 7,
}

EDGE_WIDTH = 0.6
GROUND_FACE = "#f1ede3"
GROUND_EDGE = "#cfc7b4"

# Dimension lines.
DIM_COLOR = "#13476b"
DIM_LINEWIDTH = 0.8
DIM_FONTSIZE = 8
DIM_TICK = 60.0          # half-length (mm) of the tick mark across the dim line

TITLE_FONTSIZE = 13
LABEL_FONTSIZE = 8


def style_for(category: str):
    return CATEGORY_STYLE.get(category, DEFAULT_STYLE)


def zorder_for(category: str) -> int:
    return CATEGORY_ZORDER.get(category, 1)
