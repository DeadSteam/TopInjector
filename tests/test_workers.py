"""Integration tests for Celery workers: scheduler, stale_checker, daily_billing."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select


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


# -- Stale checker worker tests ----------------------------------------------- #


async def test_mark_stale_tasks_flags_only_long_running(daily_project, app_fixture):
    """In-progress tasks untouched for 30+ minutes become stuck; fresh and finished ones don't."""
    from services.queue_service.domain.models import QueueTask
    from workers.stale_checker import mark_stale_tasks

    project_id, _ = daily_project
    long_ago = datetime.now(timezone.utc) - timedelta(minutes=35)
    recently = datetime.now(timezone.utc) - timedelta(minutes=5)
    specs = {"stale": ("in_progress", long_ago), "fresh": ("in_progress", recently), "done": ("completed", long_ago)}

    ids = {}
    async with app_fixture.state.session_factory() as session:
        for name, (status, touched) in specs.items():
            task = QueueTask(
                project_id=UUID(project_id), click_url=f"https://example.com/{name}",
                status=status, created_at=touched, updated_at=touched,
            )
            session.add(task)
            await session.flush()
            ids[name] = task.id
        await session.commit()

    async with app_fixture.state.session_factory() as session:
        assert await mark_stale_tasks(session) == 1

    async with app_fixture.state.session_factory() as session:
        rows = dict((await session.execute(select(QueueTask.id, QueueTask.status))).all())
    assert (rows[ids["stale"]], rows[ids["fresh"]], rows[ids["done"]]) == ("stuck", "in_progress", "completed")


# -- Daily billing admin skip tests ------------------------------------------- #


async def test_daily_billing_skips_admin_users(app_fixture):
    """Admin users should be skipped by the daily billing cycle."""
    from services.auth_service.domain.models import User, Plan
    from services.project_service.domain.models import Project, UserPlan
    from workers.daily_billing import daily_billing

    async with app_fixture.state.session_factory() as session:
        # Create admin user.
        admin_user = User(email="admin-billing@example.com", password_hash="x", display_name="AdminBill", is_admin=True)
        session.add(admin_user)
        await session.flush()

        # Create a normal user.
        normal_user = User(email="normal-billing@example.com", password_hash="x", display_name="NormalBill")
        session.add(normal_user)
        await session.flush()

        project_admin = Project(
            id=uuid4(), user_id=admin_user.id, name="AdminProj", domain="admin.example.com", is_active=True,
        )
        session.add(project_admin)

        project_normal = Project(
            id=uuid4(), user_id=normal_user.id, name="NormalProj", domain="normal.example.com", is_active=True,
        )
        session.add(project_normal)
        await session.commit()

    # Run billing cycle.
    result = await daily_billing(app_fixture.state.session_factory())

    assert result["skipped"] >= 1  # admin should be skipped