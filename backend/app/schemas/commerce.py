import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus, ReservationStatus
from app.schemas.vehicle import VehicleSummary


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str


def _user(u) -> UserSummary:
    return UserSummary(id=u.id, email=u.email, full_name=u.full_name)


# ---------- Reservas ----------
class ReservationCreate(BaseModel):
    vehicle_id: uuid.UUID
    hours: int | None = Field(default=None, ge=1, le=72, description="Vigencia; por defecto 48 h")
    notes: str | None = Field(default=None, max_length=300)
    user_id: uuid.UUID | None = Field(default=None, description="Solo admin: reservar a nombre de un cliente")


class ReservationOut(BaseModel):
    id: uuid.UUID
    status: ReservationStatus
    expires_at: datetime
    cancelled_at: datetime | None
    notes: str | None
    created_at: datetime
    vehicle: VehicleSummary
    user: UserSummary

    @classmethod
    def from_model(cls, r) -> "ReservationOut":
        return cls(
            id=r.id, status=r.status, expires_at=r.expires_at, cancelled_at=r.cancelled_at, notes=r.notes,
            created_at=r.created_at, vehicle=VehicleSummary.from_model(r.vehicle), user=_user(r.user),
        )


# ---------- Órdenes y pagos ----------
class OrderCreate(BaseModel):
    vehicle_id: uuid.UUID
    user_id: uuid.UUID | None = Field(default=None, description="Solo admin: orden a nombre de un cliente")


class PaymentCreate(BaseModel):
    method: PaymentMethod
    card_number: str | None = Field(
        default=None, pattern=r"^[0-9 ]{12,23}$",
        description="Simulado; NO se guarda. Una tarjeta que termina en 0000 se rechaza",
    )
    simulate_decline: bool = Field(default=False, description="Forzar un pago rechazado (pruebas)")


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_mxn: float
    method: PaymentMethod
    status: PaymentStatus
    reference: str
    created_at: datetime


class SaleOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    sale_price_mxn: float
    sold_at: datetime
    confirmed_by: uuid.UUID
    vehicle: VehicleSummary | None = None
    buyer: UserSummary | None = None

    @classmethod
    def from_model(cls, s, include_details: bool = True) -> "SaleOut":
        return cls(
            id=s.id, order_id=s.order_id, sale_price_mxn=float(s.sale_price_mxn), sold_at=s.sold_at,
            confirmed_by=s.confirmed_by,
            vehicle=VehicleSummary.from_model(s.vehicle) if include_details else None,
            buyer=_user(s.order.user) if include_details else None,
        )


class OrderOut(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    total_mxn: float
    reservation_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    vehicle: VehicleSummary
    user: UserSummary
    payments: list[PaymentOut]
    sale: SaleOut | None

    @classmethod
    def from_model(cls, o, sale=None) -> "OrderOut":
        return cls(
            id=o.id, status=o.status, total_mxn=float(o.total_mxn), reservation_id=o.reservation_id,
            created_at=o.created_at, updated_at=o.updated_at, vehicle=VehicleSummary.from_model(o.vehicle),
            user=_user(o.user), payments=[PaymentOut.model_validate(p) for p in o.payments],
            sale=SaleOut.from_model(sale, include_details=False) if sale else None,
        )


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    operation: str
    source: str
    from_status: str | None
    to_status: str | None
    details: dict | None
    created_at: datetime
    stock_number: str | None = None
    actor_name: str | None = None
