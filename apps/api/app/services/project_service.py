"""Project service — business logic for project creation from the wizard.

The wizard collects a rich nested payload (step1..step5 + screen). This service
resolves the bits the frontend cannot supply in MVP (no auth middleware, no
company selector): the owner (default seeded user) and the Company
(create-or-get from step1/step2). Keeps the router thin (CLAUDE.md §13.3).
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Company, Project
from app.models.user import User
from app.schemas.project import ProjectWizardCreate

logger = logging.getLogger(__name__)

# MVP has no auth middleware; default the owner to the seeded admin user.
DEFAULT_OWNER_EMAIL = "admin@3dwall.com"


class ProjectService:
    """Creates projects from the multi-step wizard payload."""

    async def create_from_wizard(
        self, db: AsyncSession, data: ProjectWizardCreate
    ) -> Project:
        step1 = data.step1
        step2 = data.step2

        owner = await self._get_default_owner(db)
        company = await self._resolve_or_create_company(db, step1, step2)

        # Persist step3/4/5 verbatim into preferences (MVP catch-all; structured
        # breakdown deferred — see plan's out-of-scope).
        preferences = {
            key: step.model_dump(exclude_none=True)
            for key, step in (
                ("proposal_style", data.step3),
                ("visual_requirements", data.step4),
                ("review_export", data.step5),
            )
            if step is not None
        }

        screen_info = self._clean_screen(data.screen)

        project = Project(
            name=step1.project_name,
            description=step1.description,
            company_id=company.id,
            owner_id=owner.id,
            status="draft",
            priority=step1.priority,
            screen_info=screen_info,
            preferences=preferences or None,
        )
        db.add(project)
        await db.flush()
        await db.refresh(project)
        logger.info(
            "Created project %s for company %s (owner=%s, screen=%s)",
            project.id, company.id, owner.email, bool(screen_info),
        )
        return project

    @staticmethod
    def _clean_screen(screen) -> Optional[dict]:
        """Drop None fields; return None if nothing meaningful remains."""
        if screen is None:
            return None
        cleaned = screen.model_dump(exclude_none=True)
        return cleaned or None

    async def _get_default_owner(self, db: AsyncSession) -> User:
        result = await db.execute(select(User).where(User.email == DEFAULT_OWNER_EMAIL))
        user = result.scalar_one_or_none()
        if user is not None:
            return user
        # Fallback: any seeded user.
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            raise RuntimeError(
                "No users seeded — cannot resolve project owner. "
                "Run init_db or configure auth."
            )
        return user

    async def _resolve_or_create_company(self, db: AsyncSession, step1, step2) -> Company:
        name = step1.client_name.strip()
        result = await db.execute(select(Company).where(Company.name == name))
        company = result.scalar_one_or_none()
        if company is not None:
            return company
        company = Company(
            name=name,
            industry=step1.industry,
            website=step2.company_website if step2 else None,
            description=step2.company_description if step2 else None,
        )
        db.add(company)
        await db.flush()
        await db.refresh(company)
        return company


project_service = ProjectService()
