"""Tests for Documents API — upload, list, index, delete."""

import io
import uuid

import pytest
import pytest_asyncio

from app.models.document import Document, DocumentChunk


class TestDocumentCRUD:
    """Test document CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, client):
        response = await client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_upload_document(self, client, sample_project_id):
        file_content = b"Test document content for upload"
        response = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["originalFilename"] == "test.txt"
        assert data["contentType"] == "text/plain"
        assert data["fileSize"] == len(file_content)
        return data["id"]

    @pytest.mark.asyncio
    async def test_list_documents_after_upload(self, client, sample_project_id):
        # Upload first
        await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("list_test.txt", io.BytesIO(b"content"), "text/plain")},
        )

        response = await client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        filenames = [d["originalFilename"] for d in data["items"]]
        assert "list_test.txt" in filenames

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, client, sample_project_id):
        upload_resp = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("get_test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        doc_id = upload_resp.json()["data"]["id"]

        response = await client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["data"]["originalFilename"] == "get_test.txt"

    @pytest.mark.asyncio
    async def test_delete_document(self, client, sample_project_id):
        upload_resp = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("delete_test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        doc_id = upload_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_filter_documents_by_project(self, client, sample_project_id, db_session):
        # Upload to project
        await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("proj_doc.txt", io.BytesIO(b"content"), "text/plain")},
        )

        # Filter by project
        response = await client.get(
            "/api/v1/documents",
            params={"project_id": str(sample_project_id)},
        )
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["projectId"] == str(sample_project_id)

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/documents/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_search_documents_by_filename(self, client, sample_project_id):
        await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("quarterly-report.txt", io.BytesIO(b"content"), "text/plain")},
        )
        await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(sample_project_id), "auto_index": "false"},
            files={"file": ("unrelated.txt", io.BytesIO(b"content"), "text/plain")},
        )

        response = await client.get("/api/v1/documents", params={"q": "quarterly"})
        assert response.status_code == 200
        filenames = [d["originalFilename"] for d in response.json()["items"]]
        assert filenames == ["quarterly-report.txt"]


class TestDocumentBatchOperations:
    """Batch delete + CSV manifest export."""

    async def _upload(self, client, project_id, filename: str) -> str:
        resp = await client.post(
            "/api/v1/documents/upload",
            params={"project_id": str(project_id), "auto_index": "false"},
            files={"file": (filename, io.BytesIO(b"content"), "text/plain")},
        )
        assert resp.status_code == 201
        return resp.json()["data"]["id"]

    @pytest.mark.asyncio
    async def test_delete_batch_removes_selected_documents(self, client, sample_project_id):
        keep_id = await self._upload(client, sample_project_id, "keep.txt")
        drop_ids = [
            await self._upload(client, sample_project_id, "drop-a.txt"),
            await self._upload(client, sample_project_id, "drop-b.txt"),
        ]

        response = await client.post(
            "/api/v1/documents/delete-batch",
            json={"document_ids": drop_ids},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 2
        assert data["deleted"] == 2
        assert data["notFound"] == 0

        remaining = await client.get("/api/v1/documents")
        remaining_ids = [d["id"] for d in remaining.json()["items"]]
        assert keep_id in remaining_ids
        for dropped in drop_ids:
            assert dropped not in remaining_ids

    @pytest.mark.asyncio
    async def test_delete_batch_reports_missing_ids(self, client, sample_project_id):
        doc_id = await self._upload(client, sample_project_id, "present.txt")

        response = await client.post(
            "/api/v1/documents/delete-batch",
            json={"document_ids": [doc_id, str(uuid.uuid4())]},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["deleted"] == 1
        assert data["notFound"] == 1

    @pytest.mark.asyncio
    async def test_delete_batch_rejects_empty_selection(self, client):
        response = await client.post(
            "/api/v1/documents/delete-batch", json={"document_ids": []}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_export_returns_csv_manifest(self, client, sample_project_id):
        await self._upload(client, sample_project_id, "exported.txt")

        response = await client.get("/api/v1/documents/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "documents.csv" in response.headers["content-disposition"]

        body = response.content.decode("utf-8")
        assert body.startswith("\ufeff")
        assert "文件名" in body
        assert "exported.txt" in body

    @pytest.mark.asyncio
    async def test_export_honours_explicit_selection(self, client, sample_project_id):
        wanted_id = await self._upload(client, sample_project_id, "wanted.txt")
        await self._upload(client, sample_project_id, "skipped.txt")

        response = await client.get(
            "/api/v1/documents/export", params={"document_ids": [wanted_id]}
        )
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        assert "wanted.txt" in body
        assert "skipped.txt" not in body
