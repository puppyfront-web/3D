"""Text chunking strategies for document processing."""

from typing import List, Optional


class TextChunker:
    """Split documents into chunks suitable for embedding and retrieval."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n\n",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def chunk_text(self, text: str) -> List[dict]:
        """Split text into overlapping chunks.

        Returns a list of dicts with keys:
            content, chunk_index, token_count
        """
        if not text or not text.strip():
            return []

        # Split on separator first
        segments = text.split(self.separator)
        chunks: List[dict] = []
        current_chunk = ""
        index = 0

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            # If adding this segment exceeds chunk size, save current and start new
            if len(current_chunk) + len(segment) + 2 > self.chunk_size and current_chunk:
                chunks.append(self._make_chunk(current_chunk, index))
                index += 1
                # Keep overlap from the end of the previous chunk
                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    current_chunk = current_chunk[-self.chunk_overlap:] + "\n\n" + segment
                else:
                    current_chunk = segment
            else:
                current_chunk = current_chunk + "\n\n" + segment if current_chunk else segment

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(self._make_chunk(current_chunk, index))

        return chunks

    def chunk_by_sentences(self, text: str, sentences_per_chunk: int = 5) -> List[dict]:
        """Split text into chunks by sentence count.

        Useful for smaller, more precise retrieval units.
        """
        if not text:
            return []

        # Simple sentence splitting
        sentences = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Split on sentence-ending punctuation
            parts = line.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n")
            for sentence in parts.split("\n"):
                sentence = sentence.strip()
                if sentence:
                    sentences.append(sentence)

        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            batch = sentences[i : i + sentences_per_chunk]
            chunks.append(
                self._make_chunk(" ".join(batch), len(chunks))
            )

        return chunks

    def chunk_by_pages(self, pages: List[str]) -> List[dict]:
        """Chunk text that is already split by page number.

        Each page becomes a chunk with page_number metadata.
        """
        chunks = []
        for page_num, page_text in enumerate(pages, start=1):
            if page_text and page_text.strip():
                chunks.append(
                    self._make_chunk(page_text, len(chunks), page_number=page_num)
                )
        return chunks

    @staticmethod
    def _make_chunk(
        content: str,
        index: int,
        page_number: Optional[int] = None,
    ) -> dict:
        """Create a chunk dict with metadata."""
        return {
            "content": content.strip(),
            "chunk_index": index,
            "token_count": len(content.split()),
            "page_number": page_number,
        }
