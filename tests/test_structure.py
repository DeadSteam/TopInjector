"""Module layout: one shared base, one place for settings, no duplicate routing."""

import importlib.util


def test_core_package_removed():
    assert importlib.util.find_spec("core") is None


def test_all_models_share_one_declarative_base():
    from services.models import Base as registry_base
    from shared.database.base import Base

    assert registry_base is Base
    assert {"users", "projects", "queries", "queue_tasks"} <= set(Base.metadata.tables)


def test_events_package_exports_bus():
    from shared.events import Event, EventBus, get_bus

    assert isinstance(get_bus(), EventBus)
    assert Event(type="x").payload == {}


def _api_paths() -> set[str]:
    from main import create_app

    return set(create_app().openapi()["paths"])


def test_every_route_lives_under_api_or_health():
    stray = [p for p in _api_paths() if not (p.startswith("/api/") or p == "/health")]
    assert stray == []


def test_auth_routes_have_single_prefix():
    assert {"/api/auth/login", "/api/auth/register", "/api/auth/refresh", "/api/auth/me"} <= _api_paths()


def test_module_routers_mounted_under_their_prefix():
    paths = _api_paths()
    assert "/api/projects/" in paths
    assert "/api/queue/push" in paths
    assert "/api/external/v1/projects" in paths
