"""Unit tests for ProjectRepository, QueryRepository, and QueueTaskRepository."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from services.auth_service.domain.models import User
from services.project_service.domain.models import Project, ProjectToken, Query
from services.project_service.repositories.project_repo import ProjectRepository
from services.project_service.repositories.query_repo import QueryRepository
from services.queue_service.domain.models import QueueTask
from services.queue_service.repositories.task_repo import QueueTaskRepository


# ── Fixtures ───────────────────────────────────────────────────────────────────


async def _user(session) -> User:
    user = User(email="repo-test@example.com", password_hash="x", display_name="RepoTester")
    session.add(user)
    await session.flush()
    return user


async def _project(session, user, domain="repotest.example.com") -> Project:
    p = Project(user_id=user.id, name="Repo Test", domain=domain)
    session.add(p)
    await session.flush()
    return p


# ── ProjectRepository tests ───────────────────────────────────────────────────


async def test_repo_create_and_get_by_id(session):
    user = await _user(session)
    project = await _project(session, user)
    repo = ProjectRepository(session)

    found = await repo.get_by_id(project.id)
    assert found is not None
    assert found.id == project.id
    assert found.domain == "repotest.example.com"


async def test_repo_get_by_id_not_found(session):
    repo = ProjectRepository(session)
    found = await repo.get_by_id(uuid4())
    assert found is None


async def test_repo_get_all_for_user(session):
    user = await _user(session)
    p1 = await _project(session, user, "alpha.example.com")
    p2 = await _project(session, user, "beta.example.com")

    repo = ProjectRepository(session)
    projects = await repo.get_all_for_user(user.id)

    ids = {p.id for p in projects}
    assert p1.id in ids
    assert p2.id in ids


async def test_repo_create_and_delete(session):
    user = await _user(session)
    project = await _project(session, user)
    repo = ProjectRepository(session)

    new_project = Project(user_id=user.id, name="New", domain="new.example.com")
    created = await repo.create(new_project)
    assert created.id is not None

    await repo.delete(created)
    fetched = await repo.get_by_id(created.id)
    assert fetched is None


async def test_repo_delete_cascades_to_queries(session):
    user = await _user(session)
    project = await _project(session, user)

    q = Query(project_id=project.id, text="test query", url="https://example.com")
    session.add(q)
    await session.commit()

    repo = ProjectRepository(session)
    await repo.delete(project)
    await session.commit()

    remaining = await session.execute(select(Query).where(Query.project_id == project.id))
    assert remaining.scalars().first() is None


async def test_project_repo_get_by_id_after_delete(session):
    user = await _user(session)
    project = await _project(session, user)
    repo = ProjectRepository(session)

    await session.delete(project)
    await session.commit()

    assert await repo.get_by_id(project.id) is None


# ── QueryRepository tests ─────────────────────────────────────────────────────


async def test_repo_create_query(session):
    user = await _user(session)
    project = await _project(session, user)
    query = Query(
        project_id=project.id,
        text="buy shoes online",
        url="https://example.com/shoes",
        click_url="https://google.com/search?q=shoes",
        daily_clicks=10,
        position=3,
    )
    repo = QueryRepository(session)
    await repo.create(query)

    result = await repo.get_by_project(project.id)
    assert len(result) == 1
    assert result[0].text == "buy shoes online"


async def test_repo_get_by_project_empty(session):
    user = await _user(session)
    project = await _project(session, user)
    repo = QueryRepository(session)

    result = await repo.get_by_project(project.id)
    assert result == []


async def test_repo_delete_all_for_project(session):
    user = await _user(session)
    project = await _project(session, user)

    q1 = Query(project_id=project.id, text="query 1", url="https://example.com/1")
    q2 = Query(project_id=project.id, text="query 2", url="https://example.com/2")
    session.add_all([q1, q2])
    await session.flush()

    repo = QueryRepository(session)
    deleted = await repo.delete_all_for_project(project.id)
    assert deleted == 2

    remaining = await repo.get_by_project(project.id)
    assert remaining == []


async def test_repo_create_query_with_geo_targeting(session):
    user = await _user(session)
    project = await _project(session, user)

    q = Query(
        project_id=project.id,
        text="geo query",
        url="https://example.com/geo",
        daily_clicks=20,
        geo={"country": "RU"},
        frequency=5,
    )
    repo = QueryRepository(session)
    await repo.create(q)

    result = await repo.get_by_project(project.id)
    assert len(result) == 1
    assert result[0].geo.get("country") == "RU"


async def test_repo_multiple_queries_per_project(session):
    user = await _user(session)
    project = await _project(session, user)

    queries = [
        Query(project_id=project.id, text=f"query {i}", url=f"https://example.com/{i}", click_url=f"https://google.com?q={i}")
        for i in range(5)
    ]
    repo = QueryRepository(session)
    for q in queries:
        await repo.create(q)

    result = await repo.get_by_project(project.id)
    assert len(result) == 5


# ── QueueTaskRepository tests ────────────────────────────────────────────────


async def test_repo_get_all(session):
    user = await _user(session)
    project = await _project(session, user)

    t1 = QueueTask(project_id=project.id, click_url="https://example.com/1", source="strategy")
    t2 = QueueTask(project_id=project.id, click_url="https://example.com/2", source="autoburst")
    session.add_all([t1, t2])
    await session.flush()

    repo = QueueTaskRepository(session)
    tasks = await repo.get_all()
    assert len(tasks) >= 2


async def test_repo_get_pending_for_project(session):
    user = await _user(session)
    project = await _project(session, user)

    pending1 = QueueTask(project_id=project.id, click_url="https://example.com/1", source="strategy")
    pending2 = QueueTask(project_id=project.id, click_url="https://example.com/2", source="proklik")
    running = QueueTask(
        project_id=project.id, click_url="https://example.com/3", status="in_progress"
    )
    session.add_all([pending1, pending2, running])
    await session.flush()

    repo = QueueTaskRepository(session)
    pending = await repo.get_pending_for_project(project.id)

    ids = {t.id for t in pending}
    assert pending1.id in ids
    assert pending2.id in ids
    assert running.id not in ids


async def test_repo_update_status(session):
    user = await _user(session)
    project = await _project(session, user)

    task = QueueTask(project_id=project.id, click_url="https://example.com", source="strategy")
    session.add(task)
    await session.flush()

    repo = QueueTaskRepository(session)
    result = await repo.update_status(task.id, "completed")
    assert result is True

    fetch_result = await session.execute(select(QueueTask).where(QueueTask.id == task.id))
    updated_task = fetch_result.scalars().first()
    assert updated_task.status == "completed"


async def test_repo_update_status_stuck(session):
    user = await _user(session)
    project = await _project(session, user)

    task = QueueTask(project_id=project.id, click_url="https://example.com", source="proklik")
    session.add(task)
    await session.flush()

    repo = QueueTaskRepository(session)
    await repo.update_status(task.id, "in_progress")
    await repo.update_status(task.id, "stuck")

    fetch_result = await session.execute(select(QueueTask).where(QueueTask.id == task.id))
    updated_task = fetch_result.scalars().first()
    assert updated_task.status == "stuck"


async def test_repo_update_status_completed_blocked(session):
    """Once completed, status cannot change."""
    user = await _user(session)
    project = await _project(session, user)

    task = QueueTask(project_id=project.id, click_url="https://example.com", source="strategy")
    session.add(task)
    await session.flush()

    repo = QueueTaskRepository(session)
    await repo.update_status(task.id, "completed")
    result = await repo.update_status(task.id, "in_progress")
    assert result is False


async def test_repo_clear_for_project(session):
    user = await _user(session)
    project = await _project(session, user)

    t1 = QueueTask(project_id=project.id, click_url="https://example.com/1", source="strategy")
    t2 = QueueTask(project_id=project.id, click_url="https://example.com/2", source="autoburst")
    session.add_all([t1, t2])
    await session.flush()

    repo = QueueTaskRepository(session)
    cleared = await repo.clear_for_project(project.id)
    assert cleared == 2

    pending = await repo.get_pending_for_project(project.id)
    assert pending == []


async def test_repo_task_url_uniqueness_and_reuse(session):
    """Two pending tasks with same click_url within a project is rejected; once one finishes, another can reuse the URL."""
    user = await _user(session)
    project = await _project(session, user)

    # Create first task and commit immediately so it survives rollback
    t1 = QueueTask(project_id=project.id, click_url="https://example.com/page", source="strategy")
    session.add(t1)
    await session.flush()
    proj_id = project.id
    task_id = t1.id  # Capture IDs before commit (objects expire after)
    await session.commit()

    repo = QueueTaskRepository(session)

    # Duplicate pending should raise IntegrityError
    t2 = QueueTask(project_id=proj_id, click_url="https://example.com/page", source="autoburst")
    session.add(t2)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
    else:
        pytest.fail("Should have raised IntegrityError for duplicate pending URL")

    # Complete first task
    ok = await repo.update_status(task_id, "completed")
    assert ok is True
    await session.commit()

    # Now a new task with same URL should succeed
    t3 = QueueTask(project_id=proj_id, click_url="https://example.com/page", source="strategy")
    session.add(t3)
    await session.flush()


async def test_repo_pending_url_unique(session):
    """Only one pending task per URL per project."""
    user = await _user(session)
    project = await _project(session, user)

    t1 = QueueTask(project_id=project.id, click_url="https://example.com/page", source="strategy")
    session.add(t1)
    await session.flush()

    t2 = QueueTask(project_id=project.id, click_url="https://example.com/page", source="autoburst")
    session.add(t2)
    try:
        await session.flush()
    except IntegrityError:
        pass  # expected
    else:
        pytest.fail("Should have raised IntegrityError for duplicate pending URL")


async def test_completed_tasks_same_url_allowed(session):
    """Finished tasks may repeat the same URL."""
    user = await _user(session)
    project = await _project(session, user)

    t1 = QueueTask(project_id=project.id, click_url="https://example.com/page", source="strategy", status="completed")
    t2 = QueueTask(project_id=project.id, click_url="https://example.com/page", source="autoburst", status="completed")
    session.add_all([t1, t2])
    await session.commit()  # Should not raise


async def test_repo_get_all_filtered_status(session):
    user = await _user(session)
    project = await _project(session, user)

    pending_task = QueueTask(project_id=project.id, click_url="https://example.com/pending", source="strategy")
    completed_task = QueueTask(
        project_id=project.id, click_url="https://example.com/done", source="proklik", status="completed"
    )
    session.add_all([pending_task, completed_task])
    await session.flush()

    repo = QueueTaskRepository(session)
    all_tasks = await repo.get_all()
    assert len(all_tasks) >= 2


# ── ProjectToken repository tests ─────────────────────────────────────────────


async def test_repo_create_project_token(session):
    user = await _user(session)
    project = await _project(session, user)

    token = ProjectToken(
        user_id=user.id,
        project_id=project.id,
        name="Test Token",
        token_string="tk_test_01234567890abcdef",
    )
    session.add(token)
    await session.flush()

    result = await session.execute(
        select(ProjectToken).where(ProjectToken.token_string == "tk_test_01234567890abcdef")
    )
    found = result.scalars().first()
    assert found is not None
    assert found.name == "Test Token"


async def test_project_token_unique_constraint(session):
    user = await _user(session)
    project = await _project(session, user)

    t1 = ProjectToken(
        user_id=user.id,
        project_id=project.id,
        name="Token 1",
        token_string="tk_duplicate_abc123def",
    )
    session.add(t1)
    await session.flush()

    t2 = ProjectToken(
        user_id=user.id,
        project_id=project.id,
        name="Token 2",
        token_string="tk_duplicate_abc123def",
    )
    session.add(t2)
    with pytest.raises(IntegrityError):
        await session.flush()


# ── Repository cascade: project delete cleans tasks ───────────────────────────


async def test_project_delete_cascades_to_queue_tasks(session):
    user = await _user(session)
    project = await _project(session, user)

    t1 = QueueTask(project_id=project.id, click_url="https://example.com/1", source="strategy")
    t2 = QueueTask(project_id=project.id, click_url="https://example.com/2", source="autoburst")
    session.add_all([t1, t2])
    await session.commit()

    repo = ProjectRepository(session)
    await repo.delete(project)
    await session.commit()

    remaining = await session.execute(select(QueueTask).where(QueueTask.project_id == project.id))  # type: ignore[name-defined]
    assert remaining.scalars().first() is None


async def test_project_delete_cascades_to_queries(session):
    user = await _user(session)
    project = await _project(session, user)

    q1 = Query(project_id=project.id, text="cascade query 1", url="https://example.com/1")
    q2 = Query(project_id=project.id, text="cascade query 2", url="https://example.com/2")
    session.add_all([q1, q2])
    await session.commit()

    repo = ProjectRepository(session)
    await repo.delete(project)
    await session.commit()

    remaining = await session.execute(select(Query).where(Query.project_id == project.id))
    assert remaining.scalars().first() is None


# ── Query daily_clicks constraint test ────────────────────────────────────────


async def test_query_requires_project_id(session):
    """Query cannot exist without a valid project."""
    repo = QueryRepository(session)
    q = Query(text="orphan", url="https://example.com", click_url="https://google.com")
    with pytest.raises(IntegrityError):
        await repo.create(q)
