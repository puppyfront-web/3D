"""Database initialization with seed data."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory, engine
from app.models import (
    Case,
    Company,
    CompanyProfile,
    Document,
    Feedback,
    GenerationOutput,
    GenerationTask,
    PromptTemplate,
    Project,
    ProposalTemplate,
    QualityRule,
    RetrievalLog,
    Role,
    SOPWorkflow,
    Skill,
    TechnicalRule,
    User,
    VisualStyle,
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
    """Insert realistic sample data when the database is empty."""
    async with async_session_factory() as session:
        # Check if data already exists
        from sqlalchemy import select
        existing = await session.execute(select(User).limit(1))
        if existing.scalar_one_or_none():
            return

        now = datetime.now(timezone.utc)

        # --- Roles ---
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

        # --- Users ---
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

        # --- Companies ---
        techcorp = Company(
            id=uuid.uuid4(),
            name="TechCorp Solutions",
            industry="Technology",
            website="https://techcorp.example.com",
            description="Leading enterprise software solutions provider specializing in cloud infrastructure and AI-powered analytics.",
            created_at=now,
            updated_at=now,
        )
        greenenergy = Company(
            id=uuid.uuid4(),
            name="GreenEnergy Corp",
            industry="Energy",
            website="https://greenenergy.example.com",
            description="Renewable energy company focused on solar panel manufacturing and wind farm operations.",
            created_at=now,
            updated_at=now,
        )
        medhealth = Company(
            id=uuid.uuid4(),
            name="MedHealth Innovations",
            industry="Healthcare",
            website="https://medhealth.example.com",
            description="Healthcare technology company developing AI-assisted diagnostic tools and telemedicine platforms.",
            created_at=now,
            updated_at=now,
        )
        session.add_all([techcorp, greenenergy, medhealth])
        await session.flush()

        # --- Company Profiles ---
        profile_techcorp = CompanyProfile(
            id=uuid.uuid4(),
            company_id=techcorp.id,
            strengths="Strong R&D capabilities; Patent portfolio of 200+ patents; Global presence in 30 countries; Annual revenue of $2.5B",
            weaknesses="Legacy system dependencies; Slow adoption of emerging frameworks; High employee turnover in engineering",
            market_position="Market leader in enterprise cloud solutions with 25% market share",
            key_products="CloudSuite Platform, DataInsight Analytics, SecureVault Cybersecurity",
            competitors="Amazon AWS, Microsoft Azure, Google Cloud Platform",
            recent_news="Launched new AI-powered analytics platform; Acquired two cybersecurity startups in Q3",
            culture="Innovation-driven, fast-paced engineering culture with emphasis on continuous learning",
            financials="Annual revenue: $2.5B, Growth rate: 18% YoY, R&D budget: $400M",
            created_at=now,
            updated_at=now,
        )
        session.add(profile_techcorp)
        await session.flush()

        # --- Projects ---
        project1 = Project(
            id=uuid.uuid4(),
            name="TechCorp Digital Transformation Proposal",
            description="Comprehensive digital transformation proposal for TechCorp's cloud migration initiative",
            company_id=techcorp.id,
            owner_id=admin_user.id,
            status="in_progress",
            priority="high",
            created_at=now,
            updated_at=now,
        )
        project2 = Project(
            id=uuid.uuid4(),
            name="GreenEnergy Solar Farm Expansion",
            description="Proposal for expanding solar farm capacity with next-generation panel technology",
            company_id=greenenergy.id,
            owner_id=demo_user.id,
            status="draft",
            priority="medium",
            created_at=now,
            updated_at=now,
        )
        project3 = Project(
            id=uuid.uuid4(),
            name="MedHealth Telemedicine Platform",
            description="Platform proposal for AI-powered remote patient monitoring and diagnostics",
            company_id=medhealth.id,
            owner_id=demo_user.id,
            status="completed",
            priority="high",
            created_at=now,
            updated_at=now,
        )
        session.add_all([project1, project2, project3])
        await session.flush()

        # --- Documents ---
        doc1 = Document(
            id=uuid.uuid4(),
            project_id=project1.id,
            filename="techcorp_requirements.pdf",
            original_filename="TechCorp_Requirements_2024.pdf",
            content_type="application/pdf",
            file_size=2048576,
            file_path="storage/techcorp_requirements.pdf",
            title="TechCorp Project Requirements Document",
            status="indexed",
            chunk_count=12,
            created_at=now,
            updated_at=now,
        )
        doc2 = Document(
            id=uuid.uuid4(),
            project_id=project1.id,
            filename="cloud_architecture.pptx",
            original_filename="Cloud_Architecture_Overview.pptx",
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            file_size=5242880,
            file_path="storage/cloud_architecture.pptx",
            title="Cloud Architecture Overview Presentation",
            status="indexed",
            chunk_count=8,
            created_at=now,
            updated_at=now,
        )
        doc3 = Document(
            id=uuid.uuid4(),
            project_id=project2.id,
            filename="solar_panel_specs.pdf",
            original_filename="NextGen_Solar_Panel_Specifications.pdf",
            content_type="application/pdf",
            file_size=1048576,
            file_path="storage/solar_panel_specs.pdf",
            title="NextGen Solar Panel Technical Specifications",
            status="indexed",
            chunk_count=6,
            created_at=now,
            updated_at=now,
        )
        session.add_all([doc1, doc2, doc3])
        await session.flush()

        # --- Cases ---
        case1 = Case(
            id=uuid.uuid4(),
            project_id=project1.id,
            title="Enterprise Cloud Migration - Global Logistics Corp",
            client_name="Global Logistics Corp",
            industry="Logistics",
            challenge="Legacy on-premise systems causing scalability issues during peak shipping seasons, resulting in 15% order processing delays",
            solution="Migrated core logistics platform to cloud-native microservices architecture with auto-scaling capabilities",
            results="40% improvement in processing speed, 99.9% uptime, $3.2M annual cost savings",
            technologies="AWS, Kubernetes, Docker, PostgreSQL, Redis, RabbitMQ",
            duration="8 months",
            team_size=12,
            budget_range="$800K - $1.2M",
            quality_score=92,
            is_published=True,
            created_at=now,
            updated_at=now,
        )
        case2 = Case(
            id=uuid.uuid4(),
            project_id=project1.id,
            title="AI-Powered Supply Chain Optimization - RetailMax",
            client_name="RetailMax Inc",
            industry="Retail",
            challenge="Inefficient supply chain management leading to 20% excess inventory and frequent stockouts of popular items",
            solution="Implemented AI-driven demand forecasting and automated inventory replenishment system",
            results="25% reduction in excess inventory, 98% product availability, 30% improvement in forecast accuracy",
            technologies="Python, TensorFlow, Azure ML, SAP Integration, Kafka",
            duration="6 months",
            team_size=8,
            budget_range="$500K - $750K",
            quality_score=88,
            is_published=True,
            created_at=now,
            updated_at=now,
        )
        case3 = Case(
            id=uuid.uuid4(),
            project_id=project2.id,
            title="Solar Farm Monitoring Dashboard - SunPower Estates",
            client_name="SunPower Estates",
            industry="Energy",
            challenge="Manual monitoring of 500+ solar panels across multiple locations causing delayed fault detection",
            solution="Built IoT-based real-time monitoring platform with predictive maintenance alerts",
            results="60% faster fault detection, 15% increase in energy output, 40% reduction in maintenance costs",
            technologies="IoT Sensors, React, Node.js, TimescaleDB, Grafana, MQTT",
            duration="4 months",
            team_size=6,
            budget_range="$200K - $350K",
            quality_score=85,
            is_published=True,
            created_at=now,
            updated_at=now,
        )
        case4 = Case(
            id=uuid.uuid4(),
            project_id=project3.id,
            title="Telemedicine Platform - CityHealth Network",
            client_name="CityHealth Network",
            industry="Healthcare",
            challenge="Limited access to specialist care in rural areas, long wait times averaging 6 weeks for appointments",
            solution="Developed HIPAA-compliant telemedicine platform with AI-assisted triage and scheduling optimization",
            results="85% reduction in wait times, 40% increase in specialist consultations, 95% patient satisfaction score",
            technologies="React, Node.js, WebRTC, AWS, TensorFlow, HL7 FHIR",
            duration="10 months",
            team_size=15,
            budget_range="$1.0M - $1.5M",
            quality_score=95,
            is_published=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([case1, case2, case3, case4])
        await session.flush()

        # --- Prompt Templates ---
        # Note: These templates provide supplementary admin-configurable instructions.
        # The framework structure (六看, OUTPUT_SCHEMA, etc.) is always in the skill's
        # _default_prompt() as the base. These templates are APPENDED as extra guidance,
        # not replacing the default. Admins can edit these via /admin/prompt-templates.
        pt1 = PromptTemplate(
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
        pt2 = PromptTemplate(
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
        pt3 = PromptTemplate(
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
        session.add_all([pt1, pt2, pt3])
        await session.flush()

        # --- Proposal Templates ---
        prop_t1 = ProposalTemplate(
            id=uuid.uuid4(),
            name="Standard Technical Proposal",
            description="Comprehensive technical proposal template suitable for most IT projects",
            category="technical",
            sections={
                "executive_summary": "Brief overview of the proposal",
                "understanding": "Demonstrate understanding of client needs",
                "solution": "Proposed technical solution",
                "methodology": "Implementation methodology and approach",
                "timeline": "Project timeline with milestones",
                "team": "Team structure and roles",
                "budget": "Detailed budget breakdown",
                "risks": "Risk assessment and mitigation",
                "success_metrics": "KPIs and success criteria",
                "appendix": "Supporting documents and references",
            },
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        prop_t2 = ProposalTemplate(
            id=uuid.uuid4(),
            name="Creative Pitch Deck",
            description="Visually-focused proposal template for creative and design projects",
            category="creative",
            sections={
                "cover": "Eye-catching title slide",
                "problem": "The challenge statement",
                "solution": "Creative solution overview",
                "portfolio": "Relevant case studies",
                "approach": "Creative methodology",
                "timeline": "Project phases",
                "investment": "Budget and ROI",
                "team": "Creative team profiles",
                "next_steps": "Call to action",
            },
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        session.add_all([prop_t1, prop_t2])
        await session.flush()

        # --- SOP Workflows ---
        sop1 = SOPWorkflow(
            id=uuid.uuid4(),
            name="Standard Proposal Generation SOP",
            description="Standard operating procedure for generating project proposals",
            version="1.2",
            steps=[
                {
                    "order": 1,
                    "name": "Gather Requirements",
                    "description": "Collect and document all client requirements",
                    "agent": "company_analysis",
                    "inputs": ["company_name", "industry", "website"],
                },
                {
                    "order": 2,
                    "name": "Company Analysis",
                    "description": "Analyze the client company and generate profile",
                    "agent": "company_analysis",
                    "inputs": ["gathered_requirements"],
                },
                {
                    "order": 3,
                    "name": "Case Study Selection",
                    "description": "Select relevant case studies from knowledge base",
                    "agent": "retriever",
                    "inputs": ["company_profile", "requirements"],
                },
                {
                    "order": 4,
                    "name": "Generate Proposal",
                    "description": "Generate the proposal document",
                    "agent": "proposal",
                    "inputs": ["company_profile", "case_studies", "requirements"],
                },
                {
                    "order": 5,
                    "name": "Quality Review",
                    "description": "Review generated proposal against quality rules",
                    "agent": "quality_check",
                    "inputs": ["proposal_draft"],
                },
                {
                    "order": 6,
                    "name": "Visual Enhancement",
                    "description": "Apply visual styling and generate presentation",
                    "agent": "visual",
                    "inputs": ["final_proposal"],
                },
            ],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        sop2 = SOPWorkflow(
            id=uuid.uuid4(),
            name="Quick Proposal SOP",
            description="Accelerated proposal generation for repeat clients",
            version="1.0",
            steps=[
                {
                    "order": 1,
                    "name": "Load Client Profile",
                    "description": "Load existing company profile",
                    "agent": "company_analysis",
                    "inputs": ["company_id"],
                },
                {
                    "order": 2,
                    "name": "Quick Case Match",
                    "description": "Auto-match relevant case studies",
                    "agent": "retriever",
                    "inputs": ["company_profile", "project_type"],
                },
                {
                    "order": 3,
                    "name": "Generate Proposal",
                    "description": "Generate proposal with existing data",
                    "agent": "proposal",
                    "inputs": ["company_profile", "case_studies"],
                },
            ],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        # ── 两层 SOP 架构 ──
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
        session.add_all([sop1, sop2, sop_base, sop_smart_mfg])
        await session.flush()

        # --- Visual Styles ---
        vs1 = VisualStyle(
            id=uuid.uuid4(),
            name="Modern Tech",
            description="Clean, modern design with bold colors and geometric elements",
            primary_color="#1a73e8",
            secondary_color="#4285f4",
            accent_color="#34a853",
            background_color="#ffffff",
            font_primary="Inter",
            font_secondary="Roboto",
            layout="grid",
            brand_guidelines="Use geometric shapes and clean lines. Minimum use of gradients. Bold headings with generous whitespace.",
            created_at=now,
            updated_at=now,
        )
        vs2 = VisualStyle(
            id=uuid.uuid4(),
            name="Corporate Professional",
            description="Traditional corporate style with refined typography",
            primary_color="#1b3a5c",
            secondary_color="#2c5f8a",
            accent_color="#d4a843",
            background_color="#f8f9fa",
            font_primary="Georgia",
            font_secondary="Arial",
            layout="classic",
            brand_guidelines="Conservative color palette. Serif fonts for headings. Ample white space. Professional charts and graphs.",
            created_at=now,
            updated_at=now,
        )
        vs3 = VisualStyle(
            id=uuid.uuid4(),
            name="Creative Bold",
            description="Vibrant and creative style for design-forward proposals",
            primary_color="#6c5ce7",
            secondary_color="#a29bfe",
            accent_color="#fd79a8",
            background_color="#0c0c1d",
            font_primary="Poppins",
            font_secondary="Montserrat",
            layout="asymmetric",
            brand_guidelines="Bold gradients and vibrant colors. Large typography. Asymmetric layouts. Use of illustrations and icons.",
            created_at=now,
            updated_at=now,
        )
        session.add_all([vs1, vs2, vs3])
        await session.flush()

        # --- Technical Rules ---
        tr1 = TechnicalRule(
            id=uuid.uuid4(),
            name="Cloud Architecture Standards",
            category="architecture",
            description="Standards for cloud-based solution architectures",
            rule_text="All cloud solutions must follow microservices architecture, use containerized deployments, implement auto-scaling, and include disaster recovery plans.",
            severity="critical",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        tr2 = TechnicalRule(
            id=uuid.uuid4(),
            name="Security Requirements",
            category="security",
            description="Mandatory security standards for all proposals",
            rule_text="All proposals must include: data encryption at rest and in transit, role-based access control, regular security audits, and compliance with relevant regulations (GDPR, HIPAA, SOC2).",
            severity="critical",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        tr3 = TechnicalRule(
            id=uuid.uuid4(),
            name="Performance Benchmarks",
            category="performance",
            description="Required performance metrics for proposed solutions",
            rule_text="Solutions must target: API response time < 200ms, page load time < 2s, 99.9% uptime SLA, horizontal scalability to 10x baseline load.",
            severity="warning",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([tr1, tr2, tr3])
        await session.flush()

        # --- Quality Rules ---
        qr1 = QualityRule(
            id=uuid.uuid4(),
            name="Proposal Completeness",
            category="completeness",
            description="Ensures all required sections are present in proposals",
            rule_text="Every proposal must contain: Executive Summary, Problem Statement, Proposed Solution, Timeline, Budget, Team Qualifications, and Success Metrics.",
            weight=1.0,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        qr2 = QualityRule(
            id=uuid.uuid4(),
            name="Case Study Relevance",
            category="relevance",
            description="Checks that referenced case studies are relevant to the proposal",
            rule_text="At least 2 case studies must be included with matching industry or technology. Case study descriptions must be at least 200 words each.",
            weight=0.8,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        qr3 = QualityRule(
            id=uuid.uuid4(),
            name="Professional Tone",
            category="tone",
            description="Ensures professional writing style throughout the proposal",
            rule_text="Proposals must use professional business language, avoid jargon, maintain consistent terminology, and be written in active voice.",
            weight=0.6,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([qr1, qr2, qr3])
        await session.flush()

        # --- Generation Tasks ---
        gt1 = GenerationTask(
            id=uuid.uuid4(),
            project_id=project1.id,
            type="company_analysis",
            status="completed",
            prompt_used="Analyze TechCorp Solutions...",
            model_used="mock-v1",
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        gt2 = GenerationTask(
            id=uuid.uuid4(),
            project_id=project1.id,
            type="proposal",
            status="completed",
            prompt_used="Generate proposal for TechCorp Digital Transformation...",
            model_used="mock-v1",
            started_at=now,
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add_all([gt1, gt2])
        await session.flush()

        # --- Generation Outputs ---
        go1 = GenerationOutput(
            id=uuid.uuid4(),
            task_id=gt1.id,
            content_type="application/json",
            content='{"strengths": ["Strong R&D capabilities", "Global presence in 30 countries", "Annual revenue of $2.5B"], "weaknesses": ["Legacy system dependencies", "High employee turnover"], "market_position": "Market leader in enterprise cloud solutions", "key_products": ["CloudSuite Platform", "DataInsight Analytics"]}',
            used_cases=[str(case1.id), str(case2.id)],
            used_documents=[str(doc1.id), str(doc2.id)],
            used_chunks=[],
            used_sop_version="1.2",
            created_at=now,
            updated_at=now,
        )
        go2 = GenerationOutput(
            id=uuid.uuid4(),
            task_id=gt2.id,
            content_type="text/markdown",
            content="# TechCorp Digital Transformation Proposal\n\n## Executive Summary\n\nThis proposal outlines a comprehensive digital transformation strategy for TechCorp Solutions, focusing on cloud-native modernization and AI-powered analytics.\n\n## Understanding of Requirements\n\nTechCorp requires a modern, scalable cloud platform to replace legacy on-premise systems...",
            used_cases=[str(case1.id)],
            used_documents=[str(doc1.id)],
            used_chunks=["chunk_1", "chunk_2", "chunk_5"],
            used_sop_version="1.2",
            created_at=now,
            updated_at=now,
        )
        session.add_all([go1, go2])
        await session.flush()

        # --- Retrieval Logs ---
        rl1 = RetrievalLog(
            id=uuid.uuid4(),
            query="cloud migration best practices",
            retrieval_type="hybrid",
            results_count=5,
            top_scores=[0.95, 0.89, 0.82, 0.78, 0.71],
            document_ids=[str(doc1.id), str(doc2.id)],
            latency_ms=120,
            created_at=now,
            updated_at=now,
        )
        session.add(rl1)
        await session.flush()

        # --- Feedback ---
        fb1 = Feedback(
            id=uuid.uuid4(),
            project_id=project1.id,
            user_id=admin_user.id,
            generation_task_id=gt2.id,
            rating=4,
            comment="Good proposal structure. Could improve the budget section with more detailed breakdowns.",
            category="quality",
            created_at=now,
            updated_at=now,
        )
        session.add(fb1)
        await session.flush()

        # --- Skills (built-in skill definitions) ---
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
