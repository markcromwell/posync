import importlib
import pkgutil

from fastapi import FastAPI

from app.config import settings
from app.health import router as health_router


def create_app() -> FastAPI:
    # App factory. /health is always wired; EVERY router under app/routers/ is auto-included so the
    # boot-smoke import exercises the whole app graph — this is what catches missing deps (jinja2 /
    # python-multipart) before deploy. Drop a new app/routers/<name>.py exposing `router` and it's live.
    application = FastAPI(title=settings.app_name, version=settings.version)
    application.include_router(health_router)
    import app.routers as routers_pkg
    for mod in pkgutil.iter_modules(routers_pkg.__path__):
        module = importlib.import_module(f"app.routers.{mod.name}")
        router = getattr(module, "router", None)
        if router is not None:
            application.include_router(router)
    _init_db_if_present()
    return application


def _init_db_if_present() -> None:
    # SQLite default → create tables at startup. Postgres → schema is owned by Alembic (applied at
    # deploy/CI), so we do NOT create_all there. No-op when the +db module isn't installed.
    try:
        from app.db import init_sqlite_schema
    except ImportError:
        return
    init_sqlite_schema()
