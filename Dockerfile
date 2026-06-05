# Lightweight, reproducible run environment for the pergola plan generator.
# Modern Python frees us from the host's Python 3.9; no system CAD tools needed.
FROM python:3.12-slim

# Headless matplotlib: force the Agg backend (no display required).
ENV MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/mpl \
    XDG_CACHE_HOME=/tmp/.cache \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /work

# build123d's OpenCascade backend (OCP) links against these shared libraries
# even when run fully headless — without them `import OCP` fails on libGL.so.1.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 libglu1-mesa libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*

# Install deps first so the layer caches across code edits.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Project code is mounted at runtime (-v "$PWD":/work), so nothing else to copy.
CMD ["python", "generate.py", "site.yaml"]
