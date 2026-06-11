"""Proposal Generation Agent — 多轮对话状态机驱动的策划案生成工作流。

States:
  COLLECTING  → 收集用户需求（公司名、行业、项目类型等）
  ANALYZING   → 内部调用 company_analysis Skill + RAG 检索
  GENERATING  → 内部调用 proposal_generation Skill + 质量自检
  REVIEWING   → 等待用户确认/修改/重来
  COMPLETED   → 策划案确认完成，产出 handoff 数据给视觉 Agent
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSE chunk helper (same pattern as visual_concept.py)
# ---------------------------------------------------------------------------


def _sse_chunk(
    chunk_type: str,
    text: Optional[str] = None,
    data: Optional[Dict] = None,
) -> str:
    """Build an SSE-formatted string for streaming to the frontend."""
    payload: Dict[str, Any] = {"type": chunk_type}
    if text is not None:
        payload["text"] = text
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RequirementInfo:
    """从用户自然语言中提取的结构化需求。"""

    raw_input: str = ""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    project_type: Optional[str] = None  # curtain_wall | exhibition | culture_tourism | multimedia
    project_description: Optional[str] = None
    key_requirements: List[str] = field(default_factory=list)
    target_audience: Optional[str] = None
    budget_range: Optional[str] = None
    timeline: Optional[str] = None
    constraints: Optional[str] = None

    _MERGEABLE_FIELDS = (
        "company_name", "industry", "project_type",
        "project_description", "target_audience",
        "budget_range", "timeline", "constraints",
    )

    def merge_field(self, field_name: str, value: Any) -> None:
        if field_name in self._MERGEABLE_FIELDS:
            setattr(self, field_name, value)
        elif field_name == "key_requirements" and isinstance(value, list):
            self.key_requirements = value

    def get_missing_critical_fields(self) -> List[str]:
        """Return field names that are critical but still empty.

        Infers from raw_input as a fallback when LLM extraction is imperfect.
        """
        # Auto-infer project_type from raw_input keywords
        if not self.project_type and self.raw_input:
            type_map = {
                "幕墙": "3D幕墙", "LED": "3D幕墙", "裸眼3D": "3D幕墙", "媒体立面": "3D幕墙",
                "展厅": "企业展厅", "展陈": "企业展厅", "展馆": "展馆",
                "博物馆": "展馆", "规划馆": "展馆", "科技馆": "展馆",
                "文旅": "文旅夜游", "夜游": "文旅夜游", "光影秀": "文旅夜游", "沉浸式": "沉浸式体验",
                "互动装置": "互动装置", "数字沙盘": "数字沙盘",
            }
            for kw, ptype in type_map.items():
                if kw in self.raw_input:
                    self.project_type = ptype
                    break

        missing = []
        # company_name is satisfied if raw_input has enough context (>10 chars beyond trigger words)
        has_company_context = bool(
            self.company_name
            or self.project_description
            or (self.raw_input and len(self.raw_input) > 15)
        )
        if not has_company_context:
            missing.append("company_name")
        if not self.project_type:
            missing.append("project_type")
        return missing

    def has_enough_info(self) -> bool:
        return len(self.get_missing_critical_fields()) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_input": self.raw_input,
            "company_name": self.company_name,
            "industry": self.industry,
            "project_type": self.project_type,
            "project_description": self.project_description,
            "key_requirements": self.key_requirements,
            "target_audience": self.target_audience,
            "budget_range": self.budget_range,
            "timeline": self.timeline,
            "constraints": self.constraints,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RequirementInfo:
        return cls(
            raw_input=data.get("raw_input", ""),
            company_name=data.get("company_name"),
            industry=data.get("industry"),
            project_type=data.get("project_type"),
            project_description=data.get("project_description"),
            key_requirements=data.get("key_requirements", []),
            target_audience=data.get("target_audience"),
            budget_range=data.get("budget_range"),
            timeline=data.get("timeline"),
            constraints=data.get("constraints"),
        )


# Field labels for parameter card UI
FIELD_LABELS: Dict[str, str] = {
    "company_name": "客户企业名称",
    "project_type": "项目类型",
    "industry": "所属行业",
    "project_description": "项目描述",
    "target_audience": "目标受众",
    "budget_range": "预算范围",
    "timeline": "期望工期",
    "constraints": "特殊约束",
}

FIELD_OPTIONS: Dict[str, List[str]] = {
    "project_type": [
        "3D幕墙/裸眼3D", "企业展厅", "博物馆/规划馆",
        "文旅夜游", "沉浸式体验", "多媒体展项",
        "互动装置", "数字沙盘", "主题公园",
    ],
}


@dataclass
class ProposalContext:
    """ProposalAgent 的持久化状态，序列化到 Message.metadata_json。"""

    state: Literal[
        "COLLECTING", "ANALYZING", "GENERATING",
        "REVIEWING", "COMPLETED",
    ] = "COLLECTING"

    requirement: RequirementInfo = field(default_factory=RequirementInfo)
    ask_round: int = 0
    max_ask_rounds: int = 3
    missing_info: List[str] = field(default_factory=list)

    # Sub-step results
    company_analysis: Optional[Dict[str, Any]] = None
    context_pack_text: Optional[str] = None
    used_cases: List[str] = field(default_factory=list)
    used_documents: List[str] = field(default_factory=list)
    used_chunks: List[str] = field(default_factory=list)
    proposal_content: Optional[str] = None
    proposal_sections: List[Dict[str, Any]] = field(default_factory=list)
    missing_info_from_proposal: List[str] = field(default_factory=list)
    quality_check: Optional[Dict[str, Any]] = None

    # Auto-filled from project context
    auto_filled: Dict[str, str] = field(default_factory=dict)
    project_context_loaded: bool = False

    # Venue & screen params loaded from the project (workspace case), so the
    # proposal can use real params instead of fabricating / blanket 待确认.
    screen_info: Optional[Dict[str, Any]] = None

    # Agent-to-agent handoff
    domain: str = "curtain_wall"
    output_for_next_agent: Optional[Dict[str, Any]] = None

    def should_ask_more(self) -> bool:
        return self.ask_round < self.max_ask_rounds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_state": self.state,
            "requirement": self.requirement.to_dict(),
            "ask_round": self.ask_round,
            "max_ask_rounds": self.max_ask_rounds,
            "missing_info": self.missing_info,
            "company_analysis": self.company_analysis,
            "context_pack_text": self.context_pack_text,
            "used_cases": self.used_cases,
            "used_documents": self.used_documents,
            "used_chunks": self.used_chunks,
            "proposal_content": self.proposal_content,
            "proposal_sections": self.proposal_sections,
            "missing_info_from_proposal": self.missing_info_from_proposal,
            "quality_check": self.quality_check,
            "auto_filled": self.auto_filled,
            "project_context_loaded": self.project_context_loaded,
            "screen_info": self.screen_info,
            "domain": self.domain,
            "output_for_next_agent": self.output_for_next_agent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProposalContext:
        req_data = data.get("requirement", {})
        ctx = cls(
            state=data.get("proposal_state", "COLLECTING"),
            requirement=RequirementInfo.from_dict(req_data),
            ask_round=data.get("ask_round", 0),
            max_ask_rounds=data.get("max_ask_rounds", 3),
            missing_info=data.get("missing_info", []),
            company_analysis=data.get("company_analysis"),
            context_pack_text=data.get("context_pack_text"),
            used_cases=data.get("used_cases", []),
            used_documents=data.get("used_documents", []),
            used_chunks=data.get("used_chunks", []),
            proposal_content=data.get("proposal_content"),
            proposal_sections=data.get("proposal_sections", []),
            missing_info_from_proposal=data.get("missing_info_from_proposal", []),
            quality_check=data.get("quality_check"),
            auto_filled=data.get("auto_filled", {}),
            project_context_loaded=data.get("project_context_loaded", False),
            screen_info=data.get("screen_info"),
            domain=data.get("domain", "curtain_wall"),
            output_for_next_agent=data.get("output_for_next_agent"),
        )
        return ctx


# ---------------------------------------------------------------------------
# ProposalAgent
# ---------------------------------------------------------------------------


class ProposalAgent:
    """Agent that drives the COLLECTING → ANALYZING → GENERATING → REVIEWING → COMPLETED state machine.

    The agent is *stateless* — all per-conversation state lives in ProposalContext,
    persisted by the caller (e.g. inside Message.metadata_json).
    """

    name: str = "proposal"

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
    ):
        self._llm = llm_service
        self._embedding = embedding_service

    async def _ensure_services(self, db=None):
        """Lazily initialize services."""
        if self._llm is None:
            from app.services.llm_service import get_llm_service
            self._llm = await get_llm_service(db)
        if self._embedding is None:
            from app.services.embedding_service import get_embedding_service
            self._embedding = await get_embedding_service(db)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        user_input: str,
        ctx: ProposalContext,
        db: Optional[Any] = None,
        project_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Route user_input to the correct handler based on ctx.state."""
        await self._ensure_services(db)

        # Load venue & screen params from the project (workspace case) once, so
        # proposal generation uses real params instead of fabricating them.
        if project_id and db and not ctx.screen_info:
            ctx.screen_info = await self._load_screen_info(project_id, db)

        # Store raw input on first entry
        if ctx.state == "COLLECTING" and not ctx.requirement.raw_input:
            ctx.requirement.raw_input = user_input

        try:
            # Auto-fill from project context on first COLLECTING
            if (
                ctx.state == "COLLECTING"
                and not ctx.project_context_loaded
                and project_id
                and db
            ):
                project_ctx = await self._load_project_context(project_id, db)
                if project_ctx:
                    yield _sse_chunk("context_card", data=project_ctx)
                    for fname, fval in project_ctx.get("auto_filled", {}).items():
                        ctx.requirement.merge_field(fname, fval)
                    ctx.auto_filled = project_ctx.get("auto_filled", {})
                    ctx.project_context_loaded = True

            if ctx.state == "REVIEWING":
                async for chunk in self._handle_reviewing(user_input, ctx, db):
                    yield chunk
            elif ctx.state == "COMPLETED":
                yield _sse_chunk("text_delta", text="策划案已完成，正在进入视觉创意阶段…")
                yield _sse_chunk("done")
            else:
                # COLLECTING (or any transient state)
                async for chunk in self._handle_collecting(user_input, ctx, db):
                    yield chunk
        except Exception as exc:
            logger.exception("ProposalAgent error")
            yield _sse_chunk("error", text=f"Agent error: {exc}")
            yield _sse_chunk("done")

    # ------------------------------------------------------------------
    # COLLECTING handler
    # ------------------------------------------------------------------

    async def _handle_collecting(
        self,
        user_input: str,
        ctx: ProposalContext,
        db: Optional[Any],
    ) -> AsyncGenerator[str, None]:
        """Parse user input → merge requirement → ask more or run pipeline."""
        # Ask LLM to extract structured fields
        parse_result = await self._llm.generate_json(
            prompt=(
                "从以下用户输入中提取策划案项目需求信息，返回 JSON：\n"
                "字段：company_name（客户企业名称）, industry（行业）, "
                "project_type（项目类型：幕墙/展厅/文旅/多媒体）, "
                "project_description（项目描述）, key_requirements（核心需求列表）, "
                "target_audience（目标受众）, budget_range（预算范围）, "
                "timeline（期望工期）, constraints（特殊约束）, "
                "missing_fields（仍然缺失的字段名列表）\n\n"
                f"用户输入：{user_input}\n\n"
                f"当前已收集的需求：{json.dumps(ctx.requirement.to_dict(), ensure_ascii=False)}"
            ),
            system_prompt=(
                "你是一个策划案项目需求分析助手。"
                "从用户自然语言中提取结构化需求字段。"
                "只返回 JSON，不要额外解释。"
            ),
        )

        # Merge parsed fields
        for key in RequirementInfo._MERGEABLE_FIELDS:
            val = parse_result.get(key)
            if val is not None:
                ctx.requirement.merge_field(key, val)
        if parse_result.get("key_requirements"):
            ctx.requirement.merge_field("key_requirements", parse_result["key_requirements"])

        # Check if we still need more info
        missing = ctx.requirement.get_missing_critical_fields()
        if missing and ctx.should_ask_more():
            ctx.ask_round += 1
            ctx.missing_info = missing
            yield _sse_chunk("text_delta", text="请补充关键信息：")
            yield _sse_chunk(
                "parameter_card",
                data={
                    "missing_fields": [
                        {
                            "field": f,
                            "label": FIELD_LABELS.get(f, f),
                            "options": FIELD_OPTIONS.get(f, []),
                        }
                        for f in missing
                    ],
                },
            )
            yield _sse_chunk("done")
            return

        # Enough info — detect domain and run pipeline
        ctx.domain = self._infer_domain(ctx.requirement)
        async for chunk in self._run_full_pipeline(ctx, db):
            yield chunk

    # ------------------------------------------------------------------
    # REVIEWING handler
    # ------------------------------------------------------------------

    async def _handle_reviewing(
        self,
        user_input: str,
        ctx: ProposalContext,
        db: Optional[Any],
    ) -> AsyncGenerator[str, None]:
        """Detect user intent: satisfied / modify / restart."""
        intent_result = await self._llm.generate_json(
            prompt=(
                "判断用户对当前策划案的意图，返回 JSON：\n"
                '{"intent": "satisfied" | "modify" | "restart", '
                '"modifications": {"field": "value", ...}, '
                '"reason": "解释"}\n\n'
                f"用户输入：{user_input}"
            ),
            system_prompt=(
                "你是一个意图识别助手。用户正在审核一份 AI 生成的策划案。\n"
                '- 如果用户表示满意/确认/可以了，intent 为 "satisfied"\n'
                '- 如果用户要求修改某些章节或内容，intent 为 "modify"，并在 modifications 中提取修改要求\n'
                '- 如果用户要求完全重来，intent 为 "restart"'
            ),
        )

        intent = intent_result.get("intent", "modify")

        if intent == "satisfied":
            ctx.state = "COMPLETED"
            # Build handoff data for VisualConceptAgent
            ctx.output_for_next_agent = self._build_handoff(ctx)
            yield _sse_chunk("text_delta", text="✅ 策划案已确认完成。正在进入视觉创意阶段…")
            yield _sse_chunk("artifact_summary", data={"proposal_confirmed": True, "domain": ctx.domain})
            yield _sse_chunk("done")
            return

        if intent == "restart":
            ctx.state = "COLLECTING"
            ctx.requirement = RequirementInfo()
            ctx.ask_round = 0
            ctx.missing_info = []
            ctx.company_analysis = None
            ctx.proposal_content = None
            ctx.quality_check = None
            yield _sse_chunk("text_delta", text="好的，让我们重新开始。请描述您的项目需求。")
            yield _sse_chunk("done")
            return

        # modify — re-generate from GENERATING step
        modifications = intent_result.get("modifications", {})
        if modifications:
            ctx.requirement.constraints = (
                f"{ctx.requirement.constraints or ''}\n用户修改意见：{json.dumps(modifications, ensure_ascii=False)}"
            ).strip()

        yield _sse_chunk("text_delta", text="正在根据您的反馈重新生成策划案…")
        async for chunk in self._run_full_pipeline(ctx, db, skip_analyzing=True):
            yield chunk

    # ------------------------------------------------------------------
    # Full generation pipeline
    # ------------------------------------------------------------------

    async def _run_full_pipeline(
        self,
        ctx: ProposalContext,
        db: Optional[Any],
        skip_analyzing: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Execute ANALYZING → GENERATING → REVIEWING sequence."""

        # --- ANALYZING ---
        if not skip_analyzing:
            ctx.state = "ANALYZING"
            yield _sse_chunk(
                "skill_progress",
                data={"skill_id": "company_analysis", "status": "running", "message": "正在分析企业信息…"},
            )
            try:
                analysis = await self._run_company_analysis(ctx, db)
                ctx.company_analysis = analysis
                # Track citations
                ctx.used_documents = analysis.get("used_documents", [])
                ctx.used_chunks = analysis.get("used_chunks", [])
            except Exception as e:
                logger.warning("Company analysis failed in ProposalAgent: %s", e)
                ctx.company_analysis = {"error": str(e)}

            # RAG retrieval
            try:
                context_pack = await self._run_rag_retrieval(ctx, db)
                ctx.context_pack_text = context_pack
            except Exception as e:
                logger.warning("RAG retrieval failed in ProposalAgent: %s", e)
                ctx.context_pack_text = None

            yield _sse_chunk(
                "skill_progress",
                data={"skill_id": "company_analysis", "status": "completed"},
            )

        # --- GENERATING ---
        ctx.state = "GENERATING"
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "proposal_generation", "status": "running", "message": "正在生成策划案…"},
        )
        try:
            proposal_result = await self._run_proposal_generation(ctx, db)
            ctx.proposal_content = proposal_result.get("content", "")
            ctx.missing_info_from_proposal = proposal_result.get("missing_info", [])
            ctx.used_cases = proposal_result.get("used_cases", [])
        except Exception as e:
            logger.exception("Proposal generation failed in ProposalAgent")
            yield _sse_chunk("error", text=f"策划案生成失败：{e}")
            yield _sse_chunk("done")
            return

        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "proposal_generation", "status": "completed"},
        )

        # Quality self-check
        try:
            quality = await self._quality_check(ctx)
            ctx.quality_check = quality
        except Exception as e:
            logger.warning("Quality check failed: %s", e)
            ctx.quality_check = {"items": [{"item": "质量检查", "status": "⚠️", "note": f"检查失败：{e}"}]}

        # Emit proposal content
        yield _sse_chunk(
            "content_block_start",
            data={"block_type": "proposal_section"},
        )
        yield _sse_chunk(
            "content_block_data",
            data={
                "type": "proposal_section",
                "data": {
                    "content": ctx.proposal_content,
                    "missing_info": ctx.missing_info_from_proposal,
                    "sections": self._extract_section_titles(ctx.proposal_content),
                    "used_cases": ctx.used_cases,
                    "quality_check": ctx.quality_check,
                },
            },
        )
        yield _sse_chunk("content_block_end")

        # --- REVIEWING ---
        ctx.state = "REVIEWING"
        yield _sse_chunk(
            "action_buttons",
            data={
                "buttons": [
                    {"label": "确认策划案", "action": "satisfied"},
                    {"label": "需要修改", "action": "modify"},
                    {"label": "重新开始", "action": "restart"},
                ],
            },
        )
        yield _sse_chunk("done")

    # ------------------------------------------------------------------
    # Internal methods — call existing Skills via SkillRunner
    # ------------------------------------------------------------------

    async def _run_company_analysis(self, ctx: ProposalContext, db) -> Dict[str, Any]:
        """Call company_analysis skill via SkillRunner."""
        from app.skills.registry import SkillRegistry
        from app.skills.runner import SkillRunner
        from app.skills.base import SkillContext

        registry = SkillRegistry.get_instance()
        if not registry.list_skills():
            registry.auto_register()
        runner = SkillRunner(registry)

        skill_ctx = SkillContext(
            db=db,
            llm_service=self._llm,
            embedding_service=self._embedding,
        )

        input_data = {
            "company_info": ctx.requirement.raw_input,
            "company_name": ctx.requirement.company_name or "",
            "user_message": ctx.requirement.raw_input,
        }

        result = await runner.run("company_analysis", input_data, skill_ctx)
        if result.get("success"):
            return result.get("output", {})
        raise RuntimeError(result.get("error", "company_analysis failed"))

    async def _run_rag_retrieval(self, ctx: ProposalContext, db) -> Optional[str]:
        """Retrieve RAG context (cases + knowledge chunks) for proposal generation.

        In conversation mode (no project_id), uses the tool registry to search
        cases and knowledge chunks directly.
        """
        if db is None:
            return None
        try:
            from app.tools.registry import ToolRegistry
            from app.tools.base import ToolContext

            tool_ctx = ToolContext(db=db, embedding_service=self._embedding)
            registry = ToolRegistry.get_instance()

            query = ctx.requirement.raw_input
            context_parts = []
            used_cases: List[str] = []
            used_chunks: List[str] = []
            used_docs: List[str] = []

            # Retrieve similar cases
            try:
                case_tool = registry.get("case_search")
                if case_tool:
                    cases = await case_tool.execute({"query": query, "limit": 3}, tool_ctx)
                    if isinstance(cases, list):
                        for c in cases:
                            if isinstance(c, dict):
                                title = c.get("title") or c.get("name", "")
                                if title:
                                    used_cases.append(title)
                                    summary = c.get("summary") or c.get("solution_summary", "")
                                    context_parts.append(f"案例：{title}\n{summary}")
            except Exception as e:
                logger.warning("Case search failed: %s", e)

            # Retrieve knowledge chunks
            try:
                ktool = registry.get("knowledge_search")
                if ktool:
                    chunks = await ktool.execute({"query": query, "limit": 5}, tool_ctx)
                    if isinstance(chunks, list):
                        for ch in chunks:
                            if isinstance(ch, dict):
                                text = ch.get("chunk_text") or ch.get("text", "")
                                if text:
                                    used_chunks.append(ch.get("chunk_id", ""))
                                    if ch.get("document_title"):
                                        used_docs.append(ch["document_title"])
                                    context_parts.append(f"知识片段：{text[:500]}")
            except Exception as e:
                logger.warning("Knowledge search failed: %s", e)

            ctx.used_cases = used_cases
            ctx.used_documents = list(set(used_docs))
            ctx.used_chunks = used_chunks

            return "\n\n".join(context_parts) if context_parts else None
        except Exception:
            logger.warning("RAG retrieval failed in ProposalAgent", exc_info=True)
            return None

    async def _run_proposal_generation(self, ctx: ProposalContext, db) -> Dict[str, Any]:
        """Call proposal_generation skill via SkillRunner."""
        from app.skills.registry import SkillRegistry
        from app.skills.runner import SkillRunner
        from app.skills.base import SkillContext

        registry = SkillRegistry.get_instance()
        if not registry.list_skills():
            registry.auto_register()
        runner = SkillRunner(registry)

        skill_ctx = SkillContext(
            db=db,
            llm_service=self._llm,
            embedding_service=self._embedding,
        )

        input_data = {
            "requirement_text": ctx.requirement.raw_input,
            "company_profile": ctx.company_analysis,
            "context_pack": ctx.context_pack_text,
            "user_message": ctx.requirement.raw_input,
            "domain": ctx.domain,
            "screen_info": ctx.screen_info,
        }

        result = await runner.run("proposal_generation", input_data, skill_ctx)
        if result.get("success"):
            return result.get("output", {})
        raise RuntimeError(result.get("error", "proposal_generation failed"))

    async def _quality_check(self, ctx: ProposalContext) -> Dict[str, Any]:
        """LLM-based quality self-check on the generated proposal."""
        items = await self._llm.generate_json(
            prompt=(
                "对以下策划案进行质量自检，返回 JSON：\n"
                '{"items": [{"item": "检查项名称", "status": "✅" | "⚠️", "note": "说明"}]}\n\n'
                "检查维度：\n"
                "1. 需求理解准确性\n"
                "2. 企业画像完整性\n"
                "3. 创意主题明确性\n"
                "4. 方案可行性\n"
                "5. 信息缺失检查\n"
                "6. 引用来源可追溯性\n\n"
                f"策划案内容（前2000字）：\n{(ctx.proposal_content or '')[:2000]}"
            ),
            system_prompt="你是策划案质量审核专家。严格检查，发现问题用 ⚠️ 标注。只返回 JSON。",
        )
        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_domain(requirement: RequirementInfo) -> str:
        """Infer business domain from requirement fields."""
        text = f"{requirement.project_type or ''} {requirement.project_description or ''} {requirement.raw_input}"
        domain_keywords = {
            "exhibition": ["展厅", "展陈", "展馆", "博物馆", "规划馆", "科技馆", "党建馆"],
            "culture_tourism": ["文旅", "夜游", "沉浸式体验", "光影秀", "景区", "主题公园"],
            "multimedia": ["互动装置", "数字沙盘", "AR", "VR", "多媒体", "体感交互"],
            "curtain_wall": ["幕墙", "LED", "裸眼3D", "媒体立面", "3D展示", "户外大屏"],
        }
        scores = {d: sum(1 for kw in kws if kw in text) for d, kws in domain_keywords.items()}
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        return best if scores[best] > 0 else "curtain_wall"

    @staticmethod
    def _build_handoff(ctx: ProposalContext) -> Dict[str, Any]:
        """Build structured data for VisualConceptAgent to consume."""
        req = ctx.requirement
        analysis = ctx.company_analysis or {}

        # Extract visual direction from analysis or requirement
        visual_direction = ""
        if isinstance(analysis, dict):
            visual_direction = analysis.get("recommended_visual_direction", "")
            if not visual_direction:
                # Try to derive from analysis overview
                overview = analysis.get("analysis", {})
                if isinstance(overview, dict):
                    visual_direction = overview.get("recommend_visual_direction", "")

        # Map project_type to scene
        scene_map = {
            "curtain_wall": "品牌发布会",
            "exhibition": "企业展厅",
            "culture_tourism": "文旅夜游",
            "multimedia": "多媒体展项",
        }

        return {
            "proposal_content": ctx.proposal_content,
            "company_analysis": ctx.company_analysis,
            "visual_direction": visual_direction or f"{req.project_type or '综合'}项目视觉方案",
            "scene": scene_map.get(ctx.domain, req.project_type or "品牌发布会"),
            "visual_style": req.project_type or "科技感",
            "brand_or_theme": req.company_name or "",
            "target_audience": req.target_audience or "",
            "key_elements": req.key_requirements or [],
            "domain": ctx.domain,
            "color_tone": "",
            "constraints": req.constraints or "",
        }

    @staticmethod
    def _extract_section_titles(content: Optional[str]) -> List[Dict[str, Any]]:
        """Extract ## headings from markdown content."""
        if not content:
            return []
        sections = []
        for line in content.split("\n"):
            if line.startswith("## "):
                title = line[3:].strip()
                sections.append({"title": title, "status": "draft"})
        return sections

    @staticmethod
    async def _load_screen_info(project_id: str, db) -> Optional[Dict[str, Any]]:
        """Load venue & screen params from the project, if any."""
        try:
            import uuid as _uuid
            from app.models.project import Project

            project = await db.get(Project, _uuid.UUID(project_id))
            return project.screen_info if project else None
        except Exception:
            logger.warning("Failed to load screen_info for %s", project_id, exc_info=True)
            return None

    @staticmethod
    async def _load_project_context(project_id: str, db) -> Optional[Dict[str, Any]]:
        """Load project info for auto-filling requirement fields."""
        try:
            import uuid as _uuid
            from sqlalchemy import select
            from app.models.project import Project
            from app.models.company import Company

            result = await db.execute(
                select(Project, Company)
                .join(Company, Project.company_id == Company.id, isouter=True)
                .where(Project.id == _uuid.UUID(project_id))
            )
            row = result.first()
            if not row:
                return None

            project, company = row
            auto_filled: Dict[str, str] = {}
            if company and company.name:
                auto_filled["company_name"] = company.name
            if company and company.industry:
                auto_filled["industry"] = company.industry
            if project and project.description:
                auto_filled["project_description"] = project.description

            return {
                "project_name": project.name if project else "",
                "company_name": company.name if company else "",
                "auto_filled": auto_filled,
            }
        except Exception:
            logger.warning("Failed to load project context for %s", project_id, exc_info=True)
            return None
