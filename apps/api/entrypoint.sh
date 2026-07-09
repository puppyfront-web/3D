#!/bin/bash
set -e

# ─── Wait for database ───────────────────────────────────────────────
echo "[entrypoint] Waiting for database..."
MAX_WAIT=60
WAITED=0
until pg_isready -h "${DB_HOST:-db}" -p 5432 -U "${POSTGRES_USER:-postgres}" -q 2>/dev/null; do
    WAITED=$((WAITED + 2))
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "[entrypoint] ERROR: Database not ready after ${MAX_WAIT}s"
        exit 1
    fi
    sleep 2
done
echo "[entrypoint] Database is ready."

# ─── Run Alembic migrations ──────────────────────────────────────────
echo "[entrypoint] Running database migrations..."
# Pre-migration safety check (prevents irreversible data loss from migration 012)
bash /app/scripts/check_migration_safety.sh || {
    echo "FATAL: Migration pre-check failed. Fix duplicates or set SKIP_MIGRATION_CHECK=1"
    exit 1
}
alembic upgrade head
echo "[entrypoint] Migrations complete."

# ─── Seed required runtime data (idempotent) ─────────────────────────
echo "[entrypoint] Seeding runtime data if needed..."
python - <<'PY'
import asyncio
from app.db.init_db import seed_if_needed

asyncio.run(seed_if_needed())
PY
echo "[entrypoint] Seed complete."

# ─── Start API server ────────────────────────────────────────────────
WORKERS="${API_WORKERS:-4}"
echo "[entrypoint] Starting uvicorn with ${WORKERS} workers..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WORKERS}" \
    --loop uvloop \
    --http httptools
