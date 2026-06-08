"""Documents router — upload, list, CRUD, and knowledge base indexing."""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.document import Document
from app.schemas.common import PaginatedResponse, Response
from app.schemas.document import (
    DocumentBatchIndexRequest,
    DocumentBatchIndexResponse,
    DocumentIndexResponse,
    DocumentOut,
    DocumentUpdate,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_service() -> DocumentService:
    return DocumentService(storage_path=settings.storage_path)


# ---------------------------------------------------------------------------
# Indexing endpoints — MUST come before {document_id} routes
# ---------------------------------------------------------------------------


@router.post("/index-batch", response_model=Response[DocumentBatchIndexResponse])
async def index_batch(
    body: DocumentBatchIndexRequest,
    db: AsyncSession = Depends(get_db),
):
    """Batch index documents by IDs, by project, or all un-indexed."""
    service = _get_service()

    if body.project_id and not body.document_ids:
        summary = await service.index_project_documents(body.project_id, db)
    elif body.document_ids:
        summary = await service.index_batch(body.document_ids, db)
    else:
        # Index all un-indexed documents
        summary = await service.index_all_unindexed(db)

    return Response(
        data=DocumentBatchIndexResponse(**summary),
        message=f"Indexed {summary['indexed']}/{summary['total']} documents",
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=Response[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[uuid.UUID] = Query(None),
    auto_index: bool = Query(True, description="Automatically index after upload"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document and optionally auto-index it into the knowledge base."""
    service = _get_service()

    try:
        document = await service.upload_and_index(
            file=file,
            db=db,
            project_id=project_id,
            auto_index=auto_index,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return Response(
        data=DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            content_type=document.content_type,
            file_size=document.file_size,
            status=document.status,
            chunk_count=document.chunk_count,
            message="Document uploaded and indexed"
            if document.status == "indexed"
            else "Document uploaded (indexing pending)",
        ),
        message="Document uploaded successfully",
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[DocumentOut])
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    """List documents with pagination and filters."""
    query = select(Document)
    count_query = select(func.count(Document.id))

    if project_id:
        query = query.where(Document.project_id == project_id)
        count_query = count_query.where(Document.project_id == project_id)
    if status_filter:
        query = query.where(Document.status == status_filter)
        count_query = count_query.where(Document.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Document.created_at.desc())
    result = await db.execute(query)
    documents = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[DocumentOut.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{document_id}", response_model=Response[DocumentOut])
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a document by ID."""
    document = await db.get(Document, document_id)
    if not document:
        raise NotFoundException("Document", str(document_id))
    return Response(data=DocumentOut.model_validate(document))


@router.post("/{document_id}/index", response_model=Response[DocumentIndexResponse])
async def index_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger (re-)indexing of a single document into the knowledge base."""
    service = _get_service()

    try:
        chunk_count = await service.index_document(document_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    document = await db.get(Document, document_id)
    return Response(
        data=DocumentIndexResponse(
            document_id=document_id,
            status=document.status if document else "unknown",
            chunk_count=chunk_count,
        ),
    )


@router.put("/{document_id}", response_model=Response[DocumentOut])
async def update_document(
    document_id: uuid.UUID, body: DocumentUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a document's metadata."""
    document = await db.get(Document, document_id)
    if not document:
        raise NotFoundException("Document", str(document_id))

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(document, field, value)

    await db.flush()
    await db.refresh(document)
    return Response(data=DocumentOut.model_validate(document), message="Document updated")


@router.delete("/{document_id}", response_model=Response)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a document and its chunks."""
    document = await db.get(Document, document_id)
    if not document:
        raise NotFoundException("Document", str(document_id))

    # Delete file from disk
    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)

    await db.delete(document)
    return Response(message="Document deleted")
