"""FastAPI application entry point with CORS, routers, and lifespan."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        """Startup/shutdown lifecycle handler."""
        # Startup: initialize database
        from app.db.init_db import init_db
        await init_db()
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
        cases,
        companies,
        company_profiles,
        documents,
        exports,
        feedback,
        generations,
        projects,
        rag,
        rules,
        templates,
        users,
        visual_styles,
        workflows,
    )

    prefix = "/api/v1"

    app.include_router(auth.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(projects.router, prefix=prefix)
    app.include_router(companies.router, prefix=prefix)
    app.include_router(company_profiles.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(cases.router, prefix=prefix)
    app.include_router(templates.router, prefix=prefix)
    app.include_router(workflows.router, prefix=prefix)
    app.include_router(visual_styles.router, prefix=prefix)
    app.include_router(rules.router, prefix=prefix)
    app.include_router(generations.router, prefix=prefix)
    app.include_router(rag.router, prefix=prefix)
    app.include_router(agents.router, prefix=prefix)
    app.include_router(feedback.router, prefix=prefix)
    app.include_router(exports.router, prefix=prefix)


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
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "debug": settings.debug,
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "image_provider": settings.image_provider,
    }
