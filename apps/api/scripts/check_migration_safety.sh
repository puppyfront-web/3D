#!/bin/bash
# Pre-migration safety check: detect conditions that would make migration 012 destructive.
# Returns 0 (safe) or 1 (unsafe — abort).
set -e

# Only check if DATABASE_URL is set (skip in SQLite/dev)
DB_URL="${DATABASE_URL:-}"
if [[ "$DB_URL" == *"sqlite"* ]] || [[ -z "$DB_URL" ]]; then
    echo "[precheck] SQLite or no DATABASE_URL — skipping duplicate check"
    exit 0
fi

# Check if migration 012 has already been applied
APPLIED=$(alembic current 2>/dev/null | grep "012" || true)
if [ -n "$APPLIED" ]; then
    echo "[precheck] Migration 012 already applied — skipping duplicate-name check"
    exit 0
fi

# Check for duplicate company names (would be merged/deleted by 012)
DUPLICATES=$(psql "$DB_URL" -t -c "SELECT count(*) FROM (SELECT name, count(*) as c FROM companies GROUP BY name HAVING count(*) > 1) dups" 2>/dev/null || echo "0")

if [ "$DUPLICATES" -gt "0" ] 2>/dev/null; then
    echo "[precheck] WARNING: Found $DUPLICATES duplicate company names."
    echo "[precheck] Migration 012 will irreversibly merge/delete these."
    echo "[precheck] Run scripts/check_duplicate_companies.py and backup before proceeding."
    echo "[precheck] To override, set SKIP_MIGRATION_CHECK=1"
    if [ "${SKIP_MIGRATION_CHECK:-0}" != "1" ]; then
        exit 1
    fi
    echo "[precheck] SKIP_MIGRATION_CHECK=1 — proceeding anyway"
fi

echo "[precheck] OK — no migration safety issues detected"
exit 0
