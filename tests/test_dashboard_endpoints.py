"""Authenticated listing/dashboard endpoints used by the main app layout."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest_asyncio
from httpx import AsyncClient, codes
from sqlalchemy import select


@pytest_asyncio.fixture
async def owned_project(app_fixture, auth_headers):
    """Project with a custom integration and one pending task, owned by the auth_headers user."""
    from services.auth_service.domain.models import User
    from services.project_service.domain.models import Project, ProjectToken
    from services.queue_service.domain.models import QueueTask

    async with app_fixture.state.session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "owner@example.com"))).scalar_one()
        project = Project(
            id=uuid4(),
            user_id=user.id,
            name="Dashboard Project",
            domain="dashboard.example.com",
            integrations={"integration_type": "custom-srv"},
        )
        session.add(project)
        await session.flush()
        session.add(QueueTask(  # a minute old, so tasks added by a test sort after it
            project_id=project.id, click_url="https://dashboard.example.com/",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        session.add(ProjectToken(user_id=user.id, project_id=project.id, name="mobile", token_string="dash-token"))
        await session.commit()
        return project


async def test_create_project_owned_by_token_user(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/projects/",
        json={"name": "Created via UI", "domain": "https://ui.example.com", "region": "Москва"},
        headers=auth_headers,
    )
    assert resp.status_code == codes.OK, resp.text

    listing = await client.get("/api/projects/?page=1&page_size=20", headers=auth_headers)
    assert "Created via UI" in [p["name"] for p in listing.json()["items"]]


async def test_added_query_is_persisted(client: AsyncClient, auth_headers, owned_project):
    path = f"/api/projects/{owned_project.id}/queries"
    resp = await client.post(path, json={"text": "купить слона"}, headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text

    listing = await client.get(path, headers=auth_headers)
    assert "купить слона" in [q["text"] for q in listing.json()]


async def test_deleted_project_is_gone(client: AsyncClient, auth_headers, owned_project):
    resp = await client.delete(f"/api/projects/{owned_project.id}", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text

    again = await client.get(f"/api/projects/{owned_project.id}", headers=auth_headers)
    assert again.status_code == codes.NOT_FOUND


async def test_pushed_tasks_are_persisted(client: AsyncClient, auth_headers, owned_project):
    resp = await client.post(
        "/api/queue/push",
        json={"project_id": str(owned_project.id), "tasks": [{"click_url": "https://dashboard.example.com/a"}]},
        headers=auth_headers,
    )
    assert resp.status_code == codes.OK, resp.text

    stats = await client.get(f"/api/queue/stats?project_id={owned_project.id}", headers=auth_headers)
    assert stats.json()["pending"] == 2  # fixture task + pushed task


async def test_submitted_results_are_persisted(client: AsyncClient, auth_headers, owned_project):
    tasks = (await client.get(f"/api/queue/?project_id={owned_project.id}", headers=auth_headers)).json()
    resp = await client.post(
        "/api/queue/results",
        json={"results": [{"task_id": tasks[0]["id"], "status": "completed", "position": 3}]},
        headers=auth_headers,
    )
    assert resp.json() == {"updated": 1, "errors": []}

    stats = await client.get(f"/api/queue/stats?project_id={owned_project.id}", headers=auth_headers)
    assert (stats.json()["pending"], stats.json()["completed"]) == (0, 1)


async def test_cleared_queue_stays_empty(client: AsyncClient, auth_headers, owned_project):
    resp = await client.post(f"/api/queue/clear?project_id={owned_project.id}", headers=auth_headers)
    assert resp.json() == {"deleted": 1}

    stats = await client.get(f"/api/queue/stats?project_id={owned_project.id}", headers=auth_headers)
    assert stats.json()["pending"] == 0


async def test_proklik_creates_clickable_tasks_from_queries(client: AsyncClient, auth_headers, owned_project):
    await client.post(
        f"/api/projects/{owned_project.id}/queries",
        json={"text": "купить слона", "click_url": "https://yandex.ru/search/?text=slon"},
        headers=auth_headers,
    )
    for _ in range(2):  # repeated prokliks on the same query must not collide
        resp = await client.post(
            "/api/queue/proklik", json={"project_id": str(owned_project.id), "count": 2}, headers=auth_headers
        )
        assert resp.status_code == codes.OK, resp.text

    tasks = (await client.get(f"/api/queue/?project_id={owned_project.id}", headers=auth_headers)).json()
    prokliks = [t for t in tasks if t["source"] == "proklik"]
    assert len(prokliks) == 4
    assert {t["click_url"] for t in prokliks} == {"https://yandex.ru/search/?text=slon"}


async def test_proklik_without_queries_is_rejected(client: AsyncClient, auth_headers, owned_project):
    resp = await client.post(
        "/api/queue/proklik", json={"project_id": str(owned_project.id), "count": 1}, headers=auth_headers
    )
    assert resp.status_code == codes.BAD_REQUEST


async def test_queue_list_filters_by_integration(client: AsyncClient, auth_headers, owned_project):
    resp = await client.get("/api/queue/?integration=custom-srv", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text
    assert len(resp.json()) == 1
    other = await client.get("/api/queue/?integration=yandex-webmaster", headers=auth_headers)
    assert other.json() == []


async def test_list_projects_authenticated(client: AsyncClient, auth_headers, owned_project):
    resp = await client.get("/api/projects/?page=1&page_size=20", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text


async def test_list_integrations_includes_custom(client: AsyncClient, auth_headers, owned_project):
    resp = await client.get("/api/projects/integrations", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text
    assert "custom-srv" in {i["key"] for i in resp.json()["integrations"]}


async def test_dashboard_stats_with_project(client: AsyncClient, auth_headers, owned_project):
    resp = await client.get("/api/queue/dashboard-stats", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text
    assert set(resp.json()) >= {"overdue", "today_planned", "today_completed", "balance"}


async def test_dashboard_servers_with_pending_task(client: AsyncClient, auth_headers, owned_project):
    resp = await client.get("/api/queue/dashboard-servers", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text


async def test_queue_stats_integration_filter(client: AsyncClient, auth_headers, owned_project):
    resp = await client.get("/api/queue/stats?integration=custom-srv", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text
    assert resp.json()["pending"] == 1


async def test_external_status_with_token(client: AsyncClient, owned_project):
    resp = await client.get("/api/external/v1/external/status", headers={"X-Auth-Token": "dash-token"})
    assert resp.status_code == codes.OK, resp.text


async def _finished_task(app_fixture, project_id, status: str, minutes_ago: int) -> None:
    """A task created long ago whose result came in `minutes_ago` minutes ago."""
    from services.queue_service.domain.models import QueueTask

    finished = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    async with app_fixture.state.session_factory() as session:
        session.add(QueueTask(
            project_id=project_id, click_url=f"https://dashboard.example.com/{uuid4()}", status=status,
            created_at=finished - timedelta(days=2), updated_at=finished,
        ))
        await session.commit()


async def test_dashboard_servers_count_results_by_finish_time(client: AsyncClient, auth_headers, owned_project, app_fixture):
    for status, minutes_ago in [("completed", 5), ("completed", 40), ("not_found", 10), ("completed", 25 * 60)]:
        await _finished_task(app_fixture, owned_project.id, status, minutes_ago)

    [panel] = (await client.get("/api/queue/dashboard-servers", headers=auth_headers)).json()
    assert panel["integration"] == "custom-srv"
    assert (panel["pending"], panel["speed_per_15min"], panel["completed_24h"], panel["not_found_24h"]) == (1, 1, 2, 1)
    assert sum(panel["hourly_bars"]) == 2


async def test_dashboard_servers_groups_projects_without_integration(client: AsyncClient, auth_headers, owned_project):
    created = await client.post("/api/projects/", json={"name": "Plain", "domain": "plain.example.com"}, headers=auth_headers)
    pid = created.json()["id"]
    await client.post(
        "/api/queue/push", json={"project_id": pid, "tasks": [{"click_url": "https://plain.example.com/"}]},
        headers=auth_headers,
    )

    resp = await client.get("/api/queue/dashboard-servers", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text
    assert [(s["integration"], s["pending"]) for s in resp.json()] == [("custom-srv", 1), ("default", 1)]


async def test_queue_list_shows_results_newest_first(client: AsyncClient, auth_headers, owned_project):
    await client.post(
        "/api/queue/push",
        json={"project_id": str(owned_project.id), "tasks": [{"click_url": "https://dashboard.example.com/new"}]},
        headers=auth_headers,
    )
    tasks = (await client.get("/api/queue/", headers=auth_headers)).json()
    assert [t["click_url"] for t in tasks] == ["https://dashboard.example.com/new", "https://dashboard.example.com/"]

    await client.post(
        "/api/queue/results",
        json={"results": [{"task_id": tasks[1]["id"], "status": "completed", "position": 7, "details": "ok"}]},
        headers=auth_headers,
    )
    done = (await client.get("/api/queue/?status=completed", headers=auth_headers)).json()[0]
    assert (done["position"], done["project_id"], done["project_name"]) == (7, str(owned_project.id), "Dashboard Project")
    assert done["updated_at"]
    assert len((await client.get("/api/queue/?limit=1", headers=auth_headers)).json()) == 1


async def test_queue_date_filter_includes_the_whole_end_day(client: AsyncClient, auth_headers, owned_project):
    created = (await client.get("/api/queue/", headers=auth_headers)).json()[0]["created_at"]
    today = datetime.fromisoformat(created).date()
    for path in ("/api/queue/", "/api/queue/stats"):
        same_day = (await client.get(f"{path}?from_date={today}&to_date={today}", headers=auth_headers)).json()
        later = (await client.get(f"{path}?from_date={today + timedelta(days=1)}", headers=auth_headers)).json()
        if path == "/api/queue/stats":
            same_day, later = same_day["pending"], later["pending"]
        else:
            same_day, later = len(same_day), len(later)
        assert (same_day, later) == (1, 0), path


async def test_default_integration_means_project_without_one(client: AsyncClient, auth_headers, owned_project):
    pid = (await client.post("/api/projects/", json={"name": "Plain", "domain": "plain.example.com"}, headers=auth_headers)).json()["id"]
    await client.post(
        "/api/queue/push", json={"project_id": pid, "tasks": [{"click_url": "https://plain.example.com/"}]},
        headers=auth_headers,
    )
    tasks = (await client.get("/api/queue/?integration=default", headers=auth_headers)).json()
    assert [t["click_url"] for t in tasks] == ["https://plain.example.com/"]
    assert (await client.get("/api/queue/stats?integration=default", headers=auth_headers)).json()["pending"] == 1
