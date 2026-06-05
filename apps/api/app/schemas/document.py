"""Document schemas."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    title: Optional[str] = Field(None, max_length=500)


class DocumentCreate(DocumentBase):
    project_id: uuid.UUID


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, max_length=50)


class DocumentOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
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
    message: str = "Document uploaded successfully"
