"""Reservas, órdenes de compra, pagos simulados y ventas."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import (
    OrderStatus, PaymentMethod, PaymentStatus, ReservationStatus, pg_enum,
)
from app.models.user import User
from app.models.vehicle import Vehicle


class Reservation(TimestampMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        # La BD garantiza que un vehículo no tenga dos reservas activas a la vez
        Index(
            "uq_reservations_one_active_per_vehicle", "vehicle_id",
            unique=True, postgresql_where=text("status = 'activa'"),
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        pg_enum(ReservationStatus, "reservation_status"),
        default=ReservationStatus.ACTIVA,
        server_default=ReservationStatus.ACTIVA.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(300))

    vehicle: Mapped[Vehicle] = relationship()
    user: Mapped[User] = relationship()


class PurchaseOrder(TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        # Un vehículo solo puede tener una orden "viva" (no cancelada)
        Index(
            "uq_purchase_orders_one_open_per_vehicle", "vehicle_id",
            unique=True, postgresql_where=text("status <> 'cancelada'"),
        ),
        CheckConstraint("total_mxn > 0", name="total_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reservations.id"))
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"),
        default=OrderStatus.PENDIENTE,
        server_default=OrderStatus.PENDIENTE.value,
    )
    total_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # precio congelado al crear la orden

    vehicle: Mapped[Vehicle] = relationship()
    user: Mapped[User] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount_mxn > 0", name="amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    amount_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    method: Mapped[PaymentMethod] = mapped_column(pg_enum(PaymentMethod, "payment_method"))
    status: Mapped[PaymentStatus] = mapped_column(pg_enum(PaymentStatus, "payment_status"))
    reference: Mapped[str] = mapped_column(String(40), unique=True)  # folio simulado
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[PurchaseOrder] = relationship(back_populates="payments")


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), unique=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), unique=True)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    sale_price_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[PurchaseOrder] = relationship()
    vehicle: Mapped[Vehicle] = relationship()
