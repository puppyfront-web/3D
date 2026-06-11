"""Dry-run audit for the 012_company_name_unique migration.

Read-only. Prints how many duplicate company names exist, which rows would be
merged/deleted, and the projects/profiles that would be re-pointed — so you can
review before running ``alembic upgrade head`` (which is irreversible; back up
first with ``scripts/backup.sh``).

Run from apps/api::

    python scripts/check_duplicate_companies.py

Exit code: 0 if no duplicates (safe to migrate), 1 if duplicates exist.
"""

import asyncio
import sys
from pathlib import Path

# Allow `python scripts/check_duplicate_companies.py` from apps/api regardless
# of how PYTHONPATH is set.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db.session import async_session_factory  # noqa: E402


async def main() -> int:
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT name, COUNT(*) AS dup_count,
                           array_agg(id ORDER BY id) AS ids
                    FROM companies
                    GROUP BY name
                    HAVING COUNT(*) > 1
                    ORDER BY COUNT(*) DESC
                    """
                )
            )
        ).all()

        if not rows:
            print("No duplicate company names found — safe to run migration 012.")
            return 0

        total_extra = sum(r.dup_count - 1 for r in rows)
        print(
            f"Found {len(rows)} name(s) with duplicates "
            f"({total_extra} extra row(s) to delete):\n"
        )

        for r in rows:
            keeper, *dups = r.ids
            projects = (
                await db.execute(
                    text("SELECT COUNT(*) FROM projects WHERE company_id = ANY(:ids)"),
                    {"ids": dups},
                )
            ).scalar_one()
            profiles = (
                await db.execute(
                    text("SELECT COUNT(*) FROM company_profiles WHERE company_id = ANY(:ids)"),
                    {"ids": dups},
                )
            ).scalar_one()
            print(f"  - {r.name!r}: keeper={keeper}, dups={dups}")
            print(f"      projects to re-point: {projects}, profiles to drop: {profiles}")

        print("\nMigration 012 would merge each group into its keeper (MIN id).")
        print("This is irreversible — run scripts/backup.sh, then `alembic upgrade head`.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
