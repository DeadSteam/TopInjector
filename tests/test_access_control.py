"""Panel API access control: auth required, users only see and change their own (or delegated) projects."""

import pytest_asyncio
from httpx import AsyncClient, codes

from tests.conftest import register


@pytest_asyncio.fixture
async def owner(client: AsyncClient) -> dict[str, str]:
    return await register(client, "owner@example.com")


@pytest_asyncio.fixture
async def stranger(client: AsyncClient) -> dict[str, str]:
    return await register(client, "stranger@example.com")


async def _user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    return (await client.get("/api/users/profile", headers=headers)).json()["id"]


@pytest_asyncio.fixture
async def project_id(client: AsyncClient, owner) -> str:
    resp = await client.post("/api/projects/", json={"name": "Owned", "domain": "owned.example.com"}, headers=owner)
    assert resp.status_code == codes.OK, resp.text
    pid = resp.json()["id"]
    await client.post(f"/api/projects/{pid}/queries", json={"text": "owned query"}, headers=owner)
    client.cookies.clear()  # register/login set an auth cookie; tests authenticate explicitly
    return pid


async def _delegate(client: AsyncClient, owner, project_id: str, delegate_headers, role: str) -> None:
    delegate_id = await _user_id(client, delegate_headers)
    resp = await client.post(
        f"/api/projects/{project_id}/delegates", json={"delegate_user_id": delegate_id, "role": role}, headers=owner
    )
    assert resp.status_code == codes.OK, resp.text


# ── Authentication ──────────────────────────────────────────────────────────── #


async def test_project_endpoints_require_auth(client: AsyncClient, project_id):
    for method, path in [
        ("GET", "/api/projects/"),
        ("POST", "/api/projects/"),
        ("GET", f"/api/projects/{project_id}"),
        ("DELETE", f"/api/projects/{project_id}"),
        ("GET", "/api/projects/groups"),
        ("GET", "/api/queue/"),
        ("GET", "/api/queue/stats"),
        ("POST", "/api/queue/proklik"),
        ("GET", "/api/analytics/summary"),
    ]:
        resp = await client.request(method, path, json={} if method == "POST" else None)
        assert resp.status_code == codes.UNAUTHORIZED, f"{method} {path} -> {resp.status_code}"


async def test_cookie_auth_allowed_for_reads_only(client: AsyncClient, owner, project_id):
    token = owner["Authorization"].removeprefix("Bearer ")
    client.cookies.set("token", token)
    try:
        assert (await client.get("/api/projects/")).status_code == codes.OK
        resp = await client.post("/api/projects/", json={"name": "Via cookie", "domain": "cookie.example.com"})
        assert resp.status_code == codes.UNAUTHORIZED
    finally:
        client.cookies.clear()


# ── Ownership ───────────────────────────────────────────────────────────────── #


async def test_list_shows_only_accessible_projects(client: AsyncClient, owner, stranger, project_id):
    mine = await client.get("/api/projects/", headers=owner)
    theirs = await client.get("/api/projects/", headers=stranger)
    assert [p["id"] for p in mine.json()["items"]] == [project_id]
    assert theirs.json()["items"] == []


async def test_stranger_cannot_read_or_delete_project(client: AsyncClient, owner, stranger, project_id):
    assert (await client.get(f"/api/projects/{project_id}", headers=stranger)).status_code == codes.NOT_FOUND
    assert (await client.delete(f"/api/projects/{project_id}", headers=stranger)).status_code == codes.NOT_FOUND
    assert (await client.get(f"/api/projects/{project_id}", headers=owner)).status_code == codes.OK


async def test_stranger_cannot_touch_queue_of_project(client: AsyncClient, owner, stranger, project_id):
    proklik = await client.post("/api/queue/proklik", json={"project_id": project_id, "count": 1}, headers=stranger)
    assert proklik.status_code == codes.NOT_FOUND
    listing = await client.get(f"/api/queue/?project_id={project_id}", headers=stranger)
    assert listing.status_code == codes.NOT_FOUND

    await client.post("/api/queue/proklik", json={"project_id": project_id, "count": 2}, headers=owner)
    assert (await client.get("/api/queue/stats", headers=owner)).json()["pending"] == 2
    assert (await client.get("/api/queue/stats", headers=stranger)).json()["pending"] == 0
    assert (await client.get("/api/queue/", headers=stranger)).json() == []


async def test_bulk_delete_ignores_foreign_projects(client: AsyncClient, owner, stranger, project_id):
    resp = await client.post("/api/projects/bulk-delete", json={"project_ids": [project_id]}, headers=stranger)
    assert resp.json()["deleted"] == 0
    assert (await client.get(f"/api/projects/{project_id}", headers=owner)).status_code == codes.OK


async def test_bulk_toggle_applies_to_own_projects(client: AsyncClient, owner, project_id):
    resp = await client.post(
        "/api/projects/bulk-toggle", json={"project_ids": [project_id], "is_active": False}, headers=owner
    )
    assert resp.json()["updated"] == 1


async def test_global_search_returns_only_own_projects(client: AsyncClient, owner, stranger, project_id):
    mine = await client.get("/api/projects/global-search?q=Owned", headers=owner)
    assert mine.status_code == codes.OK, mine.text
    assert [p["id"] for p in mine.json()["projects"]] == [project_id]
    theirs = await client.get("/api/projects/global-search?q=Owned", headers=stranger)
    assert theirs.json()["projects"] == []


async def test_groups_are_per_user(client: AsyncClient, owner, stranger):
    created = await client.post("/api/projects/groups", json={"name": "Мои"}, headers=owner)
    assert created.status_code == codes.OK, created.text
    group_id = created.json()["id"]

    assert [g["id"] for g in (await client.get("/api/projects/groups", headers=owner)).json()] == [group_id]
    assert (await client.get("/api/projects/groups", headers=stranger)).json() == []
    resp = await client.put(f"/api/projects/groups/{group_id}", json={"name": "чужая"}, headers=stranger)
    assert resp.status_code == codes.NOT_FOUND


async def test_admin_stats_forbidden_for_regular_user(client: AsyncClient, owner):
    assert (await client.get("/api/projects/admin/stats", headers=owner)).status_code == codes.FORBIDDEN
    assert (await client.get("/api/users/profile", headers=owner)).json()["is_admin"] is False


async def test_admin_emails_grant_admin_stats(client: AsyncClient, owner, monkeypatch):
    from shared.config import settings

    monkeypatch.setattr(settings, "admin_emails", "Owner@Example.com")
    assert (await client.get("/api/users/profile", headers=owner)).json()["is_admin"] is True
    assert (await client.get("/api/projects/admin/stats", headers=owner)).status_code == codes.OK


async def test_analytics_counts_only_own_clicks(client: AsyncClient, owner, stranger, project_id):
    await client.post("/api/queue/proklik", json={"project_id": project_id, "count": 1}, headers=owner)
    task_id = (await client.get(f"/api/queue/?project_id={project_id}", headers=owner)).json()[0]["id"]
    await client.post(
        "/api/queue/results", json={"results": [{"task_id": task_id, "status": "completed", "position": 4}]},
        headers=owner,
    )

    assert (await client.get("/api/analytics/summary", headers=owner)).json()["completed_clicks"] == 1
    assert (await client.get("/api/analytics/summary", headers=stranger)).json()["completed_clicks"] == 0
    tracking = await client.get(f"/api/analytics/tracking/positions?project_id={project_id}", headers=stranger)
    assert tracking.json()["tracking"] == []


async def test_stranger_cannot_submit_results_for_foreign_task(client: AsyncClient, owner, stranger, project_id):
    await client.post("/api/queue/proklik", json={"project_id": project_id, "count": 1}, headers=owner)
    task_id = (await client.get(f"/api/queue/?project_id={project_id}", headers=owner)).json()[0]["id"]
    resp = await client.post(
        "/api/queue/results", json={"results": [{"task_id": task_id, "status": "completed"}]}, headers=stranger
    )
    assert resp.json()["updated"] == 0


async def test_nested_resources_of_foreign_project_are_unreachable(client: AsyncClient, owner, stranger, project_id):
    """Using my own project id in the path must not reach another project's queries/markers/webmarkers."""
    mine = (await client.post("/api/projects/", json={"name": "Mine", "domain": "mine.example.com"}, headers=stranger)).json()["id"]
    query_id = (await client.get(f"/api/projects/{project_id}/queries", headers=owner)).json()[0]["id"]
    marker_id = (await client.post(f"/api/projects/{project_id}/markers", json={"name": "m", "url": "https://x"}, headers=owner)).json()["id"]
    web_id = (await client.post(f"/api/projects/{project_id}/webmarkers", json={"platform": "yandex"}, headers=owner)).json()["id"]

    attempts = [
        ("PUT", f"/api/projects/{mine}/queries/{query_id}", {"click_url": "https://evil"}),
        ("DELETE", f"/api/projects/{mine}/queries/{query_id}", None),
        ("PUT", f"/api/projects/{mine}/markers/{marker_id}", {"name": "evil"}),
        ("DELETE", f"/api/projects/{mine}/markers/{marker_id}", None),
        ("PUT", f"/api/projects/{mine}/webmarkers/{web_id}", {"verification_code": "evil"}),
        ("POST", f"/api/projects/{mine}/webmarkers/{web_id}/verify", None),
        ("DELETE", f"/api/projects/{mine}/webmarkers/{web_id}", None),
        ("POST", f"/api/projects/{mine}/boost", {"query_ids": [query_id], "daily_clicks": 99}),
        ("POST", f"/api/projects/{mine}/queries/bulk-update", {"query_ids": [query_id], "click_url": "https://evil"}),
    ]
    for method, path, body in attempts:
        await client.request(method, path, json=body, headers=stranger)

    query = [q for q in (await client.get(f"/api/projects/{project_id}/queries", headers=owner)).json() if q["id"] == query_id]
    assert query and query[0]["click_url"] != "https://evil" and query[0]["daily_clicks"] != 99
    markers = (await client.get(f"/api/projects/{project_id}/markers", headers=owner)).json()
    assert [m["name"] for m in (markers.get("markers", markers) if isinstance(markers, dict) else markers)] == ["m"]
    webs = (await client.get(f"/api/projects/{project_id}/webmarkers", headers=owner)).json()
    webs = webs.get("webmarkers", webs) if isinstance(webs, dict) else webs
    assert len(webs) == 1 and webs[0].get("verification_code") != "evil" and not webs[0].get("is_verified")


# ── Delegation ──────────────────────────────────────────────────────────────── #


async def test_delegate_can_be_added_by_email(client: AsyncClient, owner, stranger, project_id):
    resp = await client.post(
        f"/api/projects/{project_id}/delegates", json={"email": "Stranger@Example.com", "role": "view"}, headers=owner
    )
    assert resp.status_code == codes.OK, resp.text
    delegates = (await client.get(f"/api/projects/{project_id}/delegates", headers=owner)).json()
    assert [(d["email"], d["role"]) for d in delegates] == [("stranger@example.com", "view")]
    assert (await client.get(f"/api/projects/{project_id}", headers=stranger)).status_code == codes.OK

    unknown = await client.post(f"/api/projects/{project_id}/delegates", json={"email": "nobody@example.com"}, headers=owner)
    assert unknown.status_code == codes.NOT_FOUND


async def test_view_delegate_can_read_but_not_write(client: AsyncClient, owner, stranger, project_id):
    await _delegate(client, owner, project_id, stranger, "view")
    assert (await client.get(f"/api/projects/{project_id}", headers=stranger)).status_code == codes.OK
    assert project_id in [p["id"] for p in (await client.get("/api/projects/", headers=stranger)).json()["items"]]
    resp = await client.put(f"/api/projects/{project_id}", json={"name": "hijack"}, headers=stranger)
    assert resp.status_code == codes.FORBIDDEN


async def test_edit_delegate_can_write_but_not_delete(client: AsyncClient, owner, stranger, project_id):
    await _delegate(client, owner, project_id, stranger, "edit")
    resp = await client.put(f"/api/projects/{project_id}", json={"name": "Renamed"}, headers=stranger)
    assert resp.status_code == codes.OK, resp.text
    assert (await client.delete(f"/api/projects/{project_id}", headers=stranger)).status_code == codes.FORBIDDEN
