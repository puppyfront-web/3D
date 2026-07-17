"""OperationRunService — minimal P2 observability parent (PRESALE_DELIVERY_SPEC §11.2).

Wraps a presale main-flow turn in a single OperationRun row with a per-step
JSON log. Used by _handle_auto_fill today; extensible to conversational /
export turns later. Soft-fails everywhere — observability must never break
the user-facing flow.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_run import OperationRun

logger = logging.getLogger(__name__)


class OperationRunService:
    """Create / update / finalise OperationRun rows."""

    async def start(
        self,
        db: AsyncSession,
        project_id,
        operation_type: str,
        conversation_id=None,
    ) -> Optional[OperationRun]:
        """Create a running OperationRun. Returns None on failure (soft-fail)."""
        try:
            run = OperationRun(
                id=uuid.uuid4(),
                project_id=uuid.UUID(str(project_id)),
                conversation_id=uuid.UUID(str(conversation_id))
                if conversation_id
                else None,
                operation_type=operation_type,
                status="running",
                steps=[],
                started_at=datetime.now(timezone.utc),
            )
            db.add(run)
            await db.flush()
            return run
        except Exception:
            logger.exception("operation_run: start failed; continuing without trace")
            return None

    async def add_step(
        self,
        db: AsyncSession,
        run: Optional[OperationRun],
        step: str,
        status: str,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a step record to run.steps. Soft-fails."""
        if run is None:
            return
        try:
            steps = list(run.steps or [])
            entry: Dict[str, Any] = {
                "step": step,
                "status": status,
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }
            if error:
                entry["error"] = error
            if extra:
                entry["extra"] = extra
            steps.append(entry)
            run.steps = steps
            await db.flush()
        except Exception:
            logger.exception("operation_run: add_step failed; continuing")

    async def finish(
        self,
        db: AsyncSession,
        run: Optional[OperationRun],
        status: str = "completed",
        error: Optional[str] = None,
    ) -> None:
        """Mark the run finished. Soft-fails."""
        if run is None:
            return
        try:
            run.status = status
            run.ended_at = datetime.now(timezone.utc)
            if error:
                run.error = error
            await db.flush()
        except Exception:
            logger.exception("operation_run: finish failed; continuing")


operation_run_service = OperationRunService()
