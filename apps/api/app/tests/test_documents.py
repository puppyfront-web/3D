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
        assert data["original_filename"] == "test.txt"
        assert data["content_type"] == "text/plain"
        assert data["file_size"] == len(file_content)
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
        filenames = [d["original_filename"] for d in data["items"]]
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
        assert response.json()["data"]["original_filename"] == "get_test.txt"

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
            assert item["project_id"] == str(sample_project_id)

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/documents/{fake_id}")
        assert response.status_code == 404
