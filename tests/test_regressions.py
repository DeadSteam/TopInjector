"""Regressions found by the all-routes smoke test and the browser walk-through."""

from httpx import AsyncClient, codes


async def _project(client: AsyncClient, headers, domain: str = "copy.example.com") -> str:
    resp = await client.post("/api/projects/", json={"name": "Original", "domain": domain}, headers=headers)
    assert resp.status_code == codes.OK, resp.text
    return resp.json()["id"]


async def test_copy_project_keeps_domain(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers)
    await client.post(f"/api/projects/{pid}/queries", json={"text": "q1"}, headers=auth_headers)

    resp = await client.post(f"/api/projects/{pid}/copy", json={"name": "Copy"}, headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text

    items = (await client.get("/api/projects/", headers=auth_headers)).json()["items"]
    assert sorted((p["name"], p["domain"], p["query_count"]) for p in items) == [
        ("Copy", "copy.example.com", 1),
        ("Original", "copy.example.com", 1),
    ]


async def test_verify_email_marks_user_verified(client: AsyncClient, auth_headers):
    # Verification uses the single-purpose token from the e-mail link, not a login session.
    from services.auth_service.routes.auth import _create_verify_token

    uid = (await client.get("/api/users/profile", headers=auth_headers)).json()["id"]
    verify_headers = {"Authorization": f"Bearer {_create_verify_token(uid)}"}

    resp = await client.post("/api/auth/verify-email", headers=verify_headers)
    assert resp.json() == {"message": "Email verified successfully"}
    again = await client.post("/api/auth/verify-email", headers=verify_headers)
    assert again.json() == {"message": "Email already verified"}


async def test_refresh_issues_working_tokens(client: AsyncClient):
    await client.post("/api/auth/register", json={"email": "ref@example.com", "password": "secret123"})
    login = (await client.post("/api/auth/login", json={"email": "ref@example.com", "password": "secret123"})).json()
    client.cookies.clear()

    resp = await client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == codes.OK, resp.text
    profile = await client.get("/api/users/profile", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    assert profile.json()["email"] == "ref@example.com"


async def test_inactive_user_cannot_log_in(client: AsyncClient, app_fixture):
    from sqlalchemy import update

    from services.auth_service.domain.models import User

    await client.post("/api/auth/register", json={"email": "off@example.com", "password": "secret123"})
    async with app_fixture.state.session_factory() as session:
        await session.execute(update(User).where(User.email == "off@example.com").values(is_active=False))
        await session.commit()
    resp = await client.post("/api/auth/login", json={"email": "off@example.com", "password": "secret123"})
    assert resp.status_code == codes.UNAUTHORIZED


async def test_summary_report_lists_only_queries_with_positions(client: AsyncClient, auth_headers):
    other = {"Authorization": (await client.post(
        "/api/auth/register", json={"email": "rep-other@example.com", "password": "secret123"})).json()["access_token"]}
    other = {"Authorization": f"Bearer {other['Authorization']}"}
    foreign = await _project(client, other, "foreign.example.com")
    await client.post(f"/api/projects/{foreign}/queries", json={"text": "чужой запрос"}, headers=other)

    pid = await _project(client, auth_headers, "report.example.com")
    await client.post(f"/api/projects/{pid}/queries", json={"text": "с позицией"}, headers=auth_headers)
    await client.post(f"/api/projects/{pid}/queries", json={"text": "без позиции"}, headers=auth_headers)
    q_with = [q for q in (await client.get(f"/api/projects/{pid}/queries", headers=auth_headers)).json() if q["text"] == "с позицией"][0]
    await client.post("/api/queue/proklik", json={"project_id": pid, "query_ids": [q_with["id"]]}, headers=auth_headers)
    task = (await client.get(f"/api/queue/?project_id={pid}", headers=auth_headers)).json()[0]
    await client.post("/api/queue/results", json={"results": [{"task_id": task["id"], "status": "completed", "position": 4}]}, headers=auth_headers)

    csv_text = (await client.get(f"/api/projects/{pid}/reports/summary.csv", headers=auth_headers)).text
    rows_after_header = csv_text.split("query_text,best_position")[1].strip().splitlines()
    assert rows_after_header == ["с позицией,4"]


async def test_second_token_for_same_project_conflicts(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "tok.example.com")
    first = await client.post("/api/users/api-tokens", json={"name": "a", "project_id": pid}, headers=auth_headers)
    assert first.status_code == codes.OK
    second = await client.post("/api/users/api-tokens", json={"name": "b", "project_id": pid}, headers=auth_headers)
    assert second.status_code == codes.CONFLICT


async def test_project_clear_queue_deletes_selected_statuses(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "clear.example.com")
    await client.post(f"/api/projects/{pid}/queries", json={"text": "c"}, headers=auth_headers)
    await client.post("/api/queue/proklik", json={"project_id": pid, "count": 3}, headers=auth_headers)
    task = (await client.get(f"/api/queue/?project_id={pid}", headers=auth_headers)).json()[0]
    await client.post("/api/queue/results", json={"results": [{"task_id": task["id"], "status": "completed"}]}, headers=auth_headers)

    resp = await client.post(f"/api/projects/{pid}/clear-queue", json={"statuses": ["pending", "in_progress"]}, headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text
    assert resp.json()["remaining"] == 1
    stats = (await client.get(f"/api/queue/stats?project_id={pid}", headers=auth_headers)).json()
    assert (stats["pending"], stats["completed"]) == (0, 1)


async def test_projects_in_a_group_list_and_open(client: AsyncClient, auth_headers):
    gid = (await client.post("/api/projects/groups", json={"name": "Москва"}, headers=auth_headers)).json()["id"]
    resp = await client.post("/api/projects/", json={"name": "В группе", "domain": "grp.example.com", "group_id": gid}, headers=auth_headers)
    pid = resp.json()["id"]

    listing = await client.get("/api/projects/", headers=auth_headers)
    assert listing.status_code == codes.OK, listing.text
    assert listing.json()["items"][0]["group_name"] == "Москва"
    project = await client.get(f"/api/projects/{pid}", headers=auth_headers)
    assert project.status_code == codes.OK, project.text
    assert project.json()["group_name"] == "Москва"


async def test_project_list_filters_by_integration_and_lists_all_regions(client: AsyncClient, auth_headers):
    specs = [("Y", "yandex-webmaster", "Москва"), ("G", "google-search-console", "Казань"), ("D", None, "Санкт-Петербург")]
    for name, kind, region in specs:
        body = {"name": name, "domain": f"{name.lower()}.example.com", "region": region}
        if kind:
            body["integrations"] = {"integration_type": kind}
        await client.post("/api/projects/", json=body, headers=auth_headers)

    def names(resp):
        return sorted(p["name"] for p in resp.json()["items"])

    assert names(await client.get("/api/projects/?integration_type=yandex-webmaster", headers=auth_headers)) == ["Y"]
    assert names(await client.get("/api/projects/?integration_type=default", headers=auth_headers)) == ["D"]
    page1 = await client.get("/api/projects/?page=1&page_size=1", headers=auth_headers)
    assert page1.json()["regions"] == ["Казань", "Москва", "Санкт-Петербург"]  # all regions, not just this page


async def test_analytics_summary_has_total_and_success_rate(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "rate.example.com")
    await client.post(f"/api/projects/{pid}/queries", json={"text": "r"}, headers=auth_headers)
    await client.post("/api/queue/proklik", json={"project_id": pid, "count": 4}, headers=auth_headers)
    tasks = (await client.get(f"/api/queue/?project_id={pid}", headers=auth_headers)).json()
    outcomes = ["completed", "completed", "completed", "not_found"]
    await client.post("/api/queue/results", json={"results": [
        {"task_id": t["id"], "status": s, "position": 3} for t, s in zip(tasks, outcomes)]}, headers=auth_headers)

    summary = (await client.get(f"/api/analytics/summary?project_id={pid}", headers=auth_headers)).json()
    assert summary["total_clicks"] == 3
    assert summary["completed_rate"] == 0.75   # 3 of 4 finished tasks found the site


async def test_bulk_query_update_works_with_ui_payload(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "bulkq.example.com")
    ids = [(await client.post(f"/api/projects/{pid}/queries", json={"text": t}, headers=auth_headers)).json()["id"] for t in ("a", "b")]
    resp = await client.post(f"/api/projects/{pid}/queries/bulk-update",
                             json={"query_ids": ids, "daily_clicks": 4, "geo": {"city": "msk"}}, headers=auth_headers)
    assert resp.json() == {"updated": 2}
    queries = (await client.get(f"/api/projects/{pid}/queries", headers=auth_headers)).json()
    assert {(q["daily_clicks"], q["geo"]["city"]) for q in queries} == {(4, "msk")}


async def test_integrations_list_has_no_duplicates(client: AsyncClient, auth_headers):
    for i, kind in enumerate(("google-search-console", "my-own-server")):
        await client.post("/api/projects/", json={"name": f"I{i}", "domain": f"i{i}.example.com",
                                                   "integrations": {"integration_type": kind}}, headers=auth_headers)
    keys = [i["key"] for i in (await client.get("/api/projects/integrations", headers=auth_headers)).json()["integrations"]]
    assert len(keys) == len(set(keys)), keys
    assert "my-own-server" in keys


async def test_project_settings_are_saved(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "settings.example.com")
    gid = (await client.post("/api/projects/groups", json={"name": "G"}, headers=auth_headers)).json()["id"]
    changes = {
        "name": "Новое имя", "daily_limit": 77, "strategy_type": "hourly", "region": "Казань", "group_id": gid,
        "scheduling_window": {"start": "09:00", "end": "18:00"}, "integrations": {"integration_type": "custom"},
        "geo_settings": {"multigeo": [{"region": "Москва", "percent": 100}]}, "query_modifications": {"typos": True},
    }
    resp = await client.put(f"/api/projects/{pid}", json=changes, headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text

    project = (await client.get(f"/api/projects/{pid}", headers=auth_headers)).json()
    for key, value in changes.items():
        assert project[key] == value, key


async def test_project_update_is_audited_with_changed_fields(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "audit.example.com")
    await client.put(f"/api/projects/{pid}", json={"daily_limit": 42, "scheduling_window": {"start": "09:00", "end": "18:00"}}, headers=auth_headers)
    entries = (await client.get(f"/api/projects/{pid}/audit-log", headers=auth_headers)).json()["entries"]
    update = next(e for e in entries if e["action"] == "update_project")
    assert update["old_values"] == {"daily_limit": 500, "scheduling_window": None}
    assert update["new_values"] == {"daily_limit": 42, "scheduling_window": {"start": "09:00", "end": "18:00"}}


async def test_project_update_ignores_protected_fields(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "protected.example.com")
    other = (await client.post("/api/auth/register", json={"email": "thief@example.com", "password": "secret123"})).json()
    other_id = (await client.get("/api/users/profile", headers={"Authorization": f"Bearer {other['access_token']}"})).json()["id"]

    resp = await client.put(f"/api/projects/{pid}", json={"user_id": other_id, "balance_credits": 10**9}, headers=auth_headers)
    assert resp.status_code == codes.UNPROCESSABLE_ENTITY
    balance = (await client.get(f"/api/projects/{pid}/balance", headers=auth_headers)).json()
    assert balance["balance"] == 0
    assert (await client.get(f"/api/projects/{pid}", headers=auth_headers)).status_code == codes.OK  # still mine


async def test_project_update_rejects_foreign_group(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "grp-guard.example.com")
    other = (await client.post("/api/auth/register", json={"email": "grp-other@example.com", "password": "secret123"})).json()
    foreign_gid = (await client.post("/api/projects/groups", json={"name": "Чужая"},
                                     headers={"Authorization": f"Bearer {other['access_token']}"})).json()["id"]
    resp = await client.put(f"/api/projects/{pid}", json={"group_id": foreign_gid}, headers=auth_headers)
    assert resp.status_code == codes.UNPROCESSABLE_ENTITY


async def test_status_bar_counts_are_real(client: AsyncClient, auth_headers, app_fixture):
    from datetime import datetime, timedelta, timezone
    from uuid import UUID

    from services.queue_service.domain.models import QueueTask

    daily = await _project(client, auth_headers, "daily.example.com")
    hourly = (await client.post("/api/projects/", json={"name": "H", "domain": "h.example.com", "strategy_type": "hourly", "daily_limit": 24}, headers=auth_headers)).json()["id"]
    off = (await client.post("/api/projects/", json={"name": "Off", "domain": "off.example.com", "daily_limit": 99}, headers=auth_headers)).json()["id"]
    await client.put(f"/api/projects/{daily}", json={"daily_limit": 10}, headers=auth_headers)
    await client.post("/api/projects/bulk-toggle", json={"project_ids": [off], "is_active": False}, headers=auth_headers)

    now = datetime.now(timezone.utc)
    async with app_fixture.state.session_factory() as session:
        session.add_all([
            QueueTask(project_id=UUID(daily), click_url="https://d/1", status="pending", created_at=now - timedelta(hours=2)),
            QueueTask(project_id=UUID(daily), click_url="https://d/2", status="pending", created_at=now),
            QueueTask(project_id=UUID(daily), click_url="https://d/3", status="completed", created_at=now - timedelta(days=3), updated_at=now),
            QueueTask(project_id=UUID(hourly), click_url="https://h/1", status="completed", created_at=now, updated_at=now),
            QueueTask(project_id=UUID(hourly), click_url="https://h/2", status="completed", created_at=now - timedelta(days=3), updated_at=now - timedelta(days=3)),
        ])
        await session.commit()

    stats = (await client.get("/api/queue/dashboard-stats", headers=auth_headers)).json()
    assert stats["overdue"] == 1                      # waiting for over 30 minutes
    assert stats["today_completed"] == 2              # finished today, whenever created
    assert stats["today_planned"] == 10 + 24          # daily quotas of active projects


async def test_openapi_and_health_are_under_api_prefix(client: AsyncClient):
    """nginx only forwards /api/* to the backend, so the spec and health check must live there."""
    assert (await client.get("/api/openapi.json")).status_code == codes.OK
    assert (await client.get("/api/external/v1/health")).json() == {"status": "ok"}


async def test_geo_code_search_works(client: AsyncClient, auth_headers):
    resp = await client.get("/api/projects/geo-codes/search?q=Моск", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text


async def test_missing_required_fields_are_rejected_not_crashing(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers)
    for path in ("/api/projects/", "/api/projects/groups", f"/api/projects/{pid}/queries",
                 f"/api/projects/{pid}/delegates", "/api/queue/push"):
        resp = await client.post(path, json={}, headers=auth_headers)
        assert resp.status_code == codes.UNPROCESSABLE_ENTITY, f"{path} -> {resp.status_code}"


async def _completed_clicks(client: AsyncClient, headers, pid: str, positions: list[int | None]) -> None:
    """Complete one proklik task per entry, reporting that position (None = agent sent no position)."""
    await client.post(f"/api/projects/{pid}/queries", json={"text": "слон"}, headers=headers)
    await client.post("/api/queue/proklik", json={"project_id": pid, "count": len(positions)}, headers=headers)
    tasks = (await client.get(f"/api/queue/?project_id={pid}", headers=headers)).json()
    results = [{"task_id": t["id"], "status": "completed", **({"position": pos} if pos else {})}
               for t, pos in zip(tasks, positions, strict=True)]
    await client.post("/api/queue/results", json={"results": results}, headers=headers)


async def test_analytics_summary_reports_average_position(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "avg.example.com")
    await _completed_clicks(client, auth_headers, pid, [2, 5, None])

    summary = (await client.get(f"/api/analytics/summary?project_id={pid}", headers=auth_headers)).json()
    assert (summary["completed_clicks"], summary["avg_position"]) == (3, 3.5)
    empty = await _project(client, auth_headers, "empty.example.com")
    assert (await client.get(f"/api/analytics/summary?project_id={empty}", headers=auth_headers)).json()["avg_position"] is None


async def test_top_ranges_count_clicks_without_position(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "ranges.example.com")
    await _completed_clicks(client, auth_headers, pid, [2, 5, None])

    for mode in ("", "&suggestion_mode=without"):
        data = (await client.get(f"/api/analytics/top-ranges?project_id={pid}{mode}", headers=auth_headers)).json()
        assert [(r["label"], r["clicks"]) for r in data["ranges"]] == [("1–3 (Топ-3)", 1), ("4–5", 1)]
        assert (data["total_clicks"], data["no_position_clicks"]) == (2, 1)


async def test_csv_reports_download_for_cyrillic_project_name(client: AsyncClient, auth_headers):
    resp = await client.post("/api/projects/", json={"name": "Окна СПб", "domain": "okna.example.com"}, headers=auth_headers)
    pid = resp.json()["id"]
    await _completed_clicks(client, auth_headers, pid, [4])

    for report in ("analytics", "summary"):
        resp = await client.get(f"/api/projects/{pid}/reports/{report}.csv", headers=auth_headers)
        assert resp.status_code == codes.OK, report
        assert "filename*=UTF-8''" in resp.headers["content-disposition"]
        assert resp.content.startswith("﻿".encode())  # Excel needs the BOM to read UTF-8


async def test_queries_survive_export_and_reimport(client: AsyncClient, auth_headers):
    source = await _project(client, auth_headers, "source.example.com")
    created = await client.post(f"/api/projects/{source}/queries", json={"text": "купить слона"}, headers=auth_headers)
    await client.put(
        f"/api/projects/{source}/queries/{created.json()['id']}",
        json={"daily_clicks": 7, "frequency": 300, "geo": {"region": "Москва"}, "url": "https://source.example.com/slon"},
        headers=auth_headers,
    )
    exported = await client.get(f"/api/projects/{source}/queries/export.csv", headers=auth_headers)

    target = await _project(client, auth_headers, "target.example.com")
    for _ in range(2):  # the second import finds the query already there
        resp = await client.post(f"/api/projects/{target}/queries/import", content=exported.content, headers=auth_headers)
        assert resp.status_code == codes.OK, resp.text
    assert resp.json() == {"created": 0, "skipped": 1}

    [query] = (await client.get(f"/api/projects/{target}/queries", headers=auth_headers)).json()
    assert (query["text"], query["daily_clicks"], query["frequency"], query["geo"]) == ("купить слона", 7, 300, {"region": "Москва"})
    assert query["url"] == "https://source.example.com/slon"
    assert query["click_url"]


async def test_import_accepts_excel_csv(client: AsyncClient, auth_headers):
    """Russian Excel saves with a BOM and ';' separators."""
    pid = await _project(client, auth_headers, "excel.example.com")
    body = "﻿text;url\nокна пвх;https://excel.example.com/okna\n".encode()
    resp = await client.post(f"/api/projects/{pid}/queries/import", content=body, headers=auth_headers)
    assert resp.json() == {"created": 1, "skipped": 0}
    [query] = (await client.get(f"/api/projects/{pid}/queries", headers=auth_headers)).json()
    assert (query["text"], query["url"]) == ("окна пвх", "https://excel.example.com/okna")

    cp1251 = "Текст\nокна дешево\n".encode("cp1251")  # "CSV (разделители - запятые)" in older Excel
    resp = await client.post(f"/api/projects/{pid}/queries/import", content=cp1251, headers=auth_headers)
    assert resp.json() == {"created": 1, "skipped": 0}


async def test_global_search_query_results_link_to_the_query(client: AsyncClient, auth_headers):
    pid = await _project(client, auth_headers, "search.example.com")
    await client.post(f"/api/projects/{pid}/queries", json={"text": "окна & двери #1"}, headers=auth_headers)

    [hit] = (await client.get("/api/projects/global-search?q=двери", headers=auth_headers)).json()["queries"]
    assert hit["project_name"] == "Original"
    assert hit["href"] == f"/projects/{pid}?tab=queries&query=%D0%BE%D0%BA%D0%BD%D0%B0+%26+%D0%B4%D0%B2%D0%B5%D1%80%D0%B8+%231"
