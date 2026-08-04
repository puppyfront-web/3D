"""Canvas agent orchestrator — fills canvas nodes via LLM and records NodeSources.

This is the phase-2 AI-fill loop. For each board group it runs **two LLM
passes**:

1. **Extract** — from the company record + web_search hits + uploaded
   materials, extract concrete enterprise *facts* (data points, years,
   events, quotes) per node → ``content.extracted``. Nothing may be
   fabricated; if a node has no source material, its ``extracted`` stays empty.
2. **Plan** — *only* grounded in the extracted facts, draft concise pre-sales
   copy usable in a proposal → ``content.planning``. Nodes whose ``extracted``
   is empty get no ``planning`` and instead a ``pending_questions`` entry
   asking the user to supply the missing material; their status becomes
   ``pending_review`` so the export gate can flag them.

This separation keeps the canvas showing **real enterprise facts** (e.g.
"华为 2023 研发投入 1647 亿元") rather than vague advisory text (e.g.
"建议提炼为：以创新为核心的精神…"), per AGENTS.md §4.1/§4.3 and the §5 ban
on fabricated content.

Design choices (phase 2 MVP):
  - **Lightweight direct-LLM fill** rather than wrapping the existing
    proposal_generation / company_analysis skills. Those skills emit markdown
    artefacts shaped for the chat workspace; mapping them onto 20 individual
    nodes is brittle. A focused per-group LLM call is more controllable and
    unit-testable with the mock LLM. The existing skills remain available for
    the chat workspace; a skill-wrapping path can be added later behind the
    same orchestrator interface.
  - **Per-group fan-out** (company_intro / product_tech_scenarios /
    future_social_responsibility) so a single failure degrades only one board.
    Each group now costs 2 LLM calls (extract + plan); 3 groups → 6 calls.
  - **NodeSource materialisation**: every filled node gets ≥1 NodeSource row
    so provenance is queryable (GAP-2 from the audit). Source type is
    ``ai_completed`` by default; if web_search results are passed in they're
    recorded as ``web_search`` sources with confidence=medium and the snippet
    as the quote.

Run model: BackgroundTasks + DB status polling (decision: no Redis queue in
MVP). The router creates a SkillExecution row (status=running) and dispatches
this orchestrator; on completion it flips status and records node_ids.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canvas import CanvasNode, NodeSource, ProjectVersion
from app.models.project import Company, Project
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# Map each board group to (a) the node_keys it owns and (b) a prompt hint.
# Node keys mirror canvas_service._DEFAULT_GROUPS.
_GROUP_NODE_KEYS: Dict[str, List[str]] = {
    "company_intro": [
        "company_profile", "company_scale", "development_history",
        "honors_qualifications", "enterprise_spirit", "team_capability", "core_value",
    ],
    "product_tech_scenarios": [
        "product_system", "technology_capability", "application_scenarios",
        "typical_cases", "solutions", "delivery_capability", "customer_value",
    ],
    "future_social_responsibility": [
        "future_layout", "development_strategy", "social_responsibility",
        "public_welfare", "party_building", "sustainable_development", "brand_vision",
    ],
}

_GROUP_PROMPT_INTENT: Dict[str, str] = {
    "company_intro": "企业基本情况、规模、发展历程、荣誉资质、团队与核心价值",
    "product_tech_scenarios": "核心产品体系、技术能力、应用场景、典型案例与客户价值",
    "future_social_responsibility": "未来战略布局、社会责任、可持续发展和品牌愿景",
}


class CanvasAgentOrchestrator:
    """Fills canvas nodes for a project version via LLM, with provenance."""

    async def fill_canvas(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        web_search_results: Optional[List[Dict[str, Any]]] = None,
        extra_context: Optional[str] = None,
        document_context: Optional[str] = None,
        document_sources: Optional[List[Dict[str, Any]]] = None,
        stage: str = "full",
    ) -> Dict[str, Any]:
        """Fill all draft nodes on the version's canvas.

        Returns a summary: {filled_count, skipped_count, errors, node_ids}.
        Idempotent: only nodes with status in {draft, pending_review} are
        (re)filled; already-filled nodes are skipped unless force=True.

        `extra_context` carries the user's free-text requirement from the chat
        (e.g. "华为通信历史演进") so the LLM fills nodes against the real
        enterprise need rather than just the (possibly empty) Company record.

        `stage` controls which agents run, so the frontend can re-trigger a
        single stage on demand (PRD §13):
          - "full"         → document_parse + requirement + planner + consistency + tone + ui_expert (default)
          - "ui_expert"    → UI 专家 only (re-run the UI pass without redoing extract/plan)
          - "tone"         → 方案定调 only
          - "consistency"  → 一致性检查 only (re-run the cross-board review)

        Stage order matters: consistency runs BEFORE tone/ui so the downstream
        agents reason over consistency-amended copy (issues flow back as
        pending_questions on the flagged nodes — PRD §13.2 step 8 → 9).

        On a ``full`` run, each stage also consults the workflow manifest
        (active SOPWorkflow bound to agent="canvas") — an admin can disable a
        stage there without code changes (CLAUDE.md §3.2 / §12.6). Explicit
        single-stage triggers always run regardless.
        """
        project = await db.get(Project, project_id)
        if project is None:
            return {"success": False, "error": f"Project not found: {project_id}"}

        company = await db.get(Company, project.company_id) if project.company_id else None
        company_context = self._company_context(
            company, project, extra_context, document_context
        )

        # Load all nodes for this version's canvas.
        nodes = await self._load_nodes(db, version_id)
        if not nodes:
            return {"success": False, "error": "No canvas nodes found for version"}

        llm = await get_llm_service(db)
        filled: List[str] = []
        errors: List[str] = []

        # Group nodes by their group_key (resolved via the node's group).
        nodes_by_group = await self._group_nodes_by_board(db, nodes)

        # ── Load internal knowledge (SOP / cases / RAG) via ToolRegistry ──
        # PRD §23.5.4: the AI can invoke internal SOP, cases and templates for
        # the canvas path too, not only in the chat skills. This is best-effort
        # and degrades silently if ToolRegistry / a tool / the db is unavailable
        # — the orchestrator must never fail because a tool is missing.
        internal_knowledge_context, ik_sources = await self._load_internal_knowledge(
            db, company, nodes_by_group
        )

        # ── Workflow manifest (CLAUDE.md §12.6 — stage toggle is configurable) ──
        # On a `full` run, each stage checks the manifest before executing: an
        # admin disables a stage by flipping `enabled=false` on the active
        # SOPWorkflow bound to agent="canvas". No such SOP / empty stages ⇒
        # everything enabled (backward compatible). Explicit single-stage
        # triggers (stage=<id>) ALWAYS run — the user asked for that stage
        # directly, the manifest must not silently veto it.
        manifest = await self._load_workflow_manifest(db) if stage == "full" else None

        def _stage_on(stage_id: str) -> bool:
            return (manifest is None) or manifest.get(stage_id, True)

        def _should_run(stage_id: str) -> bool:
            """Full-flow gate: explicit trigger OR (full AND manifest-on)."""
            return stage == stage_id or (stage == "full" and _stage_on(stage_id))

        # ── Assemble the structured Context Pack (PRD §9.3) ──
        # Captures EVERYTHING the agents reasoned over — enterprise profile,
        # project requirement, matched cases, referenced docs/chunks, SOP,
        # web + uploaded material — so the generation is traceable and the
        # version snapshot can replay it. Persisted onto layout_config after
        # the stages finish (a single source of truth the frontend renders).
        context_pack = self._build_context_pack(
            company, project, extra_context, document_context,
            web_search_results, document_sources, ik_sources,
        )

        # ── Stage -1: 资料解析 Agent (PRD §13.2 step 2 / §11.2) ──
        # Auto-classify the project's uploaded documents into the 9 PRD
        # categories and extract a per-doc summary, so the planner can cite
        # each board's relevant material by category instead of a flat blob.
        # Only fills category when the user hasn't set one (never overwrites a
        # manual classification). Soft-fails: a parse error never blocks.
        if _should_run("document_parse"):
            try:
                doc_analyses = await self._parse_project_documents(db, project_id, llm)
                if doc_analyses:
                    context_pack["document_analyses"] = doc_analyses
                    # also surface new analyses in uploaded_materials so the
                    # traceability drawer lists every parsed doc, not just the
                    # ones the chat path referenced via [ref_doc:].
                    existing_ids = {
                        u.get("document_id") for u in context_pack.get("uploaded_materials", [])
                    }
                    for analysis in doc_analyses:
                        if analysis["document_id"] not in existing_ids:
                            context_pack.setdefault("uploaded_materials", []).append({
                                "document_id": analysis["document_id"],
                                "title": analysis["title"],
                                "category": analysis["category"],
                                "excerpt": analysis["summary"][:240],
                            })
            except Exception as e:
                logger.exception("document parse failed")
                errors.append(f"document_parse: {e}")

        # ── Stage 0: 需求采集 Agent (PRD §13.2 step 1) ──
        # Structured-extract the user's free-text requirement into scene /
        # goal / audience / key_asks, and flag missing critical info. Runs
        # before the planner so the boards fill against a clarified intent,
        # and its output merges into context_pack.project_requirement +
        # pending_info (the traceability record + the export gate consume
        # those). Soft-fails: a parse error never blocks the fill.
        if _should_run("requirement") and company_context != self._NO_DATA_SENTINEL:
            try:
                req = await self._collect_requirement(
                    llm, company_context, extra_context,
                )
                if req:
                    # Merge LLM-extracted fields under the ORM-seeded requirement.
                    pr = dict(context_pack.get("project_requirement") or {})
                    for k in ("scene", "goal", "audience", "key_asks"):
                        v = req.get(k)
                        if v:
                            pr[k] = v
                    context_pack["project_requirement"] = pr
                    # Missing critical fields → pending_info (export gate flags).
                    pending = list(context_pack.get("pending_info") or [])
                    for m in (req.get("missing_info") or []):
                        if m and m not in pending:
                            pending.append(m)
                    if pending:
                        context_pack["pending_info"] = pending
            except Exception as e:
                logger.exception("requirement collection failed")
                errors.append(f"requirement: {e}")

        # ── Stage 1: 策划专家 — extract facts + draft planning copy per board ──
        # The three boards are independent, so their LLM passes run concurrently
        # via asyncio.gather (the expensive IO — 2 LLM calls per board).
        # DB writes (_apply_group_result) stay serial on this shared session.
        if _should_run("planner"):
            import asyncio as _asyncio

            group_items = [
                (gk, intent, nodes_by_group.get(gk, []))
                for gk, intent in _GROUP_PROMPT_INTENT.items()
                if nodes_by_group.get(gk, [])  # skip empty boards
            ]

            async def _run_one(gk: str, intent: str, group_nodes: List[CanvasNode]):
                try:
                    res = await self._run_group_llm_passes(
                        llm, gk, intent, group_nodes,
                        company_context, web_search_results,
                        internal_knowledge_context,
                    )
                    return gk, group_nodes, res, None
                except Exception as e:  # noqa: BLE001 — surface to apply phase
                    logger.exception("Fill failed for group %s", gk)
                    return gk, group_nodes, None, e

            gathered = await _asyncio.gather(
                *[_run_one(gk, intent, gnodes) for gk, intent, gnodes in group_items]
            )

            # Apply serially on the shared session (DB writes are not the
            # bottleneck; LLM IO already overlapped above).
            for gk, group_nodes, res, err in gathered:
                if err is not None:
                    errors.append(f"{gk}: {err}")
                    for n in group_nodes:
                        n.status = "pending_review"
                    continue
                self._apply_group_result(db, gk, group_nodes, res)
                filled.extend(n.id for n in group_nodes)

            # Materialise web_search NodeSources onto company_intro nodes (if any).
            if web_search_results:
                await self._attach_web_sources(db, nodes_by_group.get("company_intro", []), web_search_results)
            if document_sources:
                await self._attach_document_sources(
                    db, nodes_by_group.get("company_intro", []), document_sources
                )
            # Record provenance for internal-knowledge hits (SOP/cases/RAG).
            # PRD §15.1: every board's node detail should surface the internal
            # knowledge it referenced, so we attach to each board's anchor
            # (the first filled node), not just company_intro.
            if ik_sources:
                await self._attach_internal_sources(
                    db, nodes_by_group, ik_sources
                )

        # Collect planning copy once — consistency, tone and UI all reason over
        # it. Recomputed AFTER consistency so downstream stages see the
        # consistency-amended pending_questions too (回流: PRD §13.2 step 8 → 9).
        planning_payload = self._collect_planning(nodes_by_group)

        # ── Stage 2: 一致性检查 Agent — cross-board consistency review (PRD
        # §13.2 step 8). Runs RIGHT AFTER the planner and BEFORE tone/UI so the
        # downstream stages reason over consistency-amended copy. Each issue is
        # appended to the offending node's ``pending_questions`` and the node is
        # demoted to pending_review, so tone/UI see the flagged text and the
        # export gate can surface it. Soft-fails: a checker error never blocks.
        consistency_issues: List[Dict[str, Any]] = []
        if _should_run("consistency") and planning_payload:
            try:
                consistency_issues = await self._run_consistency_check(
                    db, llm, company_context, nodes_by_group, planning_payload,
                )
                if consistency_issues:
                    canvas_c = await self._load_canvas(db, version_id)
                    if canvas_c is not None:
                        layout_c = dict(canvas_c.layout_config or {})
                        layout_c["consistency_issues"] = consistency_issues
                        canvas_c.layout_config = layout_c
                    # Recompute planning_payload so tone/UI below ingest the
                    # consistency-amended pending_questions (回流).
                    planning_payload = self._collect_planning(nodes_by_group)
            except Exception as e:
                logger.exception("Consistency check failed")
                errors.append(f"consistency: {e}")

        # ── Stage 3: 方案定调 Agent — synthesize project-level style/tone from
        # the (consistency-amended) planning copy. Only runs when at least one
        # node has planning content; otherwise the canvas is mostly empty and
        # there is nothing to set a tone against (PRD §13.4). Tone is stored on
        # the canvas's layout_config so it flows to the frontend and is captured
        # by the version snapshot with no schema change.
        tone: Optional[Dict[str, Any]] = None
        if _should_run("tone") and planning_payload:
            try:
                tone = await self._generate_tone(llm, company_context, planning_payload)
            except Exception as e:
                logger.exception("Tone generation failed")
                errors.append(f"tone: {e}")
        elif stage == "ui_expert":
            # UI-only re-run: reuse the tone already stored on the canvas so the
            # UI advice stays consistent with the prior tone (don't regenerate).
            canvas_existing = await self._load_canvas(db, version_id)
            if canvas_existing is not None:
                tone = (canvas_existing.layout_config or {}).get("tone")
        if tone and stage in ("full", "tone"):
            canvas = await self._load_canvas(db, version_id)
            if canvas is not None:
                layout = dict(canvas.layout_config or {})
                layout["tone"] = tone
                canvas.layout_config = layout

        # ── Stage 4: UI 专家 Agent — per-board UI expression advice, grounded
        # in each node's planning copy and the project tone (PRD §13.5). Fills
        # ``content.ui_suggestion`` only on nodes that already have planning
        # content; empty nodes stay untouched (no fabrication). In "ui_expert"
        # mode this degrades to use ``extracted`` content when planning is empty,
        # so a node can still get UI advice even if the planner pass hasn't run.
        if _should_run("ui_expert"):
            try:
                await self._generate_ui_suggestions(
                    db, llm, nodes_by_group, tone,
                    allow_extracted_fallback=(stage == "ui_expert"),
                )
            except Exception as e:
                logger.exception("UI suggestion generation failed")
                errors.append(f"ui_suggestion: {e}")
            if stage == "ui_expert":
                filled.extend(n.id for n in nodes)

        await db.flush()

        # ── Persist the Context Pack onto the canvas (PRD §9.3 traceability) ──
        # Stored on layout_config.context_pack so it (a) flows to the frontend
        # for the traceability panel and (b) is captured by the next version
        # snapshot. Best-effort: a canvas reload failure never blocks the fill.
        #
        # Merge semantics: a sub-stage run (ui_expert / tone / consistency /
        # requirement / document_parse) is invoked by _run_fill_background with
        # web_search_results=None and document_sources=None, so the freshly
        # assembled pack would have empty web_references / uploaded_materials.
        # Overwriting with that would ERASE the traceability record an earlier
        # `full` run captured. So: `full` overwrites; any sub-stage merges into
        # the existing pack (non-empty new fields win, empty fields keep prior).
        try:
            canvas_cp = await self._load_canvas(db, version_id)
            if canvas_cp is not None:
                layout_cp = dict(canvas_cp.layout_config or {})
                if stage == "full":
                    final_pack = context_pack
                else:
                    existing = layout_cp.get("context_pack") or {}
                    final_pack = self._merge_context_pack(existing, context_pack)
                layout_cp["context_pack"] = final_pack
                canvas_cp.layout_config = layout_cp
        except Exception:
            logger.exception("context_pack: failed to persist onto canvas")

        # Count nodes that are already filled (not draft/pending_review) so the
        # skipped_count reflects reality (Defect #10: was always 0).
        already_filled = sum(
            1 for n in nodes if n.status not in ("draft", "pending_review")
        )

        # Distinguish hard failures (planner stage couldn't fill any node) from
        # soft failures (tone/UI sub-agents failed but nodes were filled).
        # Previously any soft error flipped success to False, making the frontend
        # report failure even when 19/20 nodes filled correctly (Defect #10).
        planner_errors = [
            e for e in errors if not e.startswith(
                ("tone:", "ui_suggestion:", "consistency:", "requirement:", "document_parse:")
            )
        ]
        soft_errors = [
            e for e in errors if e.startswith(
                ("tone:", "ui_suggestion:", "consistency:", "requirement:", "document_parse:")
            )
        ]
        # has_filled gates `success`. A `full` run is considered productive as
        # long as it didn't hard-fail — the manifest may have disabled planner
        # (admin's choice), and the context pack / requirement / document_parse
        # stages still ran. Explicit sub-stage triggers count their own output.
        has_filled = (
            len(filled) > 0
            or stage == "full"
            or stage in (
                "tone", "ui_expert", "consistency", "requirement", "document_parse",
            )
        )

        return {
            "success": has_filled and len(planner_errors) == 0,
            "filled_count": len(filled),
            "skipped_count": already_filled,
            "errors": errors,
            "soft_errors": soft_errors,
            "node_ids": [str(nid) for nid in filled],
            "tone_generated": bool(tone),
            "consistency_issues": consistency_issues,
            "stage": stage,
        }

    # ─── Internals ────────────────────────────────────────────────────────

    # Sentinel returned by _company_context when no usable source material is
    # available at all. _run_group_llm_passes checks for this and, when present, skips
    # both LLM passes — every node in the group is marked pending_review with a
    # "please supply material" entry in pending_questions, so we never emit
    # fabricated content (AGENTS.md §4.3, §5).
    _NO_DATA_SENTINEL = "__NO_ENTERPRISE_DATA__"

    def _company_context(
        self,
        company: Optional[Company],
        project: Project,
        extra_context: Optional[str] = None,
        document_context: Optional[str] = None,
    ) -> str:
        parts: List[str] = []
        if company:
            if company.name:
                parts.append(f"企业名称：{company.name}")
            if company.industry:
                parts.append(f"所属行业：{company.industry}")
            if company.website:
                parts.append(f"官网：{company.website}")
            if company.description:
                parts.append(f"简介：{company.description}")
        if project.description:
            parts.append(f"项目需求：{project.description}")
        # Free-text requirement from the chat (e.g. "华为通信历史演进").
        # Takes priority as the most direct signal of what the user wants.
        if extra_context and extra_context.strip():
            parts.append(f"用户需求：{extra_context.strip()}")
        if document_context and document_context.strip():
            parts.append(f"上传资料摘要：\n{document_context.strip()}")
        if not parts:
            # Signal to _run_group_llm_passes that there is nothing to extract from.
            return self._NO_DATA_SENTINEL
        return "\n".join(parts)

    # PRD §11.2 attachment categories — the canonical 9 the workspace tray
    # uses. The document-parse agent picks from this exact set so auto-classed
    # docs land in the same buckets a user would assign manually.
    _DOC_CATEGORIES: List[str] = [
        "企业介绍", "产品资料", "技术资料", "荣誉资质",
        "案例资料", "发展历程", "社会责任", "参考案例", "其他资料",
    ]

    async def _load_workflow_manifest(self, db: AsyncSession) -> Dict[str, bool]:
        """Load the canvas workflow manifest — the per-stage enable map.

        Source: the active ``SOPWorkflow`` row bound to ``agent="canvas"``;
        its ``pipeline_stages`` list carries ``{stage, enabled}`` entries the
        admin edits in the SOP management UI (CLAUDE.md §3.2 / §12.6 — expert
        capabilities must be configurable, not hardcoded).

        Returns ``{stage_id: enabled}``. Empty dict when no such SOP exists
        or it has no stages → the orchestrator treats "no manifest" as
        "all enabled" (``_stage_on`` defaults unknown stages to True), so the
        default behaviour is unchanged. Best-effort: any failure → empty map.
        """
        try:
            from app.models.workflow import SOPWorkflow

            result = await db.execute(
                select(SOPWorkflow)
                .where(
                    SOPWorkflow.bound_agent == "canvas",
                    SOPWorkflow.is_active.is_(True),
                )
                .limit(1)
            )
            sop = result.scalar_one_or_none()
            if sop is None or not sop.pipeline_stages:
                return {}
            return {
                str(s.get("stage")): bool(s.get("enabled", True))
                for s in sop.pipeline_stages
                if isinstance(s, dict) and s.get("stage")
            }
        except Exception:
            logger.exception("workflow manifest load failed — defaulting to all-on")
            return {}

    async def _parse_project_documents(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        llm: Any,
    ) -> List[Dict[str, Any]]:
        """资料解析 Agent — auto-classify + summarise the project's uploaded
        documents (PRD §13.2 step 2 / §11.2).

        For each parsed document the LLM picks one of the 9 PRD categories and
        writes a 1-2 sentence summary. The category is written back onto the
        Document row ONLY when the user hasn't set one (manual classification
        always wins). Returns a per-doc analysis list for the context pack.

        Degrades gracefully: no documents / unparseable LLM output / a single
        doc failure → that doc is skipped, never blocks the fill.
        """
        from app.models.document import Document, DocumentChunk

        # Load parsed documents for this project (status indexed means the
        # parser produced chunks). Cap to 10 to bound LLM cost.
        res = await db.execute(
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.status == "indexed",
            )
            .limit(10)
        )
        documents = list(res.scalars().all())
        if not documents:
            return []

        analyses: List[Dict[str, Any]] = []
        cat_list = " / ".join(self._DOC_CATEGORIES)
        for doc in documents:
            # Pull the first few chunks as the classification corpus.
            chunk_res = await db.execute(
                select(DocumentChunk.content)
                .where(DocumentChunk.document_id == doc.id)
                .order_by(DocumentChunk.chunk_index.asc())
                .limit(3)
            )
            corpus = "\n".join(
                (c or "").strip() for c in chunk_res.scalars() if (c or "").strip()
            )[:1200]
            if not corpus:
                continue

            title = doc.title or doc.original_filename or doc.filename
            prompt = (
                "你是企业3D数字化展示售前的资料解析专家。请判断下方资料属于哪个类别，"
                "并提炼1-2句摘要（用于后续售前方案生成引用）。\n\n"
                f"【资料标题】{title}\n"
                f"【资料正文（节选）】\n{corpus}\n\n"
                f"可选类别（必须从中选一个）：{cat_list}\n\n"
                "硬性约束：\n"
                "1. 仅基于资料正文判断，不得编造未出现的信息。\n"
                "2. 摘要要具体（含关键数据/产品/事件），不要空泛。\n\n"
                "请严格返回JSON："
                '{"category":"类别名(须在上列9类中)","summary":"1-2句摘要"}'
                "。不要返回任何其他文字、不要markdown代码块。"
            )
            try:
                raw = await llm.generate(prompt, temperature=0.2, max_tokens=400)
                parsed = self._parse_json_object(raw)
                category = parsed.get("category") if parsed else None
                summary = (parsed.get("summary") or "").strip() if parsed else ""
            except Exception:
                logger.exception("document parse failed for doc %s", doc.id)
                continue

            if category not in self._DOC_CATEGORIES:
                category = "其他资料"
            if not summary:
                summary = corpus[:120]

            # Write category back ONLY when the user hasn't set one.
            if not doc.category:
                doc.category = category

            analyses.append({
                "document_id": str(doc.id),
                "title": title,
                "filename": doc.original_filename,
                "category": category,
                "summary": summary,
            })
        return analyses

    async def _collect_requirement(
        self,
        llm: Any,
        company_context: str,
        extra_context: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """需求采集 Agent — structured-extract the project requirement (PRD
        §13.2 step 1 / §4.4).

        Parses the user's free-text requirement + the company record into
        structured fields the planner fills against (scene / goal / audience /
        key_asks), and lists any critical missing info that should be flagged
        to the user (never fabricated). Returns None on parse failure
        (soft-fail — the planner still runs on the raw context).

        Does NOT invent requirements not present in the source text; an empty
        extraction returns the fields as nulls so the caller can mark them
        pending rather than guessing.
        """
        prompt = (
            "你是企业3D数字化展示售前的需求采集专家。请从下方企业背景与用户需求中，"
            "**结构化抽取**本次方案的关键需求字段。严格基于已有信息，不得编造用户未提及的"
            "诉求；信息确实缺失时填 null 并在 missing_info 里说明。\n\n"
            f"【企业背景与用户需求】\n{company_context}\n\n"
            "请严格返回JSON，字段固定：\n"
            '{"scene":"应用场景(如企业展厅/裸眼3D幕墙/发布会,8-20字)",'
            '"goal":"展示目的(如品牌升级/产品发布/获客,8-20字)",'
            '"audience":"目标受众(如行业客户/政府/消费者,8-20字)",'
            '"key_asks":["关键诉求1","关键诉求2"],'
            '"missing_info":["缺失的关键信息(如预算/工期/场地尺寸)"]}\n'
            "不要返回任何其他文字、不要markdown代码块。"
        )
        raw = await llm.generate(prompt, temperature=0.2, max_tokens=600)
        parsed = self._parse_json_object(raw)
        if not parsed:
            return None
        # Normalise list-valued fields + drop empty strings → None.
        out: Dict[str, Any] = {}
        for k in ("scene", "goal", "audience"):
            v = parsed.get(k)
            out[k] = (str(v).strip() or None) if v else None
        asks = parsed.get("key_asks")
        if isinstance(asks, str):
            asks = [asks]
        out["key_asks"] = [str(a) for a in asks if a] if isinstance(asks, list) else []
        missing = parsed.get("missing_info")
        if isinstance(missing, str):
            missing = [missing]
        out["missing_info"] = (
            [str(m) for m in missing if m] if isinstance(missing, list) else []
        )
        return out

    def _build_context_pack(
        self,
        company: Optional[Company],
        project: Project,
        extra_context: Optional[str],
        document_context: Optional[str],
        web_search_results: Optional[List[Dict[str, Any]]],
        document_sources: Optional[List[Dict[str, Any]]],
        ik_sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Assemble the structured Context Pack (PRD §9.3).

        A plain dict (not the app.rag.context_pack.ContextPack class — that one
        serves the chat skills and renders to a prompt string; the orchestrator
        needs a traceability record that serializes onto layout_config). The
        shape mirrors PRD §9.3's mandated sections so the frontend can render
        them grouped and the version snapshot can replay what fed the fill.
        """
        # Enterprise profile (the "who").
        enterprise_profile: Dict[str, Any] = {}
        if company is not None:
            for f in ("name", "industry", "website", "description"):
                v = getattr(company, f, None)
                if v:
                    enterprise_profile[f] = v

        # Project requirement (the "what") — merge ORM fields + chat free-text.
        project_requirement: Dict[str, Any] = {}
        if project is not None:
            for f in ("name", "description", "status"):
                v = getattr(project, f, None)
                if v:
                    project_requirement[f] = v
        if extra_context and extra_context.strip():
            project_requirement["raw_input"] = extra_context.strip()
        if document_context and document_context.strip():
            project_requirement["uploaded_summary"] = document_context.strip()[:500]

        # Route internal-knowledge hits by source_type (SOP / case / RAG chunk).
        matched_cases: List[Dict[str, Any]] = []
        sop_checklist: List[Dict[str, Any]] = []
        referenced_chunks: List[Dict[str, Any]] = []
        prompt_templates: List[Dict[str, Any]] = []
        for src in ik_sources or []:
            stype = src.get("source_type") or ""
            entry = {
                "name": src.get("source_name"),
                "quote": src.get("quote"),
                "document_id": src.get("document_id"),
            }
            if stype == "internal_case":
                matched_cases.append(entry)
            elif stype == "internal_sop":
                sop_checklist.append(entry)
            elif stype == "internal_template":
                # RAG chunks carry a document_id; templates don't.
                if src.get("document_id"):
                    referenced_chunks.append(entry)
                else:
                    prompt_templates.append(entry)
            elif stype == "internal_ui":
                prompt_templates.append(entry)

        web_references = [
            {
                "title": h.get("title") or h.get("name"),
                "url": h.get("url") or h.get("link"),
                "snippet": (h.get("content") or h.get("snippet") or "")[:240],
            }
            for h in (web_search_results or [])
        ]
        uploaded_materials = [
            {
                "document_id": d.get("document_id"),
                "title": d.get("title") or d.get("filename"),
                "filename": d.get("filename"),
                "excerpt": (d.get("excerpt") or "")[:240],
            }
            for d in (document_sources or [])
        ]

        return {
            "enterprise_profile": enterprise_profile,
            "project_requirement": project_requirement,
            "matched_cases": matched_cases,
            "sop_checklist": sop_checklist,
            "referenced_chunks": referenced_chunks,
            "prompt_templates": prompt_templates,
            "web_references": web_references,
            "uploaded_materials": uploaded_materials,
            # Snapshot counts so the frontend can badge without deep parsing.
            "summary": {
                "cases": len(matched_cases),
                "chunks": len(referenced_chunks),
                "sop": len(sop_checklist),
                "web": len(web_references),
                "uploads": len(uploaded_materials),
            },
        }

    @staticmethod
    def _merge_context_pack(
        existing: Dict[str, Any], new: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge a sub-stage's freshly assembled pack into the existing one.

        Rule: per key, a non-empty new value wins; an empty new value keeps the
        prior value. This lets a `requirement`-only run overwrite
        project_requirement while preserving the web_references / uploaded
        materials an earlier `full` run captured (those arrive as [] when the
        sub-stage is invoked without web/document context). ``summary`` is
        rebuilt from whichever side has the richer lists (preferring new when
        non-empty). Enterprise_profile / project_requirement dicts merge
        field-by-field for the same reason.
        """
        merged: Dict[str, Any] = {}
        keys = set(existing) | set(new)
        for k in keys:
            ev = existing.get(k)
            nv = new.get(k)
            # Dict fields: shallow-merge so a sub-stage can add fields without
            # wiping the ones it didn't recompute.
            if isinstance(ev, dict) and isinstance(nv, dict):
                merged[k] = {**(ev or {}), **{kk: vv for kk, vv in nv.items() if vv}}
                continue
            # List / scalar: non-empty new wins, else existing, else new.
            if nv not in (None, "", [], {}):
                merged[k] = nv
            elif ev not in (None, "", [], {}):
                merged[k] = ev
            else:
                merged[k] = nv if nv is not None else ev
        return merged

    async def _load_nodes(self, db: AsyncSession, version_id: uuid.UUID) -> List[CanvasNode]:
        from app.models.canvas import Canvas

        result = await db.execute(
            select(CanvasNode)
            .join(Canvas, CanvasNode.canvas_id == Canvas.id)
            .where(Canvas.project_version_id == version_id)
        )
        return list(result.scalars().all())

    async def _group_nodes_by_board(
        self, db: AsyncSession, nodes: List[CanvasNode]
    ) -> Dict[str, List[CanvasNode]]:
        from app.models.canvas import CanvasGroup

        if not nodes:
            return {}
        group_ids = {n.group_id for n in nodes if n.group_id}
        group_key_map: Dict[uuid.UUID, str] = {}
        if group_ids:
            res = await db.execute(
                select(CanvasGroup.id, CanvasGroup.group_key).where(
                    CanvasGroup.id.in_(group_ids)
                )
            )
            group_key_map = {row[0]: row[1] for row in res.all()}

        out: Dict[str, List[CanvasNode]] = {}
        for n in nodes:
            gk = group_key_map.get(n.group_id) if n.group_id else None
            if gk:
                out.setdefault(gk, []).append(n)
        return out

    async def _run_group_llm_passes(
        self,
        llm: Any,
        group_key: str,
        intent: str,
        nodes: List[CanvasNode],
        company_context: str,
        web_search_results: Optional[List[Dict[str, Any]]],
        internal_knowledge: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run the two LLM passes for one board WITHOUT touching the DB.

        Returns a result dict ``{"extracted_map": {...}, "planning_map": {...}}``
        on success, ``None`` when the extract pass was unparseable, or the
        sentinel ``{"no_data": True}`` when there is no verified source
        material (caller marks every node pending_review). Pure of side
        effects — safe to run concurrently across the three boards.
        """
        # No source material at all → skip LLM, signal pending_review.
        # Internal knowledge alone is REFERENCE-only and must NOT unlock the
        # LLM: without verified enterprise data the model would fabricate, so
        # we still take the sentinel path when there is no company/web data.
        has_verified_source = (
            company_context != self._NO_DATA_SENTINEL or bool(web_search_results)
        )
        if not has_verified_source:
            return {"no_data": True}

        node_specs = [{"node_key": n.node_key, "title": n.title} for n in nodes]

        # ── Pass 1: extract concrete facts ──
        extract_prompt = self._build_extract_prompt(
            intent, node_specs, company_context, web_search_results,
            internal_knowledge,
        )
        raw_extract = await llm.generate(extract_prompt, temperature=0.2, max_tokens=2000)
        extracted_map = self._parse_fill_response(raw_extract, nodes)

        if not extracted_map:
            # Unparseable extract output → caller marks the group pending_review.
            return None

        # ── Pass 2: draft pre-sales copy, grounded ONLY on extracted facts ──
        plan_prompt = self._build_planning_prompt(intent, node_specs, extracted_map)
        raw_plan = await llm.generate(plan_prompt, temperature=0.4, max_tokens=2000)
        planning_map = self._parse_fill_response(raw_plan, nodes)

        return {"extracted_map": extracted_map, "planning_map": planning_map}

    def _apply_group_result(
        self,
        db: AsyncSession,
        group_key: str,
        nodes: List[CanvasNode],
        result: Optional[Dict[str, Any]],
    ) -> None:
        """Apply an LLM-pass result to the nodes + write NodeSource rows.

        Serial DB writes on the shared session — called once per board after
        the concurrent LLM passes have resolved.
        """
        # No-data sentinel → every node pending_review with a missing-material
        # question. Never fabricate.
        if isinstance(result, dict) and result.get("no_data"):
            for node in nodes:
                old = node.content or {}
                node.content = {
                    "extracted": list(old.get("extracted", [])),
                    "planning": list(old.get("planning", [])),
                    "ui_suggestion": list(old.get("ui_suggestion", [])),
                    "pending_questions": (
                        list(old.get("pending_questions", []))
                        + [f"未找到与「{node.title}」相关的企业资料，请补充官网/年报/上传材料后再生成。"]
                    ),
                }
                node.status = "pending_review"
            return

        # Unparseable extract → group stays pending_review, no raise.
        if not result:
            for node in nodes:
                node.status = "pending_review"
            return

        extracted_map = result.get("extracted_map") or {}
        planning_map = result.get("planning_map") or {}

        for node in nodes:
            key = node.node_key or node.title
            ex_facts = extracted_map.get(key) or []
            if isinstance(ex_facts, str):
                ex_facts = [ex_facts]
            ex_facts = [str(f) for f in ex_facts if f]

            old = node.content or {}
            pending = list(old.get("pending_questions", []))

            if ex_facts:
                # Node has source facts → plan from them. If the LLM gave no
                # plan entry, fall back to reusing the facts themselves so the
                # node is never silently empty.
                plan_items = planning_map.get(key) or []
                if isinstance(plan_items, str):
                    plan_items = [plan_items]
                plan_items = [str(p) for p in plan_items if p] or list(ex_facts)
                content = {
                    "extracted": ex_facts,
                    "planning": plan_items,
                    "ui_suggestion": list(old.get("ui_suggestion", [])),
                    "pending_questions": pending,
                }
                node.content = content
                node.status = "filled"
                # Provenance quote uses the real fact, not the planning copy.
                db.add(NodeSource(
                    id=uuid.uuid4(),
                    node_id=node.id,
                    source_type="ai_completed",
                    source_name=f"AI 填充（{group_key}）",
                    confidence="medium",
                    quote=content["extracted"][0],
                ))
            else:
                # No facts for this node → do not fabricate. Mark for review.
                content = {
                    "extracted": [],
                    "planning": [],
                    "ui_suggestion": list(old.get("ui_suggestion", [])),
                    "pending_questions": pending + [
                        f"未从资料中找到「{node.title}」相关事实，建议补充企业官网/年报/上传材料后再生成。",
                    ],
                }
                node.content = content
                node.status = "pending_review"

    def _build_extract_prompt(
        self,
        intent: str,
        node_specs: List[Dict[str, str]],
        company_context: str,
        web_search_results: Optional[List[Dict[str, Any]]],
        internal_knowledge: Optional[str] = None,
    ) -> str:
        """Pass 1: extract concrete facts per node from source material only.

        The LLM is constrained to pull data points / years / events / quotes
        already present in the company record, web_search hits and uploaded
        materials. It must NOT invent, paraphrase from general industry
        knowledge, or write advisory text — those are forbidden by AGENTS.md
        §4.1 / §5.1.

        ``internal_knowledge`` (SOP/cases/RAG) is injected as a REFERENCE-only
        block: it helps the LLM recognise *what kind* of fact to look for, but
        the prompt explicitly tells it to prefer verified uploads and web
        search over internal-KB excerpts (PRD §23.5.4).
        """
        web_block = ""
        if web_search_results:
            snippets = "\n".join(
                f"- {h.get('source_title', '')}: {h.get('snippet', '')}"
                for h in web_search_results[:5]
            )
            web_block = f"\n\n【网络搜索结果】\n{snippets}"

        source_block = company_context if company_context != self._NO_DATA_SENTINEL else "（仅网络搜索结果，见下方）"

        kb_block = ""
        if internal_knowledge and internal_knowledge.strip():
            kb_block = (
                f"\n\n【内部知识库参考】\n{internal_knowledge.strip()}\n"
                f"（注：以上内部知识库内容仅供参考，优先使用用户上传资料和网络搜索的已验证信息。）"
            )

        return (
            f"你是企业信息抽取助手。请**仅**从下方提供的企业资料与网络搜索结果中，"
            f"为「{intent}」板块的每个节点抽取**该企业的具体客观事实**"
            f"（如数据、年份、事件、产品名、引述等）。\n\n"
            f"【企业资料】\n{source_block}{web_block}{kb_block}\n\n"
            f"【需要抽取事实的节点】\n{json.dumps(node_specs, ensure_ascii=False)}\n\n"
            f"硬性约束：\n"
            f"1. 只抽取资料中**确实存在**的信息，禁止编造、禁止基于行业常识臆测。\n"
            f"2. 每条事实尽量标注来源，格式如「华为 2023 年研发投入 1647 亿元（来源：年报）」。\n"
            f"3. 不要给建议、不要写策划文案、不要做总结修饰——只列客观事实。\n"
            f"4. 某节点若资料中无相关信息，返回空数组 []，不要凑数。\n"
            f"5. 内部知识库内容仅供参考，不得直接当作该企业的事实写入，除非在企业资料或网络搜索结果中得到验证。\n\n"
            f"请严格返回 JSON：{{\"<node_key>\": [\"事实1\", ...]}}。"
            f"不要返回任何其他文字、不要 markdown 代码块。"
        )

    def _build_planning_prompt(
        self,
        intent: str,
        node_specs: List[Dict[str, str]],
        extracted_map: Dict[str, Any],
    ) -> str:
        """Pass 2: draft pre-sales copy grounded ONLY on extracted facts.

        For each node, the LLM receives the facts extracted in pass 1 and must
        turn them into 1-2 sentences of polished pre-sales copy usable in a
        proposal. It must NOT introduce new facts or generalise beyond what's
        in the provided facts; nodes whose fact list is empty are passed
        through as empty arrays so the caller can mark them pending_review.
        """
        # Hand the LLM the per-node facts it produced in pass 1.
        facts_for_prompt = {
            (n["node_key"] or n["title"]): (extracted_map.get(n["node_key"]) or extracted_map.get(n["title"]) or [])
            for n in node_specs
        }

        return (
            f"你是企业3D数字化展示售前策划专家。下面已经从该企业的真实资料中抽取了客观事实，"
            f"请**仅基于这些事实**，为「{intent}」板块的每个节点撰写 1-2 句精炼的售前文案"
            f"（具体、可放入售前方案，不要空泛修饰）。\n\n"
            f"【已抽取的节点事实】\n{json.dumps(facts_for_prompt, ensure_ascii=False)}\n\n"
            f"【需要撰写文案的节点】\n{json.dumps(node_specs, ensure_ascii=False)}\n\n"
            f"硬性约束：\n"
            f"1. 不得补充事实以外的新信息（不新增数据、年份、产品名、客户名等）。\n"
            f"2. 不得编造、不得使用「建议、应该、可以」等空泛建议措辞。\n"
            f"3. 某节点事实为空数组时，该节点也返回空数组 []。\n"
            f"4. 文案是对事实的精炼表达，可以重组语序、突出卖点，但信息量不得超过事实。\n\n"
            f"请严格返回 JSON：{{\"<node_key>\": [\"文案1\", ...]}}。"
            f"不要返回任何其他文字、不要 markdown 代码块。"
        )

    def _parse_fill_response(
        self, raw: str, nodes: List[CanvasNode]
    ) -> Dict[str, Any]:
        """Parse LLM output into {node_key: [str, ...]}."""
        text = (raw or "").strip()
        # Strip markdown code fences if present.
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        # Find the outermost JSON object.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {}  # caller falls back to pending_review

    async def _attach_web_sources(
        self,
        db: AsyncSession,
        nodes: List[CanvasNode],
        web_results: List[Dict[str, Any]],
    ) -> None:
        """Record web_search hits as NodeSource rows on the first node of the
        company_intro board (a single visible anchor for web provenance)."""
        if not nodes or not web_results:
            return
        anchor = nodes[0]
        for hit in web_results[:5]:
            db.add(NodeSource(
                id=uuid.uuid4(),
                node_id=anchor.id,
                source_type="web_search",
                source_name=hit.get("source_title") or hit.get("url"),
                confidence="medium",
                quote=hit.get("snippet"),
                metadata_json={"url": hit.get("url")} if hit.get("url") else None,
            ))

    async def _attach_document_sources(
        self,
        db: AsyncSession,
        nodes: List[CanvasNode],
        document_sources: List[Dict[str, Any]],
    ) -> None:
        """Record uploaded/reference documents as NodeSource rows."""
        if not nodes or not document_sources:
            return
        anchor = nodes[0]
        for doc in document_sources[:5]:
            db.add(NodeSource(
                id=uuid.uuid4(),
                node_id=anchor.id,
                source_type="uploaded_file",
                source_ref_id=doc.get("document_id"),
                source_name=doc.get("title") or doc.get("filename"),
                confidence="high",
                quote=doc.get("excerpt"),
                metadata_json={
                    "project_id": doc.get("project_id"),
                    "chunk_ids": doc.get("chunk_ids", []),
                },
            ))

    # ─── Internal knowledge (SOP / cases / RAG) via ToolRegistry ───────────
    # PRD §23.5.4: the canvas fill can invoke internal SOP, cases and templates,
    # mirroring the chat skill path. Tools are loaded lazily (import inside the
    # method) to avoid circular imports and so a missing tool degrades silently.

    async def _load_internal_knowledge(
        self,
        db: AsyncSession,
        company: Optional[Company],
        nodes_by_group: Dict[str, List[CanvasNode]],
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Load internal SOP / cases / RAG knowledge via the ToolRegistry.

        Returns ``(internal_knowledge_context, provenance_sources)``.

        ``internal_knowledge_context`` is a single text block (SOP steps + top
        case summaries + top RAG chunk excerpts) injected into the extract
        prompt as REFERENCE material. ``provenance_sources`` is a list of
        NodeSource-shaped dicts (source_type / source_name / quote) the caller
        records on the company_intro anchor node.

        Degrades gracefully: if ToolRegistry isn't available, no tools are
        registered, or db is None, returns ``(None, [])`` after a debug log.
        The orchestrator must NEVER fail because a tool is missing.
        """
        if db is None:
            logger.debug("internal_knowledge: no db session, skipping")
            return None, []

        company_name = (company.name if company else "") or ""
        industry = (company.industry if company else "") or ""

        # Lazy import — avoids circular deps with the tools package.
        try:
            from app.tools.registry import ToolRegistry
            from app.tools.base import ToolContext
        except Exception:  # pragma: no cover — defensive, registry is stable
            logger.debug("internal_knowledge: ToolRegistry import failed, skipping")
            return None, []

        try:
            registry = ToolRegistry.get_instance()
        except Exception:  # pragma: no cover
            logger.debug("internal_knowledge: ToolRegistry unavailable, skipping")
            return None, []

        if not registry.list_tools():
            logger.debug("internal_knowledge: no tools registered, skipping")
            return None, []

        # Embedding service is optional (knowledge_search falls back to
        # keyword-only when it's absent). Best-effort: ignore failures.
        embedding_service = None
        try:
            from app.services.embedding_service import get_embedding_service
            embedding_service = await get_embedding_service(db)
        except Exception:
            logger.debug("internal_knowledge: embedding service unavailable, "
                         "knowledge_search will use keyword fallback")

        tool_ctx = ToolContext(db=db, embedding_service=embedding_service)

        blocks: List[str] = []
        sources: List[Dict[str, Any]] = []

        # ── SOP: load active workflows, extract their steps as guidance ──
        try:
            sop_tool = registry.get("sop_load")
            if sop_tool is not None:
                sop_params: Dict[str, Any] = {}
                # Prefer an industry-matched SOP when the industry is known;
                # otherwise fall back to the generic base SOP by name fragment.
                if industry:
                    sop_params["name_contains"] = industry
                else:
                    sop_params["name_contains"] = "Base"
                sop_result = await sop_tool.execute(sop_params, tool_ctx)
                if sop_result.success and sop_result.data.get("sop"):
                    sop_data = sop_result.data["sop"]
                    sop_name = sop_data.get("name") or "SOP"
                    steps = sop_data.get("steps") or []
                    if steps:
                        steps_text = json.dumps(steps, ensure_ascii=False)
                        blocks.append(f"【参考 SOP：{sop_name}】\n步骤指引：{steps_text}")
                        sources.append({
                            "source_type": "internal_sop",
                            "source_name": sop_name,
                            "quote": (steps_text[:200] + "…") if len(steps_text) > 200 else steps_text,
                        })
        except Exception as e:
            logger.debug("internal_knowledge: sop_load failed (%s), skipping SOP", e)

        # ── Cases: search the case library by the company's industry ──
        try:
            case_tool = registry.get("case_search")
            if case_tool is not None and industry:
                case_result = await case_tool.execute(
                    {"industry": industry, "limit": 3}, tool_ctx
                )
                if case_result.success and case_result.data.get("cases"):
                    case_lines: List[str] = []
                    for c in case_result.data["cases"][:3]:
                        title = c.get("title") or "案例"
                        challenge = c.get("challenge") or ""
                        solution = c.get("solution") or ""
                        case_lines.append(
                            f"- {title}：挑战={challenge}；方案={solution}"
                        )
                        sources.append({
                            "source_type": "internal_case",
                            "source_name": title,
                            "quote": f"挑战：{challenge}；方案：{solution}",
                        })
                    if case_lines:
                        blocks.append(
                            "【参考案例（同行业）】\n" + "\n".join(case_lines)
                        )
        except Exception as e:
            logger.debug("internal_knowledge: case_search failed (%s), skipping cases", e)

        # ── RAG: semantic + keyword search built from name + industry ──
        try:
            ks_tool = registry.get("knowledge_search")
            if ks_tool is not None:
                rag_query = f"{company_name} {industry}".strip() or company_name
                if rag_query:
                    ks_result = await ks_tool.execute(
                        {"query": rag_query, "top_k": 5}, tool_ctx
                    )
                    if ks_result.success and ks_result.data.get("chunks"):
                        chunk_lines: List[str] = []
                        for ch in ks_result.data["chunks"][:5]:
                            content = (ch.get("content") or "").strip()
                            if not content:
                                continue
                            title = ch.get("title") or ch.get("section_title") or "知识库片段"
                            chunk_lines.append(f"- [{title}] {content[:160]}")
                            sources.append({
                                "source_type": "internal_template",
                                "source_name": title,
                                "quote": content[:200],
                                "document_id": ch.get("document_id"),
                            })
                        if chunk_lines:
                            blocks.append(
                                "【知识库检索片段】\n" + "\n".join(chunk_lines)
                            )
        except Exception as e:
            logger.debug("internal_knowledge: knowledge_search failed (%s), skipping RAG", e)

        if not blocks:
            return None, []
        return "\n\n".join(blocks), sources

    async def _attach_internal_sources(
        self,
        db: AsyncSession,
        nodes_by_group: Dict[str, List[CanvasNode]],
        ik_sources: List[Dict[str, Any]],
    ) -> None:
        """Record internal-knowledge (SOP/cases/RAG) hits as NodeSource rows.

        PRD §15.1: every board's node detail should surface the internal
        knowledge the planner referenced, so we attach the same source set to
        EACH board's anchor (its first filled node), not just company_intro.
        Confidence is 'low' because this is REFERENCE material.
        """
        if not ik_sources:
            return

        # Resolve one anchor per board: prefer the first filled node, fall back
        # to the first node in the group. Boards with no nodes are skipped.
        anchors: List[CanvasNode] = []
        for group_key in _GROUP_PROMPT_INTENT:
            group_nodes = nodes_by_group.get(group_key) or []
            if not group_nodes:
                continue
            anchor = next(
                (n for n in group_nodes if n.status == "filled"),
                group_nodes[0],
            )
            anchors.append(anchor)

        if not anchors:
            return

        for anchor in anchors:
            for src in ik_sources[:10]:
                db.add(NodeSource(
                    id=uuid.uuid4(),
                    node_id=anchor.id,
                    source_type=src.get("source_type") or "internal_template",
                    source_name=src.get("source_name"),
                    confidence="low",
                    quote=src.get("quote"),
                    metadata_json=(
                        {"document_id": src["document_id"]}
                        if src.get("document_id") else None
                    ),
                ))

    # ─── 方案定调 Agent (PRD §13.4) ─────────────────────────────────────────

    def _collect_planning(
        self, nodes_by_group: Dict[str, List[CanvasNode]]
    ) -> Dict[str, Dict[str, Any]]:
        """Collect each filled node's planning copy, keyed by group_key.

        Returns ``{group_key: {node_key: {title, planning, pending_questions,
        node_id}}}`` for every node whose ``content.planning`` is non-empty.
        This is the corpus the consistency / tone / UI agents reason over — it
        carries only the grounded pre-sales copy the planner produced, so no
        downstream agent can invent enterprise facts (AGENTS.md §5).

        ``pending_questions`` is included so that, AFTER consistency runs, its
        flagged issues flow back into the corpus tone/UI consume — they then
        see the contradictions and don't set a tone that papers over them.
        """
        out: Dict[str, Dict[str, Any]] = {}
        for gk, group_nodes in nodes_by_group.items():
            for n in group_nodes:
                content = n.content or {}
                planning = content.get("planning") or []
                if not planning:
                    continue
                pending = content.get("pending_questions") or []
                out.setdefault(gk, {})[n.node_key or n.title] = {
                    "title": n.title,
                    "planning": [str(p) for p in planning if p],
                    "pending_questions": [str(p) for p in pending if p],
                    "node_id": str(n.id),
                }
        return out

    async def _load_canvas(self, db: AsyncSession, version_id: uuid.UUID) -> Any:
        from app.models.canvas import Canvas

        result = await db.execute(
            select(Canvas).where(Canvas.project_version_id == version_id)
        )
        return result.scalar_one_or_none()

    async def _generate_tone(
        self,
        llm: Any,
        company_context: str,
        planning_payload: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """方案定调 Agent — synthesize project-level style & narrative tone.

        Consumes the planner output across all three boards and produces a
        single tone object (PRD §13.4): theme name, style keywords, narrative
        spine, visual tone, info hierarchy, presentation rhythm, key modules,
        UI principles. Grounded ONLY in the planning copy + company context;
        on parse failure returns None and the caller records a soft error.
        """
        # Flatten planning into a readable board→bullet structure. Include
        # pending_questions (consistency findings) so the tone agent doesn't
        # paper over contradictions the consistency stage just flagged.
        boards_brief = {}
        for gk, nodes in planning_payload.items():
            boards_brief[gk] = [
                {
                    "title": v["title"],
                    "planning": v["planning"][:3],
                    "pending_questions": v.get("pending_questions", []),
                }
                for v in nodes.values()
            ]

        prompt = (
            "你是企业3D数字化展示方案定调专家。下面已由策划专家基于企业真实资料生成了"
            "「企业介绍 / 产品技术场景 / 未来社会责任」三大板块的售前文案。"
            "请**仅基于这些已确认的策划内容**，为整套方案提炼统一的视觉与表达定调，"
            "用于指导后续UI表达和大屏呈现。\n\n"
            f"【企业背景】\n{company_context if company_context != self._NO_DATA_SENTINEL else '（见下方策划内容）'}\n\n"
            f"【已生成的策划内容】\n{json.dumps(boards_brief, ensure_ascii=False)}\n\n"
            "硬性约束：\n"
            "1. 定调必须紧扣上方策划内容的实际信息，禁止引入企业未提及的卖点或数据。\n"
            "2. 风格关键词3-5个，每个2-4字（如「科技感」「工业感」「未来感」）。\n"
            "3. 叙事主线是一句话，概括从企业介绍→产品技术→未来的内容递进逻辑。\n"
            "4. UI设计原则3-5条，面向3D展示幕墙/大屏的视觉表达（不是通用Web规范）。\n\n"
            "请严格返回JSON，字段固定：\n"
            '{"theme_name":"主题名称(8-15字)","style_keywords":["关键词1","关键词2"],'
            '"narrative_spine":"一句话叙事主线","visual_tone":"视觉基调描述",'
            '"info_hierarchy":["信息层级要点1","信息层级要点2"],'
            '"presentation_rhythm":"展示节奏描述","key_modules":["重点模块1","重点模块2"],'
            '"ui_principles":["UI设计原则1","UI设计原则2"]}\n'
            "不要返回任何其他文字、不要markdown代码块。"
        )
        raw = await llm.generate(prompt, temperature=0.4, max_tokens=1200)
        tone = self._parse_json_object(raw)
        if not tone or "style_keywords" not in tone:
            return None
        # Normalise list-valued fields so the frontend can render safely.
        for key in ("style_keywords", "info_hierarchy", "key_modules", "ui_principles"):
            val = tone.get(key)
            if isinstance(val, str):
                tone[key] = [val]
            elif not isinstance(val, list):
                tone[key] = []
        return tone

    # ─── UI 专家 Agent (PRD §13.5) ──────────────────────────────────────────

    async def _run_consistency_check(
        self,
        db: AsyncSession,
        llm: Any,
        company_context: str,
        nodes_by_group: Dict[str, List[CanvasNode]],
        planning_payload: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """一致性检查 Agent — cross-board consistency review (PRD §13.2 step 8).

        Feeds all three boards' planning copy to the LLM and asks it to flag
        consistency problems ONLY of these kinds (no style nitpicks):
          - terminology drift (same entity named differently across boards)
          - narrative gaps (a board asserts something another board contradicts
            or that has no supporting node)
          - contradicting data points (different years / numbers / claims)

        Each returned issue carries ``node_key`` + ``message``; we append the
        message to that node's ``pending_questions`` so it surfaces in the
        node-detail drawer and the export gate. Returns the raw issue list so
        the caller can also store it on ``layout_config.consistency_issues``.

        Grounded strictly in the planning copy — never invents enterprise
        facts. On parse failure returns [] (soft-fail).
        """
        # Flatten to a compact board→node→bullets view the LLM can diff across.
        boards = {}
        node_key_to_node: Dict[str, CanvasNode] = {}
        for gk, nodes_map in planning_payload.items():
            board_nodes = []
            for nk, payload in nodes_map.items():
                node_key_to_node[nk] = next(
                    (n for n in nodes_by_group.get(gk, []) if (n.node_key or n.title) == nk),
                    None,  # type: ignore[arg-type]
                )
                board_nodes.append({
                    "node_key": nk,
                    "title": payload["title"],
                    "planning": payload["planning"][:3],
                })
            boards[gk] = board_nodes

        if not any(boards.values()):
            return []

        prompt = (
            "你是企业3D数字化展示方案的**一致性检查专家**。下面是同一套方案三大板块"
            "（企业介绍 / 产品技术应用场景 / 未来社会责任）已生成的售前文案。"
            "请**仅基于这些已确认内容**做跨板块一致性核查，找出以下类型的问题：\n"
            "1. 术语漂移：同一企业/产品/技术在不同板块命名不一致。\n"
            "2. 叙事断裂：某板块的论断在其它板块缺乏支撑，或前后矛盾。\n"
            "3. 数据冲突：年份、数字、规模、排名等在不同板块相互矛盾。\n\n"
            f"【企业背景】\n{company_context if company_context != self._NO_DATA_SENTINEL else '（见下方策划内容）'}\n\n"
            f"【三大板块策划内容】\n{json.dumps(boards, ensure_ascii=False)}\n\n"
            "硬性约束：\n"
            "- 只报告**跨板块的一致性问题**，不评价单板块文案好坏、不改写内容。\n"
            "- 每条问题必须指明出问题的 node_key（来自上方数据），且给出可操作的核查建议。\n"
            "- 若没有发现问题，返回 {\"issues\": []}，禁止编造问题。\n\n"
            '请严格返回JSON：{"issues":[{"node_key":"出问题的节点key","message":"一致性问题描述与建议"}]}'
            "。不要返回任何其他文字、不要markdown代码块。"
        )
        raw = await llm.generate(prompt, temperature=0.2, max_tokens=1200)
        parsed = self._parse_json_object(raw)
        raw_issues = parsed.get("issues") if isinstance(parsed, dict) else None
        if not isinstance(raw_issues, list):
            return []

        issues: List[Dict[str, Any]] = []
        for item in raw_issues:
            if not isinstance(item, dict):
                continue
            node_key = str(item.get("node_key") or "").strip()
            message = str(item.get("message") or "").strip()
            if not node_key or not message:
                continue
            issues.append({"node_key": node_key, "message": message})
            # Append to the offending node's pending_questions (idempotent:
            # skip if the exact message is already present).
            target = node_key_to_node.get(node_key)
            if target is None:
                continue
            old = target.content or {}
            pending = list(old.get("pending_questions", []))
            tag = f"【一致性核查】{message}"
            if tag not in pending:
                pending.append(tag)
                target.content = {
                    "extracted": list(old.get("extracted", [])),
                    "planning": list(old.get("planning", [])),
                    "ui_suggestion": list(old.get("ui_suggestion", [])),
                    "pending_questions": pending,
                }
                # Promote to pending_review so the export gate can surface it.
                if target.status == "filled":
                    target.status = "pending_review"
        return issues

    async def _generate_ui_suggestions(
        self,
        db: AsyncSession,
        llm: Any,
        nodes_by_group: Dict[str, List[CanvasNode]],
        tone: Optional[Dict[str, Any]],
        allow_extracted_fallback: bool = False,
    ) -> None:
        """UI 专家 Agent — per-board UI expression advice.

        For each board, the LLM receives the board's planning copy plus the
        project tone, and returns 1-2 concrete UI expression bullets per node
        (homepage direction, large-screen layout, 3D visual treatment, motion).
        Output lands in ``content.ui_suggestion`` on nodes that already have
        planning content; nodes without planning are skipped (no fabrication).

        When ``allow_extracted_fallback`` is True (UI-only re-run path), nodes
        with no ``planning`` but with ``extracted`` material are still advised,
        so a node can get UI guidance even if the planner pass hasn't run yet.
        The resulting NodeSource is tagged ``degraded=true`` for traceability.
        """
        tone_brief = ""
        if tone:
            tone_brief = (
                f"【项目定调】\n主题：{tone.get('theme_name','')}\n"
                f"风格关键词：{', '.join(tone.get('style_keywords', []))}\n"
                f"视觉基调：{tone.get('visual_tone','')}\n"
                f"UI设计原则：{'; '.join(tone.get('ui_principles', []))}\n\n"
            )

        for group_key, intent in _GROUP_PROMPT_INTENT.items():
            group_nodes = nodes_by_group.get(group_key, [])
            # Advise on nodes that have planning content; optionally fall back
            # to extracted material when re-running the UI pass alone.
            def _has_basis(n: CanvasNode) -> bool:
                content = n.content or {}
                if content.get("planning"):
                    return True
                return bool(allow_extracted_fallback and content.get("extracted"))

            candidates = [n for n in group_nodes if _has_basis(n)]
            if not candidates:
                continue

            node_specs = [
                {
                    "node_key": n.node_key or n.title,
                    "title": n.title,
                    "planning": [str(p) for p in (n.content or {}).get("planning", [])][:3],
                    "extracted": (
                        [str(p) for p in (n.content or {}).get("extracted", [])][:3]
                        if allow_extracted_fallback else []
                    ),
                }
                for n in candidates
            ]

            prompt = (
                f"你是企业3D数字化展示UI专家。请基于下方「{intent}」板块已确认的策划文案"
                "和项目定调，为每个节点输出1-2条**具体的UI/大屏表达建议**"
                "（如首页视觉方向、大屏布局、3D视觉处理、动效与组件、信息可视化方式）。\n\n"
                f"{tone_brief}"
                f"【节点及策划文案】\n{json.dumps(node_specs, ensure_ascii=False)}\n\n"
                "硬性约束：\n"
                "1. UI建议必须紧扣该节点的策划内容，不得新增企业未提及的产品或数据。\n"
                "2. 每条建议要具体可执行（指明视觉元素/布局方式/动效），不要空泛口号。\n"
                "3. 面向3D展示幕墙/裸眼3D/LED媒体立面/数字展厅场景，不是通用Web。\n"
                "4. 某节点若不适合给UI建议，返回空数组 []。\n\n"
                "请严格返回JSON：{\"<node_key>\":[\"UI建议1\",...]}。"
                "不要返回任何其他文字、不要markdown代码块。"
            )
            raw = await llm.generate(prompt, temperature=0.4, max_tokens=1800)
            ui_map = self._parse_fill_response(raw, candidates)

            for node in candidates:
                key = node.node_key or node.title
                items = ui_map.get(key) or []
                if isinstance(items, str):
                    items = [items]
                items = [str(i) for i in items if i]
                if not items:
                    continue
                used_planning = bool((node.content or {}).get("planning"))
                old = node.content or {}
                node.content = {
                    "extracted": list(old.get("extracted", [])),
                    "planning": list(old.get("planning", [])),
                    "ui_suggestion": items,
                    "pending_questions": list(old.get("pending_questions", [])),
                }
                # UI advice is AI-generated guidance → mark its provenance so
                # the node-detail drawer can show it as a distinct source.
                # ``degraded=true`` flags the extracted-fallback path.
                db.add(NodeSource(
                    id=uuid.uuid4(),
                    node_id=node.id,
                    source_type="ai_completed",
                    source_name=f"UI 专家建议（{group_key}）",
                    confidence="medium",
                    quote=items[0],
                    metadata_json={
                        "agent": "ui_expert",
                        "degraded": not used_planning,
                    },
                ))

    def _parse_json_object(self, raw: str) -> Dict[str, Any]:
        """Lenient JSON object parse (strips code fences, slices to braces)."""
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


canvas_agent_orchestrator = CanvasAgentOrchestrator()
