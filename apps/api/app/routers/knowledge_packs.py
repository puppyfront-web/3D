"""Knowledge Pack import API (M3)."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.knowledge_pack import KnowledgePackImportResult, KnowledgePackTemplateOut
from app.services.knowledge_pack_service import knowledge_pack_service

router = APIRouter(prefix="/knowledge/packs", tags=["knowledge-packs"])


@router.get("/templates", response_model=Response[List[KnowledgePackTemplateOut]])
async def list_pack_templates(
    _admin: User = Depends(require_admin),
):
    items = await knowledge_pack_service.list_templates()
    return Response(
        data=[KnowledgePackTemplateOut.model_validate(t) for t in items]
    )


@router.post("/import", response_model=Response[KnowledgePackImportResult])
async def import_knowledge_pack(
    file: UploadFile = File(...),
    project_id: Optional[uuid.UUID] = Query(
        None, description="Cases 与 eval 默认关联的项目 ID"
    ),
    force: bool = Query(False, description="忽略相同 pack 内容 hash，强制重新导入"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    raw = await file.read()
    result = await knowledge_pack_service.import_zip(
        db, raw, project_id=project_id, force=force
    )
    await db.commit()
    return Response(
        data=KnowledgePackImportResult.model_validate(result),
        message="导入完成" if not result.get("skipped") else "已跳过（相同 Pack 已导入）",
    )
