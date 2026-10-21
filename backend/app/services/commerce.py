"""Reservas, órdenes de compra, pagos simulados y ventas.

Ciclo de vida:

    vehículo:   disponible ──reserva──► reservado ──venta confirmada──► vendido
                    ▲                       │
                    └── cancelación/vencimiento

    reserva:    activa ─► cancelada | expirada | convertida (pasó a orden)
    orden:      pendiente ─pago aprobado─► pagada ─admin confirma─► confirmada
                    └──────────────┴──► cancelada

Cada operación que cambia el estado de un vehículo:
  1. bloquea la fila del vehículo (SELECT ... FOR UPDATE) para serializar peticiones simultáneas,
  2. valida el estado actual,
  3. aplica los cambios y registra el historial en la MISMA transacción,
  4. hace commit y solo entonces publica el evento para los clientes conectados.
Los índices únicos parciales de la BD son una segunda barrera contra duplicados.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core import events
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.models import Payment, PurchaseOrder, Reservation, Sale, User, Vehicle
from app.models.enums import (
    OperationSource, OrderStatus, PaymentStatus, ReservationStatus, VehicleStatus,
)
from app.schemas.commerce import OrderCreate, PaymentCreate, ReservationCreate
from app.services import history
from app.services.vehicles import get_vehicle

OPEN_ORDER_STATUSES = (OrderStatus.PENDIENTE, OrderStatus.PAGADA)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_admin(user: User) -> bool:
    return user.role.name == "admin"


def _lock_vehicle(db: Session, vehicle_id: uuid.UUID) -> Vehicle:
    vehicle = db.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.deleted_at.is_(None)).with_for_update(of=Vehicle)
    )
    if not vehicle:
        raise NotFound("Vehículo no encontrado", "vehicle_not_found")
    return vehicle


def _resolve_customer(db: Session, actor: User, user_id: uuid.UUID | None) -> User:
    """Un cliente siempre opera a su nombre; un admin puede operar a nombre de un cliente."""
    if user_id is None or user_id == actor.id:
        return actor
    if not _is_admin(actor):
        raise Forbidden("No puedes operar a nombre de otro usuario", "forbidden")
    customer = db.get(User, user_id)
    if not customer or not customer.is_active:
        raise NotFound("Cliente no encontrado", "user_not_found")
    return customer


def _vehicle_event(db: Session, vehicle_id: uuid.UUID, reason: str) -> None:
    v = get_vehicle(db, vehicle_id)
    events.publish("vehicle.status_changed", {
        "id": str(v.id), "stock_number": v.stock_number, "status": v.status.value,
        "row_version": v.row_version, "reason": reason,
    })


def _has_open_order(db: Session, vehicle_id: uuid.UUID) -> bool:
    return db.scalar(select(PurchaseOrder.id).where(
        PurchaseOrder.vehicle_id == vehicle_id, PurchaseOrder.status.in_(OPEN_ORDER_STATUSES)
    )) is not None


# ======================= Reservas =======================
def get_reservation(db: Session, reservation_id: uuid.UUID, actor: User) -> Reservation:
    r = db.get(Reservation, reservation_id)
    if not r or (not _is_admin(actor) and r.user_id != actor.id):
        raise NotFound("Reserva no encontrada", "reservation_not_found")
    return r


def list_reservations(db: Session, actor: User, status: ReservationStatus | None, page: int, size: int):
    stmt = select(Reservation)
    if not _is_admin(actor):
        stmt = stmt.where(Reservation.user_id == actor.id)
    if status:
        stmt = stmt.where(Reservation.status == status)
    return _paginate(db, stmt.order_by(Reservation.created_at.desc()), page, size)


def expire_reservations(db: Session, vehicle_id: uuid.UUID | None = None) -> int:
    """Vence las reservas activas cuya fecha ya pasó y libera sus vehículos."""
    stmt = select(Reservation.id, Reservation.vehicle_id).where(
        Reservation.status == ReservationStatus.ACTIVA, Reservation.expires_at <= _now()
    )
    if vehicle_id:
        stmt = stmt.where(Reservation.vehicle_id == vehicle_id)
    expired, released = [], []
    for reservation_id, res_vehicle_id in db.execute(stmt).all():
        # Mismo orden de bloqueo que el resto de operaciones (vehículo -> reserva): evita deadlocks
        vehicle = _lock_vehicle(db, res_vehicle_id)
        r = db.get(Reservation, reservation_id, with_for_update=True, populate_existing=True)
        if r.status != ReservationStatus.ACTIVA or r.expires_at > _now():
            continue  # otra petición ya la canceló o convirtió
        r.status = ReservationStatus.EXPIRADA
        expired.append(r)
        if vehicle.status == VehicleStatus.RESERVADO and not _has_open_order(db, vehicle.id):
            vehicle.status = VehicleStatus.DISPONIBLE
            released.append(vehicle.id)
        history.record(db, operation="reserva_expirada", source=OperationSource.SISTEMA, actor_id=None,
                       vehicle_id=r.vehicle_id, from_status=VehicleStatus.RESERVADO, to_status=vehicle.status,
                       details={"reservation_id": r.id, "expires_at": r.expires_at.isoformat()})
    if expired:
        db.commit()
        for r in expired:
            events.publish("reservation.expired", {"id": str(r.id), "vehicle_id": str(r.vehicle_id),
                                                   "user_id": str(r.user_id)})
        for vid in released:
            _vehicle_event(db, vid, "reserva_expirada")
    return len(expired)


def create_reservation(db: Session, data: ReservationCreate, actor: User, source: OperationSource) -> Reservation:
    settings = get_settings()
    customer = _resolve_customer(db, actor, data.user_id)
    expire_reservations(db, data.vehicle_id)  # una reserva vencida no debe bloquear una nueva

    vehicle = _lock_vehicle(db, data.vehicle_id)
    if vehicle.status != VehicleStatus.DISPONIBLE:
        raise Conflict(f"El vehículo no está disponible (estado: {vehicle.status.value})", "vehicle_not_available")

    hours = min(data.hours or settings.reservation_default_hours, settings.reservation_max_hours)
    reservation = Reservation(vehicle_id=vehicle.id, user_id=customer.id, notes=data.notes,
                              expires_at=_now() + timedelta(hours=hours))
    db.add(reservation)
    vehicle.status = VehicleStatus.RESERVADO
    db.flush()
    history.record(db, operation="reserva_creada", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   from_status=VehicleStatus.DISPONIBLE, to_status=VehicleStatus.RESERVADO,
                   details={"reservation_id": reservation.id, "cliente": customer.email, "horas": hours})
    db.commit()
    events.publish("reservation.created", {"id": str(reservation.id), "vehicle_id": str(vehicle.id),
                                           "user_id": str(customer.id), "stock_number": vehicle.stock_number,
                                           "expires_at": reservation.expires_at.isoformat()})
    _vehicle_event(db, vehicle.id, "reserva_creada")
    return reservation


def cancel_reservation(db: Session, reservation_id: uuid.UUID, actor: User, source: OperationSource) -> Reservation:
    reservation = get_reservation(db, reservation_id, actor)
    vehicle = _lock_vehicle(db, reservation.vehicle_id)
    db.refresh(reservation, with_for_update=True)
    if reservation.status != ReservationStatus.ACTIVA:
        raise Conflict(f"La reserva ya está {reservation.status.value}", "reservation_not_active")

    reservation.status = ReservationStatus.CANCELADA
    reservation.cancelled_at = _now()
    previous = vehicle.status
    if vehicle.status == VehicleStatus.RESERVADO and not _has_open_order(db, vehicle.id):
        vehicle.status = VehicleStatus.DISPONIBLE
    history.record(db, operation="reserva_cancelada", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   from_status=previous, to_status=vehicle.status, details={"reservation_id": reservation.id})
    db.commit()
    events.publish("reservation.cancelled", {"id": str(reservation.id), "vehicle_id": str(vehicle.id),
                                             "user_id": str(reservation.user_id)})
    _vehicle_event(db, vehicle.id, "reserva_cancelada")
    return reservation


# ======================= Órdenes =======================
def get_order(db: Session, order_id: uuid.UUID, actor: User) -> PurchaseOrder:
    order = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.payments))
                      .where(PurchaseOrder.id == order_id))
    if not order or (not _is_admin(actor) and order.user_id != actor.id):
        raise NotFound("Orden no encontrada", "order_not_found")
    return order


def get_sale_for_order(db: Session, order_id: uuid.UUID) -> Sale | None:
    return db.scalar(select(Sale).where(Sale.order_id == order_id))


def list_orders(db: Session, actor: User, status: OrderStatus | None, page: int, size: int):
    stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.payments))
    if not _is_admin(actor):
        stmt = stmt.where(PurchaseOrder.user_id == actor.id)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    return _paginate(db, stmt.order_by(PurchaseOrder.created_at.desc()), page, size)


def create_order(db: Session, data: OrderCreate, actor: User, source: OperationSource) -> PurchaseOrder:
    """Solicitud de compra. Si el cliente tenía una reserva activa del vehículo, se convierte en orden."""
    customer = _resolve_customer(db, actor, data.user_id)
    expire_reservations(db, data.vehicle_id)
    vehicle = _lock_vehicle(db, data.vehicle_id)

    if _has_open_order(db, vehicle.id):
        raise Conflict("El vehículo ya tiene una orden de compra en proceso", "vehicle_has_open_order")
    reservation = db.scalar(select(Reservation).where(
        Reservation.vehicle_id == vehicle.id, Reservation.status == ReservationStatus.ACTIVA
    ))
    if vehicle.status == VehicleStatus.VENDIDO:
        raise Conflict("El vehículo ya fue vendido", "vehicle_sold")
    if reservation and reservation.user_id != customer.id:
        raise Conflict("El vehículo está reservado por otro cliente", "vehicle_reserved_by_other")

    previous = vehicle.status
    order = PurchaseOrder(vehicle_id=vehicle.id, user_id=customer.id, total_mxn=vehicle.price_mxn,
                          reservation_id=reservation.id if reservation else None)
    db.add(order)
    if reservation:
        reservation.status = ReservationStatus.CONVERTIDA
    vehicle.status = VehicleStatus.RESERVADO  # el vehículo queda apartado mientras se paga
    db.flush()
    history.record(db, operation="orden_creada", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   from_status=previous, to_status=vehicle.status,
                   details={"order_id": order.id, "total_mxn": order.total_mxn, "cliente": customer.email,
                            "reservation_id": reservation.id if reservation else None})
    db.commit()
    events.publish("order.created", {"id": str(order.id), "vehicle_id": str(vehicle.id), "user_id": str(customer.id),
                                     "status": order.status.value, "total_mxn": float(order.total_mxn)})
    if previous != vehicle.status:
        _vehicle_event(db, vehicle.id, "orden_creada")
    return get_order(db, order.id, actor)


def pay_order(db: Session, order_id: uuid.UUID, data: PaymentCreate, actor: User,
              source: OperationSource) -> PurchaseOrder:
    """Pago SIMULADO: no se mueve dinero real ni se guarda el número de tarjeta."""
    order = get_order(db, order_id, actor)
    _lock_vehicle(db, order.vehicle_id)
    db.refresh(order, with_for_update=True)
    if order.status != OrderStatus.PENDIENTE:
        raise Conflict(f"La orden está {order.status.value}; solo se pagan órdenes pendientes", "order_not_pending")

    card = (data.card_number or "").replace(" ", "")
    approved = not data.simulate_decline and not card.endswith("0000")
    payment = Payment(order_id=order.id, amount_mxn=order.total_mxn, method=data.method,
                      status=PaymentStatus.APROBADO if approved else PaymentStatus.RECHAZADO,
                      reference=f"SIM-{uuid.uuid4().hex[:12].upper()}")
    db.add(payment)
    if approved:
        order.status = OrderStatus.PAGADA
    db.flush()
    history.record(db, operation="pago_aprobado" if approved else "pago_rechazado", source=source,
                   actor_id=actor.id, vehicle_id=order.vehicle_id,
                   details={"order_id": order.id, "payment_id": payment.id, "reference": payment.reference,
                            "monto_mxn": payment.amount_mxn, "metodo": data.method})
    db.commit()
    events.publish("order.paid" if approved else "order.payment_declined",
                   {"id": str(order.id), "vehicle_id": str(order.vehicle_id), "user_id": str(order.user_id),
                    "status": order.status.value, "payment_reference": payment.reference})
    db.expire(order)
    return get_order(db, order.id, actor)


def cancel_order(db: Session, order_id: uuid.UUID, actor: User, source: OperationSource) -> PurchaseOrder:
    order = get_order(db, order_id, actor)
    vehicle = _lock_vehicle(db, order.vehicle_id)
    db.refresh(order, with_for_update=True)
    if order.status not in OPEN_ORDER_STATUSES:
        raise Conflict(f"La orden ya está {order.status.value}", "order_not_open")
    if order.status == OrderStatus.PAGADA and not _is_admin(actor):
        raise Forbidden("Una orden pagada solo la puede cancelar un administrador", "forbidden")

    order.status = OrderStatus.CANCELADA
    previous = vehicle.status
    vehicle.status = VehicleStatus.DISPONIBLE
    history.record(db, operation="orden_cancelada", source=source, actor_id=actor.id, vehicle_id=vehicle.id,
                   from_status=previous, to_status=vehicle.status, details={"order_id": order.id})
    db.commit()
    events.publish("order.cancelled", {"id": str(order.id), "vehicle_id": str(vehicle.id),
                                       "user_id": str(order.user_id)})
    _vehicle_event(db, vehicle.id, "orden_cancelada")
    return get_order(db, order.id, actor)


def confirm_sale(db: Session, order_id: uuid.UUID, admin: User, source: OperationSource) -> PurchaseOrder:
    """El administrador confirma la venta de una orden pagada: el vehículo queda vendido."""
    order = get_order(db, order_id, admin)
    vehicle = _lock_vehicle(db, order.vehicle_id)
    db.refresh(order, with_for_update=True)
    if order.status != OrderStatus.PAGADA:
        raise Conflict(f"Solo se confirman órdenes pagadas (estado actual: {order.status.value})",
                       "order_not_paid")
    if vehicle.status == VehicleStatus.VENDIDO:
        raise Conflict("El vehículo ya fue vendido", "vehicle_sold")

    sale = Sale(order_id=order.id, vehicle_id=vehicle.id, confirmed_by=admin.id, sale_price_mxn=order.total_mxn)
    db.add(sale)
    order.status = OrderStatus.CONFIRMADA
    previous = vehicle.status
    vehicle.status = VehicleStatus.VENDIDO
    db.flush()
    history.record(db, operation="venta_confirmada", source=source, actor_id=admin.id, vehicle_id=vehicle.id,
                   from_status=previous, to_status=VehicleStatus.VENDIDO,
                   details={"order_id": order.id, "sale_id": sale.id, "precio_mxn": sale.sale_price_mxn})
    db.commit()
    events.publish("sale.confirmed", {"id": str(sale.id), "order_id": str(order.id), "vehicle_id": str(vehicle.id),
                                      "user_id": str(order.user_id), "sale_price_mxn": float(sale.sale_price_mxn)})
    _vehicle_event(db, vehicle.id, "venta_confirmada")
    return get_order(db, order.id, admin)


def list_sales(db: Session, page: int, size: int):
    return _paginate(db, select(Sale).order_by(Sale.sold_at.desc()), page, size)


# ======================= utilidades =======================
def _paginate(db: Session, stmt, page: int, size: int):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(stmt.limit(size).offset((page - 1) * size)).all()
    return items, total
