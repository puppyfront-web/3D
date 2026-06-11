"""TTL-cached service holder for long-lived consumers.

Long-lived objects (retrievers, intent detectors, indexers) hold a service
built from DB-backed provider config. When an admin changes settings via the
UI, those consumers must pick up the new config without a process restart.
This helper centralizes the "cache + monotonic expiry" pattern so every
consumer refreshes within ``ttl_seconds`` — instead of each hand-rolling its
own (and some caching forever, silently ignoring config changes).
"""

import time
from typing import Any, Awaitable, Callable, Optional


class TTLCachedService:
    """Holder that refreshes an async-built service after a TTL.

    Example::

        self._embedding = TTLCachedService(factory=get_embedding_service, ttl=30.0)
        ...
        service = await self._embedding.get(db)
    """

    def __init__(
        self,
        factory: Callable[..., Awaitable[Any]],
        ttl_seconds: float = 30.0,
        initial: Optional[Any] = None,
    ) -> None:
        self._factory = factory
        self._ttl = ttl_seconds
        self._service: Optional[Any] = initial
        # An explicitly-provided service counts as fresh right now. Using 0.0
        # here would make it instantly stale and discard the caller's service
        # on the first get() — a subtle bug we avoid by stamping "now".
        self._cached_at: float = time.monotonic() if initial is not None else 0.0

    @property
    def service(self) -> Optional[Any]:
        """The currently cached service, without checking freshness."""
        return self._service

    async def get(self, db: Optional[Any] = None) -> Any:
        """Return the cached service, rebuilding via the factory when stale.

        If we already hold a service but this call has no ``db`` (a code path
        that only has .env config), keep the existing one rather than
        rebuilding from .env-only config — otherwise a DB-configured service
        could be silently downgraded.
        """
        stale = self._service is None or (time.monotonic() - self._cached_at) > self._ttl
        if stale and not (db is None and self._service is not None):
            self._service = await self._factory(db)
            self._cached_at = time.monotonic()
        return self._service
