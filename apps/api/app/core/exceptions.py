"""Custom exception classes and FastAPI exception handlers."""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        detail: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(message)


class NotFoundException(AppException):
    """Resource not found."""

    def __init__(self, resource: str = "Resource", resource_id: str = ""):
        msg = f"{resource}"
        if resource_id:
            msg = f"{resource} with id '{resource_id}' not found"
        super().__init__(message=msg, status_code=404)


class BadRequestException(AppException):
    """Bad request exception."""

    def __init__(self, message: str = "Bad request"):
        super().__init__(message=message, status_code=400)


class ForbiddenException(AppException):
    """Forbidden access."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(message=message, status_code=403)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach custom exception handlers to the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        content: Dict[str, Any] = {
            "success": False,
            "message": exc.message,
        }
        if exc.detail:
            content["detail"] = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    @app.exception_handler(NotFoundException)
    async def not_found_handler(
        request: Request, exc: NotFoundException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # exc.errors() may carry the original exception object (e.g. a
        # ValueError raised by a field_validator) in ``ctx``, which JSONResponse
        # cannot serialize — surfacing as a TypeError 500 instead of a clean
        # 422. jsonable_encoder renders it safely.
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Validation error",
                "detail": jsonable_encoder(exc.errors()),
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "Database integrity error",
                "detail": str(exc.orig),
            },
        )
