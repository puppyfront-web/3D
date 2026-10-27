"""Eval Center API — golden set regression (admin only)."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse, Response
from app.schemas.eval import (
    EvalCaseCreate,
    EvalCaseFromLab,
    EvalCaseOut,
    EvalImportTemplate,
    EvalRunCreate,
    EvalRunOut,
    EvalSetCreate,
    EvalSetOut,
)
from app.services.eval_service import eval_service

router = APIRouter(prefix="/eval", tags=["eval"])


@router.get("/sets", response_model=PaginatedResponse[EvalSetOut])
async def list_eval_sets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    items, total = await eval_service.list_sets(db, page=page, page_size=page_size, status=status)
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[EvalSetOut.model_validate(s, from_attributes=True) for s in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/sets", response_model=Response[EvalSetOut])
async def create_eval_set(
    body: EvalSetCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = await eval_service.create_set(
        db,
        name=body.name,
        description=body.description,
        project_id=body.project_id,
    )
    await db.commit()
    return Response(data=EvalSetOut.model_validate(row, from_attributes=True))


@router.get("/sets/{set_id}/cases", response_model=Response[List[EvalCaseOut]])
async def list_eval_cases(
    set_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    cases = await eval_service.list_cases(db, set_id)
    return Response(
        data=[EvalCaseOut.model_validate(c, from_attributes=True) for c in cases]
    )


@router.post("/sets/{set_id}/cases", response_model=Response[EvalCaseOut])
async def create_eval_case(
    set_id: uuid.UUID,
    body: EvalCaseCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = await eval_service.create_case(
        db,
        set_id,
        body.model_dump(),
    )
    await db.commit()
    return Response(data=EvalCaseOut.model_validate(row, from_attributes=True))


@router.post("/import-template", response_model=Response[EvalSetOut])
async def import_eval_template(
    body: EvalImportTemplate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    row = await eval_service.import_smoke_template(
        db,
        template_id=body.template_id,
        name=body.name,
        project_id=body.project_id,
    )
    await db.commit()
    return Response(data=EvalSetOut.model_validate(row, from_attributes=True))


@router.delete("/cases/{case_id}", response_model=Response[dict])
async def delete_eval_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await eval_service.delete_case(db, case_id)
    await db.commit()
    return Response(data={"deleted": True, "id": str(case_id)})


@router.post("/cases/from-lab", response_model=Response[EvalCaseOut])
async def create_case_from_lab(
    body: EvalCaseFromLab,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    chunk_ids: List[str] = []
    doc_ids: List[str] = []
    if body.top_k_snapshot and 0 <= body.pick_rank < len(body.top_k_snapshot):
        pick = body.top_k_snapshot[body.pick_rank]
        cid = pick.get("chunk_id") or pick.get("chunkId")
        did = pick.get("document_id") or pick.get("documentId")
        if cid:
            chunk_ids = [str(cid)]
        if did:
            doc_ids = [str(did)]
    row = await eval_service.create_case(
        db,
        body.set_id,
        {
            "query": body.query,
            "expected_chunk_ids": chunk_ids,
            "expected_document_ids": doc_ids,
            "source": "hit_test",
        },
    )
    await db.commit()
    return Response(data=EvalCaseOut.model_validate(row, from_attributes=True))


@router.post("/runs", response_model=Response[EvalRunOut])
async def create_eval_run(
    body: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    run = await eval_service.run_set(
        db, body.set_id, config_overrides=body.config_overrides
    )
    await db.commit()
    return Response(data=EvalRunOut.model_validate(run, from_attributes=True))


@router.get("/runs/{run_id}", response_model=Response[EvalRunOut])
async def get_eval_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    run = await eval_service.get_run(db, run_id)
    return Response(data=EvalRunOut.model_validate(run, from_attributes=True))


@router.get("/runs", response_model=Response[List[EvalRunOut]])
async def list_eval_runs(
    set_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    runs = await eval_service.list_runs(db, set_id=set_id, limit=limit)
    return Response(
        data=[EvalRunOut.model_validate(r, from_attributes=True) for r in runs]
    )
