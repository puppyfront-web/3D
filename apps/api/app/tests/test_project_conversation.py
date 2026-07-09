"""Tests for project-scoped conversations — the canvas workspace chat wiring.

Covers:
  - GET /projects/{id}/conversation: get-or-create semantics (idempotent, binds
    the conversation to the project, returns history).
  - GET /conversations?project_id=...: list filtering by project.

These back the canvas workspace left-rail chat panel, which needs a stable,
project-bound conversation independent of the global sidebar chat list.

Note: tests create their own project/company rows with unique names rather than
reusing the shared `sample_project_id` fixture, because that fixture inserts a
hard-coded company name ("Test Company") which trips the UNIQUE constraint on
companies.name when several tests in one session each request it.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.conversation import Message
from app.services.conversation_service import ConversationService


async def _seed_project(db_session) -> uuid.UUID:
    """Insert a fresh project (with a unique company) and return its id."""
    from app.models.project import Company, Project
    from app.models.user import Role, User

    suffix = uuid.uuid4().hex[:8]
    role = Role(
        id=uuid.uuid4(),
        name=f"role_{suffix}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email=f"user_{suffix}@test",
        name=f"User {suffix}",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()

    company = Company(
        id=uuid.uuid4(),
        name=f"Company {suffix}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()

    project = Project(
        id=uuid.uuid4(),
        name=f"Project {suffix}",
        company_id=company.id,
        owner_id=user.id,
        status="draft",
        priority="medium",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.flush()
    return project.id


@pytest.mark.asyncio
async def test_get_project_conversation_creates_and_is_idempotent(
    client, db_session
):
    """First call creates a conversation bound to the project; the second call
    returns the same conversation (get-or-create), not a new one."""
    project_id = await _seed_project(db_session)

    r1 = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert r1.status_code == 200
    body1 = r1.json()["data"]
    assert body1["projectId"] == str(project_id)
    conv_id = body1["id"]
    assert body1["messageCount"] == 0

    # Second call is idempotent — same conversation, no duplicate.
    r2 = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert r2.status_code == 200
    body2 = r2.json()["data"]
    assert body2["id"] == conv_id


@pytest.mark.asyncio
async def test_get_project_conversation_returns_history(client, db_session):
    """After posting a message via the non-streaming endpoint, the
    project-conversation endpoint must include it in history."""
    project_id = await _seed_project(db_session)

    # Create + grab the conversation id.
    r = await client.get(f"/api/v1/projects/{project_id}/conversation")
    conv_id = r.json()["data"]["id"]

    # Post a user message (non-streaming fallback).
    await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"message": "补充企业的荣誉资质"},
    )

    # Reload via the project endpoint — history must include the round trip.
    r2 = await client.get(f"/api/v1/projects/{project_id}/conversation")
    body = r2.json()["data"]
    assert body["messageCount"] >= 2  # user + assistant ack
    roles = [m["role"] for m in body["messages"]]
    assert "user" in roles


@pytest.mark.asyncio
async def test_get_project_conversation_404_for_missing_project(client):
    """A non-existent project must 404, not create an orphan conversation."""
    r = await client.get(f"/api/v1/projects/{uuid.uuid4()}/conversation")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_conversations_filters_by_project(client, db_session):
    """GET /conversations?project_id=... returns only that project's
    conversation, isolating canvas chat from the global sidebar list."""
    project_id = await _seed_project(db_session)

    # Create the project-bound conversation.
    r = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert r.status_code == 200
    project_conv_id = r.json()["data"]["id"]

    # Also create a free-standing (no project) conversation.
    other = await client.post("/api/v1/conversations", json={"title": "闲聊"})
    assert other.status_code == 200
    other_id = other.json()["data"]["id"]
    assert other_id != project_conv_id

    # Scoped list returns only the project conversation.
    scoped = await client.get(
        f"/api/v1/conversations?project_id={project_id}"
    )
    assert scoped.status_code == 200
    items = scoped.json()["data"]
    ids = [c["id"] for c in items]
    assert project_conv_id in ids
    assert other_id not in ids


async def _create_first_canvas_node_id(client, project_id: uuid.UUID) -> str:
    """Create V1 for a project and return its first node id."""
    create = await client.post(f"/api/v1/projects/{project_id}/versions")
    assert create.status_code == 201, create.text
    canvas = (await client.get(f"/api/v1/projects/{project_id}/canvas")).json()["data"]
    return canvas["nodes"][0]["id"]


@pytest.mark.asyncio
async def test_get_project_conversation_filters_global_vs_node_scope(
    client, db_session
):
    """Project conversation history must be filtered by scope.

    Global scope excludes node-scoped turns. A node scope returns only the
    turns for that node.
    """
    project_id = await _seed_project(db_session)
    node_id = await _create_first_canvas_node_id(client, project_id)

    r = await client.get(f"/api/v1/projects/{project_id}/conversation")
    conv_id = r.json()["data"]["id"]
    service = ConversationService()

    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "user",
        "这是全局问题",
        metadata={"scope": "global"},
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "assistant",
        "这是全局回答",
        metadata={"intent": "conversational"},
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "user",
        "这是节点问题",
        metadata={"node_id": node_id},
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "assistant",
        "这是节点回答",
        metadata={"intent": "node_edit", "node_id": node_id},
    )
    await db_session.commit()

    global_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert global_resp.status_code == 200
    global_messages = global_resp.json()["data"]["messages"]
    assert [m["content"] for m in global_messages] == ["这是全局问题", "这是全局回答"]

    node_resp = await client.get(
        f"/api/v1/projects/{project_id}/conversation?node_id={node_id}"
    )
    assert node_resp.status_code == 200
    node_messages = node_resp.json()["data"]["messages"]
    assert [m["content"] for m in node_messages] == ["这是节点问题", "这是节点回答"]


@pytest.mark.asyncio
async def test_get_project_conversation_hides_legacy_node_turn_from_global_scope(
    client, db_session
):
    """Legacy node turns without user metadata must still stay out of global scope."""
    project_id = await _seed_project(db_session)
    node_id = await _create_first_canvas_node_id(client, project_id)

    r = await client.get(f"/api/v1/projects/{project_id}/conversation")
    conv_id = r.json()["data"]["id"]
    service = ConversationService()

    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "user",
        "遗留节点提问",
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "assistant",
        "遗留节点回答",
        metadata={"intent": "node_edit", "node_id": node_id},
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "user",
        "后续全局提问",
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "assistant",
        "后续全局回答",
        metadata={"intent": "conversational"},
    )
    await db_session.commit()

    global_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    assert global_resp.status_code == 200
    global_messages = global_resp.json()["data"]["messages"]
    assert [m["content"] for m in global_messages] == ["后续全局提问", "后续全局回答"]

    node_resp = await client.get(
        f"/api/v1/projects/{project_id}/conversation?node_id={node_id}"
    )
    assert node_resp.status_code == 200
    node_messages = node_resp.json()["data"]["messages"]
    assert [m["content"] for m in node_messages] == ["遗留节点提问", "遗留节点回答"]


class _StubNodeEditLLM:
    async def generate_with_history_stream(self, messages, system_prompt, temperature):
        yield "建议先补充企业规模和代表案例。"


async def _drain(gen):
    async for _ in gen:
        pass


@pytest.mark.asyncio
async def test_node_scoped_stream_persists_user_message_with_node_id(
    client, db_session, monkeypatch
):
    """Node-scoped turns must persist node_id on the user message as well."""
    project_id = await _seed_project(db_session)
    node_id = await _create_first_canvas_node_id(client, project_id)

    conv_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    conv_id = conv_resp.json()["data"]["id"]

    async def _stub_get_llm_service(db):
        return _StubNodeEditLLM()

    monkeypatch.setattr(
        "app.services.conversation_service.get_llm_service",
        _stub_get_llm_service,
    )

    service = ConversationService()
    await _drain(
        service.process_message_stream(
            db_session,
            conv_id,
            "请补强这个节点的表达",
            node_id=node_id,
        )
    )

    messages = (
        await db_session.execute(
            select(Message)
            .where(Message.conversation_id == uuid.UUID(conv_id))
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()
    assert [m.role for m in messages[-2:]] == ["user", "assistant"]
    assert messages[-2].metadata_json is not None
    assert messages[-2].metadata_json["node_id"] == node_id
    assert messages[-1].metadata_json is not None
    assert messages[-1].metadata_json["node_id"] == node_id


@pytest.mark.asyncio
async def test_project_and_node_scopes_have_distinct_threads(client, db_session):
    """Project and node scopes must resolve to different persistent threads."""
    project_id = await _seed_project(db_session)
    node_id = await _create_first_canvas_node_id(client, project_id)

    global_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    node_resp = await client.get(
        f"/api/v1/projects/{project_id}/conversation?node_id={node_id}"
    )

    assert global_resp.status_code == 200
    assert node_resp.status_code == 200
    assert global_resp.json()["data"]["threadId"] != node_resp.json()["data"]["threadId"]


@pytest.mark.asyncio
async def test_thread_scoped_history_does_not_leak_between_project_and_node(
    client, db_session, monkeypatch
):
    """Node-thread history must stay isolated from the project thread."""
    project_id = await _seed_project(db_session)
    node_id = await _create_first_canvas_node_id(client, project_id)

    global_resp = await client.get(f"/api/v1/projects/{project_id}/conversation")
    conv_id = global_resp.json()["data"]["id"]
    project_thread_id = global_resp.json()["data"]["threadId"]
    node_thread_id = (
        await client.get(f"/api/v1/projects/{project_id}/conversation?node_id={node_id}")
    ).json()["data"]["threadId"]

    async def _stub_get_llm_service(db):
        return _StubNodeEditLLM()

    monkeypatch.setattr(
        "app.services.conversation_service.get_llm_service",
        _stub_get_llm_service,
    )

    service = ConversationService()
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "user",
        "全局问题",
        thread_id=uuid.UUID(project_thread_id),
    )
    await service.save_message(
        db_session,
        uuid.UUID(conv_id),
        "assistant",
        "全局回答",
        thread_id=uuid.UUID(project_thread_id),
    )
    await _drain(
        service.process_message_stream(
            db_session,
            conv_id,
            "节点问题",
            node_id=node_id,
            thread_id=node_thread_id,
        )
    )

    reloaded_global = await client.get(f"/api/v1/projects/{project_id}/conversation")
    reloaded_node = await client.get(
        f"/api/v1/projects/{project_id}/conversation?node_id={node_id}"
    )

    assert [m["content"] for m in reloaded_global.json()["data"]["messages"]] == [
        "全局问题",
        "全局回答",
    ]
    assert [m["content"] for m in reloaded_node.json()["data"]["messages"]] == [
        "节点问题",
        "建议先补充企业规模和代表案例。",
    ]
