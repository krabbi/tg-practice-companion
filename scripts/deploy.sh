#!/usr/bin/env bash
# deploy.sh — idempotent production deploy script.
#
# Ordered sequence (must be preserved):
#   1. git pull (latest source)
#   2. docker compose pull bot (fresh GHCR image)
#   3. Build SPA via throwaway node:20-alpine container into frontend/dist/
#   4. docker compose build web (rebuild web image from source)
#   5. docker compose --profile bot run --rm bot alembic upgrade head
#      (discrete blocking migration step — exits 0 on success, non-zero aborts script)
#   6. docker compose --profile bot up -d bot  (migrations already applied; entrypoint alembic is now a no-op)
#   7. docker compose --profile web up -d  (web + nginx with fresh dist/)
#
# Secrets / configuration: all in .env on the server. Never committed to git.
#
# Usage (called by the CD workflow via SSH):
#   cd /path/to/tg-practice-companion && bash scripts/deploy.sh
#
# Can also be run manually as the fallback procedure.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

log() { echo "[deploy] $(date -u +%H:%M:%S) $*"; }

# ---------------------------------------------------------------------------
# 1. Update source
# ---------------------------------------------------------------------------
log "Fetching latest source..."
git fetch origin
git checkout main
git pull origin main

# ---------------------------------------------------------------------------
# 2. Pull the freshly published bot image from GHCR
# ---------------------------------------------------------------------------
log "Pulling bot image from GHCR..."
docker compose --profile bot pull bot

# ---------------------------------------------------------------------------
# 3. Build the Vue SPA in a throwaway node:20-alpine container
#    The server has no Node installed; the container writes into frontend/dist/
#    on the host via a bind-mount. A failed build aborts the script (set -e)
#    so we never reach `up -d` with a stale or partial dist.
# ---------------------------------------------------------------------------
log "Building Vue SPA (node:20-alpine container)..."
docker run --rm \
  -v "$REPO_DIR/frontend:/app" \
  -w /app \
  node:20-alpine \
  sh -c "npm ci && npm run build"

log "SPA build complete — frontend/dist/ is up to date."

# ---------------------------------------------------------------------------
# 4. Rebuild the web image from source
# ---------------------------------------------------------------------------
log "Building web image from source..."
docker compose build web

# ---------------------------------------------------------------------------
# 5. Apply database migrations (blocking, discrete step)
#    `docker compose run` honours depends_on — it starts the db service first
#    and waits for its healthcheck (service_healthy) before launching the bot
#    container. The entrypoint always runs `alembic upgrade head` unconditionally,
#    then exec's any passed command. Passing `alembic upgrade head` explicitly means
#    the idempotent re-run exits 0 and the container exits cleanly — a reliable
#    blocking gate. set -e aborts the deploy if migrations fail.
# ---------------------------------------------------------------------------
log "Applying database migrations..."
docker compose --profile bot run --rm bot alembic upgrade head

log "Migrations applied successfully."

# ---------------------------------------------------------------------------
# 6. Start (or recreate) the bot container
#    Migrations are already committed; the entrypoint's own `alembic upgrade head`
#    runs again but is a no-op (alembic detects no pending migrations).
# ---------------------------------------------------------------------------
log "Starting bot container..."
docker compose --profile bot up -d bot

# ---------------------------------------------------------------------------
# 7. Start (or recreate) web + nginx with the fresh dist/ and image
#    Migration ordering is guaranteed by step 5's blocking exit — no wait needed.
# ---------------------------------------------------------------------------
log "Starting web + nginx..."
docker compose --profile web up -d

log "Deploy complete."
