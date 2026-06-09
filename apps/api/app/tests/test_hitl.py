"""Tests for Human-in-the-Loop: sections_meta parsing, section status updates, export gate."""

import uuid

import pytest
import pytest_asyncio

from app.models.generation import GenerationOutput, GenerationTask


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def generation_task_with_output(db_session, sample_project_id):
    """Create a GenerationTask + GenerationOutput with sections_meta."""
    task = GenerationTask(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        type="proposal",
        status="completed",
        prompt_used="test prompt",
        model_used="mock",
    )
    db_session.add(task)
    await db_session.flush()

    output = GenerationOutput(
        id=uuid.uuid4(),
        task_id=task.id,
        content_type="text/markdown",
        content="## 1. 需求理解\n一些内容\n\n## 2. 企业解析摘要\n更多内容\n\n## 3. 项目背景\n背景",
        sections_meta=[
            {"id": str(uuid.uuid4()), "title": "需求理解", "order": 1, "status": "draft", "reviewed_by": None, "reviewed_at": None},
            {"id": str(uuid.uuid4()), "title": "企业解析摘要", "order": 2, "status": "draft", "reviewed_by": None, "reviewed_at": None},
            {"id": str(uuid.uuid4()), "title": "项目背景", "order": 3, "status": "draft", "reviewed_by": None, "reviewed_at": None},
        ],
    )
    db_session.add(output)
    await db_session.flush()
    return task, output


@pytest_asyncio.fixture
async def generation_output_no_meta(db_session, sample_project_id):
    """Create a GenerationOutput without sections_meta (legacy data)."""
    task = GenerationTask(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        type="proposal",
        status="completed",
    )
    db_session.add(task)
    await db_session.flush()

    output = GenerationOutput(
        id=uuid.uuid4(),
        task_id=task.id,
        content_type="text/markdown",
        content="Some legacy content without sections",
    )
    db_session.add(output)
    await db_session.flush()
    return task, output


# ── sections_meta parsing ─────────────────────────────────────────────


class TestParseSectionsMeta:
    """Test _parse_sections_meta static method."""

    def test_parse_10_chapters(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        markdown = """## 1. 需求理解
内容1

## 2. 企业解析摘要
内容2

## 3. 项目背景
内容3

## 4. 项目目标
内容4

## 5. 创意主题
内容5

## 6. 方案亮点
内容6

## 7. 视觉方向
内容7

## 8. 参考案例
内容8

## 9. 实施建议
内容9

## 10. 风险与待确认事项
内容10"""
        result = ProposalGenerationSkill._parse_sections_meta(markdown)
        assert len(result) == 10
        assert result[0]["title"] == "需求理解"
        assert result[0]["order"] == 1
        assert result[0]["status"] == "draft"
        assert result[9]["title"] == "风险与待确认事项"
        assert result[9]["order"] == 10

    def test_parse_empty_content(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        result = ProposalGenerationSkill._parse_sections_meta("")
        assert result == []

    def test_parse_no_headings(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        result = ProposalGenerationSkill._parse_sections_meta("Just some text\nno headings here")
        assert result == []

    def test_parse_partial_chapters(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        markdown = "## 1. 需求理解\nContent\n\n## 2. 项目背景\nMore"
        result = ProposalGenerationSkill._parse_sections_meta(markdown)
        assert len(result) == 2
        assert result[0]["order"] == 1
        assert result[1]["order"] == 2

    def test_parse_dot_format(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        markdown = "## 1. Title One\n\n## 2. Title Two"
        result = ProposalGenerationSkill._parse_sections_meta(markdown)
        assert len(result) == 2
        assert result[0]["title"] == "Title One"
        assert result[1]["title"] == "Title Two"

    def test_parse_space_format(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        markdown = "## 1  Title One\n\n## 2  Title Two"
        result = ProposalGenerationSkill._parse_sections_meta(markdown)
        assert len(result) == 2

    def test_each_section_has_uuid(self):
        from app.skills.builtins.proposal_generation import ProposalGenerationSkill

        markdown = "## 1. A\n## 2. B"
        result = ProposalGenerationSkill._parse_sections_meta(markdown)
        # Each id should be a valid UUID string
        for section in result:
            uuid.UUID(section["id"])  # Will raise if invalid


# ── Section status API ────────────────────────────────────────────────


class TestSectionStatusAPI:
    """Test PATCH /generations/outputs/{id}/sections/{order}/status."""

    @pytest.mark.asyncio
    async def test_approve_section(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/1/status",
            json={"status": "approved", "reviewed_by": "admin"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        meta = data["sections_meta"]
        section_1 = next(s for s in meta if s["order"] == 1)
        assert section_1["status"] == "approved"
        assert section_1["reviewed_by"] == "admin"
        assert section_1["reviewed_at"] is not None

    @pytest.mark.asyncio
    async def test_mark_review_section(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/2/status",
            json={"status": "review"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        section_2 = next(s for s in data["sections_meta"] if s["order"] == 2)
        assert section_2["status"] == "review"
        assert section_2["reviewed_by"] is None
        assert section_2["reviewed_at"] is None

    @pytest.mark.asyncio
    async def test_revert_to_draft(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        # First approve, then revert
        await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/1/status",
            json={"status": "approved", "reviewed_by": "admin"},
        )
        response = await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/1/status",
            json={"status": "draft"},
        )
        assert response.status_code == 200
        section_1 = next(s for s in response.json()["data"]["sections_meta"] if s["order"] == 1)
        assert section_1["status"] == "draft"
        assert section_1["reviewed_by"] is None
        assert section_1["reviewed_at"] is None

    @pytest.mark.asyncio
    async def test_section_order_out_of_range(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/99/status",
            json={"status": "approved"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_section_order_zero(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/0/status",
            json={"status": "approved"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_nonexistent_output(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.patch(
            f"/api/v1/generations/outputs/{fake_id}/sections/1/status",
            json={"status": "approved"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_status_value(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/1/status",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 422  # Validation error


# ── Output update API ─────────────────────────────────────────────────


class TestOutputUpdateAPI:
    """Test PUT /generations/outputs/{id}."""

    @pytest.mark.asyncio
    async def test_update_content(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.put(
            f"/api/v1/generations/outputs/{output.id}",
            json={"content": "## Updated content\nNew text here"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["content"] == "## Updated content\nNew text here"

    @pytest.mark.asyncio
    async def test_update_sections_meta(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        new_meta = [
            {"id": str(uuid.uuid4()), "title": "新章节", "order": 1, "status": "draft", "reviewed_by": None, "reviewed_at": None},
        ]
        response = await client.put(
            f"/api/v1/generations/outputs/{output.id}",
            json={"sections_meta": new_meta},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["sections_meta"]) == 1
        assert data["sections_meta"][0]["title"] == "新章节"

    @pytest.mark.asyncio
    async def test_update_nonexistent_output(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/v1/generations/outputs/{fake_id}",
            json={"content": "anything"},
        )
        assert response.status_code == 404


# ── Export gate ────────────────────────────────────────────────────────


class TestExportGate:
    """Test export eligibility checks."""

    @pytest.mark.asyncio
    async def test_export_blocked_when_unapproved(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.post(f"/api/v1/exports/word/{task.id}")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "blockers" in detail
        assert len(detail["blockers"]) == 3  # All 3 sections are draft

    @pytest.mark.asyncio
    async def test_export_blocked_partial_approval(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        # Approve only section 1
        await client.patch(
            f"/api/v1/generations/outputs/{output.id}/sections/1/status",
            json={"status": "approved", "reviewed_by": "admin"},
        )

        response = await client.post(f"/api/v1/exports/pdf/{task.id}")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert len(detail["blockers"]) == 2  # Sections 2 and 3 still draft

    @pytest.mark.asyncio
    async def test_export_allowed_when_all_approved(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        # Approve all 3 sections
        for order in range(1, 4):
            await client.patch(
                f"/api/v1/generations/outputs/{output.id}/sections/{order}/status",
                json={"status": "approved", "reviewed_by": "admin"},
            )

        response = await client.post(f"/api/v1/exports/word/{task.id}")
        # Should succeed (200) or fail with a non-403 error (e.g. missing library)
        # The key assertion: it must NOT be 403 (gate passed)
        if response.status_code == 403:
            pytest.fail("Export gate should have passed but returned 403")

    @pytest.mark.asyncio
    async def test_export_allowed_legacy_data(self, client, generation_output_no_meta):
        task, output = generation_output_no_meta

        # Legacy data (no sections_meta) should pass the gate
        response = await client.post(f"/api/v1/exports/word/{task.id}")
        # Gate should pass; may still fail for other reasons (no python-docx in test env)
        if response.status_code == 403:
            pytest.fail("Legacy data should pass export gate without sections_meta")

    @pytest.mark.asyncio
    async def test_pptx_export_gate(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.post(f"/api/v1/exports/pptx/{task.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_pdf_export_gate(self, client, generation_task_with_output):
        task, output = generation_task_with_output

        response = await client.post(f"/api/v1/exports/pdf/{task.id}")
        assert response.status_code == 403
