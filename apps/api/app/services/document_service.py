"""Document service — orchestrates upload, indexing, and status management."""

import logging
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.rag.indexer import DocumentIndexer
from app.services.file_type_validator import validate_real_type

logger = logging.getLogger(__name__)

# Knowledge-base documents (RAG-indexed).
# NOTE: legacy .doc/.ppt (binary Office formats) are intentionally NOT supported —
# we have no parser for them and they would index as gibberish. Users must
# convert to .docx/.pptx. XLSX/CSV are added for tabular reference material.
ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md", ".xlsx", ".xls", ".csv"}


class DocumentService:
    """Orchestrates document upload, indexing, and status management."""

    def __init__(self, storage_path: str = "storage"):
        self._storage_path = storage_path

    async def upload_and_index(
        self,
        file: UploadFile,
        db: AsyncSession,
        project_id: Optional[uuid.UUID] = None,
        auto_index: bool = True,
    ) -> Document:
        """Upload a file and optionally auto-index it.

        1. Validate file extension
        2. Save file to storage directory
        3. Create Document DB record (status='uploaded')
        4. If auto_index=True, run DocumentIndexer
        5. Return the Document with updated status
        """
        # Validate extension
        original_filename = file.filename or "unnamed"
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"不支持的文件类型 '{ext}'，允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # Read content and enforce size limit before touching disk.
        content = await file.read()
        if len(content) > settings.max_upload_size:
            raise ValueError(
                f"文件过大：{len(content)} 字节，上限 {settings.max_upload_size} 字节"
            )

        # Save to disk
        stored_name = f"{uuid.uuid4().hex}{ext}"
        storage_dir = os.path.abspath(self._storage_path)
        os.makedirs(storage_dir, exist_ok=True)
        file_path = os.path.join(storage_dir, stored_name)

        with open(file_path, "wb") as f:
            f.write(content)

        # Defense-in-depth: sniff real MIME via libmagic and reject mismatches.
        # Cleanup the saved file on failure so we never leave orphaned bytes.
        if not validate_real_type(file_path, ext):
            try:
                os.remove(file_path)
            except OSError:
                pass
            raise ValueError(
                f"文件内容与扩展名 '{ext}' 不一致，疑似伪造文件类型"
            )

        # Create DB record
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

        # Auto-index
        if auto_index:
            try:
                chunk_count = await self._run_indexer(document.id, db)
                await db.refresh(document)
                logger.info(
                    "Auto-indexed document %s: %d chunks",
                    document.id,
                    chunk_count,
                )
            except Exception as e:
                logger.error("Auto-index failed for document %s: %s", document.id, e)
                document.status = "error"
                await db.flush()

        return document

    async def import_file_from_path(
        self,
        source_path: str,
        *,
        original_filename: str,
        db: AsyncSession,
        project_id: Optional[uuid.UUID] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        auto_index: bool = True,
    ) -> Document:
        """Copy a file from disk into storage and optionally index (Knowledge Pack)."""
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"不支持的文件类型 '{ext}'，允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        with open(source_path, "rb") as src:
            content = src.read()
        if len(content) > settings.max_upload_size:
            raise ValueError(
                f"文件过大：{len(content)} 字节，上限 {settings.max_upload_size} 字节"
            )

        stored_name = f"{uuid.uuid4().hex}{ext}"
        storage_dir = os.path.abspath(self._storage_path)
        os.makedirs(storage_dir, exist_ok=True)
        file_path = os.path.join(storage_dir, stored_name)
        shutil.copy2(source_path, file_path)

        if not validate_real_type(file_path, ext):
            try:
                os.remove(file_path)
            except OSError:
                pass
            raise ValueError(f"文件内容与扩展名 '{ext}' 不一致")

        document = Document(
            project_id=project_id,
            filename=stored_name,
            original_filename=original_filename,
            content_type="application/octet-stream",
            file_size=len(content),
            file_path=file_path,
            title=title or original_filename,
            category=category,
            status="uploaded",
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)

        if auto_index:
            try:
                await self._run_indexer(document.id, db)
                await db.refresh(document)
            except Exception as e:
                logger.error("Pack auto-index failed for %s: %s", document.id, e)
                document.status = "error"
                document.parse_status = "parse_failed"
                await db.flush()

        return document

    async def index_document(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """Index (or re-index) a single document.

        For re-indexing: deletes existing DocumentChunk rows first.
        Returns chunk count created. Mirrors the parse lifecycle into
        ``parse_status`` so the workspace attachment tray can show a 6-state
        badge (uploaded / parsing / parsed / parse_failed / classified /
        pending_confirm) independently of the coarse indexer ``status``.
        """
        document = await db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        # Mark parsing in progress (visible to a polling tray).
        document.parse_status = "parsing"
        await db.flush()

        # Delete existing chunks for clean re-index
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await db.flush()

        try:
            chunk_count = await self._run_indexer(document_id, db)
            # The indexer sets document.status; mirror it into parse_status.
            doc = await db.get(Document, document_id)
            if doc is not None:
                doc.parse_status = "parsed" if doc.status == "indexed" else "parse_failed"
                await db.flush()
            return chunk_count
        except Exception:
            doc = await db.get(Document, document_id)
            if doc is not None:
                doc.parse_status = "parse_failed"
                doc.status = "error"
                await db.flush()
            raise

    async def index_batch(
        self,
        document_ids: List[uuid.UUID],
        db: AsyncSession,
    ) -> dict:
        """Index multiple documents by ID.

        Returns summary: {total, indexed, failed, total_chunks}.
        """
        summary = {
            "total": len(document_ids),
            "indexed": 0,
            "failed": 0,
            "total_chunks": 0,
        }

        for doc_id in document_ids:
            try:
                chunk_count = await self.index_document(doc_id, db)
                summary["indexed"] += 1
                summary["total_chunks"] += chunk_count
            except Exception as e:
                logger.error("Batch index failed for %s: %s", doc_id, e)
                summary["failed"] += 1

        return summary

    async def index_project_documents(
        self,
        project_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict:
        """Index all un-indexed documents in a project.

        Delegates to DocumentIndexer.index_project_documents().
        """
        indexer = DocumentIndexer()
        return await indexer.index_project_documents(project_id, db)

    async def index_all_unindexed(
        self,
        db: AsyncSession,
    ) -> dict:
        """Index all documents with status != 'indexed' across all projects."""
        result = await db.execute(
            select(Document).where(Document.status != "indexed")
        )
        documents = result.scalars().all()

        summary = {
            "total": len(documents),
            "indexed": 0,
            "failed": 0,
            "total_chunks": 0,
        }

        for doc in documents:
            try:
                # Delete old chunks if any
                await db.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.document_id == doc.id
                    )
                )
                await db.flush()

                chunk_count = await self._run_indexer(doc.id, db)
                summary["indexed"] += 1
                summary["total_chunks"] += chunk_count
            except Exception as e:
                logger.error("Index failed for %s: %s", doc.id, e)
                doc.status = "error"
                summary["failed"] += 1

        return summary

    async def _run_indexer(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """Run the DocumentIndexer on a single document."""
        indexer = DocumentIndexer()
        return await indexer.index_document(document_id, db)
