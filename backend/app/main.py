"""Punto de entrada de la API AutoMarket."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.api.v1.router import api_router
from app.core.config import INSECURE_SECRET, get_settings
from app.core.errors import register_error_handlers
from app.core.realtime import manager
from app.db.session import SessionLocal
from app.services.commerce import expire_reservations

settings = get_settings()
log = logging.getLogger("automarket")

if settings.environment == "production" and settings.jwt_secret == INSECURE_SECRET:
    raise RuntimeError("Configura JWT_SECRET en backend/.env antes de ejecutar en producción")


def _expire_once() -> int:
    with SessionLocal() as db:
        return expire_reservations(db)


async def _expiration_loop() -> None:
    """Vence reservas aunque nadie esté usando la API en ese momento."""
    while True:
        try:
            count = await run_in_threadpool(_expire_once)
            if count:
                log.info("Reservas vencidas: %d", count)
        except Exception:
            log.exception("Error al vencer reservas")
        await asyncio.sleep(settings.expiration_check_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    manager.start(asyncio.get_running_loop())
    task = asyncio.create_task(_expiration_loop())
    yield
    task.cancel()
    manager.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API central compartida por **AutoMarket.exe** (administradores) y la **página web** (clientes).\n\n"
        "1. Obtén un token en `POST /api/v1/auth/login`.\n"
        "2. Pulsa **Authorize** y pégalo para probar los endpoints protegidos.\n\n"
        "Los errores tienen siempre el formato `{\"detail\": \"...\", \"code\": \"...\"}`."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Client-App"],
)
register_error_handlers(app)

settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
app.include_router(api_router, prefix="/api/v1")
