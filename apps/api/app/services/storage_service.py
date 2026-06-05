"""File storage abstraction service."""

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional

from app.core.config import settings


class StorageService(ABC):
    """Abstract file storage interface."""

    @abstractmethod
    async def save(self, file: BinaryIO, filename: str, content_type: str) -> str:
        """Store a file and return its storage path/key."""

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read a file from storage by its path/key."""

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file from storage. Returns True if successful."""

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file exists at the given path."""

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Get the accessible URL or path for a stored file."""


class LocalStorageService(StorageService):
    """Local filesystem storage implementation."""

    def __init__(self, base_path: Optional[str] = None):
        self._base_path = os.path.abspath(base_path or settings.storage_path)
        os.makedirs(self._base_path, exist_ok=True)

    async def save(self, file: BinaryIO, filename: str, content_type: str) -> str:
        """Save a file to the local filesystem."""
        _, ext = os.path.splitext(filename)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(self._base_path, stored_name)

        with open(filepath, "wb") as f:
            shutil.copyfileobj(file, f)

        return filepath

    async def read(self, path: str) -> bytes:
        """Read a file from the local filesystem."""
        full_path = self._resolve(path)
        with open(full_path, "rb") as f:
            return f.read()

    async def delete(self, path: str) -> bool:
        """Delete a file from the local filesystem."""
        full_path = self._resolve(path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    async def exists(self, path: str) -> bool:
        """Check if a file exists locally."""
        return os.path.exists(self._resolve(path))

    def get_url(self, path: str) -> str:
        """Return the local file path as the URL."""
        return self._resolve(path)

    def _resolve(self, path: str) -> str:
        """Resolve a path to an absolute path within the storage directory."""
        if os.path.isabs(path):
            return path
        return os.path.join(self._base_path, path)


def get_storage_service() -> StorageService:
    """Factory function to create the storage service."""
    return LocalStorageService()
