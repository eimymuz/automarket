import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_source, require_admin
from app.db.session import get_db
from app.models import OperationHistory, User, Vehicle
from app.models.enums import OperationSource, OrderStatus, ReservationStatus
from app.schemas.commerce import (
    HistoryOut, OrderCreate, OrderOut, PaymentCreate, ReservationCreate, ReservationOut, SaleOut,
)
from app.schemas.common import ErrorOut, Page
from app.services import commerce as svc

ERRORS = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}}
reservations = APIRouter(prefix="/reservations", tags=["Reservas"])
orders = APIRouter(prefix="/orders", tags=["Órdenes y pagos simulados"])
admin_router = APIRouter(tags=["Ventas e historial"])


def _order_out(db: Session, order) -> OrderOut:
    return OrderOut.from_model(order, svc.get_sale_for_order(db, order.id))


# ---------- Reservas ----------
@reservations.post("", response_model=ReservationOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
def create_reservation(data: ReservationCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user), source: OperationSource = Depends(get_source)):
    """Reserva un vehículo **disponible** (48 h por defecto, máximo 72 h). El vehículo pasa a *reservado*.
    Responde **409 vehicle_not_available** si alguien más ya lo reservó."""
    return ReservationOut.from_model(svc.create_reservation(db, data, user, source))


@reservations.get("", response_model=Page[ReservationOut])
def list_reservations(status: ReservationStatus | None = None, page: int = Query(1, ge=1),
                      page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Clientes: sus reservas. Admin: todas."""
    items, total = svc.list_reservations(db, user, status, page, page_size)
    return Page(items=[ReservationOut.from_model(r) for r in items], total=total, page=page, page_size=page_size)


@reservations.get("/{reservation_id}", response_model=ReservationOut, responses=ERRORS)
def get_reservation(reservation_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ReservationOut.from_model(svc.get_reservation(db, reservation_id, user))


@reservations.post("/{reservation_id}/cancel", response_model=ReservationOut, responses=ERRORS)
def cancel_reservation(reservation_id: uuid.UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user), source: OperationSource = Depends(get_source)):
    """Cancela una reserva activa (el dueño o un admin). El vehículo vuelve a *disponible*."""
    return ReservationOut.from_model(svc.cancel_reservation(db, reservation_id, user, source))


# ---------- Órdenes ----------
@orders.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
def create_order(data: OrderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                 source: OperationSource = Depends(get_source)):
    """Solicitud de compra. Toma el precio vigente; si el cliente tenía reserva activa, se convierte en orden."""
    return _order_out(db, svc.create_order(db, data, user, source))


@orders.get("", response_model=Page[OrderOut])
def list_orders(status: OrderStatus | None = None, page: int = Query(1, ge=1),
                page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """Clientes: sus pedidos. Admin: todas las órdenes."""
    items, total = svc.list_orders(db, user, status, page, page_size)
    return Page(items=[_order_out(db, o) for o in items], total=total, page=page, page_size=page_size)


@orders.get("/{order_id}", response_model=OrderOut, responses=ERRORS)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _order_out(db, svc.get_order(db, order_id, user))


@orders.post("/{order_id}/payments", response_model=OrderOut, status_code=status.HTTP_201_CREATED,
             responses=ERRORS)
def pay_order(order_id: uuid.UUID, data: PaymentCreate, db: Session = Depends(get_db),
              user: User = Depends(get_current_user), source: OperationSource = Depends(get_source)):
    """**Pago simulado** (sin dinero real; la tarjeta no se guarda). Aprobado -> orden *pagada*.
    Para simular un rechazo: `simulate_decline: true` o una tarjeta que termine en `0000`."""
    return _order_out(db, svc.pay_order(db, order_id, data, user, source))


@orders.post("/{order_id}/cancel", response_model=OrderOut, responses=ERRORS)
def cancel_order(order_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                 source: OperationSource = Depends(get_source)):
    """Cancela una orden pendiente (cliente) o pagada (solo admin). El vehículo vuelve a *disponible*."""
    return _order_out(db, svc.cancel_order(db, order_id, user, source))


@orders.post("/{order_id}/confirm", response_model=OrderOut, responses=ERRORS)
def confirm_sale(order_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin),
                 source: OperationSource = Depends(get_source)):
    """**Admin.** Confirma la venta de una orden *pagada*: el vehículo pasa a *vendido*."""
    return _order_out(db, svc.confirm_sale(db, order_id, admin, source))


# ---------- Ventas e historial (admin) ----------
@admin_router.get("/sales", response_model=Page[SaleOut])
def list_sales(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), _: User = Depends(require_admin)):
    items, total = svc.list_sales(db, page, page_size)
    return Page(items=[SaleOut.from_model(s) for s in items], total=total, page=page, page_size=page_size)


@admin_router.get("/history", response_model=Page[HistoryOut])
def list_history(operation: str | None = Query(None, max_length=50), source: OperationSource | None = None,
                 vehicle_id: uuid.UUID | None = None, page: int = Query(1, ge=1),
                 page_size: int = Query(50, ge=1, le=100), db: Session = Depends(get_db),
                 _: User = Depends(require_admin)):
    """**Admin.** Historial global de operaciones (lo que alimenta la pantalla Historial)."""
    filters = []
    if operation:
        filters.append(OperationHistory.operation == operation)
    if source:
        filters.append(OperationHistory.source == source)
    if vehicle_id:
        filters.append(OperationHistory.vehicle_id == vehicle_id)
    total = db.scalar(select(func.count()).select_from(OperationHistory).where(*filters))
    rows = db.execute(
        select(OperationHistory, Vehicle.stock_number, User.full_name)
        .outerjoin(Vehicle, Vehicle.id == OperationHistory.vehicle_id)
        .outerjoin(User, User.id == OperationHistory.actor_user_id)
        .where(*filters)
        .order_by(OperationHistory.created_at.desc(), OperationHistory.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    items = [HistoryOut.model_validate(h).model_copy(update={"stock_number": stock, "actor_name": actor})
             for h, stock, actor in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)
