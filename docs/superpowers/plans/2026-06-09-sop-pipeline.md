# SOP Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a conversation-driven SOP pipeline that executes the full flow (company analysis → proposal → visual → export) with pause/resume at key stages.

**Architecture:** Pipeline state is stored in conversation `metadata_json`. A new `_handle_sop_pipeline` method in `conversation_service.py` orchestrates the 4 stages, pausing after stages 1-3 for user confirmation. Intent detection routes new `sop_pipeline` intent. Recovery from paused state happens on user's next message.

**Tech Stack:** Python/FastAPI backend, React/Next.js frontend, SSE streaming

**Spec:** `docs/superpowers/specs/2026-06-09-sop-pipeline-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `apps/api/app/services/intent_service.py` | Add `sop_pipeline` keyword detection + action classification |
| Modify | `apps/api/app/services/conversation_service.py` | Add pipeline handler + state load/save + routing |
| Modify | `apps/api/app/skills/builtins/proposal_generation.py` | Accept `company_profile` dict as input |
| Modify | `apps/api/app/skills/builtins/export.py` | Accept raw content + images for pipeline export |
| Modify | `apps/web/components/chat/welcome-screen.tsx` | Add 6th "完整方案" card |

---

## Task 1: Pipeline State Data Class

**Files:**
- Create: `apps/api/app/services/pipeline_state.py`

This is the data model for pipeline session state. It serializes to/from dict for storage in conversation `metadata_json`.

- [ ] **Step 1: Create `pipeline_state.py`**

```python
"""Pipeline session state — stored in conversation metadata_json."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Ordered stage definitions for the standard pipeline
STAGE_ORDER = [
    "company_analysis",
    "proposal_generation",
    "visual_generation",
    "export",
]

# Stages that pause for user confirmation after execution
PAUSE_STAGES = {"company_analysis", "proposal_generation", "visual_generation"}


@dataclass
class PipelineState:
    """Represents an in-progress SOP pipeline session."""

    status: str = "running"  # running | paused | completed | failed
    current_stage: str = "company_analysis"
    completed_stages: List[str] = field(default_factory=list)
    project_context: Dict[str, Any] = field(default_factory=dict)
    stage_outputs: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline": {
                "status": self.status,
                "current_stage": self.current_stage,
                "completed_stages": self.completed_stages,
                "project_context": self.project_context,
                "stage_outputs": self.stage_outputs,
                "started_at": self.started_at,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PipelineState:
        p = data.get("pipeline", data)
        return cls(
            status=p.get("status", "running"),
            current_stage=p.get("current_stage", "company_analysis"),
            completed_stages=p.get("completed_stages", []),
            project_context=p.get("project_context", {}),
            stage_outputs=p.get("stage_outputs", {}),
            started_at=p.get("started_at", ""),
        )

    # ── Helpers ──

    def next_stage(self) -> Optional[str]:
        """Return the next stage after current, or None if done."""
        try:
            idx = STAGE_ORDER.index(self.current_stage)
        except ValueError:
            return None
        next_idx = idx + 1
        if next_idx >= len(STAGE_ORDER):
            return None
        return STAGE_ORDER[next_idx]

    def advance(self) -> Optional[str]:
        """Mark current stage completed, advance to next. Returns new stage or None."""
        if self.current_stage not in self.completed_stages:
            self.completed_stages.append(self.current_stage)
        nxt = self.next_stage()
        if nxt is None:
            self.status = "completed"
            return None
        self.current_stage = nxt
        self.status = "running"
        return nxt

    def pause(self) -> None:
        """Pause pipeline, waiting for user confirmation."""
        self.status = "paused"

    def reset(self) -> None:
        """Reset pipeline to initial state."""
        self.status = "running"
        self.current_stage = "company_analysis"
        self.completed_stages = []
        self.stage_outputs = {}
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.pipeline_state import PipelineState; s = PipelineState(); print(s.to_dict())"`
Expected: JSON dict with pipeline state printed

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/pipeline_state.py
git commit -m "feat(pipeline): add PipelineState data class for SOP session tracking"
```

---

## Task 2: Add `sop_pipeline` Intent Detection

**Files:**
- Modify: `apps/api/app/services/intent_service.py`

Add keyword matching for the `sop_pipeline` intent. This goes in `_keyword_match()` before the existing skill keyword loop.

- [ ] **Step 1: Add pipeline keyword constants (after line 53)**

Insert at the top of the file, after `_VISUAL_CONCEPT_KEYWORDS`:

```python
_PIPELINE_KEYWORDS_HIGH = [
    "设计一套3D幕墙方案", "做一套完整方案", "从零开始做方案",
    "端到端方案", "全流程", "从头到尾做", "帮我设计方案",
    "完整方案", "全套方案",
]

_PIPELINE_KEYWORDS_MEDIUM = [
    "3D幕墙方案", "LED方案设计", "裸眼3D方案", "数字展示方案",
    "媒体立面方案", "策划全套",
]
```

- [ ] **Step 2: Add pipeline matching in `_keyword_match` (insert before line 158)**

Inside `_keyword_match()`, after the image-generation pattern block (line 156) and before the `_SKILL_KEYWORDS` loop (line 158), insert:

```python
        # Check for SOP pipeline intent
        for kw in _PIPELINE_KEYWORDS_HIGH:
            if kw in message:
                return IntentResult(
                    intent="sop_pipeline",
                    confidence=0.85,
                    input_data={"user_message": message},
                )
        for kw in _PIPELINE_KEYWORDS_MEDIUM:
            if kw in message:
                return IntentResult(
                    intent="sop_pipeline",
                    confidence=0.7,
                    input_data={"user_message": message},
                )
```

- [ ] **Step 3: Add action classification for paused pipeline**

Add a new method to `IntentDetector` class (after `_keyword_match`):

```python
    @staticmethod
    def classify_pipeline_action(message: str) -> str:
        """Classify user action when pipeline is paused.

        Returns: "confirm" | "modify" | "restart"
        """
        msg = message.strip()
        confirm_words = ["确认", "继续", "下一步", "没问题", "可以", "好的", "通过", "ok", "OK"]
        restart_words = ["重新开始", "从头来", "重来", "重置"]

        for w in restart_words:
            if w in msg:
                return "restart"

        # If message is short and matches a confirm word, treat as confirm
        if len(msg) <= 20:
            for w in confirm_words:
                if w in msg:
                    return "confirm"

        # Otherwise treat as modify feedback
        return "modify"
```

- [ ] **Step 4: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "
from app.services.intent_service import IntentDetector
d = IntentDetector()
import asyncio
r = asyncio.run(d.detect('给华为设计一套3D幕墙方案', [], db=None))
print(r.intent, r.confidence)
"`
Expected: `sop_pipeline 0.85`

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/intent_service.py
git commit -m "feat(intent): add sop_pipeline keyword detection and action classification"
```

---

## Task 3: Pipeline State Load/Save in ConversationService

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

Add two helper methods to load and save pipeline state from conversation message metadata. Follow the same pattern as `_load_visual_concept_ctx`.

- [ ] **Step 1: Add `_load_pipeline_state` method (insert after `_load_visual_concept_ctx` around line 507)**

```python
    def _load_pipeline_state(self, messages: List[Message]) -> Optional["PipelineState"]:
        """Recover pipeline state from the most recent assistant message metadata."""
        from app.services.pipeline_state import PipelineState

        for msg in reversed(messages):
            if msg.metadata_json and "pipeline" in msg.metadata_json:
                return PipelineState.from_dict(msg.metadata_json)
        return None
```

- [ ] **Step 2: Add import for PipelineState at top of file**

Add to the existing imports near the top:

```python
from app.services.pipeline_state import PipelineState
```

- [ ] **Step 3: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add pipeline state load helper to ConversationService"
```

---

## Task 4: Add Pipeline Routing in `process_message_stream`

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

Add pipeline routing *before* the existing intent-based routing. This checks for a paused pipeline first, then adds the `sop_pipeline` intent branch.

- [ ] **Step 1: Add paused-pipeline recovery before intent routing (insert after line 198)**

After `history = self.build_message_history(messages)` (line 198) and before `# 3. Detect intent` (line 200), insert:

```python
        # 2.5 Check for paused pipeline that needs resuming
        pipeline_state = self._load_pipeline_state(messages)
        if pipeline_state and pipeline_state.status == "paused":
            logger.info("Resuming paused pipeline at stage: %s", pipeline_state.current_stage)
            async for chunk in self._handle_sop_pipeline_resume(
                db, conv_uuid, user_message, pipeline_state, history
            ):
                yield chunk
            return
```

- [ ] **Step 2: Add `sop_pipeline` intent branch (insert after line 213)**

In the routing block, after `if intent.intent == "run_skill"` and before `elif intent.intent == "visual_concept"`, insert:

```python
        if intent.intent == "sop_pipeline" and intent.skill_id is None:
            async for chunk in self._handle_sop_pipeline(
                db, conv_uuid, user_message, intent, history
            ):
                yield chunk
```

Note: The full routing becomes:

```python
        # 4. Route based on intent
        if intent.intent == "sop_pipeline" and intent.skill_id is None:
            async for chunk in self._handle_sop_pipeline(
                db, conv_uuid, user_message, intent, history
            ):
                yield chunk
        elif intent.intent == "run_skill" and intent.skill_id:
            async for chunk in self._handle_skill_execution(
                db, conv_uuid, intent, history
            ):
                yield chunk
        elif intent.intent == "visual_concept":
            ...
```

- [ ] **Step 3: Verify syntax**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add sop_pipeline routing and paused-pipeline recovery"
```

---

## Task 5: Implement `_handle_sop_pipeline` — Main Pipeline Launcher

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

This is the core pipeline handler. It initializes the pipeline state and executes Stage 1 (company_analysis).

- [ ] **Step 1: Add `_handle_sop_pipeline` method (insert before `_handle_visual_concept`)**

```python
    async def _handle_sop_pipeline(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        intent: IntentResult,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Launch a full SOP pipeline: company_analysis → proposal → visual → export.

        Executes Stage 1 immediately, then pauses for user confirmation.
        """
        from app.services.pipeline_state import PipelineState

        # Quick pre-check: does the user message contain any entity info?
        has_entity = len(user_message) > 10  # Simple heuristic for MVP
        if not has_entity:
            prompt_text = (
                "请提供以下信息，我将为您启动完整的方案设计流程：\n\n"
                "1. **企业名称**（必填）\n"
                "2. 所属行业\n"
                "3. 项目需求简述\n\n"
                "例如：*「给华为科技公司设计一套3D展示幕墙方案，用于新品发布会」*"
            )
            yield f"data: {json.dumps({'type': 'text_delta', 'text': prompt_text})}\n\n"
            await self.save_message(
                db, conversation_id, "assistant",
                content=prompt_text, content_type="text",
                auto_commit=True,
            )
            return

        # Initialize pipeline state
        state = PipelineState()
        state.project_context = {
            "user_message": user_message,
            "company_name": self._extract_company_name(user_message),
        }

        # Execute Stage 1: company_analysis
        async for chunk in self._execute_pipeline_stage(
            db, conversation_id, state, history
        ):
            yield chunk
```

- [ ] **Step 2: Add `_extract_company_name` helper**

```python
    @staticmethod
    def _extract_company_name(message: str) -> str:
        """Extract likely company name from user message. Simple heuristic for MVP."""
        # Look for pattern: 给/为/帮 XX(公司/科技/集团...)
        import re
        patterns = [
            r"给\s*(\S{2,10}?(?:公司|集团|科技|股份|有限))",
            r"为\s*(\S{2,10}?(?:公司|集团|科技|股份|有限))",
            r"帮\s*(\S{2,10}?(?:公司|集团|科技|股份|有限))",
            r"(\S{2,8})的.*(?:方案|幕墙|展示)",
        ]
        for pat in patterns:
            m = re.search(pat, message)
            if m:
                return m.group(1)
        return ""
```

- [ ] **Step 3: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add _handle_sop_pipeline launcher and company name extraction"
```

---

## Task 6: Implement `_execute_pipeline_stage` — Stage Runner

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

This method executes a single pipeline stage by calling the appropriate Skill, then either pauses or advances.

- [ ] **Step 1: Add `_execute_pipeline_stage` method**

```python
    async def _execute_pipeline_stage(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        state: "PipelineState",
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Execute the current pipeline stage, stream results, and pause/advance."""
        from app.skills.base import SkillContext
        from app.skills.registry import SkillRegistry
        from app.skills.runner import SkillRunner
        from app.services.embedding_service import get_embedding_service
        from app.services.image_service import get_image_service

        stage = state.current_stage

        # ── Build skill input from pipeline context ──
        input_data = self._build_stage_input(stage, state, history)

        # Get project_id from conversation
        conv = await self.get_conversation_detail(db, str(conversation_id))
        project_id = str(conv.project_id) if conv and conv.project_id else None
        if project_id:
            input_data["project_id"] = project_id

        # ── Prepare context ──
        registry = SkillRegistry.get_instance()
        if not registry.list_skills():
            registry.auto_register()

        context = SkillContext(
            project_id=project_id,
            user_id=None,
            db=db,
            llm_service=await get_llm_service(db),
            embedding_service=await get_embedding_service(db),
            image_service=await get_image_service(db),
        )

        # ── Stream stage-start indicator ──
        stage_names = {
            "company_analysis": "企业解析",
            "proposal_generation": "策划案生成",
            "visual_generation": "视觉方案生成",
            "export": "方案导出",
        }
        stage_display = stage_names.get(stage, stage)

        # Stream progress text
        progress_text = f"🔄 **{stage_display}** 阶段开始执行...\n\n"
        yield f"data: {json.dumps({'type': 'text_delta', 'text': progress_text})}\n\n"

        # ── Execute skill(s) ──
        runner = SkillRunner(registry)
        all_output: Dict[str, Any] = {}

        if stage == "visual_generation":
            # Special: run visual_prompt then image_generation x2
            vp_result = await runner.run("visual_prompt", input_data, context)
            if vp_result.get("success"):
                all_output = vp_result.get("output", {})
                # Auto-chain: generate 2 images
                collected_images: list = []
                for _ in range(2):
                    img_input = {
                        "prompt": all_output.get("positive_prompt", ""),
                        "negative_prompt": all_output.get("negative_prompt", ""),
                        "width": input_data.get("width", 1024),
                        "height": input_data.get("height", 768),
                    }
                    if project_id:
                        img_input["project_id"] = project_id
                    img_result = await runner.run("image_generation", img_input, context)
                    if img_result.get("success"):
                        url = img_result.get("output", {}).get("image_url")
                        if url:
                            collected_images.append({"url": url})
                if collected_images:
                    all_output["images"] = collected_images
                    all_output["image_url"] = collected_images[0]["url"]
        elif stage == "export":
            # Export: use stage_outputs from previous stages
            export_input = self._build_export_input(state, project_id)
            result = await runner.run("export", export_input, context)
            if result.get("success"):
                all_output = result.get("output", {})
            else:
                # Fallback: export directly from proposal content
                all_output = await self._fallback_export(state, context, project_id)
        else:
            # Standard: run single skill
            skill_id = stage  # company_analysis or proposal_generation
            result = await runner.run(skill_id, input_data, context)
            if result.get("success"):
                all_output = result.get("output", {})
            else:
                error_msg = result.get("error", "执行失败")
                error_text = f"❌ **{stage_display}** 执行失败：{error_msg}\n\n请尝试重新描述需求。"
                yield f"data: {json.dumps({'type': 'text_delta', 'text': error_text})}\n\n"
                state.status = "failed"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=error_text, content_type="text",
                    metadata=state.to_dict(), auto_commit=True,
                )
                return

        # ── Save stage output ──
        state.stage_outputs[stage] = all_output

        # ── Render output text ──
        skill_id_for_render = "visual_prompt" if stage == "visual_generation" else stage
        content_text = self._render_skill_output(skill_id_for_render, all_output)

        # ── Build content blocks ──
        blocks = self._build_stage_blocks(stage, all_output, state)

        # ── Stream output ──
        yield f"data: {json.dumps({'type': 'text_delta', 'text': content_text})}\n\n"

        for block in blocks:
            yield f"data: {json.dumps({'type': 'content_block_start', 'data': {'block_type': block['type']}})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_data', 'data': block})}\n\n"
            yield f"data: {json.dumps({'type': 'content_block_end'})}\n\n"

        # ── Pause or complete ──
        from app.services.pipeline_state import PAUSE_STAGES

        if stage in PAUSE_STAGES:
            state.pause()
        else:
            state.advance()  # export stage → completed

        # ── Save assistant message with pipeline state ──
        await self.save_message(
            db, conversation_id, "assistant",
            content=content_text, content_type="rich",
            rich_content={"blocks": blocks},
            metadata=state.to_dict(), auto_commit=True,
        )
```

- [ ] **Step 2: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add _execute_pipeline_stage with skill dispatch and pause logic"
```

---

## Task 7: Implement Stage Input/Block Builders

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

Helper methods to build skill input from pipeline state and render content blocks per stage.

- [ ] **Step 1: Add `_build_stage_input` method**

```python
    @staticmethod
    def _build_stage_input(
        stage: str, state: "PipelineState", history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Build skill input data from pipeline state and history."""
        user_msg = state.project_context.get("user_message", "")

        if stage == "company_analysis":
            return {
                "company_info": user_msg,
                "company_name": state.project_context.get("company_name", ""),
            }

        elif stage == "proposal_generation":
            company_output = state.stage_outputs.get("company_analysis", {})
            return {
                "requirement_text": user_msg,
                "company_profile": company_output,  # Pass Stage 1 output directly
                "company_info": user_msg,
            }

        elif stage == "visual_generation":
            proposal_output = state.stage_outputs.get("proposal_generation", {})
            company_output = state.stage_outputs.get("company_analysis", {})
            return {
                "user_message": user_msg,
                "proposal_context": proposal_output,
                "visual_direction": company_output.get("recommended_visual_direction", ""),
                "style": state.project_context.get("visual_style"),
            }

        elif stage == "export":
            return {}  # Built separately in _build_export_input

        return {"user_message": user_msg}
```

- [ ] **Step 2: Add `_build_stage_blocks` method**

```python
    @staticmethod
    def _build_stage_blocks(
        stage: str, output: Dict[str, Any], state: "PipelineState"
    ) -> List[Dict[str, Any]]:
        """Build rich content blocks for a pipeline stage."""
        blocks: List[Dict[str, Any]] = []

        # Skill progress block
        blocks.append({
            "type": "skill_progress",
            "data": {"skill_id": stage, "status": "completed"},
        })

        # Stage-specific content block
        if stage == "company_analysis" and output:
            blocks.append({"type": "company_analysis_card", "data": output})

        elif stage == "proposal_generation" and output:
            missing = output.get("missing_info", [])
            sections = output.get("sections_meta", [])
            blocks.append({
                "type": "proposal_section",
                "data": {
                    "content_type": "text/markdown",
                    "missing_info": missing if isinstance(missing, list) else [],
                    "sections": sections if isinstance(sections, list) else [],
                },
            })

        elif stage == "visual_generation" and output:
            blocks.append({"type": "visual_result", "data": output})

        elif stage == "export" and output:
            blocks.append({"type": "artifact", "data": output})

        # Action buttons for pause stages
        if stage == "company_analysis":
            blocks.append({
                "type": "action_buttons",
                "data": {"buttons": [
                    {"label": "✓ 确认企业画像，继续", "value": "确认继续", "action": "quick_reply"},
                    {"label": "↻ 重新生成", "value": "重新生成企业解析", "action": "quick_reply"},
                ]},
            })
        elif stage == "proposal_generation":
            blocks.append({
                "type": "action_buttons",
                "data": {"buttons": [
                    {"label": "✓ 确认策划案，继续", "value": "确认继续", "action": "quick_reply"},
                    {"label": "✎ 我有修改意见", "value": "修改策划案", "action": "quick_reply"},
                ]},
            })
        elif stage == "visual_generation":
            blocks.append({
                "type": "action_buttons",
                "data": {"buttons": [
                    {"label": "使用方案 A", "value": "使用第一张效果图", "action": "quick_reply"},
                    {"label": "使用方案 B", "value": "使用第二张效果图", "action": "quick_reply"},
                    {"label": "两个都用", "value": "两张都可以继续", "action": "quick_reply"},
                ]},
            })

        return blocks
```

- [ ] **Step 3: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add stage input builder and content block builder"
```

---

## Task 8: Implement `_handle_sop_pipeline_resume` — Pause/Resume Handler

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

This method handles user messages when the pipeline is paused — classifying them as confirm/modify/restart.

- [ ] **Step 1: Add `_handle_sop_pipeline_resume` method**

```python
    async def _handle_sop_pipeline_resume(
        self,
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_message: str,
        state: "PipelineState",
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Resume a paused pipeline based on user action (confirm/modify/restart)."""
        from app.services.intent_service import IntentDetector

        action = IntentDetector.classify_pipeline_action(user_message)

        if action == "restart":
            state.reset()
            confirm_text = "🔄 已重置方案流程，重新从企业解析开始...\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': confirm_text})}\n\n"
            async for chunk in self._execute_pipeline_stage(
                db, conversation_id, state, history
            ):
                yield chunk
            return

        if action == "confirm":
            stage_names = {
                "company_analysis": "企业画像",
                "proposal_generation": "策划案",
                "visual_generation": "视觉方案",
            }
            current_name = stage_names.get(state.current_stage, state.current_stage)
            confirm_text = f"✅ **{current_name}** 已确认，进入下一阶段...\n\n"
            yield f"data: {json.dumps({'type': 'text_delta', 'text': confirm_text})}\n\n"

            next_stage = state.advance()
            if next_stage is None:
                # Pipeline completed
                done_text = "🎉 方案流程已全部完成！所有产物已保存。"
                yield f"data: {json.dumps({'type': 'text_delta', 'text': done_text})}\n\n"
                await self.save_message(
                    db, conversation_id, "assistant",
                    content=confirm_text + done_text, content_type="text",
                    metadata=state.to_dict(), auto_commit=True,
                )
                return

            async for chunk in self._execute_pipeline_stage(
                db, conversation_id, state, history
            ):
                yield chunk
            return

        # action == "modify" — re-run current stage with user feedback
        state.project_context["modify_feedback"] = user_message
        modify_text = f"📝 收到修改意见，正在重新生成...\n\n"
        yield f"data: {json.dumps({'type': 'text_delta', 'text': modify_text})}\n\n"
        state.status = "running"
        async for chunk in self._execute_pipeline_stage(
            db, conversation_id, state, history
        ):
            yield chunk
```

- [ ] **Step 2: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add pipeline resume handler with confirm/modify/restart"
```

---

## Task 9: Add Export Helpers for Pipeline Mode

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`

The standard `export` skill requires a `task_id` (GenerationOutput DB record). In pipeline mode, we may not have a saved output. Add fallback export helpers.

- [ ] **Step 1: Add `_build_export_input` method**

```python
    @staticmethod
    def _build_export_input(
        state: "PipelineState", project_id: Optional[str]
    ) -> Dict[str, Any]:
        """Build export skill input from accumulated pipeline outputs."""
        # Try to get task_id from proposal_generation output
        proposal_output = state.stage_outputs.get("proposal_generation", {})
        task_id = proposal_output.get("output_id") or proposal_output.get("task_id")

        if task_id:
            return {"task_id": str(task_id), "format": "word"}

        # No task_id — will use fallback
        return {"task_id": "", "format": "word"}
```

- [ ] **Step 2: Add `_fallback_export` method**

```python
    async def _fallback_export(
        self,
        state: "PipelineState",
        context: "SkillContext",
        project_id: Optional[str],
    ) -> Dict[str, Any]:
        """Direct export when no GenerationOutput record exists (pipeline chat mode)."""
        try:
            from app.services.export_service import get_export_service

            # Assemble content from pipeline outputs
            proposal_output = state.stage_outputs.get("proposal_generation", {})
            content = proposal_output.get("content", proposal_output.get("proposal_text", ""))

            if not content:
                # Try to use the rendered text from stage_outputs
                company_output = state.stage_outputs.get("company_analysis", {})
                parts = []
                if company_output:
                    parts.append("# 企业解析\n")
                    parts.append(str(company_output.get("summary", "")))
                if proposal_output:
                    parts.append("\n# 策划方案\n")
                    parts.append(str(proposal_output))
                content = "\n".join(parts)

            if not content:
                return {"error": "No content to export"}

            service = get_export_service()
            file_path = await service.export_to_word(
                content=content,
                filename=f"pipeline_{state.started_at[:10]}.docx",
            )
            return {"file_path": file_path, "format": "word"}
        except Exception as e:
            return {"error": str(e)}
```

- [ ] **Step 3: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.services.conversation_service import ConversationService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/conversation_service.py
git commit -m "feat(pipeline): add export input builder and fallback export for chat mode"
```

---

## Task 10: Adapt `proposal_generation` Skill to Accept Company Profile

**Files:**
- Modify: `apps/api/app/skills/builtins/proposal_generation.py`

Currently the chat mode ignores `company_profile`. We need to inject it into the prompt when available.

- [ ] **Step 1: Modify `_execute_chat_mode` to use company_profile**

Find the `_execute_chat_mode` method (around line 92). After the line that reads `requirement_text = input_data.get(...)` add:

```python
        company_profile = input_data.get("company_profile")
```

Then, in the prompt assembly section, when building the user prompt, include company profile context if available:

```python
        # Build prompt with optional company profile context
        if company_profile:
            import json as _json
            profile_text = _json.dumps(company_profile, ensure_ascii=False, indent=2) if isinstance(company_profile, dict) else str(company_profile)
            user_prompt = (
                f"以下是已完成的企业画像分析：\n\n{profile_text}\n\n"
                f"请基于以上企业画像，结合以下项目需求生成策划案：\n\n{requirement_text}"
            )
        else:
            user_prompt = requirement_text
```

Use `user_prompt` instead of `requirement_text` in the LLM call.

- [ ] **Step 2: Verify**

Run: `cd /Users/tutu/apps/3D/apps/api && python -c "from app.skills.builtins.proposal_generation import ProposalGenerationSkill; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/skills/builtins/proposal_generation.py
git commit -m "feat(proposal): accept company_profile dict from pipeline context"
```

---

## Task 11: Add "完整方案" Card to Welcome Screen

**Files:**
- Modify: `apps/web/components/chat/welcome-screen.tsx`

Add a 6th card that triggers the full pipeline.

- [ ] **Step 1: Add Rocket icon import**

Change line 11 from:
```tsx
  X,
  Palette,
```
to:
```tsx
  X,
  Palette,
  Rocket,
```

- [ ] **Step 2: Add the card to `suggestions` array**

Insert after the "方案导出" card (line 58), before the closing `];`:

```tsx
    {
      icon: Rocket,
      title: "完整方案",
      description: "从企业解析到导出的端到端方案生成",
      message: "帮我设计一套完整的3D幕墙方案",
    },
```

- [ ] **Step 3: Verify**

Run: `cd /Users/tutu/apps/3D/apps/web && npx tsc --noEmit --pretty 2>&1 | grep "welcome-screen" || echo "No errors"`
Expected: `No errors`

- [ ] **Step 4: Commit**

```bash
git add apps/web/components/chat/welcome-screen.tsx
git commit -m "feat(ui): add '完整方案' card to welcome screen for SOP pipeline"
```

---

## Task 12: End-to-End Integration Test

**Files:**
- Create: `apps/api/app/tests/test_pipeline.py`

- [ ] **Step 1: Write pipeline integration test**

```python
"""Integration tests for SOP pipeline flow."""

import pytest
from app.services.pipeline_state import PipelineState, STAGE_ORDER, PAUSE_STAGES
from app.services.intent_service import IntentDetector


class TestPipelineState:
    def test_initial_state(self):
        state = PipelineState()
        assert state.status == "running"
        assert state.current_stage == "company_analysis"
        assert state.completed_stages == []

    def test_advance(self):
        state = PipelineState()
        nxt = state.advance()
        assert nxt == "proposal_generation"
        assert "company_analysis" in state.completed_stages
        assert state.status == "running"

    def test_advance_to_completion(self):
        state = PipelineState()
        state.advance()  # → proposal
        state.advance()  # → visual
        state.advance()  # → export
        nxt = state.advance()  # → None (completed)
        assert nxt is None
        assert state.status == "completed"

    def test_pause(self):
        state = PipelineState()
        state.pause()
        assert state.status == "paused"

    def test_reset(self):
        state = PipelineState()
        state.advance()
        state.advance()
        state.reset()
        assert state.current_stage == "company_analysis"
        assert state.completed_stages == []
        assert state.status == "running"

    def test_serialization_roundtrip(self):
        state = PipelineState()
        state.project_context = {"company_name": "华为"}
        state.stage_outputs["company_analysis"] = {"summary": "test"}
        d = state.to_dict()
        restored = PipelineState.from_dict(d)
        assert restored.project_context["company_name"] == "华为"
        assert restored.stage_outputs["company_analysis"]["summary"] == "test"
        assert restored.status == state.status
        assert restored.current_stage == state.current_stage

    def test_pause_stages(self):
        assert "company_analysis" in PAUSE_STAGES
        assert "proposal_generation" in PAUSE_STAGES
        assert "visual_generation" in PAUSE_STAGES
        assert "export" not in PAUSE_STAGES


class TestIntentDetection:
    @pytest.fixture
    def detector(self):
        return IntentDetector()

    def test_pipeline_intent_high_confidence(self, detector):
        import asyncio
        result = asyncio.run(
            detector.detect("给华为设计一套3D幕墙方案", [], db=None)
        )
        assert result.intent == "sop_pipeline"
        assert result.confidence >= 0.8

    def test_pipeline_intent_medium_confidence(self, detector):
        import asyncio
        result = asyncio.run(
            detector.detect("LED方案设计", [], db=None)
        )
        assert result.intent == "sop_pipeline"

    def test_not_pipeline_intent(self, detector):
        import asyncio
        result = asyncio.run(
            detector.detect("帮我进行企业解析", [], db=None)
        )
        assert result.intent != "sop_pipeline"


class TestPipelineActionClassification:
    def test_confirm_action(self):
        assert IntentDetector.classify_pipeline_action("确认") == "confirm"
        assert IntentDetector.classify_pipeline_action("继续") == "confirm"
        assert IntentDetector.classify_pipeline_action("没问题") == "confirm"

    def test_restart_action(self):
        assert IntentDetector.classify_pipeline_action("重新开始") == "restart"
        assert IntentDetector.classify_pipeline_action("从头来") == "restart"

    def test_modify_action(self):
        assert IntentDetector.classify_pipeline_action("第三章改一下") == "modify"
        assert IntentDetector.classify_pipeline_action("色调再冷一点") == "modify"
        assert IntentDetector.classify_pipeline_action("我觉得视觉方案可以更科技感一些") == "modify"
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/tutu/apps/3D/apps/api && python -m pytest app/tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/tests/test_pipeline.py
git commit -m "test(pipeline): add integration tests for PipelineState and intent detection"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/tutu/apps/3D/apps/api && python -m pytest app/tests/ -v --tb=short`
Expected: All existing + new tests pass

- [ ] **Step 2: Run frontend type check**

Run: `cd /Users/tutu/apps/3D/apps/web && npx tsc --noEmit --pretty 2>&1 | grep -v "proposal/page" | head -20`
Expected: No new errors (the pre-existing `proposal/page.tsx` error is unrelated)

- [ ] **Step 3: Manual smoke test**

1. Open the web app
2. Verify the new "完整方案" card appears on the welcome screen
3. Click it, verify "帮我设计一套完整的3D幕墙方案" is sent
4. Verify the backend detects `sop_pipeline` intent (check uvicorn console logs)
5. Verify company_analysis stage executes

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(pipeline): complete SOP pipeline implementation — Tasks 1-12"
```
