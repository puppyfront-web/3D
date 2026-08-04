"""Tests for document parser enhancements: XLSX/CSV, extension fallback,
DOC/PPT rejection, upload size limit, and magic-bytes mismatch cleanup.

These cover the four compat-fix workstreams:
  1. Excel/CSV support (parser + allowlist)
  2. DOC/PPT removal from allowlist
  3. Upload size limit (50 MB default)
  4. Magic-bytes validation + orphan cleanup on mismatch
"""

import csv
import io
import os
import tempfile

import pytest
import pytest_asyncio

from app.services.document_parser import DocumentParser
from app.services.document_service import ALLOWED_EXTENSIONS
from app.services.file_type_validator import validate_real_type


# ─── XLSX / CSV parsing ─────────────────────────────────────────────


class TestXlsxParsing:
    """Verify XLSX parser produces structured text from a real workbook."""

    def _make_xlsx(self, path: str) -> None:
        """Build a tiny real .xlsx so the parser has actual content to read."""
        from openpyxl import Workbook
        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Sheet1"
        ws1.append(["客户", "行业", "金额"])
        ws1.append(["A 公司", "3D 幕墙", 100000])
        ws2 = wb.create_sheet("Sheet2")
        ws2.append(["备注"])
        ws2.append(["test row"])
        wb.save(path)

    @pytest.mark.asyncio
    async def test_parse_xlsx_extracts_all_sheets(self, tmp_path):
        path = str(tmp_path / "sample.xlsx")
        self._make_xlsx(path)

        text = await DocumentParser.parse(path, "")

        assert "[Sheet: Sheet1]" in text
        assert "[Sheet: Sheet2]" in text
        assert "客户" in text
        assert "A 公司" in text
        assert "100000" in text
        assert "test row" in text

    @pytest.mark.asyncio
    async def test_parse_xlsx_via_content_type(self, tmp_path):
        """content_type path should resolve to the same parser."""
        path = str(tmp_path / "via_ct.xlsx")
        self._make_xlsx(path)
        text = await DocumentParser.parse(
            path,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert "客户" in text


class TestCsvParsing:
    @pytest.mark.asyncio
    async def test_parse_csv_utf8(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("name,value\n中文,1\nEnglish,2\n", encoding="utf-8")

        text = await DocumentParser.parse(str(path), "text/csv")
        assert "name" in text
        assert "中文" in text
        assert "English" in text

    @pytest.mark.asyncio
    async def test_parse_csv_fallback_ext(self, tmp_path):
        """Empty content_type should still resolve via .csv extension."""
        path = tmp_path / "fallback.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")

        text = await DocumentParser.parse(str(path), "")
        assert "a" in text and "1" in text


# ─── Extension fallback ─────────────────────────────────────────────


class TestExtensionFallback:
    """When content_type is empty/unknown, parser must pick by extension."""

    @pytest.mark.asyncio
    async def test_pdf_fallback_by_ext(self, tmp_path):
        path = tmp_path / "weird.pdf"
        # Build a real 1-page PDF so fitz can save it. We only assert the
        # dispatcher chose the PDF branch (no exception), not the OCR path
        # (which depends on optional libs).
        try:
            import fitz  # noqa: F401
        except ImportError:
            pytest.skip("PyMuPDF not installed")
        doc = fitz.open()
        doc.new_page()
        doc.save(str(path))
        doc.close()

        text = await DocumentParser.parse(str(path), "")
        # No exception + returns a string = dispatcher worked.
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_unknown_content_type_uses_extension(self, tmp_path):
        path = tmp_path / "octet.txt"
        path.write_text("hello world", encoding="utf-8")

        text = await DocumentParser.parse(str(path), "application/octet-stream")
        assert text == "hello world"


# ─── Allowlist: DOC/PPT removed, XLSX/CSV added ─────────────────────


class TestAllowlist:
    def test_doc_ppt_removed_from_knowledge_base(self):
        assert ".doc" not in ALLOWED_EXTENSIONS
        assert ".ppt" not in ALLOWED_EXTENSIONS

    def test_xlsx_xls_csv_added(self):
        assert ".xlsx" in ALLOWED_EXTENSIONS
        assert ".xls" in ALLOWED_EXTENSIONS
        assert ".csv" in ALLOWED_EXTENSIONS

    def test_core_formats_preserved(self):
        for ext in (".pdf", ".pptx", ".docx", ".txt", ".md"):
            assert ext in ALLOWED_EXTENSIONS


# ─── Upload size limit ──────────────────────────────────────────────


class TestUploadSizeLimit:
    """The 50 MB cap is enforced in the service layer before disk write.

    We test the constant + a synthetic oversized buffer via the API endpoint
    (see test_upload_too_large below). Unit-level: verify settings exposes it.
    """

    def test_max_upload_size_configured(self):
        from app.core.config import settings
        assert settings.max_upload_size == 50 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_upload_too_large_rejected(self, client, sample_project_id):
        # Build a payload larger than the limit. Patch the limit down so the
        # test doesn't allocate 50 MB of memory.
        from app.core.config import settings
        original = settings.max_upload_size
        settings.max_upload_size = 100  # 100 bytes
        try:
            big = b"x" * 500
            response = await client.post(
                "/api/v1/documents/upload",
                params={"project_id": str(sample_project_id), "auto_index": "false"},
                files={"file": ("big.txt", io.BytesIO(big), "text/plain")},
            )
            assert response.status_code == 400
            assert "过大" in response.json()["detail"]
        finally:
            settings.max_upload_size = original


# ─── Magic bytes mismatch + cleanup ─────────────────────────────────


class TestMagicValidation:
    def test_validate_real_type_passes_for_real_text(self, tmp_path):
        path = tmp_path / "real.txt"
        path.write_text("hello", encoding="utf-8")
        # Either libmagic is installed and returns text/plain (pass), or it's
        # absent and we fail-open (pass). Either way → True.
        assert validate_real_type(str(path), ".txt") is True

    def test_validate_real_type_detects_spoofed_pdf(self, tmp_path):
        """A .pdf that's actually plain text should be flagged — but only if
        libmagic is actually available. When it isn't, we fail open (True)."""
        path = tmp_path / "fake.pdf"
        path.write_text("not really a pdf", encoding="utf-8")
        try:
            import magic  # noqa: F401
        except ImportError:
            pytest.skip("python-magic not installed — fail-open path covered elsewhere")
        # libmagic present: should detect the mismatch.
        assert validate_real_type(str(path), ".pdf") is False

    @pytest.mark.asyncio
    async def test_spoofed_upload_rejected_and_file_cleaned(
        self, client, sample_project_id, tmp_path, monkeypatch
    ):
        """Upload a .pdf whose bytes are plain text. Backend must 400 AND
        remove the saved file so no orphan remains on disk."""
        try:
            import magic  # noqa: F401
        except ImportError:
            pytest.skip("python-magic not installed — cannot verify spoof detection")

        storage_before = set(os.listdir(tmp_path)) if os.path.isdir(tmp_path) else set()
        response = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("spoof.pdf", io.BytesIO(b"plain text not pdf"), "application/pdf")},
        )
        assert response.status_code == 400
        assert "不一致" in response.json()["detail"]
        # No new file should linger in the storage dir matching this upload.
        storage_after = set(os.listdir(tmp_path)) if os.path.isdir(tmp_path) else set()
        assert storage_after == storage_before


# ─── DOC/PPT rejection via API ──────────────────────────────────────


class TestDocPptRejection:
    @pytest.mark.asyncio
    async def test_doc_rejected(self, client, sample_project_id):
        response = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("legacy.doc", io.BytesIO(b"\xd0\xcf\x11\xe0"), "application/msword")},
        )
        assert response.status_code == 400
        assert ".doc" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_ppt_rejected(self, client, sample_project_id):
        response = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("legacy.ppt", io.BytesIO(b"\xd0\xcf\x11\xe0"), "application/vnd.ms-powerpoint")},
        )
        assert response.status_code == 400
        assert ".ppt" in response.json()["detail"]


# ─── OCR fallback (degrades gracefully when paddleocr absent) ───────


class TestOCRFallback:
    @pytest.mark.asyncio
    async def test_ocr_service_no_crash_without_paddle(self):
        """OCRService.extract_text must return "" — never raise — when
        paddleocr isn't installed. PDF parsing relies on this."""
        from app.services.ocr_service import OCRService
        # Force a fresh instance so we don't pick up a cached engine from
        # another test.
        OCRService._instance = None
        OCRService._engine = None
        OCRService._engine_unavailable = False

        # Write a tiny file so the path exists even though OCR will no-op.
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            path = f.name
        try:
            result = await OCRService().extract_text(path)
            assert result == ""
        finally:
            os.unlink(path)
