"""Endpoint de salud: confirma que la API responde y si PostgreSQL es accesible."""
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    try:
        with engine.connect() as conn:
            db_version = conn.execute(text("SELECT version()")).scalar_one()
        database = {"status": "ok", "version": db_version.split(",")[0]}
    except Exception as exc:  # noqa: BLE001 - se reporta el error, no se propaga
        database = {"status": "error", "detail": type(exc).__name__}

    return {
        "api": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": database,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
