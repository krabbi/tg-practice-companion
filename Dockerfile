# syntax=docker/dockerfile:1
# Multi-stage build: frontend-builder / base → dev (watches) / prod (slim run)
ARG PYTHON_VERSION=3.11

# ── frontend-builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

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
