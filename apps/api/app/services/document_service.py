"""Document service — orchestrates upload, indexing, and status management."""

import logging
import os
import uuid
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.rag.indexer import DocumentIndexer

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".txt", ".md"}


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
        # Validate
        original_filename = file.filename or "unnamed"
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # Save to disk
        stored_name = f"{uuid.uuid4().hex}{ext}"
        storage_dir = os.path.abspath(self._storage_path)
        os.makedirs(storage_dir, exist_ok=True)
        file_path = os.path.join(storage_dir, stored_name)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

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

    async def index_document(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """Index (or re-index) a single document.

        For re-indexing: deletes existing DocumentChunk rows first.
        Returns chunk count created.
        """
        document = await db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        # Delete existing chunks for clean re-index
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await db.flush()

        return await self._run_indexer(document_id, db)

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
