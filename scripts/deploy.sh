#!/usr/bin/env bash
# deploy.sh — idempotent production deploy script.
#
# Ordered sequence (must be preserved):
#   1. git pull (latest source)
#   2. docker compose pull bot (fresh GHCR image)
#   3. Build SPA via throwaway node:20-alpine container into frontend/dist/
#   4. docker compose build web (rebuild web image from source)
#   5. docker compose --profile bot up -d bot  (bot starts + runs alembic upgrade head)
#   6. Wait for bot to become healthy (migrations committed before web starts)
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
# 5. Start (or recreate) the bot container
#    The bot entrypoint runs `alembic upgrade head` before the bot process
#    starts, so migrations are committed before web starts.
# ---------------------------------------------------------------------------
log "Starting bot container (runs migrations on startup)..."
docker compose --profile bot up -d bot

# ---------------------------------------------------------------------------
# 6. Wait for the bot container to become healthy
#    `docker inspect` returns the health status; we poll until it is "healthy"
#    or until the timeout (120 s) expires.
# ---------------------------------------------------------------------------
log "Waiting for bot to become healthy (up to 120 s)..."
TIMEOUT=120
ELAPSED=0
INTERVAL=5
while true; do
  STATUS=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$(docker compose --profile bot ps -q bot)" 2>/dev/null || echo "not-running")
  if [ "$STATUS" = "healthy" ]; then
    log "Bot is ready (status: $STATUS)."
    break
  fi
  if [ "$STATUS" = "no-healthcheck" ]; then
    log "ERROR: bot container has no healthcheck configured — cannot verify migration ordering."
    exit 1
  fi
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    log "ERROR: bot did not become healthy within ${TIMEOUT}s (last status: $STATUS)."
    exit 1
  fi
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

# Give the bot one extra second after the health check to finish logging
# the migration completion message (cosmetic — not a correctness requirement).
sleep 1

# ---------------------------------------------------------------------------
# 7. Start (or recreate) web + nginx with the fresh dist/ and image
# ---------------------------------------------------------------------------
log "Starting web + nginx..."
docker compose --profile web up -d

log "Deploy complete."
