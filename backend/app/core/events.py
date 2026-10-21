"""Bus de eventos de dominio.

Los servicios publican un evento DESPUÉS de confirmar (commit) cada cambio. En la etapa de
WebSockets se suscribirá un difusor que reenvía estos eventos a AutoMarket.exe y a la web.

Formato de cada evento:
    {"seq": 42, "type": "vehicle.updated", "data": {...}, "occurred_at": "2026-10-19T22:00:00+00:00"}

`seq` crece de uno en uno mientras el servidor esté encendido: si un cliente ve un salto, perdió
eventos y debe recargar los datos por REST.
"""
import itertools
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone

log = logging.getLogger("automarket.events")

Subscriber = Callable[[dict], None]
_subscribers: list[Subscriber] = []
_seq = itertools.count(1)
_seq_lock = threading.Lock()


def subscribe(callback: Subscriber) -> None:
    _subscribers.append(callback)


def unsubscribe(callback: Subscriber) -> None:
    if callback in _subscribers:
        _subscribers.remove(callback)


def publish(event_type: str, data: dict) -> None:
    with _seq_lock:
        seq = next(_seq)
    event = {"seq": seq, "type": event_type, "data": data, "occurred_at": datetime.now(timezone.utc).isoformat()}
    log.info("evento %s %s", event_type, data.get("id", ""))
    for callback in list(_subscribers):
        try:
            callback(event)
        except Exception:  # un suscriptor con error no debe romper la operación
            log.exception("Error en suscriptor de eventos")
