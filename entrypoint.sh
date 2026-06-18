#!/bin/sh
set -e

echo "Running Alembic migrations..."
alembic upgrade head

# Honor an explicit command (e.g. `docker compose run bot python -m cli.seed ...`);
# fall back to launching the bot when no command is given (the default service start).
if [ "$#" -gt 0 ]; then
    echo "Running command: $*"
    exec "$@"
fi

echo "Starting bot..."
exec python -m bot
