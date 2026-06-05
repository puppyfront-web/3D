"""Security helpers for API authentication (MVP: simple API key)."""

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Validate the incoming API key against the configured secret.

    In development mode (debug=True), requests without an API key are
    allowed through.  In production every request must carry the correct
    key in the ``X-API-Key`` header.
    """
    if settings.debug and not api_key:
        return "anonymous"

    expected = settings.api_key
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
