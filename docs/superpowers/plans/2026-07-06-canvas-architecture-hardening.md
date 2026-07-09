# Canvas Architecture Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the canvas workspace architecture by isolating conversation scopes, making Alembic the only schema authority, converging current-version state to one source of truth, and normalizing provenance per consuming node.

**Architecture:** Implement the work in four phases with migration-safe sequencing. First remove runtime schema mutation, then introduce explicit conversation threads/scopes, then collapse version truth to a single project pointer, and finally replace anchor-node provenance with normalized source records plus per-node links.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Next.js, Zustand, pytest

---

### File Structure

**Backend schema and models**
- Modify: `apps/api/alembic/versions/014_canvas_and_versions.py`
- Create: `apps/api/alembic/versions/015_conversation_threads.py`
- Create: `apps/api/alembic/versions/016_version_truth_convergence.py`
- Create: `apps/api/alembic/versions/017_source_records_and_links.py`
- Modify: `apps/api/app/models/conversation.py`
- Modify: `apps/api/app/models/project.py`
- Modify: `apps/api/app/models/canvas.py`
- Modify: `apps/api/app/models/__init__.py`

**Backend services and routers**
- Modify: `apps/api/app/services/conversation_service.py`
- Modify: `apps/api/app/services/canvas_service.py`
- Modify: `apps/api/app/services/canvas_agent_orchestrator.py`
- Modify: `apps/api/app/routers/projects.py`
- Modify: `apps/api/app/routers/conversations.py`
- Modify: `apps/api/app/db/init_db.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/entrypoint.sh`
- Create: `apps/api/scripts/dev_bootstrap.sh`

**Frontend**
- Modify: `apps/web/lib/canvas-api.ts`
- Modify: `apps/web/lib/use-project-chat.ts`
- Modify: `apps/web/app/workspace/canvas/[projectId]/page.tsx`
- Modify: `apps/web/types/index.ts`

**Tests**
- Modify: `apps/api/app/tests/test_project_conversation.py`
- Modify: `apps/api/app/tests/test_canvas.py`
- Create: `apps/api/app/tests/test_conversation_threads.py`
- Create: `apps/api/app/tests/test_provenance_links.py`

---

### Task 1: Remove runtime schema mutation and make migrations authoritative

**Files:**
- Modify: `apps/api/app/db/init_db.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/entrypoint.sh`
- Create: `apps/api/scripts/dev_bootstrap.sh`
- Test: `apps/api/app/tests/test_canvas.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_api_startup_does_not_create_missing_columns_implicitly():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_canvas.py -k "does_not_create_missing_columns_implicitly" -v`
Expected: FAIL because startup still calls `create_all()`.

- [ ] **Step 3: Write minimal implementation**

```python
async def seed_if_needed() -> None:
    await seed_database()
```

```python
from app.db.init_db import seed_if_needed
await seed_if_needed()
```

```bash
#!/bin/bash
set -e
alembic upgrade head
python -c "import asyncio; from app.db.init_db import seed_if_needed; asyncio.run(seed_if_needed())"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_canvas.py -k "does_not_create_missing_columns_implicitly" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/db/init_db.py apps/api/app/main.py apps/api/entrypoint.sh apps/api/scripts/dev_bootstrap.sh apps/api/app/tests/test_canvas.py
git commit -m "refactor: make alembic the only schema authority"
```

### Task 2: Introduce conversation threads/scopes

**Files:**
- Create: `apps/api/alembic/versions/015_conversation_threads.py`
- Modify: `apps/api/app/models/conversation.py`
- Modify: `apps/api/app/services/conversation_service.py`
- Modify: `apps/api/app/routers/projects.py`
- Modify: `apps/api/app/routers/conversations.py`
- Test: `apps/api/app/tests/test_conversation_threads.py`
- Test: `apps/api/app/tests/test_project_conversation.py`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_project_and_node_scopes_have_distinct_threads():
    ...

@pytest.mark.asyncio
async def test_llm_history_reads_only_current_thread():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_conversation_threads.py app/tests/test_project_conversation.py -k "thread or scope" -v`
Expected: FAIL because messages are still stored only by conversation id.

- [ ] **Step 3: Write minimal implementation**

```python
class ConversationThread(Base):
    __tablename__ = "conversation_threads"
```

```python
async def get_or_create_thread(..., scope_type: str, scope_ref_id: str | None = None): ...
async def get_thread_history(...): ...
```

```python
@router.get("/{project_id}/conversation")
async def get_project_conversation(...):
    thread = await _conv_service.get_or_create_thread(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_conversation_threads.py app/tests/test_project_conversation.py -k "thread or scope" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/015_conversation_threads.py apps/api/app/models/conversation.py apps/api/app/services/conversation_service.py apps/api/app/routers/projects.py apps/api/app/routers/conversations.py apps/api/app/tests/test_conversation_threads.py apps/api/app/tests/test_project_conversation.py
git commit -m "refactor: model canvas chat scopes as threads"
```

### Task 3: Move frontend chat state from node hint to thread identity

**Files:**
- Modify: `apps/web/lib/canvas-api.ts`
- Modify: `apps/web/lib/use-project-chat.ts`
- Modify: `apps/web/types/index.ts`
- Modify: `apps/web/app/workspace/canvas/[projectId]/page.tsx`

- [ ] **Step 1: Write the failing regression target**

```text
1. 全局对话发送一轮后切到节点 A，节点面板不显示全局消息。
2. 节点 A 发一轮后切到节点 B，节点 B 不显示 A 的消息。
3. 退出节点对话后仍停留在 project thread，不自动回绑。
```

- [ ] **Step 2: Verify the regression exists before the fix**

Run: browser smoke in current branch before frontend thread-id switch
Expected: state still depends on scope reload hints rather than true thread identity.

- [ ] **Step 3: Write minimal implementation**

```ts
type ConversationScopeDetail = ConversationDetail & { threadId: string }
```

```ts
getProjectConversation(projectId, nodeId?) // returns thread id
streamChat(threadId, ...)
```

```ts
const [threadId, setThreadId] = useState<string | null>(null)
```

- [ ] **Step 4: Verify the regression is fixed**

Run: `cd apps/web && npm run lint && npm run build`
Expected: PASS, and manual smoke shows scope isolation by thread.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/canvas-api.ts apps/web/lib/use-project-chat.ts apps/web/types/index.ts apps/web/app/workspace/canvas/[projectId]/page.tsx
git commit -m "refactor: bind canvas chat to thread identity"
```

### Task 4: Converge current-version truth to the project pointer

**Files:**
- Create: `apps/api/alembic/versions/016_version_truth_convergence.py`
- Modify: `apps/api/app/models/project.py`
- Modify: `apps/api/app/models/canvas.py`
- Modify: `apps/api/app/services/canvas_service.py`
- Modify: `apps/api/app/tests/test_canvas.py`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_current_canvas_reads_from_project_pointer_only():
    ...

@pytest.mark.asyncio
async def test_restore_version_updates_single_truth_source():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_canvas.py -k "pointer_only or single_truth_source" -v`
Expected: FAIL because version logic still depends on `is_current`.

- [ ] **Step 3: Write minimal implementation**

```python
project.current_version_id = version.id
```

```python
async def get_current_version(...):
    return await db.get(ProjectVersion, project.current_version_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_canvas.py -k "pointer_only or single_truth_source" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/016_version_truth_convergence.py apps/api/app/models/project.py apps/api/app/models/canvas.py apps/api/app/services/canvas_service.py apps/api/app/tests/test_canvas.py
git commit -m "refactor: converge current version to project pointer"
```

### Task 5: Replace anchor-node provenance with normalized source records

**Files:**
- Create: `apps/api/alembic/versions/017_source_records_and_links.py`
- Modify: `apps/api/app/models/canvas.py`
- Modify: `apps/api/app/services/canvas_agent_orchestrator.py`
- Create: `apps/api/app/tests/test_provenance_links.py`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_group_fill_attaches_sources_to_all_consuming_nodes():
    ...

@pytest.mark.asyncio
async def test_uploaded_and_web_sources_are_materialized_as_records():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_provenance_links.py -v`
Expected: FAIL because web/document sources are still attached only to the anchor node.

- [ ] **Step 3: Write minimal implementation**

```python
class SourceRecord(Base): ...
class NodeSourceLink(Base): ...
```

```python
async def _attach_sources_to_nodes(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_provenance_links.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/alembic/versions/017_source_records_and_links.py apps/api/app/models/canvas.py apps/api/app/services/canvas_agent_orchestrator.py apps/api/app/tests/test_provenance_links.py
git commit -m "refactor: normalize canvas provenance per node"
```

### Task 6: Full regression sweep

**Files:**
- Test: `apps/api/app/tests/test_project_conversation.py`
- Test: `apps/api/app/tests/test_conversation_threads.py`
- Test: `apps/api/app/tests/test_canvas.py`
- Test: `apps/api/app/tests/test_provenance_links.py`

- [ ] **Step 1: Run focused backend regression**

Run: `cd apps/api && pytest app/tests/test_project_conversation.py app/tests/test_conversation_threads.py app/tests/test_canvas.py app/tests/test_provenance_links.py -v`
Expected: PASS

- [ ] **Step 2: Run frontend static verification**

Run: `cd apps/web && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Run Docker smoke**

Run:

```bash
docker compose up -d --build api web
curl http://localhost:8000/health
curl http://localhost:3000
```

Expected: services healthy and canvas workspace accessible.

- [ ] **Step 4: Manual scope/version/provenance smoke**

```text
1. 创建项目并进入 canvas。
2. 全局对话发送一轮，确认 project thread 正常。
3. 切到节点 A，再切到节点 B，消息不串。
4. 退出节点对话，回到全局 thread。
5. 新建版本、切历史版本，确认只读边界正常。
6. 查看节点来源，确认不是只挂在 anchor node。
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: lock canvas architecture regressions"
```
