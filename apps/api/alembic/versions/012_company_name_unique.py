"""Add a UNIQUE constraint on companies.name (merging existing duplicates).

Closes the create-or-get race in ProjectService._resolve_or_create_company
that produced duplicate Company rows for the same client name, and blocks
the blank-client_name path that created a '' company shared across customers.

Before adding the constraint, existing duplicates are merged: for each name
the MIN(id) survives, its projects and company_profiles are re-pointed, and
the duplicate rows are deleted. companies.name is referenced only by
projects.company_id and company_profiles.company_id (both default RESTRICT),
so both must be cleared before the dup rows can go.

This migration modifies production data irreversibly. Run
``scripts/check_duplicate_companies.py`` first and take a backup
(``scripts/backup.sh``).

Revision ID: 012
Revises: 011
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Snapshot the keeper (MIN id) per duplicated name into a temp table so the
    # subsequent UPDATEs/DELETEs don't GROUP BY rows they're mutating.
    op.execute(
        """
        CREATE TEMP TABLE _company_keep AS
        SELECT name, MIN(id) AS keep_id
        FROM companies
        GROUP BY name
        HAVING COUNT(*) > 1
        """
    )

    # 1. Re-point projects from duplicate companies to their keeper.
    op.execute(
        """
        UPDATE projects p
        SET company_id = k.keep_id
        FROM companies c
        JOIN _company_keep k ON k.name = c.name
        WHERE p.company_id = c.id AND c.id <> k.keep_id
        """
    )

    # 2. company_profiles.company_id is UNIQUE 1:1. The keeper keeps its own
    #    profile; any profile still attached to a duplicate is dropped (its data
    #    was effectively attached to the keeper the workflow used). Re-pointing
    #    onto a keeper that already has one would violate the unique constraint.
    op.execute(
        """
        DELETE FROM company_profiles
        WHERE company_id IN (
            SELECT c.id FROM companies c
            JOIN _company_keep k ON k.name = c.name
            WHERE c.id <> k.keep_id
        )
        """
    )

    # 3. Duplicate companies are no longer referenced — drop them.
    op.execute(
        """
        DELETE FROM companies c
        USING _company_keep k
        WHERE c.name = k.name AND c.id <> k.keep_id
        """
    )

    op.execute("DROP TABLE _company_keep")

    # 4. Names are now unique — enforce it.
    op.create_unique_constraint("uq_companies_name", "companies", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_companies_name", "companies", type_="unique")
