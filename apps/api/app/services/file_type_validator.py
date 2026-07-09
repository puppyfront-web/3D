"""File type validation via magic bytes.

The existing extension check (`ALLOWED_EXTENSIONS`) trusts the filename, which
is trivially spoofable. This module sniffs the file's real MIME via libmagic
and cross-checks it against the declared extension.

Two important wrinkles:
  * OOXML formats (docx/pptx/xlsx) are ZIP containers, so libmagic reports
    `application/zip` for them. We accept that as a valid match.
  * libmagic itself isn't installed, the call fails, or python-magic is
    missing → we return True and let the downstream parser/indexer be the
    authority. Magic is a defense-in-depth check, not a hard gate: failing
    closed would break uploads in minimal deployments where libmagic isn't
    present, which is worse than the spoofing risk we're mitigating.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Map of declared extension → set of acceptable real MIME types.
# OOXML formats list `application/zip` because that's what libmagic sees
# when it doesn't have the office-specific magic definitions loaded.
_EXPECTED_MIME_BY_EXT: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    ".xls": {"application/vnd.ms-excel", "application/octet-stream"},
    ".csv": {"text/plain", "application/csv", "text/csv"},
    ".txt": {"text/plain"},
    ".md": {"text/plain", "text/markdown"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".svg": {"image/svg+xml", "text/xml", "text/plain"},
    ".mp4": {"video/mp4"},
    ".mov": {"video/quicktime"},
    ".avi": {"video/x-msvideo"},
    ".zip": {"application/zip", "application/x-zip-compressed"},
    ".rar": {"application/x-rar", "application/x-rar-compressed"},
    ".json": {"application/json", "text/plain"},
}


def _sniff_mime(file_path: str) -> Optional[str]:
    """Return the real MIME of a file via libmagic, or None if unavailable."""
    try:
        import magic
    except ImportError:
        return None
    try:
        return magic.from_file(file_path, mime=True)
    except Exception as e:  # noqa: BLE001 — libmagic can fail many ways
        logger.debug("magic sniff failed for %s: %s", file_path, e)
        return None


def validate_real_type(file_path: str, declared_ext: str) -> bool:
    """Return True if the file's real MIME is compatible with its extension.

    Returns True (pass) when magic is unavailable — see module docstring for
    the fail-open rationale. Returns False only when we *confidently* detect
    a mismatch (i.e. magic ran successfully and produced a known-incompatible
    MIME for the declared extension).
    """
    declared_ext = declared_ext.lower()
    expected = _EXPECTED_MIME_BY_EXT.get(declared_ext)
    # Unknown extension → defer to the extension allowlist elsewhere.
    if expected is None:
        return True

    real_mime = _sniff_mime(file_path)
    if real_mime is None:
        return True  # libmagic unavailable — fail open.

    # text/plain is a wildcard: csv/txt/md/json/csv all sniff as text/plain
    # on many systems, and empty/tiny files often report inode/x-empty or
    # application/octet-stream. Don't block those — the parser is the authority.
    if real_mime in expected:
        return True
    if real_mime in {"text/plain", "application/octet-stream", "inode/x-empty"}:
        return True

    logger.warning(
        "MIME mismatch for %s: declared=%s real=%s",
        os.path.basename(file_path), declared_ext, real_mime,
    )
    return False
