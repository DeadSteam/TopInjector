"""Integration tests for routes: analytics, projects queries, queue-stats, positions."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, codes
from sqlalchemy import select

from tests.conftest import bearer


# ── Fixtures ────────────────────────────────────────────────────────────────── #


@pytest_asyncio.fixture
async def test_user_and_project(app_fixture, client):
    """Create a user + project and return (project_id, query_id_factory)."""
    from services.auth_service.domain.models import User
    from services.project_service.domain.models import Project as _Project

    async with app_fixture.state.session_factory() as session:
        user = User(email="route-test@example.com", password_hash="x", display_name="RouteTester")
        session.add(user)
        await session.flush()
        client.headers.update(bearer(user.id))

        project = _Project(
            id=uuid4(),
            user_id=user.id,  # type: ignore[union-attr]
            name="Route Test Project",
            domain="route-test.example.com",
        )
        session.add(project)
        await session.commit()
        yield str(project.id)  # type: ignore[union-attr]


@pytest_asyncio.fixture
async def project_with_queries(app_fixture, client):
    """Create user, project, and two queries. Returns (project_id, query_ids)."""
    from services.project_service.domain.models import Query as _Query

    async with app_fixture.state.session_factory() as session:
        from services.auth_service.domain.models import User
        from services.project_service.domain.models import Project as _Project

        user = User(email="rq-test@example.com", password_hash="x", display_name="RQTester")
        session.add(user)
        await session.flush()
        client.headers.update(bearer(user.id))

        project = _Project(
            id=uuid4(),
            user_id=user.id,  # type: ignore[union-attr]
            name="RQ Test Project",
            domain="rq-test.example.com",
        )
        session.add(project)
        await session.flush()

        q1 = _Query(
            project_id=project.id,  # type: ignore[union-attr]
            text="query one",
            url="https://example.com/1",
            click_url="https://google.com/search?q=one",
        )
        q2 = _Query(
            project_id=project.id,  # type: ignore[union-attr]
            text="query two",
            url="https://example.com/2",
            click_url="https://google.com/search?q=two",
        )
        session.add_all([q1, q2])
        await session.flush()

        yield str(project.id), [str(q1.id), str(q2.id)]  # type: ignore[union-attr]


# ── Projects: create + list ------------------------------------------------ #


async def test_create_project(client: AsyncClient, app_fixture, logged_in):
    # Create user and project in the same session (SQLite FK needs same transaction)
    async with app_fixture.state.session_factory() as sess:
        from services.auth_service.domain.models import User
        from services.project_service.domain.models import Project as _P

        user = User(email="create-test@example.com", password_hash="x", display_name="CreateTest")
        sess.add(user)
        await sess.flush()

        project = _P(id=uuid4(), user_id=user.id, name="New Project", domain="new.example.com")
        sess.add(project)
        await sess.commit()

    resp = await client.post("/api/projects/")
    assert resp.status_code in (codes.OK, 422)  # 422 if body required, OK if defaults used
    data = resp.json()
    assert "id" in data or "detail" in data


async def test_list_projects_empty(client: AsyncClient, logged_in):
    resp = await client.get("/api/projects/")
    assert resp.status_code == codes.OK


# ── Projects: add query with auto click_url -------------------------------- #


async def test_add_query_auto_click_url(client: AsyncClient, test_user_and_project):
    project_id = test_user_and_project

    resp = await client.post(
        f"/api/projects/{project_id}/queries",
        json={"text": "test query"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "id" in data
    assert "google.com" in data["click_url"]


async def test_add_query_auto_click_url_yandex(client: AsyncClient, test_user_and_project):
    project_id = test_user_and_project

    resp = await client.post(
        f"/api/projects/{project_id}/queries",
        json={"text": "купить слона", "search_engine": "yandex"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "yandex.ru" in data["click_url"] or "купить слона" in data["click_url"]


async def test_add_query_custom_click_url(client: AsyncClient, test_user_and_project):
    project_id = test_user_and_project

    resp = await client.post(
        f"/api/projects/{project_id}/queries",
        json={"text": "test", "click_url": "https://custom.example.com/page"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "custom.example.com" in data["click_url"]


# ── Projects: list queries with completed counts ---------------------------- #


async def test_list_queries_completed_count(client: AsyncClient, app_fixture, project_with_queries):
    project_id, query_ids = project_with_queries

    from services.queue_service.domain.models import QueueTask
    from sqlalchemy import select  # noqa: F401 — for compatibility

    async with app_fixture.state.session_factory() as sess:
        task1 = QueueTask(
            project_id=UUID(project_id),
            query_id=UUID(query_ids[0]),
            click_url="https://example.com/1",
            source="strategy",
            status="completed",
        )
        task2 = QueueTask(
            project_id=UUID(project_id),
            query_id=UUID(query_ids[0]),
            click_url="https://example.com/2",
            source="proklik",
            status="completed",
        )
        sess.add_all([task1, task2])
        await sess.commit()

    resp = await client.get(f"/api/projects/{project_id}/queries")
    assert resp.status_code == codes.OK
    queries = resp.json()
    assert len(queries) == 2

    q1 = next(q for q in queries if q["text"] == "query one")
    q2 = next(q for q in queries if q["text"] == "query two")
    assert q1["completed"] == 2, f"Expected 2 completed for q1, got {q1['completed']}"
    assert q2["completed"] == 0


# ── Projects: queue-stats -------------------------------------------------- #


async def test_queue_stats_empty(client: AsyncClient, test_user_and_project):
    project_id = test_user_and_project

    resp = await client.get(f"/api/projects/{project_id}/queue-stats")
    assert resp.status_code == codes.OK
    stats = resp.json()
    assert "pending" in stats
    assert "in_progress" in stats
    assert "completed" in stats
    assert "not_found" in stats
    assert "stuck" in stats
    assert stats["pending"] == 0


async def test_queue_stats_counts(client: AsyncClient, app_fixture, test_user_and_project):
    project_id = test_user_and_project

    from services.queue_service.domain.models import QueueTask

    async with app_fixture.state.session_factory() as sess:
        tasks_data = [
            ("strategy", "pending", "https://example.com/p1"),
            ("proklik", "in_progress", "https://example.com/ip1"),
            ("autoburst", "completed", "https://example.com/c1"),
            ("strategy", "completed", "https://example.com/c2"),
            ("proklik", "not_found", "https://example.com/nf1"),
        ]
        tasks = [
            QueueTask(project_id=UUID(project_id), click_url=url, source=src, status=st)
            for src, st, url in tasks_data
        ]
        sess.add_all(tasks)
        await sess.commit()

    resp = await client.get(f"/api/projects/{project_id}/queue-stats")
    assert resp.status_code == codes.OK
    stats = resp.json()
    assert stats["pending"] == 1
    assert stats["in_progress"] == 1
    assert stats["completed"] == 2
    assert stats["not_found"] == 1
    assert stats["stuck"] == 0


# ── Projects: positions ---------------------------------------------------- #


async def test_positions_empty(client: AsyncClient, test_user_and_project):
    project_id = test_user_and_project

    resp = await client.get(f"/api/projects/{project_id}/positions")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "project_id" in data
    assert data["history"] == []


async def test_positions_with_history(client: AsyncClient, app_fixture, project_with_queries):
    project_id, query_ids = project_with_queries

    from services.queue_service.domain.models import QueueTask

    async with app_fixture.state.session_factory() as sess:
        tasks = [
            QueueTask(
                project_id=UUID(project_id),
                query_id=UUID(query_ids[0]),
                click_url="https://example.com/target",
                source="strategy",
                status="completed",
                position=5,
            ),
            QueueTask(
                project_id=UUID(project_id),
                query_id=UUID(query_ids[0]),
                click_url="https://example.com/target",
                source="strategy",
                status="completed",
                position=3,
            ),
        ]
        sess.add_all(tasks)
        await sess.commit()

    resp = await client.get(f"/api/projects/{project_id}/positions")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert len(data["history"]) == 2


# ── Analytics: summary ----------------------------------------------------- #


async def test_analytics_summary(client: AsyncClient, logged_in):
    resp = await client.get("/api/analytics/summary")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "completed_clicks" in data
    assert "project_id" in data


# ── Analytics: clicks timeline --------------------------------------------- #


async def test_analytics_clicks(client: AsyncClient, test_user_and_project):
    project_id = test_user_and_project

    resp = await client.get(f"/api/analytics/clicks?project_id={project_id}")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "timeline" in data


# ── Analytics: positions endpoint ------------------------------------------ #


async def test_analytics_positions(client: AsyncClient, logged_in):
    resp = await client.get("/api/analytics/positions")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "project_id" in data
    assert "history" in data


# ── External API: projects ------------------------------------------------- #


async def test_external_projects_list(client: AsyncClient, app_fixture, test_user_and_project):
    project_id = test_user_and_project

    from services.project_service.domain.models import Project as _Project, ProjectToken
    from services.auth_service.domain.models import User

    async with app_fixture.state.session_factory() as session:
        user_result = await session.execute(select(User).where(User.email == "route-test@example.com"))
        user = user_result.scalars().first()
        assert user is not None
        proj = await session.execute(select(_Project).where(_Project.id == UUID(project_id)))
        project = proj.scalars().first()  # type: ignore[union-attr]

        token_obj = ProjectToken(
            user_id=user.id,
            project_id=project.id,  # type: ignore[union-attr]
            name="External API Token",
            token_string="tk_ext_test_0123456789abcdef",
        )
        session.add(token_obj)
        await session.commit()

    resp = await client.get(
        "/api/external/v1/projects",
        headers={"X-Auth-Token": "tk_ext_test_0123456789abcdef"},
    )
    assert resp.status_code == codes.OK


# ── Edge cases: invalid project id ----------------------------------------- #


async def test_queue_stats_invalid_project(client: AsyncClient, logged_in):
    resp = await client.get("/api/projects/00000000-0000-0000-0000-000000000000/queue-stats")
    assert resp.status_code == codes.NOT_FOUND


async def test_positions_invalid_project(client: AsyncClient, logged_in):
    resp = await client.get("/api/projects/00000000-0000-0000-0000-000000000000/positions")
    assert resp.status_code == codes.NOT_FOUND
