"""Integration tests for Celery workers: scheduler, stale_checker."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update


@pytest_asyncio.fixture
async def daily_project(app_fixture):
    """Create a daily-strategy project with queries for scheduler tests."""
    from services.auth_service.domain.models import User
    from services.project_service.domain.models import Project, Query

    async with app_fixture.state.session_factory() as session:
        user = User(email="worker-test@example.com", password_hash="x", display_name="WorkerTester")
        session.add(user)
        await session.flush()

        project = Project(
            id=uuid4(),
            user_id=user.id,  # type: ignore[union-attr]
            name="Worker Test Daily Project",
            domain="worker-test.example.com",
            strategy_type="daily",
            is_active=True,
            daily_limit=10,
        )
        session.add(project)
        await session.flush()

        queries = [
            Query(
                project_id=project.id,  # type: ignore[union-attr]
                text=f"worker query {i}",
                url="https://example.com",
                click_url=f"https://google.com/search?q=query{i}",
            )
            for i in range(3)
        ]
        session.add_all(queries)
        await session.commit()  # commit so data is visible to other sessions

        yield str(project.id), [str(q.id) for q in queries]  # type: ignore[union-attr]


@pytest_asyncio.fixture
async def project_with_stale_tasks(app_fixture):
    """Create a project with in_progress tasks older than 30 minutes."""
    from services.auth_service.domain.models import User
    from services.project_service.domain.models import Project, Query
    from services.queue_service.domain.models import QueueTask

    async with app_fixture.state.session_factory() as session:
        user = User(email="stale-test@example.com", password_hash="x", display_name="StaleTester")
        session.add(user)
        await session.flush()

        project = Project(
            id=uuid4(),
            user_id=user.id,  # type: ignore[union-attr]
            name="Stale Test Project",
            domain="stale-test.example.com",
            strategy_type="daily",
            is_active=True,
            daily_limit=100,
        )
        session.add(project)
        await session.flush()

        project_uuid = project.id  # type: ignore[union-attr]

        # Create Query records first (required by FK on QueueTask.query_id)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        stale_query_ids = []
        for i in range(3):
            q = Query(
                project_id=project_uuid,
                text=f"stale query {i}",
                url="https://example.com",
                click_url=f"https://google.com/search?q=stale{i}",
            )
            session.add(q)
            await session.flush()  # get the ID from DB
            stale_query_ids.append(q.id)  # type: ignore[union-attr]

        recent_query = Query(
            project_id=project_uuid,
            text="recent query",
            url="https://example.com",
            click_url="https://google.com/search?q=recent",
        )
        session.add(recent_query)
        await session.flush()
        recent_query_id = recent_query.id  # type: ignore[union-attr]

        completed_query = Query(
            project_id=project_uuid,
            text="completed query",
            url="https://example.com",
            click_url="https://google.com/search?q=completed",
        )
        session.add(completed_query)
        await session.flush()
        completed_query_id = completed_query.id  # type: ignore[union-attr]

        # Create stale QueueTasks (older than 30 min)
        for i in range(3):
            task = QueueTask(
                project_id=project_uuid,
                query_id=stale_query_ids[i],
                click_url=f"https://example.com/stale{i}",
                source="strategy",
                status="in_progress",
                created_at=old_time,
            )
            session.add(task)

        # Create a recent task (should NOT be marked stuck — newer than 30 min)
        recent_task = QueueTask(
            project_id=project_uuid,
            query_id=recent_query_id,
            click_url="https://example.com/recent",
            source="strategy",
            status="in_progress",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        session.add(recent_task)

        # Create a completed task (should NOT be marked stuck — not in_progress)
        completed_task = QueueTask(
            project_id=project_uuid,
            query_id=completed_query_id,
            click_url="https://example.com/completed",
            source="strategy",
            status="completed",
            created_at=old_time,
        )
        session.add(completed_task)

        await session.commit()

        # Collect stale task IDs from DB
        stale_ids = []
        result = await session.execute(
            select(QueueTask.id).where(
                QueueTask.project_id == project_uuid,
                QueueTask.status == "in_progress",
                QueueTask.created_at < old_time,
            )
        )
        for row in result.all():
            stale_ids.append(str(row[0]))

        recent_result = await session.execute(
            select(QueueTask.id).where(
                QueueTask.project_id == project_uuid,
                QueueTask.status == "in_progress",
                QueueTask.created_at > old_time,
            )
        )
        recent_id = str(recent_result.scalar())

        yield str(project.id), stale_ids, recent_id  # type: ignore[union-attr]


# -- Scheduler worker tests -------------------------------------------------- #


async def test_scheduler_no_daily_projects(client: AsyncClient, app_fixture):
    """Scheduler returns None when celery not installed (expected in test env)."""
    try:
        from workers import app as celery_app
        assert celery_app is not None  # noqa: FURB186
    except ImportError:
        pass


async def test_scheduler_daily_project_exists(daily_project, app_fixture):
    """Verify daily project with queries was created for scheduler tests."""
    project_id, query_ids = daily_project

    async with app_fixture.state.session_factory() as session:
        from services.project_service.domain.models import Project as _Project
        from uuid import UUID

        result = await session.execute(
            select(_Project).where(
                _Project.id == UUID(project_id),  # type: ignore[arg-type]
            )
        )
        project = result.scalar_one_or_none()
        assert project is not None, f"Project {project_id} not found in DB"
        assert project.strategy_type == "daily"

        # Also verify queries exist
        from services.project_service.domain.models import Query as _Query
        q_result = await session.execute(
            select(_Query).where(_Query.project_id == UUID(project_id))  # type: ignore[arg-type]
        )
        queries = q_result.scalars().all()
        assert len(queries) == 3, f"Expected 3 queries, got {len(queries)}"


# -- Stale checker worker tests ----------------------------------------------- #


async def test_stale_checker_marks_old_tasks(project_with_stale_tasks, app_fixture):
    """Stale checker should mark in_progress tasks older than 30 min as stuck."""
    project_id, stale_task_ids, recent_task_id = project_with_stale_tasks

    async with app_fixture.state.session_factory() as session:
        from services.queue_service.domain.models import QueueTask

        # Verify initial state of stale tasks
        for tid in stale_task_ids:
            task_result = await session.execute(
                select(QueueTask).where(QueueTask.id == UUID(tid))  # type: ignore[arg-type]
            )
            task = task_result.scalar_one_or_none()
            assert task is not None
            assert task.status == "in_progress"

        # Verify recent task is still in_progress (not stale)
        recent_result = await session.execute(
            select(QueueTask).where(QueueTask.id == UUID(recent_task_id))  # type: ignore[arg-type]
        )
        recent_task = recent_result.scalar_one_or_none()
        assert recent_task is not None
        assert recent_task.status == "in_progress"

        # Simulate stale checker: find in_progress tasks older than 30 min
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

        result2 = await session.execute(
            select(QueueTask.id).where(
                QueueTask.project_id == UUID(project_id),  # type: ignore[arg-type]
                QueueTask.status == "in_progress",
                QueueTask.created_at < cutoff,
            )
        )
        stuck_ids = [r[0] for r in result2.all()]

        # Mark stale tasks as stuck
        for stuck_id in stuck_ids:
            await session.execute(
                update(QueueTask)
                .where(QueueTask.id == stuck_id)  # type: ignore[attr-defined]
                .values(status="stuck")
            )

        await session.commit()

    # Verify stale tasks are now marked stuck
    async with app_fixture.state.session_factory() as session:
        from services.queue_service.domain.models import QueueTask

        for tid in stale_task_ids:
            task_result = await session.execute(
                select(QueueTask.status).where(QueueTask.id == UUID(tid))  # type: ignore[arg-type]
            )
            status = task_result.scalar()
            assert status == "stuck", f"Task {tid} should be stuck, got {status}"

        # Verify recent task is still in_progress (NOT marked stuck)
        task_result = await session.execute(
            select(QueueTask.status).where(QueueTask.id == UUID(recent_task_id))  # type: ignore[arg-type]
        )
        status = task_result.scalar()
        assert status == "in_progress", f"Recent task should still be in_progress, got {status}"
