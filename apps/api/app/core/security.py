"""Security utilities — password hashing, JWT creation/verification, auth dependencies."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt directly (avoids passlib/bcrypt 5.x incompatibility)."""
    # bcrypt has a 72-byte limit; truncate to avoid ValueError
    pwd_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    if not hashed:
        return False
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False

def create_access_token(user_id: str, role: str, expires_minutes: int = None) -> str:
    expire_minutes = expires_minutes or settings.access_token_expire_minutes
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(
    token: Optional[str] = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT and return the current user. Raises 401 if invalid."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    import uuid
    try:
        user = await db.get(User, uuid.UUID(user_id))
    except (ValueError, Exception):
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_user_optional(
    token: Optional[str] = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising 401. For endpoints that work both authenticated and anonymous."""
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None

async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to have admin role."""
    # user.role is a relationship to Role; check role.name
    role_name = getattr(user.role, "name", None) if user.role else None
    if role_name != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
