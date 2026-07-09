"""Revision service — snapshot and retrieve asset version history."""
import uuid
from datetime import datetime
from typing import Any, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_asset_revision import KnowledgeAssetRevision

# Columns excluded from snapshots — they are bookkeeping fields, not
# meaningful content, and including them would just bloat every revision row.
_EXCLUDED_COLUMNS = {"id", "created_at", "updated_at"}


def build_snapshot(instance: Any) -> dict:
    """Build a JSON-serializable snapshot of a model instance's current state.

    Walks the model's columns (excluding id/created_at/updated_at) and
    serializes UUID / datetime values to strings so the result can be stored
    in a JSON column.
    """
    snapshot = {}
    for column in instance.__table__.columns:
        if column.name in _EXCLUDED_COLUMNS:
            continue
        value = getattr(instance, column.name)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        snapshot[column.name] = value
    return snapshot


async def create_snapshot(
    db: AsyncSession,
    asset_type: str,
    asset_id: uuid.UUID,
    snapshot_data: dict,
    change_summary: str = None,
    created_by: uuid.UUID = None,
) -> KnowledgeAssetRevision:
    """Create a revision snapshot of an asset before/after an update."""
    # Get the next version number
    max_no = await db.execute(
        select(func.max(KnowledgeAssetRevision.version_no)).where(
            KnowledgeAssetRevision.asset_type == asset_type,
            KnowledgeAssetRevision.asset_id == asset_id,
        )
    )
    current_max = max_no.scalar() or 0
    revision = KnowledgeAssetRevision(
        id=uuid.uuid4(),
        asset_type=asset_type,
        asset_id=asset_id,
        version_no=current_max + 1,
        snapshot=snapshot_data,
        change_summary=change_summary,
        created_by=created_by,
    )
    db.add(revision)
    await db.flush()
    return revision

async def list_revisions(
    db: AsyncSession,
    asset_type: str,
    asset_id: uuid.UUID,
) -> List[KnowledgeAssetRevision]:
    """List all revisions for an asset, newest first."""
    result = await db.execute(
        select(KnowledgeAssetRevision)
        .where(
            KnowledgeAssetRevision.asset_type == asset_type,
            KnowledgeAssetRevision.asset_id == asset_id,
        )
        .order_by(KnowledgeAssetRevision.version_no.desc())
    )
    return list(result.scalars().all())

async def get_revision(
    db: AsyncSession,
    revision_id: uuid.UUID,
) -> Optional[KnowledgeAssetRevision]:
    return await db.get(KnowledgeAssetRevision, revision_id)
