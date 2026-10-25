"""Security review 2026-10-25: tests that pin each fix. Written before the fix (TDD)."""

import pytest
from httpx import AsyncClient

from tests.conftest import register


# --- 1. The unauthenticated admin router is gone -------------------------------- #


async def test_open_admin_endpoints_are_removed(client: AsyncClient):
    assert (await client.get("/admin/users")).status_code == 404
    assert (await client.post("/admin/users/create-admin", params={"email": "e@e.io", "password": "p"})).status_code == 404
    assert (await client.post("/admin/seed-admin")).status_code == 404
    assert (await client.post("/admin/projects/force-infinite-balance")).status_code == 404


# --- 2. The default JWT secret is refused outside debug ------------------------- #


def test_default_jwt_secret_rejected_in_production():
    from shared.config.settings import DEFAULT_JWT_SECRET, Settings

    with pytest.raises(ValueError):
        Settings(debug=False, jwt_secret=DEFAULT_JWT_SECRET)
    # A real, long secret is accepted.
    Settings(debug=False, jwt_secret="x" * 40)


# --- 3. The e-mail verification link is not a full session ---------------------- #


async def test_verification_link_token_cannot_open_a_session(client: AsyncClient):
    from services.auth_service.routes.auth import _create_verify_token
    from shared.auth.jwt_utils import decode_access_token

    headers = await register(client, "verify@example.com")
    uid = (await client.get("/api/users/profile", headers=headers)).json()["id"]

    link_token = _create_verify_token(uid)
    assert decode_access_token(link_token) is None  # useless as a session token

    # It still verifies the e-mail,
    ok = await client.post("/api/auth/verify-email", headers={"Authorization": f"Bearer {link_token}"})
    assert ok.status_code == 200
    # but a real access token must NOT be usable to verify someone's e-mail.
    access = headers["Authorization"].split()[1]
    assert (await client.post("/api/auth/verify-email", headers={"Authorization": f"Bearer {access}"})).status_code == 401


# --- 4. Repeated failed logins are throttled ------------------------------------ #


async def test_repeated_failed_logins_are_throttled(client: AsyncClient):
    await register(client, "brute@example.com")
    client.cookies.clear()
    statuses = [
        (await client.post("/api/auth/login", json={"email": "brute@example.com", "password": f"bad{i}"})).status_code
        for i in range(25)
    ]
    assert 429 in statuses


# --- 5. Password length is validated instead of crashing bcrypt ----------------- #


async def test_overlong_password_is_rejected_cleanly(client: AsyncClient):
    r = await client.post("/api/auth/register", json={"email": "long@example.com", "password": "x" * 100})
    assert r.status_code == 422


# --- 6. E-mail is validated ----------------------------------------------------- #


async def test_invalid_email_is_rejected(client: AsyncClient):
    r = await client.post("/api/auth/register", json={"email": "not-an-email", "password": "secret123"})
    assert r.status_code == 422


# --- 7. Notifications require authentication ------------------------------------ #


async def test_notifications_require_auth(client: AsyncClient):
    assert (await client.get("/api/notifications/")).status_code == 401


# --- 8. proklik can't be asked for an unbounded number of tasks ----------------- #


async def _project_with_query(client: AsyncClient, headers: dict) -> str:
    pid = (await client.post("/api/projects/", json={"name": "P", "domain": "p.example.com"}, headers=headers)).json()["id"]
    await client.post(f"/api/projects/{pid}/queries", json={"text": "q", "url": "https://p.example.com"}, headers=headers)
    return pid


async def test_proklik_count_is_bounded(client: AsyncClient):
    headers = await register(client, "proklik@example.com")
    pid = await _project_with_query(client, headers)
    r = await client.post("/api/queue/proklik", json={"project_id": pid, "count": 10_000_000}, headers=headers)
    assert r.status_code == 422


# --- 9. A URL with a dangerous scheme is rejected on queries -------------------- #


async def test_query_rejects_javascript_url(client: AsyncClient):
    headers = await register(client, "url@example.com")
    pid = (await client.post("/api/projects/", json={"name": "P", "domain": "p.example.com"}, headers=headers)).json()["id"]
    r = await client.post(
        f"/api/projects/{pid}/queries",
        json={"text": "q", "url": "javascript:alert(document.cookie)"},
        headers=headers,
    )
    assert r.status_code == 422


# --- 10. Panel queue/push won't attach another project's query ------------------ #


async def test_push_rejects_foreign_query(client: AsyncClient):
    owner = await register(client, "pusha@example.com")
    pid_a = await _project_with_query(client, owner)
    pid_b = (await client.post("/api/projects/", json={"name": "B", "domain": "b.example.com"}, headers=owner)).json()["id"]
    foreign_qid = (await client.get(f"/api/projects/{pid_a}/queries", headers=owner)).json()[0]["id"]

    r = await client.post(
        "/api/queue/push",
        json={"project_id": pid_b, "tasks": [{"click_url": "https://b.example.com", "query_id": foreign_qid}]},
        headers=owner,
    )
    assert r.status_code == 422


# --- 11. CSV export neutralises spreadsheet formulas ---------------------------- #


async def test_csv_export_neutralises_formulas(client: AsyncClient):
    headers = await register(client, "csv@example.com")
    pid = (await client.post("/api/projects/", json={"name": "P", "domain": "p.example.com"}, headers=headers)).json()["id"]
    await client.post(f"/api/projects/{pid}/queries", json={"text": "=1+2+cmd|' /C calc'!A1"}, headers=headers)

    body = (await client.get(f"/api/projects/{pid}/queries/export.csv", headers=headers)).text
    # No cell is allowed to start a line with a formula trigger.
    for line in body.splitlines()[1:]:
        assert not line.lstrip('﻿').startswith(("=", "+", "-", "@"))
