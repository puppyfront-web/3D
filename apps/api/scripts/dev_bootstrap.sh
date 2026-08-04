#!/bin/bash
set -euo pipefail

echo "[dev-bootstrap] Running Alembic migrations..."
alembic upgrade head

echo "[dev-bootstrap] Seeding runtime data if needed..."
python - <<'PY'
import asyncio
from app.db.init_db import seed_if_needed

asyncio.run(seed_if_needed())
PY

echo "[dev-bootstrap] Done."
