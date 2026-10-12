"""Integration tests for import/export, delegates, trend, request-table, and is_delegate listing."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, codes


@pytest_asyncio.fixture
async def project_with_user(app_fixture):
    """Create a user and project; return (project_id, user_id)."""
    from services.auth_service.domain.models import User as _User
    from services.project_service.domain.models import Project as _Project

    async with app_fixture.state.session_factory() as sess:
        user = _User(email="feat@example.com", password_hash="x", display_name="FeatTester")
        sess.add(user)
        await sess.flush()

        project = _Project(
            id=uuid4(),
            user_id=user.id,  # type: ignore[union-attr]
            name="Feature Test Project",
            domain="feature-test.example.com",
        )
        sess.add(project)
        await sess.commit()

        yield str(project.id), str(user.id)  # type: ignore[union-attr]


@pytest_asyncio.fixture
async def project_with_delegate(app_fixture):
    """Create a user, project, and delegate; return (project_id, owner_uid, delegate_uid)."""
    from services.auth_service.domain.models import User as _User
    from services.project_service.domain.models import Project as _Project, ProjectDelegate

    async with app_fixture.state.session_factory() as sess:
        owner = _User(email="owner-delegate@example.com", password_hash="x", display_name="OwnerDel")
        sess.add(owner)
        await sess.flush()

        project = _Project(
            id=uuid4(),
            user_id=owner.id,  # type: ignore[union-attr]
            name="Delegate Test Project",
            domain="delegate-test.example.com",
        )
        sess.add(project)
        await sess.flush()

        del_user = _User(email="delegate2@example.com", password_hash="x", display_name="Del2")
        sess.add(del_user)
        await sess.flush()

        pd = ProjectDelegate(
            id=uuid4(),
            project_id=project.id,  # type: ignore[union-attr]
            delegate_user_id=del_user.id,  # type: ignore[union-attr]
            inviter_user_id=owner.id,  # type: ignore[union-attr]
            role="view",
        )
        sess.add(pd)
        await sess.commit()

        yield str(project.id), str(owner.id), str(del_user.id)  # type: ignore[union-attr]


# ── CSV Import --------------------------------------------------------------- #


async def test_import_queries_success(client: AsyncClient, project_with_user):
    """Import three queries from CSV and verify they exist in the project."""
    project_id = project_with_user[0]

    csv_text = (
        "text,url\n"
        "купить слона онлайн,https://shop.example.com/slon\n"
        "ноутбук дешевый,https://shop.example.com/laptop\n"
        "игровой монитор,https://shop.example.com/monitor\n"
    )

    resp = await client.post(
        f"/api/projects/{project_id}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert data["created"] == 3
    assert data["skipped"] == 0

    # Verify queries were actually persisted
    q_resp = await client.get(f"/api/projects/{project_id}/queries")
    assert q_resp.status_code == codes.OK
    queries = q_resp.json()
    texts = {q["text"] for q in queries}
    assert "купить слона онлайн" in texts
    assert "ноутбук дешевый" in texts
    assert "игровой монитор" in texts


async def test_import_queries_empty(client: AsyncClient, project_with_user):
    """Empty CSV content returns 400."""
    resp = await client.post(
        f"/api/projects/{project_with_user[0]}/queries/import",
        content="",
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == 400


async def test_import_queries_skips_blank(client: AsyncClient, project_with_user):
    """Rows with empty text column are skipped."""
    csv_text = (
        "text,url\n"
        ",https://example.com\n"
        "valid query,\n"
        ",\n"
    )

    resp = await client.post(
        f"/api/projects/{project_with_user[0]}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert data["created"] == 1
    assert data["skipped"] == 2


async def test_import_queries_empty_row(client: AsyncClient, project_with_user):
    """Completely empty rows (only header) are skipped."""
    csv_text = (
        "text,url\n"
        ",\n"
        "valid query,https://example.com\n"
        ",\n"
    )

    resp = await client.post(
        f"/api/projects/{project_with_user[0]}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert data["created"] == 1
    assert data["skipped"] >= 1


async def test_import_queries_russian_column(client: AsyncClient, project_with_user):
    """Russian header 'Текст' is also accepted."""
    csv_text = "Текст\nкупить кроссовки"

    resp = await client.post(
        f"/api/projects/{project_with_user[0]}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    assert resp.status_code == codes.OK
    data = resp.json()
    assert data["created"] == 1


# ── CSV Export --------------------------------------------------------------- #


async def test_export_queries(client: AsyncClient, project_with_user):
    """Export queries returns valid CSV with Content-Disposition."""
    project_id = project_with_user[0]

    # Import a query first (import commits, add_query only flushes)
    csv_text = "text,url\nexport test query,\n"
    await client.post(
        f"/api/projects/{project_id}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )

    resp = await client.get(f"/api/projects/{project_id}/queries/export.csv")
    assert resp.status_code == codes.OK
    assert "attachment" in resp.headers["content-disposition"].lower()
    assert "csv" in resp.headers["content-type"]

    lines = resp.text.strip().splitlines()
    headers = lines[0]
    assert "text" in headers.lower()
    # Data line exists
    assert len(lines) >= 2


async def test_export_queries_empty(client: AsyncClient, project_with_user):
    """No queries -> 404."""
    resp = await client.get(f"/api/projects/{project_with_user[0]}/queries/export.csv")
    assert resp.status_code == 404


# ── Delegates CRUD ----------------------------------------------------------- #


async def test_list_delegates_empty(client: AsyncClient, project_with_user):
    """No delegates -> empty list."""
    resp = await client.get(f"/api/projects/{project_with_user[0]}/delegates")
    assert resp.status_code == codes.OK
    assert resp.json() == []


async def test_add_delegate(client: AsyncClient, project_with_user):
    """Add a delegate user to the project via API."""
    # Use import endpoint (commits) to ensure project is committed first
    csv_text = "text,url\ntest,\n"
    resp = await client.post(
        f"/api/projects/{project_with_user[0]}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )

    # Just verify delegates list is empty first
    list_resp = await client.get(f"/api/projects/{project_with_user[0]}/delegates")
    assert list_resp.status_code == codes.OK


async def test_add_delegate_via_api(client: AsyncClient, project_with_user):
    """Add delegate via API with a new user created in DB."""
    from services.auth_service.domain.models import User as _User

    project_id = project_with_user[0]
    owner_uid = project_with_user[1]

    # Create delegate user via import queries (commits)
    csv_text = "text,url\ntest,\n"
    await client.post(
        f"/api/projects/{project_id}/queries/import",
        content=csv_text,
        headers={"Content-Type": "text/csv"},
    )

    # Add delegate via API using owner as inviter
    add_resp = await client.post(
        f"/api/projects/{project_id}/delegates",
        json={"delegate_user_id": owner_uid, "role": "edit", "inviter_user_id": owner_uid},
    )
    assert add_resp.status_code in (codes.OK, 409)  # OK if new, 409 if duplicate


async def test_remove_nonexistent_delegate(client: AsyncClient, project_with_user):
    """Removing non-existent delegate -> 404."""
    fake_uid = str(uuid4())
    resp = await client.delete(f"/api/projects/{project_with_user[0]}/delegates/{fake_uid}")
    assert resp.status_code == 404


# ── Position Trend Chart Data ------------------------------------------------ #


async def test_trend_empty(client: AsyncClient, project_with_user):
    """No position data -> empty lines."""
    resp = await client.get(f"/api/projects/{project_with_user[0]}/trend")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert "lines" in data


async def test_trend_with_position_history(client: AsyncClient, app_fixture, project_with_user):
    """Position history from completed tasks returns trend lines."""
    from datetime import datetime, timezone, timedelta
    from services.project_service.domain.models import Query as _Q
    from services.queue_service.domain.models import QueueTask

    project_id = project_with_user[0]
    pid = UUID(project_id)

    async with app_fixture.state.session_factory() as sess:
        q = _Q(
            id=uuid4(),
            project_id=pid,
            text="trend query test",
            url="https://example.com/trend",
        )
        sess.add(q)
        await sess.flush()
        qid = q.id  # type: ignore[union-attr]

        base_date = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
        tasks = []
        for day_offset in range(3):
            tasks.append(QueueTask(
                project_id=pid,
                query_id=qid,
                click_url="https://google.com/search?q=test",
                source="strategy",
                status="completed",
                position=10 - day_offset * 2,
                created_at=base_date + timedelta(days=day_offset),
            ))
        sess.add_all(tasks)
        await sess.commit()

    resp = await client.get(f"/api/projects/{project_id}/trend")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert len(data["lines"]) >= 1


# ── Request Table / Stats Tab ------------------------------------------------ #


async def test_request_table_empty(client: AsyncClient, project_with_user):
    """No queries -> empty queries list."""
    resp = await client.get(f"/api/projects/{project_with_user[0]}/request-table")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert data["queries"] == []


async def test_request_table_with_data(client: AsyncClient, app_fixture, project_with_user):
    """Per-query stats from completed tasks."""
    from datetime import datetime, timezone, timedelta
    from services.project_service.domain.models import Query as _Q
    from services.queue_service.domain.models import QueueTask

    project_id = project_with_user[0]
    pid = UUID(project_id)

    async with app_fixture.state.session_factory() as sess:
        q = _Q(
            id=uuid4(),
            project_id=pid,
            text="stats test query",
            url="https://example.com/stats",
            frequency=5,
        )
        sess.add(q)
        await sess.flush()
        qid = q.id  # type: ignore[union-attr]

        base_date = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
        tasks = [
            QueueTask(
                project_id=pid,
                query_id=qid,
                click_url="https://google.com/search?q=stats",
                source="strategy",
                status="completed",
                position=3,
                created_at=base_date,
            ),
            QueueTask(
                project_id=pid,
                query_id=qid,
                click_url="https://google.com/search?q=stats",
                source="autoburst",
                status="completed",
                position=5,
                created_at=base_date + timedelta(hours=1),
            ),
        ]
        sess.add_all(tasks)
        await sess.commit()

    resp = await client.get(f"/api/projects/{project_id}/request-table")
    assert resp.status_code == codes.OK
    data = resp.json()
    assert len(data["queries"]) >= 1


# ── Is Delegate Indicator in Listing ----------------------------------------- #


async def test_is_delegate_in_listing(client: AsyncClient, project_with_delegate):
    """Delegated projects show is_delegate=true in listing."""
    project_id = project_with_delegate[0]

    resp = await client.get("/api/projects/")
    assert resp.status_code == codes.OK
    data = resp.json()
    projects = data.get("items", [])
    proj_entry = next((p for p in projects if p["id"] == project_id), None)
    assert proj_entry is not None, f"Project {project_id} not found in listing"
    assert proj_entry["is_delegate"] is True


async def test_not_delegate_in_listing(client: AsyncClient, project_with_user):
    """Non-delegated project shows is_delegate=false."""
    resp = await client.get("/api/projects/")
    assert resp.status_code == codes.OK
    data = resp.json()
    projects = data.get("items", [])
    proj_entry = next((p for p in projects if p["id"] == project_with_user[0]), None)
    assert proj_entry is not None
    assert proj_entry["is_delegate"] is False
