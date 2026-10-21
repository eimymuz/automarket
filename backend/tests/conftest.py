"""Fixtures de pruebas de la API.

Cada prueba usa UNA conexión con una transacción externa que se revierte al final; los commit()
de los servicios se convierten en SAVEPOINTs. Así las pruebas usan PostgreSQL real (triggers,
índices únicos, FOR UPDATE) sin dejar datos en la base.
"""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core import events
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.session import engine, get_db
from app.main import app
from app.models import Brand, Role, User, Vehicle, VehicleModel
from app.models.enums import FuelType, Transmission

PASSWORD = "Secreta123"


def _db_available() -> bool:
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="PostgreSQL no disponible")


@pytest.fixture
def db():
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", autoflush=False,
                      expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_dir", tmp_path)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def published():
    """Eventos publicados durante la prueba (lo que recibirán los clientes por WebSocket)."""
    captured: list[dict] = []
    events.subscribe(captured.append)
    yield captured
    events.unsubscribe(captured.append)


def make_user(db: Session, role: str, name: str = "Usuario Prueba") -> tuple[User, dict]:
    role_id = db.scalar(select(Role.id).where(Role.name == role))
    user = User(email=f"{role}-{uuid.uuid4().hex[:8]}@test.mx", password_hash=hash_password(PASSWORD),
                full_name=name, role_id=role_id)
    db.add(user)
    db.flush()
    token, _ = create_access_token(user.id, role)
    return user, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(db):
    return make_user(db, "admin", "Admin Prueba")


@pytest.fixture
def customer(db):
    return make_user(db, "cliente", "Cliente Uno")


@pytest.fixture
def other_customer(db):
    return make_user(db, "cliente", "Cliente Dos")


@pytest.fixture
def make_vehicle(db):
    def _make(**overrides) -> Vehicle:
        brand = db.scalar(select(Brand).where(Brand.name == "MarcaPrueba")) or Brand(name="MarcaPrueba")
        model = db.scalar(select(VehicleModel).where(VehicleModel.name == "ModeloPrueba")) or \
            VehicleModel(brand=brand, name="ModeloPrueba", body_type="SUV")
        data = dict(stock_number=f"T-{uuid.uuid4().hex[:8].upper()}", model=model, year=2025, version="Base",
                    price_mxn=Decimal("450000.00"), mileage_km=10000, color="Rojo",
                    transmission=Transmission.AUTOMATICA, fuel_type=FuelType.GASOLINA, engine="2.0L")
        data.update(overrides)
        vehicle = Vehicle(**data)
        db.add(vehicle)
        db.flush()
        return vehicle
    return _make
