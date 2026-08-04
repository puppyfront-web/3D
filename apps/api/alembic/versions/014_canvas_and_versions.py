"""Canvas workspace + snapshot version model.

Introduces the infinite-canvas data model (technical design §5, PRD §16):
  - project_versions   (snapshot-based version per project)
  - canvases           (1:1 with project_versions)
  - canvas_groups      (the three board sections)
  - canvas_nodes       (leaf nodes carrying AI-filled content)
  - canvas_edges       (node-to-node connections)
  - node_sources       (per-node provenance, materializes SkillResult.used_*)

Also extends two existing tables:
  - projects.current_version_id  (UUID pointer, not a FK — avoids circular FK)
  - skill_executions.agent_role / node_ids
    (lets a SkillExecution double as an AgentRun when the canvas orchestrator
     drives a skill to fill nodes)

Uses sa.Uuid() (SQLAlchemy 2.0 dialect-agnostic UUID) to stay consistent with
migrations 001–013 and keep working on both PostgreSQL and SQLite (dev.db).

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- project_versions -------------------------------------------------
    op.create_table(
        "project_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_name", sa.String(255), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column(
            "based_on_version_id",
            sa.Uuid(),
            sa.ForeignKey("project_versions.id"),
            nullable=True,
        ),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_project_versions_is_current", "project_versions", ["is_current"]
    )

    # --- canvases (1:1 with project_versions) -----------------------------
    op.create_table(
        "canvases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_version_id",
            sa.Uuid(),
            sa.ForeignKey("project_versions.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("viewport", sa.JSON(), nullable=True),
        sa.Column("layout_config", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- canvas_groups ----------------------------------------------------
    op.create_table(
        "canvas_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "canvas_id",
            sa.Uuid(),
            sa.ForeignKey("canvases.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("group_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.JSON(), nullable=True),
        sa.Column("style", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- canvas_nodes -----------------------------------------------------
    op.create_table(
        "canvas_nodes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "canvas_id",
            sa.Uuid(),
            sa.ForeignKey("canvases.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("canvas_groups.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("node_key", sa.String(100), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False, server_default="module_node"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("position", sa.JSON(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- canvas_edges -----------------------------------------------------
    op.create_table(
        "canvas_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "canvas_id",
            sa.Uuid(),
            sa.ForeignKey("canvases.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_node_id",
            sa.Uuid(),
            sa.ForeignKey("canvas_nodes.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_node_id",
            sa.Uuid(),
            sa.ForeignKey("canvas_nodes.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("edge_type", sa.String(50), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- node_sources -----------------------------------------------------
    op.create_table(
        "node_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "node_id",
            sa.Uuid(),
            sa.ForeignKey("canvas_nodes.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_ref_id", sa.String(64), nullable=True),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- extend projects --------------------------------------------------
    op.add_column(
        "projects",
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
    )

    # --- extend skill_executions (AgentRun role) --------------------------
    op.add_column("skill_executions", sa.Column("agent_role", sa.String(50), nullable=True))
    op.add_column("skill_executions", sa.Column("node_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    # skill_executions
    op.drop_column("skill_executions", "node_ids")
    op.drop_column("skill_executions", "agent_role")
    # projects
    op.drop_column("projects", "current_version_id")
    # node_sources
    op.drop_table("node_sources")
    # canvas_edges
    op.drop_table("canvas_edges")
    # canvas_nodes
    op.drop_table("canvas_nodes")
    # canvas_groups
    op.drop_table("canvas_groups")
    # canvases
    op.drop_table("canvases")
    # project_versions
    op.drop_index("ix_project_versions_is_current", table_name="project_versions")
    op.drop_table("project_versions")
