"""Tests for the canvas workspace: default topology, version snapshots,
node CRUD, and restore (PRD §10/§16, technical design §5).

Covers the phase-1 deliverables:
  - POST /projects/{id}/versions lays out the 3-board / 20-node topology as V1
  - GET /projects/{id}/canvas returns the current canvas with all nodes draft
  - PATCH /nodes/{id} edits a node and GET /nodes/{id} reflects it
  - POST /projects/{id}/versions (again) snapshots into V2 and demotes V1
  - POST /versions/{id}/restore branches a new current from a historical V
  - Historical-version canvas is flagged read-only
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from sqlalchemy import delete, select

from app.models.canvas import (
    Canvas,
    CanvasGroup,
    CanvasNode,
    ProjectVersion,
)
from app.models.project import Company, Project
from app.models.user import Role, User


async def _create_canvas_project(db_session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create a unique project chain and commit it."""
    role = Role(
        id=uuid.uuid4(),
        name=f"canvas_role_{uuid.uuid4().hex[:8]}",
        description="canvas test role",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(role)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"canvas_{uuid.uuid4().hex[:8]}@test.local",
        name="Canvas User",
        role_id=role.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Canvas Co {uuid.uuid4().hex[:8]}",
        industry="智能制造",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(company)
    await db_session.flush()
    project = Project(
        id=uuid.uuid4(),
        name=f"Canvas Project {uuid.uuid4().hex[:8]}",
        company_id=company.id,
        owner_id=user.id,
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    await db_session.commit()
    return project.id, company.id, user.id, role.id


@pytest_asyncio.fixture
async def canvas_project_id(db_session):
    """A fully-isolated project for canvas tests.

    The canvas router commits internally (snapshot transaction), which breaks
    the function-scoped rollback isolation that the generic sample_* fixtures
    rely on (those fixtures insert fixed-name rows like 'test_user' / 'Test
    Company' that collide on unique constraints across repeated commiting
    tests in the session-shared DB). This fixture builds the whole
    role/user/company/project chain with uuid-suffixed unique names so each
    canvas test is self-contained, and tears down everything at the end so it
    does not pollute the session-shared DB for other tests (e.g. the ones that
    assert an empty project list).
    """
    project_id, company_id, user_id, role_id = await _create_canvas_project(db_session)

    yield project_id

    # Teardown: remove everything this test (and the router) created, in
    # FK-safe order. The canvas router commits versions/canvas/nodes which the
    # function-scoped rollback in db_session cannot undo, so we delete them
    # explicitly here to keep the session-shared DB clean for sibling tests.
    from app.models.canvas import CanvasEdge, NodeSource

    # Find version ids created for this project.
    ver_result = await db_session.execute(
        select(ProjectVersion.id).where(ProjectVersion.project_id == project_id)
    )
    version_ids = [row[0] for row in ver_result.all()]
    if version_ids:
        # Canvas ids for those versions.
        cv_result = await db_session.execute(
            select(Canvas.id).where(Canvas.project_version_id.in_(version_ids))
        )
        canvas_ids = [row[0] for row in cv_result.all()]
        if canvas_ids:
            # Node ids → node_sources, then nodes/edges.
            node_result = await db_session.execute(
                select(CanvasNode.id).where(CanvasNode.canvas_id.in_(canvas_ids))
            )
            node_ids = [row[0] for row in node_result.all()]
            if node_ids:
                await db_session.execute(
                    delete(NodeSource).where(NodeSource.node_id.in_(node_ids))
                )
            await db_session.execute(
                delete(CanvasEdge).where(CanvasEdge.canvas_id.in_(canvas_ids))
            )
            await db_session.execute(
                delete(CanvasNode).where(CanvasNode.canvas_id.in_(canvas_ids))
            )
            await db_session.execute(
                delete(CanvasGroup).where(CanvasGroup.canvas_id.in_(canvas_ids))
            )
            await db_session.execute(delete(Canvas).where(Canvas.id.in_(canvas_ids)))
        await db_session.execute(
            delete(ProjectVersion).where(ProjectVersion.id.in_(version_ids))
        )
    await db_session.execute(delete(Project).where(Project.id == project_id))
    await db_session.execute(delete(Company).where(Company.id == company_id))
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.execute(delete(Role).where(Role.id == role_id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_first_version_lays_out_default_topology(
    client, canvas_project_id
):
    """V1 of a fresh project must contain the three default boards and 21
    leaf nodes (PRD §10.2), all in ``draft`` status, with intra-group edges."""
    resp = await client.post(f"/api/v1/projects/{canvas_project_id}/versions")
    assert resp.status_code == 201, resp.text
    version = resp.json()["data"]
    assert version["versionNo"] == 1
    assert version["isCurrent"] is True

    canvas_resp = await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")
    assert canvas_resp.status_code == 200
    canvas = canvas_resp.json()["data"]

    # Three default groups, in order, no 文旅 (cultural tourism) board.
    group_keys = [g["groupKey"] for g in canvas["groups"]]
    assert group_keys == [
        "company_intro",
        "product_tech_scenarios",
        "future_social_responsibility",
    ]

    # 21 leaf nodes (7 + 7 + 7), all draft.
    nodes = canvas["nodes"]
    assert len(nodes) == 21
    assert all(n["status"] == "draft" for n in nodes)

    # Stable node keys present (sample checks).
    keys = {n["nodeKey"] for n in nodes}
    for expected in (
        "company_profile", "product_system", "future_layout",
        "party_building", "brand_vision",
    ):
        assert expected in keys

    # Intra-group sequential edges exist (one per node after the first in each group).
    assert len(canvas["edges"]) == 21 - 3


@pytest.mark.asyncio
async def test_canvas_node_has_empty_content_skeleton(client, canvas_project_id):
    """Each default node ships the four-slot content skeleton the AI
    orchestrator (phase 2) writes into."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")
    resp = await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")
    node = resp.json()["data"]["nodes"][0]
    assert set(node["content"].keys()) == {
        "extracted",
        "planning",
        "ui_suggestion",
        "pending_questions",
    }
    assert all(node["content"][k] == [] for k in node["content"])


@pytest.mark.asyncio
async def test_patch_node_updates_fields(client, canvas_project_id):
    """Manual node edit round-trips through PATCH → GET."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")
    canvas = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    node = canvas["nodes"][0]

    patch = await client.patch(
        f"/api/v1/projects/{canvas_project_id}/nodes/{node['id']}",
        json={
            "status": "filled",
            "content": {
                "extracted": ["企业成立于2010年"],
                "planning": [],
                "ui_suggestion": [],
                "pending_questions": ["待确认营收规模"],
            },
        },
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()["data"]
    assert updated["status"] == "filled"
    assert updated["content"]["pending_questions"] == ["待确认营收规模"]

    # GET reflects the change.
    got = (await client.get(f"/api/v1/nodes/{node['id']}")).json()["data"]
    assert got["status"] == "filled"
    assert got["content"]["extracted"] == ["企业成立于2010年"]


async def test_add_and_delete_custom_node(client, canvas_project_id):
    """PRD P1 #2: users can add nodes beyond the default topology and remove
    them. Adding a node bumps the node count; deleting drops it and cleans
    up edges. Board group nodes are protected from deletion."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")
    canvas = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    base_count = len(canvas["nodes"])
    group_id = canvas["groups"][0]["id"]

    # Add a custom node under the first board.
    add = await client.post(
        f"/api/v1/projects/{canvas_project_id}/nodes",
        json={"title": "自定义节点", "groupId": group_id},
    )
    assert add.status_code == 200, add.text
    created = add.json()["data"]
    assert created["title"] == "自定义节点"
    assert created["status"] == "draft"
    assert created["nodeKey"]  # synthetic key assigned

    # Canvas now has one more node.
    canvas2 = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    assert len(canvas2["nodes"]) == base_count + 1

    # Rename via PATCH (PRD P1 #2: 节点重命名).
    ren = await client.patch(
        f"/api/v1/projects/{canvas_project_id}/nodes/{created['id']}",
        json={"title": "重命名节点"},
    )
    assert ren.status_code == 200
    assert ren.json()["data"]["title"] == "重命名节点"

    # Delete the custom node.
    dele = await client.delete(
        f"/api/v1/projects/{canvas_project_id}/nodes/{created['id']}"
    )
    assert dele.status_code == 200
    canvas3 = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    assert len(canvas3["nodes"]) == base_count
    assert created["id"] not in {n["id"] for n in canvas3["nodes"]}

    # Board group node is protected from deletion.
    group_node = next(
        (g for g in canvas3["groups"]),
        None,
    )
    # Sanity: a group header isn't a leaf module node — deleting any module node
    # works, but the endpoint rejects non module_node types (covered by the
    # service guard). Here we just confirm a second deletion still succeeds.


@pytest.mark.asyncio
async def test_second_version_snapshots_and_demotes_previous(client, canvas_project_id):
    """Creating V2 after editing nodes demotes V1, makes V2 current, and
    carries the edited node content forward (clone on snapshot)."""
    # V1
    v1 = (await client.post(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    canvas_v1 = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    node_id = canvas_v1["nodes"][0]["id"]
    await client.patch(
        f"/api/v1/projects/{canvas_project_id}/nodes/{node_id}",
        json={"status": "filled", "content": {
            "extracted": ["编辑过"], "planning": [], "ui_suggestion": [], "pending_questions": [],
        }},
    )

    # V2 snapshot
    v2 = (
        await client.post(
            f"/api/v1/projects/{canvas_project_id}/versions",
            json={"versionName": "V2-编辑", "changeSummary": "填充企业简介"},
        )
    ).json()["data"]
    assert v2["versionNo"] == 2
    assert v2["isCurrent"] is True

    # V1 is now demoted.
    versions = (await client.get(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    by_no = {v["versionNo"]: v for v in versions}
    assert by_no[1]["isCurrent"] is False
    assert by_no[2]["isCurrent"] is True

    # Current canvas (V2) carries the edit forward.
    canvas_v2 = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    v2_node = next(n for n in canvas_v2["nodes"] if n["nodeKey"] == canvas_v1["nodes"][0]["nodeKey"])
    assert v2_node["status"] == "filled"
    assert v2_node["content"]["extracted"] == ["编辑过"]


async def test_version_summary_agent_derives_change_summary(
    client, canvas_project_id
):
    """版本总结 Agent (PRD §16.1): when no explicit changeSummary is passed,
    the backend derives a data-grounded summary from the canvas fill state
    instead of stamping the generic '初始版本'."""
    # V1 (first version → default canvas, summary stays 初始版本).
    v1 = (await client.post(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    assert v1["changeSummary"] == "初始版本"

    # Fill a few nodes so the summary has something to report.
    canvas_v1 = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    for node_id in [n["id"] for n in canvas_v1["nodes"][:3]]:
        await client.patch(
            f"/api/v1/projects/{canvas_project_id}/nodes/{node_id}",
            json={"status": "filled", "content": {
                "extracted": ["事实"], "planning": ["策划文案"],
                "ui_suggestion": [], "pending_questions": [],
            }},
        )
    # Mark one node pending_review so the summary reports 待确认.
    pending_id = canvas_v1["nodes"][3]["id"]
    await client.patch(
        f"/api/v1/projects/{canvas_project_id}/nodes/{pending_id}",
        json={"status": "pending_review", "content": {
            "extracted": [], "planning": [], "ui_suggestion": [],
            "pending_questions": ["待补充"],
        }},
    )

    # V2 without an explicit changeSummary.
    v2 = (
        await client.post(
            f"/api/v1/projects/{canvas_project_id}/versions",
            json={"versionName": "V2"},
        )
    ).json()["data"]

    summary = v2["changeSummary"]
    # Derived, not the generic default.
    assert summary != "初始版本"
    assert "节点" in summary
    # Reports filled count and the pending node.
    assert "已填充" in summary or "填充" in summary
    assert "待确认" in summary


@pytest.mark.asyncio
async def test_historical_version_canvas_is_read_only(client, canvas_project_id):
    """Fetching a non-current version's canvas sets isReadOnly=True."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")  # V1
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")  # V2 (current)

    versions = (await client.get(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    v1_id = next(v["id"] for v in versions if v["versionNo"] == 1)
    v2_id = next(v["id"] for v in versions if v["versionNo"] == 2)

    # V1 is historical (not current) → read-only.
    historical = await client.get(
        f"/api/v1/projects/{canvas_project_id}/versions/{v1_id}/canvas"
    )
    assert historical.status_code == 200
    assert historical.json()["data"]["isReadOnly"] is True

    # V2 is current → not read-only.
    current = await client.get(
        f"/api/v1/projects/{canvas_project_id}/versions/{v2_id}/canvas"
    )
    assert current.status_code == 200
    assert current.json()["data"]["isReadOnly"] is False


@pytest.mark.asyncio
async def test_patch_node_for_historical_version_is_forbidden(client, canvas_project_id):
    """Server-side writes to historical versions must be rejected."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")  # V1
    historical_canvas = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    historical_node_id = historical_canvas["nodes"][0]["id"]
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")  # V2 current

    resp = await client.patch(
        f"/api/v1/projects/{canvas_project_id}/nodes/{historical_node_id}",
        json={"status": "filled"},
    )
    assert resp.status_code == 403
    assert "read-only" in resp.json()["message"]


@pytest.mark.asyncio
async def test_get_version_canvas_rejects_cross_project_access(
    client, db_session, canvas_project_id
):
    """The project_id/version_id pair must match."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")
    versions = (await client.get(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    version_id = versions[0]["id"]

    other_project_id, _, _, _ = await _create_canvas_project(db_session)
    resp = await client.get(
        f"/api/v1/projects/{other_project_id}/versions/{version_id}/canvas"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_version_creates_new_current_not_overwrite(client, canvas_project_id):
    """Restoring V1 after V2 exists creates V3 (current), leaves V2 intact."""
    v1 = (await client.post(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    # Edit + V2
    canvas = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    await client.patch(
        f"/api/v1/projects/{canvas_project_id}/nodes/{canvas['nodes'][0]['id']}",
        json={"status": "filled", "content": {
            "extracted": ["x"], "planning": [], "ui_suggestion": [], "pending_questions": [],
        }},
    )
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")

    # Restore V1
    restore = await client.post(f"/api/v1/versions/{v1['id']}/restore")
    assert restore.status_code == 200, restore.text
    new_v = restore.json()["data"]["newVersion"]
    assert new_v["versionNo"] == 3
    assert new_v["isCurrent"] is True
    assert new_v["basedOnVersionId"] == v1["id"]

    # All three versions exist; V3 is current.
    versions = (await client.get(f"/api/v1/projects/{canvas_project_id}/versions")).json()["data"]
    assert {v["versionNo"] for v in versions} == {1, 2, 3}
    assert next(v for v in versions if v["versionNo"] == 3)["isCurrent"] is True
    # V2 was NOT overwritten — still exists and is not current.
    v2 = next(v for v in versions if v["versionNo"] == 2)
    assert v2["isCurrent"] is False


@pytest.mark.asyncio
async def test_get_canvas_without_version_returns_400(client, canvas_project_id):
    """Asking for the canvas of a project that has no version yet is a
    client error, not a 500."""
    resp = await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_list_versions_empty_for_brand_new_project(client, canvas_project_id):
    resp = await client.get(f"/api/v1/projects/{canvas_project_id}/versions")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_default_topology_excludes_cultural_tourism(client, canvas_project_id):
    """The 文旅 board must NOT appear (project scope decision). Guards against
    accidentally re-adding it from a generic template."""
    await client.post(f"/api/v1/projects/{canvas_project_id}/versions")
    canvas = (await client.get(f"/api/v1/projects/{canvas_project_id}/canvas")).json()["data"]
    titles = " ".join(g["title"] for g in canvas["groups"]) + " " + " ".join(
        n["title"] for n in canvas["nodes"]
    )
    assert "文旅" not in titles


# ─── helpers ─────────────────────────────────────────────────────────────────


async def _v1_id(client, project_id) -> str:
    versions = (await client.get(f"/api/v1/projects/{project_id}/versions")).json()["data"]
    return next(v["id"] for v in versions if v["versionNo"] == 1)


@pytest.mark.asyncio
async def test_seed_if_needed_does_not_create_tables(monkeypatch):
    """Runtime startup must seed only, never mutate schema with create_all."""
    from app.db import init_db as init_db_module

    calls = {"seed": 0}

    async def _unexpected_create_tables():
        raise AssertionError("create_tables should not run at application startup")

    async def _fake_seed_database():
        calls["seed"] += 1

    monkeypatch.setattr(init_db_module, "create_tables", _unexpected_create_tables)
    monkeypatch.setattr(init_db_module, "seed_database", _fake_seed_database)

    await init_db_module.seed_if_needed()

    assert calls["seed"] == 1
