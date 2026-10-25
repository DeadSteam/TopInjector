"""External API (/api/external/v1, X-Auth-Token) and project balance."""

import pytest_asyncio
from httpx import AsyncClient, codes

from tests.conftest import register


@pytest_asyncio.fixture
async def setup(client: AsyncClient):
    """Owner with two projects; an API token bound to the first one."""
    owner = await register(client, "ext-owner@example.com")
    client.cookies.clear()
    p1 = (await client.post("/api/projects/", json={"name": "P1", "domain": "p1.example.com"}, headers=owner)).json()["id"]
    p2 = (await client.post("/api/projects/", json={"name": "P2", "domain": "p2.example.com"}, headers=owner)).json()["id"]
    q1 = (await client.post(f"/api/projects/{p1}/queries", json={"text": "alpha"}, headers=owner)).json()["id"]
    q2 = (await client.post(f"/api/projects/{p2}/queries", json={"text": "beta"}, headers=owner)).json()["id"]
    tok = await client.post("/api/users/api-tokens", json={"name": "mobile", "project_id": p1}, headers=owner)
    assert tok.status_code == codes.OK, tok.text
    ext = {"X-Auth-Token": tok.json()["token"]}
    return {"owner": owner, "ext": ext, "p1": p1, "p2": p2, "q1": q1, "q2": q2}


async def _push(client, s, *urls):
    resp = await client.post("/api/external/v1/queue/push", json={"tasks": [{"click_url": u} for u in urls]}, headers=s["ext"])
    assert resp.status_code == codes.OK, resp.text


# ── Tokens ──────────────────────────────────────────────────────────────────── #


async def test_api_token_is_bound_to_project(client: AsyncClient, setup):
    status = (await client.get("/api/external/v1/external/status", headers=setup["ext"])).json()
    assert status["project"]["id"] == setup["p1"]


async def test_api_token_requires_accessible_project(client: AsyncClient, setup):
    stranger = await register(client, "ext-stranger@example.com")
    for body in ({"name": "no project"}, {"name": "foreign", "project_id": setup["p1"]}):
        resp = await client.post("/api/users/api-tokens", json=body, headers=stranger)
        assert resp.status_code in (codes.UNPROCESSABLE_ENTITY, codes.NOT_FOUND), (body, resp.status_code)


async def test_api_token_listing_shows_project(client: AsyncClient, setup):
    tokens = (await client.get("/api/users/api-tokens", headers=setup["owner"])).json()
    assert [t["project_id"] for t in tokens] == [setup["p1"]]


# ── Project scoping ─────────────────────────────────────────────────────────── #


async def test_token_cannot_touch_other_project(client: AsyncClient, setup):
    ext, p2 = setup["ext"], setup["p2"]
    assert (await client.put(f"/api/external/v1/projects/{p2}", json={"name": "x"}, headers=ext)).status_code == codes.NOT_FOUND
    assert (await client.patch(f"/api/external/v1/projects/{p2}/status", json={"is_active": False}, headers=ext)).status_code == codes.NOT_FOUND
    assert (await client.delete(f"/api/external/v1/projects/{p2}", headers=ext)).status_code == codes.NOT_FOUND
    assert (await client.get(f"/api/external/v1/terms?project_id={p2}", headers=ext)).status_code == codes.NOT_FOUND
    assert (await client.get(f"/api/external/v1/boosts?project_id={p2}", headers=ext)).status_code == codes.NOT_FOUND
    assert (await client.post(f"/api/external/v1/queue/clear?project_id={p2}", headers=ext)).status_code == codes.NOT_FOUND
    # P2 untouched
    names = {p["name"] for p in (await client.get("/api/projects/", headers=setup["owner"])).json()["items"]}
    assert names == {"P1", "P2"}


async def test_update_own_project(client: AsyncClient, setup):
    resp = await client.put(
        f"/api/external/v1/projects/{setup['p1']}", json={"name": "P1 renamed", "daily_limit": 42}, headers=setup["ext"]
    )
    assert resp.status_code == codes.OK, resp.text
    project = (await client.get(f"/api/projects/{setup['p1']}", headers=setup["owner"])).json()
    assert (project["name"], project["daily_limit"]) == ("P1 renamed", 42)


async def test_terms_listing_defaults_to_token_project(client: AsyncClient, setup):
    terms = (await client.get("/api/external/v1/terms", headers=setup["ext"])).json()
    assert [t["text"] for t in terms["terms"]] == ["alpha"]


async def test_clear_removes_only_pending_of_token_project(client: AsyncClient, setup):
    await _push(client, setup, "https://p1.example.com/a", "https://p1.example.com/b")
    resp = await client.post("/api/external/v1/queue/clear", headers=setup["ext"])
    assert resp.json() == {"deleted": 2}


# ── Terms upsert ────────────────────────────────────────────────────────────── #


async def test_terms_upsert_keeps_existing_query_ids(client: AsyncClient, setup):
    resp = await client.post(
        "/api/external/v1/terms/upsert",
        json={"queries": [{"text": "alpha", "daily_clicks": 7}, {"text": "gamma", "url": "https://p1.example.com/g"}]},
        headers=setup["ext"],
    )
    assert resp.json() == {"created": 1, "updated": 1}

    terms = {t["text"]: t for t in (await client.get("/api/external/v1/terms", headers=setup["ext"])).json()["terms"]}
    assert set(terms) == {"alpha", "gamma"}
    assert terms["alpha"]["id"] == setup["q1"]
    assert terms["alpha"]["daily_clicks"] == 7


# ── Queue ───────────────────────────────────────────────────────────────────── #


async def test_push_rejects_query_from_other_project(client: AsyncClient, setup):
    resp = await client.post(
        "/api/external/v1/queue/push",
        json={"tasks": [{"click_url": "https://p1.example.com/x", "query_id": setup["q2"]}]},
        headers=setup["ext"],
    )
    assert resp.status_code == codes.UNPROCESSABLE_ENTITY


async def test_claim_hands_out_each_task_once(client: AsyncClient, setup):
    await _push(client, setup, "https://p1.example.com/1", "https://p1.example.com/2", "https://p1.example.com/3")

    first = (await client.post("/api/external/v1/queue/claim", json={"limit": 2}, headers=setup["ext"])).json()["tasks"]
    second = (await client.post("/api/external/v1/queue/claim", json={"limit": 2}, headers=setup["ext"])).json()["tasks"]
    assert len(first) == 2 and len(second) == 1
    assert not {t["id"] for t in first} & {t["id"] for t in second}

    pending = (await client.get("/api/external/v1/queue?status=pending", headers=setup["ext"])).json()["total"]
    in_progress = (await client.get("/api/external/v1/queue?status=in_progress", headers=setup["ext"])).json()["total"]
    assert (pending, in_progress) == (0, 3)


async def test_results_reject_unknown_status(client: AsyncClient, setup):
    await _push(client, setup, "https://p1.example.com/r")
    task = (await client.post("/api/external/v1/queue/claim", json={"limit": 1}, headers=setup["ext"])).json()["tasks"][0]
    bad = await client.post(
        "/api/external/v1/queue/results", json={"results": [{"task_id": task["id"], "status": "done!"}]}, headers=setup["ext"]
    )
    assert bad.status_code == codes.UNPROCESSABLE_ENTITY
    internal = await client.post(
        "/api/queue/results", json={"results": [{"task_id": task["id"], "status": "done!"}]}, headers=setup["owner"]
    )
    assert internal.status_code == codes.UNPROCESSABLE_ENTITY


# ── Balance ─────────────────────────────────────────────────────────────────── #


async def test_external_balance_add_and_set_change_balance(client: AsyncClient, setup):
    await client.post("/api/external/v1/balance/add", json={"amount": 150}, headers=setup["ext"])
    balance = (await client.get(f"/api/projects/{setup['p1']}/balance", headers=setup["owner"])).json()
    assert balance["balance_rub"] == 150

    await client.post("/api/external/v1/balance/set", json={"balance": 40}, headers=setup["ext"])
    balance = (await client.get(f"/api/projects/{setup['p1']}/balance", headers=setup["owner"])).json()
    assert balance["balance_rub"] == 40


async def test_panel_balance_endpoints_work_without_query_params(client: AsyncClient, setup):
    p1, owner = setup["p1"], setup["owner"]
    assert (await client.post(f"/api/projects/{p1}/balance/add", json={"amount": 10}, headers=owner)).status_code == codes.OK
    assert (await client.get(f"/api/projects/{p1}/balance", headers=owner)).status_code == codes.OK
    history = await client.get(f"/api/projects/{p1}/balance/history?page=1&page_size=20", headers=owner)
    assert history.status_code == codes.OK and history.json()["total"] == 1


async def test_user_endpoints_report_not_implemented(client: AsyncClient, setup):
    resp = await client.post("/api/external/v1/users", json={"email": "x@example.com"}, headers=setup["ext"])
    assert resp.status_code == codes.NOT_IMPLEMENTED
