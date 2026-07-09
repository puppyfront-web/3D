"""FastAPI application entry point with CORS, routers, and lifespan."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import get_db


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        """Startup/shutdown lifecycle handler."""
        # Startup: seed required data only. Schema changes must come from Alembic.
        from app.db.init_db import seed_if_needed
        await seed_if_needed()

        # Register built-in TOOLS first, then SKILLS. Order matters: skills
        # validate their required_services against the ToolRegistry at
        # registration time, so registering tools first avoids the spurious
        # "requires tool X which is not registered" errors on startup.
        from app.tools.registry import ToolRegistry
        tool_registry = ToolRegistry.get_instance()
        if not tool_registry.list_tools():
            tool_registry.auto_register()

        # Register built-in skills on startup (not lazy on first router hit).
        from app.skills.registry import SkillRegistry
        registry = SkillRegistry.get_instance()
        if not registry.list_skills():
            registry.auto_register()

        yield
        # Shutdown: clean up engine connections
        from app.db.session import engine
        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Mount routers under /api/v1
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """Include all API routers with the /api/v1 prefix."""
    from app.routers import (
        agents,
        auth,
        canvas,
        cases,
        companies,
        company_profiles,
        conversations,
        documents,
        exports,
        feedback,
        generations,
        industry_materials,
        pricing_experiences,
        projects,
        rag,
        rules,
        settings,
        skills,
        talking_points,
        templates,
        users,
        visual_styles,
        workflows,
    )

    prefix = "/api/v1"

    # auth.router (login/logout/register) stays unprotected; every other
    # router requires a valid JWT via get_current_user. Health/ready endpoints
    # are defined directly on `app` below, not via include_router, so they
    # remain public too.
    from app.core.security import get_current_user

    auth_deps = [Depends(get_current_user)]

    app.include_router(auth.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(projects.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(companies.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(company_profiles.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(documents.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(cases.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(templates.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(workflows.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(visual_styles.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(rules.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(generations.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(rag.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(agents.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(feedback.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(exports.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(skills.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(conversations.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(settings.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(canvas.router, prefix=prefix, dependencies=auth_deps)
    # Internal knowledge bases (PRD §12)
    app.include_router(industry_materials.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(talking_points.router, prefix=prefix, dependencies=auth_deps)
    app.include_router(pricing_experiences.router, prefix=prefix, dependencies=auth_deps)


# Create the application instance
app = create_app()


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Liveness probe — the process is up.

    Intentionally has no DB dependency: it must keep returning 200 while the DB
    is slow or down, so orchestrators (k8s/docker) don't kill the pod and mask
    the real DB problem. Use /ready for dependency checks.
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "debug": settings.debug,
    }


@app.get("/ready", tags=["health"])
async def readiness_check(db=Depends(get_db)):
    """Readiness probe — DB reachable + live provider config.

    Reflects the *live* config from the database (admin UI) with .env fallback,
    in sync with what the service factories actually use. Point k8s readiness
    (not liveness) here.
    """
    from app.services.settings_service import SettingsService

    cfg = await SettingsService.get_raw_many(
        db, [
            "llm_provider", "embedding_provider", "image_provider",
            "embedding_dimensions",
        ]
    )

    # Vector-column dimension check. document_chunks.embedding is fixed at
    # Vector(1536) by the ORM model + migration; a non-mock embedding provider
    # configured with a different dimension silently breaks vector search.
    # Surface this as a readiness warning so ops catches misconfigurations
    # without grepping logs. (get_embedding_service also degrades to mock on
    # mismatch — this just makes the misconfiguration visible in /ready.)
    warnings = []
    embedding_provider = cfg["embedding_provider"]
    try:
        embedding_dimensions = int(cfg["embedding_dimensions"])
    except (TypeError, ValueError):
        embedding_dimensions = settings.embedding_dimensions

    if (
        embedding_provider
        and embedding_provider != "mock"
        and embedding_dimensions != 1536
    ):
        warnings.append(
            f"embedding_dimensions={embedding_dimensions} but the "
            f"document_chunks.embedding column is Vector(1536); vector "
            f"search will degrade to keyword. Align the embedding model to "
            f"1536 dims or add a migration to reindex the column."
        )

    return {
        "status": "ready",
        "version": settings.app_version,
        "debug": settings.debug,
        "llm_provider": cfg["llm_provider"],
        "embedding_provider": cfg["embedding_provider"],
        "image_provider": cfg["image_provider"],
        "embedding_dimensions": embedding_dimensions,
        "warnings": warnings,
    }
