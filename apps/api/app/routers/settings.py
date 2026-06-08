"""Settings router — runtime configuration for LLM / Embedding / Image providers."""

from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import Response
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=Response[Dict[str, str]])
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all application settings (sensitive values masked)."""
    data = await SettingsService.get_all(db)
    return Response(data=data)


@router.put("", response_model=Response[Dict[str, str]])
async def update_settings(
    body: Dict[str, str],
    db: AsyncSession = Depends(get_db),
):
    """Update application settings. Masked API keys are skipped."""
    data = await SettingsService.update_many(db, body)
    await db.commit()
    return Response(data=data, message="Settings updated")
