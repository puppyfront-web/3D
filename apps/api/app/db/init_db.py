"""Database initialization with seed data."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory, engine
from app.models import (
    Role,
    Skill,
    SOPWorkflow,
    User,
)
from app.db.base import Base


async def create_tables() -> None:
    """Create all tables and pgvector indexes (used during development)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create HNSW index for vector similarity search (PostgreSQL only)
        try:
            await conn.execute(
                __import__("sqlalchemy").text(
                    "CREATE INDEX IF NOT EXISTS idx_chunks_embedding "
                    "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
        except Exception:
            pass  # Not PostgreSQL or pgvector not available


async def seed_database() -> None:
    """Insert essential seed data when the database is empty.

    Only system-required data is seeded here:
    - Roles & Users (auth)
    - Skills (SkillRuntime)
    - SOP Workflows (two-layer architecture: base + industry extension)
    - Prompt Templates (industry-specific supplementary instructions)

    All other data (companies, projects, cases, documents, etc.) should be
    created through the application UI or API.
    """
    async with async_session_factory() as session:
        # Check if data already exists
        from sqlalchemy import select
        existing = await session.execute(select(User).limit(1))
        if existing.scalar_one_or_none():
            return

        now = datetime.now(timezone.utc)

        # ── Roles ──
        admin_role = Role(
            id=uuid.uuid4(),
            name="admin",
            description="System administrator with full access",
            created_at=now,
            updated_at=now,
        )
        user_role = Role(
            id=uuid.uuid4(),
            name="user",
            description="Standard user with project access",
            created_at=now,
            updated_at=now,
        )
        viewer_role = Role(
            id=uuid.uuid4(),
            name="viewer",
            description="Read-only access to projects",
            created_at=now,
            updated_at=now,
        )
        session.add_all([admin_role, user_role, viewer_role])
        await session.flush()

        # ── Users ──
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@3dwall.com",
            name="System Admin",
            role_id=admin_role.id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        demo_user = User(
            id=uuid.uuid4(),
            email="demo@3dwall.com",
            name="Demo User",
            role_id=user_role.id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([admin_user, demo_user])
        await session.flush()

        # ── Prompt Templates ──
        # These provide supplementary admin-configurable instructions.
        # The framework structure (六看, OUTPUT_SCHEMA, etc.) is always in the
        # skill's _default_prompt() as the base. These templates are APPENDED
        # as extra guidance, not replacing the default.
        from app.models import PromptTemplate

        pt_analysis = PromptTemplate(
            id=uuid.uuid4(),
            name="企业分析补充指令",
            description="企业解析 Skill 的补充分析指令，管理员可自定义行业侧重点",
            category="analysis",
            template_text="""请额外关注以下维度：
- 企业在3D显示/LED/数字视觉产业链中的角色定位
- 企业数字化和沉浸式体验相关投入
- 品牌视觉基因和传播调性
- 是否有裸眼3D、XR、数字孪生等技术布局

六看各方向分析深度建议：
- 向后看：重点挖掘品牌故事和创始愿景，为创意主题提供灵感
- 向前看：关注企业在新媒体、数字展示方面的战略规划
- 向右看：关注3D显示、LED媒体立面行业趋势
- 向下看：重点分析企业在产业链中的不可替代性""",
            variables=["company_name", "industry", "context"],
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        pt_generation = PromptTemplate(
            id=uuid.uuid4(),
            name="策划案补充指令",
            description="策划案生成 Skill 的补充指令，管理员可自定义行业偏好和强调重点",
            category="generation",
            template_text="""策划案生成补充要求：
- 创意主题需结合企业品牌基因和行业特征
- 视觉方向建议需考虑3D展示幕墙的物理特性（观看距离、屏幕比例、环境光）
- 实施建议需区分内容制作阶段和现场实施阶段
- 参考案例优先引用与客户同行业、同场景的成功案例

行业常见场景参考：
- 商业综合体：裸眼3D地标、节日主题、品牌联动
- 品牌发布：产品视觉冲击、品牌叙事、社交媒体传播
- 文旅夜游：沉浸式体验、故事化内容、互动装置
- 展览展示：科技感呈现、数据可视化、空间氛围""",
            variables=[
                "project_name",
                "client_name",
                "requirements",
                "case_studies",
                "company_profile",
            ],
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        pt_visual = PromptTemplate(
            id=uuid.uuid4(),
            name="视觉 Prompt 补充指令",
            description="视觉 Prompt 生成 Skill 的补充指令，管理员可自定义风格偏好和行业规范",
            category="visual",
            template_text="""视觉 Prompt 生成补充要求：
- positive_prompt 需包含画面主体、环境、氛围、光线、材质等关键描述
- 负向 Prompt 需排除低质量、变形、文字等常见问题
- 构图需考虑3D展示幕墙的异形屏比例和最佳观看角度

行业视觉风格参考：
- 科技品牌：深色背景 + 发光线条 + 粒子效果 + 金属质感
- 商业综合体：城市天际线 + 光影流动 + 3D纵深感
- 文旅夜游：自然元素 + 光效 + 沉浸式氛围
- 汽车品牌：产品特写 + 动态模糊 + 科技感环境""",
            variables=[
                "project_type",
                "industry",
                "style_preferences",
                "target_audience",
            ],
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([pt_analysis, pt_generation, pt_visual])
        await session.flush()

        # ── SOP Workflows (两层架构) ──
        # 第一层（sop_base）：通用文案策划 SOP — 所有行业通用
        #   包含：企业信息采集 → 背景分析 → 企业六看 → 质量审核
        # 第二层（sop_industry_*）：行业扩展 SOP — 行业定制
        #   智能制造：核心价值提炼 → 技术一张图 → 产品拆解
        #   未来可加：汽车品牌、商业地产、文旅夜游...
        #
        # rules.type 区分：
        #   "general" = 通用规则，所有行业适用
        #   "custom"  = 行业定制规则，仅限本行业

        # ── 第一层：通用文案策划 SOP ──
        sop_base = SOPWorkflow(
            id=uuid.uuid4(),
            name="通用文案策划 SOP（Base）",
            description="所有行业通用的文案策划标准流程。"
                        "涵盖企业信息采集、背景分析（宏观/中观/微观）、企业六看画像、质量审核。"
                        "行业定制内容通过行业扩展 SOP 叠加。",
            version="1.0",
            pipeline_stages=[
                {
                    "stage": "enterprise_understanding",
                    "name": "企业理解",
                    "description": "收集企业基础信息，构建全景画像",
                },
                {
                    "stage": "background_analysis",
                    "name": "背景分析",
                    "description": "从宏观、中观、微观三个层面分析行业与项目背景",
                },
                {
                    "stage": "quality_review",
                    "name": "质量审核",
                    "description": "审核文案质量，确保专业性和准确性",
                },
            ],
            steps=[
                {
                    "order": 1,
                    "name": "企业信息采集",
                    "description": "收集企业的基础信息，包括企业名称、所属行业、"
                                    "核心产品与服务、目标客户群、项目需求概述。",
                    "agent": "company_analysis",
                    "inputs": ["company_name", "industry", "core_products",
                               "target_audience", "project_requirements"],
                    "outputs": ["raw_company_data"],
                    "stage": "enterprise_understanding",
                    "rules": [
                        {"type": "general", "description": "必须收集行业、产品、客户三个维度的核心信息"},
                        {"type": "general", "description": "缺失关键字段时标记「需要进一步确认」，不编造"},
                    ],
                    "prompts": [
                        {"number": 1, "question": "企业核心产品或服务的行业地位如何？",
                         "purpose": "判断市场定位"},
                        {"number": 2, "question": "本次项目的核心目标是什么？",
                         "purpose": "明确项目方向"},
                    ],
                    "dependencies": [],
                },
                {
                    "order": 2,
                    "name": "背景分析",
                    "description": "从宏观（国家政策与产业趋势）、中观（行业格局与竞争态势）、"
                                    "微观（具体项目定位与目标）三个层面进行背景分析。",
                    "agent": "company_analysis",
                    "inputs": ["raw_company_data", "industry"],
                    "outputs": ["background_analysis_report"],
                    "stage": "background_analysis",
                    "rules": [
                        {"type": "general", "description": "宏观：引用与行业相关的国家政策、产业规划，标注政策来源"},
                        {"type": "general", "description": "中观：分析行业发展趋势、竞争格局和标杆企业"},
                        {"type": "general", "description": "微观：明确项目定位（在哪里、做什么、达到什么目的）"},
                        {"type": "general", "description": "所有数据必须真实可溯源，禁止编造政策条文或行业数据"},
                    ],
                    "prompts": [
                        {"number": 1, "question": "当前政策环境下，该行业面临的关键机遇和挑战是什么？",
                         "purpose": "建立宏观政策连接"},
                        {"number": 2, "question": "行业的核心趋势和标杆是什么？",
                         "purpose": "构建中观行业图景"},
                        {"number": 3, "question": "项目定位（在哪里、做什么、达到什么目的）？",
                         "purpose": "锚定微观项目目标"},
                    ],
                    "dependencies": ["企业信息采集"],
                },
                {
                    "order": 3,
                    "name": "企业六看分析",
                    "description": "基于「六看」框架对企业进行全景画像："
                                    "向后看发展历史、向前看发展规划、向左看竞争对手、"
                                    "向右看行业情况、向上看政策背景、向下看生态位。",
                    "agent": "company_analysis",
                    "inputs": ["raw_company_data", "background_analysis_report"],
                    "outputs": ["company_profile"],
                    "stage": "enterprise_understanding",
                    "rules": [
                        {"type": "general", "description": "向后看：梳理企业发展历程、核心积累和关键里程碑"},
                        {"type": "general", "description": "向前看：提炼企业战略规划、技术路线图和发展方向"},
                        {"type": "general", "description": "向左看：分析核心竞争对手的能力和策略"},
                        {"type": "general", "description": "向右看：评估行业整体发展趋势、标准和生态"},
                        {"type": "general", "description": "向上看：梳理与企业发展相关的国家和地方政策"},
                        {"type": "general", "description": "向下看：明确企业在产业链中的生态位和核心价值"},
                    ],
                    "prompts": [
                        {"number": 1, "question": "企业「核心生态位」在行业中是什么？",
                         "purpose": "确认差异化定位"},
                        {"number": 2, "question": "企业在产业链中处于什么位置？",
                         "purpose": "明确产业链角色"},
                    ],
                    "dependencies": ["背景分析"],
                },
                {
                    "order": 4,
                    "name": "质量审核",
                    "description": "审核最终文案的质量，确保专业性、准确性和可交付性。",
                    "agent": "quality_check",
                    "inputs": ["company_profile", "all_deliverables"],
                    "outputs": ["review_result"],
                    "stage": "quality_review",
                    "rules": [
                        {"type": "general", "description": "用真实数据并标明来源，禁止无出处引用"},
                        {"type": "general", "description": "文案总结避免AI味（模板化表述、空泛总结、过度修饰）"},
                        {"type": "general", "description": "只分析不判断，不做超出数据支撑范围的结论"},
                        {"type": "general", "description": "以10年经验策展人视角输出，文案需精炼、逻辑强、专业"},
                        {"type": "general", "description": "所有报价、工期、技术参数必须标记「需要进一步确认」"},
                    ],
                    "dependencies": [],
                },
            ],
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        # ── 第二层：智能制造行业扩展 SOP ──
        sop_smart_mfg = SOPWorkflow(
            id=uuid.uuid4(),
            name="智能制造行业文案扩展 SOP",
            description="智能制造行业的文案策划定制流程，需与「通用文案策划 SOP（Base）」配合使用。"
                        "在通用流程（背景分析+六看+质量审核）之间插入行业定制步骤："
                        "核心价值提炼 → 技术一张图 → 产品拆解。"
                        "适用场景：智能制造品牌馆、企业展厅、产线可视化。",
            version="1.0",
            pipeline_stages=[
                {
                    "stage": "core_value",
                    "name": "核心价值提炼",
                    "description": "基于企业画像提炼核心价值，构建行业叙事逻辑",
                },
                {
                    "stage": "content_creation",
                    "name": "内容创作",
                    "description": "技术架构图 + 产品拆解",
                },
            ],
            steps=[
                {
                    "order": 1,
                    "name": "企业信息采集（行业补充）",
                    "description": "在通用企业信息基础上，补充智能制造行业专属信息："
                                    "产线规模、自动化等级、已部署的工业系统。",
                    "agent": "company_analysis",
                    "inputs": ["raw_company_data"],
                    "outputs": ["industry_specific_data"],
                    "stage": "enterprise_understanding",
                    "rules": [
                        {"type": "custom", "description": "必须包含产线自动化等级评估（手工/半自动/全自动/智能化）"},
                        {"type": "custom", "description": "记录企业是否已部署 MES/ERP/SCADA/PLM 等工业系统"},
                    ],
                    "prompts": [
                        {"number": 1, "question": "企业当前产线自动化程度如何？",
                         "purpose": "评估数字化基础"},
                        {"number": 2, "question": "核心产品在智能制造产业链中的技术壁垒是什么？",
                         "purpose": "判断技术竞争力"},
                    ],
                    "dependencies": ["企业信息采集"],
                },
                {
                    "order": 2,
                    "name": "企业核心价值提炼",
                    "description": "基于六看分析结果，提炼智能制造企业核心价值主张，构建叙事逻辑。"
                                    "叙事逻辑聚焦行业赛道，确保后续技术一张图和产品拆解有清晰框架。",
                    "agent": "proposal",
                    "inputs": ["company_profile", "background_analysis_report"],
                    "outputs": ["core_value_narrative"],
                    "stage": "core_value",
                    "rules": [
                        {"type": "general", "description": "叙事逻辑必须聚焦行业赛道，避免空泛的企业愿景描述"},
                        {"type": "general", "description": "核心价值需能支撑后续技术架构和产品拆解的内容框架"},
                        {"type": "custom", "description": "智能制造企业的叙事逻辑通常围绕：效率提升、质量管控、柔性生产、数据驱动"},
                    ],
                    "prompts": [
                        {"number": 1, "question": "企业最核心的差异化价值是什么？用一句话概括。",
                         "purpose": "提炼核心价值主张"},
                        {"number": 2, "question": "这个核心价值如何与智能制造行业趋势呼应？",
                         "purpose": "验证叙事逻辑的行业适配性"},
                    ],
                    "dependencies": ["企业六看分析"],
                },
                {
                    "order": 3,
                    "name": "技术一张图",
                    "description": "基于核心价值叙事，梳理企业技术架构全景图。"
                                    "智能制造企业通常包含：信息层（数据采集与展示）、"
                                    "控制层（MES/SCADA/PLC）、执行层（机器人/AGV/产线设备）。",
                    "agent": "proposal",
                    "inputs": ["core_value_narrative", "company_profile"],
                    "outputs": ["technology_blueprint"],
                    "stage": "content_creation",
                    "rules": [
                        {"type": "general", "description": "技术架构需分层呈现，形成闭环"},
                        {"type": "general", "description": "每层需标注关键技术组件和数据流向"},
                        {"type": "custom", "description": "智能制造技术架构标准分层：信息层→控制层→执行层"},
                        {"type": "custom", "description": "需结合企业实际部署的系统和设备，不虚构技术栈"},
                    ],
                    "dependencies": ["企业核心价值提炼"],
                },
                {
                    "order": 4,
                    "name": "产品拆解",
                    "description": "对企业的核心产品或解决方案进行结构化拆解，"
                                    "展示产品组成、技术特点和客户价值。",
                    "agent": "proposal",
                    "inputs": ["technology_blueprint", "company_profile"],
                    "outputs": ["product_breakdown"],
                    "stage": "content_creation",
                    "rules": [
                        {"type": "general", "description": "产品拆解需从功能模块、技术实现、应用场景三个维度展开"},
                        {"type": "general", "description": "每个产品/模块需标注核心卖点和差异化优势"},
                        {"type": "custom", "description": "需与前面技术一张图的技术架构保持一致"},
                    ],
                    "dependencies": ["技术一张图"],
                },
                {
                    "order": 5,
                    "name": "质量审核（行业补充）",
                    "description": "在通用质量审核基础上，增加智能制造行业专项检查。",
                    "agent": "quality_check",
                    "inputs": ["core_value_narrative", "technology_blueprint", "product_breakdown"],
                    "outputs": ["industry_review_result"],
                    "stage": "quality_review",
                    "rules": [
                        {"type": "custom", "description": "检查技术一张图与产品拆解是否与叙事逻辑一致"},
                        {"type": "custom", "description": "六看分析中需重点验证工业4.0/工业互联网/数字孪生等技术布局的准确性"},
                        {"type": "custom", "description": "技术参数（产线规模、设备型号、系统版本）必须标记「需要进一步确认」"},
                    ],
                    "dependencies": ["产品拆解"],
                },
            ],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([sop_base, sop_smart_mfg])
        await session.flush()

        # ── Skills (built-in skill definitions) ──
        skills_data = [
            {
                "skill_id": "company_analysis",
                "name": "企业解析",
                "description": "分析企业行业、品牌、受众、视觉偏好，生成企业画像",
                "category": "analysis",
                "manifest_json": {
                    "skill_id": "company_analysis",
                    "name": "企业解析",
                    "required_services": ["llm.generate_json", "knowledge.retrieve"],
                    "permissions": ["read_knowledge", "write_project_output"],
                },
                "input_schema_json": {
                    "type": "object",
                    "properties": {
                        "company_id": {"type": "string"},
                        "additional_context": {"type": "string"},
                    },
                    "required": ["company_id"],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "company_profile": {"type": "object"},
                        "missing_info": {"type": "array"},
                    },
                },
                "required_services_json": ["llm.generate_json", "knowledge.retrieve"],
                "permissions_json": ["read_knowledge", "write_project_output"],
                "visibility": "internal",
                "version": "1.0.0",
            },
            {
                "skill_id": "case_retrieval",
                "name": "案例检索",
                "description": "基于项目需求检索匹配的案例库",
                "category": "retrieval",
                "manifest_json": {
                    "skill_id": "case_retrieval",
                    "name": "案例检索",
                    "required_services": ["knowledge.retrieve"],
                    "permissions": ["read_knowledge"],
                },
                "input_schema_json": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "industry": {"type": "string"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "cases": {"type": "array"},
                    },
                },
                "required_services_json": ["knowledge.retrieve"],
                "permissions_json": ["read_knowledge"],
                "visibility": "internal",
                "version": "1.0.0",
            },
            {
                "skill_id": "proposal_generation",
                "name": "策划案生成",
                "description": "根据企业画像、项目需求和案例库生成策划案初稿",
                "category": "proposal",
                "manifest_json": {
                    "skill_id": "proposal_generation",
                    "name": "策划案生成",
                    "required_services": ["llm.generate", "knowledge.context_pack", "export.docx"],
                    "permissions": ["read_knowledge", "write_project_output"],
                },
                "input_schema_json": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "template_id": {"type": "string"},
                        "sop_workflow_id": {"type": "string"},
                    },
                    "required": ["project_id"],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "proposal_sections": {"type": "array"},
                        "citations": {"type": "array"},
                        "missing_info": {"type": "array"},
                    },
                },
                "required_services_json": ["llm.generate", "knowledge.context_pack", "export.docx"],
                "permissions_json": ["read_knowledge", "write_project_output"],
                "visibility": "internal",
                "version": "1.0.0",
            },
            {
                "skill_id": "visual_prompt",
                "name": "视觉 Prompt 生成",
                "description": "生成视觉策略、正向/负向 Prompt 和构图建议",
                "category": "visual",
                "manifest_json": {
                    "skill_id": "visual_prompt",
                    "name": "视觉 Prompt 生成",
                    "required_services": ["llm.generate_json"],
                    "permissions": ["read_knowledge", "write_project_output"],
                },
                "input_schema_json": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "style_preferences": {"type": "string"},
                        "visual_style_id": {"type": "string"},
                    },
                    "required": ["project_id"],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "visual_strategy": {"type": "object"},
                        "positive_prompt": {"type": "string"},
                        "negative_prompt": {"type": "string"},
                    },
                },
                "required_services_json": ["llm.generate_json"],
                "permissions_json": ["read_knowledge", "write_project_output"],
                "visibility": "internal",
                "version": "1.0.0",
            },
            {
                "skill_id": "image_generation",
                "name": "图片生成",
                "description": "根据 Prompt 调用图片生成服务",
                "category": "visual",
                "manifest_json": {
                    "skill_id": "image_generation",
                    "name": "图片生成",
                    "required_services": ["image.generate"],
                    "permissions": ["write_project_output"],
                },
                "input_schema_json": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "negative_prompt": {"type": "string"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                    "required": ["prompt"],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "image_url": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                },
                "required_services_json": ["image.generate"],
                "permissions_json": ["write_project_output"],
                "visibility": "internal",
                "version": "1.0.0",
            },
            {
                "skill_id": "export",
                "name": "方案导出",
                "description": "将生成结果导出为 Word/PDF 文档",
                "category": "export",
                "manifest_json": {
                    "skill_id": "export",
                    "name": "方案导出",
                    "required_services": ["export.docx", "export.pdf"],
                    "permissions": ["read_project_output"],
                },
                "input_schema_json": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "format": {"type": "string", "enum": ["word", "pdf"]},
                    },
                    "required": ["task_id", "format"],
                },
                "output_schema_json": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                    },
                },
                "required_services_json": ["export.docx", "export.pdf"],
                "permissions_json": ["read_project_output"],
                "visibility": "internal",
                "version": "1.0.0",
            },
        ]

        for sd in skills_data:
            skill = Skill(
                id=uuid.uuid4(),
                skill_id=sd["skill_id"],
                name=sd["name"],
                description=sd["description"],
                category=sd["category"],
                manifest_json=sd["manifest_json"],
                input_schema_json=sd["input_schema_json"],
                output_schema_json=sd["output_schema_json"],
                required_services_json=sd["required_services_json"],
                permissions_json=sd["permissions_json"],
                visibility=sd["visibility"],
                version=sd["version"],
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(skill)

        await session.commit()


async def init_db() -> None:
    """Create tables and seed the database."""
    await create_tables()
    await seed_database()
