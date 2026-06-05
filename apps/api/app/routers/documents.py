"""Documents router — upload + list + CRUD."""

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
from app.models.project import Project
from app.schemas.common import PaginatedResponse, Response
from app.schemas.document import DocumentOut, DocumentUpdate, DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".txt", ".md"}


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


@router.post("/upload", response_model=Response[DocumentUploadResponse], status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document and store it locally."""
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundException("Project", str(project_id))

    original_filename = file.filename or "unnamed"
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_dir = os.path.abspath(settings.storage_path)
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, stored_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    document = Document(
        project_id=project_id,
        filename=stored_name,
        original_filename=original_filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        file_path=file_path,
        title=original_filename,
        status="uploaded",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    return Response(
        data=DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            content_type=document.content_type,
            file_size=document.file_size,
            status=document.status,
        ),
        message="Document uploaded successfully",
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
    """Delete a document."""
    document = await db.get(Document, document_id)
    if not document:
        raise NotFoundException("Document", str(document_id))
    await db.delete(document)
    return Response(message="Document deleted")
