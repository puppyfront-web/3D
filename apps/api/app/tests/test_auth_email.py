"""Email verification-code auth flow — send / login / reset / abuse limits."""

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import Role, User

pytestmark = pytest.mark.asyncio


async def _seed_login_user(db_session, email="coder@example.com", password="old-pass-123"):
    role = Role(name=f"role-{email}", description=None)
    db_session.add(role)
    await db_session.flush()
    user = User(
        email=email,
        name="Coder",
        role_id=role.id,
        is_active=True,
        hashed_password=hash_password(password),
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _send_code(client: AsyncClient, email: str, purpose: str = "login"):
    res = await client.post(
        "/api/v1/auth/email-code/send",
        json={"email": email, "purpose": purpose},
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def test_email_code_login_flow(client: AsyncClient, db_session):
    await _seed_login_user(db_session)
    data = await _send_code(client, "coder@example.com")
    # mock email provider → dev_code returned so the flow is testable
    assert data["devCode"] and len(data["devCode"]) == 6

    res = await client.post(
        "/api/v1/auth/login/email",
        json={"email": "coder@example.com", "code": data["devCode"]},
    )
    assert res.status_code == 200, res.text
    payload = res.json()["data"]
    assert payload["accessToken"]
    assert payload["user"]["email"] == "coder@example.com"


async def test_code_is_single_use(client: AsyncClient, db_session):
    await _seed_login_user(db_session)
    data = await _send_code(client, "coder@example.com")
    ok = await client.post(
        "/api/v1/auth/login/email",
        json={"email": "coder@example.com", "code": data["devCode"]},
    )
    assert ok.status_code == 200
    replay = await client.post(
        "/api/v1/auth/login/email",
        json={"email": "coder@example.com", "code": data["devCode"]},
    )
    assert replay.status_code == 401


async def test_wrong_code_increments_attempts_then_locks(client: AsyncClient, db_session):
    from app.services.verification_code_service import MAX_ATTEMPTS

    await _seed_login_user(db_session)
    data = await _send_code(client, "coder@example.com")

    for _ in range(MAX_ATTEMPTS):
        res = await client.post(
            "/api/v1/auth/login/email",
            json={"email": "coder@example.com", "code": "000000"},
        )
        assert res.status_code == 401

    # correct code no longer accepted after exhausting attempts
    res = await client.post(
        "/api/v1/auth/login/email",
        json={"email": "coder@example.com", "code": data["devCode"]},
    )
    assert res.status_code == 401


async def test_resend_cooldown(client: AsyncClient, db_session):
    await _seed_login_user(db_session)
    await _send_code(client, "coder@example.com")
    res = await client.post(
        "/api/v1/auth/email-code/send",
        json={"email": "coder@example.com", "purpose": "login"},
    )
    assert res.status_code == 429


async def test_unknown_email_rejected(client: AsyncClient):
    res = await client.post(
        "/api/v1/auth/email-code/send",
        json={"email": "nobody@example.com", "purpose": "login"},
    )
    assert res.status_code == 404


async def test_password_reset_flow(client: AsyncClient, db_session):
    await _seed_login_user(db_session, password="old-pass-123")
    data = await _send_code(client, "coder@example.com", purpose="reset")

    res = await client.post(
        "/api/v1/auth/password/reset",
        json={
            "email": "coder@example.com",
            "code": data["devCode"],
            "new_password": "brand-new-pass-456",
        },
    )
    assert res.status_code == 200, res.text

    # old password no longer works, new one does
    old = await client.post(
        "/api/v1/auth/login",
        json={"email": "coder@example.com", "password": "old-pass-123"},
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/auth/login",
        json={"email": "coder@example.com", "password": "brand-new-pass-456"},
    )
    assert new.status_code == 200
