"""Bundle the rendered views into shareable deliverables.

Produces, in the output directory:
  * one PNG per view
  * plan.pdf  — every view, one per page (vector, good for printing/emailing)
  * index.html — a single self-contained-ish page embedding the PNGs
"""
from __future__ import annotations

import os
from typing import List, Tuple

from matplotlib.backends.backend_pdf import PdfPages
from jinja2 import Template

_HTML = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pergola plan</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f6f4ef; color: #222; }
  header { padding: 24px 32px; background: #fff; border-bottom: 1px solid #ddd; }
  header h1 { margin: 0 0 4px; font-size: 22px; }
  header p { margin: 0; color: #666; font-size: 14px; }
  main { padding: 24px 32px; display: flex; flex-direction: column; gap: 28px; }
  figure { margin: 0; background: #fff; border: 1px solid #e2ddd2; border-radius: 8px;
           box-shadow: 0 1px 4px rgba(0,0,0,.05); overflow: hidden; }
  figcaption { padding: 10px 16px; font-weight: 600; border-bottom: 1px solid #eee; }
  img { display: block; width: 100%; height: auto; }
  footer { padding: 16px 32px 40px; color: #999; font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>Pergola — architectural plan</h1>
  <p>Generated from <code>{{ config_name }}</code> · all dimensions in {{ units }} ·
     <a href="{{ pdf_name }}">download PDF</a></p>
</header>
<main>
  {% for title, img in views %}
  <figure>
    <figcaption>{{ title }}</figcaption>
    <img src="{{ img }}" alt="{{ title }}">
  </figure>
  {% endfor %}
</main>
<footer>Regenerate any time with <code>./run.sh</code> after editing the YAML.</footer>
</body>
</html>"""
)


def write_outputs(views: List[Tuple[str, str, "Figure"]], outdir: str,
                  config_name: str, units: str) -> dict:
    """``views`` = list of (key, title, figure). Returns paths written."""
    os.makedirs(outdir, exist_ok=True)
    png_entries = []  # (title, filename)
    pdf_path = os.path.join(outdir, "plan.pdf")

    with PdfPages(pdf_path) as pdf:
        for key, title, fig in views:
            png_name = f"{key}.png"
            fig.savefig(os.path.join(outdir, png_name), dpi=fig.get_dpi(),
                        bbox_inches="tight", facecolor="white")
            pdf.savefig(fig, facecolor="white")
            png_entries.append((title, png_name))

    html_path = os.path.join(outdir, "index.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(_HTML.render(views=png_entries, config_name=config_name,
                              units=units, pdf_name="plan.pdf"))

    return {
        "pdf": pdf_path,
        "html": html_path,
        "pngs": [os.path.join(outdir, n) for _, n in png_entries],
    }
