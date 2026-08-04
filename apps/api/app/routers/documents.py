"""Documents router — upload, list, CRUD, export, and knowledge base indexing."""

import csv
import io
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response as RawResponse
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.document import Document
from app.schemas.common import PaginatedResponse, Response
from app.schemas.document import (
    DocumentBatchDeleteRequest,
    DocumentBatchDeleteResponse,
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


def _build_filters(
    project_id: Optional[uuid.UUID],
    status_filter: Optional[str],
    category: Optional[str],
    parse_status: Optional[str],
    q: Optional[str],
) -> List[ColumnElement[bool]]:
    """Shared filter set for the list and export views, so both stay in sync."""
    filters: List[ColumnElement[bool]] = []
    if project_id:
        filters.append(Document.project_id == project_id)
    if status_filter:
        filters.append(Document.status == status_filter)
    if category:
        filters.append(Document.category == category)
    if parse_status:
        filters.append(Document.parse_status == parse_status)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Document.original_filename.ilike(pattern),
                Document.title.ilike(pattern),
                Document.filename.ilike(pattern),
            )
        )
    return filters


async def _remove_document(document: Document, db: AsyncSession) -> None:
    """Delete a document row plus its stored file (chunks cascade)."""
    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)
    await db.delete(document)


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


@router.post("/delete-batch", response_model=Response[DocumentBatchDeleteResponse])
async def delete_batch(
    body: DocumentBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple documents (and their chunks + stored files) at once."""
    documents = (
        await db.execute(select(Document).where(Document.id.in_(body.document_ids)))
    ).scalars().all()

    for document in documents:
        await _remove_document(document, db)
    await db.flush()

    deleted = len(documents)
    total = len(body.document_ids)
    return Response(
        data=DocumentBatchDeleteResponse(
            total=total,
            deleted=deleted,
            not_found=total - deleted,
        ),
        message=f"Deleted {deleted}/{total} documents",
    )


# ---------------------------------------------------------------------------
# Export — must come before {document_id} routes
# ---------------------------------------------------------------------------

_EXPORT_COLUMNS = [
    ("id", "ID"),
    ("original_filename", "文件名"),
    ("title", "标题"),
    ("category", "分类"),
    ("content_type", "类型"),
    ("file_size", "大小(字节)"),
    ("status", "入库状态"),
    ("parse_status", "解析状态"),
    ("chunk_count", "分块数"),
    ("project_id", "项目ID"),
    ("created_at", "上传时间"),
]


@router.get("/export")
async def export_documents(
    project_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    parse_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, min_length=1, max_length=200),
    document_ids: Optional[List[uuid.UUID]] = Query(
        None, description="Export only these documents (overrides filters)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Export the 资料清单 as CSV — the current filter set, or an explicit selection.

    Metadata only: the manifest lets an admin audit what is in the knowledge
    base without shipping document contents out of the system.
    """
    query = select(Document).order_by(Document.created_at.desc())
    if document_ids:
        query = query.where(Document.id.in_(document_ids))
    else:
        for condition in _build_filters(project_id, status_filter, category, parse_status, q):
            query = query.where(condition)

    documents = (await db.execute(query)).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in _EXPORT_COLUMNS])
    for document in documents:
        row = []
        for field, _ in _EXPORT_COLUMNS:
            value = getattr(document, field, None)
            row.append("" if value is None else str(value))
        writer.writerow(row)

    # UTF-8 BOM so Excel on Windows detects the encoding instead of mojibake.
    payload = ("\ufeff" + buffer.getvalue()).encode("utf-8")
    return RawResponse(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="documents.csv"'},
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
    category: Optional[str] = Query(None, description="附件分类过滤"),
    parse_status: Optional[str] = Query(None, description="解析状态过滤"),
    q: Optional[str] = Query(None, min_length=1, max_length=200, description="文件名/标题搜索"),
    db: AsyncSession = Depends(get_db),
):
    """List documents with pagination and filters."""
    query = select(Document)
    count_query = select(func.count(Document.id))

    for condition in _build_filters(project_id, status_filter, category, parse_status, q):
        query = query.where(condition)
        count_query = count_query.where(condition)

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

    await _remove_document(document, db)
    return Response(message="Document deleted")


@router.post("/{document_id}/auto-tag", response_model=Response[dict])
async def auto_tag_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Auto-suggest category for a document using LLM."""
    from app.services.auto_tagger import suggest_tags

    doc = await db.get(Document, document_id)
    if not doc:
        raise NotFoundException("Document", str(document_id))
    # Use the first chunk as content sample
    from app.models.document import DocumentChunk

    chunks = (
        await db.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.document_id == document_id)
            .limit(3)
        )
    ).scalars().all()
    content = "\n".join(chunks) or doc.title or doc.original_filename
    result = await suggest_tags(
        db, "document", content, doc.title or doc.original_filename
    )
    return Response(data=result)
