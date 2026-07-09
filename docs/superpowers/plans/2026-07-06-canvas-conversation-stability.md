# Canvas Conversation Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the canvas left-rail conversation so node-scoped chat, node switching, and version switching never leak messages across scopes.

**Architecture:** Keep a single project conversation record, but make history reads scope-aware on the backend and scope-aware reloads on the frontend. Treat scope switches as hard boundaries: abort the old stream, clear transient state, fetch the new scope, and ignore stale callbacks.

**Tech Stack:** FastAPI, SQLAlchemy async, Next.js, React 19, Zustand, pytest

---

### Task 1: Define scope filtering in the backend

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`
- Modify: `apps/api/app/routers/projects.py`
- Test: `apps/api/app/tests/test_project_conversation.py`

- [x] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_get_project_conversation_filters_global_vs_node_scope(...):
    ...

@pytest.mark.asyncio
async def test_get_project_conversation_hides_legacy_node_turn_from_global_scope(...):
    ...
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_project_conversation.py -k "scope or legacy" -v`
Expected: FAIL because the endpoint always returns full history.

- [x] **Step 3: Write minimal implementation**

```python
async def get_history(...): ...
def filter_messages_for_scope(...): ...
@router.get("/{project_id}/conversation")
async def get_project_conversation(..., node_id: str | None = None): ...
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_project_conversation.py -k "scope or legacy" -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/routers/projects.py apps/api/app/tests/test_project_conversation.py
git commit -m "fix: scope project conversation history"
```

### Task 2: Persist node scope metadata for new node-scoped turns

**Files:**
- Modify: `apps/api/app/services/conversation_service.py`
- Test: `apps/api/app/tests/test_project_conversation.py`

- [x] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_node_scoped_stream_persists_user_message_with_node_id(...):
    ...
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/api && pytest app/tests/test_project_conversation.py -k "persists_user_message_with_node_id" -v`
Expected: FAIL because the user message is saved without `metadata.node_id`.

- [x] **Step 3: Write minimal implementation**

```python
await self.save_message(
    db,
    conv_uuid,
    "user",
    user_message,
    metadata={"node_id": node_id} if node_id else None,
    auto_commit=True,
)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd apps/api && pytest app/tests/test_project_conversation.py -k "persists_user_message_with_node_id" -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add apps/api/app/services/conversation_service.py apps/api/app/tests/test_project_conversation.py
git commit -m "fix: persist node scope metadata on chat turns"
```

### Task 3: Reload frontend history by scope and cut stale streams

**Files:**
- Modify: `apps/web/lib/canvas-api.ts`
- Modify: `apps/web/lib/use-project-chat.ts`

- [x] **Step 1: Write the failing test or explicit regression target**

Because the web app currently has no frontend test harness, encode the regression as a deterministic manual verification target:

```text
1. Enter node A, send a message, switch to node B.
2. Node B must not show node A messages.
3. Switch back to global scope.
4. Global scope must not show node-scoped messages.
5. While streaming in node A, switch to node B.
6. Old stream must not append into node B.
```

- [x] **Step 2: Verify the regression exists before the fix**

Run: manual inspection in current build
Expected: stale node messages leak across scope boundaries.

- [x] **Step 3: Write minimal implementation**

```ts
getProjectConversation(projectId, nodeId?)
useEffect(() => {
  abortRef.current?.abort();
  clearStreamingState();
  loadConversationForScope();
}, [projectId, activeNodeId]);
```

- [x] **Step 4: Verify the regression is fixed**

Run: `cd apps/web && npm run lint`
Then perform the manual flow above.
Expected: no cross-scope message leakage, no stale stream append.

- [x] **Step 5: Commit**

```bash
git add apps/web/lib/canvas-api.ts apps/web/lib/use-project-chat.ts
git commit -m "fix: isolate canvas conversation state by scope"
```

### Task 4: Full regression sweep

**Files:**
- Test: `apps/api/app/tests/test_project_conversation.py`
- Test: `apps/api/app/tests/test_conversation_persistence.py`

- [x] **Step 1: Run focused backend regression**

Run: `cd apps/api && pytest app/tests/test_project_conversation.py app/tests/test_conversation_persistence.py -v`
Expected: PASS

- [x] **Step 2: Run broader canvas regression**

Run: `cd apps/api && pytest app/tests/test_canvas.py app/tests/test_project_conversation.py app/tests/test_conversation_persistence.py -v`
Expected: PASS

- [x] **Step 3: Run frontend static verification**

Run: `cd apps/web && npm run lint`
Expected: PASS

- [x] **Step 4: Manual canvas verification**

```text
1. 全局对话发送一轮，确认显示正常
2. 切节点 A，对话只显示 A 历史
3. 切节点 B，对话只显示 B 历史
4. 退出节点，对话只显示全局历史
5. 切历史版本，节点标签消失且不残留节点消息
6. 历史版本点节点，不应持续停留在节点级聊天
```

- [x] **Step 5: Commit**

```bash
git add -A
git commit -m "test: lock canvas conversation regressions"
```
