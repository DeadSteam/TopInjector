"""Phase-1 platform features: subscription plans and external-service accounts."""

from httpx import AsyncClient

from tests.conftest import register


# --- Plans --------------------------------------------------------------------- #


async def test_plans_list_is_public_and_seeded(client: AsyncClient):
    # The public catalogue doesn't require auth. Seeds come from migration 0015, but the
    # test DB is built from models, so the endpoint seeds on first read if the table is empty.
    r = await client.get("/api/plans")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()["plans"]}
    assert {"start", "lite", "pro"} <= slugs


async def test_plan_status_defaults_to_start(client: AsyncClient):
    headers = await register(client, "planuser@example.com")
    r = await client.get("/api/plan/status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["plan"]["slug"] == "start"
    assert body["limits"]["max_projects"] >= 1
    assert body["usage"]["projects"] == 0


async def test_plan_status_requires_auth(client: AsyncClient):
    assert (await client.get("/api/plan/status")).status_code == 401


async def test_switch_plan(client: AsyncClient):
    headers = await register(client, "switch@example.com")
    r = await client.put("/api/plan", json={"slug": "pro"}, headers=headers)
    assert r.status_code == 200
    assert (await client.get("/api/plan/status", headers=headers)).json()["plan"]["slug"] == "pro"


async def test_switch_plan_rejects_unknown_slug(client: AsyncClient):
    headers = await register(client, "badplan@example.com")
    r = await client.put("/api/plan", json={"slug": "nope"}, headers=headers)
    assert r.status_code == 404


# --- External service accounts ------------------------------------------------- #


async def test_external_service_crud_is_user_scoped(client: AsyncClient):
    owner = await register(client, "svc-owner@example.com")
    acc = await client.post(
        "/api/external-services",
        json={"service_type": "xmlriver", "display_name": "My XMLRiver", "config_json": {"user": "1", "key": "k"}},
        headers=owner,
    )
    assert acc.status_code == 200, acc.text
    acc_id = acc.json()["id"]

    # Owner sees it; a stranger does not.
    assert any(a["id"] == acc_id for a in (await client.get("/api/external-services", headers=owner)).json()["accounts"])
    stranger = await register(client, "svc-stranger@example.com")
    assert (await client.get("/api/external-services", headers=stranger)).json()["accounts"] == []
    assert (await client.put(f"/api/external-services/{acc_id}", json={"display_name": "x"}, headers=stranger)).status_code == 404


async def test_external_service_rejects_unknown_type(client: AsyncClient):
    headers = await register(client, "svc-type@example.com")
    r = await client.post(
        "/api/external-services",
        json={"service_type": "evil_bot_farm", "display_name": "x"},
        headers=headers,
    )
    assert r.status_code == 422


async def test_webmaster_domains(client: AsyncClient):
    headers = await register(client, "wm@example.com")
    acc_id = (await client.post(
        "/api/external-services",
        json={"service_type": "yandex_webmaster", "display_name": "WM"},
        headers=headers,
    )).json()["id"]

    add = await client.post(
        f"/api/external-services/{acc_id}/domains", json={"domain": "example.com"}, headers=headers
    )
    assert add.status_code == 200, add.text
    domains = (await client.get(f"/api/external-services/{acc_id}/domains", headers=headers)).json()["domains"]
    assert [d["domain"] for d in domains] == ["example.com"]
