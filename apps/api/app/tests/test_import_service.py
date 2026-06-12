"""Tests for ImportService — file parsing and validation logic."""
import json
import pytest
from sqlalchemy import select

from app.services.import_service import ImportService, ImportResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeUploadFile:
    """Minimal stand-in for fastapi.UploadFile."""

    def __init__(self, content: str, filename: str = "data.json"):
        self.content = content.encode("utf-8")
        self.filename = filename
        self._read = False

    async def read(self) -> bytes:
        return self.content


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_json_array_of_cases():
    """Parse JSON array of cases -> 2 items."""
    data = [
        {"title": "Case A", "client_name": "Client A"},
        {"title": "Case B", "client_name": "Client B"},
    ]
    f = FakeUploadFile(json.dumps(data), "cases.json")
    result = await ImportService.parse_file(f, "case")
    assert result.imported == 2
    assert result.failed == 0
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_parse_json_single_case():
    """Parse JSON single case object -> 1 item."""
    data = {"title": "Case A", "client_name": "Client A"}
    f = FakeUploadFile(json.dumps(data), "case.json")
    result = await ImportService.parse_file(f, "case")
    assert result.imported == 1
    assert result.failed == 0


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_csv_with_headers():
    """Parse CSV with headers -> items."""
    csv_text = "title,client_name,industry\nCase A,Client A,Tech\nCase B,Client B,Retail"
    f = FakeUploadFile(csv_text, "cases.csv")
    result = await ImportService.parse_file(f, "case")
    assert result.imported == 2
    assert result.items[0]["title"] == "Case A"
    assert result.items[1]["industry"] == "Retail"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_invalid_extension():
    """Unsupported extension -> error."""
    f = FakeUploadFile("{}", "cases.xml")
    result = await ImportService.parse_file(f, "case")
    assert result.failed == 1
    assert result.imported == 0
    assert "不支持的文件格式" in result.errors[0]


@pytest.mark.asyncio
async def test_parse_empty_file():
    """Empty file -> error."""
    f = FakeUploadFile("  ", "cases.json")
    result = await ImportService.parse_file(f, "case")
    assert result.failed == 1
    assert "文件内容为空" in result.errors[0]


@pytest.mark.asyncio
async def test_parse_malformed_json():
    """Malformed JSON -> error."""
    f = FakeUploadFile("{bad json}", "cases.json")
    result = await ImportService.parse_file(f, "case")
    assert result.failed == 1
    assert "文件解析失败" in result.errors[0]


# ---------------------------------------------------------------------------
# Text parsing — prompt templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_txt_prompt_template():
    """TXT file as prompt template -> extracts name, text, variables."""
    text = "My Template\nGenerate a {{style}} image with {{mood}} atmosphere"
    f = FakeUploadFile(text, "template.txt")
    result = await ImportService.parse_file(f, "prompt_template")
    assert result.imported == 1
    item = result.items[0]
    assert item["name"] == "My Template"
    assert "{{style}}" in item["template_text"]
    assert set(item["variables"]) == {"style", "mood"}
    assert item["category"] == "imported"


@pytest.mark.asyncio
async def test_parse_md_prompt_template():
    """MD file as prompt template -> extracts name and text."""
    text = "Scene Prompt\nCreate a {{scene}} with {{lighting}} lighting"
    f = FakeUploadFile(text, "prompt.md")
    result = await ImportService.parse_file(f, "prompt_template")
    assert result.imported == 1
    assert result.items[0]["name"] == "Scene Prompt"


# ---------------------------------------------------------------------------
# Text parsing — technical rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_txt_technical_rules():
    """TXT file as technical rules -> splits by blank lines."""
    text = "Rule A\nDescription for rule A\n\nRule B\nDescription for rule B"
    f = FakeUploadFile(text, "rules.txt")
    result = await ImportService.parse_file(f, "technical_rule")
    assert result.imported == 2
    assert result.items[0]["name"] == "Rule A"
    assert result.items[1]["name"] == "Rule B"
    assert result.items[0]["category"] == "imported"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_case_without_title():
    """Case without title -> validation error."""
    data = {"client_name": "Client A"}
    f = FakeUploadFile(json.dumps(data), "case.json")
    result = await ImportService.parse_file(f, "case")
    assert result.failed == 1
    assert result.imported == 0
    assert "title" in result.errors[0]


@pytest.mark.asyncio
async def test_validate_case_without_client_name():
    """Case without client_name -> validation error."""
    data = {"title": "Some Title"}
    f = FakeUploadFile(json.dumps(data), "case.json")
    result = await ImportService.parse_file(f, "case")
    assert result.failed == 1
    assert "client_name" in result.errors[0]


@pytest.mark.asyncio
async def test_validate_case_numeric_conversion():
    """Case with string numeric fields -> converted to proper types."""
    data = {"title": "Case", "client_name": "Client", "team_size": "5", "quality_score": "4.5"}
    f = FakeUploadFile(json.dumps(data), "case.json")
    result = await ImportService.parse_file(f, "case")
    assert result.imported == 1
    assert result.items[0]["team_size"] == 5
    assert result.items[0]["quality_score"] == 4.5


@pytest.mark.asyncio
async def test_validate_quality_rule_weight_conversion():
    """Quality rule with string weight -> converted to float."""
    data = {"name": "Rule", "rule_text": "Text", "weight": "2.5"}
    f = FakeUploadFile(json.dumps(data), "quality.json")
    result = await ImportService.parse_file(f, "quality_rule")
    assert result.imported == 1
    assert result.items[0]["weight"] == 2.5


@pytest.mark.asyncio
async def test_validate_sop_workflow_without_name():
    """SOP workflow without name -> validation error."""
    data = {"description": "Some description"}
    f = FakeUploadFile(json.dumps(data), "wf.json")
    result = await ImportService.parse_file(f, "sop_workflow")
    assert result.failed == 1
    assert "name" in result.errors[0]


@pytest.mark.asyncio
async def test_mixed_valid_and_invalid_items():
    """JSON array with some valid and some invalid items."""
    data = [
        {"title": "Valid Case", "client_name": "Client"},
        {"title": "Missing Client"},
        {"client_name": "Missing Title"},
    ]
    f = FakeUploadFile(json.dumps(data), "cases.json")
    result = await ImportService.parse_file(f, "case")
    assert result.imported == 1
    assert result.failed == 2
    assert len(result.items) == 1


# ---------------------------------------------------------------------------
# apply_items — conflict policy (skip / overwrite / rename)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_items_inserts_new(db_session):
    """No existing match -> insert, count imported."""
    applied = await ImportService.apply_items(
        db_session, "sop_workflow",
        [{"name": "Brand New", "description": "fresh"}],
        mode="skip",
    )
    assert applied.imported == 1
    assert applied.skipped == 0
    assert applied.updated == 0


@pytest.mark.asyncio
async def test_apply_items_skip_on_conflict(db_session):
    """Existing natural-key match + skip -> skipped, no duplicate, no change."""
    from app.models.workflow import SOPWorkflow

    db_session.add(SOPWorkflow(name="Dup", description="old"))
    await db_session.flush()

    applied = await ImportService.apply_items(
        db_session, "sop_workflow",
        [{"name": "Dup", "description": "new"}],
        mode="skip",
    )
    assert applied.skipped == 1
    assert applied.imported == 0

    rows = (await db_session.execute(select(SOPWorkflow))).scalars().all()
    assert len(rows) == 1  # no duplicate created
    assert rows[0].description == "old"  # unchanged


@pytest.mark.asyncio
async def test_apply_items_overwrite_on_conflict(db_session):
    """Existing match + overwrite -> updated, fields replaced."""
    from sqlalchemy import select

    from app.models.workflow import SOPWorkflow

    db_session.add(SOPWorkflow(name="Dup", description="old", version="1.0"))
    await db_session.flush()

    applied = await ImportService.apply_items(
        db_session, "sop_workflow",
        [{"name": "Dup", "description": "new", "version": "2.0"}],
        mode="overwrite",
    )
    assert applied.updated == 1
    assert applied.imported == 0

    rows = (await db_session.execute(select(SOPWorkflow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].description == "new"
    assert rows[0].version == "2.0"


@pytest.mark.asyncio
async def test_apply_items_rename_on_conflict(db_session):
    """Existing match + rename -> new copy with suffixed name."""
    from sqlalchemy import select

    from app.models.workflow import SOPWorkflow

    db_session.add(SOPWorkflow(name="Dup"))
    await db_session.flush()

    applied = await ImportService.apply_items(
        db_session, "sop_workflow", [{"name": "Dup"}], mode="rename",
    )
    assert applied.imported == 1

    names = sorted(r.name for r in (await db_session.execute(select(SOPWorkflow))).scalars().all())
    assert names == ["Dup", "Dup (副本)"]


@pytest.mark.asyncio
async def test_apply_items_case_natural_key_is_title_and_client(db_session, sample_project_id):
    """Case conflict matches on (title, client_name), not project_id."""
    from sqlalchemy import select

    from app.models.case import Case

    db_session.add(Case(project_id=sample_project_id, title="T", client_name="C"))
    await db_session.flush()

    # Same title+client -> skip; different client -> insert.
    applied = await ImportService.apply_items(
        db_session, "case",
        [
            {"project_id": sample_project_id, "title": "T", "client_name": "C"},
            {"project_id": sample_project_id, "title": "T", "client_name": "Other"},
        ],
        mode="skip",
    )
    assert applied.skipped == 1
    assert applied.imported == 1
    assert (await db_session.execute(select(Case))).scalars().all().__len__() == 2


def test_build_import_response_merges_counts():
    """Parse-level failures + apply counts merge into response kwargs."""
    parsed = ImportResult(failed=1, errors=["第 1 条: bad"])
    applied = ImportResult(imported=2, skipped=3, updated=4, failed=1, errors=["db err"])
    out = ImportService.build_import_response(parsed, applied, "工作流")
    assert out["imported"] == 2
    assert out["skipped"] == 3
    assert out["updated"] == 4
    assert out["failed"] == 2  # 1 parse + 1 apply
    assert out["errors"] == ["第 1 条: bad", "db err"]
    assert "工作流" in out["message"]
