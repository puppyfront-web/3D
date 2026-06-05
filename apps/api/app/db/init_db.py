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
    TechnicalRule,
    User,
    VisualStyle,
)
from app.db.base import Base


async def create_tables() -> None:
    """Create all tables (used during development)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
        pt1 = PromptTemplate(
            id=uuid.uuid4(),
            name="Company Analysis Prompt",
            description="Comprehensive company analysis template for generating detailed company profiles",
            category="analysis",
            template_text="""Analyze the following company and generate a comprehensive profile:

Company: {company_name}
Industry: {industry}
Additional Context: {context}

Please provide:
1. Company Strengths (3-5 key strengths)
2. Company Weaknesses (2-3 areas of concern)
3. Market Position Analysis
4. Key Products and Services
5. Competitive Landscape
6. Recent News and Developments
7. Company Culture and Values
8. Financial Overview

Format the response as structured JSON.""",
            variables=["company_name", "industry", "context"],
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        pt2 = PromptTemplate(
            id=uuid.uuid4(),
            name="Proposal Generation Prompt",
            description="Template for generating professional project proposals",
            category="generation",
            template_text="""Generate a professional proposal based on the following information:

Project: {project_name}
Client: {client_name}
Requirements: {requirements}
Budget Range: {budget}
Timeline: {timeline}

Using these relevant case studies:
{case_studies}

And company information:
{company_profile}

Please generate a comprehensive proposal including:
1. Executive Summary
2. Understanding of Requirements
3. Proposed Solution
4. Implementation Approach
5. Timeline and Milestones
6. Team Structure
7. Budget Breakdown
8. Risk Assessment
9. Success Metrics""",
            variables=[
                "project_name",
                "client_name",
                "requirements",
                "budget",
                "timeline",
                "case_studies",
                "company_profile",
            ],
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        pt3 = PromptTemplate(
            id=uuid.uuid4(),
            name="Visual Prompt Generation",
            description="Template for generating visual design prompts for project presentations",
            category="visual",
            template_text="""Create a visual design prompt for a project presentation based on:

Project Type: {project_type}
Industry: {industry}
Style Preferences: {style_preferences}
Target Audience: {target_audience}

Generate a detailed visual prompt that includes:
1. Color palette recommendations (primary, secondary, accent colors)
2. Typography suggestions
3. Layout structure
4. Key visual elements
5. Brand consistency guidelines""",
            variables=[
                "project_type",
                "industry",
                "style_preferences",
                "target_audience",
            ],
            is_default=False,
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
        session.add_all([sop1, sop2])
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

        await session.commit()


async def init_db() -> None:
    """Create tables and seed the database."""
    await create_tables()
    await seed_database()
