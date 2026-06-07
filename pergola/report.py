"""Bundle the rendered views into shareable deliverables.

Produces, in the output directory:
  * one PNG per view
  * plan.pdf  — every view, one per page (vector, good for printing/emailing)
  * index.html — a single self-contained-ish page embedding the PNGs
"""
from __future__ import annotations

import hashlib
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
{% if model_glb %}<script type="module"
  src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>{% endif %}
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
  model-viewer { display: block; width: 100%; height: 480px; background: #f0eee8; }
  .downloads { padding: 12px 16px; border-top: 1px solid #eee; font-size: 13px; }
  .downloads a { margin-right: 18px; }
  .glossary { padding: 16px 20px; }
  .glossary dl { margin: 0; display: grid; grid-template-columns: max-content 1fr;
                 gap: 6px 18px; font-size: 14px; }
  .glossary dt { font-weight: 600; }
  .glossary dt .en { font-weight: 400; color: #888; font-size: 13px; }
  .glossary dd { margin: 0; color: #444; }
  .section-head { padding: 4px 4px 0; }
  .section-head h2 { margin: 18px 0 2px; font-size: 18px; }
  .section-head p { margin: 0 0 4px; color: #666; font-size: 14px; max-width: 60em; }
  figcaption .note { display: block; font-weight: 400; color: #555; font-size: 13px;
                     margin-top: 4px; max-width: 70em; }
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
  {% if model_glb %}
  <figure>
    <figcaption>3D model — drag to rotate, scroll to zoom</figcaption>
    <model-viewer src="{{ model_glb }}" camera-controls auto-rotate
                  shadow-intensity="1" exposure="1.1"
                  alt="Interactive 3D model of the pergola"></model-viewer>
    {% if downloads %}
    <div class="downloads">Download the 3D model:
      {% for label, href in downloads %}<a href="{{ href }}">{{ label }}</a>{% endfor %}
    </div>
    {% endif %}
  </figure>
  {% endif %}
  {% for title, img in views %}
  <figure>
    <figcaption>{{ title }}</figcaption>
    <img src="{{ img }}" alt="{{ title }}">
  </figure>
  {% endfor %}
  {% if details %}
  <div class="section-head">
    <h2>Holzverbindungen / timber joints</h2>
    <p>Die Pläne oben zeigen die Lage der Hölzer; im Modell durchdringen sie sich der
       Einfachheit halber. Hier steht, wie sie an den Stoßstellen <b>ineinandergreifen</b>:
       In der flush-Bauweise fluchten die Oberkanten von Sparren und Ringbalken (eine
       Dachebene), also werden die Hölzer ausgeklinkt statt gestapelt.</p>
  </div>
  {% for title, img, note in details %}
  <figure>
    <figcaption>{{ title }}{% if note %}<span class="note">{{ note }}</span>{% endif %}</figcaption>
    <img src="{{ img }}" alt="{{ title }}">
  </figure>
  {% endfor %}
  {% endif %}
  <figure class="glossary">
    <figcaption>Bauteil-Wortschatz / glossary of parts</figcaption>
    <dl>
      <dt>Pfosten <span class="en">(post)</span></dt>
      <dd>Senkrechte Stütze, die das Dach trägt. Steht hier auf einem Betonfundament.</dd>
      <dt>Fundament <span class="en">(footing)</span></dt>
      <dd>Betonblock im Boden unter jedem Pfosten.</dd>
      <dt>Pfette <span class="en">(purlin)</span></dt>
      <dd>Waagerechter Trägerbalken <b>parallel zur Hauswand</b> (entlang x). Liegt auf den
          Pfosten und trägt die Sparren. Vorne die Trauf­pfette (niedrige Kante), hinten die
          hausseitige Pfette.</dd>
      <dt>Sparren <span class="en">(rafter)</span></dt>
      <dd>Die Balken, die <b>senkrecht zur Hauswand</b> die Dachneigung hinunterlaufen (entlang y).
          Sie liegen zwischen den beiden Pfetten und tragen die Dachplatte.</dd>
      <dt>Längsbalken / Längsstrebe <span class="en">(lengthwise member)</span></dt>
      <dd>Allgemein: ein Balken <b>parallel zur Hauswand</b> (entlang x). Hier sind das die
          beiden Pfetten.</dd>
      <dt>Querbalken / Querstrebe <span class="en">(crosswise member)</span></dt>
      <dd>Allgemein: ein Balken <b>senkrecht zur Hauswand</b> (entlang y). Hier sind das die
          Sparren sowie die beiden seitlichen Randbalken des Rahmens.</dd>
      <dt>Rahmenring <span class="en">(perimeter beam ring)</span></dt>
      <dd>Der umlaufende Balkenrahmen (flush-Bauweise): die zwei Pfetten plus die zwei
          seitlichen Randbalken, die das Dach zu einer Ebene schließen.</dd>
      <dt>Traufe <span class="en">(eave)</span></dt>
      <dd>Die untere, vordere Dachkante, zu der das Dach abfällt; hier mit Regenrinne.</dd>
      <dt>Dachrinne <span class="en">(gutter)</span></dt>
      <dd>Rinne entlang der Traufe, die das Regenwasser sammelt.</dd>
      <dt>Gardinenstange <span class="en">(curtain rod)</span></dt>
      <dd>Waagerechte Stange, zwischen den beiden Eckpfosten einer Seite gespannt
          und an ihnen befestigt; daran hängt die Gardine.</dd>
      <dt>Gardine <span class="en">(curtain)</span></dt>
      <dd>Stoffbahn, die seitlich an der Gardinenstange hängt und für Schatten und
          Sichtschutz sorgt. In den Zeichnungen halbtransparent dargestellt, damit
          die Konstruktion dahinter sichtbar bleibt.</dd>
      <dt>Kämmung / Überblattung <span class="en">(housed / lap joint)</span></dt>
      <dd>Zwei kreuzende Hölzer werden je teilweise ausgeklinkt, sodass sie ineinandergreifen
          und (hier) die Oberkanten bündig fluchten. Sparren × Ringbalken = Kreuzüberblattung.</dd>
      <dt>Eck-Überblattung <span class="en">(corner half-lap)</span></dt>
      <dd>Halbholz-Eckverbindung: zwei gleich hohe Balken werden je auf halber Höhe ausgeklinkt
          und über dem Pfosten ineinandergelegt.</dd>
    </dl>
  </figure>
</main>
<footer>Regenerate any time with <code>./run.sh</code> after editing the YAML.
The STEP file opens in any CAD package; the GLB/STL open in 3D viewers and slicers.</footer>
</body>
</html>"""
)


def _versioned(path: str) -> str:
    """Return ``<basename>?v=<8-hex content hash>`` for cache-busting.

    The deployed asset filenames never change (``model.glb``, ``plan.png`` …)
    and GitHub Pages serves them with ``Cache-Control: max-age``, so a browser
    (and especially ``<model-viewer>``, which fetches the GLB and caches it by
    URL) keeps serving the stale bytes after a redeploy — the 3D model appears
    "not updated" even though Pages has the new file. Appending a hash of the
    file's contents makes the URL change exactly when the bytes change, forcing
    a refetch only when there's something new to fetch."""
    name = os.path.basename(path)
    with open(path, "rb") as fh:
        digest = hashlib.md5(fh.read()).hexdigest()[:8]
    return f"{name}?v={digest}"


def write_outputs(views: List[Tuple[str, str, "Figure"]], outdir: str,
                  config_name: str, units: str, model_paths: dict | None = None,
                  details: List[Tuple[str, str, "Figure", str]] | None = None) -> dict:
    """``views`` = list of (key, title, figure). ``details`` = optional list of
    (key, title, figure, html_note) timber-joint detail drawings shown in their
    own HTML section and appended to the PDF. ``model_paths`` = optional dict of
    3D-model files ({step, stl, glb}) to embed/link in the HTML. Returns paths."""
    os.makedirs(outdir, exist_ok=True)
    details = details or []
    png_entries = []      # (title, versioned URL)
    png_paths = []        # full paths, for the returned dict
    detail_entries = []   # (title, png_path, note)
    pdf_path = os.path.join(outdir, "plan.pdf")

    with PdfPages(pdf_path) as pdf:
        for key, title, fig in views:
            png_path = os.path.join(outdir, f"{key}.png")
            fig.savefig(png_path, dpi=fig.get_dpi(),
                        bbox_inches="tight", facecolor="white")
            pdf.savefig(fig, facecolor="white")
            png_entries.append((title, png_path))
            png_paths.append(png_path)
        for key, title, fig, note in details:
            png_path = os.path.join(outdir, f"{key}.png")
            fig.savefig(png_path, dpi=fig.get_dpi(),
                        bbox_inches="tight", facecolor="white")
            pdf.savefig(fig, facecolor="white")
            detail_entries.append((title, png_path, note))
            png_paths.append(png_path)

    # Cache-bust every generated asset by content hash so a redeploy is picked
    # up immediately (see _versioned). Done after the files exist on disk.
    png_entries = [(title, _versioned(p)) for title, p in png_entries]
    detail_entries = [(title, _versioned(p), note) for title, p, note in detail_entries]

    model_paths = model_paths or {}
    glb_name = _versioned(model_paths["glb"]) if model_paths.get("glb") else None
    _dl_labels = {"step": "STEP (CAD)", "stl": "STL (print)", "glb": "GLB (3D)"}
    downloads = [(_dl_labels[k], _versioned(model_paths[k]))
                 for k in ("step", "stl", "glb") if model_paths.get(k)]

    html_path = os.path.join(outdir, "index.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(_HTML.render(views=png_entries, details=detail_entries,
                              config_name=config_name,
                              units=units, pdf_name=_versioned(pdf_path),
                              model_glb=glb_name, downloads=downloads))

    return {
        "pdf": pdf_path,
        "html": html_path,
        "pngs": png_paths,
    }
