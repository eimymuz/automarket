"""Historial de operaciones (negocio) y auditoría (técnica, llenada por triggers)."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OperationSource, pg_enum


class OperationHistory(Base):
    """Eventos de negocio legibles: reserva creada, precio actualizado, venta confirmada..."""

    __tablename__ = "operation_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(50), index=True)
    source: Mapped[OperationSource] = mapped_column(pg_enum(OperationSource, "operation_source"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AuditLog(Base):
    """Cada INSERT/UPDATE/DELETE en tablas críticas, con la fila antes y después."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(63), index=True)
    record_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(10))  # INSERT | UPDATE | DELETE
    old_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    changed_by: Mapped[str | None] = mapped_column(String(64))  # id del usuario de la app
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
