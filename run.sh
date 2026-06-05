#!/usr/bin/env bash
# Build the image (first run / when requirements change) and generate the plan.
#
# Usage:
#   ./run.sh                 # uses site.yaml
#   ./run.sh my-other.yaml   # uses a different config
#
set -euo pipefail

IMAGE="pergola-plan"
CONFIG="${1:-site.yaml}"

# Pick docker or podman, whichever is available.
if command -v docker >/dev/null 2>&1; then
  ENGINE=docker
elif command -v podman >/dev/null 2>&1; then
  ENGINE=podman
else
  echo "Neither docker nor podman found." >&2
  exit 1
fi

cd "$(dirname "$0")"

echo ">> Building image ($ENGINE)…"
"$ENGINE" build -t "$IMAGE" .

echo ">> Generating plan from $CONFIG…"
"$ENGINE" run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  -w /work \
  "$IMAGE" \
  python generate.py "$CONFIG"

# Serve ./output over HTTP so the interactive 3D (model.glb) loads — browsers
# block that fetch under a file:// URL. The server streams the directory live, so
# once it runs it always serves the freshly generated files: the URL below stays
# valid after every ./run.sh, no restart needed.
PORT=8000
if curl -s -o /dev/null "http://localhost:${PORT}/"; then
  echo ">> Viewer already live at http://localhost:${PORT}/"
elif command -v python3 >/dev/null 2>&1; then
  nohup python3 -m http.server "$PORT" --directory "$PWD/output" >/tmp/pergola-server.log 2>&1 &
  disown
  echo ">> Started viewer at http://localhost:${PORT}/"
else
  echo ">> python3 not found on host — open output/index.html via your own web server." >&2
fi

echo ">> Done. View at http://localhost:${PORT}/  (files in ./output/)"
