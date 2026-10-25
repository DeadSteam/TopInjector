"""Smoke test: call every API operation with real ids and assert none answers with a 5xx.

Bodies are empty JSON objects, so validation errors (4xx) are fine; a 500 means the
endpoint crashes instead of rejecting bad input or doing its job.
"""

import re
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.conftest import PASSWORD, register

SAFE_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}


@pytest_asyncio.fixture
async def world(app_fixture):
    """Owner with a project, query, marker, webmarker, group, delegate, tokens, tasks and a warmup."""
    from services.project_service.domain.models import ProjectToken

    transport = ASGITransport(app=app_fixture, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner = await register(client, "smoke-owner@example.com")
        stranger = await register(client, "smoke-stranger@example.com")
        client.cookies.clear()
        stranger_id = (await client.get("/api/users/profile", headers=stranger)).json()["id"]
        owner_id = (await client.get("/api/users/profile", headers=owner)).json()["id"]

        pid = (await client.post("/api/projects/", json={"name": "Смоук проект", "domain": "smoke.example.com"}, headers=owner)).json()["id"]
        qid = (await client.post(f"/api/projects/{pid}/queries", json={"text": "smoke query"}, headers=owner)).json()["id"]
        mid = (await client.post(f"/api/projects/{pid}/markers", json={"name": "m", "url": "https://smoke.example.com"}, headers=owner)).json()["id"]
        wid = (await client.post(f"/api/projects/{pid}/webmarkers", json={"platform": "yandex"}, headers=owner)).json()["id"]
        gid = (await client.post("/api/projects/groups", json={"name": "g"}, headers=owner)).json()["id"]
        await client.post(f"/api/projects/{pid}/delegates", json={"delegate_user_id": stranger_id, "role": "view"}, headers=owner)
        await client.post("/api/queue/proklik", json={"project_id": pid, "count": 1}, headers=owner)
        tok = (await client.post("/api/users/api-tokens", json={"name": "t"}, headers=owner)).json()
        warmup = (await client.post("/api/warmups", json={"name": "w", "project_id": pid}, headers=owner)).json()

        async with app_fixture.state.session_factory() as session:  # bind an external-API token to the project
            session.add(ProjectToken(user_id=UUID(owner_id), project_id=UUID(pid), name="ext", token_string="smoke-ext"))
            await session.commit()

        third = await register(client, "smoke-third@example.com")
        client.cookies.clear()
        third_id = (await client.get("/api/users/profile", headers=third)).json()["id"]
        doomed = (await client.post("/api/projects/", json={"name": "Doomed", "domain": "doomed.example.com"}, headers=owner)).json()["id"]
        task_id = (await client.get(f"/api/queue/?project_id={pid}", headers=owner)).json()[0]["id"]
        account = (await client.post(
            "/api/external-services",
            json={"service_type": "yandex_webmaster", "display_name": "smoke"},
            headers=owner,
        )).json()
        refresh = (await client.post("/api/auth/login", json={"email": "smoke-owner@example.com", "password": PASSWORD})).json()["refresh_token"]
        client.cookies.clear()

        ids = {
            "project_id": pid, "id": pid, "query_id": qid, "marker_id": mid, "webmarker_id": wid,
            "group_id": gid, "delegate_uid": stranger_id, "token_id": tok.get("id", str(uuid4())),
            "warmup_id": warmup.get("id", str(uuid4())), "notif_id": str(uuid4()), "word": "спам",
            "user_id": owner_id, "third_id": third_id, "doomed": doomed, "task_id": task_id, "refresh": refresh,
            "account_id": account.get("id", str(uuid4())),
            "domain": "smoke.example.com",
        }
        headers = {**owner, "X-Auth-Token": "smoke-ext"}
        yield client, ids, headers


def realistic_bodies(i: dict) -> dict[tuple[str, str], object]:
    """What the frontend / a mobile client actually sends to each mutating operation."""
    multigeo = {"multigeo": [{"region": "Москва", "percent": 100}]}
    window = {"start": "07:00", "end": "22:00"}
    return {
        ("POST", "/api/auth/register"): {"email": "smoke-new@example.com", "password": "secret123", "display_name": "N"},
        ("POST", "/api/auth/login"): {"email": "smoke-owner@example.com", "password": PASSWORD},
        ("POST", "/api/auth/refresh"): {"refresh_token": i["refresh"]},
        ("PUT", "/api/users/profile"): {"display_name": "Smoke Owner"},
        ("POST", "/api/users/api-tokens"): {"name": "ci", "project_id": i["project_id"]},
        ("POST", "/api/users/settings/messenger"): {"telegram_webhook_url": "https://t.me/hook", "max_connector_id": "42"},
        ("POST", "/api/users/settings/external-services"): {"xml_river": {"user": "1", "key": "k"}},
        ("POST", "/api/users/password"): {"current_password": PASSWORD, "new_password": PASSWORD},
        ("POST", "/api/users/avatar"): {"avatar_url": "https://img.example.com/a.png"},
        ("POST", "/api/users/settings/stop-words"): {"stop_words": ["спам", "Казино"]},
        ("POST", "/api/users/settings/stop-words/add"): {"word": "кредит"},
        ("POST", "/api/projects/groups"): {"name": "g2", "icon": "folder"},
        ("PUT", "/api/projects/groups/{group_id}"): {"name": "g-renamed", "icon": "star"},
        ("POST", "/api/projects/"): {
            "name": "Smoke2", "domain": "smoke2.example.com", "region": "Москва", "strategy_type": "hourly",
            "daily_limit": 50, "group_id": i["group_id"], "geo_settings": multigeo,
            "integrations": {"integration_type": "custom"}, "scheduling_window": window,
            "query_modifications": {"typos": True},
        },
        ("PUT", "/api/projects/{project_id}"): {
            "name": "Smoke renamed", "daily_limit": 120, "region": "Санкт-Петербург", "strategy_type": "daily",
            "is_active": True, "geo_settings": multigeo, "integrations": {"integration_type": "yandex-webmaster"},
            "scheduling_window": window, "query_modifications": {"capital_first": True}, "group_id": i["group_id"],
        },
        ("POST", "/api/projects/{project_id}/queries"): {"text": "купить смоук", "search_engine": "yandex", "geo": {"city": "moscow"}},
        ("PUT", "/api/projects/{project_id}/queries/{query_id}"): {
            "text": "smoke edited", "daily_clicks": 5, "click_url": "https://yandex.ru/search/?text=x",
            "geo": {"city": "spb"}, "boost_min": 1, "boost_max": 3, "frequency": 2,
        },
        ("POST", "/api/projects/{project_id}/boost"): {
            "query_ids": [i["query_id"]], "daily_clicks": 3, "frequency": 2, "interval_seconds": 60, "start_from_now": True,
        },
        ("POST", "/api/projects/{project_id}/markers"): {"name": "m2", "url": "https://smoke.example.com/p", "css_selector": ".x", "description": "d"},
        ("PUT", "/api/projects/{project_id}/markers/{marker_id}"): {"name": "m-renamed", "url": "https://smoke.example.com/q"},
        ("POST", "/api/projects/{project_id}/webmarkers"): {"platform": "google", "verification_code": "abc"},
        ("PUT", "/api/projects/{project_id}/webmarkers/{webmarker_id}"): {"verification_code": "xyz"},
        ("POST", "/api/projects/{project_id}/delegates"): {"delegate_user_id": i["third_id"], "role": "edit"},
        ("POST", "/api/projects/{project_id}/queries/import"): "text,url,click_url\nимпорт запрос,https://smoke.example.com,\n",
        ("POST", "/api/projects/{project_id}/copy"): {"name": "Smoke copy"},
        ("PUT", "/api/projects/{project_id}/auto-stop"): {"auto_stop_at": "2030-01-01T00:00:00Z"},
        ("POST", "/api/projects/{project_id}/clear-queue"): {"statuses": ["pending"]},
        ("POST", "/api/projects/bulk-toggle"): {"project_ids": [i["project_id"]], "is_active": True},
        ("POST", "/api/projects/bulk-edit"): {
            "project_ids": [i["project_id"]], "daily_limit": 90, "region": "Москва", "geo_settings": multigeo,
            "scheduling_window": window, "query_modifications": {},
        },
        ("POST", "/api/projects/bulk-delete"): {"project_ids": [i["doomed"]]},
        ("POST", "/api/projects/bulk-delegate"): {"project_ids": [i["project_id"]], "delegate_user_id": i["third_id"], "role": "view"},
        ("POST", "/api/projects/{project_id}/queries/bulk-update"): {
            "query_ids": [i["query_id"]], "daily_clicks": 4, "geo": {"city": "msk"}, "click_url": "https://x.example.com", "text": "bulk",
        },
        ("POST", "/api/projects/{id}/balance/add"): {"amount": 100, "description": "top-up"},
        ("POST", "/api/projects/{id}/balance/set"): {"balance": 500, "description": "set"},
        ("POST", "/api/queue/push"): {"project_id": i["project_id"], "tasks": [
            {"click_url": "https://smoke.example.com/push", "query_id": i["query_id"], "source": "strategy", "geo": {}}]},
        ("POST", "/api/queue/results"): {"results": [{"task_id": i["task_id"], "status": "completed", "position": 5}]},
        ("POST", "/api/queue/proklik"): {"project_id": i["project_id"], "query_ids": [i["query_id"]], "clicks_per_query": 2},
        ("POST", "/api/external/v1/projects"): {"name": "Ext", "domain": "ext.example.com", "region": "ru", "strategy_type": "daily", "daily_limit": 10},
        ("PUT", "/api/external/v1/projects/{project_id}"): {"name": "Ext renamed", "daily_limit": 20},
        ("PATCH", "/api/external/v1/projects/{project_id}/status"): {"is_active": True},
        ("POST", "/api/external/v1/terms/upsert"): {"queries": [
            {"text": "ext term", "url": "https://x.example.com", "click_url": "https://y.example.com", "geo": {}, "daily_clicks": 2}]},
        ("POST", "/api/external/v1/queue/push"): {"tasks": [
            {"click_url": "https://smoke.example.com/ext", "source": "strategy", "geo": {}, "query_id": i["query_id"]}]},
        ("POST", "/api/external/v1/queue/results"): {"results": [{"task_id": i["task_id"], "status": "completed", "position": 3}]},
        ("PATCH", "/api/external/v1/users/{user_id}/status"): {"is_active": True},
        ("POST", "/api/external/v1/balance/add"): {"amount": 10},
        ("POST", "/api/external/v1/balance/set"): {"balance": 20},
        ("POST", "/api/external/v1/boosts"): {
            "query_text": "boost q", "boost_min": 1, "boost_max": 3, "frequency": 1, "url": "https://x.example.com", "click_url": "https://y.example.com"},
        ("POST", "/api/warmups"): {
            "name": "w2", "project_id": i["project_id"], "clicks_per_hour": 5, "total_target": 50,
            "start_time": "2026-10-21T08:00:00Z", "end_time": "2026-10-22T08:00:00Z"},
        ("PUT", "/api/warmups/{warmup_id}"): {"name": "w-renamed", "clicks_per_hour": 7},
        ("PUT", "/api/plan"): {"slug": "lite"},
        ("POST", "/api/external-services"): {
            "service_type": "xmlriver", "display_name": "XR", "config_json": {"user": "1", "key": "k"}},
        ("PUT", "/api/external-services/{account_id}"): {"display_name": "renamed", "is_active": True},
        ("POST", "/api/external-services/{account_id}/domains"): {"domain": "smoke.example.com"},
        ("PUT", "/api/whitelabel"): {"platform_name": "Smoke Panel", "accent_color": "#101828"},
    }


async def test_no_operation_crashes_with_realistic_bodies(app_fixture, world):
    client, ids, headers = world
    await _call_everything(app_fixture, client, ids, headers, realistic_bodies(ids))


async def test_no_operation_crashes(app_fixture, world):
    client, ids, headers = world
    await _call_everything(app_fixture, client, ids, headers, {})


async def _call_everything(app_fixture, client, ids, headers, bodies):
    spec = app_fixture.openapi()
    ops = sorted(
        ((m.upper(), path, op) for path, item in spec["paths"].items() for m, op in item.items() if m.upper() in SAFE_ORDER),
        # deletes last, and deleting the project itself at the very end
        key=lambda o: (SAFE_ORDER[o[0]], o[1] in ("/api/projects/{project_id}", "/api/external/v1/projects/{project_id}")),
    )

    crashes = []
    for method, path, op in ops:
        if path.endswith("/feed"):  # endless SSE stream
            continue
        url = re.sub(r"{(\w+)}", lambda m: ids[m.group(1)], path)
        query = {p["name"]: ("smoke" if p["name"] == "q" else ids["project_id"])
                 for p in op.get("parameters", []) if p["in"] == "query" and p.get("required")}
        body = bodies.get((method, path), {} if method in ("POST", "PUT", "PATCH") else None)
        if isinstance(body, str):  # raw CSV upload
            resp = await client.request(method, url, params=query, content=body.encode(), headers={**headers, "Content-Type": "text/csv"})
        else:
            resp = await client.request(method, url, params=query, json=body, headers=headers)
        if resp.status_code >= 500 and resp.status_code != 501:  # 501 = deliberately not implemented
            crashes.append(f"{method} {path} -> {resp.status_code} {resp.text[:120]}")

    assert crashes == [], "\n".join(crashes)
