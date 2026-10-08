# ARCHITECTURE.md §10's compose pulls ghcr.io/lilkis/api:latest, an image
# nothing in this repo ever built. This builds it from source instead, so
# deploying needs no registry and no CI.

FROM python:3.12-slim AS base

# curl is here for the compose healthcheck, which hits /health.
# libpq is needed by psycopg, which Alembic uses for migrations.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies resolve from pyproject alone, so this layer survives every
# change to app/ and only rebuilds when the dependency list moves.
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && python -c "import tomllib,subprocess,sys; \
deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; \
subprocess.check_call([sys.executable,'-m','pip','install',*deps])"

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Chunked uploads stage here between the /chunk and /complete calls
# (routers/upload.py). Declared as a volume so the two uvicorn workers in
# a container share it and a restart mid-upload doesn't strand the
# chunks — the purge job clears anything abandoned for 24h.
RUN mkdir -p /tmp/lilkis_uploads
VOLUME ["/tmp/lilkis_uploads"]

# Non-root. The app writes only to the upload staging directory.
RUN useradd --create-home --uid 10001 lilkis \
    && chown -R lilkis:lilkis /tmp/lilkis_uploads
USER lilkis

EXPOSE 8000

# Two workers, per ARCHITECTURE.md §10's note: "Do not run more than 2
# uvicorn workers without testing OOM first." They share one filesystem,
# which the chunked upload depends on — scaling this to more than one
# container needs the staging directory moved to shared storage first.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
