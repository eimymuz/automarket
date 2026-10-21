"""Bitácora de operaciones de negocio (lo que se muestra en el "Historial" de AutoMarket.exe)."""
import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy.orm import Session

from app.models import OperationHistory
from app.models.enums import OperationSource


def _jsonable(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def record(
    db: Session, *, operation: str, source: OperationSource, actor_id: uuid.UUID | None,
    vehicle_id: uuid.UUID | None = None, from_status=None, to_status=None, details: dict | None = None,
) -> None:
    db.add(OperationHistory(
        vehicle_id=vehicle_id, actor_user_id=actor_id, operation=operation, source=source,
        from_status=_jsonable(from_status), to_status=_jsonable(to_status),
        details=_jsonable(details) if details else None,
    ))
