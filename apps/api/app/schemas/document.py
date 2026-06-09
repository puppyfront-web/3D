"""Document schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from app.schemas.common import APIBaseModel
from pydantic import Field


class DocumentBase(APIBaseModel):
    title: Optional[str] = Field(None, max_length=500)


class DocumentCreate(DocumentBase):
    project_id: Optional[uuid.UUID] = None


class DocumentUpdate(APIBaseModel):
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, max_length=50)


class DocumentOut(APIBaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    file_path: str
    title: Optional[str] = None
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(APIBaseModel):
    """Response after a successful document upload."""

    id: uuid.UUID
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    status: str
    chunk_count: int = 0
    message: str = "Document uploaded successfully"


class DocumentIndexResponse(APIBaseModel):
    """Response after indexing a document."""

    document_id: uuid.UUID
    status: str
    chunk_count: int
    message: str = "Document indexed successfully"


class DocumentBatchIndexRequest(APIBaseModel):
    """Request body for batch indexing."""

    document_ids: Optional[List[uuid.UUID]] = None
    project_id: Optional[uuid.UUID] = None


class DocumentBatchIndexResponse(APIBaseModel):
    """Response after batch indexing."""

    total: int
    indexed: int
    failed: int
    total_chunks: int
    message: str = "Batch indexing completed"
