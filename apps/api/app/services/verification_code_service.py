"""Verification-code service — issue/verify one-time email codes.

Codes are 6-digit, single-use, expire after 10 minutes, allow at most 5
failed verify attempts, and are stored only as an HMAC digest keyed by the
app secret. A 60-second resend cooldown is enforced per (email, purpose).
"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.verification_code import EmailVerificationCode

logger = logging.getLogger(__name__)

CODE_TTL_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5
VALID_PURPOSES = {"login", "reset"}


def _digest(email: str, code: str) -> str:
    return hmac.new(
        settings.secret_key.encode(), f"{email}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes despite DateTime(timezone=True)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class VerificationCodeService:
    @staticmethod
    async def issue(
        db: AsyncSession, email: str, purpose: str
    ) -> Tuple[Optional[str], Optional[int]]:
        """Create a new code. Returns (code, retry_after_seconds).

        `code` is None when the previous code is still inside the resend
        cooldown — `retry_after_seconds` then tells the client how long to wait.
        """
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == purpose,
                EmailVerificationCode.used_at.is_(None),
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
        latest = result.scalars().first()
        if latest is not None:
            age = (now - _as_utc(latest.created_at)).total_seconds()
            if age < RESEND_COOLDOWN_SECONDS:
                return None, int(RESEND_COOLDOWN_SECONDS - age)

        code = f"{secrets.randbelow(1000000):06d}"
        db.add(
            EmailVerificationCode(
                email=email,
                purpose=purpose,
                code_hash=_digest(email, code),
                expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
            )
        )
        await db.flush()
        return code, None

    @staticmethod
    async def verify(
        db: AsyncSession, email: str, purpose: str, code: str
    ) -> bool:
        """Verify and consume the latest unused code for (email, purpose)."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == purpose,
                EmailVerificationCode.used_at.is_(None),
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
        row = result.scalars().first()
        if row is None:
            return False
        if _as_utc(row.expires_at) < now or row.attempts >= MAX_ATTEMPTS:
            return False

        if hmac.compare_digest(row.code_hash, _digest(email, code)):
            await db.execute(
                update(EmailVerificationCode)
                .where(EmailVerificationCode.id == row.id)
                .values(used_at=now)
            )
            await db.flush()
            return True

        await db.execute(
            update(EmailVerificationCode)
            .where(EmailVerificationCode.id == row.id)
            .values(attempts=EmailVerificationCode.attempts + 1)
        )
        await db.flush()
        return False
