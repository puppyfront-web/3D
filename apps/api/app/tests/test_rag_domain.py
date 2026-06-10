"""Domain-specific RAG retrieval validation tests.

These tests verify that the RAG pipeline correctly retrieves relevant
3D display-wall industry cases and documents for typical queries.

Test data covers four scenarios defined in docs/RAG_SPEC.md Section 8.2:
1. 商业综合体裸眼3D → should hit commercial / naked-eye-3D cases
2. 汽车品牌发布 → should hit automotive / tech-style / launch cases
3. 户外LED大屏 → should hit outdoor / LED / advertising cases
4. Low-quality cases should NOT rank first
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.document import Document, DocumentChunk
from app.models.project import Company, Project
from app.models.retrieval import RetrievalLog
from app.models.user import Role, User
from app.rag.retriever import HybridRetriever

# Module-level flag so we only seed once per process
_SEEDED: bool = False


async def _ensure_seed_data(db: AsyncSession):
    """Insert industry test data (idempotent — skips if already seeded)."""
    global _SEEDED
    if _SEEDED:
        return

    existing = await db.execute(select(Role).where(Role.name == "rag_tester"))
    if existing.scalar_one_or_none() is not None:
        _SEEDED = True
        return

    role = Role(
        id=uuid.uuid4(),
        name="rag_tester",
        description="Role for RAG domain tests",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(role)
    await db.flush()

    user = User(
        id=uuid.uuid4(),
        email="rag-test@example.com",
        name="RAG Tester",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    company = Company(
        id=uuid.uuid4(),
        name="Test 商业地产集团",
        industry="商业地产",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(company)
    await db.flush()

    project = Project(
        id=uuid.uuid4(),
        name="Test 3D Wall Project",
        description="A test project for RAG validation",
        company_id=company.id,
        owner_id=user.id,
        status="draft",
        priority="medium",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.flush()

    cases_data = [
        {
            "title": "某商业综合体裸眼3D巨型LED幕墙项目",
            "client_name": "万象城商业综合体",
            "industry": "商业地产",
            "challenge": "商业综合体中庭需要建设裸眼3D LED幕墙，用于吸引客流和品牌展示，要求视觉冲击力强，适合商场环境",
            "solution": "采用弧面LED显示屏配合裸眼3D内容制作，利用建筑曲面实现沉浸式视觉效果，内容结合品牌IP形象",
            "results": "日均客流提升30%，社交媒体曝光量超500万次",
            "quality_score": 92.0,
        },
        {
            "title": "新能源汽车品牌发布会LED视觉方案",
            "client_name": "某新能源汽车品牌",
            "industry": "汽车",
            "challenge": "新能源汽车品牌年度发布会，需要科技感十足的LED视觉呈现，突出智能化和未来感",
            "solution": "采用多面LED拼接加地屏互动方案，结合实时渲染和XR技术，打造沉浸式发布会体验",
            "results": "发布会直播观看超1000万，品牌搜索指数提升200%",
            "quality_score": 88.0,
        },
        {
            "title": "城市地标户外LED广告大屏项目",
            "client_name": "某市文旅集团",
            "industry": "文旅",
            "challenge": "城市核心地标位置建设户外LED大屏，用于文旅宣传和商业广告，要求高亮度、防水防尘",
            "solution": "采用P6户外高亮LED模组，配备智能亮度调节和环境感知系统，支持远程内容管理",
            "results": "年广告收入超2000万，成为城市新地标",
            "quality_score": 85.0,
        },
        {
            "title": "低质量测试案例-不应优先返回",
            "client_name": "测试客户",
            "industry": "其他",
            "challenge": "这是一个低质量案例，用于测试排序逻辑",
            "solution": "无实际解决方案",
            "results": "无",
            "quality_score": 20.0,
        },
    ]

    for cd in cases_data:
        db.add(Case(
            id=uuid.uuid4(),
            project_id=project.id,
            title=cd["title"],
            client_name=cd["client_name"],
            industry=cd["industry"],
            challenge=cd["challenge"],
            solution=cd["solution"],
            results=cd["results"],
            quality_score=cd["quality_score"],
            is_published=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))

    doc = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        filename="3d-wall-knowledge.pdf",
        original_filename="3D展示幕墙技术知识库.pdf",
        content_type="application/pdf",
        file_size=1024,
        file_path="/test/3d-wall-knowledge.pdf",
        title="3D展示幕墙技术知识库",
        status="indexed",
        chunk_count=3,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    await db.flush()

    chunks_data = [
        "裸眼3D技术是当前LED展示幕墙领域的热门方向，通过特殊的内容制作技术和显示屏曲面设计，使观众无需佩戴3D眼镜即可感受到立体视觉效果。在商业综合体、城市地标、品牌旗舰店等场景中应用广泛。",
        "LED显示屏技术参数选择指南：户外大屏通常采用P6-P10像素间距，亮度要求5000-7500cd/m²，防护等级IP65以上。室内商显常用P1.5-P3间距，亮度800-1500cd/m²。选择时需考虑观看距离、环境光照和内容类型。",
        "品牌发布会LED视觉方案设计要点：需要结合品牌调性和产品特性，通过多屏联动、地幕互动、实时渲染等技术手段打造沉浸式体验。新能源汽车品牌通常采用科技蓝和极简风格。",
    ]

    for idx, text in enumerate(chunks_data):
        db.add(DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            content=text,
            chunk_index=idx,
            page_number=idx + 1,
            token_count=len(text.split()),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))

    await db.commit()
    _SEEDED = True


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_commercial_naked_eye_3d(db_session: AsyncSession):
    """Scenario 1: 商业综合体裸眼3D → should hit commercial / naked-eye-3D case."""
    await _ensure_seed_data(db_session)
    retriever = HybridRetriever()
    results = await retriever.search(
        query="商业综合体 裸眼3D",
        top_k=5,
        db=db_session,
    )

    assert len(results) > 0, "Expected at least one result for '商业综合体裸眼3D'"

    case_results = [r for r in results if r.source == "case"]
    assert len(case_results) > 0, "Expected at least one case result"

    top_case = case_results[0]
    content_lower = top_case.content.lower() + (top_case.title or "").lower()
    assert "商业综合体" in content_lower or "裸眼3d" in content_lower, (
        f"Top case should be about commercial naked-eye 3D, got: {top_case.title}"
    )


@pytest.mark.asyncio
async def test_retrieve_automotive_launch(db_session: AsyncSession):
    """Scenario 2: 汽车品牌发布 → should hit automotive / tech-style case."""
    await _ensure_seed_data(db_session)
    retriever = HybridRetriever()
    results = await retriever.search(
        query="汽车品牌发布会 LED视觉方案",
        top_k=5,
        db=db_session,
    )

    assert len(results) > 0, "Expected at least one result for '汽车品牌发布会'"

    case_results = [r for r in results if r.source == "case"]
    assert len(case_results) > 0, "Expected at least one case result"

    all_content = " ".join(r.content for r in case_results) + " ".join(
        r.title or "" for r in case_results
    )
    assert "汽车" in all_content or "新能源" in all_content, (
        "Should find automotive case in results"
    )


@pytest.mark.asyncio
async def test_retrieve_outdoor_led(db_session: AsyncSession):
    """Scenario 3: 户外LED大屏 → should hit outdoor / LED case."""
    await _ensure_seed_data(db_session)
    retriever = HybridRetriever()
    results = await retriever.search(
        query="户外LED大屏 广告",
        top_k=5,
        db=db_session,
    )

    assert len(results) > 0, "Expected at least one result for '户外LED大屏'"

    case_results = [r for r in results if r.source == "case"]
    assert len(case_results) > 0, "Expected at least one case result"

    all_content = " ".join(r.content for r in case_results) + " ".join(
        r.title or "" for r in case_results
    )
    assert "户外" in all_content or "LED" in all_content, (
        "Should find outdoor LED case in results"
    )


@pytest.mark.asyncio
async def test_low_quality_case_not_ranked_first(db_session: AsyncSession):
    """Scenario 4: Low-quality cases should NOT rank first."""
    await _ensure_seed_data(db_session)
    retriever = HybridRetriever()
    results = await retriever.search(
        query="商业综合体 裸眼3D",
        top_k=5,
        db=db_session,
    )

    assert len(results) > 0, "Expected at least one result"

    case_results = [r for r in results if r.source == "case"]
    if case_results:
        top_case = case_results[0]
        assert "低质量" not in (top_case.title or ""), (
            "Low-quality test case should not rank first"
        )
        assert top_case.score > 0.1, (
            f"Top case score should be meaningful, got {top_case.score}"
        )


@pytest.mark.asyncio
async def test_retrieval_log_written(db_session: AsyncSession):
    """Verify that retrieval_logs table is populated after search."""
    await _ensure_seed_data(db_session)

    retriever = HybridRetriever()
    await retriever.search(
        query="裸眼3D方案",
        top_k=3,
        db=db_session,
    )

    stmt = select(RetrievalLog).where(RetrievalLog.query.contains("裸眼3D"))
    result = await db_session.execute(stmt)
    logs = result.scalars().all()

    assert len(logs) > 0, "Expected at least one retrieval_log entry"
    log = logs[0]
    assert log.retrieval_type == "hybrid"
    assert log.results_count >= 0
    assert log.latency_ms is not None and log.latency_ms >= 0


@pytest.mark.asyncio
async def test_keyword_only_hits_chunks(db_session: AsyncSession):
    """Keyword-only mode should find document chunks by text match."""
    await _ensure_seed_data(db_session)
    retriever = HybridRetriever()
    results = await retriever.search(
        query="像素间距",
        top_k=5,
        retrieval_type="keyword",
        db=db_session,
    )

    chunk_results = [r for r in results if r.source == "chunk"]
    if chunk_results:
        assert any("像素间距" in r.content for r in chunk_results), (
            "Keyword search should find chunk mentioning '像素间距'"
        )
