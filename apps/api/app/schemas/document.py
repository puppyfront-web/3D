"""Document schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    title: Optional[str] = Field(None, max_length=500)


class DocumentCreate(DocumentBase):
    project_id: Optional[uuid.UUID] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, max_length=50)


class DocumentOut(BaseModel):
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

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Response after a successful document upload."""

    id: uuid.UUID
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    status: str
    chunk_count: int = 0
    message: str = "Document uploaded successfully"


class DocumentIndexResponse(BaseModel):
    """Response after indexing a document."""

    document_id: uuid.UUID
    status: str
    chunk_count: int
    message: str = "Document indexed successfully"


class DocumentBatchIndexRequest(BaseModel):
    """Request body for batch indexing."""

    document_ids: Optional[List[uuid.UUID]] = None
    project_id: Optional[uuid.UUID] = None


class DocumentBatchIndexResponse(BaseModel):
    """Response after batch indexing."""

    total: int
    indexed: int
    failed: int
    total_chunks: int
    message: str = "Batch indexing completed"
