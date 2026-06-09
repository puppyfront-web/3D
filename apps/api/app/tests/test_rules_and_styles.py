"""Tests for Rules API — technical rules and quality rules, plus visual styles."""

import uuid

import pytest


# ── Technical Rules ────────────────────────────────────────────────────


class TestTechnicalRules:
    """Test technical rule CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_technical_rule(self, client):
        response = await client.post(
            "/api/v1/rules/technical",
            json={
                "name": "Screen Size Check",
                "category": "screen",
                "description": "Verify screen dimensions",
                "rule_text": "屏幕尺寸必须在2米以上",
                "severity": "warning",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Screen Size Check"
        assert data["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_list_technical_rules(self, client):
        response = await client.get("/api/v1/rules/technical")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_update_technical_rule(self, client):
        create_resp = await client.post(
            "/api/v1/rules/technical",
            json={"name": "Old Rule", "category": "test", "rule_text": "old text"},
        )
        rule_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/rules/technical/{rule_id}",
            json={"name": "Updated Rule", "severity": "error"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Rule"
        assert response.json()["data"]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_delete_technical_rule(self, client):
        create_resp = await client.post(
            "/api/v1/rules/technical",
            json={"name": "Delete Me", "category": "test", "rule_text": "text"},
        )
        rule_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/rules/technical/{rule_id}")
        assert response.status_code == 200


# ── Quality Rules ──────────────────────────────────────────────────────


class TestQualityRules:
    """Test quality rule CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_quality_rule(self, client):
        response = await client.post(
            "/api/v1/rules/quality",
            json={
                "name": "No Fabricated Cases",
                "category": "content",
                "description": "Ensure no fabricated case studies",
                "rule_text": "所有引用案例必须来自案例库",
                "weight": 0.8,
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "No Fabricated Cases"
        assert data["weight"] == 0.8

    @pytest.mark.asyncio
    async def test_list_quality_rules(self, client):
        response = await client.get("/api/v1/rules/quality")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_update_quality_rule(self, client):
        create_resp = await client.post(
            "/api/v1/rules/quality",
            json={"name": "Old", "category": "test", "rule_text": "old"},
        )
        rule_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/rules/quality/{rule_id}",
            json={"name": "Updated", "weight": 0.5},
        )
        assert response.status_code == 200
        assert response.json()["data"]["weight"] == 0.5

    @pytest.mark.asyncio
    async def test_delete_quality_rule(self, client):
        create_resp = await client.post(
            "/api/v1/rules/quality",
            json={"name": "Del", "category": "test", "rule_text": "text"},
        )
        rule_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/rules/quality/{rule_id}")
        assert response.status_code == 200


# ── Visual Styles ──────────────────────────────────────────────────────


class TestVisualStyles:
    """Test visual style CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_visual_style(self, client):
        response = await client.post(
            "/api/v1/visual-styles",
            json={
                "name": "Cyberpunk Tech",
                "description": "赛博朋克科技风格",
                "primary_color": "#00D4FF",
                "secondary_color": "#1E3A5F",
                "accent_color": "#FF00FF",
                "layout": "full-screen",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Cyberpunk Tech"
        assert data["primary_color"] == "#00D4FF"
        return data["id"]

    @pytest.mark.asyncio
    async def test_list_visual_styles(self, client):
        response = await client.get("/api/v1/visual-styles")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_get_visual_style(self, client):
        create_resp = await client.post(
            "/api/v1/visual-styles",
            json={"name": "Get Style", "primary_color": "#FF0000"},
        )
        style_id = create_resp.json()["data"]["id"]

        response = await client.get(f"/api/v1/visual-styles/{style_id}")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Get Style"

    @pytest.mark.asyncio
    async def test_update_visual_style(self, client):
        create_resp = await client.post(
            "/api/v1/visual-styles",
            json={"name": "Old Style", "primary_color": "#000000"},
        )
        style_id = create_resp.json()["data"]["id"]

        response = await client.put(
            f"/api/v1/visual-styles/{style_id}",
            json={"name": "New Style", "accent_color": "#00FF00"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "New Style"
        assert response.json()["data"]["accent_color"] == "#00FF00"

    @pytest.mark.asyncio
    async def test_delete_visual_style(self, client):
        create_resp = await client.post(
            "/api/v1/visual-styles",
            json={"name": "Delete Style", "primary_color": "#000000"},
        )
        style_id = create_resp.json()["data"]["id"]

        response = await client.delete(f"/api/v1/visual-styles/{style_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent_style(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/visual-styles/{fake_id}")
        assert response.status_code == 404
