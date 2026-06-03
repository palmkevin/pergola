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

echo ">> Done. See ./output/  (open output/index.html in a browser)"
