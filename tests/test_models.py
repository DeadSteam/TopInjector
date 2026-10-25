"""ORM schema: key types line up, constraints behave, tables build on a fresh DB."""

from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from services.models import Base, Project, Query, QueueTask, User


def _python_type(column) -> type:
    return column.type.python_type


def test_foreign_key_types_match_referenced_primary_keys():
    mismatches = [
        f"{fk.parent.table.name}.{fk.parent.name} -> {fk.column.table.name}.{fk.column.name}"
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
        if _python_type(fk.parent) is not _python_type(fk.column)
    ]
    assert mismatches == []


def test_project_user_id_is_uuid():
    assert _python_type(Project.__table__.c.user_id) is UUID


async def _user(session, email="owner@example.com") -> User:
    user = User(email=email, password_hash="x")
    session.add(user)
    await session.flush()
    return user


async def _project(session, user, domain="example.com") -> Project:
    project = Project(user_id=user.id, name="Site", domain=domain)
    session.add(project)
    await session.flush()
    return project


async def test_project_defaults(session):
    project = await _project(session, await _user(session))
    assert project.daily_limit == 500
    assert project.strategy_type == "daily"
    assert project.is_active is True


async def test_same_domain_allowed_for_different_users(session):
    await _project(session, await _user(session, "a@example.com"))
    await _project(session, await _user(session, "b@example.com"))
    await session.commit()


async def test_same_domain_allowed_for_same_user(session):
    """Several campaigns may target one domain (e.g. a copied project)."""
    user = await _user(session)
    await _project(session, user)
    await _project(session, user)
    assert len((await session.execute(select(Project))).scalars().all()) == 2


async def test_deleting_user_cascades_to_projects_and_queries(session):
    user = await _user(session)
    project = await _project(session, user)
    session.add(Query(project_id=project.id, text="buy shoes"))
    await session.commit()

    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()

    assert (await session.execute(select(Project))).scalars().all() == []
    assert (await session.execute(select(Query))).scalars().all() == []


async def test_queue_task_gets_uuid_and_timestamps(session):
    project = await _project(session, await _user(session))
    task = QueueTask(project_id=project.id, click_url="https://example.com/a")
    session.add(task)
    await session.flush()
    await session.refresh(task)

    assert isinstance(task.id, UUID)
    assert task.created_at is not None
    assert task.status == "pending"


async def test_completed_tasks_may_repeat_same_url(session):
    project = await _project(session, await _user(session))
    for _ in range(2):
        session.add(QueueTask(project_id=project.id, click_url="https://example.com/a", status="completed"))
    await session.commit()


async def test_second_pending_task_for_same_url_rejected(session):
    project = await _project(session, await _user(session))
    session.add(QueueTask(project_id=project.id, click_url="https://example.com/a"))
    await session.flush()
    session.add(QueueTask(project_id=project.id, click_url="https://example.com/a"))
    with pytest.raises(IntegrityError):
        await session.flush()
