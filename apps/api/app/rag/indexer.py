"""Document indexing pipeline — parse, chunk, embed, and store."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.rag.chunker import TextChunker
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService, get_embedding_service


class DocumentIndexer:
    """Full document indexing pipeline."""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
    ):
        self._embedding_service = embedding_service
        self._chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._parser = DocumentParser()

    async def _get_embedding_service(
        self, db: AsyncSession
    ) -> EmbeddingService:
        """Resolve the embedding service, reading config from the database."""
        if self._embedding_service is None:
            self._embedding_service = await get_embedding_service(db=db)
        return self._embedding_service

    async def index_document(
        self,
        document_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """Index a single document: parse, chunk, embed, and persist.

        Returns the number of chunks created.
        """
        document = await db.get(Document, document_id)
        if not document:
            return 0

        # Parse the document
        text = await self._parser.parse(document.file_path, document.content_type)
        if not text:
            document.status = "error"
            document.chunk_count = 0
            return 0

        # Chunk the text
        raw_chunks = self._chunker.chunk_text(text)

        if not raw_chunks:
            document.status = "indexed"
            document.chunk_count = 0
            return 0

        # Generate embeddings (reads provider config from database)
        texts = [c["content"] for c in raw_chunks]
        svc = await self._get_embedding_service(db)
        embeddings = await svc.embed_texts(texts)

        # Persist chunks
        for i, raw in enumerate(raw_chunks):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                content=raw["content"],
                chunk_index=raw["chunk_index"],
                page_number=raw.get("page_number"),
                token_count=raw["token_count"],
                embedding=embeddings[i] if i < len(embeddings) else None,
            )
            db.add(chunk)

        # Update document status
        document.status = "indexed"
        document.chunk_count = len(raw_chunks)

        return len(raw_chunks)

    async def index_project_documents(
        self,
        project_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict:
        """Index all un-indexed documents in a project.

        Returns a summary dict with counts.
        """
        result = await db.execute(
            select(Document).where(
                Document.project_id == project_id,
                Document.status != "indexed",
            )
        )
        documents = result.scalars().all()

        summary = {"total": len(documents), "indexed": 0, "failed": 0, "total_chunks": 0}

        for doc in documents:
            try:
                chunk_count = await self.index_document(doc.id, db)
                summary["indexed"] += 1
                summary["total_chunks"] += chunk_count
            except Exception as e:
                doc.status = "error"
                summary["failed"] += 1

        return summary
