"""Pruebas del esquema contra PostgreSQL real.

Cada prueba corre dentro de una transacción que se revierte al final,
así que no deja datos en la base.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import (
    AuditLog, Brand, PurchaseOrder, Reservation, Role, User, Vehicle, VehicleImage, VehicleModel,
)
from app.models.enums import FuelType, Transmission, VehicleStatus

try:
    with engine.connect():
        pass
except OperationalError:
    pytest.skip("PostgreSQL no disponible", allow_module_level=True)


@pytest.fixture
def db():
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def make_vehicle(db: Session, **overrides) -> Vehicle:
    brand = db.scalar(select(Brand).where(Brand.name == "Honda")) or Brand(name="Honda")
    model = VehicleModel(brand=brand, name=f"Civic-{uuid.uuid4().hex[:6]}", body_type="sedán")
    data = dict(
        stock_number=f"T-{uuid.uuid4().hex[:8]}", model=model, year=2024, version="Touring",
        price_mxn=Decimal("589900.00"), mileage_km=12000, color="Blanco",
        transmission=Transmission.CVT, fuel_type=FuelType.GASOLINA, engine="1.5L Turbo",
    )
    data.update(overrides)
    vehicle = Vehicle(**data)
    db.add(vehicle)
    db.flush()
    return vehicle


def make_user(db: Session) -> User:
    role = db.scalar(select(Role).where(Role.name == "cliente"))
    user = User(email=f"{uuid.uuid4().hex[:8]}@test.mx", password_hash="x", full_name="Prueba", role_id=role.id)
    db.add(user)
    db.flush()
    return user


def test_tablas_creadas():
    tablas = set(inspect(engine).get_table_names())
    esperadas = {
        "vehicles", "vehicle_images", "brands", "vehicle_models", "data_sources", "users", "roles",
        "reservations", "purchase_orders", "payments", "sales", "operation_history", "audit_log",
    }
    assert esperadas <= tablas


def test_roles_iniciales(db):
    assert set(db.scalars(select(Role.name))) >= {"admin", "cliente"}


def test_vehiculo_nace_disponible(db):
    v = make_vehicle(db)
    db.refresh(v)
    assert v.status == VehicleStatus.DISPONIBLE
    assert v.created_at is not None and v.row_version == 1


def test_precio_negativo_rechazado(db):
    with pytest.raises(IntegrityError, match="price_positive"):
        with db.begin_nested():
            make_vehicle(db, price_mxn=Decimal("-1"))


def test_no_dos_reservas_activas_mismo_vehiculo(db):
    v, u1, u2 = make_vehicle(db), make_user(db), make_user(db)
    vence = datetime.now(timezone.utc) + timedelta(days=2)
    db.add(Reservation(vehicle_id=v.id, user_id=u1.id, expires_at=vence))
    db.flush()
    with pytest.raises(IntegrityError, match="uq_reservations_one_active_per_vehicle"):
        with db.begin_nested():
            db.add(Reservation(vehicle_id=v.id, user_id=u2.id, expires_at=vence))
            db.flush()


def test_no_dos_ordenes_abiertas_mismo_vehiculo(db):
    v, u1, u2 = make_vehicle(db), make_user(db), make_user(db)
    db.add(PurchaseOrder(vehicle_id=v.id, user_id=u1.id, total_mxn=v.price_mxn))
    db.flush()
    with pytest.raises(IntegrityError, match="uq_purchase_orders_one_open_per_vehicle"):
        with db.begin_nested():
            db.add(PurchaseOrder(vehicle_id=v.id, user_id=u2.id, total_mxn=v.price_mxn))
            db.flush()


def test_una_sola_foto_principal(db):
    v = make_vehicle(db)
    db.add(VehicleImage(vehicle_id=v.id, url="/img/1.jpg", is_primary=True))
    db.flush()
    with pytest.raises(IntegrityError, match="uq_vehicle_images_one_primary"):
        with db.begin_nested():
            db.add(VehicleImage(vehicle_id=v.id, url="/img/2.jpg", is_primary=True))
            db.flush()


def test_auditoria_registra_cambio_de_precio_y_usuario(db):
    actor = str(uuid.uuid4())
    db.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": actor})
    v = make_vehicle(db)
    v.price_mxn = Decimal("549900.00")
    db.flush()

    logs = db.scalars(
        select(AuditLog).where(AuditLog.record_id == str(v.id)).order_by(AuditLog.id)
    ).all()
    assert [l.action for l in logs] == ["INSERT", "UPDATE"]
    assert logs[1].old_data["price_mxn"] == 589900.00
    assert logs[1].new_data["price_mxn"] == 549900.00
    assert logs[1].changed_by == actor
    assert v.row_version == 2  # bloqueo optimista incrementó la versión


def test_auditoria_no_guarda_password(db):
    u = make_user(db)
    log = db.scalar(select(AuditLog).where(AuditLog.record_id == str(u.id)))
    assert "password_hash" not in log.new_data
