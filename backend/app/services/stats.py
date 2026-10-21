"""Estadísticas agregadas para el dashboard (calculadas en PostgreSQL, no en el cliente)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    Brand, OperationHistory, PurchaseOrder, Reservation, Sale, User, Vehicle, VehicleModel,
)
from app.models.enums import OrderStatus, ReservationStatus, VehicleStatus

PRICE_BUCKETS = [(0, 300_000, "< $300 mil"), (300_000, 450_000, "$300-450 mil"), (450_000, 600_000, "$450-600 mil"),
                 (600_000, 800_000, "$600-800 mil"), (800_000, 1_000_000, "$800 mil-1 M"), (1_000_000, None, "> $1 M")]


def dashboard(db: Session) -> dict:
    active = Vehicle.deleted_at.is_(None)
    now = datetime.now(timezone.utc)

    by_status = {s.value: 0 for s in VehicleStatus}
    for status, count in db.execute(select(Vehicle.status, func.count()).where(active).group_by(Vehicle.status)):
        by_status[status.value] = count

    in_stock = Vehicle.status.in_([VehicleStatus.DISPONIBLE, VehicleStatus.RESERVADO])
    inventory_value = db.scalar(select(func.coalesce(func.sum(Vehicle.price_mxn), 0)).where(active, in_stock))

    brand_rows = db.execute(
        select(Brand.name, func.count(Vehicle.id), func.avg(Vehicle.price_mxn),
               func.count(Vehicle.id).filter(Vehicle.status == VehicleStatus.DISPONIBLE))
        .join(VehicleModel, VehicleModel.brand_id == Brand.id).join(Vehicle, Vehicle.model_id == VehicleModel.id)
        .where(active).group_by(Brand.name).order_by(func.count(Vehicle.id).desc())
    ).all()
    body_rows = db.execute(
        select(func.coalesce(VehicleModel.body_type, "Sin tipo"), func.count(Vehicle.id))
        .join(Vehicle, Vehicle.model_id == VehicleModel.id).where(active)
        .group_by(VehicleModel.body_type).order_by(func.count(Vehicle.id).desc())
    ).all()

    bucket_expr = case(
        *[((Vehicle.price_mxn >= lo) & (Vehicle.price_mxn < hi), label) if hi else (Vehicle.price_mxn >= lo, label)
          for lo, hi, label in PRICE_BUCKETS]
    )
    bucket_counts = dict(db.execute(select(bucket_expr, func.count()).where(active).group_by(bucket_expr)).all())

    since_30 = now - timedelta(days=30)
    sales_total = db.execute(select(func.count(), func.coalesce(func.sum(Sale.sale_price_mxn), 0))).one()
    sales_30 = db.execute(select(func.count(), func.coalesce(func.sum(Sale.sale_price_mxn), 0))
                          .where(Sale.sold_at >= since_30)).one()
    month = func.date_trunc("month", Sale.sold_at)
    monthly = db.execute(
        select(month, func.count(), func.sum(Sale.sale_price_mxn))
        .where(Sale.sold_at >= now - timedelta(days=365)).group_by(month).order_by(month)
    ).all()

    orders = {s.value: 0 for s in OrderStatus}
    for status, count in db.execute(select(PurchaseOrder.status, func.count()).group_by(PurchaseOrder.status)):
        orders[status.value] = count

    recent = db.execute(
        select(OperationHistory, Vehicle.stock_number, User.full_name)
        .outerjoin(Vehicle, Vehicle.id == OperationHistory.vehicle_id)
        .outerjoin(User, User.id == OperationHistory.actor_user_id)
        .order_by(OperationHistory.created_at.desc(), OperationHistory.id.desc()).limit(10)
    ).all()

    return {
        "vehicles": {"total": sum(by_status.values()), "by_status": by_status,
                     "inventory_value_mxn": float(inventory_value)},
        "by_brand": [{"brand": b, "total": t, "available": a, "avg_price_mxn": round(float(p or 0), 2)}
                     for b, t, p, a in brand_rows],
        "by_body_type": [{"body_type": b, "total": t} for b, t in body_rows],
        "price_ranges": [{"range": label, "total": bucket_counts.get(label, 0)} for *_, label in PRICE_BUCKETS],
        "reservations_active": db.scalar(select(func.count()).where(Reservation.status == ReservationStatus.ACTIVA)),
        "orders_by_status": orders,
        "sales": {
            "total": sales_total[0], "revenue_mxn": float(sales_total[1]),
            "last_30_days": sales_30[0], "revenue_last_30_days_mxn": float(sales_30[1]),
            "monthly": [{"month": m.strftime("%Y-%m"), "total": c, "revenue_mxn": float(r)} for m, c, r in monthly],
        },
        "recent_activity": [
            {"id": h.id, "operation": h.operation, "source": h.source.value, "vehicle_id": h.vehicle_id,
             "stock_number": stock, "actor": actor, "to_status": h.to_status, "created_at": h.created_at}
            for h, stock, actor in recent
        ],
    }
