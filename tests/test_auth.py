"""Auth flow and external API token validation."""

from uuid import UUID, uuid4

import pytest_asyncio
from httpx import AsyncClient, codes
from sqlalchemy import select, text


async def _user(session, email="owner@example.com"):
    from services.auth_service.domain.models import User

    user = User(email=email, password_hash="x", display_name="Owner")
    session.add(user)
    await session.flush()
    return user


# ---- Auth: register + login ----------------------------------------------- #


async def test_register_returns_tokens(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "secret123", "display_name": "New"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_register_duplicate_email(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "secret123", "display_name": "Dup"},
    )
    resp = await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "other-secret", "display_name": "Other"},
    )
    assert resp.status_code == codes.CONFLICT


async def test_login_invalid_credentials(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert resp.status_code == codes.UNAUTHORIZED


# ---- Auth /me with valid token --------------------------------------------- #


async def test_me_returns_user_id(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "me@example.com", "password": "secret123", "display_name": "Me"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "me@example.com", "password": "secret123"},
    )
    assert login_resp.status_code == codes.OK, login_resp.text
    token = login_resp.json()["access_token"]

    me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == codes.OK
    data = me_resp.json()
    assert "user_id" in data


# ---- User profile with auth dependency ------------------------------------- #


async def test_get_profile_requires_auth(client: AsyncClient):
    resp = await client.get("/api/users/profile")
    assert resp.status_code == codes.UNAUTHORIZED


async def test_get_profile_with_token(client: AsyncClient, auth_headers):
    """GET /profile with valid JWT returns user data."""
    resp = await client.get("/api/users/profile", headers=auth_headers)
    assert resp.status_code == codes.OK, f"Profile failed: {resp.text}"
    data = resp.json()
    assert data["email"] == "owner@example.com"


# ---- External API: token validation ---------------------------------------- #


async def test_external_projects_requires_token(client: AsyncClient):
    """GET /projects without X-Auth-Token returns 401."""
    resp = await client.get("/api/external/v1/projects")
    assert resp.status_code == codes.UNAUTHORIZED


async def test_external_projects_invalid_token(client: AsyncClient):
    """GET /projects with invalid token returns 401."""
    resp = await client.get(
        "/api/external/v1/projects",
        headers={"X-Auth-Token": "invalid-token"},
    )
    assert resp.status_code == codes.UNAUTHORIZED


async def test_queue_push_with_valid_token(client: AsyncClient):
    """Push task with valid X-Auth-Token returns 401 when token has no project."""
    # Token "tl_queue_test_01" doesn't exist in DB → should return 401
    resp = await client.post(
        "/api/external/v1/queue/push",
        headers={"X-Auth-Token": "tl_queue_test_01"},
        json={"tasks": [{"click_url": "https://example.com/page"}]},
    )
    assert resp.status_code == codes.UNAUTHORIZED


async def test_external_balance_add_with_token(client: AsyncClient):
    """Add balance with valid token returns 401 when token has no project."""
    resp = await client.post(
        "/api/external/v1/balance/add",
        headers={"X-Auth-Token": "tl_balance_test_01"},
        json={"amount": 500},
    )
    assert resp.status_code == codes.UNAUTHORIZED
