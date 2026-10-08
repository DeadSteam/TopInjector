"""Alembic: migrations build the same schema the models declare."""

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from services.models import Base
from shared.config.settings import Settings

ROOT = Path(__file__).resolve().parent.parent


def _config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture
def sqlite_db(tmp_path):
    path = tmp_path / "migrate.db"
    return f"sqlite+aiosqlite:///{path.as_posix()}", f"sqlite:///{path.as_posix()}"


def test_database_url_env_overrides_components():
    assert Settings(DATABASE_URL="sqlite+aiosqlite:///x.db").database_url == "sqlite+aiosqlite:///x.db"
    assert Settings().database_url.startswith("postgresql+asyncpg://")


def test_upgrade_head_creates_every_model_table(sqlite_db):
    async_url, sync_url = sqlite_db
    command.upgrade(_config(async_url), "head")

    tables = set(inspect(create_engine(sync_url)).get_table_names())
    assert tables == set(Base.metadata.tables) | {"alembic_version"}


def test_migrations_match_models(sqlite_db):
    async_url, sync_url = sqlite_db
    command.upgrade(_config(async_url), "head")

    with create_engine(sync_url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_base_drops_every_table(sqlite_db):
    async_url, sync_url = sqlite_db
    cfg = _config(async_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    assert set(inspect(create_engine(sync_url)).get_table_names()) == {"alembic_version"}


def test_postgres_sql_has_uuid_foreign_keys_and_partial_index():
    buf = io.StringIO()
    with redirect_stdout(buf):
        command.upgrade(_config("postgresql+asyncpg://u:p@localhost/db"), "head", sql=True)
    sql = buf.getvalue()

    assert "user_id UUID NOT NULL" in sql
    assert "FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE" in sql
    assert "CREATE TYPE task_status AS ENUM" in sql
    assert "WHERE status = 'pending'" in sql
