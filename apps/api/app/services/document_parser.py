"""Document parsing service for PDF, PPTX, DOCX, XLSX, CSV, TXT formats.

Dispatch is two-tiered:
  1. Primary: by the HTTP `content_type` (most reliable when the client sets it).
  2. Fallback: by file extension. Browsers frequently send `application/octet-stream`
     or leave content_type empty for office/spreadsheet formats, so extension
     fallback is required for XLSX/CSV in practice.

Every parser is import-tolerant: if its native library is not installed, it
returns a placeholder string instead of raising. This keeps uploads working
in minimal deployments — the indexer will mark the document as `error` when
the placeholder yields no real chunks (see rag/indexer.py).
"""

import csv
import os
from typing import Awaitable, Callable, Dict

# Threshold below which a PDF is suspected to be a scanned image (no text layer).
# Below it, we hand the file to OCR as a fallback. Tuned for typical CJK PDFs
# where a real text layer yields hundreds of characters per page.
_SCANNED_PDF_MIN_CHARS = 50


class DocumentParser:
    """Parse uploaded documents into plain text content."""

    @staticmethod
    async def parse(file_path: str, content_type: str) -> str:
        """Parse a document file and return its text content.

        Dispatches to the appropriate parser based on content type, with
        extension-based fallback when content_type is unknown.
        """
        if not os.path.exists(file_path):
            return ""

        parser = DocumentParser._resolve_parser(content_type, file_path)
        return await parser(file_path)

    @staticmethod
    def _resolve_parser(content_type: str, file_path: str) -> Callable[[str], Awaitable[str]]:
        """Pick a parser by content_type, falling back to file extension.

        Browsers often send empty / octet-stream content_type for office docs,
        so extension fallback is mandatory for XLSX/CSV and helps PDF too.
        """
        parsers: Dict[str, Callable[[str], Awaitable[str]]] = {
            "application/pdf": DocumentParser._parse_pdf,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": DocumentParser._parse_pptx,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentParser._parse_docx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DocumentParser._parse_xlsx,
            "application/vnd.ms-excel": DocumentParser._parse_xlsx,
            "text/csv": DocumentParser._parse_csv,
            "text/plain": DocumentParser._parse_text,
            "text/markdown": DocumentParser._parse_text,
        }

        if content_type in parsers:
            return parsers[content_type]

        # Extension fallback — only used when content_type was unknown/empty.
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        ext_parsers: Dict[str, Callable[[str], Awaitable[str]]] = {
            ".pdf": DocumentParser._parse_pdf,
            ".pptx": DocumentParser._parse_pptx,
            ".docx": DocumentParser._parse_docx,
            ".xlsx": DocumentParser._parse_xlsx,
            ".xls": DocumentParser._parse_xlsx,
            ".csv": DocumentParser._parse_csv,
            ".txt": DocumentParser._parse_text,
            ".md": DocumentParser._parse_text,
        }
        return ext_parsers.get(ext, DocumentParser._parse_text)

    # NOTE: This class previously had an `extract_chunks` method for naive
    # overlapping chunking. It was unused — the only chunker in the pipeline
    # is `app.rag.chunker.TextChunker`, invoked by the indexer
    # (app/rag/indexer.py). Text chunking lives there, not here, so the parser
    # stays focused on format → plain-text extraction.

    @staticmethod
    async def _parse_pdf(file_path: str) -> str:
        """Extract text from a PDF file.

        Falls back to OCR when PyMuPDF returns very little text — a strong
        signal the PDF is a scanned image without a text layer. OCR failure
        is non-fatal: we return whatever PyMuPDF managed to extract.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            # Fallback: return filename-based placeholder
            return f"[PDF content from {os.path.basename(file_path)}]"

        text_parts = []
        doc = fitz.open(file_path)
        try:
            for page in doc:
                text_parts.append(page.get_text())
        finally:
            doc.close()
        text = "\n\n".join(text_parts)

        # Scanned-PDF heuristic → OCR fallback.
        if len(text.strip()) < _SCANNED_PDF_MIN_CHARS:
            ocr_text = await DocumentParser._ocr_fallback(file_path)
            if ocr_text.strip():
                return ocr_text

        return text

    @staticmethod
    async def _ocr_fallback(file_path: str) -> str:
        """Run OCR on a file, returning "" on any failure or if disabled.

        Isolated so PDF parsing never breaks when OCR is unavailable.
        """
        try:
            from app.services.ocr_service import OCRService
            return await OCRService().extract_text(file_path)
        except Exception:
            return ""

    @staticmethod
    async def _parse_pptx(file_path: str) -> str:
        """Extract text from a PowerPoint file."""
        try:
            from pptx import Presentation
        except ImportError:
            return f"[PPTX content from {os.path.basename(file_path)}]"

        text_parts = []
        prs = Presentation(file_path)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text_parts.append(paragraph.text)
        return "\n".join(text_parts)

    @staticmethod
    async def _parse_docx(file_path: str) -> str:
        """Extract text from a Word document."""
        try:
            from docx import Document
        except ImportError:
            return f"[DOCX content from {os.path.basename(file_path)}]"

        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs]
        return "\n\n".join(paragraphs)

    @staticmethod
    async def _parse_xlsx(file_path: str) -> str:
        """Extract text from an Excel workbook.

        Each sheet becomes a section headed by `[Sheet: name]`; rows are
        tab-joined so the chunker sees one row per logical line. Empty cells
        are skipped to keep noise out of embeddings.
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            return f"[XLSX content from {os.path.basename(file_path)}]"

        parts: list[str] = []
        wb = load_workbook(file_path, read_only=True, data_only=True)
        try:
            for sheet in wb.worksheets:
                parts.append(f"[Sheet: {sheet.title}]")
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c is not None]
                    if cells:
                        parts.append("\t".join(cells))
        finally:
            wb.close()
        return "\n".join(parts)

    @staticmethod
    async def _parse_csv(file_path: str) -> str:
        """Read a CSV file as plain text (one row per line)."""
        rows: list[str] = []
        # Try utf-8 first, fall back to gbk — common for CN-exported CSVs.
        for encoding in ("utf-8", "gbk"):
            try:
                with open(file_path, "r", encoding=encoding, newline="") as f:
                    reader = csv.reader(f)
                    rows = ["\t".join(r) for r in reader]
                break
            except UnicodeDecodeError:
                continue
        return "\n".join(rows)

    @staticmethod
    async def _parse_text(file_path: str) -> str:
        """Read a plain text or markdown file."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


def get_document_parser() -> DocumentParser:
    """Factory function — returns a DocumentParser instance."""
    return DocumentParser()
