"""Tests for Company Profiles API — CRUD and AI generation."""

import uuid

import pytest


class TestCompanyProfileCRUD:
    """Test company profile CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_profile(self, client, sample_company_id):
        response = await client.post(
            "/api/v1/company-profiles",
            json={
                "company_id": str(sample_company_id),
                "strengths": "Strong R&D",
                "weaknesses": "Small market share",
                "market_position": "Challenger",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["strengths"] == "Strong R&D"
        assert data["market_position"] == "Challenger"

    @pytest.mark.asyncio
    async def test_get_profile_by_company(self, client, sample_company_id):
        # Create first
        await client.post(
            "/api/v1/company-profiles",
            json={"company_id": str(sample_company_id), "strengths": "Test"},
        )

        response = await client.get(f"/api/v1/company-profiles/by-company/{sample_company_id}")
        assert response.status_code == 200
        assert response.json()["data"]["strengths"] == "Test"

    @pytest.mark.asyncio
    async def test_update_profile(self, client, sample_company_id):
        create_resp = await client.post(
            "/api/v1/company-profiles",
            json={"company_id": str(sample_company_id), "strengths": "Before"},
        )
        profile_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/company-profiles/{profile_id}",
            json={"strengths": "After update", "weaknesses": "None"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["strengths"] == "After update"
        assert data["weaknesses"] == "None"

    @pytest.mark.asyncio
    async def test_duplicate_profile_rejected(self, client, sample_company_id):
        # Create first
        await client.post(
            "/api/v1/company-profiles",
            json={"company_id": str(sample_company_id)},
        )
        # Try again — should 409
        response = await client.post(
            "/api/v1/company-profiles",
            json={"company_id": str(sample_company_id)},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_profile(self, client, sample_company_id):
        create_resp = await client.post(
            "/api/v1/company-profiles",
            json={"company_id": str(sample_company_id)},
        )
        profile_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/company-profiles/{profile_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_profiles(self, client, sample_company_id):
        await client.post(
            "/api/v1/company-profiles",
            json={"company_id": str(sample_company_id)},
        )
        response = await client.get("/api/v1/company-profiles")
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_profile(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/company-profiles/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_company_analysis(self, client, sample_company_id):
        """Test AI-powered company profile generation."""
        response = await client.post(
            "/api/v1/company-profiles/generate",
            json={
                "company_id": str(sample_company_id),
                "company_info": "华为，科技行业，主要做5G通信",
                "requirement_text": "裸眼3D展示方案",
            },
        )
        # Should succeed (200) — mock mode returns placeholder
        assert response.status_code == 200
        data = response.json()["data"]
        assert "id" in data
