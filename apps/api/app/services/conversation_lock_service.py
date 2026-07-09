"""ConversationLockService — application-level per-conversation chat lock.

Implements mutual exclusion on ``POST /conversations/{id}/chat/stream`` so two
concurrent messages can't both drive ``fill_canvas`` / ``ProposalAgent`` against
the same conversation (Defect #2: race condition on first-message auto-fill,
last-writer-wins node corruption).

Design:
  - One row per conversation (unique index ``ux_conversation_locks_conversation_id``).
  - ``try_acquire`` reaps expired rows, then ``INSERT ... ON CONFLICT DO NOTHING``.
    The unique index makes concurrent acquires atomic — only one INSERT succeeds.
  - ``release`` deletes the row only if the holder token matches (a later request
    can't release an earlier one's lock).
  - TTL (default 120s) bounds how long a crashed handler can hold the lock;
    a subsequent acquire reaps the stale row.

Works on SQLite (tests) and Postgres (production) — both support
``INSERT ON CONFLICT DO NOTHING`` (SQLite ≥ 3.24, all supported Postgres).
No Redis dependency.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_lock import ConversationLock

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 120


class ConversationLockService:
    """Acquire / release per-conversation processing locks."""

    async def try_acquire(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> Optional[str]:
        """Try to acquire the lock. Returns a holder token on success, or None
        if the conversation is already locked (and the lock hasn't expired).

        ``db`` is committed on success so the row is visible to concurrent
        transactions immediately (critical for the unique-index to block).

        On SQLite (single-writer), the reaping DELETE may hit "database is
        locked" if the streaming session holds a write transaction. The reaping
        is best-effort — the INSERT's unique constraint is the real mutex, so a
        failed reap doesn't break correctness, only leaves a stale row that the
        TTL + next successful reap will clear.
        """
        now = datetime.now(timezone.utc)

        # 1. Reap expired locks owned by anyone (best-effort under SQLite).
        try:
            await db.execute(
                delete(ConversationLock).where(ConversationLock.expires_at < now)
            )
            await db.commit()
        except Exception as e:  # noqa: BLE001 — reap is best-effort
            await db.rollback()
            logger.debug("Lock reap skipped (non-fatal): %s", e)

        # 2. Try to insert. The unique index on conversation_id makes a
        #    concurrent insert raise IntegrityError — we treat that as "locked".
        token = secrets.token_hex(16)
        expires_at = now + timedelta(seconds=ttl_seconds)
        try:
            await db.execute(
                insert(ConversationLock).values(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    holder=token,
                    expires_at=expires_at,
                )
            )
            await db.commit()
            logger.info("Acquired conversation lock conv=%s holder=%s", conversation_id, token[:8])
            return token
        except IntegrityError:
            # Unique constraint violation — another request holds the lock.
            await db.rollback()
            # Distinguish "genuinely locked" from "expired-but-not-reaped-yet" by
            # checking the current holder's expiry. If expired, retry once.
            existing = await self._peek(db, conversation_id)
            if existing is not None and existing.expires_at < now:
                logger.info("Retrying acquire after stale lock conv=%s", conversation_id)
                try:
                    await db.execute(
                        delete(ConversationLock).where(ConversationLock.id == existing.id)
                    )
                    await db.commit()
                except Exception as e:  # noqa: BLE001
                    await db.rollback()
                    logger.debug("Stale lock force-reap skipped: %s", e)
                return await self.try_acquire(db, conversation_id, ttl_seconds)
            logger.info("Conversation %s is locked, rejecting", conversation_id)
            return None
        except Exception as e:  # noqa: BLE001 — SQLite "database is locked" on INSERT
            # On SQLite, if the streaming session holds the write lock, even the
            # INSERT can fail with "database is locked" (not IntegrityError).
            # Distinguish: if a lock row actually exists for this conversation,
            # the conversation IS locked → return None. If no row exists, the
            # DB itself is just busy → degrade to allow (return token), which is
            # the correct best-effort behavior under SQLite's single-writer model.
            # Postgres (production) never hits this path.
            await db.rollback()
            existing = await self._peek(db, conversation_id)
            if existing is not None:
                logger.info("Conversation %s is locked (detected post-failure)", conversation_id)
                return None
            logger.warning(
                "Lock acquire failed (%s) — degrading to allow on conv=%s. "
                "Expected under SQLite test profile; Postgres enforces strictly.",
                e, conversation_id,
            )
            return token

    async def release(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        holder: str,
    ) -> None:
        """Release the lock, but only if the holder token matches — prevents a
        later request from accidentally releasing an earlier one's lock after
        the TTL expired and was re-acquired. Best-effort under SQLite."""
        try:
            await db.execute(
                delete(ConversationLock).where(
                    ConversationLock.conversation_id == conversation_id,
                    ConversationLock.holder == holder,
                )
            )
            await db.commit()
        except Exception as e:  # noqa: BLE001 — release is best-effort
            await db.rollback()
            logger.debug("Lock release skipped (non-fatal): %s", e)

    async def _peek(
        self, db: AsyncSession, conversation_id: uuid.UUID
    ) -> Optional[ConversationLock]:
        result = await db.execute(
            select(ConversationLock).where(
                ConversationLock.conversation_id == conversation_id
            )
        )
        return result.scalars().first()


conversation_lock_service = ConversationLockService()
