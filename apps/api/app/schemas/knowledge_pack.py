"""Knowledge Pack import schemas (M3)."""

import uuid
from typing import Any, Dict, List, Optional

from app.schemas.common import APIBaseModel


class KnowledgePackImportResult(APIBaseModel):
    pack_name: str
    documents_imported: int
    cases_imported: int
    talking_points_imported: int
    eval_set_id: Optional[uuid.UUID] = None
    skipped: bool = False
    errors: List[str] = []


class KnowledgePackTemplateOut(APIBaseModel):
    template_id: str
    description: str
    format_hint: str


class DocumentChunkOut(APIBaseModel):
    id: uuid.UUID
    chunk_index: int
    page_number: Optional[int] = None
    token_count: int
    content_preview: str
    metadata_json: Optional[str] = None
