# syntax=docker/dockerfile:1
# Multi-stage build: base → dev (watches) / prod (slim run)
ARG PYTHON_VERSION=3.11

# ── base ──────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

WORKDIR /app

# System deps needed by asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install runtime deps only (no dev extras)
RUN pip install --no-cache-dir -e .

COPY . .

# ── dev ───────────────────────────────────────────────────────────────────────
FROM base AS dev

# Install dev extras (watchfiles, pytest, ruff, etc.)
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "watchfiles", "python -m bot", "."]

# ── prod ──────────────────────────────────────────────────────────────────────
FROM base AS prod

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
