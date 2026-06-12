"""ConfigExportService — serialize config entities to importable JSON.

The output is a bare JSON array of snake_case dicts (column names minus
auto-managed fields), shaped so it can be fed straight back into the matching
``POST /<menu>/import`` endpoint. Round-trip parity with ImportService is the
core contract: import only accepts snake_case keys and does not strip
id/created_at/updated_at/project_id, so export must omit them.
"""
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.services.import_service import ImportService


# Columns that must never be exported: PK + timestamps (server-managed) and
# project_id on Case (environment-specific, re-injected at import via query param).
_DENY = {"id", "created_at", "updated_at", "project_id"}


def _json_default(obj: Any) -> Any:
    """JSON encoder for ORM values that json.dumps can't handle natively."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ConfigExportService:
    """Export config entities to a re-importable JSON byte payload."""

    @staticmethod
    def _row_to_dict(row: Any) -> dict:
        """Map an ORM row to a {column: value} dict, dropping auto-managed columns."""
        return {
            c.name: getattr(row, c.name)
            for c in row.__table__.columns
            if c.name not in _DENY
        }

    @classmethod
    def _resolve_model(cls, entity_type: str):
        mapping = ImportService.ENTITY_MODELS.get(entity_type)
        if mapping is None:
            raise ValueError(f"未知实体类型: {entity_type}")
        return mapping[0]

    @classmethod
    async def export_many(cls, db: AsyncSession, entity_type: str) -> bytes:
        """Export every row of an entity type as a JSON array."""
        model = cls._resolve_model(entity_type)
        rows = (await db.execute(select(model).order_by(model.created_at.desc()))).scalars().all()
        data = [cls._row_to_dict(r) for r in rows]
        return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")

    @classmethod
    async def export_one(cls, db: AsyncSession, entity_type: str, obj_id: uuid.UUID) -> bytes:
        """Export a single row as a one-element JSON array (re-importable)."""
        model = cls._resolve_model(entity_type)
        row = await db.get(model, obj_id)
        if row is None:
            raise NotFoundException(model.__name__, str(obj_id))
        data = [cls._row_to_dict(row)]
        return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")
