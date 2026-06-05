"""Rules router — Technical + Quality rule CRUD."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.rule import QualityRule, TechnicalRule
from app.schemas.common import PaginatedResponse, Response
from app.schemas.rule import (
    QualityRuleCreate,
    QualityRuleOut,
    QualityRuleUpdate,
    TechnicalRuleCreate,
    TechnicalRuleOut,
    TechnicalRuleUpdate,
)

router = APIRouter(prefix="/rules", tags=["rules"])


# ---------------------------------------------------------------------------
# Technical Rules
# ---------------------------------------------------------------------------

@router.get("/technical", response_model=PaginatedResponse[TechnicalRuleOut])
async def list_technical_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List technical rules."""
    query = select(TechnicalRule)
    count_query = select(func.count(TechnicalRule.id))

    if category:
        query = query.where(TechnicalRule.category == category)
        count_query = count_query.where(TechnicalRule.category == category)
    if severity:
        query = query.where(TechnicalRule.severity == severity)
        count_query = count_query.where(TechnicalRule.severity == severity)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(TechnicalRule.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[TechnicalRuleOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/technical/{rule_id}", response_model=Response[TechnicalRuleOut])
async def get_technical_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    rule = await db.get(TechnicalRule, rule_id)
    if not rule:
        raise NotFoundException("TechnicalRule", str(rule_id))
    return Response(data=TechnicalRuleOut.model_validate(rule))


@router.post("/technical", response_model=Response[TechnicalRuleOut], status_code=status.HTTP_201_CREATED)
async def create_technical_rule(body: TechnicalRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = TechnicalRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return Response(data=TechnicalRuleOut.model_validate(rule), message="Technical rule created")


@router.put("/technical/{rule_id}", response_model=Response[TechnicalRuleOut])
async def update_technical_rule(
    rule_id: uuid.UUID, body: TechnicalRuleUpdate, db: AsyncSession = Depends(get_db)
):
    rule = await db.get(TechnicalRule, rule_id)
    if not rule:
        raise NotFoundException("TechnicalRule", str(rule_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.flush()
    await db.refresh(rule)
    return Response(data=TechnicalRuleOut.model_validate(rule), message="Technical rule updated")


@router.delete("/technical/{rule_id}", response_model=Response)
async def delete_technical_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    rule = await db.get(TechnicalRule, rule_id)
    if not rule:
        raise NotFoundException("TechnicalRule", str(rule_id))
    await db.delete(rule)
    return Response(message="Technical rule deleted")


# ---------------------------------------------------------------------------
# Quality Rules
# ---------------------------------------------------------------------------

@router.get("/quality", response_model=PaginatedResponse[QualityRuleOut])
async def list_quality_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List quality rules."""
    query = select(QualityRule)
    count_query = select(func.count(QualityRule.id))

    if category:
        query = query.where(QualityRule.category == category)
        count_query = count_query.where(QualityRule.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(QualityRule.created_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[QualityRuleOut.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size, total_pages=total_pages,
    )


@router.get("/quality/{rule_id}", response_model=Response[QualityRuleOut])
async def get_quality_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    rule = await db.get(QualityRule, rule_id)
    if not rule:
        raise NotFoundException("QualityRule", str(rule_id))
    return Response(data=QualityRuleOut.model_validate(rule))


@router.post("/quality", response_model=Response[QualityRuleOut], status_code=status.HTTP_201_CREATED)
async def create_quality_rule(body: QualityRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = QualityRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return Response(data=QualityRuleOut.model_validate(rule), message="Quality rule created")


@router.put("/quality/{rule_id}", response_model=Response[QualityRuleOut])
async def update_quality_rule(
    rule_id: uuid.UUID, body: QualityRuleUpdate, db: AsyncSession = Depends(get_db)
):
    rule = await db.get(QualityRule, rule_id)
    if not rule:
        raise NotFoundException("QualityRule", str(rule_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.flush()
    await db.refresh(rule)
    return Response(data=QualityRuleOut.model_validate(rule), message="Quality rule updated")


@router.delete("/quality/{rule_id}", response_model=Response)
async def delete_quality_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    rule = await db.get(QualityRule, rule_id)
    if not rule:
        raise NotFoundException("QualityRule", str(rule_id))
    await db.delete(rule)
    return Response(message="Quality rule deleted")
