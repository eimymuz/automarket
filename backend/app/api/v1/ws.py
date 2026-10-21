"""WebSocket de notificaciones en tiempo real.

    ws://<servidor>:8000/api/v1/ws?token=<JWT>&client=web

- `token` es opcional: sin él solo se reciben eventos públicos del inventario (vehicle.*).
- Mensajes del servidor: {"seq", "type", "data", "occurred_at"}. Al conectar: {"type": "connection.ready"}.
- El cliente puede enviar el texto "ping" y recibirá {"type": "pong"} (mantener viva la conexión).
- Códigos de cierre: 4401 token inválido, 4403 origen no permitido, 1013 cliente demasiado lento.
"""
import asyncio
import uuid
from collections.abc import Callable

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.realtime import Connection, manager
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import User

router = APIRouter(tags=["Tiempo real"])
# Orígenes de AutoMarket.exe empaquetado (archivo local); los navegadores deben estar en CORS_ORIGINS
DESKTOP_ORIGINS = {"file://", "null"}


def _lookup_user(user_id: uuid.UUID) -> tuple[str, str] | None:
    # Sesión corta: una conexión WebSocket puede durar horas y no debe retener una conexión a la BD
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return (str(user.id), user.role.name) if user and user.is_active else None


def get_user_lookup() -> Callable[[uuid.UUID], tuple[str, str] | None]:
    return _lookup_user


def _authenticate(token: str, lookup) -> tuple[str, str] | None:
    try:
        user_id = uuid.UUID(decode_access_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return lookup(user_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None, client: str | None = None,
                             lookup=Depends(get_user_lookup)):
    origin = websocket.headers.get("origin")
    if origin and origin not in get_settings().cors_origin_list and origin not in DESKTOP_ORIGINS:
        await websocket.close(code=4403)
        return

    user_id, role = None, "anonimo"
    if token:
        identity = await asyncio.to_thread(_authenticate, token, lookup)
        if identity is None:
            await websocket.close(code=4401)
            return
        user_id, role = identity

    await websocket.accept()
    conn = Connection(websocket=websocket, user_id=user_id, role=role, client_app=client)
    manager.register(conn)
    await websocket.send_json({"type": "connection.ready", "data": {"role": role, "user_id": user_id}})

    async def sender():
        while True:
            await websocket.send_json(await conn.queue.get())

    async def receiver():
        while True:
            if (await websocket.receive_text()).strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})

    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        manager.unregister(conn)


@router.get("/ws/stats")
def websocket_stats():
    """Clientes conectados en este momento, por rol (diagnóstico)."""
    return manager.stats()
