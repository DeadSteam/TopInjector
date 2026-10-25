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


def test_timestamp_columns_have_server_defaults(sqlite_db):
    """Models rely on the database filling created_at/updated_at; app tests build tables from the
    models, so only the migrated schema shows a missing default (inserts fail on Postgres)."""
    async_url, sync_url = sqlite_db
    command.upgrade(_config(async_url), "head")

    insp = inspect(create_engine(sync_url))
    missing = [
        f"{table}.{col['name']}"
        for table in insp.get_table_names()
        for col in insp.get_columns(table)
        if col["name"] in ("created_at", "updated_at") and col.get("default") is None
    ]
    assert missing == []


def test_revision_ids_fit_alembic_version_column():
    """Postgres stores revision ids in alembic_version.version_num VARCHAR(32); SQLite doesn't check."""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_config("sqlite://"))
    assert [r.revision for r in script.walk_revisions() if len(r.revision) > 32] == []


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
