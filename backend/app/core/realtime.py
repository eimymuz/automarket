"""Difusión de eventos de dominio a los clientes conectados por WebSocket.

Los servicios se ejecutan en hilos del threadpool de FastAPI; los WebSockets viven en el event loop.
`_on_event` (llamado desde cualquier hilo) programa el envío en el loop con run_coroutine_threadsafe.

Visibilidad:
  - vehicle.*                      -> todos (también visitantes sin sesión)
  - reservation.*, order.*, sale.* -> administradores y el cliente dueño (data.user_id)

Nota de despliegue: el difusor vive en memoria del proceso, por eso el servidor se ejecuta con
UN worker de uvicorn. Para varios workers se usaría PostgreSQL LISTEN/NOTIFY o Redis.
"""
import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.core import events

log = logging.getLogger("automarket.realtime")
PUBLIC_PREFIXES = ("vehicle.",)


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    user_id: str | None
    role: str  # admin | cliente | anonimo
    client_app: str | None = None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=500))


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[Connection] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    # ---------- ciclo de vida ----------
    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        events.subscribe(self._on_event)

    def stop(self) -> None:
        events.unsubscribe(self._on_event)
        self.loop = None

    def register(self, conn: Connection) -> None:
        self.connections.add(conn)
        log.info("WS conectado (%s, %s). Total: %d", conn.role, conn.client_app, len(self.connections))

    def unregister(self, conn: Connection) -> None:
        self.connections.discard(conn)
        log.info("WS desconectado (%s). Total: %d", conn.role, len(self.connections))

    def stats(self) -> dict:
        by_role: dict[str, int] = {}
        for c in self.connections:
            by_role[c.role] = by_role.get(c.role, 0) + 1
        return {"total": len(self.connections), "by_role": by_role}

    # ---------- difusión ----------
    @staticmethod
    def can_see(conn: Connection, event: dict) -> bool:
        if event["type"].startswith(PUBLIC_PREFIXES):
            return True
        return conn.role == "admin" or (conn.user_id is not None and event["data"].get("user_id") == conn.user_id)

    def _on_event(self, event: dict) -> None:
        if self.loop is None or self.loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._enqueue(event), self.loop)

    async def _enqueue(self, event: dict) -> None:
        for conn in list(self.connections):
            if self.can_see(conn, event):
                try:
                    conn.queue.put_nowait(event)
                except asyncio.QueueFull:  # cliente que no lee: se desconecta para no acumular memoria
                    log.warning("Cola llena; se cierra la conexión de %s", conn.role)
                    asyncio.create_task(conn.websocket.close(code=1013))


manager = ConnectionManager()
