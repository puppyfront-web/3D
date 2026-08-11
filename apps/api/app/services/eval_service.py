"""Eval set CRUD and batch retrieval runs."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.models.eval import EvalCase, EvalRun, EvalSet
from app.rag.retrieval_orchestrator import retrieval_orchestrator
from app.services.eval_scoring_service import aggregate_metrics, score_case
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

B2B_SMOKE_TEMPLATE_ID = "b2b-smoke-v1"
B2B_SMOKE_DEFAULT_NAME = "交付冒烟集"
B2B_SMOKE_CASES: List[Dict[str, Any]] = [
    {
        "query": "混合检索与可追溯问答",
        "expected_keywords": ["混合检索"],
        "notes": "资料中需包含「混合检索」等关键词；可在检索实验室保存更精确用例",
    },
    {
        "query": "智汇云有哪些核心能力",
        "expected_keywords": ["智汇云"],
        "notes": "上传产品/能力说明后运行；无资料时 Hit@k 可能为 0",
    },
    {
        "query": "适用场景是什么",
        "expected_keywords": ["场景"],
        "notes": "通用冒烟问句，建议结合企业资料改写 expected_keywords",
    },
]


class EvalService:
    async def list_sets(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[EvalSet], int]:
        q = select(EvalSet)
        cq = select(func.count(EvalSet.id))
        if status:
            q = q.where(EvalSet.status == status)
            cq = cq.where(EvalSet.status == status)
        total = (await db.execute(cq)).scalar_one()
        offset = (page - 1) * page_size
        rows = (
            await db.execute(
                q.order_by(EvalSet.updated_at.desc()).offset(offset).limit(page_size)
            )
        ).scalars().all()
        return list(rows), total

    async def get_set(self, db: AsyncSession, set_id: uuid.UUID) -> EvalSet:
        row = await db.get(EvalSet, set_id)
        if not row:
            raise NotFoundException(f"EvalSet {set_id} not found")
        return row

    async def create_set(
        self,
        db: AsyncSession,
        *,
        name: str,
        description: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
    ) -> EvalSet:
        row = EvalSet(
            name=name,
            description=description,
            project_id=project_id,
            status="active",
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    async def list_cases(self, db: AsyncSession, set_id: uuid.UUID) -> List[EvalCase]:
        await self.get_set(db, set_id)
        result = await db.execute(
            select(EvalCase).where(EvalCase.set_id == set_id).order_by(EvalCase.created_at)
        )
        return list(result.scalars().all())

    async def create_case(
        self,
        db: AsyncSession,
        set_id: uuid.UUID,
        data: Dict[str, Any],
    ) -> EvalCase:
        await self.get_set(db, set_id)
        row = EvalCase(set_id=set_id, **data)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    async def delete_case(self, db: AsyncSession, case_id: uuid.UUID) -> None:
        row = await db.get(EvalCase, case_id)
        if not row:
            raise NotFoundException(f"EvalCase {case_id} not found")
        await db.delete(row)
        await db.flush()

    async def import_smoke_template(
        self,
        db: AsyncSession,
        *,
        template_id: str = B2B_SMOKE_TEMPLATE_ID,
        name: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
    ) -> EvalSet:
        if template_id != B2B_SMOKE_TEMPLATE_ID:
            raise NotFoundException(f"Unknown eval template {template_id}")

        set_name = (name or B2B_SMOKE_DEFAULT_NAME).strip()
        existing = (
            await db.execute(select(EvalSet).where(EvalSet.name == set_name).limit(1))
        ).scalar_one_or_none()
        if existing:
            eval_set = existing
        else:
            eval_set = await self.create_set(
                db, name=set_name, description="内置 B2B 交付冒烟问答集", project_id=project_id
            )

        existing_queries = {
            q.strip()
            for q in (
                await db.execute(
                    select(EvalCase.query).where(EvalCase.set_id == eval_set.id)
                )
            ).scalars().all()
        }
        for item in B2B_SMOKE_CASES:
            q = item["query"].strip()
            if q in existing_queries:
                continue
            await self.create_case(
                db,
                eval_set.id,
                {
                    "query": q,
                    "expected_keywords": item.get("expected_keywords", []),
                    "notes": item.get("notes"),
                    "source": "template",
                },
            )
            existing_queries.add(q)

        await db.refresh(eval_set)
        return eval_set

    async def _config_snapshot(self, db: AsyncSession, overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        provider = await SettingsService.get_safe(
            db, "retrieval_provider", settings.retrieval_provider or "local"
        )
        top_k = 8
        if overrides and overrides.get("top_k"):
            top_k = int(overrides["top_k"])
        snap = {
            "top_k": top_k,
            "retrieval_provider": provider,
            "scope": (overrides or {}).get("scope", "union"),
        }
        return snap

    async def run_set(
        self,
        db: AsyncSession,
        set_id: uuid.UUID,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> EvalRun:
        eval_set = await self.get_set(db, set_id)
        cases = await self.list_cases(db, set_id)
        snap = await self._config_snapshot(db, config_overrides)
        top_k = snap["top_k"]

        run = EvalRun(
            set_id=set_id,
            status="running",
            config_snapshot_json=snap,
        )
        db.add(run)
        await db.flush()

        per_case: List[Dict[str, Any]] = []
        for case in cases:
            start = time.monotonic()
            try:
                traced = await retrieval_orchestrator.search(
                    db,
                    case.query,
                    top_k=top_k,
                    project_id=eval_set.project_id,
                    triggered_by="eval_replay",
                    eval_run_id=run.id,
                )
                elapsed = int((time.monotonic() - start) * 1000)
                ok, reason = score_case(case, traced.hits)
                per_case.append(
                    {
                        "case_id": str(case.id),
                        "pass": ok,
                        "reason": reason,
                        "latency_ms": elapsed,
                        "top_k_ids": [h.chunk_id for h in traced.hits[:top_k]],
                        "retrieval_log_id": str(traced.log_id) if traced.log_id else None,
                    }
                )
            except Exception as exc:
                logger.exception("eval run case failed set=%s case=%s", set_id, case.id)
                per_case.append(
                    {
                        "case_id": str(case.id),
                        "pass": False,
                        "reason": "error",
                        "error": str(exc)[:200],
                        "latency_ms": 0,
                        "top_k_ids": [],
                    }
                )

        metrics = aggregate_metrics(per_case)
        run.status = "completed"
        run.metrics_json = metrics
        run.per_case_results_json = per_case
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(run)
        return run

    async def get_run(self, db: AsyncSession, run_id: uuid.UUID) -> EvalRun:
        row = await db.get(EvalRun, run_id)
        if not row:
            raise NotFoundException(f"EvalRun {run_id} not found")
        return row

    async def list_runs(
        self,
        db: AsyncSession,
        set_id: Optional[uuid.UUID] = None,
        limit: int = 20,
    ) -> List[EvalRun]:
        q = select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit)
        if set_id:
            q = q.where(EvalRun.set_id == set_id)
        return list((await db.execute(q)).scalars().all())


eval_service = EvalService()
